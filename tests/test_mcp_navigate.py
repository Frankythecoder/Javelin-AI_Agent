"""Tests for the navigate function's error handling and www-retry logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcp_playwright_server import _toggle_www


class TestToggleWww:
    def test_adds_www(self):
        assert _toggle_www("https://reddit.com") == "https://www.reddit.com"

    def test_removes_www(self):
        assert _toggle_www("https://www.reddit.com") == "https://reddit.com"

    def test_adds_www_http(self):
        assert _toggle_www("http://example.com") == "http://www.example.com"

    def test_removes_www_http(self):
        assert _toggle_www("http://www.example.com") == "http://example.com"

    def test_preserves_path(self):
        assert _toggle_www("https://reddit.com/r/python") == "https://www.reddit.com/r/python"

    def test_removes_www_preserves_path(self):
        assert _toggle_www("https://www.reddit.com/r/python") == "https://reddit.com/r/python"
