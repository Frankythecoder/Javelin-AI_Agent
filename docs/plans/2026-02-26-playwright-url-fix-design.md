# Playwright URL Navigation Fix — Design

## Problem

When users ask the agent about a website by name (e.g., "What is the latest info on the Reddit website?"), the agent constructs a correct-looking URL, shows it in the dry-run plan, but after approval the Playwright tool fails. The LLM then reports "unable to fetch" or "technical issues". When users provide the full URL directly, it works.

## Root Cause

Two compounding issues:

1. **No URL normalization.** The LLM-constructed URL may contain subtle differences invisible in the plan preview — trailing whitespace, wrapping quotes, missing scheme, wrong www variant — that cause Playwright's `page.goto()` to fail.
2. **No error handling in the MCP server.** The `navigate` function has zero try/except. Any failure crashes the function, the MCP server returns a generic error, and the LLM interprets it as a technical failure.

## Solution: Approach 3 — URL Normalization + MCP Error Handling

### Part 1: URL Normalization in `playwright_mcp_tool` (agents.py)

Inside `playwright_mcp_tool`, before passing args to the MCP server:

- Strip leading/trailing whitespace from the URL
- Strip wrapping literal quote characters (`"`, `'`)
- Ensure `https://` scheme is present (prepend if missing)
- Mutate `args["url"]` in-place so the cleaned URL flows through

### Part 2: Error Handling + Retry in MCP Server (mcp_playwright_server.py)

Wrap the `navigate` function body:

- **First attempt:** `page.goto(url)` as-is
- **On failure, retry with URL variant:** toggle `www.` prefix (add if absent, remove if present)
- **Graceful errors:** return JSON with `"error"` key instead of crashing
- **Browser cleanup:** `try/finally` ensures browser always closes
- **Successful path unchanged:** screenshot + text extraction logic stays the same

### What We Don't Touch

- No changes to task classification, system instruction, dry-run flow, approval logic, graph routing, message trimming, or any other tool
- No changes to `PLAYWRIGHT_MCP_DEFINITION` (same name, parameters, description, requires_approval)
- No changes to views.py, tui.py, or the frontend
- Only two files modified: `agents.py` and `mcp_playwright_server.py`
