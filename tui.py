"""AI Agent Terminal User Interface (TUI) powered by Textual."""

import os
import sys
import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Bootstrap Django before importing anything that touches Django ORM
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Ensure the project root is on sys.path so Django can find settings.py
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import django
django.setup()

from openai import OpenAI
from django.conf import settings as django_settings

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, RichLog, OptionList, TextArea
from textual.binding import Binding
from textual.message import Message
from textual.strip import Strip
from textual import work

from agents import (
    Agent,
    SEARCH_FILE_DEFINITION, READ_FILE_DEFINITION, LIST_FILES_DEFINITION,
    CREATE_AND_EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION, RENAME_FILE_DEFINITION,
    RUN_CODE_DEFINITION, CHECK_SYNTAX_DEFINITION, RUN_TESTS_DEFINITION,
    LINT_CODE_DEFINITION, OPEN_GMAIL_AND_COMPOSE_DEFINITION,
    RECOGNIZE_IMAGE_DEFINITION, RECOGNIZE_VIDEO_DEFINITION, RECOGNIZE_AUDIO_DEFINITION,
    FIND_FILE_BROADLY_DEFINITION, FIND_DIRECTORY_BROADLY_DEFINITION,
    CHANGE_WORKING_DIRECTORY_DEFINITION,
    CREATE_PDF_DEFINITION, CREATE_DOCX_DEFINITION, CREATE_EXCEL_DEFINITION, CREATE_PPTX_DEFINITION,
    READ_PDF_DEFINITION, READ_DOCX_DEFINITION, READ_EXCEL_DEFINITION, READ_PPTX_DEFINITION,
    EDIT_PDF_DEFINITION, EDIT_DOCX_DEFINITION, EDIT_EXCEL_DEFINITION, EDIT_PPTX_DEFINITION,
    GITHUB_CREATE_BRANCH_DEFINITION, GITHUB_COMMIT_FILE_DEFINITION,
    GITHUB_COMMIT_LOCAL_FILE_DEFINITION, GITHUB_MCP_DEFINITION, CREATE_GITHUB_ISSUE_DEFINITION,
    PLAYWRIGHT_MCP_DEFINITION,
    SEARCH_FLIGHTS_DEFINITION, BOOK_TRAVEL_DEFINITION, GET_BOOKING_DEFINITION,
    CANCEL_BOOKING_DEFINITION, LIST_BOOKINGS_DEFINITION,
)

# All tool definitions in the same order as views.py
ALL_TOOLS = [
    SEARCH_FILE_DEFINITION, READ_FILE_DEFINITION, LIST_FILES_DEFINITION,
    CREATE_AND_EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION, RENAME_FILE_DEFINITION,
    RUN_CODE_DEFINITION, CHECK_SYNTAX_DEFINITION, RUN_TESTS_DEFINITION,
    LINT_CODE_DEFINITION, OPEN_GMAIL_AND_COMPOSE_DEFINITION,
    RECOGNIZE_IMAGE_DEFINITION, RECOGNIZE_VIDEO_DEFINITION, RECOGNIZE_AUDIO_DEFINITION,
    FIND_FILE_BROADLY_DEFINITION, FIND_DIRECTORY_BROADLY_DEFINITION,
    CHANGE_WORKING_DIRECTORY_DEFINITION,
    CREATE_PDF_DEFINITION, CREATE_DOCX_DEFINITION, CREATE_EXCEL_DEFINITION, CREATE_PPTX_DEFINITION,
    READ_PDF_DEFINITION, READ_DOCX_DEFINITION, READ_EXCEL_DEFINITION, READ_PPTX_DEFINITION,
    EDIT_PDF_DEFINITION, EDIT_DOCX_DEFINITION, EDIT_EXCEL_DEFINITION, EDIT_PPTX_DEFINITION,
    GITHUB_CREATE_BRANCH_DEFINITION, GITHUB_COMMIT_FILE_DEFINITION,
    GITHUB_COMMIT_LOCAL_FILE_DEFINITION, GITHUB_MCP_DEFINITION, CREATE_GITHUB_ISSUE_DEFINITION,
    PLAYWRIGHT_MCP_DEFINITION,
    SEARCH_FLIGHTS_DEFINITION, BOOK_TRAVEL_DEFINITION, GET_BOOKING_DEFINITION,
    CANCEL_BOOKING_DEFINITION, LIST_BOOKINGS_DEFINITION,
]

# ── Session persistence ──────────────────────────────────────────────

SESSIONS_DIR = Path.home() / ".ai_agent" / "sessions"


def _ensure_sessions_dir():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session_id, title, history, working_directory):
    """Save a session to a JSON file."""
    _ensure_sessions_dir()
    data = {
        "id": session_id,
        "title": title,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "working_directory": working_directory,
        "history": history,
    }
    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_session(session_id):
    """Load a session from a JSON file. Returns dict or None."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def delete_session(session_id):
    """Delete a session JSON file. Returns True if deleted."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_sessions():
    """Return list of saved sessions sorted by most recent."""
    _ensure_sessions_dir()
    sessions = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions


def resolve_session_ref(ref):
    """Resolve a session ID or a 1-based number from list_sessions() to an ID.

    An exact session ID takes priority; otherwise a numeric ref is treated as
    the position shown in the saved-sessions list. Returns None if unresolved.
    """
    if load_session(ref) is not None:
        return ref
    if ref.isdigit():
        sessions = list_sessions()
        index = int(ref) - 1
        if 0 <= index < len(sessions):
            return sessions[index]["id"]
    return None


# ── File autocomplete helper ─────────────────────────────────────

_SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env'}


def _list_directory_files(directory=None):
    """Return list of files/dirs in directory, matching web API skip list."""
    cwd = directory or os.getcwd()
    entries = []
    for dirpath, dirnames, filenames in os.walk(cwd, onerror=lambda e: None):
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


# ── Input with command history ───────────────────────────────────────

HISTORY_FILE = Path.home() / ".ai_agent" / "input_history.json"
HISTORY_LIMIT = 500


class HistoryInput(TextArea):
    """Multi-line message box with shell-style Up/Down recall of past messages.

    - Enter sends the message.
    - Shift+Enter inserts a newline (Ctrl+Enter / Ctrl+J too). Many terminals
      send plain Enter for Shift+Enter, so ending a line with a backslash and
      pressing Enter also inserts a newline, in any terminal.
    - Pastes keep every line, and Ctrl+V reads the system clipboard.
    - Up/Down recall history from the first/last line; otherwise they move
      the cursor between lines.
    """

    DEFAULT_CSS = """
    HistoryInput {
        height: auto;
        max-height: 10;
    }
    """

    BINDINGS = [
        Binding("up", "history_prev", "Previous input", show=False),
        Binding("down", "history_next", "Next input", show=False),
        # TextArea uses PageUp/PageDown for the cursor; scroll the chat instead
        Binding("pageup", "app.scroll_chat('page_up')", "Scroll up", show=False),
        Binding("pagedown", "app.scroll_chat('page_down')", "Scroll down", show=False),
    ]

    NEWLINE_KEYS = {"shift+enter", "ctrl+enter", "ctrl+j"}

    @dataclass
    class Submitted(Message):
        """Posted when Enter is pressed. Handle with `on_history_input_submitted`."""

        input: "HistoryInput"
        value: str

        @property
        def control(self):
            return self.input

    def __init__(self, *args, history_file=HISTORY_FILE, **kwargs):
        kwargs.setdefault("soft_wrap", True)
        kwargs.setdefault("highlight_cursor_line", False)
        super().__init__(*args, **kwargs)
        self._history_file = history_file
        self._history = self._load_history()
        self._history_index = len(self._history)  # len == editing a fresh line
        self._draft = ""

    def _load_history(self):
        if not self._history_file:
            return []
        try:
            data = json.loads(Path(self._history_file).read_text(encoding="utf-8"))
            return [h for h in data if isinstance(h, str)][-HISTORY_LIMIT:]
        except (OSError, ValueError):
            return []

    def _save_history(self):
        if not self._history_file:
            return
        try:
            path = Path(self._history_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._history), encoding="utf-8")
        except OSError:
            pass

    def add_to_history(self, text):
        """Record a submitted line and reset navigation to a fresh line."""
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            del self._history[:-HISTORY_LIMIT]
            self._save_history()
        self._history_index = len(self._history)
        self._draft = ""

    @property
    def value(self):
        return self.text

    @value.setter
    def value(self, text):
        self.text = text
        self.move_cursor(self.document.end)

    @property
    def cursor_position(self):
        """Cursor as a character index into `value`."""
        return self.document.get_index_from_location(self.cursor_location)

    def _show_history_entry(self):
        if self._history_index < len(self._history):
            self.value = self._history[self._history_index]
        else:
            self.value = self._draft

    def action_history_prev(self):
        if self.cursor_location[0] > 0:
            self.action_cursor_up()  # move within a multi-line message first
            return
        if self._history_index == 0:
            return
        if self._history_index == len(self._history):
            self._draft = self.value  # keep the unsent line, like bash
        self._history_index -= 1
        self._show_history_entry()

    def action_history_next(self):
        if self.cursor_location[0] < self.document.line_count - 1:
            self.action_cursor_down()
            return
        if self._history_index >= len(self._history):
            return
        self._history_index += 1
        self._show_history_entry()

    def _insert_newline(self):
        self._replace_via_keyboard("\n", *self.selection)

    async def _on_key(self, event):
        # Only keys handled here call prevent_default(); everything else falls
        # through to TextArea._on_key via normal handler dispatch.
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            row, col = self.cursor_location
            line = self.document[row]
            if col == len(line) and line.endswith("\\") and not self.selected_text:
                # Portable fallback: "text\" + Enter becomes a newline
                self._replace_via_keyboard("\n", (row, col - 1), (row, col))
            else:
                self.post_message(self.Submitted(self, self.text))
        elif event.key in self.NEWLINE_KEYS:
            event.stop()
            event.prevent_default()
            self._insert_newline()

    async def _on_paste(self, event):
        # Keep all lines (Input kept only the first) and normalise Windows line endings
        event.prevent_default()
        event.stop()
        self._paste_text(event.text)

    def action_paste(self):
        """Ctrl+V: paste from the system clipboard, falling back to the app's own."""
        text = None
        try:
            text = _read_windows_clipboard()
        except OSError:
            pass
        self._paste_text(text if text is not None else self.app.clipboard)

    def _paste_text(self, text):
        if self.read_only or not text:
            return
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if result := self._replace_via_keyboard(text, *self.selection):
            self.move_cursor(result.end_location)


