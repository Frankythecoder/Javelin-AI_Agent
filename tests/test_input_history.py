"""Tests for the TUI message box: history, newlines and paste."""

import asyncio
import json
import sys

import pytest
from textual import events
from textual.app import App

import tui
from tui import HistoryInput


class _HistoryApp(App):
    def __init__(self, history_file):
        super().__init__()
        self.history_file = history_file
        self.submitted = []

    def compose(self):
        yield HistoryInput(id="inp", history_file=self.history_file)

    def on_history_input_submitted(self, event):
        text = event.value.strip()
        self.submitted.append(text)
        event.input.value = ""
        event.input.add_to_history(text)


async def _run_navigation(history_file):
    app = _HistoryApp(history_file)
    async with app.run_test() as pilot:
        inp = app.query_one("#inp", HistoryInput)
        for line in ("first", "second", "second"):
            inp.value = line
            await pilot.press("enter")

        inp.value = "draft"
        await pilot.press("up")
        assert inp.value == "second"  # consecutive duplicate stored once
        await pilot.press("up")
        assert inp.value == "first"
        await pilot.press("up")
        assert inp.value == "first"  # stops at oldest
        assert inp.cursor_position == len("first")
        await pilot.press("down")
        assert inp.value == "second"
        await pilot.press("down")
        assert inp.value == "draft"  # unsent line restored
        await pilot.press("down")
        assert inp.value == "draft"


def test_up_down_navigates_history(tmp_path):
    history_file = tmp_path / "history.json"
    asyncio.run(_run_navigation(history_file))
    assert json.loads(history_file.read_text()) == ["first", "second"]


async def _run_persisted(history_file):
    app = _HistoryApp(history_file)
    async with app.run_test() as pilot:
        inp = app.query_one("#inp", HistoryInput)
        await pilot.press("up")
        assert inp.value == "from last run"


def test_history_persists_across_runs(tmp_path):
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(["from last run"]))
    asyncio.run(_run_persisted(history_file))


def test_corrupt_history_file_is_ignored(tmp_path):
    history_file = tmp_path / "history.json"
    history_file.write_text("not json")
    assert HistoryInput(history_file=history_file)._history == []


async def _run_newlines(history_file):
    app = _HistoryApp(history_file)
    async with app.run_test() as pilot:
        inp = app.query_one("#inp", HistoryInput)
        await pilot.press("h", "i")
        assert inp.value == "hi"  # typing isn't doubled by the custom key handler
        for key in ("shift+enter", "ctrl+enter", "ctrl+j"):
            await pilot.press(key)
        await pilot.press("x")
        assert inp.value == "hi\n\n\nx"

        await pilot.press("backslash", "enter")  # "\" + Enter -> newline, not send
        await pilot.press("y", "enter")
        assert app.submitted == ["hi\n\n\nx\ny"]
        assert inp.value == ""


def test_newline_keys_and_backslash_fallback(tmp_path):
    asyncio.run(_run_newlines(tmp_path / "history.json"))


async def _run_multiline_history(history_file):
    app = _HistoryApp(history_file)
    async with app.run_test() as pilot:
        inp = app.query_one("#inp", HistoryInput)
        inp.value = "a\nb"
        await pilot.press("enter")
        await pilot.press("up")
        assert inp.value == "a\nb" and inp.cursor_location == (1, 1)
        await pilot.press("up")  # moves within the message before older history
        assert inp.value == "a\nb" and inp.cursor_location[0] == 0
        await pilot.press("down", "down")
        assert inp.value == ""


def test_up_down_move_within_multiline_message(tmp_path):
    asyncio.run(_run_multiline_history(tmp_path / "history.json"))


async def _run_paste(history_file, monkeypatch):
    app = _HistoryApp(history_file)
    async with app.run_test() as pilot:
        inp = app.query_one("#inp", HistoryInput)
        # Terminal paste (bracketed): every line kept, CRLF normalised
        inp.post_message(events.Paste("line 1\r\nline 2\nline 3"))
        await pilot.pause()
        assert inp.value == "line 1\nline 2\nline 3"
        assert app.submitted == []  # pasted newlines don't send

        # Ctrl+V reads the system clipboard...
        inp.value = ""
        monkeypatch.setattr(tui, "_read_windows_clipboard", lambda: "from\r\nclipboard")
        await pilot.press("ctrl+v")
        assert inp.value == "from\nclipboard"

        # ...and falls back to text copied inside the app
        inp.value = ""
        monkeypatch.setattr(tui, "_read_windows_clipboard", lambda: None)
        app._clipboard = "copied in app"
        await pilot.press("ctrl+v")
        assert inp.value == "copied in app"


def test_paste_keeps_all_lines(tmp_path, monkeypatch):
    asyncio.run(_run_paste(tmp_path / "history.json", monkeypatch))


# ── Windows console Shift+Enter ──────────────────────────────────────

win32_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows console input")


def _key(ch, vk, down, state=0):
    from textual.drivers import win32

    record = win32.INPUT_RECORD()
    record.EventType = 1
    key = record.Event.KeyEvent
    key.bKeyDown, key.wRepeatCount, key.wVirtualKeyCode, key.dwControlKeyState = down, 1, vk, state
    key.uChar.UnicodeChar = ch
    return record


def _expand(records, shift_held=False, shift_is_down=lambda: False):
    from textual.drivers import win32

    buffer = (win32.INPUT_RECORD * 64)(*records)
    count, shift_held = tui._expand_shift_enter(buffer, len(records), 64, shift_held, shift_is_down)
    text = "".join(buffer[i].Event.KeyEvent.uChar.UnicodeChar for i in range(count)
                   if buffer[i].Event.KeyEvent.bKeyDown)
    return text, shift_held


SHIFT = 0x10


@win32_only
def test_shift_enter_rewritten_in_vt_input_mode():
    # In VT input mode the Enter key-down arrives with no key code or modifiers;
    # Shift is known from the Shift key record that precedes it.
    records = [_key("\x00", 0x10, 1, SHIFT), _key("\r", 0, 1), _key("\r", 0x0D, 0, SHIFT),
               _key("\x00", 0x10, 0), _key("\r", 0, 1)]
    text, shift_held = _expand(records)
    assert text == "\x00" + tui._SHIFT_ENTER_SEQUENCE + "\r"  # only the shifted Enter changes
    assert shift_held is False


@win32_only
def test_shift_state_carries_across_reads():
    _, shift_held = _expand([_key("\x00", 0x10, 1, SHIFT)])
    assert shift_held is True
    text, _ = _expand([_key("\r", 0, 1)], shift_held=shift_held)
    assert text == tui._SHIFT_ENTER_SEQUENCE


@win32_only
def test_record_flags_and_physical_shift_are_used():
    text, _ = _expand([_key("\r", 0x0D, 1, SHIFT)])  # non-VT mode: flags on the record
    assert text == tui._SHIFT_ENTER_SEQUENCE
    text, _ = _expand([_key("\r", 0, 1)], shift_is_down=lambda: True)
    assert text == tui._SHIFT_ENTER_SEQUENCE
    text, _ = _expand([_key("h", 0x48, 1), _key("\r", 0, 1)])
    assert text == "h\r"  # plain Enter untouched


@win32_only
def test_sequence_parses_as_shift_enter():
    from textual._xterm_parser import XTermParser

    keys = [event.key for event in XTermParser().feed(tui._SHIFT_ENTER_SEQUENCE)]
    assert keys == ["shift+enter"]
