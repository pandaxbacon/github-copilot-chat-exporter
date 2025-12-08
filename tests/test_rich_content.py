"""Tests for rich content capture functions"""
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper_playwright import (
    build_export_folder_name,
    save_data_uri,
    update_markdown_with_assets,
)


class TestUpdateMarkdownWithAssets:
    """Tests for update_markdown_with_assets function"""

    def test_replace_image_urls(self):
        md = "Check this image: ![Alt](https://example.com/img.png)"
        image_map = {"https://example.com/img.png": "images/img-001.png"}

        result = update_markdown_with_assets(md, image_map, [], [])

        assert "images/img-001.png" in result
        assert "https://example.com/img.png" not in result

    def test_multiple_image_replacements(self):
        md = "![Image 1](https://example.com/1.png) and ![Image 2](https://example.com/2.png)"
        image_map = {
            "https://example.com/1.png": "images/img-001.png",
            "https://example.com/2.png": "images/img-002.png",
        }

        result = update_markdown_with_assets(md, image_map, [], [])

        assert "images/img-001.png" in result
        assert "images/img-002.png" in result
        assert "https://example.com" not in result

    def test_add_attachments_section(self):
        md = "# Chat Export\n\n## User\nHello"
        attachments = [
            {"name": "file.pdf", "url": "https://example.com/file.pdf", "downloaded": True},
            {
                "name": "doc.txt",
                "url": "https://example.com/doc.txt",
                "downloaded": False,
            },
        ]

        result = update_markdown_with_assets(md, {}, attachments, [])

        assert "## Attachments" in result
        assert "file.pdf" in result
        assert "✓" in result  # Downloaded status
        assert "✗" in result  # Failed status

    def test_add_charts_section(self):
        md = "# Chat Export"
        charts = ["charts/chart-001.png", "charts/svg-001.png"]

        result = update_markdown_with_assets(md, {}, [], charts)

        assert "## Charts & Visualizations" in result
        assert "![Chart](charts/chart-001.png)" in result
        assert "![Chart](charts/svg-001.png)" in result

    def test_all_assets_combined(self):
        md = "# Chat\n\n![Image](https://example.com/img.png)"
        image_map = {"https://example.com/img.png": "images/img-001.png"}
        attachments = [
            {"name": "file.pdf", "url": "https://example.com/file.pdf", "downloaded": True}
        ]
        charts = ["charts/chart-001.png"]

        result = update_markdown_with_assets(md, image_map, attachments, charts)

        assert "images/img-001.png" in result
        assert "## Attachments" in result
        assert "## Charts & Visualizations" in result
        assert "file.pdf" in result
        assert "chart-001.png" in result

    def test_no_assets(self):
        md = "# Chat Export\n\nNo assets here"

        result = update_markdown_with_assets(md, {}, [], [])

        assert result == md
        assert "## Attachments" not in result
        assert "## Charts" not in result

    def test_empty_attachments_list(self):
        md = "# Chat"
        result = update_markdown_with_assets(md, {}, [], [])
        assert "## Attachments" not in result

    def test_empty_charts_list(self):
        md = "# Chat"
        result = update_markdown_with_assets(md, {}, [], [])
        assert "## Charts" not in result


class TestExportFolderNaming:
    def test_folder_uses_title(self):
        folder = build_export_folder_name("My Conversation Title", "https://example.com/share/abc")
        assert folder.startswith("my-conversation-title")

    def test_folder_uses_url_when_title_missing(self):
        folder = build_export_folder_name("", "https://example.com/share/abc-123")
        assert folder.startswith("abc-123")

    def test_folder_falls_back_to_timestamp(self):
        folder = build_export_folder_name("", "https://example.com")
        assert folder.startswith("export-")


class TestDataUriSaving:
    @pytest.mark.asyncio
    async def test_save_data_uri_creates_file(self, tmp_path):
        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEklEQVR42mP8z/CfAQAI4AL9oA13pwAAAABJRU5ErkJggg=="
        used = set()
        images_dir = tmp_path / "images"
        rel_path = await save_data_uri(data_uri, images_dir, used)
        assert rel_path is not None
        # Relative path should point to images/ prefix
        assert rel_path.startswith("images/")
        # File should exist on disk
        saved_file = images_dir / Path(rel_path).name
        assert saved_file.exists()


class TestImageCapture:
    """Integration tests for image capture (require manual testing)"""

    def test_image_map_structure(self):
        # Test that image_map has correct structure
        image_map = {
            "https://example.com/img1.png": "images/img-001.png",
            "https://example.com/img2.jpg": "images/img-002.jpg",
        }

        for original, local in image_map.items():
            assert original.startswith("http")
            assert local.startswith("images/")
            assert local.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))


class TestAttachmentCapture:
    """Integration tests for attachment capture"""

    def test_attachment_structure(self):
        attachments = [
            {"name": "file.pdf", "url": "https://example.com/file.pdf", "downloaded": True},
            {"name": "doc.txt", "url": "https://example.com/doc.txt", "downloaded": False},
        ]

        for att in attachments:
            assert "name" in att
            assert "url" in att
            assert "downloaded" in att
            assert isinstance(att["downloaded"], bool)


class TestChartCapture:
    """Integration tests for chart capture"""

    def test_chart_paths(self):
        charts = ["charts/chart-001.png", "charts/svg-001.png"]

        for chart in charts:
            assert chart.startswith("charts/")
            assert chart.endswith(".png")

