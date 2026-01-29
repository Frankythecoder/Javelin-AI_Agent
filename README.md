# AI Agent Django Project

## Overview

This project is a Django-based web application that integrates with OpenAI's generative AI models to provide agentic code generation, file management, and chat capabilities. It features a modern chat UI, advanced agentic tools for sandboxed execution, and a comprehensive evaluation framework for research and benchmarking.

---

## Features

- **OpenAI Integration:**
  Utilizes the `gpt-4o` model for high-performance reasoning and code generation.

- **Agentic File & System Tools:**
  - **Broad Search Capability:** Automatically searches common user directories (Desktop, Documents, Downloads, Pictures, etc.) if a file or directory is not found in the current working directory.
  - **CRUD Operations:** Read, list, create, edit, delete, and rename files of any type using both **absolute and relative paths**.
  - **Enhanced Reading:** `read_file` supports character offsets, size limits, and automatically prompts to use vision tools for images.
  - **Vision & Multimedia:** Built-in support for `recognize_image` and `recognize_video` using GPT-4o vision (requires `opencv-python`).
  - **Sandboxed Execution:** A dedicated `run_code` tool allows the agent to execute shell commands and Python scripts to verify its work.
  - **Self-Reflection:** Built-in system instructions prompt the agent to verify filesystem states and iteratively correct errors.

- **Automated Evaluation Framework:**
  - **Benchmark Dataset:** 24+ diverse tasks covering debugging, refactoring, and multi-step reasoning.
  - **Automated Runner:** Systematic evaluation of agent performance with rate-limiting support for free-tier API keys.
  - **Quantitative Metrics:** Automated success rate calculation and category-specific breakdown.

- **Modern Web Interface:**
  - Responsive chat UI for real-time interaction.
  - RESTful API endpoints for programmatic integration.

---

## Project Structure

```
ai_agent/
├── agents.py                # Core agent logic, self-reflection, and tool definitions
├── evals/                   # Evaluation Framework
│   ├── tasks.json           # Benchmark task dataset
│   ├── runner.py            # Automated evaluation execution script
│   ├── metrics.py           # Quantitative analysis and reporting script
│   ├── baseline_results.json # Ablation study baseline results
│   └── full_results.json     # Full feature evaluation results
├── chat/                    # Django app for the web interface
│   ├── templates/chat/index.html
│   └── views.py             # Chat API and page logic
├── settings.py              # Django configuration (uses .env for secrets)
├── report_content.txt       # Detailed research report and ablation study
├── requirements.txt         # Project dependencies
└── manage.py                # Django management script
```

---

## Setup

### 1. Clone the Repository

```sh
git clone <your-repo-url>
cd ai_agent
```

### 2. Install Dependencies

Requires Python 3.8+.

```sh
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_openai_api_key

# Gmail Configuration
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_PASSWORD=your_16_char_app_password

# Browser Configuration (Optional)
CHROME_PROFILE_DIRECTORY=Profile 23

# Optional S3 support
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_STORAGE_BUCKET_NAME=your_bucket
```

---

## Gmail & Chrome Profile Setup

The agent includes a specialized `open_gmail_and_compose` tool that can create drafts with attachments and open them in a specific Chrome profile.

### 1. Gmail Tool Configuration
To enable the Gmail tool:
- **Enable IMAP**: Go to Gmail Settings > Forwarding and POP/IMAP and ensure **Enable IMAP** is selected.
- **Generate App Password**: If you have 2-Step Verification enabled, go to your Google Account security settings and create a 16-character **App Password**.
- **Update `.env`**: Add your `GMAIL_ADDRESS` and `GMAIL_PASSWORD` (the app password).

### 2. Chrome Profile Selection
The agent can open Gmail in the specific Chrome profile where you are already logged in:
- **Auto-Discovery**: By default, `agents.py` scans your local Chrome `User Data` directory to find the profile associated with your `GMAIL_ADDRESS`.
- **Manual Setting**: If you want to force a specific profile, find your profile folder name (e.g., `Default`, `Profile 1`, `Profile 23`) and set it as `CHROME_PROFILE_DIRECTORY` in your `.env` file.
- **How to find your profile name**: Visit `chrome://version/` in Chrome and look at the **Profile Path**. The last part of the path (e.g., `Profile 23`) is your directory name.

---


### 4. Database Migration

```sh
python manage.py migrate
```

### 5. Run the Server

