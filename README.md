# AI Agent Django Project

## Overview

This project is a Django-based web application that integrates with OpenAI's generative AI models to provide agentic code generation, file management, and chat capabilities. It features a modern chat UI, advanced agentic tools for sandboxed execution, and a comprehensive evaluation framework for research and benchmarking.

---

## Features

- **OpenAI Integration:**
  Utilizes the `gpt-4o` model for high-performance reasoning and code generation.

- **Agentic File & System Tools:**
  - **CRUD Operations:** Read, list, create, edit, delete, and rename files of any type.
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
# Optional S3 support
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_STORAGE_BUCKET_NAME=your_bucket
```

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

## Usage

- **Chat with OpenAI:** Use the web UI or POST to `/api/chat/`.
- **System Tasks:** Ask the agent to "Write a script, run it, and tell me if it passes".
- **Self-Correction:** The agent will automatically attempt to fix errors if a tool execution fails.

---

## Security

- File operations are restricted by OS-level permissions.
- API keys are managed via environment variables.
- Sandboxed execution is performed in the local shell; use with caution in sensitive environments.

---

## License

MIT License

---

## Acknowledgments

- [OpenAI](https://openai.com/)
- [Django Framework](https://www.djangoproject.com/)
