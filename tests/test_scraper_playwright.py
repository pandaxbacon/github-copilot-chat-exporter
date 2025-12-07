"""Tests for scraper_playwright.py"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_playwright import (
    Message,
    flatten_content,
    extract_messages_from_json,
    messages_to_markdown,
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



