# Contributing to GitHub Copilot Chat Exporter

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## How to Contribute

### Reporting Issues

If you encounter bugs or have feature requests:

1. Check existing issues to avoid duplicates
2. Create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Python version and OS
   - Relevant logs or screenshots

### Submitting Pull Requests

1. **Fork the repository**
2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes:**
   - Follow existing code style
   - Add docstrings to new functions
   - Update README if adding features
   - Test your changes locally

4. **Commit your changes:**
   ```bash
   git commit -m "Add: brief description of your changes"
   ```

5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request** with:
   - Clear description of changes
   - Reference to related issues (if any)
   - Screenshots/output examples (if applicable)

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/github-copilot-chat-exporter.git
cd github-copilot-chat-exporter

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
python -m playwright install chromium

# Make your changes and test
python scraper_playwright.py --mode login --url <TEST_URL>
python scraper_playwright.py --mode run --url <TEST_URL>
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Keep functions focused and single-purpose
- Add docstrings for public functions
- Comment non-obvious logic

## Testing

Before submitting:

1. Test both `scraper_playwright.py` and `scraper_requests.py`
2. Verify exports produce valid Markdown
3. Check PDF generation (if applicable)
4. Test with different share URLs
5. Ensure no credentials are committed

## Areas for Contribution

We welcome contributions in:

- **Selector improvements:** GitHub may update their DOM structure
- **Error handling:** Better exception messages and recovery
- **Output formats:** Additional export formats (HTML, DOCX, etc.)
- **Performance:** Faster extraction or batch processing
- **Documentation:** Clarify setup steps, add examples
- **Testing:** Unit tests, integration tests

## Questions?

Feel free to open a discussion issue or reach out via GitHub Issues.

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on the issue, not the person
- Assume good intentions

Thank you for contributing! 🎉



