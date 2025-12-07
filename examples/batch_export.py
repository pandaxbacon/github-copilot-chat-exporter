#!/usr/bin/env python3
"""
Batch export example: Export multiple Copilot share URLs sequentially.

Prerequisites:
- Run login mode first: python scraper_playwright.py --mode login --url <URL>
- This creates storage_state.json in the repo root

Usage:
    python examples/batch_export.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import scraper modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_playwright import run_export


# List of share URLs to export
URLS = [
    "https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144",
    # Add more URLs here:
    # "https://github.com/copilot/share/another-id",
    # "https://github.com/copilot/share/yet-another-id",
]


async def export_with_custom_name(url: str, index: int, pdf: bool = False):
    """
    Export a URL and rename output files with timestamp and index.
    
    Args:
        url: Share URL to export
        index: Numeric index for this export
        pdf: Whether to also generate PDF
    """
    print(f"\n[{index + 1}/{len(URLS)}] Exporting: {url}")
    
    try:
        await run_export(url, pdf=pdf)
        
        # Rename outputs with timestamp and index
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = f"chat-export-{timestamp}-{index + 1}"
        
        md_src = Path("chat-export.md")
        md_dst = Path(f"{base_name}.md")
        if md_src.exists():
            md_src.rename(md_dst)
            print(f"  ✓ Saved: {md_dst}")
        
        if pdf:
            pdf_src = Path("chat-export.pdf")
            pdf_dst = Path(f"{base_name}.pdf")
            if pdf_src.exists():
                pdf_src.rename(pdf_dst)
                print(f"  ✓ Saved: {pdf_dst}")
        
        html_src = Path("page.html")
        html_dst = Path(f"{base_name}.html")
        if html_src.exists():
            html_src.rename(html_dst)
            
    except SystemExit as e:
        if e.code == 1:
            print(f"  ✗ Error: storage_state.json not found")
        elif e.code == 2:
            print(f"  ✗ Error: No messages extracted from {url}")


async def main():
    """Batch export multiple URLs."""
    print(f"Starting batch export of {len(URLS)} URL(s)...")
    print("=" * 60)
    
    for i, url in enumerate(URLS):
        await export_with_custom_name(url, i, pdf=True)
        
        # Brief delay between exports to be respectful to servers
        if i < len(URLS) - 1:
            await asyncio.sleep(2)
    
    print("\n" + "=" * 60)
    print(f"✓ Batch export complete! Processed {len(URLS)} URL(s)")


if __name__ == "__main__":
    asyncio.run(main())



