#!/usr/bin/env python3
"""
Playwright-based exporter for GitHub Copilot share pages.
- mode=login: open headed browser for manual GitHub login, then save storage_state.json
- mode=run: reuse storage_state.json, headless, export Markdown (and optional PDF)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import base64
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright


DEFAULT_URL = "https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144"
STATE_PATH = Path("storage_state.json")
MESSAGE_SELECTORS = [
    "main .message-container",
    "main [data-testid='message-group']",
    "main article[data-testid='chat-message']",
    "main div[data-testid='copilot-chat-message']",
    "main div[data-target='copilot-chat-message']",
    "main li[data-testid='copilot-chat-message']",
]
# Supported attachment file extensions for side panel extraction
SUPPORTED_ATTACHMENTS = [
    '.csv', '.txt', '.json', '.xml', '.yaml', '.yml', '.md',
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs'
]


@dataclass
class Message:
    role: str
    content: str


@dataclass
class AssetCaptureResult:
    image_map: Dict[str, str]
    attachments: List[Dict[str, Any]]
    charts: List[str]
    csv_files: List[Dict[str, Any]]


def slugify(text: str) -> str:
    """Convert arbitrary text to a filesystem-friendly slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "export"


def build_export_folder_name(title: Optional[str], url: str) -> str:
    """Choose a stable folder name from the conversation title, URL, or timestamp."""
    parsed = urlparse(url)
    candidate = slugify(title or "")
    if not candidate and parsed.path:
        candidate = slugify(Path(parsed.path).name)
    if not candidate:
        candidate = datetime.utcnow().strftime("export-%Y%m%d-%H%M%S")
    return candidate


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def infer_extension_from_mime(mime: str) -> str:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "text/plain": ".txt",
        "application/json": ".json",
    }
    return mapping.get(mime.lower(), ".bin")


def unique_filename(
    base_dir: Path, stem: str, ext: str, used: Optional[Set[str]] = None
) -> str:
    """Generate a unique filename within base_dir using a counter suffix."""
    used = used or set()
    counter = 1
    while True:
        candidate = f"{stem}-{counter:03d}{ext}"
        if candidate not in used and not (base_dir / candidate).exists():
            used.add(candidate)
            return candidate
        counter += 1


def filename_from_content_disposition(header: str) -> Optional[str]:
    """Extract filename from Content-Disposition header if present."""
    if not header:
        return None
    match = re.search(r'filename\\*?="?([^";]+)"?', header)
    if match:
        return match.group(1)
    return None


def flatten_content(raw: Any) -> str:
    """
    Recursively flatten nested content structures to plain text.

    Handles JSON API responses where content may be nested in lists, dicts,
    or stored under keys like "content", "text", or "body".

    Args:
        raw: Any structure (str, list, dict, or other) to flatten

    Returns:
        Flattened string representation

    Examples:
        >>> flatten_content("Hello")
        'Hello'
        >>> flatten_content({"content": "World"})
        'World'
        >>> flatten_content([{"text": "A"}, {"text": "B"}])
        'A\\nB'
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "\n".join(filter(None, (flatten_content(item) for item in raw)))
    if isinstance(raw, dict):
        # Common Copilot schemas use "content" or "text"
        for key in ("content", "text", "body"):
            if key in raw:
                return flatten_content(raw[key])
    return str(raw)


async def save_data_uri(
    data_uri: str, images_dir: Path, used_names: Set[str]
) -> Optional[str]:
    """Persist a base64 data URI to disk and return relative path."""
    try:
        header, encoded = data_uri.split(",", 1)
        mime_match = re.search(r"data:(.*?);base64", header)
        mime = mime_match.group(1) if mime_match else "application/octet-stream"
        ext = infer_extension_from_mime(mime)
        filename = unique_filename(images_dir, "img", ext, used_names)
        binary = base64.b64decode(encoded)
        ensure_directory(images_dir)
        (images_dir / filename).write_bytes(binary)
        return f"images/{filename}"
    except Exception:
        return None


async def download_binary(
    request_ctx, url: str, dest_dir: Path, stem: str, used_names: Set[str]
) -> Optional[str]:
    """Download a binary resource via Playwright's request context."""
    try:
        resp = await request_ctx.get(url, timeout=20_000)
        if not resp.ok:
            return None
        content_type = resp.headers.get("content-type", "").split(";")[0]
        ext = infer_extension_from_mime(content_type or "")
        filename = unique_filename(dest_dir, stem, ext, used_names)
        ensure_directory(dest_dir)
        (dest_dir / filename).write_bytes(await resp.body())
        return filename
    except Exception:
        return None


