# AI Agent Django Project

## Overview

This project is a Django-based web application that integrates with OpenAI's GPT-4o model to provide advanced agentic capabilities with human-in-the-loop controls. The system features a modern chat UI, 25+ specialized tools for file management, code execution, multimedia processing, and external integrations, along with comprehensive safety mechanisms including dry-run mode, agent control, and prompt injection detection.

---

## 🚀 Key Features

### **Core Agent System**
- **Dual-Mode Operation:**
  - **Dry-Run Mode:** Agent generates a complete action plan and waits for user approval before executing anything (default for new tasks)
  - **Per-Tool Approval:** After dry-run approval, individual high-risk tools still require approval while low-risk tools execute automatically
- **Agent Control System:**
  - **Stop Button:** Immediately halt agent execution mid-task
  - **Tool Enable/Disable:** Globally enable or disable all tool execution with a kill switch
  - **Thread-Safe State Management:** All control operations are thread-safe using locks
- **Prompt Injection Detection:** Built-in heuristics to detect and block potential prompt injection attacks

### **File & System Operations (8 Tools)**
- **Broad Search Capability:** Automatically searches common user directories (Desktop, Documents, Downloads, Pictures, OneDrive, etc.) when files aren't found in the current directory
- **File CRUD Operations:**
  - `read_file` - Read with offset/limit support and binary file detection
  - `list_files` - Directory listing with file/folder differentiation
  - `search_file` / `find_file_broadly` - Fuzzy file search across common directories
  - `find_directory_broadly` - Directory discovery with recursive search (up to 4 levels deep)
  - `create_and_edit_file` - Create new files or edit existing ones with string replacement
  - `delete_file` - Delete files or entire directories (requires approval)
  - `rename_file` - Rename/move files (requires approval)
  - `change_working_directory` - Switch between projects/folders (requires approval)

### **Code Execution & Validation (4 Tools)**
- `run_code` - Execute shell commands and scripts locally with timeout protection (requires approval)
- `check_syntax` - Syntax validation for Python, Java, C/C++, Rust, JavaScript, TypeScript, Go, SQL
- `run_tests` - Auto-detect and run test suites (pytest, cargo test, npm test, go test, etc.)
- `lint_code` - Static analysis with pylint, eslint, cppcheck, clippy, go vet, etc.

### **Multimedia Recognition (3 Tools)**
- **Image Analysis:** `recognize_image` - GPT-4o Vision for image understanding
- **Video Analysis:** `recognize_video` - Frame extraction + GPT-4o Vision for video content
- **Audio Analysis:** `recognize_audio` - GPT-4o Audio for speech-to-text, music identification, and ambient sound recognition
  - Supports: WAV, MP3, OGG, FLAC, WebM, M4A, MP4, AAC, WMA, Opus
  - Automatic format conversion for unsupported formats using pydub

### **Document Creation (4 Tools)**
- `create_pdf` - Generate PDF documents with custom layout using ReportLab
- `create_docx` - Create Word documents with tables and formatting
- `create_excel` - Generate Excel spreadsheets with data and borders
- `create_pptx` - Create PowerPoint presentations with multiple slide layouts

### **Gmail Integration (1 Tool)**
- `open_gmail_and_compose` - Open Gmail compose window or create drafts with attachments
  - **IMAP Draft Creation:** Automatically creates drafts with file attachments
  - **Chrome Profile Detection:** Auto-discovers the correct Chrome profile based on your Gmail address
  - **Fallback Mechanism:** Opens compose window if IMAP fails
  - **HTML Email Support:** Sends both plain-text and HTML versions

### **GitHub Integration via MCP (4 Tools)**
- `github_create_branch` - Create new branches (requires approval)
- `github_commit_file` - Commit content to a branch (requires approval)
- `github_commit_local_file` - Commit local files to GitHub (requires approval)
- `github_create_pr` - Create pull requests with title/body (requires approval)
- **Workflow:** Create branch → Commit files → Create PR (3-step process)

### **Browser Automation via MCP (1 Tool)**
- `playwright_navigate` - Navigate websites using Playwright (requires approval)
- Screenshot capture support

### **Chat Session Management**
- **Persistent Conversations:** Save, load, and delete chat sessions
- **Auto-Titling:** Sessions can have custom titles or auto-generated ones
- **History Management:** Full conversation history stored in SQLite database
- **Tool Logging:** All tool executions logged with inputs/outputs to `ToolLog` model

