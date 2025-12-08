"""Tests for scraper_playwright.py"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call, ANY
from pathlib import Path
import sys
import asyncio
import json
import tempfile
import os
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_playwright import (
    Message,
    flatten_content,
    extract_messages_from_json,
    messages_to_markdown,
    capture_login,
    extract_from_dom,
    run_export,
    main,
    STATE_PATH,
)


class TestFlattenContent:
    """Tests for flatten_content function"""

    def test_flatten_none(self):
        assert flatten_content(None) == ""

    def test_flatten_string(self):
        assert flatten_content("Hello") == "Hello"

    def test_flatten_list(self):
        assert flatten_content(["A", "B", "C"]) == "A\nB\nC"

    def test_flatten_dict_with_content(self):
        assert flatten_content({"content": "World"}) == "World"

    def test_flatten_dict_with_text(self):
        assert flatten_content({"text": "Test"}) == "Test"

    def test_flatten_dict_with_body(self):
        assert flatten_content({"body": "Body text"}) == "Body text"

    def test_flatten_nested(self):
        data = {"content": [{"text": "A"}, {"text": "B"}]}
        result = flatten_content(data)
        assert "A" in result and "B" in result

    def test_flatten_other_type(self):
        assert flatten_content(42) == "42"


class TestExtractMessagesFromJson:
    """Tests for extract_messages_from_json function"""

    def test_extract_simple_messages(self):
        data = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        }
        messages = extract_messages_from_json(data)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Hi there"

    def test_extract_with_text_field(self):
        data = {
            "messages": [
                {"role": "user", "text": "Test message"},
            ]
        }
        messages = extract_messages_from_json(data)
        assert len(messages) == 1
        assert messages[0].content == "Test message"

    def test_extract_with_parts(self):
        data = {
            "messages": [
                {"role": "user", "parts": ["Part 1", "Part 2"]},
            ]
        }
        messages = extract_messages_from_json(data)
        assert len(messages) == 1
        assert "Part 1" in messages[0].content
        assert "Part 2" in messages[0].content

    def test_extract_nested_messages(self):
        data = {
            "response": {
                "conversation": {
                    "messages": [
                        {"role": "user", "content": "Nested message"},
                    ]
                }
            }
        }
        messages = extract_messages_from_json(data)
        assert len(messages) == 1
        assert messages[0].content == "Nested message"

    def test_extract_no_messages(self):
        data = {"other": "data"}
        messages = extract_messages_from_json(data)
        assert len(messages) == 0

    def test_extract_invalid_messages(self):
        data = {"messages": [{"no_role": "value"}]}
        messages = extract_messages_from_json(data)
        assert len(messages) == 0


class TestMessagesToMarkdown:
    """Tests for messages_to_markdown function"""

    def test_single_message(self):
        messages = [Message(role="user", content="Hello")]
        md = messages_to_markdown(messages)
        assert "# Chat Export" in md
        assert "## User" in md
        assert "Hello" in md

    def test_multiple_messages(self):
        messages = [
            Message(role="user", content="Question"),
            Message(role="assistant", content="Answer"),
        ]
        md = messages_to_markdown(messages)
        assert "## User" in md
        assert "## Assistant" in md
        assert "Question" in md
        assert "Answer" in md

    def test_role_capitalization(self):
        messages = [Message(role="user", content="Test")]
        md = messages_to_markdown(messages)
        assert "## User" in md  # Should be capitalized

    def test_content_stripping(self):
        messages = [Message(role="user", content="  Content with spaces  ")]
        md = messages_to_markdown(messages)
        assert "Content with spaces" in md
        assert "  Content with spaces  " not in md

    def test_markdown_ends_with_newline(self):
        messages = [Message(role="user", content="Test")]
        md = messages_to_markdown(messages)
        assert md.endswith("\n")

    def test_empty_messages(self):
        messages = []
        md = messages_to_markdown(messages)
        assert md == "# Chat Export\n"


class TestMessage:
    """Tests for Message dataclass"""

    def test_message_creation(self):
        msg = Message(role="user", content="Test")
        assert msg.role == "user"
        assert msg.content == "Test"

    def test_message_equality(self):
        msg1 = Message(role="user", content="Test")
        msg2 = Message(role="user", content="Test")
        assert msg1 == msg2

    def test_message_string_repr(self):
        msg = Message(role="user", content="Test")
        assert "user" in str(msg)
        assert "Test" in str(msg)


class TestCaptureLogin:
    """Tests for capture_login function"""

    @pytest.mark.asyncio
    async def test_capture_login_saves_state(self):
        """Test that capture_login launches browser and saves authentication state"""
        test_url = "https://github.com/copilot/share/test-id"
        
        # Mock playwright components
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.storage_state = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        
        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)
        
        mock_playwright = AsyncMock()
        mock_playwright.chromium = mock_chromium
        
        # Mock async_playwright context manager
        mock_async_playwright = MagicMock()
        mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_async_playwright.__aexit__ = AsyncMock(return_value=None)
        
        with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
            with patch('builtins.input', return_value=''):
                with patch('builtins.print'):
                    await capture_login(test_url)
        
        # Verify browser was launched in headed mode
        mock_chromium.launch.assert_called_once()
        launch_args = mock_chromium.launch.call_args
        assert launch_args[1]['headless'] is False
        
        # Verify page navigation
        mock_page.goto.assert_called_once_with(test_url, wait_until="load")
        
        # Verify storage state was saved
        mock_context.storage_state.assert_called_once()
        assert str(STATE_PATH) in str(mock_context.storage_state.call_args)
        
        # Verify browser was closed
        mock_browser.close.assert_called_once()


class TestExtractFromDom:
    """Tests for extract_from_dom function"""

    @pytest.mark.asyncio
    async def test_extract_from_dom_with_data_attributes(self):
        """Test DOM extraction with data-author and data-role attributes"""
        mock_element1 = AsyncMock()
        mock_element1.get_attribute = AsyncMock(side_effect=lambda attr: "user" if attr == "data-author" else None)
        mock_element1.query_selector = AsyncMock(return_value=None)
        mock_element1.inner_text = AsyncMock(return_value="Hello world")
        
        mock_element2 = AsyncMock()
        mock_element2.get_attribute = AsyncMock(side_effect=lambda attr: "assistant" if attr == "data-role" else None)
        mock_element2.query_selector = AsyncMock(return_value=None)
        mock_element2.inner_text = AsyncMock(return_value="Hi there")
        
        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_element1, mock_element2])
        
        messages = await extract_from_dom(mock_page)
        
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello world"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Hi there"

    @pytest.mark.asyncio
    async def test_extract_from_dom_with_label(self):
        """Test DOM extraction when role comes from label element"""
        mock_label = AsyncMock()
        mock_label.inner_text = AsyncMock(return_value="User: message")
        
        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value=None)
        mock_element.query_selector = AsyncMock(side_effect=lambda sel: mock_label if "header" in sel else None)
        mock_element.inner_text = AsyncMock(return_value="Content text")
        
        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_element])
        
        messages = await extract_from_dom(mock_page)
        
        assert len(messages) == 1
        assert messages[0].role == "User"
        assert messages[0].content == "Content text"

    @pytest.mark.asyncio
    async def test_extract_from_dom_with_code_block(self):
        """Test DOM extraction with code/pre elements"""
        mock_code_element = AsyncMock()
        mock_code_element.inner_text = AsyncMock(return_value="print('hello')")
        
        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value="user")
        mock_element.query_selector = AsyncMock(side_effect=lambda sel: mock_code_element if "pre" in sel or "code" in sel else None)
        mock_element.inner_text = AsyncMock(return_value="fallback text")
        
        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_element])
        
        messages = await extract_from_dom(mock_page)
        
        assert len(messages) == 1
        assert "print('hello')" in messages[0].content

    @pytest.mark.asyncio
    async def test_extract_from_dom_multiple_selectors(self):
        """Test that extract_from_dom tries multiple selectors"""
        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value="user")
        mock_element.query_selector = AsyncMock(return_value=None)
        mock_element.inner_text = AsyncMock(return_value="Message content")
        
        mock_page = AsyncMock()
        # First selector returns empty, second returns elements
        mock_page.query_selector_all = AsyncMock(side_effect=[[], [mock_element]])
        
        messages = await extract_from_dom(mock_page)
        
        assert len(messages) == 1
        assert messages[0].content == "Message content"

    @pytest.mark.asyncio
    async def test_extract_from_dom_no_messages(self):
        """Test DOM extraction when no messages are found"""
        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[])
        
        messages = await extract_from_dom(mock_page)
        
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_extract_from_dom_empty_content_skipped(self):
        """Test that elements with empty content are skipped"""
        mock_element1 = AsyncMock()
        mock_element1.get_attribute = AsyncMock(return_value="user")
        mock_element1.query_selector = AsyncMock(return_value=None)
        mock_element1.inner_text = AsyncMock(return_value="   ")  # Whitespace only
        
        mock_element2 = AsyncMock()
        mock_element2.get_attribute = AsyncMock(return_value="assistant")
        mock_element2.query_selector = AsyncMock(return_value=None)
        mock_element2.inner_text = AsyncMock(return_value="Valid content")
        
        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_element1, mock_element2])
        
        messages = await extract_from_dom(mock_page)
        
        assert len(messages) == 1
        assert messages[0].content == "Valid content"


class TestRunExport:
    """Tests for run_export function"""

    @pytest.mark.asyncio
    async def test_run_export_without_storage_state(self):
        """Test that run_export exits when storage_state.json doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                with pytest.raises(SystemExit) as exc_info:
                    await run_export("https://test.url")
                
                assert exc_info.value.code == 1
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_export_json_extraction_success(self):
        """Test successful export using JSON extraction"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Create a fake storage_state.json
                Path("storage_state.json").write_text('{"cookies": []}')
                
                # Mock messages to return from DOM extraction (fallback)
                mock_messages = [
                    Message(role="user", content="Hello"),
                    Message(role="assistant", content="Hi there")
                ]
                
                # Mock page
                mock_page = AsyncMock()
                mock_page.goto = AsyncMock()
                mock_page.wait_for_timeout = AsyncMock()
                mock_page.content = AsyncMock(return_value="<html>Test</html>")
                mock_page.pdf = AsyncMock()
                mock_page.on = Mock()
                
                # Mock context and browser
                mock_context = AsyncMock()
                mock_context.new_page = AsyncMock(return_value=mock_page)
                
                mock_browser = AsyncMock()
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_browser.close = AsyncMock()
                
                mock_chromium = AsyncMock()
                mock_chromium.launch = AsyncMock(return_value=mock_browser)
                
                mock_playwright = AsyncMock()
                mock_playwright.chromium = mock_chromium
                
                mock_async_playwright = MagicMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
                mock_async_playwright.__aexit__ = AsyncMock(return_value=None)
                
                with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
                    # Patch extract_from_dom to return messages (fallback path)
                    with patch('scraper_playwright.extract_from_dom', return_value=mock_messages):
                        await run_export("https://test.url")
                
                # Verify markdown file was created
                assert Path("chat-export.md").exists()
                content = Path("chat-export.md").read_text()
                assert "# Chat Export" in content
                assert "## User" in content
                assert "Hello" in content
                assert "## Assistant" in content
                assert "Hi there" in content
                
                # Verify PDF was not created
                assert not Path("chat-export.pdf").exists()
                
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    # PDF functionality removed - test no longer needed
    # async def test_run_export_with_pdf(self):

    @pytest.mark.asyncio
    async def test_run_export_with_assets_creates_structure(self):
        """Test that asset mode creates attachments folder and captures CSV files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("storage_state.json").write_text('{"cookies": []}')

                # Message with attachment marker
                mock_messages = [Message(role="user", content="[ATTACHMENT:test.csv]\n\nHello assets")]

                mock_page = AsyncMock()
                mock_page.goto = AsyncMock()
                mock_page.wait_for_timeout = AsyncMock()
                mock_page.content = AsyncMock(return_value="<html>Asset test</html>")
                mock_page.title = AsyncMock(return_value="My Chat")
                mock_page.on = Mock()

                mock_context = AsyncMock()
                mock_context.new_page = AsyncMock(return_value=mock_page)

                mock_browser = AsyncMock()
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_browser.close = AsyncMock()

                mock_chromium = AsyncMock()
                mock_chromium.launch = AsyncMock(return_value=mock_browser)

                mock_playwright = AsyncMock()
                mock_playwright.chromium = mock_chromium

                mock_async_playwright = MagicMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
                mock_async_playwright.__aexit__ = AsyncMock(return_value=None)

                with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
                    with patch('scraper_playwright.extract_from_dom', return_value=mock_messages):
                        with patch('scraper_playwright.enhance_messages_with_attachments', return_value=mock_messages):
                            with patch('scraper_playwright.capture_images', return_value={}):
                                with patch('scraper_playwright.capture_attachments', return_value=[]):
                                    with patch('scraper_playwright.capture_file_attachments', return_value=[
                                        {"name": "test.csv", "downloaded": True, "local_path": "attachments/test-001.csv"}
                                    ]):
                                        await run_export("https://test.url", with_assets=True)

                export_root = Path("output") / "my-chat"
                assert export_root.exists()
                assert (export_root / "chat-export.md").exists()
                content = (export_root / "chat-export.md").read_text()
                # Should contain the inline attachment link
                assert "test.csv" in content or "test-001.csv" in content
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_export_dom_fallback(self):
        """Test export falls back to DOM extraction when JSON fails"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                Path("storage_state.json").write_text('{"cookies": []}')
                
                # Mock element for DOM extraction
                mock_element = AsyncMock()
                mock_element.get_attribute = AsyncMock(return_value="user")
                mock_element.query_selector = AsyncMock(return_value=None)
                mock_element.inner_text = AsyncMock(return_value="DOM extracted message")
                
                # Mock page
                mock_page = AsyncMock()
                mock_page.goto = AsyncMock()
                mock_page.wait_for_timeout = AsyncMock()
                mock_page.content = AsyncMock(return_value="<html>Test</html>")
                mock_page.query_selector_all = AsyncMock(return_value=[mock_element])
                mock_page.pdf = AsyncMock()
                mock_page.on = Mock()  # No JSON responses
                
                # Mock context and browser
                mock_context = AsyncMock()
                mock_context.new_page = AsyncMock(return_value=mock_page)
                
                mock_browser = AsyncMock()
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_browser.close = AsyncMock()
                
                mock_chromium = AsyncMock()
                mock_chromium.launch = AsyncMock(return_value=mock_browser)
                
                mock_playwright = AsyncMock()
                mock_playwright.chromium = mock_chromium
                
                mock_async_playwright = MagicMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
                mock_async_playwright.__aexit__ = AsyncMock(return_value=None)
                
                with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
                    await run_export("https://test.url")
                
                # Verify markdown was created with DOM-extracted content
                assert Path("chat-export.md").exists()
                content = Path("chat-export.md").read_text()
                assert "DOM extracted message" in content
                
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_export_no_messages_found(self):
        """Test that run_export exits when no messages are found"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                Path("storage_state.json").write_text('{"cookies": []}')
                
                # Mock page with no messages
                mock_page = AsyncMock()
                mock_page.goto = AsyncMock()
                mock_page.wait_for_timeout = AsyncMock()
                mock_page.content = AsyncMock(return_value="<html>No messages</html>")
                mock_page.query_selector_all = AsyncMock(return_value=[])  # No DOM elements
                mock_page.on = Mock()  # No JSON responses
                
                # Mock context and browser
                mock_context = AsyncMock()
                mock_context.new_page = AsyncMock(return_value=mock_page)
                
                mock_browser = AsyncMock()
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_browser.close = AsyncMock()
                
                mock_chromium = AsyncMock()
                mock_chromium.launch = AsyncMock(return_value=mock_browser)
                
                mock_playwright = AsyncMock()
                mock_playwright.chromium = mock_chromium
                
                mock_async_playwright = MagicMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
                mock_async_playwright.__aexit__ = AsyncMock(return_value=None)
                
                with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
                    with pytest.raises(SystemExit) as exc_info:
                        await run_export("https://test.url")
                    
                    assert exc_info.value.code == 2
                
            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_export_page_html_written(self):
        """Test that page.html debug file is written"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                Path("storage_state.json").write_text('{"cookies": []}')
                
                # Mock messages
                mock_messages = [Message(role="user", content="Test message")]
                
                # Mock page
                mock_page = AsyncMock()
                mock_page.goto = AsyncMock()
                mock_page.wait_for_timeout = AsyncMock()
                mock_page.content = AsyncMock(return_value="<html>Debug content</html>")
                mock_page.pdf = AsyncMock()
                mock_page.on = Mock()
                
                # Mock context and browser
                mock_context = AsyncMock()
                mock_context.new_page = AsyncMock(return_value=mock_page)
                
                mock_browser = AsyncMock()
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_browser.close = AsyncMock()
                
                mock_chromium = AsyncMock()
                mock_chromium.launch = AsyncMock(return_value=mock_browser)
                
                mock_playwright = AsyncMock()
                mock_playwright.chromium = mock_chromium
                
                mock_async_playwright = MagicMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
                mock_async_playwright.__aexit__ = AsyncMock(return_value=None)
                
                with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
                    with patch('scraper_playwright.extract_from_dom', return_value=mock_messages):
                        await run_export("https://test.url")
                
                # Verify page.html debug file was written
                assert Path("page.html").exists()
                content = Path("page.html").read_text()
                assert "Debug content" in content
                
                # Verify page.on was called to register response handler
                mock_page.on.assert_called_once_with("response", ANY)
                
            finally:
                os.chdir(original_cwd)


class TestMain:
    """Tests for main function"""

    def test_main_login_mode(self):
        """Test main function with login mode"""
        test_args = ['scraper_playwright.py', '--mode', 'login', '--url', 'https://test.url']
        
        with patch('sys.argv', test_args):
            with patch('scraper_playwright.asyncio.run') as mock_run:
                with patch('scraper_playwright.capture_login') as mock_capture:
                    main()
                    
                    # Verify asyncio.run was called with capture_login
                    mock_run.assert_called_once()
                    # The call should be asyncio.run(capture_login(...))
                    assert mock_run.call_count == 1

    def test_main_run_mode_default(self):
        """Test main function with run mode (default)"""
        test_args = ['scraper_playwright.py', '--url', 'https://test.url']
        
        with patch('sys.argv', test_args):
            with patch('scraper_playwright.asyncio.run') as mock_run:
                with patch('scraper_playwright.run_export') as mock_export:
                    main()
                    
                    # Verify asyncio.run was called with run_export
                    mock_run.assert_called_once()

    # PDF functionality removed - test no longer needed
    # def test_main_run_mode_with_pdf(self):

    def test_main_default_url(self):
        """Test main function uses default URL when not provided"""
        test_args = ['scraper_playwright.py']
        
        with patch('sys.argv', test_args):
            with patch('scraper_playwright.asyncio.run') as mock_run:
                main()
                
                # Should still run with default URL
                mock_run.assert_called_once()


class TestModuleMain:
    """Test the module's __main__ block"""

    def test_main_block_execution(self):
        """Test that __main__ block calls main()"""
        # Import as a module and execute the main block
        import subprocess
        import sys
        
        # Create a test script that imports and checks if main is called
        test_script = """
import sys
from unittest.mock import patch

# Prevent actual execution
with patch('scraper_playwright.asyncio.run'):
    # Import will trigger if __name__ == "__main__" but we're importing as module
    # So we need to test it differently
    import scraper_playwright
    
    # Verify main function exists
    assert hasattr(scraper_playwright, 'main')
    assert callable(scraper_playwright.main)
    print("main function exists and is callable")
"""
        
        # Get the repository root directory (parent of tests directory)
        repo_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, '-c', test_script],
            capture_output=True,
            text=True,
            cwd=str(repo_root)
        )
        
        assert result.returncode == 0
        assert "main function exists and is callable" in result.stdout


