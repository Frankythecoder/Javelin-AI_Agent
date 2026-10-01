# Javelin: a Local-First AI Agent with Experience-Augmented Tool Planning

## Overview

Javelin is a local-first, tool-using AI agent built on Django, LangChain and LangGraph. It works with your real files, shell, documents, GitHub repositories, browser, email and travel bookings through **41 tools**. Human-in-the-loop safety gates control what it can do.

The project's research contribution is **EATP (Experience-Augmented Tool Planning)**. EATP is a retrieval memory over the agent's own past executions. It lets the agent learn from earlier successes, failures and user corrections without fine-tuning. The repository includes a 100-task evaluation harness with ablation baselines that measures EATP's effect.

**Three ways to use it** (all share one `Agent` core):

| Interface | Command |
|---|---|
| Web UI (Django + vanilla JS) | `python manage.py runserver` → http://localhost:8000/ |
| Terminal UI (Textual) | `python tui.py` (or `javelin` after `pip install -e .`) |
| Plain CLI REPL | `python -m agents.core` |

> For a component-by-component walkthrough (graph nodes, message formats, concurrency, extension points), see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Key Features

### Agent core (LangGraph)
- **LangGraph state machine:** `classify_task → call_model → collect_dry_run | execute_or_hold_tools → format_output`, with a recursion limit of 25 and a node trace kept in `execution_path`.
- **Heavy/light model routing:** a light model sorts each task as `heavy` or `light`. Heavy tasks go to the heavy model and light tasks to the cheaper model. Both models are set in `.env` (`MODEL_NAME`, `LIGHT_MODEL_NAME`; defaults `gpt-6-sol` / `gpt-5.6-terra`).
- **Context management:** a rolling history window (`max_history=15`) that never separates a tool call from its result. Dropped turns are compressed into an LLM-written running summary.
- **Tool-call pairing repair:** if a plan is stopped or partly denied, each unanswered tool call gets an explicit "not executed" placeholder. Tool results left without a parent are removed. This keeps the history valid for the API.
- **Interrupted-task resume:** when the user says "continue", "resume", "retry" and so on, the agent finds the interrupted work and adds context so it can pick up where it stopped.
- **20-rule system instruction:** covers task classification (SIMPLE vs COMPLEX → explore/clarify/plan/execute), self-recovery (up to 3 alternative approaches before escalating), exact document page counts, and GitHub-through-MCP-only.

### Human-in-the-loop safety
- **Dry-run mode (default for new tasks):** the agent proposes the full plan with a plain-English summary. Nothing runs until you approve it.
- **Per-tool approval:** after a plan is approved, follow-up high-risk tools (delete, run code, GitHub writes, bookings, edits) still need individual approval. Read-only tools run automatically.
- **Stop button and tool kill switch:** thread-safe `AgentControlState`. The flags are checked before every tool dispatch and at every graph node.
- **Prompt-injection screening:** about 13 regex patterns (instruction overrides, privilege escalation) block a message before it reaches the LLM.
- **Audit trail:** every tool call is written to the `ToolLog` table, whether it succeeds or fails.
- **Output limits:** 10K characters for shell output and file reads, 6K for browser page text.

### EATP: Experience-Augmented Tool Planning
- After each task, an `ExperienceRecord` is stored in **ChromaDB** (HNSW, cosine). It holds the task, its category, the planned and executed tools, the results, the outcome, user corrections and approval/denial actions.
- Before planning, similar past experiences are retrieved with `text-embedding-3-small`. Matches below 0.75 similarity are dropped. The rest are **re-ranked in this order: records with corrections, then failures, then similarity × recency**. Recency decays from 30 to 180 days, and repeated confirmations give a boost. The results are added to the system prompt as "Lessons from Past Experience" within an 800-token budget.
- **Deduplication:** near-duplicate records (similarity > 0.95) are merged. The merge increments `confirmation_count` and combines the corrections.
- **Feedback:** the `rate_experience` tool lets the user rate the last task from 1 to 5.
- **Migration script** (`agents/migrate_experiences.py`) re-embeds stored records when the embedding model changes.
- The production store lives at `~/.ai_agent/experiences`. Evaluations use a separate store at `~/.ai_agent/experiences_eval`.

