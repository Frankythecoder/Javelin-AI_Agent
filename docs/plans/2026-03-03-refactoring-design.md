# Refactoring Design: agents.py + index.html

**Date:** 2026-03-03
**Goal:** No file exceeds 1000 lines. Zero logic/behavior changes.

## Part 1: agents.py (4,814 lines) → agents/ package

### File Split

| New File | Contents | Est. Lines |
|----------|----------|------------|
| `agents/__init__.py` | Re-exports all public names for backward compatibility | ~80 |
| `agents/control.py` | `AgentControlState`, `ToolDefinition`, `ApprovalAwareTool`, `tool_definition_to_langchain`, `_json_type_to_python` | ~100 |
| `agents/helpers.py` | `find_file_broadly`, `find_directory_broadly`, `_normalize_url`, `is_prompt_injection`, `main()` | ~220 |
| `agents/file_tools.py` | 9 file tool functions + definitions (search, read, list, delete, create_and_edit, rename, find_file/dir_broadly_tool, change_wd) | ~420 |
| `agents/code_tools.py` | 4 code tool functions + definitions (run_code, check_syntax, run_tests, lint_code) | ~150 |
| `agents/github_tools.py` | `_github_mcp_call` + 5 tool functions + definitions | ~200 |
| `agents/email_tools.py` | Gmail draft creation, Chrome profile helpers, `open_gmail_and_compose_tool`, `playwright_mcp_tool` + definitions | ~300 |
| `agents/multimedia_tools.py` | Image/video/audio recognition tool functions + definitions | ~230 |
| `agents/travel_tools.py` | Duffel API helpers (`_duffel_headers`, `_duffel_post`, `_duffel_get`, `_parse_iso_duration`, cache) + 5 travel tool functions + definitions | ~650 |
| `agents/document_tools.py` | `_parse_markdown_blocks`, `_md_inline_to_html` + PDF/DOCX/Excel/PPTX create/read/edit functions + 12 definitions | ~850 |
| `agents/core.py` | `AgentState`, `Agent` class (LangGraph graph, chat_once, execute_dry_run, run, CLI mode, all internal methods) | ~950 |

### Import Compatibility

`agents/__init__.py` re-exports every public name so these continue to work unchanged:
- `from agents import Agent, SEARCH_FILE_DEFINITION, ...` (tui.py)
- `import agents as agents_module` then `agents_module.Agent` (evals/runner.py, chat/views.py)
- `from agents import _normalize_url` (tests/test_normalize_url.py)

### Internal Dependencies Between New Files

- `helpers.py` → standalone (os, re only)
- `control.py` → standalone (langchain_core, pydantic)
- `file_tools.py` → imports from `helpers.py` (find_file_broadly, find_directory_broadly)
- `code_tools.py` → imports `run_code_tool` internally (check_syntax/run_tests/lint use it)
- `github_tools.py` → standalone (mcp, requests)
- `email_tools.py` → imports from `helpers.py` (find_chrome_profile_for_email uses settings)
- `multimedia_tools.py` → standalone (openai, cv2, base64)
- `travel_tools.py` → standalone (requests, Duffel API)
- `document_tools.py` → imports from `helpers.py` (find_file_broadly for read/edit tools)
- `core.py` → imports from `control.py` (AgentControlState, ToolDefinition, tool_definition_to_langchain) and `helpers.py` (is_prompt_injection)

## Part 2: index.html (1,618 lines) → split CSS/JS

| New File | Contents |
|----------|----------|
| `chat/static/chat/css/chat.css` | All CSS from `<style>` block |
| `chat/static/chat/js/chat.js` | All JavaScript from `<script>` block |
| `chat/templates/chat/index.html` | Slim HTML with `{% load static %}`, `<link>` to CSS, `<script src>` to JS |

### Django Static Files Setup

- Add `{% load static %}` at top of index.html
- Replace `<style>...</style>` with `<link rel="stylesheet" href="{% static 'chat/css/chat.css' %}">`
- Replace `<script>...</script>` with `<script src="{% static 'chat/js/chat.js' %}"></script>`
- Ensure `django.contrib.staticfiles` is in INSTALLED_APPS (already is)

## Constraints

- Zero logic changes — code moves between files, nothing else
- All existing imports must continue to work
- All existing tests must pass
- The `agents.py` file gets deleted after the package is created