### **Automated Evaluation Framework**
- **Benchmark Dataset:** 24+ diverse tasks covering debugging, refactoring, and multi-step reasoning
- **Automated Runner:** Systematic evaluation with rate-limiting support
- **Quantitative Metrics:** Success rate calculation and category-specific breakdown

---

## 📁 Project Structure

```
ai_agent/
├── agents.py                      # Core agent logic (2,400 lines)
│   ├── AgentControlState          # Stop/enable/disable tools with thread-safe locks
│   ├── ToolDefinition             # Tool schema with approval requirements
│   ├── Agent class                # Main agent with dual-mode operation
│   │   ├── chat_once()            # Single chat interaction with dry-run/per-tool modes
│   │   ├── execute_dry_run()      # Execute approved plan
│   │   ├── _process_response_for_api()  # Response processing logic
│   │   ├── _generate_plan_summary()     # LLM-generated plan summaries
│   │   └── _execute_tool_by_name()      # Tool execution with logging
│   ├── 25+ Tool Definitions       # All tool schemas and functions
│   └── is_prompt_injection()      # Security detection
│
├── chat/                          # Django app
│   ├── models.py                  # Database models
│   │   ├── ToolLog                # Tool execution logging
│   │   └── ChatSession            # Persistent chat history
│   ├── views.py                   # API endpoints
│   │   ├── chat_api               # Main chat endpoint with approval handling
│   │   ├── agent_control_api      # Stop/enable/disable controls
│   │   ├── chat_sessions_api      # Save/load sessions (GET/POST)
│   │   └── chat_session_detail_api # Individual session operations (GET/DELETE)
│   ├── urls.py                    # URL routing
│   ├── templates/chat/index.html  # Chat UI
│   ├── management/commands/       # Custom Django commands
│   │   ├── export_logs_csv.py     # Export tool logs to CSV
│   │   └── showlogs.py            # Display tool logs in console
│   └── migrations/                # Database migrations
│
├── evals/                         # Evaluation Framework
│   ├── tasks.json                 # 24+ benchmark tasks
│   ├── runner.py                  # Automated evaluation runner
│   ├── metrics.py                 # Success rate analysis
│   └── baseline_results.json      # Evaluation results
│
├── mcp_github_server.py           # MCP server for GitHub operations
├── mcp_playwright_server.py       # MCP server for browser automation
├── utils.py                       # S3 module loading utilities
├── settings.py                    # Django config (uses .env)
├── requirements.txt               # Dependencies (22 packages)
├── db.sqlite3                     # SQLite database
└── manage.py                      # Django management script
```

---

## 🛠️ Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd ai_agent
```

### 2. Install Dependencies

Requires Python 3.8+. Install all required packages:

```bash
pip install -r requirements.txt
```

**Dependencies include:**
- Django - Web framework
- openai - GPT-4o integration
- opencv-python - Video frame extraction
- pydub - Audio format conversion
- reportlab, python-docx, openpyxl, python-pptx - Document creation
- mcp>=1.2.0 - Model Context Protocol for GitHub/Playwright
- playwright - Browser automation
- requests, boto3, django-storages - External integrations

### 3. Environment Variables

Create a `.env` file in the project root with the following configuration:

```env
# Required: OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Gmail Integration (Optional)
GMAIL_SENDER_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# Chrome Profile (Optional - auto-detected if not set)
CHROME_PROFILE_DIRECTORY=Profile 23

# GitHub MCP (Optional - for GitHub operations)
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_pat
GITHUB_REPO_OWNER=your_username
GITHUB_REPO_NAME=your_repo

