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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

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
    args = parser.parse_args()

    if args.mode == "login":
        asyncio.run(capture_login(args.url))
    else:
        asyncio.run(run_export(args.url, pdf=args.pdf))


if __name__ == "__main__":
    main()
