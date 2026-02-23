# TUI @filename Autocomplete — Design

**Date:** 2026-02-23
**Status:** Approved

## Overview

Add @filename autocomplete to the TUI input, matching the web interface behavior. When the user types `@` followed by characters, a dropdown appears showing matching files/directories in the current working directory. Selecting a file inserts `@filename ` into the input. No file content is read or injected — the AI sees `@filename` as literal text.

## Behavior

1. User types `@` in the input (at start or after whitespace)
2. A dropdown list appears with files/directories matching the typed query
3. Filtered: skips `.git`, `__pycache__`, `node_modules`, `.venv`, `venv`, `.env` (same as web)
4. User navigates with arrow keys, selects with Enter/Tab, dismisses with Escape
5. On selection: `@query` is replaced with `@filename ` (with trailing space)
6. Message sent as-is — no content injection

## Implementation

- Custom dropdown using Textual's `OptionList` widget, shown/hidden dynamically
- `on_input_changed` handler detects `@` trigger and filters file list
- File listing helper scans the working directory (non-recursive, same skip list as web)
- Arrow keys and Enter/Tab captured to navigate/select from dropdown
- Escape hides the dropdown

## Files Changed

- `tui.py` — add file listing helper, dropdown widget, input change detection

## Files NOT Changed

- `agents.py`, `chat/`, `settings.py`, all other files unchanged