# AWS S3 (Optional - for S3 module loading)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_STORAGE_BUCKET_NAME=your_bucket_name
```

### 4. Database Setup

Run migrations to create the database schema:

```bash
python manage.py migrate
```

This creates the SQLite database with:
- `ToolLog` model - Logs all tool executions with inputs/outputs
- `ChatSession` model - Stores persistent chat conversations

### 5. Run the Development Server

```bash
python manage.py runserver
```

Visit **http://localhost:8000/** to access the chat UI.

---

## 📧 Gmail & Chrome Profile Setup

The agent includes a specialized `open_gmail_and_compose` tool that can create drafts with attachments and open them in a specific Chrome profile.

### Gmail Tool Configuration

**Step 1: Enable IMAP**
- Go to Gmail Settings → Forwarding and POP/IMAP
- Enable **IMAP Access**

**Step 2: Generate App Password**
- Go to [Google Account Security](https://myaccount.google.com/security)
- Enable 2-Step Verification if not already enabled
- Click **App Passwords**
- Generate a new 16-character app password
- Copy this password (not your regular Gmail password)

**Step 3: Update .env**
```env
GMAIL_SENDER_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop  # 16-char app password
```

### Chrome Profile Auto-Discovery

The agent automatically finds the correct Chrome profile:

**How it works:**
1. Scans Chrome's `User Data` directory
2. Reads `Preferences` file from each profile
3. Matches your `GMAIL_SENDER_ADDRESS` to find the correct profile
4. Opens Gmail in that profile automatically

**Manual Profile Override (Optional):**

If auto-discovery doesn't work, you can manually specify the profile:

1. Visit `chrome://version/` in Chrome
2. Look at the **Profile Path** field
3. Note the last part (e.g., `Default`, `Profile 1`, `Profile 23`)
4. Add to `.env`:
   ```env
   CHROME_PROFILE_DIRECTORY=Profile 23
   ```

**Supported Platforms:**
- Windows: `%LocalAppData%\Google\Chrome\User Data`
- macOS: `~/Library/Application Support/Google/Chrome`
- Linux: `~/.config/google-chrome`

---

## 🧪 Evaluation & Benchmarking

The project includes a robust evaluation pipeline for research purposes.

### Run Automated Evaluation

Run the agent against the benchmark dataset:

```bash
# Full evaluation with all features
python evals/runner.py full_results.json

# Baseline evaluation (requires disabling features in agents.py first)
python evals/runner.py baseline_results.json
```

### Generate Metrics

Analyze results and calculate success rates:

```bash
python evals/metrics.py full_results.json
```

**Output includes:**
- Overall success rate
- Category-specific breakdown (debugging, refactoring, multi-step)
- Individual task results
- Average execution time

---

## 🔄 How the Agent Works

### Dual-Mode Operation Flow

**Mode 1: Dry-Run (Default for New Tasks)**

```
User Request → Agent Plans Actions → Generates Summary → User Reviews Plan
                                                                ↓
                                                          Approve/Deny
                                                                ↓
                                                     [Execute All Tools]
```

1. User sends a message
2. Agent analyzes and creates a complete action plan
3. LLM generates a plain-English summary of what will happen
4. User sees the plan and can approve or deny
5. If approved, all tools execute sequentially
6. Agent switches to per-tool mode for any follow-up actions

**Mode 2: Per-Tool Approval (After Dry-Run Approval)**

```
Tool Call → Check requires_approval?
              ↓                    ↓
         [Yes: Pending]      [No: Execute]
              ↓                    ↓
        User Reviews         Continue Flow
              ↓
       Approve/Deny
```

1. High-risk tools (delete_file, run_code, etc.) require individual approval
2. Low-risk tools (read_file, list_files) execute automatically
3. User can deny specific actions without stopping the entire workflow

### Tool Approval Tiers

**Requires Approval (High-Risk):**
- `delete_file` - Irreversible file/directory deletion
- `rename_file` - Can cause data loss if used incorrectly
- `run_code` - Arbitrary shell command execution
- `create_and_edit_file` - File modification
- `change_working_directory` - Changes agent context
- GitHub operations - External service modifications
- `playwright_navigate` - Browser automation

**Auto-Execute (Low-Risk):**
- `read_file`, `list_files` - Read-only operations
- `search_file`, `find_file_broadly` - File discovery
- `recognize_image`, `recognize_video`, `recognize_audio` - Analysis
- `open_gmail_and_compose` - Opens browser window (user sends email)

### Agent Control System

**Stop Execution:**
```javascript
POST /api/agent-control/
{
  "action": "stop"
}
```
- Immediately halts all ongoing operations
- Sets `control.stopped = True`
- Checked before every tool execution
- Thread-safe with lock protection

**Disable/Enable Tools:**
```javascript
POST /api/agent-control/
{
  "action": "disable_tools"  // or "enable_tools"
}
```
- Global kill switch for all tool execution
- Tools return "🔒 Tool execution disabled" message
- Can be re-enabled without restarting the agent

### Broad File Search

When a file isn't found in the current directory:

1. **Direct Check:** Absolute path or relative to current directory
2. **Well-Known Folders:** Desktop, Documents, Downloads, Pictures, Videos, OneDrive
3. **Recursive Search:** Up to 4 levels deep in common directories
4. **Partial Matching:** Fuzzy filename matching (case-insensitive)
5. **Auto-Resolution:** Returns absolute path for the requested operation

**Example:**
```python
# User says: "Read the file meeting_notes"
# Agent searches:
# 1. ./meeting_notes
# 2. ~/Desktop/meeting_notes*
# 3. ~/Documents/meeting_notes*
# 4. ~/Downloads/meeting_notes*
# 5. Recursive in above folders
# → Finds: C:/Users/Frank/Documents/Work/meeting_notes.txt
```

---

## 💻 Usage Examples

### Web UI

Visit http://localhost:8000/ and interact through the chat interface:

```
You: Find the image named 'receipt' on my desktop and tell me what it says

[Agent generates plan]
Plan:
1. Find file: receipt
2. Analyze image: C:/Users/Frank/Desktop/receipt.jpg

[You approve]

Agent: I found your receipt. It shows a purchase from Starbucks for $12.45...
```

### API Usage

**Send a message:**
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a Python script that calculates fibonacci numbers",
    "history": []
  }'
```

**Response (Dry-Run):**
```json
{
  "status": "dry_run",
  "dry_run_plan": [
    {
      "id": "call_abc123",
      "name": "create_and_edit_file",
      "arguments": {"path": "fibonacci.py", "old_str": "", "new_str": "def fib(n):..."},
      "summary": "Edit/create file: fibonacci.py"
    }
  ],
  "response": "I'll create a Python script that calculates Fibonacci numbers...",
  "history": [...]
}
```

**Approve the plan:**
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "status": "dry_run_approved",
    "dry_run_plan": [...],
    "history": [...]
  }'
```

### Save Chat Session

```bash
curl -X POST http://localhost:8000/api/chat-sessions/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Project Work",
    "history": [...]
  }'
```

### Load Chat Session

```bash
curl http://localhost:8000/api/chat-sessions/1/
```

### View Tool Logs

```bash
# Console output
python manage.py showlogs

# Export to CSV
python manage.py export_logs_csv tool_logs.csv
```

---

## 🔒 Security

### ⚠️ WARNING: High Privilege Access

**This agent has extensive system access:**
- File operations accept **absolute paths** anywhere the process has permission
- Shell command execution via `run_code` tool
- Email draft creation and browser control
- GitHub repository modifications

### Built-In Safety Mechanisms

**1. Dry-Run Mode (Default)**
- All actions are previewed before execution
- User must explicitly approve the complete plan
- No surprises or unexpected operations

**2. Tool Approval Tiers**
- High-risk tools require individual approval even after dry-run
- Destructive operations (delete, run_code) always require approval
- Read-only operations execute automatically

**3. Agent Control System**
- **Stop Button:** Immediately halt execution mid-task
- **Tool Kill Switch:** Globally disable all tool execution
- Thread-safe state management

**4. Prompt Injection Detection**
- Built-in heuristics detect common injection patterns:
  - "ignore previous instructions"
  - "disregard earlier commands"
  - "bypass restrictions"
  - "you are now admin"
  - Privilege escalation attempts
- Blocked messages return security warning

**5. Tool Execution Logging**
- All tool calls logged to database with inputs/outputs
- Audit trail for security review
- Export logs to CSV for analysis

**6. Output Truncation**
- Command output limited to 10,000 characters
- File reads limited to 10,000 characters by default
- Prevents rate limit abuse and token overflow

### Security Best Practices

**DO:**
- Run the server as a non-privileged user
- Review dry-run plans carefully before approving
- Use `.env` file for sensitive credentials (not version controlled)
- Monitor tool logs regularly
- Keep `OPENAI_API_KEY` and `GMAIL_APP_PASSWORD` secure

**DON'T:**
- Run as Administrator/Root in production
- Approve plans you don't understand
- Commit `.env` file to version control
- Share your OpenAI API key
- Disable approval requirements without understanding the risk

### OS-Level Restrictions

File operations are constrained by:
- User permissions of the process running the Django server
- OS-level file system permissions
- Network firewall rules (for external integrations)

### Data Privacy

**What stays local:**
- File contents (unless explicitly sent to OpenAI for analysis)
- Tool execution results
- Chat history in SQLite database
- Environment variables