```sh
python manage.py runserver
```
Visit [http://localhost:8000/](http://localhost:8000/) to access the chat UI.

---

## Evaluation & Benchmarking

The project includes a robust evaluation pipeline for research purposes.

### Run Automated Evaluation
To run the agent against the benchmark dataset:
```sh
# Full evaluation
python evals/runner.py full_results.json

# Baseline (Ablation) evaluation
# (Requires manually disabling features in agents.py first)
python evals/runner.py baseline_results.json
```

### Generate Metrics
To analyze the results and see success rates:
```sh
python evals/metrics.py full_results.json
```

---

## How it Works: Broad File Search

The agent is designed to be helpful even when the user provides incomplete paths. When a tool (like `read_file` or `delete_file`) is called with a filename that doesn't exist in the current directory:

1.  **Direct Check**: It first checks if the path is absolute or exists relative to the current directory.
2.  **Well-Known Folders**: It checks common user folders (Desktop, Documents, Downloads, Pictures, Videos, etc.).
3.  **Recursive Search**: It performs a limited-depth recursive search (up to 4 levels) in those common directories to find the most likely match.
4.  **Auto-Resolution**: If found, it automatically resolves to the absolute path for the requested operation.

---

## Usage

- **Chat with OpenAI:** Use the web UI or POST to `/api/chat/`.
- **System Tasks:** Ask the agent to "Find the image named 'receipt' on my desktop and tell me what it says".
- **File Management:** "Create a new python script in a folder called 'scripts' that prints hello world".
- **Self-Correction:** The agent will automatically attempt to fix errors if a tool execution fails.

---

## Security

> [!WARNING]
> **High Privilege Access**: The file tools now accept **absolute paths**. This allows the agent to read, write, delete, and rename files anywhere on the system that the process has permission for. Use with extreme caution.

- File operations are restricted by the OS-level permissions of the user running the Django server.
- API keys are managed via environment variables.
- Sandboxed execution is performed in the local shell; avoid running as Administrator/Root in production environments.

---

## What This Agent Is Currently Capable Of

**Local OS-Level File System Access**

- Reads files using absolute or relative paths
- **Broad file discovery across**: Desktop, Documents, Pictures/Videos and Onedrive (where available).
- Partial name matching and recursive search
- Directory listing
- This mimics human-like OS navigation, not API-only access.

**File Creation & Modification**

- Create new files at arbitrary paths
- Edit existing files using string replacement
- Rename files
- Delete files or entire directories

## ⚠️ Extremely powerful, but high risk without strict controls.

**Code Execution & Validation**

- Execute shell commands locally
- Run scripts (Python, Node, etc.)
- Syntax checking for multiple languages
- Run test suites automatically
- Run static analysis (linting)
- This makes the agent comparable to a junior DevOps / software engineer.

**Gmail Integration (Local Account)**

- Open Gmail compose window in correct Chrome profile
- Create Gmail drafts via IMAP
- Attach files programmatically
- HTML + plain-text email bodies
- Fallback mechanisms if IMAP fails
- Email is created inside the user’s own Gmail account, not via third-party servers.

**Browser Automation**

- Open URLs automatically
- Select Chrome profiles based on email identity

**Image & Video Understanding**

- Image analysis via GPT-4o Vision
- Video analysis via frame extraction + vision model
- Automatic detection of binary/image files

**Tool-Oriented Agent Architecture**

- Explicit tool definitions
- Tool execution logging
- Approval-required tools (HITL)
- Automatic retries and follow-up reasoning

**Docker Sandboxing**

- Agent runs inside Docker container
- Isolated execution environment
- Resource limits enforced at container level

**Human-in-the-Loop**
- Approve / deny actions before execution
- Manual gating of destructive operations

## Why This Agent Is More Capable Than Common Agents

**Compared to typical SaaS or framework-based agents, this system:**

- Works directly on the user’s machine
- Handles real OS files instead of abstract documents
- Interacts with Gmail natively
- Executes real commands instead of simulating actions
- Requires no cloud-side file uploads
- **It is best categorized as a**: Local AI Operator / Copilot, not a chatbot

## Why This Is NOT Yet a Sellable Product

**Despite technical power, the agent is currently:**
- Too permissive
- Too broad in scope
- Too risky for non-technical buyers
- Insufficiently transparent for security review
- To sell this agent, power must be converted into controlled, user-consented power.

## Features That MUST Be REMOVED (or Hard-Disabled)

- Arbitrary Shell Execution
- run_code
- **Reason**: Severe security risk, Unacceptable for sales, enterprise, or consumer environments
- **Replacement**: Allowlisted, fixed-function commands only (if any)

**Unrestricted File Deletion & Renaming**

- delete_file
- rename_file

- **Reason**: High risk of irreversible damage, Legal and compliance concerns

**Broad Filesystem Search by Default**

- Global recursive file discovery

- **Reason**: Privacy violation risk, Accidental exposure of sensitive data

**Video Recognition (Optional Removal)**

- **Reason**: High cost, Low ROI for most buyers, Difficult to justify in security reviews

## Features That MUST Be RESTRICTED (Not Removed)

- **File Access**: Must be sandboxed to user-approved directories only
- **Default**: no access, Explicit opt-in required
- **Gmail Integration**: Rate limits per day
- **Image Recognition**: Business use only (documents, screenshots), No personal photos

## Features That MUST Be ADDED (Non-Negotiable)

**Permission & Scope System**

- **Persistent permission model**: File read scopes, File write scopes, Email scopes, Browser scopes
- **Permissions must be**: Explicit, Revocable and Visible to the user

**Immutable System Instructions**

- System prompt must be locked
- Tool descriptions cannot be overridden
- Prevent prompt injection and jailbreaks

**Local Audit Timeline**

- Human-readable, exportable log:
- Timestamp
- Action
- Target
- Approval decision
- Stored locally and owned by the user.

**Dry-Run Mode**

- Agent plans actions
- Executes nothing
- Shows full plan
- Recommended default for first-time users.

**Kill Switch**

- **Instant ability to**: Pause agent, Cancel queued actions, Disable all tools

**Resource & Execution Limits**

- **Enforce**: Max tools per request, Max execution time, CPU / memory caps, Docker alone is insufficient.

**Bring-Your-Own-Key (BYOK)**

- User provides LLM API keys
- No proxying through vendor servers
- No prompt or output logging by default

**Clear Data Flow Disclosure**

- **Plain-English explanation of**: What data stays local, What data is sent to the LLM, What is never uploaded, Critical for trust and legal review.

## Competitive Advantage Recommendations

**Local LLM Mode**

- Ollama / LM Studio support
- Full offline execution

**Enterprise Policy Files**

Example:

```sh
filesystem:
  read_only: true
email:
  enabled: false
browser:
  allowed_domains:
    - gmail.com
```
**Prompt Injection Detection**

- **Basic heuristics to block**: Instruction override attempts, Privilege escalation prompts

## LangChain & LangGraph Integration Plan

- This agent can be further hardened and modularized by integrating LangChain and LangGraph without changing its core capabilities.
- The goal of this integration is structure, control, and observability — not adding abstraction for its own sake.

**Why Integrate LangChain?**

- LangChain should be used as a tool orchestration and interface layer, not as the execution engine.
- **LangChain will provide**:Standardized tool schemas, Consistent tool calling across LLM providers, Easy model swapping (OpenAI, Anthropic, local models), Callback hooks for logging, tracing, and cost tracking
- **LangChain should NOT**:Access the filesystem directly, Execute shell commands, Bypass Docker or permission checks

**LangChain Architecture Mapping**

- **Current Component	LangChain Equivalent**:
- Tool definitions	@tool decorators
- Agent prompt	ChatPromptTemplate
- Tool routing	AgentExecutor
- HITL approval	Custom callback / wrapper

**Important rule**:

- LangChain tools must act as thin adapters that call your existing, sandboxed Python functions.

**Why LangGraph Is Critical for Production?**

- LangGraph is strongly recommended for production readiness.
- **It enables**: Explicit state machines, Deterministic control flow, Retry & failure branches, Human approval nodes, Hard execution boundaries
- This solves the biggest weakness of free-form agents: uncontrolled execution paths.

**LangGraph State Design**

Recommended shared state:

```sh
AgentState = {
  "user_input": str,
  "plan": list,
  "approved": bool,
  "tool_queue": list,
  "audit_log": list,
  "permissions": dict,
  "errors": list
}
```
**Recommended LangGraph Node Layout**

```sh
[User Input]
      ↓
[Planner Node]
      ↓
[Permission Check Node]
      ↓
[Human Approval Node]
      ↓
[Tool Execution Node]
      ↓
[Audit Logger Node]
      ↓
[Response Node]
```

- **Each node must be**: Side-effect free (except execution node), Deterministic and Fully logged

**Planner–Executor Separation (Mandatory)**

- **Use LangGraph to enforce a strict split**: Planner, Generates step-by-step plan, No tool execution, Executor, Executes exactly one approved tool per step, Cannot re-plan
- This prevents runaway autonomy and increases trust.

**Human-in-the-Loop via LangGraph**

- HITL should be a first-class node, not a conditional check.
- **Capabilities**: Pause graph execution, Resume on approval, Abort cleanly on denial
- **This allows future upgrades such as**: Multi-user approval, Admin overrides

**Callback & Observability Integration**

- **Use LangChain callbacks for**: Token usage tracking, Tool invocation logging, Latency measurement, Error reporting
- All callback data must remain local by default.

**Migration Strategy (Safe & Incremental)**

- Wrap existing tools with LangChain adapters
- Replace direct LLM calls with LangChain models
- Introduce LangGraph for planning + execution
- Gradually move logic into graph nodes
- Lock execution behind approval + scopes
- No rewrite required.

**What LangChain / LangGraph Must NOT Control**

- Docker sandbox
- OS-level permissions
- Gmail credentials
- File system boundaries
- These remain outside the agent framework for security reasons.

## Final Product Positioning

- **A local-first AI operator that works inside your computer, not on someone else’s server.**

## Definition of “Sellable”

**This agent is sellable when:**

- Nothing executes without user consent
- All access is scoped and revocable
- All actions are previewed
- All actions are logged
- Users can stop it instantly
- No unexpected data leaves the machine

## Final Note

- **The hardest part**: capability — is already built.
- The remaining work is trust engineering, not AI research.
- **If these guidelines are followed, this agent becomes**: A professional-grade local AI copilot suitable for real customers, teams, and enterprises.

## License

MIT License

---

## Acknowledgments

- [OpenAI](https://openai.com/)
- [Django Framework](https://www.djangoproject.com/)
