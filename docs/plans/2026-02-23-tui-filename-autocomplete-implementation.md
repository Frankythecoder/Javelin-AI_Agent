# TUI @filename Autocomplete — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add @filename autocomplete to the TUI input, matching the web interface behavior — a dropdown of files appears when the user types `@`, and selecting one inserts the filename into the message.

**Architecture:** A file listing helper function scans the working directory (same skip list as web). An `OptionList` widget is added to the layout (hidden by default). `on_input_changed` detects `@` triggers and shows/filters the list. Selection inserts the filename into the input. All changes in `tui.py` only.

**Tech Stack:** Python, Textual (`OptionList`, `Input.Changed`, `OptionList.OptionSelected`).

---

### Task 1: Add file listing helper function

**Files:**
- Modify: `tui.py` — add helper after session persistence functions, before the `AgentTUI` class

**Step 1: Add `_list_directory_files` function**

Insert after the `list_sessions()` function and before the `class AgentTUI` line. This mirrors the web's `list_directory_files_api` logic in `chat/views.py:282-313`:

```python
# ── File autocomplete helper ─────────────────────────────────────

_SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env'}


def _list_directory_files(directory=None):
    """Return list of files/dirs in directory, matching web API skip list."""
    cwd = directory or os.getcwd()
    entries = []
    for dirpath, dirnames, filenames in os.walk(cwd):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, cwd)
        for fname in filenames:
            rel_path = fname if rel_dir == '.' else os.path.join(rel_dir, fname).replace('\\', '/')
            entries.append(rel_path)
        for dname in dirnames:
            rel_path = dname if rel_dir == '.' else os.path.join(rel_dir, dname).replace('\\', '/')
            entries.append(rel_path)
    entries.sort()
    return entries
```

**Step 2: Verify import**

Run: `python -c "import tui; print(len(tui._list_directory_files('.')))"`
Expected: A number > 0 (prints count of files in current directory).

**Step 3: Commit**

```bash
git add tui.py
git commit -m "feat: add file listing helper for @filename autocomplete"
```

---

### Task 2: Add OptionList widget and CSS to layout

**Files:**
- Modify: `tui.py` — imports, CSS, `compose()`, `__init__()`

**Step 1: Add OptionList to imports**

Change the import line:

```python
from textual.widgets import Header, Footer, Input, Static, RichLog
```

To:

```python
from textual.widgets import Header, Footer, Input, Static, RichLog, OptionList
```

**Step 2: Add CSS for the autocomplete dropdown**

Add this CSS rule inside the `CSS = """` string, after the `.approval-bar` rule and before the closing `"""`:

```css
    #file-autocomplete {
        dock: bottom;
        max-height: 10;
        display: none;
        background: $surface;
        border: solid $accent;
        margin: 0 0;
    }
```

**Step 3: Add the OptionList to compose()**

In the `compose()` method, add the `OptionList` widget right before the `Input` widget:

Change:

```python
        yield Input(placeholder="Type your message... (/help for commands)", id="input-box")
```

To:

```python
        yield OptionList(id="file-autocomplete")
        yield Input(placeholder="Type your message... (/help for commands)", id="input-box")
```

**Step 4: Add autocomplete state to `__init__()`**

Add these lines after the `self._pending_history = []` line in `__init__()`:

```python
        # Autocomplete state
        self._file_at_trigger_pos = -1
        self._file_list_cache = []
```

**Step 5: Verify import**

Run: `python -c "import tui; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add tui.py
git commit -m "feat: add OptionList widget for file autocomplete dropdown"
```

---

### Task 3: Add @-trigger detection and dropdown show/hide logic

**Files:**
- Modify: `tui.py` — add `on_input_changed`, show/hide helpers

**Step 1: Add input change handler and helpers**

Add these methods to the `AgentTUI` class, after `action_cancel_input()` and before the `# ── CLI entry point` section:

