#!/usr/bin/env python3
"""
Basic export example: Export a single Copilot share URL to Markdown.

Prerequisites:
- Run login mode first: python scraper_playwright.py --mode login --url <URL>
- This creates storage_state.json in the repo root

Usage:
    python examples/basic_export.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import scraper modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_playwright import run_export


async def main():
    """Export a single share URL to Markdown."""
    
    # Replace with your share URL
    url = "https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144"
    
    print(f"Exporting: {url}")
    
    try:
        await run_export(url, pdf=False)
        print("\n✓ Export complete!")
        print("  - chat-export.md")
        print("  - page.html (for debugging)")
    except SystemExit as e:
        if e.code == 1:
            print("\n✗ Error: storage_state.json not found")
            print("  Run: python scraper_playwright.py --mode login --url <URL>")
        elif e.code == 2:
            print("\n✗ Error: No messages extracted")
            print("  Check page.html to inspect the rendered page")


if __name__ == "__main__":
    asyncio.run(main())