async def capture_images(page, export_root: Path) -> Dict[str, str]:
    """
    Skip image downloads - keep remote URLs in markdown.
    Images will be fetched during PDF generation or viewed remotely in markdown.
    """
    # Return empty map - no URL replacements needed
    return {}


async def capture_attachments(page, export_root: Path) -> List[Dict[str, Any]]:
    """Download attachment links (anchors) when accessible."""
    attachments_dir = export_root / "attachments"
    anchors: List[Dict[str, str]] = await page.eval_on_selector_all(
        "a[href]",
        "(els) => els.map((el) => ({href: el.href || '', download: el.download || '', text: el.textContent || ''}))",
    )
    used_names: Set[str] = set()
    request_ctx = page.context.request
    results: List[Dict[str, Any]] = []

    for anchor in anchors:
        href = (anchor.get("href") or "").strip()
        if not href.lower().startswith(("http://", "https://")):
            continue

        # Skip navigation links (copilot UI, anchor links, etc.)
        if any(nav in href for nav in ['/copilot/c/', '/copilot/agents', '/copilot/spaces', '/spark', '#']):
            continue

        name_hint = anchor.get("download") or Path(urlparse(href).path).name or "attachment"
        stem = slugify(Path(name_hint).stem or "attachment")

        try:
            resp = await request_ctx.get(href, timeout=20_000)
        except Exception:
            # Skip links that fail to download (likely not actual attachments)
            resp = None

        if not resp or not resp.ok:
            downloaded = False
            filename = None
        else:
            content_type = resp.headers.get("content-type", "").split(";")[0].lower()
            disposition = resp.headers.get("content-disposition", "")

            # Skip HTML pages (likely navigation links, not downloadable files)
            if content_type.startswith("text/html") and "attachment" not in disposition.lower():
                downloaded = False
                filename = None
            else:
                cd_name = filename_from_content_disposition(disposition)
                chosen_name = cd_name or name_hint
                ext = Path(chosen_name).suffix or infer_extension_from_mime(content_type or "")
                stem_local = slugify(Path(chosen_name).stem or stem or "attachment")
                filename = unique_filename(attachments_dir, stem_local, ext, used_names)
                ensure_directory(attachments_dir)
                (attachments_dir / filename).write_bytes(await resp.body())
                downloaded = True

        downloaded = filename is not None
        entry: Dict[str, Any] = {
            "name": filename or name_hint or "attachment",
            "url": href,
            "downloaded": downloaded,
        }
        if downloaded:
            entry["local_path"] = f"attachments/{filename}"
        results.append(entry)

    return results


