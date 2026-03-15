# Design: Project File Reorganization

**Date:** 2026-03-15
**Status:** Approved

## Problem

The project root has 22+ files — Django config, MCP servers, sample scripts, test assets, and a logo all mixed together. This makes the project hard to navigate.

## Solution

Organize root-level files into purpose-specific directories following standard Django conventions.

## New Structure

```
ai_agent/
├── .env, .gitignore, manage.py, tui.py        # root essentials
├── pyproject.toml, README.md, requirements.txt  # project metadata
├── Dockerfile.sandbox, db.sqlite3               # infra & data
│
├── config/                    # Django project config (was flat in root)
│   ├── __init__.py            # moved from root __init__.py
│   ├── settings.py            # moved, BASE_DIR updated to parent.parent
│   ├── urls.py                # moved
│   ├── asgi.py                # moved
│   └── wsgi.py                # moved
│
├── mcp/                       # MCP server package
│   ├── __init__.py            # new
│   ├── github_server.py       # was mcp_github_server.py
│   └── playwright_server.py   # was mcp_playwright_server.py
│
├── samples/                   # sample/test files
│   ├── simple_shooter.py
│   ├── oddnumbers.java
│   ├── test_imap.py
│   ├── test_image.jpg
│   └── test_video.mp4
│
├── assets/                    # project assets
│   └── javelin.png            # logo
│
├── agents/                    # unchanged
├── chat/                      # unchanged
├── docs/                      # unchanged
├── evals/                     # unchanged
└── tests/                     # unchanged
```

## Deleted Files

- `nul` — Windows artifact (empty file created by accident)

## Import Updates Required

### Django settings module (4 files)
- `manage.py`: `DJANGO_SETTINGS_MODULE` = `'settings'` -> `'config.settings'`
- `tui.py`: `DJANGO_SETTINGS_MODULE` = `'settings'` -> `'config.settings'`
- `config/asgi.py`: `DJANGO_SETTINGS_MODULE` = `'settings'` -> `'config.settings'`
- `config/wsgi.py`: `DJANGO_SETTINGS_MODULE` = `'settings'` -> `'config.settings'`

### Django settings internals (3 values in config/settings.py)
- `BASE_DIR`: `Path(__file__).resolve().parent` -> `Path(__file__).resolve().parent.parent`
- `ROOT_URLCONF`: `'urls'` -> `'config.urls'`
- `WSGI_APPLICATION`: `'wsgi.application'` -> `'config.wsgi.application'`

### MCP server imports (3 files)
- `agents/email_tools.py`: `from mcp_playwright_server import _toggle_www` -> `from mcp.playwright_server import _toggle_www`
- `agents/github_tools.py`: path to `mcp_github_server.py` -> `mcp/github_server.py` (relative path in subprocess call)
- `tests/test_mcp_navigate.py`: `from mcp_playwright_server import _toggle_www` -> `from mcp.playwright_server import _toggle_www`

### Logo path (1 file)
- `chat/views.py`: `os.path.join(settings.BASE_DIR, 'javelin.png')` -> `os.path.join(settings.BASE_DIR, 'assets', 'javelin.png')`

## Constraints
- Zero logic or behavior changes
- All existing imports must continue working
- Django check must pass
- All 16 tests must pass
- pyproject.toml entry point (`javelin = "tui:main"`) stays valid since tui.py stays in root
