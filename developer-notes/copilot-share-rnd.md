# Copilot share export R&D (2025-12-06)

## Access checks
- `curl -I https://github.com/copilot/share/402e4282-01e0-8402-a111-3e4244516144` returns `302` to `https://github.com/login?return_to=...`.
- Following redirects lands on the GitHub login page; raw HTML is the standard login form (no chat content present).
- Headful navigation shows the same login experience; no conversation DOM is present without authentication.
- Probing `https://api.githubcopilot.com/share/<id>` returns `404` without auth; no unauthenticated JSON endpoint was observed.

## Implications
- Static requests scraping will not work unless the page is publicly reachable without login (not the case for the sample).
- Browser automation is required with an authenticated GitHub session.
- Auth can be safely reused via Playwright `storage_state.json` captured after a manual login in a headed session.

## Working plan
- Provide a requests scraper that simply detects login redirects and exits with a clear warning.
- Provide a Playwright scraper with two modes:
  - `--mode login` (headed) for manual GitHub login, saving `storage_state.json`.
  - `--mode run` (headless) reusing the saved storage, capturing the rendered DOM, exporting Markdown, and optionally PDF.
- Extraction strategy in Playwright:
  - First, inspect captured JSON responses for a `messages` array with `role` and `content`/`text`/`parts`.
  - Fallback to DOM selectors: `main [data-testid='message-group']`, `main article[data-testid='chat-message']`, `main div[data-testid='copilot-chat-message']`, `main div[data-target='copilot-chat-message']`, `main li[data-testid='copilot-chat-message']`.
  - Save `page.html` for debugging when selectors/API responses change.

## Headless vs. headful
- Login requires headful/manual interaction.
- After login is captured, headless execution is sufficient for export (wait for `networkidle` and a short settle delay).
- If exports return empty, rerun in headed mode to visually confirm the chat renders, then inspect `page.html`/network logs for updated selectors.


