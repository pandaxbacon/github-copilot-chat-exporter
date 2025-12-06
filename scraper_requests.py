#!/usr/bin/env python3
"""
Minimal static scraper for GitHub Copilot share pages.
Only works if the share page is publicly reachable without login.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import List

import requests
from bs4 import BeautifulSoup


DEFAULT_URL = "https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144"


@dataclass
class Message:
    role: str
    content: str


def fetch_html(url: str) -> requests.Response:
    """
    Fetch HTML content from a URL following redirects.

    Args:
        url: Full URL to fetch

    Returns:
        requests.Response object with final URL and content

    Raises:
        requests.RequestException: On network errors or timeouts
    """
    session = requests.Session()
    resp = session.get(url, allow_redirects=True, timeout=20)
    return resp


def looks_like_login(resp: requests.Response) -> bool:
    """
    Detect if the response is a login page or redirect.

    Checks both the final URL and page content for login indicators.

    Args:
        resp: requests.Response from fetch_html()

    Returns:
        True if page appears to require authentication

    Examples:
        >>> resp = fetch_html("https://github.com/copilot/share/...")
        >>> looks_like_login(resp)
        True  # if redirected to login
    """
    url = resp.url.lower()
    if "/login" in url or "github.com/login" in url:
        return True
    text = resp.text.lower()
    return "sign in to github" in text or "login" in text


def parse_messages(html: str) -> List[Message]:
    """
    Parse chat messages from static HTML using BeautifulSoup.

    Only works if GitHub rendered the chat content server-side.
    Most share pages require JavaScript and authentication.

    Args:
        html: Raw HTML string from response

    Returns:
        List of Message objects extracted from DOM

    Note:
        Tries multiple CSS selectors and stops at first match.
        Returns empty list if no messages found.
    """
    soup = BeautifulSoup(html, "html.parser")

    selectors = [
        "main [data-testid='message-group']",
        "main article[data-testid='chat-message']",
        "main div[data-testid='copilot-chat-message']",
        "main div[data-target='copilot-chat-message']",
    ]

    messages: List[Message] = []
    for selector in selectors:
        for el in soup.select(selector):
            role = el.get("data-author") or el.get("data-role")
            # Only try to extract role from text if no data attribute found
            if not role:
                role_text = el.get_text(strip=True).split("\n", 1)[0]
                if role_text and len(role_text) < 40:
                    role = role_text.split(":")[0]
            role = role or "unknown"
            content_el = el.select_one("pre, code, .markdown-body") or el
            content = content_el.get_text("\n", strip=True)
            if content:
                messages.append(Message(role=role, content=content))
        if messages:
            break
    return messages


def messages_to_markdown(messages: List[Message]) -> str:
    """
    Convert messages to clean Markdown format.

    Args:
        messages: List of Message objects

    Returns:
        Formatted Markdown string with headers for each role

    Examples:
        >>> msgs = [Message(role="user", content="Hello")]
        >>> md = messages_to_markdown(msgs)
        >>> "## User" in md
        True
    """
    lines: List[str] = ["# Chat Export", ""]
    for msg in messages:
        lines.append(f"## {msg.role.title()}")
        lines.append(msg.content.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    """
    Main CLI entry point for static HTML scraping.

    Fetches the share URL, checks for login redirects, parses messages
    from static HTML, and exports to chat-export.md.

    Returns:
        0: Success
        1: Login required (use Playwright scraper instead)
        2: No messages found (likely JS-rendered page)

    Examples:
        $ python scraper_requests.py --url https://github.com/copilot/share/...
        [warn] Page redirected to login. Static scraping will not work.
    """
    parser = argparse.ArgumentParser(
        description="Static HTML scraper for Copilot share pages."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Share URL to fetch")
    args = parser.parse_args()

    resp = fetch_html(args.url)
    print(f"[info] GET {args.url} -> {resp.status_code} ({resp.url})")

    if looks_like_login(resp):
        print(
            "[warn] Page redirected to login or shows a login form. Static scraping will not work."
        )
        return 1

    messages = parse_messages(resp.text)
    if not messages:
        print(
            "[warn] No chat content found in static HTML; the page likely renders content client-side."
        )
        return 2

    markdown = messages_to_markdown(messages)
    with open("chat-export.md", "w", encoding="utf-8") as fh:
        fh.write(markdown)
    print("[ok] Wrote chat-export.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