async def capture_file_attachments(page, export_root: Path) -> List[Dict[str, Any]]:
    """Capture file attachments from Copilot workbench panel."""
    try:
        attachments_dir = export_root / "attachments"
        ensure_directory(attachments_dir)
        used_names: Set[str] = set()
        results: List[Dict[str, Any]] = []
        
        print("[info] Looking for file attachment buttons...")
        
        # Find all elements that might contain file attachments
        # 1. <a> tags with supported file extensions
        # 2. Reference token links (user uploads)
        file_buttons = []
        
        # Strategy 1: Find <a> tags with supported extensions
        all_links = await page.query_selector_all('a')
        for link in all_links:
            try:
                text = await link.text_content()
                if text and any(ext in text.lower() for ext in SUPPORTED_ATTACHMENTS):
                    file_buttons.append((link, text.strip()))
            except Exception as e:
                print(f"[debug] Error reading link text: {e}")
                continue
        
        # Strategy 2: Find reference token links specifically
        ref_links = await page.query_selector_all("a[class*='ReferenceToken']")
        for link in ref_links:
            try:
                text = await link.text_content()
                if text and any(ext in text.lower() for ext in SUPPORTED_ATTACHMENTS):
                    # Check if not already in list
                    if not any(text.strip() == existing[1] for existing in file_buttons):
                        file_buttons.append((link, text.strip()))
            except Exception:
                continue
        
        # Strategy 3: Find code block headers with supported file types (Copilot-generated files)
        code_headers = await page.query_selector_all("[class*='CodeBlock'][class*='languageName'], [class*='languageName']")
        for header in code_headers:
            try:
                text = await header.text_content()
                if text and any(ext in text.lower() for ext in SUPPORTED_ATTACHMENTS):
                    # These aren't clickable by themselves, we need the parent figure or container
                    parent = await header.evaluate_handle('el => el.closest("figure, [class*=CodeBlock]")')
                    if parent:
                        # Check if not already in list
                        if not any(text.strip() == existing[1] for existing in file_buttons):
                            file_buttons.append((parent.as_element(), text.strip()))
            except Exception:
                continue
        
        print(f"[info] Found {len(file_buttons)} file attachment buttons")
        
        for file_link, button_text in file_buttons:
            try:
                print(f"[info] Clicking file button: {button_text}")
                await file_link.click()
                
                # Wait for side panel to appear
                await page.wait_for_timeout(2000)
                
                # Check if side panel opened
                side_panel = await page.query_selector('xpath=/html/body/div[1]/div[7]/main/react-app/div/div/div[3]')
                if not side_panel:
                    print(f"[warn] Side panel did not open for: {button_text}")
                    continue
                
                await page.wait_for_timeout(2000)
                
                # Extract content from the side panel
                raw_content = await page.evaluate('''() => {
                    // Try to find content in the side panel
                    const sidePanel = document.evaluate('/html/body/div[1]/div[7]/main/react-app/div/div/div[3]', 
                                                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (!sidePanel) return "";
                    
                    // Look for textboxes with CSV content
                    const textboxes = sidePanel.querySelectorAll('[role="textbox"]');
                    for (const box of textboxes) {
                        const text = box.textContent || box.innerText || '';
                        if (text.includes(',') && text.length > 50) {
                            return text;
                        }
                    }
                    
                    // Try to get all text from the panel
                    const allText = sidePanel.textContent || sidePanel.innerText || '';
                    if (allText.includes(',') && allText.length > 100) {
                        return allText;
                    }
                    
                    return "";
                }''')
                
                if raw_content and len(raw_content) > 50:
                    # Parse filename from button text
                    attachment_filename = button_text.replace('name=', '').strip()
                    
                    # Extract extension from filename
                    ext = Path(attachment_filename).suffix.lower()
                    if not ext or ext not in SUPPORTED_ATTACHMENTS:
                        ext = '.txt'  # Default fallback
                    
                    stem = slugify(Path(attachment_filename).stem)
                    filename = unique_filename(attachments_dir, stem, ext, used_names)
                    
                    # Save the raw file content without parsing
                    (attachments_dir / filename).write_text(raw_content)
                    
                    print(f"[ok] Saved file: {filename} ({len(raw_content)} bytes)")
                    
                    results.append({
                        "name": attachment_filename,
                        "local_path": f"attachments/{filename}",
                        "downloaded": True,
                        "type": ext.lstrip('.')
                    })
                    
                    # Try to close the side panel with timeout
                    try:
                        close_button = await page.wait_for_selector(
                            'button:has-text("Close")', 
                            timeout=2000
                        )
                        if close_button:
                            await close_button.click()
                            await page.wait_for_timeout(500)
                    except Exception:
                        # If close button not found or timeout, just continue
                        pass
                else:
                    print(f"[warn] No content extracted from file button: {button_text}")
                    
            except Exception as e:
                print(f"[warn] Failed to capture file {button_text}: {e}")
        
        return results
    
    except Exception as e:
        print(f"[error] File attachment capture failed: {e}")
        import traceback
        traceback.print_exc()
        return []


async def capture_charts(page, export_root: Path) -> List[str]:
    """Capture canvas and SVG elements as PNG screenshots."""
    charts_dir = export_root / "charts"
    charts: List[str] = []
    ensure_directory(charts_dir)
    used_names: Set[str] = set()

    canvases = await page.query_selector_all("canvas")
    for idx, canvas in enumerate(canvases, start=1):
        filename = unique_filename(charts_dir, "canvas", ".png", used_names)
        try:
            await canvas.screenshot(path=str(charts_dir / filename))
            charts.append(f"charts/{filename}")
        except Exception:
            print("[warn] Failed to capture canvas element")

    svgs = await page.query_selector_all("svg")
    for _idx, svg in enumerate(svgs, start=len(charts) + 1):
        filename = unique_filename(charts_dir, "svg", ".png", used_names)
        try:
            await svg.screenshot(path=str(charts_dir / filename), timeout=5000)
            charts.append(f"charts/{filename}")
        except Exception:
            # Skip SVGs that timeout or fail
            pass

    return charts


