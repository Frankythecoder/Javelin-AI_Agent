# Welcome Message Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show a branded ASCII art welcome banner with quick-start tips when the TUI starts, which scrolls away once the user sends a message.

**Architecture:** Add a `_show_welcome()` method to `AgentTUI` that writes Rich-markup-styled ASCII art and help text to the `RichLog` widget. Called from `on_mount()` only when no session is being loaded.

**Tech Stack:** Textual (existing), Rich markup (existing)

---

### Task 1: Add `_show_welcome()` method

**Files:**
- Modify: `tui.py:268` (insert new method between `_init_agent` and the Input handling section)

**Step 1: Add the `_show_welcome` method after `_init_agent`**

Insert the following method at line 268 (after `_init_agent`, before the `# ── Input handling` comment):

```python
    def _show_welcome(self):
        log = self.query_one("#chat-log", RichLog)
        logo = (
            "  [bold dodger_blue1]"
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
```

**Step 2: Call `_show_welcome()` from `on_mount()`**

Modify `on_mount()` (line 258) to call `_show_welcome()` when no session is being loaded. Change from:

```python
    def on_mount(self):
        os.chdir(self.working_dir)
        self._init_agent()
        if self.load_session_id:
            self._do_load_session(self.load_session_id)
        self.query_one("#input-box", Input).focus()
```

To:

```python
    def on_mount(self):
        os.chdir(self.working_dir)
        self._init_agent()
        if self.load_session_id:
            self._do_load_session(self.load_session_id)
        else:
            self._show_welcome()
        self.query_one("#input-box", Input).focus()
```

**Step 3: Verify manually**

Run: `cd C:/Users/Frank/ai_agent && python -m tui`
Expected:
- ASCII "JAVELIN" logo appears in blue in the chat area
- Quick-start commands listed below
- Typing a message and pressing Enter shows the conversation; welcome scrolls up

Run: `cd C:/Users/Frank/ai_agent && python -m tui --load <some-session-id>`
Expected:
- Welcome message does NOT appear; session history loads instead

**Step 4: Commit**

```bash
git add tui.py
git commit -m "feat: add branded welcome message to TUI startup"
```