### MCP integration
- `mcp_servers/github_server.py`: a FastMCP server for branch, commit, local-file commit and pull-request creation.
- `mcp_servers/playwright_server.py`: a FastMCP server for headless navigation, screenshots and page-text extraction. It retries with and without the `www.` prefix.
- The agent starts these servers as stdio subprocesses. Any MCP-compatible host can use them too.

---

## Tool Catalog (41 tools)

| Category | Module | Tools | Approval |
|---|---|---|---|
| File & system (9) | `agents/file_tools.py` | `search_file`, `read_file`, `list_files`, `find_file_broadly`, `find_directory_broadly`, `create_and_edit_file`, `delete_file`, `rename_file`, `change_working_directory` | Required for writes, deletes, renames and `cd` |
| Code (4) | `agents/code_tools.py` | `run_code`, `check_syntax`, `run_tests`, `lint_code` | Required for `run_code` |
| Multimedia (3) | `agents/multimedia_tools.py` | `recognize_image`, `recognize_video` (OpenCV frames + GPT-4o), `recognize_audio` (GPT-4o audio, pydub conversion) | None |
| Document creation (4) | `agents/document_tools.py` | `create_pdf`, `create_docx`, `create_excel`, `create_pptx` (Markdown input, `<!-- PAGE_BREAK -->` markers) | None |
| Document read/edit (8) | `agents/document_rw_tools.py` | `read_/edit_` for pdf, docx, excel, pptx (PyMuPDF with pdfplumber fallback) | Required for edits |
| GitHub (5) | `agents/github_tools.py` | `github_create_branch`, `github_commit_file`, `github_commit_local_file`, `github_create_pr` (MCP), `create_github_issue` (REST) | Required |
| Email (1) | `agents/email_tools.py` | `open_gmail_and_compose`: IMAP draft with attachments, opened in the Chrome profile that matches the address | None |
| Browser (1) | `agents/email_tools.py` | `playwright_navigate` | Required |
| Travel (5) | `agents/travel_tools.py` | `search_flights`, `book_travel`, `get_booking`, `list_bookings`, `cancel_booking` (Duffel API) | Required for booking and cancelling |
| Feedback (1) | `agents/feedback_tools.py` | `rate_experience` (EATP) | None |

The broad file search looks in Desktop, Documents, Downloads, Pictures, Videos, OneDrive and common project folders, up to 4 levels deep, with fuzzy filename matching.

---

## Project Structure

```
ai_agent/
├── manage.py                  # Django entrypoint
├── tui.py                     # Textual terminal UI
├── pyproject.toml             # `javelin` console script
├── requirements.txt
├── sampleenv.txt              # template for .env
├── Dockerfile.sandbox         # sandbox image for code execution (planned)
├── ARCHITECTURE.md            # in-depth architecture reference
│
├── config/                    # Django project: settings (env-driven), urls, wsgi/asgi
├── chat/                      # Django app
│   ├── models.py              # ToolLog, ChatSession, Booking
│   ├── views.py               # JSON API + single shared Agent instance
│   ├── urls.py
│   ├── templates/chat/index.html
│   ├── static/chat/{css,js}/  # chat.css, chat.js
│   └── management/commands/   # showlogs, export_logs_csv
│
├── agents/                    # Agent package
│   ├── core.py                # Agent class, AgentState, LangGraph, system instruction, CLI main()
│   ├── agent_messages.py      # message conversion, trimming, summarization, pairing repair
│   ├── control.py             # AgentControlState, ToolDefinition, ApprovalAwareTool
│   ├── helpers.py             # broad file search, URL normalization, prompt-injection check
│   ├── *_tools.py             # tool implementations by category
│   ├── experience_store.py    # EATP: ExperienceRecord + ChromaDB store
│   ├── experience_logger.py   # EATP: record builder, category inference
│   └── migrate_experiences.py # EATP: re-embedding on model change
│
├── mcp_servers/               # github_server.py, playwright_server.py
├── evals/                     # evaluation harness (see below)
├── tests/                     # pytest suite
├── samples/                   # sample input files
└── assets/                    # logo
```

