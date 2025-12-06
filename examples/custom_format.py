#!/usr/bin/env python3
"""
Custom format example: Export with custom Markdown/JSON/HTML formatting.

Prerequisites:
- Run login mode first: python scraper_playwright.py --mode login --url <URL>
- This creates storage_state.json in the repo root

Usage:
    python examples/custom_format.py
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List

# Add parent directory to path to import scraper modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_playwright import Message, extract_from_dom, extract_messages_from_json, STATE_PATH
from playwright.async_api import async_playwright


def format_as_json(messages: List[Message]) -> str:
    """
    Format messages as pretty-printed JSON.
    
    Args:
        messages: List of Message objects
        
    Returns:
        JSON string with indentation
    """
    data = [{"role": msg.role, "content": msg.content} for msg in messages]
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_as_html(messages: List[Message]) -> str:
    """
    Format messages as standalone HTML page.
    
    Args:
        messages: List of Message objects
        
    Returns:
        Complete HTML document string
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <title>Chat Export</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }",
        "    .message { margin: 20px 0; padding: 15px; border-radius: 8px; }",
        "    .user { background: #f0f0f0; }",
        "    .assistant { background: #e3f2fd; }",
        "    .role { font-weight: bold; margin-bottom: 8px; }",
        "    pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Chat Export</h1>",
    ]
    
    for msg in messages:
        role_class = msg.role.lower()
        html_parts.append(f"  <div class='message {role_class}'>")
        html_parts.append(f"    <div class='role'>{msg.role.title()}</div>")
        
        # Simple markdown-to-html for code blocks
        content = msg.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if "```" in content:
            # Wrap code blocks in <pre>
            parts = content.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Inside code block
                    html_parts.append(f"    <pre>{part}</pre>")
                else:
                    html_parts.append(f"    <div>{part}</div>")
        else:
            html_parts.append(f"    <div>{content}</div>")
        
        html_parts.append("  </div>")
    
    html_parts.extend(["</body>", "</html>"])
    return "\n".join(html_parts)


def format_as_plain_text(messages: List[Message]) -> str:
    """
    Format messages as plain text (no Markdown headers).
    
    Args:
        messages: List of Message objects
        
    Returns:
        Plain text with separators
    """
    lines = []
    for msg in messages:
        lines.append("=" * 60)
        lines.append(f"{msg.role.upper()}")
        lines.append("-" * 60)
        lines.append(msg.content.strip())
        lines.append("")
    return "\n".join(lines)


async def main():
    """Export with custom formats."""
    url = "https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144"
    
    if not STATE_PATH.exists():
        print("[error] storage_state.json not found. Run --mode login first.")
        sys.exit(1)
    
    print(f"Exporting: {url}")
    print("Generating custom formats...")
    
    captured_json = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(STATE_PATH))
        page = await context.new_page()
        
        async def handle_response(response):
            try:
                headers = await response.all_headers()
                if "application/json" in headers.get("content-type", ""):
                    text = await response.text()
                    data = json.loads(text)
                    captured_json.append((response.url, data))
            except Exception:
                pass
        
        page.on("response", handle_response)
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # Extract messages
        messages: List[Message] = []
        for _, data in captured_json:
            messages = extract_messages_from_json(data)
            if messages:
                break
        
        if not messages:
            messages = await extract_from_dom(page)
        
        await browser.close()
    
    if not messages:
        print("[error] No messages extracted")
        sys.exit(2)
    
    # Write different formats
    Path("export.json").write_text(format_as_json(messages), encoding="utf-8")
    print("  ✓ Saved: export.json")
    
    Path("export.html").write_text(format_as_html(messages), encoding="utf-8")
    print("  ✓ Saved: export.html")
    
    Path("export.txt").write_text(format_as_plain_text(messages), encoding="utf-8")
    print("  ✓ Saved: export.txt")
    
    print("\n✓ Custom format export complete!")


if __name__ == "__main__":
    asyncio.run(main())