**What is sent to OpenAI:**
- User messages
- Agent responses
- Tool names and arguments (in context)
- Tool results (to continue conversation)

**Never sent to OpenAI:**
- `.env` file contents
- Credentials or API keys
- Files not explicitly requested for analysis

---

## 🎯 What This Agent Is Currently Capable Of

### **1. Local OS-Level File System Access**
- ✅ Reads files using absolute or relative paths
- ✅ **Broad file discovery** across Desktop, Documents, Pictures, Videos, OneDrive
- ✅ Partial name matching and fuzzy search
- ✅ Recursive search (up to 4 levels deep)
- ✅ Directory listing with file/folder differentiation
- ✅ Binary file detection and appropriate tool recommendation
- 💡 Mimics human-like OS navigation, not API-only access

### **2. File Creation & Modification**
- ✅ Create new files at arbitrary paths with directory auto-creation
- ✅ Edit existing files using string replacement (old_str → new_str)
- ✅ Rename/move files across directories
- ✅ Delete files or entire directories (with approval)
- ✅ Change working directory to switch between projects
- ⚠️ Extremely powerful, but high risk without strict controls

### **3. Code Execution & Validation**
- ✅ Execute shell commands locally (30s timeout)
- ✅ Run scripts (Python, Node, Java, Rust, Go, etc.)
- ✅ Syntax checking for 8+ languages
- ✅ Auto-detect and run test suites (pytest, cargo test, npm test, etc.)
- ✅ Static analysis/linting (pylint, eslint, clippy, etc.)
- ✅ Output truncation (10k chars) to prevent rate limit abuse
- 💡 Comparable to a junior DevOps engineer or software developer

### **4. Multimedia Recognition (GPT-4o)**
- ✅ **Image Analysis:** Object detection, OCR, scene understanding
- ✅ **Video Analysis:** Frame extraction + GPT-4o Vision for video content
- ✅ **Audio Analysis:** Speech-to-text, music identification, ambient sound recognition
  - Supports 10+ audio formats (WAV, MP3, OGG, FLAC, WebM, M4A, etc.)
  - Automatic format conversion using pydub
- 💡 Full multimedia understanding pipeline

### **5. Document Creation**
- ✅ **PDF Generation:** Custom layouts with ReportLab
- ✅ **Word Documents:** Tables, headings, paragraphs with python-docx
- ✅ **Excel Spreadsheets:** Data tables with formatting and borders
- ✅ **PowerPoint Presentations:** Multiple slide layouts with content
- 💡 Programmatic document creation for reports and presentations

### **6. Gmail Integration (Local Account)**
- ✅ Open Gmail compose window in correct Chrome profile
- ✅ Create Gmail drafts via IMAP with attachments
- ✅ Auto-discover Chrome profile based on email address
- ✅ HTML + plain-text email bodies
- ✅ Fallback mechanisms if IMAP fails
- 💡 Email created in user's own Gmail account, not via third-party servers

### **7. GitHub Integration (via MCP)**
- ✅ Create branches from main or any base branch
- ✅ Commit files with custom messages
- ✅ Commit local files to repository
- ✅ Create pull requests with title/body
- ✅ 3-step workflow: Branch → Commit → PR
- 💡 Full GitHub workflow automation without using git CLI

### **8. Browser Automation (via MCP)**
- ✅ Navigate to URLs using Playwright
- ✅ Capture screenshots
- ✅ Chrome profile selection
- 💡 Foundation for web scraping and testing

### **9. Tool-Oriented Agent Architecture**
- ✅ **Dual-Mode Operation:** Dry-run + per-tool approval
- ✅ **Explicit Tool Definitions:** 25+ tools with schemas
- ✅ **Tool Execution Logging:** Database logging with inputs/outputs
- ✅ **Approval Tiers:** High-risk vs. low-risk tool separation
- ✅ **Agent Control System:** Stop, enable/disable tools with thread-safe locks
- ✅ **Automatic Retries:** LLM-driven error correction
- 💡 Production-ready agentic architecture

### **10. Human-in-the-Loop Controls**
- ✅ **Dry-Run Mode:** Preview complete action plan before execution
- ✅ **Per-Tool Approval:** Approve/deny individual high-risk operations
- ✅ **Stop Button:** Immediately halt execution mid-task
- ✅ **Tool Kill Switch:** Globally disable tool execution
- ✅ **LLM-Generated Summaries:** Plain-English plan descriptions
- 💡 User maintains full control over agent actions