---

## Setup

### 1. Install dependencies

Python 3.8+ is required. Python 3.10+ is recommended for LangGraph and ChromaDB.

```bash
git clone https://github.com/Frankythecoder/ai_agent.git
cd ai_agent
pip install -r requirements.txt
pip install textual matplotlib numpy PyMuPDF   # TUI, figure generation, PDF reading
playwright install chromium                     # browser automation
```

### 2. Configure `.env`

Copy `sampleenv.txt` to `.env` in the project root and fill in the values:

```env
OPENAI_API_KEY=...                 # required: LLM, embeddings, vision, audio
MODEL_NAME=gpt-6-sol               # heavy model
LIGHT_MODEL_NAME=gpt-5.6-terra     # light model (also used for task classification)
LLM_REQUEST_TIMEOUT=180            # optional; seconds per LLM call

GMAIL_ADDRESS=you@gmail.com        # optional: Gmail drafts via IMAP
GMAIL_PASSWORD=xxxx xxxx xxxx xxxx # 16-char Google app password
CHROME_PROFILE_DIRECTORY=Default   # optional; auto-detected from GMAIL_ADDRESS

GITHUB_TOKEN=...                   # optional: GitHub tools
GITHUB_REPO=owner/repo

DUFFEL_API_TOKEN=...               # optional: flight search/booking

AWS_ACCESS_KEY_ID=...              # optional: S3 static storage (production)
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...
AWS_S3_REGION_NAME=...
```

**Gmail:** enable IMAP in Gmail settings. Then create an App Password under Google Account → Security, which needs 2-Step Verification turned on. To match your address, the agent reads each Chrome profile's `Preferences` file. To set the profile manually, open `chrome://version/` and copy the last part of the *Profile Path*.

### 3. Create the database and run

```bash
python manage.py migrate
python manage.py runserver        # web UI at http://localhost:8000/
# or
python tui.py [--dir PATH] [--load]
```

---

## How a Request Flows

```
User message
   │  prompt-injection check ──► blocked? → security warning
   │  EATP retrieve → "Lessons from Past Experience" added to system prompt
   ▼
classify_task (light model) ──► heavy | light
   ▼
call_model (tools bound)
   ├─ no tool calls ───────────────► format_output → status "success"
   ├─ fresh task (dry-run mode) ───► collect_dry_run → status "dry_run" (plan + summary)
   └─ follow-up (per-tool mode) ───► execute_or_hold_tools
                                       ├─ high-risk → status "pending" (await approval)
                                       └─ low-risk  → execute, loop back to call_model
After execution: ExperienceRecord built and stored in ChromaDB
```

### HTTP API (`chat/urls.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/chat/` | POST | Main chat. Dispatches on `status`: none, `dry_run_approved`, `dry_run_denied`, `approved`, `denied` |
| `/api/agent/control/` | POST | `{"action": "stop" \| "disable_tools" \| "enable_tools"}` |
| `/api/chats/` | GET / POST | List / save chat sessions |
| `/api/chats/<id>/` | GET / DELETE | Load / delete a session |
| `/api/files/` | GET | List files in the working directory |
| `/api/graph/` | GET | Mermaid diagram of the LangGraph |
| `/api/test-error/` | POST | Inject a failure at a named graph node (testing) |
| `/api/shutdown/` | POST | Stop the dev server |

Example: a fresh request returns a plan, and a second request approves it.

