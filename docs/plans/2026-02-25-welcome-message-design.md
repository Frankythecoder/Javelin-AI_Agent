# Welcome Message Design

## Summary

Add a branded welcome message with ASCII art logo and quick-start tips to the TUI chat display area, shown on startup when no session is being loaded.

## Approach

- **Single file change:** `tui.py`
- **New method:** `_show_welcome()` writes the ASCII "JAVELIN" logo + tagline + key commands to `#chat-log` via `RichLog.write()`
- **Called from:** `on_mount()`, only when `self.load_session_id` is `None`
- **Disappears naturally:** scrolls up as conversation messages are added; no clearing logic needed
- **Display-only:** not stored in `conversation_history`

## Welcome Content

```
██╗ █████╗ ██╗   ██╗███████╗██╗     ██╗███╗   ██╗
██║██╔══██╗██║   ██║██╔════╝██║     ██║████╗  ██║
██║███████║██║   ██║█████╗  ██║     ██║██╔██╗ ██║
██║██╔══██║╚██╗ ██╔╝██╔══╝  ██║     ██║██║╚██╗██║
╚████╔╝██║  ██║ ╚████╔╝ ███████╗███████╗██║██║ ╚████║
 ╚═══╝ ╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝

Your AI-powered coding assistant.

Quick start:
  /help       Show all commands
  /save       Save your session
  /sessions   Browse past sessions
  /tools      Toggle tool access

Type a message below to begin.
```

## Styling

- ASCII art: `[bold dodger_blue1]`
- Tagline: `[dim]`
- Command names: `[bold]`
- Command descriptions: `[dim]`

## Constraints

- No new files or dependencies
- No changes to message rendering, input handling, or any other existing logic
- Welcome message is not stored in conversation history
