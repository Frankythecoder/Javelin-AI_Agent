# evals/mocks.py
"""Mock responses for external API tools used during evaluation.

These provide deterministic, realistic responses so eval runs don't
require real API access for travel, GitHub, email, and browser tools.
"""
import json


def _search_flights(args):
    origin = args.get("origin", "JFK")
    destination = args.get("destination", "LHR")
    return json.dumps({
        "offers": [
            {"id": "off_mock_001", "airline": "BA", "price": "$450",
             "departure": "10:30", "arrival": "18:45", "stops": 0,
             "origin": origin, "destination": destination},
            {"id": "off_mock_002", "airline": "AA", "price": "$520",
             "departure": "14:00", "arrival": "22:15", "stops": 1,
             "origin": origin, "destination": destination},
        ]
    })


def _book_travel(args):
    offer_id = args.get("offer_id", "off_mock_001")
    return json.dumps({
        "booking_ref": "MOCK-BK-001",
        "offer_id": offer_id,
        "status": "confirmed",
        "passenger": "Test User",
        "total_price": "$450",
    })


def _get_booking(args):
    ref = args.get("booking_reference", "MOCK-BK-001")
    return json.dumps({
        "booking_ref": ref,
        "status": "confirmed",
        "route": "JFK \u2192 LHR",
        "passenger": "Test User",
        "departure": "2026-06-15T10:30:00",
    })


def _cancel_booking(args):
    ref = args.get("booking_reference", "MOCK-BK-001")
    return json.dumps({
        "booking_ref": ref,
        "status": "cancelled",
        "refund_amount": "$450",
    })


def _list_bookings(args):
    return json.dumps({
        "bookings": [
            {"ref": "MOCK-BK-001", "route": "JFK \u2192 LHR",
             "status": "confirmed", "date": "2026-06-15"},
        ]
    })


def _github_create_branch(args):
    branch = args.get("branch_name", "test-branch")
    return json.dumps({
        "branch": branch,
        "status": "created",
        "base": "main",
    })


def _github_commit_file(args):
    path = args.get("file_path", "file.txt")
    return json.dumps({
        "commit_sha": "abc123mock",
        "status": "committed",
        "file": path,
    })


def _github_commit_local_file(args):
    path = args.get("file_path", "file.txt")
    return json.dumps({
        "commit_sha": "def456mock",
        "status": "committed",
        "file": path,
    })


def _github_create_pr(args):
    title = args.get("title", "Mock PR")
    return json.dumps({
        "pr_number": 42,
        "title": title,
        "url": "https://github.com/mock/repo/pull/42",
        "status": "open",
    })


def _create_github_issue(args):
    title = args.get("title", "Mock Issue")
    return json.dumps({
        "issue_number": 7,
        "title": title,
        "url": "https://github.com/mock/repo/issues/7",
        "status": "open",
    })


def _open_gmail_and_compose(args):
    to = args.get("to", "test@example.com")
    subject = args.get("subject", "")
    return json.dumps({
        "status": "draft_created",
        "to": to,
        "subject": subject,
    })


def _playwright_navigate(args):
    url = args.get("url", "https://example.com")
    return json.dumps({
        "status": "page_loaded",
        "url": url,
        "title": "Mock Page \u2014 " + url.split("//")[-1].split("/")[0],
        "text_content": "This is mock page content for testing purposes. "
                        "The page contains sample text that the agent can analyze.",
    })


MOCK_REGISTRY = {
    "search_flights": _search_flights,
    "book_travel": _book_travel,
    "get_booking": _get_booking,
    "cancel_booking": _cancel_booking,
    "list_bookings": _list_bookings,
    "github_create_branch": _github_create_branch,
    "github_commit_file": _github_commit_file,
    "github_commit_local_file": _github_commit_local_file,
    "github_create_pr": _github_create_pr,
    "create_github_issue": _create_github_issue,
    "open_gmail_and_compose": _open_gmail_and_compose,
    "playwright_navigate": _playwright_navigate,
}
