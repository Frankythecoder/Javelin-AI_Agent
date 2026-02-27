import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents import _normalize_url


class TestNormalizeUrl:
    def test_full_url_unchanged(self):
        assert _normalize_url("https://reddit.com") == "https://reddit.com"

    def test_http_url_unchanged(self):
        assert _normalize_url("http://example.com") == "http://example.com"

    def test_adds_https_when_no_scheme(self):
        assert _normalize_url("reddit.com") == "https://reddit.com"

    def test_strips_whitespace(self):
        assert _normalize_url("  https://reddit.com  ") == "https://reddit.com"

    def test_strips_quotes(self):
        assert _normalize_url('"https://reddit.com"') == "https://reddit.com"

    def test_strips_single_quotes(self):
        assert _normalize_url("'reddit.com'") == "https://reddit.com"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _normalize_url("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _normalize_url("   ")

    def test_domain_with_path(self):
        assert _normalize_url("reddit.com/r/python") == "https://reddit.com/r/python"

    def test_preserves_other_schemes(self):
        assert _normalize_url("ftp://files.example.com") == "ftp://files.example.com"
