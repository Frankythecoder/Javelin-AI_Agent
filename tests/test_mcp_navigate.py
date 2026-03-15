import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_servers.playwright_server import _toggle_www


class TestToggleWww:
    def test_add_www(self):
        assert _toggle_www("https://reddit.com") == "https://www.reddit.com"

    def test_remove_www(self):
        assert _toggle_www("https://www.reddit.com") == "https://reddit.com"

    def test_add_www_http(self):
        assert _toggle_www("http://example.com") == "http://www.example.com"

    def test_remove_www_http(self):
        assert _toggle_www("http://www.example.com") == "http://example.com"

    def test_add_www_with_path(self):
        assert _toggle_www("https://reddit.com/r/python") == "https://www.reddit.com/r/python"

    def test_no_scheme_returns_unchanged(self):
        assert _toggle_www("reddit.com") == "reddit.com"
