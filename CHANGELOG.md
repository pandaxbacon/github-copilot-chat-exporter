# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Batch export mode with multiple URLs
- Custom selector configuration for DOM changes
- Export to additional formats (DOCX, plain text)

## [1.0.0] - 2025-12-06

### Added
- **Homebrew formula support**
  - Console script entry point (`copilot-exporter` command)
  - Personal tap for easy installation on macOS/Linux
  - Automated Python environment and Playwright setup

- **CI/CD Pipeline**
  - GitHub Actions workflow for automated testing
  - Multi-OS testing (Ubuntu, macOS, Windows)
  - Multi-Python version testing (3.9, 3.10, 3.11)
  - Codecov integration for code coverage tracking
  - Linting and formatting checks

- **Playwright scraper** (`scraper_playwright.py`)
  - Login mode: headed browser for manual GitHub authentication
  - Run mode: headless export with saved session state
  - JSON API extraction with DOM fallback
  - Markdown export with optional PDF generation
  - Debug output (`page.html`) for troubleshooting

- **Requests scraper** (`scraper_requests.py`)
  - Static HTML parser for publicly accessible pages
  - Login detection and graceful exit when auth required
  - BeautifulSoup-based message extraction

- **Documentation**
  - Comprehensive README with installation, usage, examples
  - R&D notes documenting share page access requirements
  - Contributing guidelines and MIT license
  - Test plan and validation steps

- **Development tools**
  - Python virtual environment setup instructions
  - Pinned dependencies in `requirements.txt`
  - Type hints and docstrings throughout
  - Example scripts for common use cases

### Technical Details
- Python 3.9+ support
- Playwright 1.48.0 for browser automation
- Authentication via `storage_state.json`
- Multiple CSS selector fallbacks for robustness
- Network response capture for API extraction

---

## Release Notes

### [1.0.0] - First Stable Release (2025-12-06)

First stable release of GitHub Copilot Chat Exporter. Provides command-line tools
to export GitHub Copilot shared conversations to Markdown and PDF formats.

**Key Features:**
- ✅ Homebrew installation support (macOS/Linux)
- ✅ `copilot-exporter` command-line tool
- ✅ Authenticated export via Playwright
- ✅ Markdown and PDF output
- ✅ JSON API + DOM extraction strategy
- ✅ Reusable session state

**Known Limitations:**
- Requires manual login (no OAuth or API tokens)
- DOM selectors may need updates if GitHub changes structure
- Single URL export only (batch mode planned for future releases)

**Getting Started (Homebrew):**
```bash
brew tap pandaxbacon/tap
brew install copilot-exporter
copilot-exporter --mode login --url <SHARE_URL>
copilot-exporter --mode run --url <SHARE_URL> --pdf
```

**Getting Started (Manual):**
```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python -m playwright install chromium

# Login once
python scraper_playwright.py --mode login --url <SHARE_URL>

# Export
python scraper_playwright.py --mode run --url <SHARE_URL> --pdf
```

---

