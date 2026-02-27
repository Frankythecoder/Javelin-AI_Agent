# Playwright URL Navigation Fix - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `playwright_navigate` reliably navigate to websites when users reference them by name (e.g., "the Reddit website") without a full URL.

**Architecture:** Two-layer fix. Layer 1: `_normalize_url()` in `agents.py` sanitizes URLs before they reach the MCP server. Layer 2: `mcp_playwright_server.py` gets error handling, www-retry, and structured JSON responses. Prerequisite: install Playwright browser binaries.

**Tech Stack:** Python, Playwright (async API), MCP (FastMCP server + stdio client)

---

### Task 0: Install Playwright Browser Binaries

**Prerequisite — nothing else works without this.**

**Step 1: Install Chromium binary**

Run: `python -m playwright install chromium`

Expected: Downloads ~150MB Chromium binary. Output ends with success message showing browser path.

**Step 2: Verify installation**

Run: `python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); page = b.new_page(); page.goto('https://example.com'); print(page.title()); b.close(); p.stop()"`

Expected: Prints `Example Domain`

**Step 3: Commit — no code changes, just verification**

No commit needed for this task.

---

### Task 1: URL Normalization — Tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_normalize_url.py`

**Step 1: Create tests directory and init file**

Create `tests/__init__.py` as an empty file.

**Step 2: Write the failing tests**

Create `tests/test_normalize_url.py`:

```python
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
```

**Step 3: Run tests to verify they fail**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_normalize_url.py -v`

Expected: FAIL — `ImportError: cannot import name '_normalize_url' from 'agents'`

**Step 4: Commit**

```bash
git add tests/__init__.py tests/test_normalize_url.py
git commit -m "test: add failing tests for _normalize_url"
```

---

### Task 2: URL Normalization — Implementation

**Files:**
- Modify: `agents.py:496` (insert `_normalize_url` before `playwright_mcp_tool`)
- Modify: `agents.py:496-517` (add normalization call inside `playwright_mcp_tool`)

**Step 1: Add `_normalize_url()` function**

Insert immediately before `def playwright_mcp_tool(args):` (line 496 in current file):

```python
def _normalize_url(url: str) -> str:
    """Clean up an LLM-constructed URL before passing it to Playwright."""
    url = url.strip().strip('"').strip("'").strip()
    if not url:
        raise ValueError("URL is empty after normalization")
    if "://" not in url:
        url = "https://" + url
    return url
```

**Step 2: Call `_normalize_url` in `playwright_mcp_tool`**

At the top of `playwright_mcp_tool(args)`, before `import asyncio`, add:

```python
    if "url" in args:
        try:
            args["url"] = _normalize_url(args["url"])
        except ValueError as e:
            return f"Playwright MCP error: {e}"
```

The full function should look like:

```python
def playwright_mcp_tool(args):
    if "url" in args:
        try:
            args["url"] = _normalize_url(args["url"])
        except ValueError as e:
            return f"Playwright MCP error: {e}"

    import asyncio
    import sys
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    async def _call():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_playwright_server.py")],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("navigate", args)
                return result.content[0].text if result.content else ""

    try:
        return asyncio.run(_call())
    except Exception as e:
        return f"Playwright MCP error: {e}"
```

**Step 3: Run tests to verify they pass**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_normalize_url.py -v`

Expected: All 10 tests PASS

**Step 4: Commit**

```bash
git add agents.py
git commit -m "feat: add URL normalization to playwright_mcp_tool"
```

---

### Task 3: MCP Server Error Handling — Tests

**Files:**
- Create: `tests/test_mcp_navigate.py`

**Step 1: Write the failing tests**

Create `tests/test_mcp_navigate.py`:

```python
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_playwright_server import _toggle_www


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
```

**Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_mcp_navigate.py -v`

Expected: FAIL — `ImportError: cannot import name '_toggle_www' from 'mcp_playwright_server'`

**Step 3: Commit**

```bash
git add tests/test_mcp_navigate.py
git commit -m "test: add failing tests for _toggle_www"
```

---

### Task 4: MCP Server Error Handling — Implementation

**Files:**
- Modify: `mcp_playwright_server.py` (full rewrite of file — 29 lines → ~55 lines)

**Step 1: Implement the enhanced MCP server**

Replace the entire contents of `mcp_playwright_server.py` with:

```python
import json
from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

server = FastMCP("playwright")


def _toggle_www(url: str) -> str:
    """Toggle www. prefix for retry on navigation failure."""
    for scheme in ("https://www.", "http://www."):
        if url.startswith(scheme):
            return url.replace(scheme, scheme.replace("www.", ""), 1)
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            return url.replace(scheme, scheme + "www.", 1)
    return url


@server.tool()
async def navigate(url: str, screenshot: str = "page.png"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            # First attempt
            try:
                await page.goto(url, timeout=60000)
            except Exception:
                # Retry with www variant
                alt_url = _toggle_www(url)
                try:
                    await page.goto(alt_url, timeout=60000)
                    url = alt_url
                except Exception as retry_err:
                    return json.dumps({
                        "error": f"Navigation failed for both {url} and {alt_url}: {retry_err}"
                    })

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # Page is still usable even without networkidle

            await page.screenshot(path=screenshot, full_page=True)
            text = await page.inner_text("body")

            return json.dumps({
                "url": url,
                "screenshot": screenshot,
                "text": text[:6000]
            })
        except Exception as e:
            return json.dumps({"error": f"Browser error: {e}"})
        finally:
            await browser.close()


if __name__ == "__main__":
    server.run()
```

**Step 2: Run _toggle_www tests to verify they pass**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_mcp_navigate.py -v`

Expected: All 6 tests PASS

**Step 3: Run ALL tests to verify nothing is broken**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/ -v`

Expected: All 16 tests PASS (10 from test_normalize_url + 6 from test_mcp_navigate)

**Step 4: Commit**

```bash
git add mcp_playwright_server.py
git commit -m "feat: add error handling and www-retry to MCP playwright server"
```

---

### Task 5: End-to-End Verification

**No files modified — manual verification only.**

**Step 1: Start the Django dev server**

Run: `cd C:/Users/Frank/ai_agent && python manage.py runserver`

**Step 2: Test via the chat UI or API**

Send this message to the agent: `"What is the latest info on the example.com website?"`

Expected behavior:
1. Agent calls `playwright_navigate` with url `"https://example.com"`
2. Tool appears in dry-run plan for approval
3. After approval, navigation succeeds
4. Agent responds with content from the page

**Step 3: Test with a name-only reference**

Send: `"Navigate to reddit"`

Expected: Agent constructs URL, normalization adds `https://`, navigation succeeds or provides clear error.

**Step 4: Run full test suite one final time**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/ -v`

Expected: All 16 tests PASS

---

## Summary of All Changes

| File | Change | Lines |
|------|--------|-------|
| `agents.py` | Add `_normalize_url()` + call in `playwright_mcp_tool()` | ~12 added |
| `mcp_playwright_server.py` | Error handling, `_toggle_www()`, www-retry, structured JSON | ~25 added |
| `tests/__init__.py` | New empty file | 0 |
| `tests/test_normalize_url.py` | 10 tests for URL normalization | ~35 |
| `tests/test_mcp_navigate.py` | 6 tests for www-toggle | ~25 |
