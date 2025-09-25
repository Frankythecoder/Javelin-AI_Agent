# AI Agent Django Project

## Overview

This project is a Django-based web application that integrates with Google's Gemini generative AI model to provide agentic code generation, file management, and chat capabilities across all directories and folders in the local machine. It features a modern chat UI, file tools, and supports code generation and manipulation for any programming language.

---

## Features

- **Gemini AI Integration:**  
  Generate code in any programming language using Google's Gemini model.

- **Agentic File Tools:**  
  - Read, list, create, edit, delete, and rename files of any type.
  - Change file extensions/types (e.g., `.py` to `.cpp` or any other programming language) programmatically.

- **Web Chat Interface:**  
  - Modern, responsive chat UI for interacting with the Gemini agent.
  - API endpoint for programmatic chat.

- **Django Backend:**  
  - Modular Django app structure.
  - S3 integration for file storage (optional, via environment variables).

---

## Project Structure

```
ai_agent/
├── agents.py                # Core agent logic, Gemini integration, file tools
├── asgi.py                  # ASGI config for Django
├── chat/
│   ├── admin.py
│   ├── apps.py
│   ├── migrations/
│   ├── models.py
│   ├── templates/
│   │   └── chat/
│   │       └── index.html   # Modern chat UI
│   ├── tests.py
│   ├── urls.py
│   └── views.py             # Chat API and page views
├── db.sqlite3               # SQLite database (default)
├── manage.py                # Django management script
├── program.cpp              # Example generated file
├── prime_num.py             # Example file
├── settings.py              # Django settings (uses .env for secrets)
├── urls.py                  # Project URL routing
├── wsgi.py                  # WSGI config for Django
```

---

## Setup

### 1. Clone the Repository

```sh
git clone <your-repo-url>
cd ai_agent
```

### 2. Install Dependencies

This project needs Python v3.8 or higher installed in your local machine.

- Django 5.x
- google-generativeai
- python-decouple
- python-dotenv
- boto3 (for S3 support)

```sh
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root with the following (see `settings.py` for all options):

```
API_KEY=your_gemini_api_key
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_STORAGE_BUCKET_NAME=your_bucket
AWS_S3_REGION_NAME=us-east-1
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

## Usage

- **Chat with Gemini:**  
  Use the web UI or POST to `/api/chat/` with a JSON body:  
  `{ "message": "Write a C++ program to print prime numbers from 1 to 10." }`

- **File Tools:**  
  The agent can read, create, edit, delete, and rename files via chat or API.

- **Change File Types:**  
  Ask the agent to rename files (e.g., "Rename program.py to program.cpp").

---

## Customization

- **Add More Tools:**  
  Extend `agents.py` with new tool functions and add them to the toolset.
- **Change Model:**  
  Update the Gemini model version in `agents.py` as needed.

---

## Security

- Keep your API keys and secrets in the `.env` file (never commit them).
- For production, set `DEBUG = False` and configure allowed hosts.

---

## License

MIT License (or your chosen license)

---

## Acknowledgments

- [Google Generative AI](https://ai.google.dev/)
- [Django](https://www.djangoproject.com/)
- [OpenAI](https://openai.com/) (for inspiration)