```bash
curl -X POST localhost:8000/api/chat/ -H "Content-Type: application/json" \
  -d '{"message": "Create fibonacci.py and run it", "history": []}'
# → {"status": "dry_run", "dry_run_plan": [...], "response": "...", "history": [...]}

curl -X POST localhost:8000/api/chat/ -H "Content-Type: application/json" \
  -d '{"status": "dry_run_approved", "dry_run_plan": [...], "history": [...]}'
```

Tool logs: `python manage.py showlogs` or `python manage.py export_logs_csv tool_logs.csv`.

---

## Evaluation Framework (`evals/`)

This harness evaluates EATP for the paper.

- **`tasks.json`:** 100 tasks in 8 categories: File Operations (15), Code Tasks (15), Document Creation/Editing (15), Cross-category (15), Travel/Booking (10), GitHub Operations (10), Multimedia (10) and Multi-tool Orchestration (10). Each task has a `task_class`, a `lesson_id`, an expected output and seed files.
- **Workspace isolation:** each task runs in a fresh temporary directory, with seed files copied in from `evals/seeds/`.
- **`mocks.py`:** deterministic stand-ins for 12 external API tools (Duffel, Gmail, GitHub, Playwright), so runs can be reproduced.
- **`validators.py`:** a ground-truth checker for each task, built from 8 primitives (file exists or contains text, response mentions something, a tool was called, a script runs, and others). Results report a *validated* success rate, not just completion.
- **`correction_policy.json`:** scripted user denials and corrections for 21 tasks, used in the populate phase.
- **`transfer_map.json`:** 21 test tasks mapped to lessons from different tasks, used to measure cross-task transfer.
- **`static_fewshot.py`:** fixed few-shot examples for the static baseline.

### Experimental conditions (`--eatp-mode`)

| Mode | Condition |
|---|---|
| `off` | No memory (baseline) |
| `static-fewshot` | Fixed hand-written examples in the prompt (control) |
| `cold` | EATP starts empty and learns during the run. With `--correction-policy` this is the populate phase |
| `warm-successes` | Warm store with corrections removed (ablation) |
| `warm` | Full EATP on a pre-populated store |

### Running the experiments

Run every command from the repository root. Output files are written to `evals/`.

```bash
python evals/runner.py --eatp-mode off            --output results_off.json
python evals/runner.py --eatp-mode static-fewshot --output results_static_fewshot.json
python evals/runner.py --eatp-mode cold           --output results_phase_a.json \
                       --correction-policy correction_policy.json
python evals/runner.py --eatp-mode warm-successes --output results_warm_successes.json
python evals/runner.py --eatp-mode warm           --output results_phase_c.json

python evals/compare_phases.py      # 5-way comparison, per-category deltas, correction carryover, transfer rate, paper summary
python evals/generate_figures.py    # 4 paper figures → evals/figures/
python evals/metrics.py results_off.json   # quick metrics for a single run
```

> `evals/full_results.json` and `evals/baseline_results.json` come from the earlier 27-task suite. They are kept for reference and are not comparable with the 100-task suite.

---

## Testing

```bash
pytest tests/
```

| Test file | Covers |
|---|---|
| `test_experience_store.py` | ChromaDB add/retrieve, deduplication, recency decay, prompt formatting |
| `test_experience_logger.py` | Record building, category inference, argument summarization |
| `test_feedback_tools.py` | `rate_experience` wiring |
| `test_eatp_integration.py`, `test_eatp_manual.py` | End-to-end EATP inside `chat_once` / `execute_dry_run` |
| `test_orphaned_tool_calls.py` | Tool-call/response pairing repair |
| `test_llm_config.py` | LLM client config (`reasoning_effort="none"` with tools bound, Responses API routing for `gpt-6-astra`, request timeout) |
| `test_mcp_navigate.py`, `test_normalize_url.py` | Playwright navigation, URL normalization, `www.` retry |
| `test_mocks.py`, `test_validators.py`, `test_static_fewshot.py` | Evaluation harness components |

---

