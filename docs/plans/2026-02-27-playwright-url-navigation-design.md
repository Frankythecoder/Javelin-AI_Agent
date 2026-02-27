# Playwright URL Navigation Fix - Design Document

**Date:** 2026-02-27
**Status:** Approved
**Branch:** finale

## Problem

When users ask "What is the latest info on the Reddit website?" (without providing a full URL), the agent correctly infers the URL and calls `playwright_navigate`, but navigation always fails with: "I'm unable to access the website directly at the moment due to a technical issue."

**Root cause:** Playwright browser binaries were never installed (`playwright install chromium`), so every navigation attempt fails. Additionally, the MCP server has no error handling, making failures opaque.

## Approach: Fix Playwright + URL Normalization (Approach A)

Minimal changes to two files, no changes to tool definitions, LangGraph, system prompts, or views.

### Section 1: URL Normalization (`agents.py`)

Add `_normalize_url()` helper before `playwright_mcp_tool()`:
- Strip whitespace and surrounding quotes
- Raise `ValueError` if URL is empty after cleanup
- Prepend `https://` if no scheme (`://`) present
- Called at the top of `playwright_mcp_tool()` to sanitize `args["url"]`

### Section 2: Error Handling & WWW-Retry (`mcp_playwright_server.py`)

Enhance the `navigate()` MCP tool:
- `_toggle_www()` helper: retry `https://reddit.com` as `https://www.reddit.com` (and vice versa)
- Try/except around `page.goto()` with www-toggle retry on failure
- Graceful `networkidle` timeout (15s) - some sites never reach networkidle but are usable
- `browser.close()` in `finally` block for cleanup
- Structured JSON responses: success `{url, screenshot, text}`, failure `{error: "..."}`

### Section 3: Browser Binary Installation (one-time setup)

Run `python -m playwright install chromium` to download Chromium binary (~150MB).

### Section 4: Scope Boundaries

**No changes to:**
- Tool definitions or parameters
- LangGraph state machine or routing
- System prompts or task classification
- Django views or API endpoints
- Approval flow or dry-run system
- Any other tool or capability
- Dependencies (using existing `playwright` and `mcp` packages)

## Files Modified

1. `agents.py` - Add `_normalize_url()`, call it in `playwright_mcp_tool()`
2. `mcp_playwright_server.py` - Add error handling, www-retry, structured responses
