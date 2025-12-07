"""Tests for scraper_requests.py"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_requests import (
    Message,
    looks_like_login,
    parse_messages,
    messages_to_markdown,
)


class TestLooksLikeLogin:
    """Tests for looks_like_login function"""

    def test_login_url_with_login_path(self):
        mock_response = Mock()
        mock_response.url = "https://github.com/login"
        mock_response.text = ""
        assert looks_like_login(mock_response) is True

    def test_login_url_with_github_login(self):
        mock_response = Mock()
        mock_response.url = "https://github.com/login?return_to=..."
        mock_response.text = ""
        assert looks_like_login(mock_response) is True

    def test_login_content_with_sign_in(self):
        mock_response = Mock()
        mock_response.url = "https://github.com/page"
        mock_response.text = "<html>Sign in to GitHub</html>"
        assert looks_like_login(mock_response) is True

    def test_login_content_with_login_text(self):
        mock_response = Mock()
        mock_response.url = "https://github.com/page"
        mock_response.text = "<html>Please login to continue</html>"
        assert looks_like_login(mock_response) is True

    def test_not_login_page(self):
        mock_response = Mock()
        mock_response.url = "https://github.com/copilot/share/abc"
        mock_response.text = "<html>Chat content here</html>"
        assert looks_like_login(mock_response) is False


class TestParseMessages:
    """Tests for parse_messages function"""

    def test_parse_with_message_group(self):
        html = """
        <main>
            <div data-testid="message-group" data-author="user">
                <p>Hello world</p>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert "Hello world" in messages[0].content

    def test_parse_with_chat_message(self):
        html = """
        <main>
            <article data-testid="chat-message" data-role="assistant">
                <div>Response text</div>
            </article>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        assert messages[0].role == "assistant"
        assert "Response text" in messages[0].content

    def test_parse_with_code_block(self):
        html = """
        <main>
            <div data-testid="message-group">
                <pre>print("hello")</pre>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        assert 'print("hello")' in messages[0].content

    def test_parse_empty_html(self):
        html = "<html><body></body></html>"
        messages = parse_messages(html)
        assert len(messages) == 0

    def test_parse_no_main(self):
        html = "<div>Some content</div>"
        messages = parse_messages(html)
        assert len(messages) == 0

    def test_parse_multiple_messages(self):
        html = """
        <main>
            <div data-testid="message-group">Message 1</div>
            <div data-testid="message-group">Message 2</div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 2


class TestMessagesToMarkdown:
    """Tests for messages_to_markdown function"""

    def test_markdown_format(self):
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        md = messages_to_markdown(messages)
        assert "# Chat Export" in md
        assert "## User" in md
        assert "## Assistant" in md
        assert "Hello" in md
        assert "Hi" in md

    def test_markdown_ends_with_newline(self):
        messages = [Message(role="user", content="Test")]
        md = messages_to_markdown(messages)
        assert md.endswith("\n")

    def test_empty_messages(self):
        messages = []
        md = messages_to_markdown(messages)
        assert md == "# Chat Export\n"



