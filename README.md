# ✨ GitHub Copilot Chat Exporter ✨

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![Playwright](https://img.shields.io/badge/playwright-1.48.0-green)
[![Homebrew](https://img.shields.io/badge/homebrew-pandaxbacon%2Ftap-orange)](https://github.com/pandaxbacon/homebrew-tap)

**Export GitHub Copilot shared conversations to clean Markdown and PDF. No API key required!**

A Python-based toolkit to extract and archive GitHub Copilot chat share pages with full authentication support and multiple output formats.

## Features

* ✅ Export Copilot shared conversations to Markdown and PDF
* ✅ Authenticated access via manual login (saves reusable session state)
* ✅ Headless automation with Playwright
* ✅ Fallback static scraper for public pages
* ✅ JSON API extraction with DOM fallback
* ✅ Debugging artifacts (`page.html`, network logs)
* ✅ Clean, readable output format
* ✅ Works on macOS, Linux, and Windows

## Installation

### macOS/Linux (Homebrew) - Recommended

```bash
brew tap pandaxbacon/tap
brew install github-copilot-chat-exporter
```

That's it! The `copilot-exporter` command is now available.

### All Platforms (Manual Setup)

#### Prerequisites

* Python 3.9 or higher
* pip (Python package installer)

#### Setup

1. **Create a virtual environment:**

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Quick Start

### Homebrew Users

1. **Authenticate (One-time setup):**

```bash
copilot-exporter --mode login --url https://github.com/copilot/share/YOUR-SHARE-ID
```

* A browser window will open
* Sign in to GitHub
* Press **Enter** in the terminal to save authentication

2. **Export Conversations:**

```bash
# Markdown only
copilot-exporter --mode run --url https://github.com/copilot/share/YOUR-SHARE-ID

# With PDF
copilot-exporter --mode run --url https://github.com/copilot/share/YOUR-SHARE-ID --pdf
```

### Manual Setup Users

1. **Authenticate (One-time setup):**

```bash
python scraper_playwright.py --mode login --url https://github.com/copilot/share/YOUR-SHARE-ID
```

* A browser window will open
* Sign in to GitHub
* Press **Enter** in the terminal to save `storage_state.json`

2. **Export Conversations:**

```bash
python scraper_playwright.py --mode run --url https://github.com/copilot/share/YOUR-SHARE-ID

# With PDF
python scraper_playwright.py --mode run --url https://github.com/copilot/share/YOUR-SHARE-ID --pdf
```

### Output Files

* `chat-export.md` - Clean Markdown format
* `chat-export.pdf` - Rendered PDF (if `--pdf` flag is used)
* `page.html` - Full page HTML for debugging
* `storage_state.json` - Saved authentication state (reusable)

## Usage

### Playwright Scraper (Recommended)

The Playwright-based scraper supports authenticated access and renders JavaScript-heavy pages.

#### Authentication Mode

```bash
python scraper_playwright.py --mode login --url <SHARE_URL>
```

Opens a headed browser for manual GitHub login, then saves authentication to `storage_state.json`.

#### Export Mode

```bash
python scraper_playwright.py --mode run --url <SHARE_URL> [--pdf]
```

Runs headless using saved authentication. Exports to Markdown and optionally PDF.

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--mode` | `login` or `run` | `run` |
| `--url` | GitHub Copilot share URL | Sample URL |
| `--pdf` | Generate PDF alongside Markdown | `False` |

### Requests Scraper (Public pages only)

For publicly accessible share pages (no authentication required):

```bash
python scraper_requests.py --url <SHARE_URL>
```

**Note:** This will exit with a warning if the page requires login. Use the Playwright scraper for authenticated pages.

## Examples

### Basic Export

```python
# Assuming storage_state.json exists from login
import asyncio
from pathlib import Path
from scraper_playwright import run_export

asyncio.run(run_export(
    url="https://github.com/copilot/share/YOUR-SHARE-ID",
    pdf=False
))
```

### Batch Export Multiple URLs

```python
import asyncio
from scraper_playwright import run_export

urls = [
    "https://github.com/copilot/share/ID-1",
    "https://github.com/copilot/share/ID-2",
    "https://github.com/copilot/share/ID-3",
]

async def batch_export():
    for url in urls:
        await run_export(url, pdf=True)
        print(f"✓ Exported {url}")

asyncio.run(batch_export())
```

## Output Format

### Markdown Structure

```markdown
# Chat Export

## User
we should not pursue a perfect cut
instead we may run multiple runs … and then add another workflow at the end to judge and vote which cut is the best

## Copilot
That's exactly the right instinct:
- There isn't one optimal chunking for all tasks.
- You've already seen two "valid but different" interpretations of the same document.
...
```

### PDF Output

When `--pdf` is specified, a formatted PDF is generated with:
* Full conversation history
* Proper code block formatting
* Readable typography
* A4 page format

## Troubleshooting

### "storage_state.json not found"

**Solution:** Run the login mode first:

```bash
python scraper_playwright.py --mode login --url <SHARE_URL>
```

### Empty or missing messages

**Possible causes:**

1. **Selectors changed:** GitHub may have updated the page structure
   * Check `page.html` to inspect the rendered DOM
   * Update `MESSAGE_SELECTORS` in `scraper_playwright.py`

2. **Network timing:** Page didn't fully load
   * Increase wait timeout in `run_export()` function
   * Run in headed mode (`headless=False`) to visually confirm rendering

### "Page redirected to login"

**Cause:** Authentication expired or not captured

**Solution:** Re-run login mode to refresh `storage_state.json`

## Platform Support

| Platform  | Status          |
| --------- | --------------- |
| ✅ macOS   | Fully supported |
| ✅ Linux   | Fully supported |
| ✅ Windows | Fully supported |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

* Built with [Playwright](https://playwright.dev/) for browser automation
* Inspired by the need to archive AI-assisted development conversations

## Support

* 📖 Documentation: See [developer-notes/](developer-notes/) for R&D details
* 🐛 Issues: Report on GitHub Issues
* ⭐ Like this project? Give it a star!

---

**Made with ❤️ for developers who want to own their AI conversation history**