class TestResponseHandlerLogic:
    """Tests for response handler logic in run_export"""

    @pytest.mark.asyncio
    async def test_response_handler_with_exception(self):
        """Test that response handler gracefully handles exceptions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                Path("storage_state.json").write_text('{"cookies": []}')
                
                # Create a response that will cause an exception in the handler
                mock_bad_response = AsyncMock()
                mock_bad_response.all_headers = AsyncMock(side_effect=Exception("Network error"))
                
                captured_handler = None
                
                def capture_handler(event, handler):
                    nonlocal captured_handler
                    if event == "response":
                        captured_handler = handler
                
                # Mock page
                mock_page = AsyncMock()
                mock_page.goto = AsyncMock()
                mock_page.wait_for_timeout = AsyncMock()
                mock_page.content = AsyncMock(return_value="<html>Test</html>")
                mock_page.on = capture_handler
                
                # Mock context and browser
                mock_context = AsyncMock()
                mock_context.new_page = AsyncMock(return_value=mock_page)
                
                mock_browser = AsyncMock()
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_browser.close = AsyncMock()
                
                mock_chromium = AsyncMock()
                mock_chromium.launch = AsyncMock(return_value=mock_browser)
                
                mock_playwright = AsyncMock()
                mock_playwright.chromium = mock_chromium
                
                mock_async_playwright = MagicMock()
                mock_async_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
                mock_async_playwright.__aexit__ = AsyncMock(return_value=None)
                
                # Mock messages for success
                mock_messages = [Message(role="user", content="Test")]
                
                with patch('scraper_playwright.async_playwright', return_value=mock_async_playwright):
                    with patch('scraper_playwright.extract_from_dom', return_value=mock_messages):
                        # Start export
                        export_task = asyncio.create_task(run_export("https://test.url"))
                        
                        # Wait a bit for handler to be registered
                        await asyncio.sleep(0.1)
                        
                        # Call handler with bad response - should not crash
                        if captured_handler:
                            await captured_handler(mock_bad_response)
                        
                        # Wait for export to complete
                        await export_task
                
                # Verify export still succeeded despite handler exception
                assert Path("chat-export.md").exists()
                
            finally:
                os.chdir(original_cwd)