### **11. Chat Session Management**
- ✅ Save conversations with custom titles
- ✅ Load previous sessions to continue work
- ✅ Delete old sessions
- ✅ Persistent history in SQLite database
- 💡 Long-term memory and context preservation

### **12. Security Features**
- ✅ **Prompt Injection Detection:** Blocks common attack patterns
- ✅ **Tool Execution Limits:** Output truncation, timeouts
- ✅ **Audit Logging:** Full tool execution history
- ✅ **Environment Variable Management:** Secure credential storage
- ✅ **OS-Level Permissions:** Constrained by user privileges
- 💡 Multiple layers of defense

---

## 🚀 Why This Agent Is More Capable Than Common Agents

**Compared to typical SaaS or framework-based agents:**

| Feature | This Agent | Typical Agents |
|---------|-----------|----------------|
| **Execution Location** | Local machine | Cloud servers |
| **File Access** | Real OS files with absolute paths | Abstract documents/sandboxed |
| **Code Execution** | Real shell commands | Simulated or restricted |
| **Email Integration** | Native Gmail via IMAP | Third-party email services |
| **GitHub Operations** | Direct API integration via MCP | Limited or no integration |
| **Multimedia** | Image, video, audio analysis | Text-only or basic OCR |
| **Privacy** | Data stays local | Data sent to cloud |
| **Control** | Dry-run + per-tool approval | Limited user control |
| **Tool Count** | 25+ specialized tools | 5-10 generic tools |
| **Persistence** | SQLite database logging | Ephemeral or limited history |

**Best categorized as:** Local AI Operator / Copilot, not a chatbot

**Key Differentiators:**
1. **Direct OS Integration** - Works with your actual files, not copies
2. **Real Command Execution** - Runs actual shell commands, not simulations
3. **Native Gmail Access** - Creates drafts in your account, not via third-party
4. **Comprehensive Multimedia** - Full image/video/audio understanding
5. **GitHub Workflow Automation** - Complete branch → commit → PR workflow
6. **Production-Ready Safety** - Dry-run mode + approval system + stop controls

---

## ✅ Current Product Readiness Status

### **Implemented Safety Features**

✅ **Dry-Run Mode** - Default behavior for new tasks
✅ **Kill Switch** - Stop button + tool disable functionality
✅ **Human-in-the-Loop** - Approval system for high-risk operations
✅ **Prompt Injection Detection** - Basic heuristics implemented
✅ **Tool Execution Logging** - Full audit trail in database
✅ **Output Limits** - Truncation to prevent abuse
✅ **Clear Data Flow** - Documented what stays local vs. sent to OpenAI

### **Path to Production Deployment**

#### **For Enterprise/Commercial Use, Consider:**

**1. Enhanced Security Controls**
- [ ] Immutable system instructions (prevent prompt override)
- [ ] Configurable tool access policies per user/role
- [ ] Rate limiting per user/session
- [ ] Allowlist for `run_code` commands (instead of arbitrary execution)
- [ ] File access scoping (restrict to specific directories)
- [ ] Advanced prompt injection detection (ML-based)

**2. Operational Requirements**
- [ ] Docker containerization with resource limits
- [ ] Horizontal scaling support
- [ ] Load balancing for multiple users
- [ ] Redis for session management
- [ ] PostgreSQL instead of SQLite
- [ ] API authentication (JWT, OAuth)
- [ ] HTTPS enforcement

**3. Compliance & Privacy**
- [ ] GDPR compliance measures
- [ ] Data retention policies
- [ ] User consent flows for each tool category
- [ ] Anonymized telemetry (optional)
- [ ] Terms of Service acceptance
- [ ] Privacy policy enforcement

**4. User Experience**
- [ ] Onboarding tutorial
- [ ] Tool permission settings UI
- [ ] Audit log viewer in UI
- [ ] Export chat history
- [ ] Multi-language support
- [ ] Mobile-responsive design

**5. Multi-Model Support**
- [ ] Anthropic Claude integration
- [ ] Google Gemini support
- [ ] Model selection per task type
- [ ] Cost optimization routing
- [ ] Fallback chains for reliability

### **Recommended Deployment Tiers**

**Tier 1: Developer/Personal Use (Current)**
- Full tool access with manual approval
- Local execution only
- No rate limits
- SQLite database
- Self-hosted