# ── Windows clipboard ────────────────────────────────────────────────
# Textual copies via the OSC 52 escape sequence, which some Windows terminals
# ignore, and its paste only sees text copied inside the app. These talk to
# the native clipboard directly so copy/paste works with other programs too.

_CF_UNICODETEXT = 13


def _win_clipboard_api():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    return ctypes, user32, kernel32


def _read_windows_clipboard():
    """Return the Windows clipboard text, or None if unavailable."""
    if sys.platform != "win32":
        return None
    ctypes, user32, kernel32 = _win_clipboard_api()
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _copy_to_windows_clipboard(text):
    """Put text on the Windows clipboard. Returns True on success."""
    if sys.platform != "win32":
        return False
    ctypes, user32, kernel32 = _win_clipboard_api()
    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = _CF_UNICODETEXT

    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True  # the clipboard now owns the memory
    finally:
        user32.CloseClipboard()


# ── Shift+Enter on Windows consoles ──────────────────────────────────
# PowerShell, cmd and Windows Terminal deliver Shift+Enter as a plain "\r",
# and Textual's Windows reader keeps only the character, dropping the Shift
# state, so the app can't tell it from Enter. We wrap the console read Textual
# uses and rewrite Shift+Enter into the kitty-protocol sequence, which
# Textual already parses as "shift+enter".

_KEY_EVENT = 0x0001
_SHIFT_PRESSED = 0x0010
_VK_SHIFT = 0x10
_SHIFT_ENTER_SEQUENCE = "\x1b[13;2u"


def _expand_shift_enter(records, count, capacity, shift_held, shift_is_down):
    """Rewrite Shift+Enter key-down records in `records` in place.

    In virtual-terminal input mode (which Textual uses) the console strips the
    virtual key code and modifier flags from the Enter key-down record, but
    other records (the Shift key itself, key-ups) keep them. So Shift is
    tracked across records, with the live keyboard state as a fallback.

    Args:
        shift_held: Shift state carried over from the previous read.
        shift_is_down: Callable returning the physical Shift state.

    Returns:
        (new record count, shift state to carry into the next read). Records
        are left untouched if the expanded sequence wouldn't fit.
    """
    shift_enter_at = set()
    for i in range(count):
        record = records[i]
        if record.EventType != _KEY_EVENT:
            continue
        key = record.Event.KeyEvent
        if key.wVirtualKeyCode:
            # Records that still carry a key code have accurate modifier flags
            shift_held = bool(key.dwControlKeyState & _SHIFT_PRESSED)
        if key.bKeyDown and key.uChar.UnicodeChar == "\r" and (shift_held or shift_is_down()):
            shift_enter_at.add(i)

    if not shift_enter_at:
        return count, shift_held

    record_type = type(records[0])
    expanded = []
    for i in range(count):
        record = records[i]
        if i in shift_enter_at:
            for char in _SHIFT_ENTER_SEQUENCE:
                synthetic = record_type()
                synthetic.EventType = _KEY_EVENT
                synthetic.Event.KeyEvent.bKeyDown = 1
                synthetic.Event.KeyEvent.wRepeatCount = 1
                synthetic.Event.KeyEvent.uChar.UnicodeChar = char
                expanded.append(synthetic)
        else:
            expanded.append(record_type.from_buffer_copy(record))

    if len(expanded) > capacity:
        return count, shift_held
    for i, record in enumerate(expanded):
        records[i] = record
    return len(expanded), shift_held


class _Kernel32ShiftEnter:
    """Stands in for Textual's kernel32 handle; only ReadConsoleInputW changes."""

    def __init__(self, kernel32):
        import ctypes

        self._kernel32 = kernel32
        self._get_async_key_state = ctypes.WinDLL("user32").GetAsyncKeyState
        self._shift_held = False

    def __getattr__(self, name):
        return getattr(self._kernel32, name)

    def _shift_is_down(self):
        return bool(self._get_async_key_state(_VK_SHIFT) & 0x8000)

    def ReadConsoleInputW(self, handle, records_ref, capacity, count_ref):
        result = self._kernel32.ReadConsoleInputW(handle, records_ref, capacity, count_ref)
        if result:
            records, count = records_ref._obj, count_ref._obj
            count.value, self._shift_held = _expand_shift_enter(
                records, count.value, capacity, self._shift_held, self._shift_is_down
            )
        return result