```python
    # ── File autocomplete ─────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed):
        """Detect @ trigger and show file autocomplete."""
        if event.input.id != "input-box":
            return

        text = event.value
        cursor_pos = len(text)  # Textual Input doesn't expose cursor; use end of text

        # Find the last @ that's at start or preceded by whitespace
        at_pos = -1
        for i in range(cursor_pos - 1, -1, -1):
            if text[i] == '@':
                if i == 0 or text[i - 1] in (' ', '\t'):
                    at_pos = i
                break
            if text[i] in (' ', '\t', '\n'):
                break

        if at_pos >= 0:
            query = text[at_pos + 1:cursor_pos]
            if ' ' not in query:
                self._file_at_trigger_pos = at_pos
                self._show_file_autocomplete(query)
                return

        self._hide_file_autocomplete()

    def _show_file_autocomplete(self, query):
        """Filter file list and populate the dropdown."""
        if not self._file_list_cache:
            self._file_list_cache = _list_directory_files(self.working_dir)

        option_list = self.query_one("#file-autocomplete", OptionList)
        option_list.clear_options()

        query_lower = query.lower()
        matches = [f for f in self._file_list_cache if query_lower in f.lower()][:20]

        if not matches:
            self._hide_file_autocomplete()
            return

        for match in matches:
            option_list.add_option(match)

        option_list.styles.display = "block"

    def _hide_file_autocomplete(self):
        """Hide the autocomplete dropdown."""
        self._file_at_trigger_pos = -1
        option_list = self.query_one("#file-autocomplete", OptionList)
        option_list.styles.display = "none"
```

**Step 2: Verify import**

Run: `python -c "import tui; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add tui.py
git commit -m "feat: add @-trigger detection and file autocomplete dropdown"
```

---

### Task 4: Add selection handling and key navigation

**Files:**
- Modify: `tui.py` — add `on_option_list_option_selected`, update key handling

**Step 1: Add selection handler**

Add this method right after `_hide_file_autocomplete()`:

```python
    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Insert selected filename into the input."""
        if event.option_list.id != "file-autocomplete":
            return

        selected = str(event.option.prompt)
        input_box = self.query_one("#input-box", Input)
        text = input_box.value
        at_pos = self._file_at_trigger_pos

        if at_pos >= 0:
            # Replace @query with @filename + trailing space
            before = text[:at_pos]
            # Find end of current query (next space or end of text)
            after_at = text[at_pos + 1:]
            space_idx = after_at.find(' ')
            if space_idx >= 0:
                after = after_at[space_idx:]
            else:
                after = ""
            input_box.value = f"{before}@{selected} {after}"

        self._hide_file_autocomplete()
        input_box.focus()
```

**Step 2: Update `action_cancel_input` to also hide autocomplete**

Change the existing `action_cancel_input` method from:

```python
    def action_cancel_input(self):
        self.query_one("#input-box", Input).value = ""
```

To:

```python
    def action_cancel_input(self):
        if self._file_at_trigger_pos >= 0:
            self._hide_file_autocomplete()
        else:
            self.query_one("#input-box", Input).value = ""
```

**Step 3: Verify import**

Run: `python -c "import tui; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add tui.py
git commit -m "feat: add file autocomplete selection and escape handling"
```

---

### Task 5: Verification

**No code changes — verification only.**

**Step 1: Full import check**

Run: `python -c "import tui; print('OK')"`
Expected: `OK`

**Step 2: Verify file listing works**

Run: `python -c "import tui; files = tui._list_directory_files('.'); print(f'{len(files)} files'); assert '.git' not in str(files); assert '__pycache__' not in str(files); print('Skip dirs working')"`
Expected: File count and "Skip dirs working".

**Step 3: Verify no other files changed**

Run: `git diff HEAD -- agents.py chat/ settings.py urls.py manage.py requirements.txt`
Expected: No output.

**Step 4: Verify javelin still works**

Run: `javelin --help`
Expected: Shows usage.
