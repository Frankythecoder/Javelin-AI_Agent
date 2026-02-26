"""Tests for the _normalize_url helper used by playwright_mcp_tool."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents import _normalize_url


class TestNormalizeUrl:
    def test_strips_whitespace(self):
        assert _normalize_url("  https://www.reddit.com  ") == "https://www.reddit.com"

    def test_strips_wrapping_double_quotes(self):
        assert _normalize_url('"https://www.reddit.com"') == "https://www.reddit.com"

    def test_strips_wrapping_single_quotes(self):
        assert _normalize_url("'https://www.reddit.com'") == "https://www.reddit.com"

    def test_adds_https_when_no_scheme(self):
        assert _normalize_url("www.reddit.com") == "https://www.reddit.com"

    def test_adds_https_to_bare_domain(self):
        assert _normalize_url("reddit.com") == "https://reddit.com"

    def test_preserves_http_scheme(self):
        assert _normalize_url("http://example.com") == "http://example.com"

    def test_preserves_valid_https_url(self):
        assert _normalize_url("https://www.reddit.com") == "https://www.reddit.com"

    def test_preserves_path_and_query(self):
        assert _normalize_url("https://example.com/page?q=1") == "https://example.com/page?q=1"

    def test_combined_whitespace_and_quotes(self):
        assert _normalize_url('  "https://www.reddit.com"  ') == "https://www.reddit.com"

    def test_no_scheme_with_whitespace(self):
        assert _normalize_url("  www.google.com  ") == "https://www.google.com"