def update_markdown_with_assets(
    markdown: str,
    attachments: List[Dict[str, Any]],
) -> str:
    """Insert inline attachment links where CSV files are referenced in markdown."""
    import re
    updated = markdown
    
    # Build a lookup map: filename -> local_path
    attachment_map = {}
    for att in attachments:
        if att.get("downloaded") and att.get("local_path"):
            name = att.get("name", "")
            attachment_map[name] = att.get("local_path")
    
    # First, replace explicit [ATTACHMENT:filename] markers if any
    def replace_attachment_marker(match):
        filename = match.group(1)
        # Match by comparing base names (without extensions and normalized)
        file_base = Path(filename).stem.replace('-', '_').lower()
        
        for att_name, att_path in attachment_map.items():
            att_base = Path(att_name).stem.replace('-', '_').lower()
            if file_base in att_base or att_base in file_base or filename.lower() == att_name.lower():
                return f"📎 **Attachment:** [{filename}]({att_path})"
        return f"📎 **Attachment:** {filename} (not captured)"
    
    updated = re.sub(r'\[ATTACHMENT:([^\]]+)\]', replace_attachment_marker, updated)
    
    # Second, find code blocks with name=*.extension pattern and insert attachment links
    # Pattern: ```name=filename.ext (at start of line)
    def insert_file_link(match):
        full_match = match.group(0)
        filename_with_name = match.group(1).strip()  # e.g., "name=aia_glossary.csv"
        filename = filename_with_name.replace('name=', '').strip()
        
        # Find matching attachment
        for att_name, att_path in attachment_map.items():
            # Match by filename (handle underscores vs hyphens, ignore extension differences)
            att_base = Path(att_name).stem.replace('-', '_').lower()
            file_base = Path(filename).stem.replace('-', '_').lower()
            
            if filename in att_name or att_name in filename or att_base in file_base or file_base in att_base:
                # Insert attachment link right before the code block
                return f"📎 **Attachment:** [{filename}]({att_path})\n\n{full_match}"
        
        # No match, return original
        return full_match
    
    # Match code blocks with name=*.extension pattern (on its own line)
    # Build pattern to match any supported extension
    ext_pattern = '|'.join([re.escape(ext) for ext in SUPPORTED_ATTACHMENTS])
    updated = re.sub(rf'```(name=[^\n]+(?:{ext_pattern}))', insert_file_link, updated, flags=re.MULTILINE)
    
    return updated


def extract_messages_from_json(obj: Any) -> List[Message]:
    """
    Extract chat messages from JSON API responses.

    Walks the JSON structure looking for "messages" arrays containing
    objects with "role" and "content"/"text"/"parts" fields.

    Args:
        obj: JSON object (dict or list) from API response

    Returns:
        List of Message objects with role and content

    Examples:
        >>> data = {"messages": [{"role": "user", "content": "Hello"}]}
        >>> msgs = extract_messages_from_json(data)
        >>> len(msgs)
        1
        >>> msgs[0].role
        'user'
    """
    found: List[Message] = []

    def walk(node: Any) -> None:
        nonlocal found  # noqa: F824
        if isinstance(node, dict):
            if "messages" in node and isinstance(node["messages"], list):
                candidate = []
                for item in node["messages"]:
                    if (
                        isinstance(item, dict)
                        and "role" in item
                        and any(k in item for k in ("content", "text", "parts"))
                    ):
                        content = (
                            item.get("content") or item.get("text") or item.get("parts")
                        )
                        candidate.append(
                            Message(
                                role=str(item["role"]), content=flatten_content(content)
                            )
                        )
                if candidate:
                    found.extend(candidate)
                    return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(obj)
    return found