**Tier 2: Team/Small Business**
- Configurable tool policies
- Shared sessions
- PostgreSQL database
- Docker deployment
- Admin dashboard

**Tier 3: Enterprise**
- SSO integration
- Role-based access control
- Audit compliance features
- Multi-tenancy support
- SLA guarantees
- Dedicated support

---

## 🎨 Competitive Advantages & Differentiators

### **1. Local-First Architecture**
- No vendor lock-in
- Data stays on user's machine
- No cloud storage costs
- Works offline (except LLM calls)

### **2. Real OS Integration**
- Not a simulation or sandbox
- Works with actual files and processes
- Native application integration (Gmail, Chrome, GitHub)

### **3. Dual-Mode Safety**
- Dry-run mode prevents surprises
- Per-tool approval for granular control
- Stop button for immediate halt
- Tool kill switch for emergency shutdown

### **4. Comprehensive Tool Suite**
- 25+ specialized tools covering:
  - File operations
  - Code execution & validation
  - Multimedia recognition
  - Document creation
  - Email & browser automation
  - GitHub workflow automation

### **5. Production-Ready Features**
- Database logging for audit trails
- Session management for persistence
- Thread-safe agent controls
- Prompt injection detection
- Output truncation for safety

### **Potential Enterprise Policy Configuration**

Example YAML config for enterprise deployment:

```yaml
# policy.yaml
filesystem:
  enabled: true
  allowed_directories:
    - /home/user/projects
    - /home/user/documents
  blocked_directories:
    - /home/user/.ssh
    - /etc
  read_only: false

code_execution:
  enabled: true
  allowed_commands:
    - python
    - pytest
    - npm
  blocked_commands:
    - rm -rf
    - sudo
  timeout_seconds: 30

email:
  enabled: true
  rate_limit_per_day: 50
  allowed_domains:
    - company.com

github:
  enabled: true
  allowed_repos:
    - company/frontend
    - company/backend

multimedia:
  enabled: true
  image_analysis: true
  video_analysis: false  # High cost
  audio_analysis: true

dry_run:
  required: true
  can_disable: false

logging:
  enabled: true
  retention_days: 90
  export_enabled: true
```

---

## 🔗 Future: LangChain & LangGraph Integration

**Current Implementation:** Custom OpenAI integration with manual tool orchestration

**Why Migrate to LangChain/LangGraph?**

### **Benefits of LangChain**
- ✅ Standardized tool schemas across LLM providers
- ✅ Easy model swapping (OpenAI → Anthropic → Gemini)
- ✅ Built-in callback hooks for logging and cost tracking
- ✅ Community-maintained integrations
- ⚠️ Use as orchestration layer, not execution engine

### **Benefits of LangGraph**
- ✅ Explicit state machines for deterministic flow
- ✅ Human approval nodes as first-class citizens
- ✅ Retry and failure branches
- ✅ Hard execution boundaries
- ✅ Prevents runaway autonomy

### **Recommended Migration Path**

**Phase 1: Adapter Layer**
```python
from langchain.tools import tool

@tool
def read_file_langchain(path: str) -> str:
    """Thin adapter to existing read_file_tool"""
    return read_file_tool({"path": path})
```

**Phase 2: Model Abstraction**
```python
from langchain.chat_models import ChatOpenAI, ChatAnthropic

# Easy model switching
llm = ChatOpenAI(model="gpt-4o")
# or
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
```

**Phase 3: LangGraph State Machine**
```python
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    user_input: str
    plan: List[dict]
    approved: bool
    tool_queue: List[dict]
    audit_log: List[dict]
    errors: List[str]

workflow = StateGraph(AgentState)
workflow.add_node("planner", planning_node)
workflow.add_node("approval", human_approval_node)
workflow.add_node("executor", tool_execution_node)
workflow.add_node("logger", audit_logger_node)

workflow.add_edge("planner", "approval")
workflow.add_edge("approval", "executor")
workflow.add_edge("executor", "logger")
```

**Phase 4: Observability**
```python
from langchain.callbacks import BaseCallbackHandler

class ToolLogCallback(BaseCallbackHandler):
    def on_tool_start(self, tool, input):
        ToolLog.objects.create(tool_name=tool, input_args=input)
```