def _enable_windows_shift_enter():
    """Install the Shift+Enter fix. Must run before the app starts reading input."""
    if sys.platform != "win32":
        return
    from textual.drivers import win32

    if not isinstance(win32.KERNEL32, _Kernel32ShiftEnter):
        win32.KERNEL32 = _Kernel32ShiftEnter(win32.KERNEL32)


# ── Chat log ─────────────────────────────────────────────────────────

class ChatLog(RichLog, can_focus=False):
    """RichLog that supports mouse text selection and doesn't yank the view.

    - Drag with the mouse to select text; Ctrl+C copies it. The log never
      takes focus, so the message box stays ready for typing and pasting.
    - New output only auto-scrolls when the view is already at the bottom,
      so scrolling up to read earlier messages isn't undone by the next write.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._follow = True  # stick to the bottom as new lines arrive

    def watch_scroll_y(self, old_value, new_value):
        super().watch_scroll_y(old_value, new_value)
        self._follow = new_value >= self.max_scroll_y

    def follow(self):
        """Jump to the latest output and resume auto-scrolling."""
        self._follow = True
        self.scroll_end(animate=False, immediate=False, x_axis=False)

    def write(self, content, width=None, expand=False, shrink=True, scroll_end=None, animate=False):
        if scroll_end is None:
            scroll_end = self.auto_scroll and self._follow
        return super().write(content, width, expand, shrink, scroll_end, animate)

    def get_text(self):
        """Return the whole log as plain text."""
        return "\n".join(strip.text.rstrip() for strip in self.lines)

    def get_selection(self, selection):
        return selection.extract(self.get_text()), "\n"

    def selection_updated(self, selection):
        self._line_cache.clear()
        self.refresh()

    def render_line(self, y):
        scroll_x, scroll_y = self.scroll_offset
        line_y = scroll_y + y
        width = self.scrollable_content_region.width
        line = self._render_line(line_y, scroll_x, width)

        selection = self.text_selection
        if selection is not None and line_y < len(self.lines):
            span = selection.get_span(line_y)
            if span is not None:
                start, end = span
                if end == -1:
                    end = self.lines[line_y].cell_length
                start = max(start - scroll_x, 0)
                end = min(end - scroll_x, width)
                if start < end:
                    style = self.screen.get_component_rich_style("screen--selection")
                    line = Strip.join([
                        line.crop(0, start),
                        line.crop(start, end).apply_style(style),
                        line.crop(end, width),
                    ])

        # Offsets let Textual map mouse positions back to (column, line) for selection.
        return line.apply_style(self.rich_style).apply_offsets(scroll_x, line_y)


# ── Textual App ──────────────────────────────────────────────────────

class AgentTUI(App):
    """Interactive terminal interface for the AI Agent."""

    TITLE = "AI Agent"
    CSS = """
    #header-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    #chat-log {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    #input-box {
        dock: bottom;
        margin: 0 0;
    }
    .user-msg {
        color: $secondary;
        margin: 1 0 0 0;
    }
    .agent-msg {
        margin: 1 0 0 0;
    }
    .tool-panel {
        background: $surface;
        border: solid $accent;
        margin: 0 2;
        padding: 0 1;
    }
    .plan-panel {
        background: $surface;
        border: solid $warning;
        margin: 1 0;
        padding: 1;
    }
    .error-panel {
        background: $error 20%;
        border: solid $error;
        margin: 1 0;
        padding: 1;
    }
    .approval-bar {
        height: 1;
        background: $warning 30%;
        padding: 0 1;
    }
    #file-autocomplete {
        dock: bottom;
        max-height: 10;
        display: none;
        background: $surface;
        border: solid $accent;
        margin: 0 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+d", "quit", "Exit", show=True, priority=True),
        Binding("ctrl+c", "stop_agent", "Stop", show=True),
        Binding("escape", "cancel_input", "Cancel", show=False),
        # Scroll the chat while the input box keeps focus
        Binding("pageup", "scroll_chat('page_up')", "Scroll up", show=False),
        Binding("pagedown", "scroll_chat('page_down')", "Scroll down", show=False),
        Binding("ctrl+home", "scroll_chat('home')", "Scroll to top", show=False),
        Binding("ctrl+end", "scroll_chat('end')", "Scroll to bottom", show=False),
    ]

    def __init__(self, working_dir=None, load_session_id=None):
        super().__init__()
        self.working_dir = working_dir or os.getcwd()
        self.load_session_id = load_session_id

        # Agent state
        self.conversation_history = []
        self.agent = None
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_title = ""

        # Approval state
        self._awaiting_approval = False
        self._approval_type = None  # "dry_run" or "pending"
        self._pending_plan = []
        self._pending_tools = []
        self._pending_history = []

        # Autocomplete state
        self._file_at_trigger_pos = -1
        self._file_list_cache = []

    def compose(self) -> ComposeResult:
        yield Static(
            f"  AI Agent  |  {self.working_dir}  |  Ready",
            id="header-bar",
        )
        # The log scrolls itself; wrapping it in another scroll container
        # would give the mouse wheel two competing targets.
        yield ChatLog(id="chat-log", wrap=True, highlight=True, markup=True)
        yield Static(f"  cwd: {self.working_dir}", id="status-bar")
        yield OptionList(id="file-autocomplete")
        yield HistoryInput(placeholder="Type your message... (/help for commands)", id="input-box")

    def on_mount(self):
        os.chdir(self.working_dir)
        self._init_agent()
        if self.load_session_id:
            self._do_load_session(self.load_session_id)
        else:
            self._show_welcome()
        self.query_one("#input-box", HistoryInput).focus()

    def _init_agent(self):
        client = OpenAI(api_key=django_settings.OPENAI_API_KEY)
        self.agent = Agent(client, django_settings.MODEL_NAME, get_user_message=None, tools=ALL_TOOLS, light_model_name=django_settings.LIGHT_MODEL_NAME)

    def _show_welcome(self):
        log = self.query_one("#chat-log", RichLog)
        logo = (
            "[bold green]"
            "     ██╗ █████╗ ██╗   ██╗███████╗██╗     ██╗███╗   ██╗\n"
            "     ██║██╔══██╗██║   ██║██╔════╝██║     ██║████╗  ██║\n"
            "     ██║███████║██║   ██║█████╗  ██║     ██║██╔██╗ ██║\n"
            "██   ██║██╔══██║╚██╗ ██╔╝██╔══╝  ██║     ██║██║╚██╗██║\n"
            "╚█████╔╝██║  ██║ ╚████╔╝ ███████╗███████╗██║██║ ╚████║\n"
            " ╚════╝ ╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝"
            "[/]\n"
        )
        info = (
            "  [dim]Your AI-powered coding assistant.[/]\n\n"
            "  [bold]Quick start:[/]\n"
            "    [bold]/help[/]       [dim]Show all commands[/]\n"
            "    [bold]/save[/]       [dim]Save your session[/]\n"
            "    [bold]/sessions[/]   [dim]Browse past sessions[/]\n"
            "    [bold]/tools[/]      [dim]Toggle tool access[/]\n\n"
            "  [dim]Type a message below to begin.[/]"
        )
        log.write(logo + info)

    # ── Input handling ────────────────────────────────────────────

    def on_history_input_submitted(self, event: HistoryInput.Submitted):
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        event.input.add_to_history(text)
        self._hide_file_autocomplete()
        self.query_one("#chat-log", ChatLog).follow()

        # Handle approval prompts
        if self._awaiting_approval:
            self._handle_approval_input(text)
            return

        # Handle quit
        if text.lower() == "quit":
            log = self.query_one("#chat-log", RichLog)
            log.write("\n[bold gold1]Goodbye! Thanks for using Javelin.[/]")
            self.set_timer(0.5, lambda: self.exit())
            return

        # Handle slash commands
        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        # Regular message
        self._send_message(text)

    def _handle_approval_input(self, text):
        # Handle session load selection
        if self._approval_type == "load_session":
            try:
                choice = int(text) - 1
                sessions = self._pending_plan  # stored session list
                if 0 <= choice < len(sessions):
                    self._awaiting_approval = False
                    self._do_load_session(sessions[choice]["id"])
                else:
                    log = self.query_one("#chat-log", RichLog)
                    log.write("[red]Invalid selection.[/]")
            except ValueError:
                self._awaiting_approval = False
                log = self.query_one("#chat-log", RichLog)
                log.write("[yellow]Load cancelled.[/]")
            return

        # Handle session delete selection
        if self._approval_type == "delete_session":
            try:
                choice = int(text) - 1
                sessions = self._pending_plan  # stored session list
                if 0 <= choice < len(sessions):
                    self._awaiting_approval = False
                    title = sessions[choice]["title"]
                    if delete_session(sessions[choice]["id"]):
                        log = self.query_one("#chat-log", RichLog)
                        log.write(f"[green]Deleted session: {title}[/]")
                    else:
                        log = self.query_one("#chat-log", RichLog)
                        log.write(f"[red]Session not found: {title}[/]")
                else:
                    log = self.query_one("#chat-log", RichLog)
                    log.write("[red]Invalid selection.[/]")
            except ValueError:
                self._awaiting_approval = False
                log = self.query_one("#chat-log", RichLog)
                log.write("[yellow]Delete cancelled.[/]")
            return

        lower = text.lower()
        if lower in ("y", "yes"):
            self._approve()
        elif lower in ("n", "no"):
            self._deny()
        else:
            log = self.query_one("#chat-log", RichLog)
            log.write("[bold yellow]Type [y] to approve or [n] to deny.[/]")

    # ── Slash commands ────────────────────────────────────────────

    def _handle_slash_command(self, text):
        log = self.query_one("#chat-log", RichLog)
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            log.write(
                "[bold]Available commands:[/]\n"
                "  /help           Show this help message\n"
                "  /save [title]   Save current session\n"
                "  /load           List and load a session\n"
                "  /delete         Delete a saved session\n"
                "  /sessions       List saved sessions\n"
                "  /clear          Clear conversation history\n"
                "  /cwd            Show current working directory\n"
                "  /stop           Stop agent execution\n"
                "  /tools          Toggle tools enabled/disabled\n"
                "  /copy           Copy the whole chat to the clipboard\n\n"
                "[bold]Typing:[/] Enter sends. Shift+Enter or Ctrl+Enter adds a new line "
                "(or end the line with \\ and press Enter). Ctrl+V pastes.\n"
                "[bold]Chat:[/] drag to select text, Ctrl+C to copy. "
                "Mouse wheel / PageUp / PageDown to scroll, Ctrl+End to jump to latest.\n"
            )
        elif cmd == "/copy":
            self.copy_to_clipboard(self.query_one("#chat-log", ChatLog).get_text())
        elif cmd == "/save":
            title = arg or self.session_title or "Untitled"
            self.session_title = title
            save_session(
                self.session_id, title, self.conversation_history, self.working_dir
            )
            log.write(f"[green]Session saved: {title}[/]")
        elif cmd == "/load":
            sessions = list_sessions()
            if not sessions:
                log.write("[yellow]No saved sessions found.[/]")
                return
            log.write("[bold]Saved sessions:[/]")
            for i, s in enumerate(sessions, 1):
                log.write(f"  {i}. {s['title']}  ({s['updated_at'][:10]})")
            log.write("[dim]Type the session number to load.[/]")
            # Store session list for next input
            self._awaiting_approval = True
            self._approval_type = "load_session"
            self._pending_plan = sessions
        elif cmd == "/delete":
            sessions = list_sessions()
            if not sessions:
                log.write("[yellow]No saved sessions found.[/]")
                return
            log.write("[bold]Saved sessions:[/]")
            for i, s in enumerate(sessions, 1):
                log.write(f"  {i}. {s['title']}  ({s['updated_at'][:10]})")
            log.write("[dim]Type the session number to delete.[/]")
            self._awaiting_approval = True
            self._approval_type = "delete_session"
            self._pending_plan = sessions
        elif cmd == "/sessions":
            sessions = list_sessions()
            if not sessions:
                log.write("[yellow]No saved sessions found.[/]")
                return
            log.write("[bold]Saved sessions:[/]")
            for i, s in enumerate(sessions, 1):
                log.write(f"  {i}. {s['title']}  ({s['updated_at'][:10]})")
        elif cmd == "/clear":
            self.conversation_history = []
            self.query_one("#chat-log", RichLog).clear()
            log.write("[green]Conversation cleared.[/]")
        elif cmd == "/cwd":
            log.write(f"[bold]Working directory:[/] {os.getcwd()}")
        elif cmd == "/stop":
            if self.agent:
                self.agent.control.stop()
            log.write("[red]Javelin stopped.[/]")
        elif cmd == "/tools":
            if self.agent:
                if self.agent.control.tools_enabled:
                    self.agent.control.disable_tools()
                    log.write("[yellow]Tools disabled.[/]")
                else:
                    self.agent.control.enable_tools()
                    log.write("[green]Tools enabled.[/]")
        else:
            log.write(f"[red]Unknown command: {cmd}[/]")

    # ── Session load helper ───────────────────────────────────────

    def _do_load_session(self, session_id):
        log = self.query_one("#chat-log", RichLog)
        data = load_session(session_id)
        if not data:
            log.write(f"[red]Session not found: {session_id}[/]")
            return
        self.conversation_history = data.get("history", [])
        self.session_id = data["id"]
        self.session_title = data.get("title", "")
        wd = data.get("working_directory")
        if wd and os.path.isdir(wd):
            os.chdir(wd)
            self.working_dir = wd
        log.write(f"[green]Loaded session: {self.session_title}[/]")
        # Replay history visually
        for msg in self.conversation_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                log.write(f"[bold dodger_blue1]You:[/] {content}")
            elif role == "assistant" and content:
                log.write(f"[bold gold1]Javelin:[/] {content}")
            elif role == "tool":
                name = msg.get("name", "tool")
                short = content[:200] + "..." if len(content) > 200 else content
                log.write(f"  [dim cyan]{name}:[/] {short}")

    # ── Core agent interaction ────────────────────────────────────

    @staticmethod
    def _strip_at_references(text):
        """Strip @ prefix from file references so the agent sees clean paths."""
        import re
        return re.sub(r'(?<!\S)@(\S+)', r'\1', text)

    @work(thread=True)
    def _send_message(self, text):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold dodger_blue1]You:[/] {text}")
        self._update_header("Thinking...")

        # Strip @ prefixes from file references before sending to agent
        agent_text = self._strip_at_references(text)

        # Auto-title from first message
        if not self.session_title:
            self.session_title = text[:40]

        result = self.agent.chat_once(
            conversation_history=self.conversation_history,
            message=agent_text,
        )

        status = result.get("status", "error")
        response = result.get("response", "")
        self.conversation_history = result.get("history", self.conversation_history)

        if status == "dry_run":
            self._show_dry_run(result)
        elif status == "pending":
            self._show_pending_tools(result)
        elif status == "success":
            log.write(f"\n[bold gold1]Javelin:[/] {response}")
            self._show_execution_path(result)
            self._auto_save()
            self._update_header("Ready")
        elif status == "error":
            log.write(f"\n[bold red]Error:[/] {response}")
            self._show_execution_path(result)
            self._update_header("Error")
        elif status == "stopped":
            log.write(f"\n[bold red]{response}[/]")
            self._show_execution_path(result)
            self._update_header("Stopped")

    def _show_dry_run(self, result):
        log = self.query_one("#chat-log", RichLog)
        plan = result.get("dry_run_plan", [])
        response = result.get("response", "")

        log.write(f"\n[bold yellow]--- Plan Preview ---[/]")
        log.write(f"{response}\n")
        for i, step in enumerate(plan, 1):
            summary = step.get("summary", step["name"])
            log.write(f"  [bold]{i}.[/] {summary}")
        log.write(f"[bold yellow]--- End Plan ---[/]\n")
        log.write("[bold yellow]Approve this plan? [y/n][/]")

        self._awaiting_approval = True
        self._approval_type = "dry_run"
        self._pending_plan = plan
        self._pending_history = result.get("history", self.conversation_history)
        self._update_header("Awaiting Approval")

    def _show_pending_tools(self, result):
        log = self.query_one("#chat-log", RichLog)
        pending = result.get("pending_tools", [])
        response = result.get("response", "")

        if response:
            log.write(f"\n[bold gold1]Javelin:[/] {response}")

        log.write(f"\n[bold yellow]--- Tool Approval Required ---[/]")
        for tool in pending:
            name = tool["name"]
            args = json.dumps(tool["arguments"], indent=2)
            log.write(f"  [bold]{name}[/]\n  [dim]{args}[/]")
        log.write("[bold yellow]Approve? [y/n][/]")

        self._awaiting_approval = True
        self._approval_type = "pending"
        self._pending_tools = pending
        self._pending_history = result.get("history", self.conversation_history)
        self._update_header("Awaiting Approval")

    # ── Approval handlers ─────────────────────────────────────────

    @work(thread=True)
    def _approve(self):
        log = self.query_one("#chat-log", RichLog)
        approval_type = self._approval_type

        # Handle session load (special case)
        if approval_type == "load_session":
            # Input was a number — handled elsewhere
            self._awaiting_approval = False
            return

        self._awaiting_approval = False
        self._update_header("Executing...")

        if approval_type == "dry_run":
            log.write("[green]Plan approved. Executing...[/]\n")
            result = self.agent.execute_dry_run(
                self._pending_plan, self._pending_history
            )
        elif approval_type == "pending":
            log.write("[green]Tools approved. Executing...[/]\n")
            # Execute each pending tool, then continue
            history = list(self._pending_history)
            for tool_call in self._pending_tools:
                tool_result = self.agent._execute_tool_by_name(
                    tool_call["name"], tool_call["arguments"]
                )
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["name"],
                    "content": tool_result,
                })
                short = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                log.write(f"  [dim cyan]{tool_call['name']}:[/] {short}")

            result = self.agent.chat_once(
                conversation_history=history, use_pending=True
            )
        else:
            return

        # Process the result
        status = result.get("status", "error")
        response = result.get("response", "")
        self.conversation_history = result.get("history", self.conversation_history)

        if status == "dry_run":
            self._show_dry_run(result)
        elif status == "pending":
            self._show_pending_tools(result)
        elif status == "success":
            log.write(f"\n[bold gold1]Javelin:[/] {response}")
            self._show_execution_path(result)
            self._auto_save()
            self._update_header("Ready")
        elif status == "error":
            log.write(f"\n[bold red]Error:[/] {response}")
            self._show_execution_path(result)
            self._update_header("Error")
        elif status == "stopped":
            log.write(f"\n[bold red]{response}[/]")
            self._show_execution_path(result)
            self._update_header("Stopped")

    @work(thread=True)
    def _deny(self):
        log = self.query_one("#chat-log", RichLog)
        approval_type = self._approval_type
        self._awaiting_approval = False

        if approval_type == "dry_run":
            log.write("[red]Plan denied.[/]\n")
            history = list(self._pending_history)
            for tool_call in self._pending_plan:
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["name"],
                    "content": "The user denied this action during the dry run review.",
                })
            result = self.agent.chat_once(conversation_history=history)
            self.conversation_history = result.get("history", self.conversation_history)
            response = result.get("response", "")
            if response:
                log.write(f"[bold gold1]Javelin:[/] {response}")

        elif approval_type == "pending":
            log.write("[red]Tool(s) denied.[/]\n")
            history = list(self._pending_history)
            for tool_call in self._pending_tools:
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["name"],
                    "content": "The user has denied this tool call/action.",
                })
            result = self.agent.chat_once(
                conversation_history=history, use_pending=True
            )
            self.conversation_history = result.get("history", self.conversation_history)
            response = result.get("response", "")
            if response:
                log.write(f"[bold gold1]Javelin:[/] {response}")

        self._auto_save()
        self._update_header("Ready")

    # ── Helpers ───────────────────────────────────────────────────

    def _show_execution_path(self, result):
        """Display the LangGraph execution path trace."""
        path = result.get("execution_path", [])
        if not path:
            return
        log = self.query_one("#chat-log", RichLog)
        parts = []
        for node in path:
            if "\u2717" in node:  # ✗ failure marker
                parts.append(f"[bold red]{node}[/]")
            elif node in ("__start__", "__end__"):
                parts.append(f"[dim]{node}[/]")
            else:
                parts.append(f"[green]{node}[/]")
        log.write(f"[dim]Graph:[/] {' → '.join(parts)}")

    def _update_header(self, status_text):
        header = self.query_one("#header-bar", Static)
        header.update(f"  AI Agent  |  {self.working_dir}  |  {status_text}")

    def _auto_save(self):
        if self.conversation_history:
            save_session(
                self.session_id,
                self.session_title or "Untitled",
                self.conversation_history,
                self.working_dir,
            )

    def action_scroll_chat(self, where):
        log = self.query_one("#chat-log", ChatLog)
        if where == "page_up":
            log.scroll_page_up(animate=False)
        elif where == "page_down":
            log.scroll_page_down(animate=False)
        elif where == "home":
            log.scroll_home(animate=False)
        elif where == "end":
            log.follow()

    def copy_to_clipboard(self, text):
        super().copy_to_clipboard(text)  # OSC 52, for terminals that support it
        try:
            _copy_to_windows_clipboard(text)
        except OSError:
            pass
        self.notify("Copied to clipboard", timeout=2)

    def action_quit(self):
        log = self.query_one("#chat-log", RichLog)
        log.write("\n[bold gold1]Goodbye! Thanks for using Javelin.[/]")
        self.set_timer(0.5, lambda: self.exit())

    def action_stop_agent(self):
        if self.agent:
            self.agent.control.stop()

        # Dismiss any pending approval and clean orphaned history
        if self._awaiting_approval:
            self._awaiting_approval = False
            self._approval_type = None
            self._pending_plan = []
            self._pending_tools = []
            self._pending_history = []
            self._clean_history_after_stop()

        log = self.query_one("#chat-log", RichLog)
        log.write("[bold red]Agent execution stopped.[/]")
        self._update_header("Stopped")

    def _clean_history_after_stop(self):
        """Remove the trailing assistant message with orphaned tool_calls.

        When stop is triggered during plan/tool approval, the conversation
        history contains an AIMessage with tool_calls but no matching tool
        responses.  Strip it so the next chat_once call has valid history.
        """
        if not self.conversation_history:
            return
        # Walk backwards — find the last assistant message with tool_calls
        for i in range(len(self.conversation_history) - 1, -1, -1):
            msg = self.conversation_history[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Check for matching tool responses after this index
                tool_call_ids = {tc["id"] for tc in msg["tool_calls"]}
                responded_ids = {
                    m["tool_call_id"] for m in self.conversation_history[i + 1:]
                    if m.get("role") == "tool"
                }
                if not tool_call_ids.issubset(responded_ids):
                    self.conversation_history = self.conversation_history[:i] + self.conversation_history[i + 1:]
                    return
                break
            if msg.get("role") != "tool":
                break

    def action_cancel_input(self):
        if self._file_at_trigger_pos >= 0:
            self._hide_file_autocomplete()
        else:
            self.query_one("#input-box", HistoryInput).value = ""

    # ── File autocomplete ─────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed):
        """Detect @ trigger and show file autocomplete."""
        if event.text_area.id != "input-box":
            return

        text = event.text_area.text
        cursor_pos = event.text_area.cursor_position

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

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Insert selected filename into the input."""
        if event.option_list.id != "file-autocomplete":
            return

        selected = str(event.option.prompt)
        input_box = self.query_one("#input-box", HistoryInput)
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


# ── CLI entry point ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Agent TUI")
    parser.add_argument("--dir", type=str, default=None, help="Working directory")
    parser.add_argument("--load", type=str, nargs="?", const="__pick__", default=None,
                        help="Load a session (pass ID or list number, or omit to pick)")
    args = parser.parse_args()

    working_dir = args.dir or os.getcwd()
    if not os.path.isdir(working_dir):
        print(f"Error: Directory not found: {working_dir}")
        sys.exit(1)

    load_session_id = None
    if args.load == "__pick__":
        sessions = list_sessions()
        if not sessions:
            print("No saved sessions found.")
        else:
            print("Saved sessions:")
            for i, s in enumerate(sessions, 1):
                print(f"  {i}. {s['title']}  ({s['updated_at'][:10]})")
            try:
                choice = int(input("Enter session number: ")) - 1
                if 0 <= choice < len(sessions):
                    load_session_id = sessions[choice]["id"]
            except (ValueError, IndexError, EOFError):
                print("Invalid selection, starting fresh.")
    elif args.load:
        load_session_id = resolve_session_ref(args.load)
        if load_session_id is None:
            print(f"Session not found: {args.load}. Starting fresh.")

    _enable_windows_shift_enter()
    app = AgentTUI(working_dir=working_dir, load_session_id=load_session_id)
    app.run()


if __name__ == "__main__":
    main()