## Notes on LLM Configuration

- Both models are set through environment variables and read in `config/settings.py`. They are no longer hard-coded in `views.py`, `tui.py`, `agents/core.py` or the eval runner.
- The agent calls the Chat Completions endpoint with `reasoning_effort="none"`. Reasoning models reject bound function tools there otherwise.
- Some models, such as `gpt-6-astra`, don't support `reasoning_effort="none"`, and on Chat Completions they reject function tools at every other effort level. These models go through the Responses API with `reasoning_effort="low"`, and their content blocks are flattened back to a plain string. Set the list with `RESPONSES_API_MODELS` (comma-separated, default `gpt-6-astra`) and the effort with `RESPONSES_REASONING_EFFORT`.
- Each LLM call has a 180s timeout by default (`LLM_REQUEST_TIMEOUT`). A complex task can generate about 10K tokens in one tool call, and the old 30s timeout cut those responses off.
- Vision and audio tools call `gpt-4o` / `gpt-4o-audio-preview` directly. EATP embeddings use `text-embedding-3-small`.

---

## Security

**This agent has high-privilege local access.** It can read and write any path the process can reach, run shell commands, create email drafts, push to GitHub and book flights.

- Review dry-run plans before approving them. Destructive tools always need approval.
- Run the agent as a non-privileged user, never as Administrator or root.
- Keep `.env` out of version control. It is already git-ignored.
- Regex injection screening is a first line of defense, not a guarantee. The approval gates are the real safeguard.
- **Sent to OpenAI:** user messages, agent responses, tool arguments and results, and embeddings of task descriptions. **Kept local:** `.env`, the SQLite database, the ChromaDB experience store, and files you haven't asked the agent to analyze.

---

## Development History

| Period | Milestone |
|---|---|
| Sep 2025 to Jan 2026 | Monolithic `agents.py` with OpenAI function calling, dry-run and per-tool approval, stop/kill switch, Gmail, GitHub and Playwright MCP, multimedia and document tools |
| Feb 2026 | LangChain/LangGraph migration and Duffel flight booking. Textual TUI with a LangGraph view. URL normalization and `www.` retry for Playwright |
| Mar 2026 (early) | Refactor into the `agents/` package. CSS and JS moved out of the template. Direct imports replace S3 module loading. `config/`, `mcp_servers/` and `samples/` reorganized |
| Mar 2026 (mid) | Eval runner switched to dynamic tool discovery. Eval tasks added for every tool category |
| Mar 2026 (late) | **EATP**: ChromaDB experience store, logger, feedback tool, retrieval in `chat_once`, embedding migration. Eval expansion to 100 tasks with validators, mocks, workspace isolation, 5 conditions, transfer analysis and paper figures |
| Jul to Sep 2026 | Configurable models (`MODEL_NAME` / `LIGHT_MODEL_NAME`), `reasoning_effort` and timeout fixes, full-history tool-call pairing repair, new regression tests |

### Roadmap
- Run the full 5-condition experiment on the 100-task suite and report the results
- Use `rate_experience` ratings as a ranking signal in EATP retrieval
- Sandbox `run_code` in a container (`Dockerfile.sandbox`)
- Scope file access with allowlists and add per-user tool policies
- Support more LLM providers through LangChain adapters

---

## License

MIT License. Copyright (c) 2025 Frank

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Acknowledgments & Contact

Built with [OpenAI](https://openai.com/), [Django](https://www.djangoproject.com/), [LangChain](https://www.langchain.com/) / [LangGraph](https://www.langchain.com/langgraph), [ChromaDB](https://www.trychroma.com/), [Model Context Protocol](https://modelcontextprotocol.io/), [Playwright](https://playwright.dev/), [Textual](https://textual.textualize.io/) and [Duffel](https://duffel.com/).

**Issues:** [GitHub Issues](https://github.com/Frankythecoder/ai_agent/issues) · **Security contact:** diviyanfrankjeyasingh@gmail.com
