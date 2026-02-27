"""AI Agent Terminal User Interface (TUI) powered by Textual."""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Bootstrap Django before importing anything that touches Django ORM
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# Ensure the project root is on sys.path so Django can find settings.py
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import django
django.setup()

from openai import OpenAI
from django.conf import settings as django_settings

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, RichLog, OptionList
from textual.containers import VerticalScroll
from textual.binding import Binding
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
    #message-area {
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
        with VerticalScroll(id="message-area"):
            yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)
        yield Static(f"  cwd: {self.working_dir}", id="status-bar")
        yield OptionList(id="file-autocomplete")
        yield Input(placeholder="Type your message... (/help for commands)", id="input-box")

    def on_mount(self):
        os.chdir(self.working_dir)
        self._init_agent()
        if self.load_session_id:
            self._do_load_session(self.load_session_id)
        else:
            self._show_welcome()
        self.query_one("#input-box", Input).focus()

    def _init_agent(self):
        client = OpenAI(api_key=django_settings.OPENAI_API_KEY)
        self.agent = Agent(client, "gpt-4.1", get_user_message=None, tools=ALL_TOOLS, light_model_name="gpt-4.1-mini")

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

    # ── Input handling ────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

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
            )
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
            log.write("[red]Agent stopped.[/]")
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
                log.write(f"[bold gold1]Agent:[/] {content}")
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
            log.write(f"\n[bold gold1]Agent:[/] {response}")
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
            log.write(f"\n[bold gold1]Agent:[/] {response}")

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
            log.write(f"\n[bold gold1]Agent:[/] {response}")
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
                log.write(f"[bold gold1]Agent:[/] {response}")

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
            self.query_one("#input-box", Input).value = ""

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


# ── CLI entry point ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Agent TUI")
    parser.add_argument("--dir", type=str, default=None, help="Working directory")
    parser.add_argument("--load", type=str, nargs="?", const="__pick__", default=None,
                        help="Load a session (pass ID or omit to pick)")
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
        load_session_id = args.load

    app = AgentTUI(working_dir=working_dir, load_session_id=load_session_id)
    app.run()


if __name__ == "__main__":
    main()
