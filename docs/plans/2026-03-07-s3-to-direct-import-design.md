# Design: Switch views.py from S3 Download to Direct Package Import

**Date:** 2026-03-07
**Status:** Approved

## Problem

`chat/views.py` downloads a monolithic `agents.py` from S3 via `load_module_from_s3()` on every Django startup. After the refactoring that split `agents.py` into the `agents/` package (13 modules), this S3 mechanism downloads the old monolith and shadows the new package. The web UI therefore uses stale code instead of the refactored package.

## Solution

Replace the S3-based dynamic module loading in `chat/views.py` with standard Python imports from the `agents/` package, matching how `tui.py` already works.

## Changes

### 1. `chat/views.py`
- Remove `from utils import load_module_from_s3` import
- Remove `bucket_name`, `s3_key`, `agents_module` lines (18-21)
- Remove all `X = agents_module.X` attribute extractions (23-63)
- Add direct imports: `from agents import Agent, SEARCH_FILE_DEFINITION, ...`
- Rest of the file (chat_api, agent_control_api, etc.) is unchanged

### 2. `utils.py`
- Remove `load_module_from_s3` function entirely
- Keep remaining utility functions if any exist

## What stays the same
- All tool definitions and Agent class behavior (zero logic changes)
- S3 still used for static files (STATICFILES_STORAGE) — separate concern
- `tui.py`, `tests/`, `evals/` — unaffected
- All other Django settings and middleware

## Constraints
- No logic or behavior changes
- Django `manage.py check` must pass
- All existing tests must pass
- Web UI must work identically after the change