### **What LangChain/LangGraph Should NOT Control**
- ❌ Direct file system access
- ❌ Shell command execution
- ❌ Gmail credentials
- ❌ OS-level permissions
- ❌ Docker sandbox configuration

These remain outside the framework for security isolation.

### **Migration Principles**
1. **Incremental:** No big-bang rewrite
2. **Backward Compatible:** Existing tools continue working
3. **Safety First:** All controls must remain functional
4. **Observable:** Maintain or improve logging
5. **Flexible:** Easy to swap or remove LangChain later

---

## 🎯 Product Positioning

**"A local-first AI operator that works inside your computer, not on someone else's server."**

### **Target Users**

**Current State (Developer/Power User):**
- Software developers
- DevOps engineers
- Data scientists
- Power users comfortable with code

**Future State (with enterprise features):**
- Development teams
- Small businesses
- Enterprise IT departments
- Non-technical users (with heavy restrictions)

### **Value Proposition**

**For Developers:**
- Automate repetitive tasks (file operations, testing, linting)
- Accelerate debugging with AI-powered code analysis
- Manage GitHub workflows without switching contexts
- Process multimedia files programmatically

**For Teams:**
- Shared knowledge base via chat sessions
- Audit trail for compliance
- Standardized workflows
- Code generation with validation

**For Enterprises:**
- Data stays on-premises
- Customizable policies per user/role
- Full audit logging
- Integration with existing tools (Gmail, GitHub)

---

## 📊 Technical Specifications

**Backend:**
- Python 3.8+
- Django 4.x
- SQLite (dev) / PostgreSQL (prod)
- OpenAI API (gpt-4o, gpt-4o-audio-preview)

**Frontend:**
- Vanilla JavaScript
- Bootstrap CSS
- WebSockets (future: real-time updates)

**Integrations:**
- Model Context Protocol (MCP) for GitHub & Playwright
- IMAP for Gmail draft creation
- Chrome DevTools Protocol for profile detection

**Performance:**
- Average response time: 2-5 seconds (depends on LLM)
- Tool execution: 0.1-30 seconds (depends on operation)
- Database size: ~10KB per chat session
- Log storage: ~1KB per tool call

**Scalability:**
- Current: Single user, single server
- Future: Multi-tenant with Redis/PostgreSQL

---

## 🔮 Roadmap

### **v1.1 (Current)**
- ✅ 25+ tools
- ✅ Dry-run mode
- ✅ Agent controls
- ✅ Session management
- ✅ Audio recognition

### **v1.2 (Planned)**
- [ ] WebSocket support for real-time updates
- [ ] Tool execution progress indicators
- [ ] Multi-model support (Anthropic, Gemini)
- [ ] Enhanced prompt injection detection (ML-based)
- [ ] Docker containerization

### **v2.0 (Future)**
- [ ] LangGraph state machine migration
- [ ] Multi-user support with authentication
- [ ] Role-based access control (RBAC)
- [ ] Policy configuration UI
- [ ] Plugin system for custom tools
- [ ] Mobile app

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Commit your changes:** `git commit -m 'Add amazing feature'`
4. **Push to the branch:** `git push origin feature/amazing-feature`
5. **Open a Pull Request**

**Areas for Contribution:**
- New tool implementations
- UI/UX improvements
- Security enhancements
- Documentation
- Test coverage
- Performance optimizations

---

## 📝 License

MIT License

Copyright (c) 2025 Frank

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

## 🙏 Acknowledgments

**Technologies:**
- [OpenAI](https://openai.com/) - GPT-4o model and API
- [Django](https://www.djangoproject.com/) - Web framework
- [Model Context Protocol](https://modelcontextprotocol.io/) - Tool integration standard
- [Playwright](https://playwright.dev/) - Browser automation
- [ReportLab](https://www.reportlab.com/) - PDF generation

**Inspiration:**
- LangChain & LangGraph - Agent architecture patterns
- AutoGPT - Autonomous agent concepts
- Cursor / GitHub Copilot - AI-powered development tools

**Community:**
- Stack Overflow - Problem-solving
- GitHub - Code hosting and collaboration
- OpenAI Forum - API best practices

---

## 📞 Support & Contact

**Issues:** [GitHub Issues](https://github.com/Frankythecoder/ai_agent/issues)

**Documentation:** This README + inline code comments

**Email:** diviyanfrankjeyasingh@gmail.com (for security issues only)

---

**⭐ If you find this project useful, please consider starring it on GitHub!**
