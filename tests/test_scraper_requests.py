"""Tests for scraper_requests.py"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import tempfile
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_requests import (
    Message,
    looks_like_login,
    parse_messages,
    messages_to_markdown,
    fetch_html,
    main,
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


class TestFetchHtml:
    """Tests for fetch_html function"""

    def test_fetch_html_success(self):
        """Test successful HTML fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>Content</html>"
        mock_response.url = "https://github.com/copilot/share/test"
        
        with patch('scraper_requests.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            result = fetch_html("https://github.com/copilot/share/test")
            
            assert result == mock_response
            mock_session.get.assert_called_once_with(
                "https://github.com/copilot/share/test",
                allow_redirects=True,
                timeout=20
            )

    def test_fetch_html_with_redirects(self):
        """Test that fetch_html follows redirects"""
        mock_response = Mock()
        mock_response.url = "https://github.com/login"  # Redirected URL
        
        with patch('scraper_requests.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            result = fetch_html("https://github.com/copilot/share/test")
            
            # Verify allow_redirects is True
            call_args = mock_session.get.call_args
            assert call_args[1]['allow_redirects'] is True

    def test_fetch_html_timeout(self):
        """Test that fetch_html uses proper timeout"""
        with patch('scraper_requests.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            fetch_html("https://test.url")
            
            # Verify timeout is set
            call_args = mock_session.get.call_args
            assert call_args[1]['timeout'] == 20


class TestParseMessagesExtended:
    """Extended tests for parse_messages function"""

    def test_parse_with_fallback_role_extraction(self):
        """Test role extraction from text when no data attributes"""
        html = """
        <main>
            <div data-testid="message-group">
                User: some text
                <div>Content here</div>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        # Role should be extracted from text

    def test_parse_with_markdown_body(self):
        """Test parsing with markdown-body class"""
        html = """
        <main>
            <div data-testid="message-group" data-author="user">
                <div class="markdown-body">Formatted content</div>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        assert "Formatted content" in messages[0].content

    def test_parse_with_copilot_chat_message_selector(self):
        """Test parsing with copilot-chat-message selector"""
        html = """
        <main>
            <div data-testid="copilot-chat-message" data-role="assistant">
                <p>Copilot response</p>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        assert messages[0].role == "assistant"
        assert "Copilot response" in messages[0].content

    def test_parse_with_data_target_selector(self):
        """Test parsing with data-target attribute"""
        html = """
        <main>
            <div data-target="copilot-chat-message" data-author="user">
                <p>User message</p>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        assert messages[0].role == "user"

    def test_parse_role_extraction_with_colon(self):
        """Test that role extraction splits on colon"""
        html = """
        <main>
            <div data-testid="message-group">
                Assistant: some helper text
                <p>Actual content</p>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        # Role should be "Assistant" (before the colon)

    def test_parse_ignores_long_role_text(self):
        """Test that very long role text is ignored"""
        html = """
        <main>
            <div data-testid="message-group">
                This is a very long text that should not be considered a role because it exceeds 40 characters limit
                <p>Content</p>
            </div>
        </main>
        """
        messages = parse_messages(html)
        assert len(messages) == 1
        # Should fall back to "unknown" role


class TestMain:
    """Tests for main function"""

    def test_main_success(self):
        """Test successful execution of main"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.url = "https://github.com/copilot/share/test"
                mock_response.text = """
                <main>
                    <div data-testid="message-group" data-author="user">
                        <p>Test message</p>
                    </div>
                </main>
                """
                
                test_args = ['scraper_requests.py', '--url', 'https://test.url']
                
                with patch('sys.argv', test_args):
                    with patch('scraper_requests.fetch_html', return_value=mock_response):
                        result = main()
                
                assert result == 0
                assert Path("chat-export.md").exists()
                
                content = Path("chat-export.md").read_text()
                assert "# Chat Export" in content
                assert "Test message" in content
                
            finally:
                os.chdir(original_cwd)

    def test_main_login_redirect(self):
        """Test main returns 1 when page requires login"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://github.com/login"
        mock_response.text = "Sign in to GitHub"
        
        test_args = ['scraper_requests.py', '--url', 'https://test.url']
        
        with patch('sys.argv', test_args):
            with patch('scraper_requests.fetch_html', return_value=mock_response):
                result = main()
        
        assert result == 1

    def test_main_no_messages_found(self):
        """Test main returns 2 when no messages found"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://github.com/copilot/share/test"
        mock_response.text = "<html><body>No messages here</body></html>"
        
        test_args = ['scraper_requests.py', '--url', 'https://test.url']
        
        with patch('sys.argv', test_args):
            with patch('scraper_requests.fetch_html', return_value=mock_response):
                result = main()
        
        assert result == 2

    def test_main_default_url(self):
        """Test main uses default URL when not provided"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://github.com/copilot/share/default"
        mock_response.text = """
        <main>
            <div data-testid="message-group" data-author="user">Message</div>
        </main>
        """
        
        test_args = ['scraper_requests.py']  # No URL argument
        
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                with patch('sys.argv', test_args):
                    with patch('scraper_requests.fetch_html', return_value=mock_response):
                        result = main()
                
                assert result == 0
                assert Path("chat-export.md").exists()
                
            finally:
                os.chdir(original_cwd)

    def test_main_file_write_with_encoding(self):
        """Test that main writes file with UTF-8 encoding"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.url = "https://github.com/copilot/share/test"
                mock_response.text = """
                <main>
                    <div data-testid="message-group" data-author="user">
                        <p>Unicode test: 你好 مرحبا</p>
                    </div>
                </main>
                """
                
                test_args = ['scraper_requests.py']
                
                with patch('sys.argv', test_args):
                    with patch('scraper_requests.fetch_html', return_value=mock_response):
                        main()
                
                # Verify file can be read with UTF-8
                content = Path("chat-export.md").read_text(encoding="utf-8")
                assert "你好" in content
                assert "مرحبا" in content
                
            finally:
                os.chdir(original_cwd)


class TestLooksLikeLoginExtended:
    """Extended tests for looks_like_login"""

    def test_case_insensitive_url_check(self):
        """Test that URL check is case insensitive"""
        mock_response = Mock()
        mock_response.url = "https://github.com/LOGIN"
        mock_response.text = ""
        assert looks_like_login(mock_response) is True

    def test_case_insensitive_content_check(self):
        """Test that content check is case insensitive"""
        mock_response = Mock()
        mock_response.url = "https://github.com/page"
        mock_response.text = "SIGN IN TO GITHUB"
        assert looks_like_login(mock_response) is True