def messages_to_markdown(messages: List[Message]) -> str:
    """
    Convert a list of messages to clean Markdown format.

    Args:
        messages: List of Message objects with role and content

    Returns:
        Formatted Markdown string with headers and content

    Examples:
        >>> msgs = [Message(role="user", content="Hello"), Message(role="assistant", content="Hi!")]
        >>> md = messages_to_markdown(msgs)
        >>> "## User" in md
        True
        >>> "## Assistant" in md
        True
    """
    lines: List[str] = ["# Chat Export", ""]
    for msg in messages:
        lines.append(f"## {msg.role.title()}")
        lines.append(msg.content.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


async def capture_login(url: str) -> None:
    """
    Launch headed browser for manual GitHub login and save authentication state.

    Opens a visible browser window, navigates to the share URL, waits for the user
    to complete GitHub login, then saves cookies/localStorage to storage_state.json
    for reuse in headless runs.

    Args:
        url: GitHub Copilot share page URL to navigate to

    Side effects:
        - Launches headed Chromium browser
        - Waits for user input (Enter key)
        - Writes storage_state.json to disk

    Examples:
        >>> asyncio.run(capture_login("https://github.com/copilot/share/..."))
        [action] Complete GitHub login in the opened browser, then press Enter...
        [ok] Saved auth state to storage_state.json
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="load")
        print(
            "[action] Complete GitHub login in the opened browser, then press Enter here to save storage_state.json..."
        )
        input()
        await context.storage_state(path=str(STATE_PATH))
        await browser.close()
    print(f"[ok] Saved auth state to {STATE_PATH}")


async def enhance_messages_with_attachments(page, messages: List[Message]) -> List[Message]:
    """
    Enhance message content with attachment references from DOM.
    
    The JSON API doesn't include reference tokens (user-uploaded files),
    so we extract them from the DOM using JavaScript evaluation.
    """
    # Use JavaScript to find all reference tokens and their associated messages
    attachment_info = await page.evaluate('''() => {
        const results = [];
        const containers = document.querySelectorAll('main .message-container');
        
        containers.forEach((container, idx) => {
            // Get message text content
            const userMsg = container.querySelector('[class*="UserMessage"]');
            const markdownBody = container.querySelector('[class*="markdown-body"]');
            const contentEl = userMsg || markdownBody;
            
            if (!contentEl) return;
            
            const messageText = contentEl.textContent.trim().substring(0, 100);
            
            // Find reference tokens
            const refTokens = container.querySelectorAll('[class*="ReferenceToken"][class*="name"]');
            const files = [];
            
            refTokens.forEach(token => {
                const text = token.textContent.trim();
                const supportedExts = ['.csv', '.txt', '.json', '.xml', '.yaml', '.yml', '.md', '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs'];
                if (text && supportedExts.some(ext => text.toLowerCase().includes(ext))) {
                    files.push(text);
                }
            });
            
            if (files.length > 0) {
                results.push({
                    messageStart: messageText,
                    files: files
                });
            }
        });
        
        return results;
    }''')
    
    # Build map
    content_to_refs = {info['messageStart']: info['files'] for info in attachment_info}
    
    # Enhance messages with reference tokens
    enhanced_messages = []
    for msg in messages:
        content = msg.content
        msg_start = content[:100]
        
        # Check if this message has reference tokens
        if msg_start in content_to_refs:
            refs = content_to_refs[msg_start]
            # Prepend attachment markers
            for ref_file in refs:
                content = f"[ATTACHMENT:{ref_file}]\n\n{content}"
        
        enhanced_messages.append(Message(role=msg.role, content=content))
    
    return enhanced_messages


async def extract_from_dom(page) -> List[Message]:
    """
    Extract messages from the rendered DOM when JSON API extraction fails.

    Fallback method that uses CSS selectors to find message containers,
    extracts role (from data attributes or labels), and content text.

    Args:
        page: Playwright Page object with rendered content

    Returns:
        List of Message objects extracted from DOM with inline attachment markers

    Note:
        Tries multiple selectors (MESSAGE_SELECTORS) and stops at first match.
        GitHub may change their DOM structure; update selectors if needed.
    """
    messages: List[Message] = []
    for selector in MESSAGE_SELECTORS:
        elements = await page.query_selector_all(selector)
        if not elements:
            continue
        for el in elements:
            role = (
                await el.get_attribute("data-author")
                or await el.get_attribute("data-role")
                or "unknown"
            )
            label = await el.query_selector("header, h2, h3, h4, .Label, .TextLabel")
            if label:
                text = (await label.inner_text()).strip()
                if text:
                    role = text.split(":")[0] or role
            # Check for reference tokens (user uploaded files) above the message
            # These appear in the ChatReferences section before user messages
            ref_files = []
            ref_spans = await el.query_selector_all(".ReferenceToken-module__name--nPIg4")
            for span in ref_spans:
                try:
                    token_text = (await token.inner_text()).strip()
                    if token_text and any(ext in token_text.lower() for ext in SUPPORTED_ATTACHMENTS):
                        ref_files.append(token_text)
                except Exception:
                    pass
            
            content_el = await el.query_selector("pre, code, .markdown-body") or el
            text = (await content_el.inner_text()).strip()
            
            # Prepend reference tokens at the start of message
            if ref_files:
                for ref_file in ref_files:
                    text = f"[ATTACHMENT:{ref_file}]\n\n{text}"
            
            # Check for file attachments in code blocks within this message (Copilot generated files)
            code_blocks = await el.query_selector_all(".CodeBlock-module__languageName--fxI6n, [class*='languageName']")
            for code_block in code_blocks:
                filename = (await code_block.inner_text()).strip()
                if filename and any(ext in filename.lower() for ext in SUPPORTED_ATTACHMENTS):
                    # Insert marker that will be replaced with actual link later
                    filename_clean = filename.replace('name=', '').strip()
                    text += f"\n\n[ATTACHMENT:{filename_clean}]"
            if text:
                messages.append(Message(role=role, content=text))
        if messages:
            break
    return messages


async def run_export(
    url: str,
    with_assets: bool = False,
    output_base: Optional[Path] = None,
) -> None:
    """
    Export a Copilot share page to Markdown with inline attachments using saved auth.

    Runs headless Playwright with storage_state.json for authentication, captures
    JSON API responses and DOM content, then exports to chat-export.md with
    inline attachment links.

    Args:
        url: GitHub Copilot share page URL to export
        with_assets: If True, capture attachments to attachments/ folder
        output_base: Base directory for exports

    Side effects:
        - Requires storage_state.json (from --mode login)
        - Writes chat-export.md
        - Optionally captures attachments to attachments/
        - Writes page.html for debugging
        - Exits with code 1 if auth missing, 2 if no messages extracted

    Examples:
        >>> asyncio.run(run_export("https://github.com/copilot/share/...", with_assets=True))
        [ok] Wrote chat-export.md
    """
    if not STATE_PATH.exists():
        print(f"[error] {STATE_PATH} not found. Run with --mode login first.")
        sys.exit(1)

    captured_json: List[Tuple[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(STATE_PATH))
        page = await context.new_page()

        async def handle_response(response):
            """Capture JSON API responses for message extraction."""
            try:
                headers = await response.all_headers()
                if "application/json" in headers.get("content-type", ""):
                    text = await response.text()
                    data = json.loads(text)
                    captured_json.append((response.url, data))
            except Exception:
                return

        page.on("response", handle_response)

        await page.goto(url, wait_until="load", timeout=60000)
        await page.wait_for_timeout(5000)  # Allow JS to settle

        html = await page.content()

        # Try JSON extraction first, fallback to DOM
        messages: List[Message] = []
        for _, data in captured_json:
            messages = extract_messages_from_json(data)
            if messages:
                break

        if not messages:
            messages = await extract_from_dom(page)

        if not messages:
            print("[warn] No messages extracted. Inspect page.html or network logs.")
            await browser.close()
            sys.exit(2)
        
        # Enhance messages with DOM-based attachment references
        # (JSON API doesn't include reference tokens, so we need to extract them from DOM)
        messages = await enhance_messages_with_attachments(page, messages)

        export_root = Path(".")
        if with_assets:
            title = await page.title()
            folder = build_export_folder_name(title, url)
            base = Path(output_base) if output_base else Path("output")
            export_root = ensure_directory(base / folder)
            ensure_directory(export_root / "attachments")

        debug_path = export_root / "page.html"
        debug_path.write_text(html, encoding="utf-8")

        markdown = messages_to_markdown(messages)

        if with_assets:
            await capture_images(page, export_root)  # No-op, kept for potential future use
            attachments = await capture_attachments(page, export_root)
            file_attachments = await capture_file_attachments(page, export_root)
            # Merge file attachments into attachments list
            attachments.extend(file_attachments)
            markdown = update_markdown_with_assets(markdown, attachments)

        md_path = export_root / "chat-export.md"
        md_path.write_text(markdown, encoding="utf-8")
        print(f"[ok] Wrote {md_path}")

        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Playwright exporter for Copilot share pages."
    )
    parser.add_argument(
        "--mode",
        choices=["login", "run"],
        default="run",
        help="login: headed auth, run: headless export",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Share URL to load")
    parser.add_argument(
        "--with-assets",
        "--capture-assets",
        dest="with_assets",
        action="store_true",
        help="Download images, attachments, and charts to local folders",
    )
    args = parser.parse_args()

    if args.mode == "login":
        asyncio.run(capture_login(args.url))
    else:
        asyncio.run(
            run_export(
                args.url,
                with_assets=args.with_assets,
                output_base=Path("output") if args.with_assets else Path("."),
            )
        )


if __name__ == "__main__":
    main()
