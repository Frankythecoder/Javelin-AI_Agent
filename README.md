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

## License

MIT License

---

## Acknowledgments

- [OpenAI](https://openai.com/)
- [Django Framework](https://www.djangoproject.com/)
