# Playwright URL Navigation Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the Playwright navigation tool so website-name queries work as reliably as full-URL queries.

**Architecture:** Two-layer fix: (1) normalize URLs in the client-side wrapper (`playwright_mcp_tool` in `agents.py`) before they reach the MCP server, and (2) add error handling + www-retry in the MCP server (`mcp_playwright_server.py`) so transient or variant-related failures are recovered automatically.

**Tech Stack:** Python, Playwright async API, MCP (FastMCP server + stdio client)

---

### Task 1: Add `_normalize_url` helper and call it in `playwright_mcp_tool`

**Files:**
- Modify: `agents.py:496-517` (the `playwright_mcp_tool` function)
- Test: `tests/test_normalize_url.py` (new file)

**Step 1: Write the failing tests**

Create `tests/test_normalize_url.py`:

```python
"""Tests for the _normalize_url helper used by playwright_mcp_tool."""


def _normalize_url(url: str) -> str:
    """Placeholder so tests can import — will be replaced by real impl."""
    raise NotImplementedError


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
```

**Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_normalize_url.py -v`
Expected: All 10 tests FAIL with `NotImplementedError`

**Step 3: Write the `_normalize_url` function and wire it into `playwright_mcp_tool`**

In `agents.py`, add `_normalize_url` as a module-level function right above `playwright_mcp_tool` (before line 496). Then add a 2-line call at the top of `playwright_mcp_tool`:

```python
def _normalize_url(url: str) -> str:
    """Clean up an LLM-constructed URL before passing it to Playwright."""
    url = url.strip().strip('"').strip("'").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def playwright_mcp_tool(args):
    # --- URL normalization (fixes LLM-constructed URLs) ---
    if "url" in args:
        args["url"] = _normalize_url(args["url"])

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

**Step 4: Update the test file to import from agents instead of using the placeholder**

Replace the placeholder in `tests/test_normalize_url.py`:

```python
"""Tests for the _normalize_url helper used by playwright_mcp_tool."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents import _normalize_url


class TestNormalizeUrl:
    # ... (same test methods, just remove the placeholder function)
```

**Step 5: Run tests to verify they pass**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_normalize_url.py -v`
Expected: All 10 tests PASS

**Step 6: Commit**

```bash
cd C:/Users/Frank/ai_agent
git add agents.py tests/test_normalize_url.py
git commit -m "feat: add URL normalization to playwright_mcp_tool"
```

---

### Task 2: Add error handling + www-retry to the MCP server

**Files:**
- Modify: `mcp_playwright_server.py` (entire `navigate` function body)
- Test: `tests/test_mcp_navigate.py` (new file)

**Step 1: Write the failing tests**

Create `tests/test_mcp_navigate.py`:

```python
"""Tests for the navigate function's error handling and www-retry logic."""
import json
import asyncio
import pytest


# We test the helper that will be extracted from navigate
def _toggle_www(url: str) -> str:
    """Placeholder — will be replaced by real impl."""
    raise NotImplementedError


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
```

**Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_mcp_navigate.py -v`
Expected: All 6 tests FAIL with `NotImplementedError`

**Step 3: Rewrite `mcp_playwright_server.py` with error handling, www-retry, and `_toggle_www` helper**

Replace the full contents of `mcp_playwright_server.py`:

```python
import json
from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

server = FastMCP("playwright")


def _toggle_www(url: str) -> str:
    """Toggle the www. prefix on a URL for retry purposes."""
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

            # First attempt with the original URL
            try:
                await page.goto(url, timeout=60000)
            except Exception:
                # Retry with toggled www. variant
                alt_url = _toggle_www(url)
                try:
                    await page.goto(alt_url, timeout=60000)
                    url = alt_url  # update so the response reflects what actually loaded
                except Exception as retry_err:
                    return json.dumps({
                        "error": f"Navigation failed for both {url} and {alt_url}: {retry_err}"
                    })

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # proceed with whatever has loaded

            await page.screenshot(path=screenshot, full_page=True)
            text = await page.inner_text("body")

            return json.dumps({
                "url": url,
                "screenshot": screenshot,
                "text": text[:6000]
            })
        except Exception as e:
            return json.dumps({
                "error": f"Browser error: {e}"
            })
        finally:
            await browser.close()


if __name__ == "__main__":
    server.run()
```

Key changes from the original:
- `browser.close()` in `finally` block — always cleans up
- `page.goto` wrapped in try/except — on failure, retries with `_toggle_www(url)`
- `wait_for_load_state("networkidle")` has a 15s timeout and is non-fatal — some sites never reach networkidle (persistent WebSockets, polling)
- All errors return `json.dumps({"error": ...})` instead of crashing

**Step 4: Update the test file to import `_toggle_www` from the real module**

Replace the placeholder in `tests/test_mcp_navigate.py`:

```python
"""Tests for the navigate function's error handling and www-retry logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mcp_playwright_server import _toggle_www


class TestToggleWww:
    # ... (same test methods, just remove the placeholder function)
```

**Step 5: Run tests to verify they pass**

Run: `cd C:/Users/Frank/ai_agent && python -m pytest tests/test_mcp_navigate.py -v`
Expected: All 6 tests PASS

**Step 6: Commit**

```bash
cd C:/Users/Frank/ai_agent
git add mcp_playwright_server.py tests/test_mcp_navigate.py
git commit -m "feat: add error handling and www-retry to MCP playwright server"
```

---

### Task 3: Manual smoke test

**Step 1: Start the agent (TUI or web UI)**

Run: `cd C:/Users/Frank/ai_agent && python tui.py` (or start Django server)

**Step 2: Test with website name**

Type: `What is the latest info on the Wikipedia website?`
Expected: Plan preview shows `Navigate to: https://www.wikipedia.org` → approve → agent returns page content summary (no "unable to fetch" error)

**Step 3: Test with full URL (regression check)**

Type: `What is the latest info on https://www.wikipedia.org?`
Expected: Same behavior as before — works correctly

**Step 4: Test with bare domain (edge case)**

Type: `What is the latest info on reddit.com?`
Expected: URL gets normalized to `https://reddit.com`, and if that fails, retries with `https://www.reddit.com`

**Step 5: Commit any final adjustments if needed**

```bash
cd C:/Users/Frank/ai_agent
git add -A
git commit -m "fix: final adjustments from smoke testing"
```
