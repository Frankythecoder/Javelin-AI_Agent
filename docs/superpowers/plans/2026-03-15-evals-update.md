# Evals Update Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update evals to use dynamic tool discovery and add eval tasks for all agent tool categories.

**Architecture:** Replace manual tool imports in `runner.py` with dynamic discovery via `dir()` + `ToolDefinition` type guard. Fix stale `agents.py` references and file paths in `tasks.json`. Append 8 new dry-run eval tasks covering GitHub, travel, document, audio, directory, browser, and email tools.

**Tech Stack:** Python, Django, OpenAI API

**Spec:** `docs/superpowers/specs/2026-03-15-evals-update-design.md`

---

## Chunk 1: Update runner.py with dynamic tool discovery

### Task 1: Replace manual imports with dynamic discovery in runner.py

**Files:**
- Modify: `evals/runner.py:35-78`

- [ ] **Step 1: Replace the manual import block and tool list**

Replace lines 35-78 (the comment, 15 manual definition imports, the `Agent` assignment, and the `run_evals` function's explicit tool list) with dynamic discovery. The full `evals/runner.py` after this change:

```python
import os
import json
import sys
import time
import django
from pathlib import Path
from django.conf import settings
from dotenv import load_dotenv
from openai import OpenAI

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Setup minimal Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        INSTALLED_APPS=[
            'chat',
        ],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3'),
            }
        },
        BASE_DIR=Path(__file__).resolve().parent.parent,
    )
    django.setup()

# Import Agent and dynamically discover all tool definitions
import agents as agents_module

Agent = agents_module.Agent

# Dynamically collect all tool definitions (with type guard)
tools = [
    getattr(agents_module, name)
    for name in sorted(dir(agents_module))
    if name.endswith('_DEFINITION')
    and isinstance(getattr(agents_module, name), agents_module.ToolDefinition)
]

assert len(tools) > 0, "No tool definitions discovered — check agents package imports"
print(f"Discovered {len(tools)} tool definitions")

def run_evals(output_file='results.json'):
    # Load tasks
    tasks_path = os.path.join(os.path.dirname(__file__), 'tasks.json')
    with open(tasks_path, 'r') as f:
        tasks = json.load(f)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    model_name = 'gpt-4.1'

    # We don't need a real get_user_message for chat_once
    agent = Agent(client, model_name, lambda: ("", False), tools, light_model_name='gpt-4.1-mini')
```

Everything from line 85 onward (`results = []`, the task loop, metrics, etc.) stays unchanged.

- [ ] **Step 2: Verify the import works**

Run: `cd /c/Users/Frank/ai_agent && python -c "import agents as m; tools = [getattr(m, n) for n in sorted(dir(m)) if n.endswith('_DEFINITION') and isinstance(getattr(m, n), m.ToolDefinition)]; print(f'{len(tools)} tools discovered')"`

Expected: `40 tools discovered`

- [ ] **Step 3: Commit**

```bash
git add evals/runner.py
git commit -m "refactor: replace manual tool imports with dynamic discovery in eval runner"
```

---

## Chunk 2: Fix stale references in tasks.json

### Task 2: Update agents.py references and file paths in existing tasks

**Files:**
- Modify: `evals/tasks.json`

- [ ] **Step 1: Update task_011 prompt**

Change `"Scan 'agents.py' for any hardcoded API keys or secrets and report if any are found (do not remove them, just report)."` to `"Scan the 'agents/' package for any hardcoded API keys or secrets and report if any are found (do not remove them, just report)."`

- [ ] **Step 2: Update task_012 prompt**

Change `"Read 'agents.py' and generate a summary of all available tools and their purposes."` to `"Read the 'agents/' package and generate a summary of all available tools and their purposes."`

- [ ] **Step 3: Update task_019 prompt**

Change `"Identify any large functions in 'agents.py' (over 50 lines) and suggest how to break them down."` to `"Identify any large functions in the 'agents/' package (over 50 lines) and suggest how to break them down."`

- [ ] **Step 4: Update task_022 prompt and expected_output**

Change prompt from `"Only check 'agents.py' and tell me if more robust error handling can be done for the 'read_file' tool (do not edit the file!) (e.g., handling binary files)."` to `"Only check 'agents/file_tools.py' and tell me if more robust error handling can be done for the 'read_file' tool (do not edit the file!) (e.g., handling binary files)."`

Change expected_output from `"Enhanced error handling in agents.py."` to `"Agent identifies potential error handling improvements without editing the file."`

- [ ] **Step 5: Update task_023 prompt**

Change `"Explain how to integrate a new tool into the current Agent class structure in 'agents.py'."` to `"Explain how to integrate a new tool into the current Agent class structure in 'agents/core.py'."`

- [ ] **Step 6: Update task_024 prompt**

Change `"Analyze 'list_files_tool' in 'agents.py' for potential performance issues when dealing with very large directories."` to `"Analyze 'list_files_tool' in 'agents/file_tools.py' for potential performance issues when dealing with very large directories."`

- [ ] **Step 7: Update task_025 prompt**

Change `"Analyze the image at 'test_image.jpg' and describe its contents."` to `"Analyze the image at 'samples/test_image.jpg' and describe its contents."`

- [ ] **Step 8: Update task_026 prompt**

Change `"Analyze the video at 'test_video.mp4' and summarize what happens."` to `"Analyze the video at 'samples/test_video.mp4' and summarize what happens."`

- [ ] **Step 9: Commit**

```bash
git add evals/tasks.json
git commit -m "fix: update stale agents.py references and file paths in eval tasks"
```

---

## Chunk 3: Add new eval tasks for missing tool categories

### Task 3: Append 8 new dry-run eval tasks to tasks.json

**Files:**
- Modify: `evals/tasks.json`

- [ ] **Step 1: Add task_028 (GitHub Tools)**

```json
{
  "id": "task_028",
  "category": "GitHub Tools",
  "prompt": "Explain step by step how you would use the available GitHub tools to create a new branch called 'feature/login', commit a file to it, open a pull request, and create a GitHub issue. Describe each tool call and its parameters. Do not actually execute these actions.",
  "expected_output": "Step-by-step explanation of GitHub tool usage covering branch creation, file commit, PR creation, and issue creation."
}
```

- [ ] **Step 2: Add task_029 (Travel Tools)**

```json
{
  "id": "task_029",
  "category": "Travel Tools",
  "prompt": "Explain how you would use the travel tools to search for flights from New York to London on 2025-06-15, book the cheapest option, retrieve the booking details, list all current bookings, and then cancel the booking. Describe each tool call and its parameters. Do not actually execute these actions.",
  "expected_output": "Step-by-step explanation covering flight search, booking, retrieval, listing, and cancellation."
}
```

- [ ] **Step 3: Add task_030 (Document Creation)**

```json
{
  "id": "task_030",
  "category": "Document Creation",
  "prompt": "Explain how you would create each of the following documents using the available tools: a PDF report titled 'Monthly Sales Summary' with a table, an Excel spreadsheet with sales data, a DOCX document with a project proposal, and a PPTX presentation with three slides. Describe each tool call and its parameters. Do not actually execute.",
  "expected_output": "Detailed explanation of tool calls for creating PDF, Excel, DOCX, and PPTX documents."
}
```

- [ ] **Step 4: Add task_031 (Document Read/Edit)**

```json
{
  "id": "task_031",
  "category": "Document Read/Edit",
  "prompt": "Explain how you would read and then edit each of the following document types: a PDF file 'report.pdf', a DOCX file 'proposal.docx', an Excel file 'data.xlsx', and a PPTX file 'slides.pptx'. For each, describe the read tool call to inspect contents and the edit tool call to make a change. Do not actually execute.",
  "expected_output": "Step-by-step explanation of read and edit tool calls for PDF, DOCX, Excel, and PPTX files."
}
```

- [ ] **Step 5: Add task_032 (Audio Recognition)**

```json
{
  "id": "task_032",
  "category": "Audio Recognition",
  "prompt": "Explain how you would use the audio recognition tool to transcribe or analyze an audio file called 'samples/meeting_recording.wav'. Describe the tool call you would make and what parameters it requires.",
  "expected_output": "Explanation of the audio recognition tool call with appropriate parameters."
}
```

- [ ] **Step 6: Add task_033 (Directory Navigation)**

```json
{
  "id": "task_033",
  "category": "Directory Navigation",
  "prompt": "Explain how you would use the change working directory tool to navigate to a subdirectory called 'data/raw' and then list its contents using the list files tool. Describe each step and tool call.",
  "expected_output": "Step-by-step explanation of directory change and file listing tool calls."
}
```

- [ ] **Step 7: Add task_034 (Browser Automation)**

```json
{
  "id": "task_034",
  "category": "Browser Automation",
  "prompt": "Explain how you would use the Playwright MCP tool to automate opening a browser, navigating to a URL, and extracting text from a page. Describe the tool call and its parameters. Do not actually execute.",
  "expected_output": "Explanation of Playwright MCP tool usage for browser automation."
}
```

- [ ] **Step 8: Add task_035 (Email Composition)**

```json
{
  "id": "task_035",
  "category": "Email Composition",
  "prompt": "Explain how you would compose and send an email using the Gmail tool to 'test@example.com' with the subject 'Meeting Follow-up' and a body summarizing action items. Describe the tool call and its parameters. Do not actually execute.",
  "expected_output": "Explanation of Gmail compose tool call with recipient, subject, and body parameters."
}
```

- [ ] **Step 9: Verify tasks.json is valid JSON**

Run: `cd /c/Users/Frank/ai_agent && python -c "import json; tasks = json.load(open('evals/tasks.json')); print(f'{len(tasks)} tasks loaded')"`

Expected: `35 tasks loaded`

- [ ] **Step 10: Commit**

```bash
git add evals/tasks.json
git commit -m "feat: add eval tasks for GitHub, travel, document, audio, navigation, browser, and email tools"
```
