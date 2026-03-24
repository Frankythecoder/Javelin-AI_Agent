# tests/test_mocks.py
import json
import pytest
from evals.mocks import MOCK_REGISTRY


class TestMockRegistry:
    def test_all_external_tools_mocked(self):
        expected = {
            "search_flights", "book_travel", "get_booking",
            "cancel_booking", "list_bookings",
            "github_create_branch", "github_commit_file",
            "github_commit_local_file", "github_create_pr",
            "create_github_issue",
            "open_gmail_and_compose", "playwright_navigate",
        }
        assert set(MOCK_REGISTRY.keys()) == expected

    def test_search_flights_returns_valid_json(self):
        result = MOCK_REGISTRY["search_flights"]({"origin": "JFK", "destination": "LHR"})
        data = json.loads(result)
        assert "offers" in data
        assert len(data["offers"]) >= 1

    def test_book_travel_returns_confirmation(self):
        result = MOCK_REGISTRY["book_travel"]({"offer_id": "off_123"})
        data = json.loads(result)
        assert data["status"] == "confirmed"

    def test_github_create_branch_uses_args(self):
        result = MOCK_REGISTRY["github_create_branch"]({"branch_name": "feat/test"})
        data = json.loads(result)
        assert data["branch"] == "feat/test"

    def test_playwright_returns_page_content(self):
        result = MOCK_REGISTRY["playwright_navigate"]({"url": "https://example.com"})
        data = json.loads(result)
        assert "text_content" in data

    def test_mock_responses_are_strings(self):
        for name, mock_fn in MOCK_REGISTRY.items():
            result = mock_fn({})
            assert isinstance(result, str), f"{name} mock did not return a string"
