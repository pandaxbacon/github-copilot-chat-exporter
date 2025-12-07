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
import os
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from playwright.async_api import async_playwright


DEFAULT_URL = "https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144"
STATE_PATH = Path("storage_state.json")
MESSAGE_SELECTORS = [
    "main [data-testid='message-group']",
    "main article[data-testid='chat-message']",
    "main div[data-testid='copilot-chat-message']",
    "main div[data-target='copilot-chat-message']",
    "main li[data-testid='copilot-chat-message']",
]


@dataclass
class Message:
    role: str
    content: str


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


async def extract_from_dom(page) -> List[Message]:
    """
    Extract messages from the rendered DOM when JSON API extraction fails.

    Fallback method that uses CSS selectors to find message containers,
    extracts role (from data attributes or labels), and content text.

    Args:
        page: Playwright Page object with rendered content

    Returns:
        List of Message objects extracted from DOM

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
            content_el = await el.query_selector("pre, code, .markdown-body") or el
            text = (await content_el.inner_text()).strip()
            if text:
                messages.append(Message(role=role, content=text))
        if messages:
            break
    return messages


async def run_export(url: str, pdf: bool) -> None:
    """
    Export a Copilot share page to Markdown (and optionally PDF) using saved auth.

    Runs headless Playwright with storage_state.json for authentication, captures
    JSON API responses and DOM content, then exports to chat-export.md and
    optionally chat-export.pdf.

    Args:
        url: GitHub Copilot share page URL to export
        pdf: If True, also generate chat-export.pdf

    Side effects:
        - Requires storage_state.json (from --mode login)
        - Writes chat-export.md, optionally chat-export.pdf
        - Writes page.html for debugging
        - Exits with code 1 if auth missing, 2 if no messages extracted

    Examples:
        >>> asyncio.run(run_export("https://github.com/copilot/share/...", pdf=True))
        [ok] Wrote chat-export.md
        [ok] Wrote chat-export.pdf
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

        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)  # Allow JS to settle

        html = await page.content()
        Path("page.html").write_text(html, encoding="utf-8")

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

        markdown = messages_to_markdown(messages)
        Path("chat-export.md").write_text(markdown, encoding="utf-8")
        print("[ok] Wrote chat-export.md")

        if pdf:
            await page.pdf(path="chat-export.pdf", format="A4", print_background=True)
            print("[ok] Wrote chat-export.pdf")

        await browser.close()


async def capture_images(page, output_dir: Path) -> Dict[str, str]:
    """
    Download all images from the page and save to output_dir/images/
    Returns mapping of original URL -> local path for Markdown replacement.
    """
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    image_map = {}
    img_elements = await page.query_selector_all("main img")

    for idx, img in enumerate(img_elements, 1):
        src = await img.get_attribute("src")
        if not src or src.startswith("data:"):
            continue

        try:
            # Download image with browser context (includes auth cookies)
            response = await page.request.get(src)
            if response.ok:
                content = await response.body()
                # Get extension from URL
                ext = src.split(".")[-1].split("?")[0][:4] or "png"
                filename = f"image-{idx:03d}.{ext}"
                (images_dir / filename).write_bytes(content)
                image_map[src] = f"images/{filename}"
                print(f"  ✓ Saved {filename}")
        except Exception as e:
            print(f"  ✗ Failed to download {src}: {e}")

    return image_map


async def capture_attachments(page, output_dir: Path) -> List[Dict]:
    """
    Extract file attachment metadata and attempt download.
    """
    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(exist_ok=True)

    attachments = []

    # Try multiple selectors for attachments
    selectors = [
        "a[download]",
        '[data-testid="attachment"]',
        'a[href*="/files/"]',
        ".attachment-link",
    ]

    for selector in selectors:
        elements = await page.query_selector_all(selector)
        for el in elements:
            href = await el.get_attribute("href")
            text = (await el.inner_text()).strip()

            if href:
                attachments.append(
                    {
                        "name": text or f"attachment-{len(attachments)+1}",
                        "url": href,
                        "downloaded": False,
                    }
                )

    # Try to download attachments
    for att in attachments:
        try:
            response = await page.request.get(att["url"])
            if response.ok:
                content = await response.body()
                # Sanitize filename
                safe_name = att["name"].replace("/", "-").replace("\\", "-")
                (attachments_dir / safe_name).write_bytes(content)
                att["downloaded"] = True
                print(f"  ✓ Downloaded {safe_name}")
        except Exception as e:
            print(f"  ✗ Failed to download {att['name']}: {e}")

    return attachments


async def capture_charts(page, output_dir: Path) -> List[str]:
    """
    Screenshot canvas elements and embedded visualizations.
    """
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(exist_ok=True)

    chart_files = []

    # Find canvas elements
    canvases = await page.query_selector_all("main canvas")
    for idx, canvas in enumerate(canvases, 1):
        filename = f"chart-{idx:03d}.png"
        try:
            await canvas.screenshot(path=str(charts_dir / filename))
            chart_files.append(f"charts/{filename}")
            print(f"  ✓ Captured {filename}")
        except Exception as e:
            print(f"  ✗ Failed to capture canvas: {e}")

    # Find SVG visualizations (with dimensions, likely charts not icons)
    svgs = await page.query_selector_all("main svg[width][height]")
    for idx, svg in enumerate(svgs, 1):
        filename = f"svg-{idx:03d}.png"
        try:
            await svg.screenshot(path=str(charts_dir / filename))
            chart_files.append(f"charts/{filename}")
            print(f"  ✓ Captured {filename}")
        except Exception as e:
            print(f"  ✗ Failed to capture SVG: {e}")

    return chart_files


def update_markdown_with_assets(
    markdown: str, image_map: Dict[str, str], attachments: List[Dict], charts: List[str]
) -> str:
    """
    Update Markdown to reference downloaded images and add attachment/chart sections.
    """
    # Replace image URLs with local paths
    for original_url, local_path in image_map.items():
        markdown = markdown.replace(original_url, local_path)

    # Add attachments section
    if attachments:
        markdown += "\n\n## Attachments\n\n"
        for att in attachments:
            status = "✓" if att["downloaded"] else "✗ (download failed)"
            markdown += f"- [{att['name']}]({att['url']}) {status}\n"

    # Add charts section
    if charts:
        markdown += "\n\n## Charts & Visualizations\n\n"
        for chart_path in charts:
            markdown += f"![Chart]({chart_path})\n\n"

    return markdown


async def export_with_assets(url: str, pdf: bool) -> None:
    """
    Export with all rich content (images, attachments, charts) as ZIP archive.
    """
    if not STATE_PATH.exists():
        print(f"[error] {STATE_PATH} not found. Run with --mode login first.")
        sys.exit(1)

    output_dir = Path("export_output")
    if output_dir.exists():
        import shutil

        shutil.rmtree(output_dir)
    output_dir.mkdir(exist_ok=True)

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

        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)  # Allow JS to settle

        print("[1/6] Extracting messages...")
        # Try JSON extraction first, fallback to DOM
        messages: List[Message] = []
        for _, data in captured_json:
            messages = extract_messages_from_json(data)
            if messages:
                break

        if not messages:
            messages = await extract_from_dom(page)

        if not messages:
            print("[error] No messages extracted. Inspect page.html.")
            await browser.close()
            sys.exit(2)

        markdown = messages_to_markdown(messages)

        print(f"[2/6] Downloading images...")
        image_map = await capture_images(page, output_dir)

        print(f"[3/6] Downloading attachments...")
        attachments = await capture_attachments(page, output_dir)

        print(f"[4/6] Capturing charts...")
        charts = await capture_charts(page, output_dir)

        print(f"[5/6] Updating Markdown...")
        markdown = update_markdown_with_assets(markdown, image_map, attachments, charts)
        (output_dir / "chat-export.md").write_text(markdown, encoding="utf-8")

        if pdf:
            await page.pdf(
                path=str(output_dir / "chat-export.pdf"),
                format="A4",
                print_background=True,
            )
            print("  ✓ Generated PDF")

        # Save page.html for debugging
        html = await page.content()
        (output_dir / "page.html").write_text(html, encoding="utf-8")

        await browser.close()

        print(f"[6/6] Creating ZIP archive...")
        zip_path = Path("chat-export-full.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(output_dir)
                    zipf.write(file_path, arcname)

        print(f"\n✓ Export complete: {zip_path}")
        print(f"  - {len(messages)} messages")
        print(f"  - {len(image_map)} images")
        print(f"  - {len(attachments)} attachments")
        print(f"  - {len(charts)} charts/visualizations")


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
        "--pdf", action="store_true", help="Render PDF alongside Markdown"
    )
    parser.add_argument(
        "--with-assets",
        action="store_true",
        help="Include images, attachments, and charts (exports as ZIP)",
    )
    args = parser.parse_args()

    if args.mode == "login":
        asyncio.run(capture_login(args.url))
    else:
        if args.with_assets:
            asyncio.run(export_with_assets(args.url, pdf=args.pdf))
        else:
            asyncio.run(run_export(args.url, pdf=args.pdf))


if __name__ == "__main__":
    main()
