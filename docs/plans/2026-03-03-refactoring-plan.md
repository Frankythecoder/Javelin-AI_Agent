# Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split agents.py (4,814 lines) into an agents/ package and extract CSS/JS from index.html (1,618 lines) so no file exceeds 1000 lines. Zero logic changes.

**Architecture:** Convert `agents.py` into `agents/` package with 11 modules organized by tool category. Each module contains tool functions + their ToolDefinition objects. `__init__.py` re-exports everything for backward compatibility. For index.html, extract `<style>` (lines 14-653) to `chat/static/chat/css/chat.css` and `<script>` (lines 701-1616) to `chat/static/chat/js/chat.js`.

**Tech Stack:** Python, Django, LangChain, LangGraph, OpenAI

---

### Task 1: Create agents/ package directory and control.py

**Files:**
- Create: `agents/__init__.py` (placeholder)
- Create: `agents/control.py`

**Step 1: Create directory structure**

```bash
mkdir -p agents
```

**Step 2: Create agents/control.py**

Extract from `agents.py` lines 63-192. This file contains:
- `AgentControlState` class (lines 63-80)
- `ToolDefinition` class (lines 133-139)
- `ApprovalAwareTool` class (lines 142-144)
- `_json_type_to_python` function (lines 147-157)
- `tool_definition_to_langchain` function (lines 160-192)

File needs these imports:
```python
from typing import Dict, Any, Callable, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field
import threading
```

**Step 3: Create placeholder agents/__init__.py**

```python
# Placeholder - will be filled after all modules are created
```

**Step 4: Verify control.py imports work**

Run: `python -c "from agents.control import AgentControlState, ToolDefinition, ApprovalAwareTool, tool_definition_to_langchain"`
Expected: No errors

**Step 5: Commit**

```bash
git add agents/
git commit -m "refactor: create agents/ package with control.py"
```

---

### Task 2: Create agents/helpers.py

**Files:**
- Create: `agents/helpers.py`

**Step 1: Create agents/helpers.py**

Extract from `agents.py`:
- `find_file_broadly` function (lines 195-282)
- `find_directory_broadly` function (lines 285-369)
- `_normalize_url` function (lines 496-503)
- `is_prompt_injection` function (lines 3666-3695)

File needs these imports:
```python
import os
import re
```

Note: `find_file_broadly` calls `find_directory_broadly` and vice versa — both are in this same file so no cross-file import needed.

**Step 2: Verify helpers.py imports work**

Run: `python -c "from agents.helpers import find_file_broadly, find_directory_broadly, _normalize_url, is_prompt_injection"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/helpers.py
git commit -m "refactor: extract helpers.py (file search, URL normalize, injection detection)"
```

---

### Task 3: Create agents/file_tools.py

**Files:**
- Create: `agents/file_tools.py`

**Step 1: Create agents/file_tools.py**

Extract from `agents.py`:
- `find_file_broadly_tool` function (lines 372-381)
- `find_directory_broadly_tool` function (lines 384-393)
- `search_file_tool` function (lines 396-406)
- `read_file_tool` function (lines 409-460)
- `list_files_tool` function (lines 465-494)
- `change_working_directory_tool` function (lines 561-582)
- `create_new_file` function (lines 585-599)
- `delete_file_tool` function (lines 602-633)
- `create_and_edit_file_tool` function (lines 636-683)
- `rename_file_tool` function (lines 686-700)
- All 9 file tool DEFINITION objects:
  - `SEARCH_FILE_DEFINITION` (lines 1299-1313)
  - `READ_FILE_DEFINITION` (lines 1317-1339)
  - `LIST_FILES_DEFINITION` (lines 1342-1356)
  - `DELETE_FILE_DEFINITION` (lines 1359-1374)
  - `CREATE_AND_EDIT_FILE_DEFINITION` (lines 1378-1401)
  - `RENAME_FILE_DEFINITION` (lines 2114-2133)
  - `FIND_FILE_BROADLY_DEFINITION` (lines 2307-2321)
  - `FIND_DIRECTORY_BROADLY_DEFINITION` (lines 2324-2338)
  - `CHANGE_WORKING_DIRECTORY_DEFINITION` (lines 2341-2356)

File needs these imports:
```python
import os
import json
import shutil
from typing import Dict, Any
from agents.helpers import find_file_broadly, find_directory_broadly
from agents.control import ToolDefinition
```

**Step 2: Verify file_tools.py imports work**

Run: `python -c "from agents.file_tools import SEARCH_FILE_DEFINITION, READ_FILE_DEFINITION, LIST_FILES_DEFINITION, DELETE_FILE_DEFINITION, CREATE_AND_EDIT_FILE_DEFINITION, RENAME_FILE_DEFINITION, FIND_FILE_BROADLY_DEFINITION, FIND_DIRECTORY_BROADLY_DEFINITION, CHANGE_WORKING_DIRECTORY_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/file_tools.py
git commit -m "refactor: extract file_tools.py (9 file operation tools)"
```

---

### Task 4: Create agents/code_tools.py

**Files:**
- Create: `agents/code_tools.py`

**Step 1: Create agents/code_tools.py**

Extract from `agents.py`:
- `run_code_tool` function (lines 703-735)
- `check_syntax_tool` function (lines 738-769)
- `run_tests_tool` function (lines 772-794)
- `lint_code_tool` function (lines 885-910)
- 4 DEFINITION objects:
  - `RUN_CODE_DEFINITION` (lines 2136-2151)
  - `CHECK_SYNTAX_DEFINITION` (lines 2154-2169)
  - `RUN_TESTS_DEFINITION` (lines 2172-2187)
  - `LINT_CODE_DEFINITION` (lines 2190-2205)

File needs these imports:
```python
import os
import subprocess
from typing import Dict, Any
from agents.control import ToolDefinition
```

Note: `check_syntax_tool`, `run_tests_tool`, and `lint_code_tool` all call `run_code_tool` internally — they're all in this same file.

**Step 2: Verify code_tools.py imports work**

Run: `python -c "from agents.code_tools import RUN_CODE_DEFINITION, CHECK_SYNTAX_DEFINITION, RUN_TESTS_DEFINITION, LINT_CODE_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/code_tools.py
git commit -m "refactor: extract code_tools.py (run, syntax, tests, lint)"
```

---

### Task 5: Create agents/github_tools.py

**Files:**
- Create: `agents/github_tools.py`

**Step 1: Create agents/github_tools.py**

Extract from `agents.py`:
- `_github_mcp_call` function (lines 796-817)
- `github_create_pr_tool` function (line 820-821)
- `github_create_branch_tool` function (lines 824-825)
- `github_commit_file_tool` function (lines 828-829)
- `github_commit_local_file_tool` function (lines 832-833)
- `create_github_issue_tool` function (lines 836-882)
- 5 DEFINITION objects:
  - `GITHUB_CREATE_BRANCH_DEFINITION` (lines 1403-1416)
  - `GITHUB_COMMIT_FILE_DEFINITION` (lines 1418-1433)
  - `GITHUB_COMMIT_LOCAL_FILE_DEFINITION` (lines 1435-1450)
  - `GITHUB_MCP_DEFINITION` (lines 1452-1467)
  - `CREATE_GITHUB_ISSUE_DEFINITION` (lines 1470-1499)

File needs these imports:
```python
import os
import requests
from typing import Dict, Any
from django.conf import settings
from agents.control import ToolDefinition
```

**Step 2: Verify github_tools.py imports work**

Run: `python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); django.setup(); from agents.github_tools import GITHUB_CREATE_BRANCH_DEFINITION, GITHUB_MCP_DEFINITION, CREATE_GITHUB_ISSUE_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/github_tools.py
git commit -m "refactor: extract github_tools.py (5 GitHub MCP tools)"
```

---

### Task 6: Create agents/email_tools.py

**Files:**
- Create: `agents/email_tools.py`

**Step 1: Create agents/email_tools.py**

Extract from `agents.py`:
- `create_gmail_draft` function (lines 913-1003)
- `find_chrome_profile_for_email` function (lines 1006-1038)
- `open_url_in_chrome_profile` function (lines 1041-1072)
- `open_gmail_and_compose_tool` function (lines 1075-1134)
- `playwright_mcp_tool` function (lines 505-559)
- 2 DEFINITION objects:
  - `OPEN_GMAIL_AND_COMPOSE_DEFINITION` (lines 2208-2237)
  - `PLAYWRIGHT_MCP_DEFINITION` (lines 1502-1515)

File needs these imports:
```python
import os
import json
import time
import re
import subprocess
import platform
import webbrowser
import imaplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
from email.policy import SMTP
from urllib.parse import quote
from typing import Dict, Any, List
from django.conf import settings
from agents.control import ToolDefinition
from agents.helpers import _normalize_url
```

Note: `playwright_mcp_tool` uses `_normalize_url` from helpers and imports `_toggle_www` from `mcp_playwright_server` at runtime.

**Step 2: Verify email_tools.py imports work**

Run: `python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); django.setup(); from agents.email_tools import OPEN_GMAIL_AND_COMPOSE_DEFINITION, PLAYWRIGHT_MCP_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/email_tools.py
git commit -m "refactor: extract email_tools.py (Gmail, Playwright tools)"
```

---

### Task 7: Create agents/multimedia_tools.py

**Files:**
- Create: `agents/multimedia_tools.py`

**Step 1: Create agents/multimedia_tools.py**

Extract from `agents.py`:
- `recognize_image_tool` function (lines 1137-1172)
- `recognize_video_tool` function (lines 1175-1237)
- `recognize_audio_tool` function (lines 1240-1297)
- 3 DEFINITION objects:
  - `RECOGNIZE_IMAGE_DEFINITION` (lines 2240-2258)
  - `RECOGNIZE_VIDEO_DEFINITION` (lines 2261-2283)
  - `RECOGNIZE_AUDIO_DEFINITION` (lines 2286-2304)

File needs these imports:
```python
import os
import base64
import cv2
from typing import Dict, Any
from openai import OpenAI
from django.conf import settings
from agents.control import ToolDefinition
```

**Step 2: Verify multimedia_tools.py imports work**

Run: `python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); django.setup(); from agents.multimedia_tools import RECOGNIZE_IMAGE_DEFINITION, RECOGNIZE_VIDEO_DEFINITION, RECOGNIZE_AUDIO_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/multimedia_tools.py
git commit -m "refactor: extract multimedia_tools.py (image, video, audio recognition)"
```

---

### Task 8: Create agents/travel_tools.py

**Files:**
- Create: `agents/travel_tools.py`

**Step 1: Create agents/travel_tools.py**

Extract from `agents.py`:
- `DUFFEL_API_BASE` constant (line 84)
- `_duffel_offer_cache` dict (line 87)
- `_duffel_headers` function (lines 90-106)
- `_duffel_post` function (lines 109-112)
- `_duffel_get` function (lines 115-118)
- `_parse_iso_duration` function (lines 121-131)
- `search_flights_tool` function (lines 1520-1620)
- `SEARCH_FLIGHTS_DEFINITION` (lines 1623-1662)
- `book_travel_tool` function (lines 1665-1822)
- `BOOK_TRAVEL_DEFINITION` (lines 1825-1925)
- `get_booking_tool` function (lines 1930-1990)
- `GET_BOOKING_DEFINITION` (lines 1993-2008)
- `cancel_booking_tool` function (lines 2011-2059)
- `CANCEL_BOOKING_DEFINITION` (lines 2062-2077)
- `list_bookings_tool` function (lines 2080-2098)
- `LIST_BOOKINGS_DEFINITION` (lines 2101-2111)

File needs these imports:
```python
import os
import re
import uuid
import requests
from typing import Dict, Any
from decimal import Decimal
from agents.control import ToolDefinition
```

Note: `book_travel_tool`, `get_booking_tool`, `cancel_booking_tool`, and `list_bookings_tool` import `from chat.models import Booking` at runtime (inside the function body). Keep those runtime imports as-is.

**Step 2: Verify travel_tools.py imports work**

Run: `python -c "from agents.travel_tools import SEARCH_FLIGHTS_DEFINITION, BOOK_TRAVEL_DEFINITION, GET_BOOKING_DEFINITION, CANCEL_BOOKING_DEFINITION, LIST_BOOKINGS_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/travel_tools.py
git commit -m "refactor: extract travel_tools.py (Duffel API, 5 travel tools)"
```

---

### Task 9: Create agents/document_tools.py

**Files:**
- Create: `agents/document_tools.py`

**Step 1: Create agents/document_tools.py**

Extract from `agents.py`:
- `_parse_markdown_blocks` function (lines 2361-2447)
- `_md_inline_to_html` function (lines 2450-2456)
- `create_pdf` function (lines 2461-2618)
- `create_docx` function (lines 2621-2762)
- `create_excel` function (lines 2765-2844)
- `create_pptx` function (lines 2847-2998)
- `read_pdf_tool` function (lines 3144-3194)
- `read_docx_tool` function (lines 3197-3256)
- `read_excel_tool` function (lines 3259-3328)
- `read_pptx_tool` function (lines 3331-3381)
- `edit_pdf_tool` function (lines 3384-3402)
- `edit_docx_tool` function (lines 3405-3423)
- `edit_excel_tool` function (lines 3426-3446)
- `edit_pptx_tool` function (lines 3449-3467)
- 12 DEFINITION objects:
  - `CREATE_PDF_DEFINITION` (lines 3003-3036)
  - `CREATE_DOCX_DEFINITION` (lines 3038-3071)
  - `CREATE_EXCEL_DEFINITION` (lines 3073-3104)
  - `CREATE_PPTX_DEFINITION` (lines 3106-3139)
  - `READ_PDF_DEFINITION` (lines 3472-3490)
  - `READ_DOCX_DEFINITION` (lines 3492-3510)
  - `READ_EXCEL_DEFINITION` (lines 3512-3534)
  - `READ_PPTX_DEFINITION` (lines 3536-3554)
  - `EDIT_PDF_DEFINITION` (lines 3556-3579)
  - `EDIT_DOCX_DEFINITION` (lines 3581-3604)
  - `EDIT_EXCEL_DEFINITION` (lines 3606-3638)
  - `EDIT_PPTX_DEFINITION` (lines 3640-3663)

File needs these imports:
```python
import os
import re
from typing import Dict, Any
from agents.helpers import find_file_broadly
from agents.control import ToolDefinition

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from openpyxl import Workbook
from openpyxl.styles import Font as XlFont, PatternFill, Alignment as XlAlignment, Border, Side
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt, Emu
from pptx.dml.color import RGBColor as PptxRGBColor
from pptx.enum.text import PP_ALIGN
```

**Step 2: Verify document_tools.py imports work**

Run: `python -c "from agents.document_tools import CREATE_PDF_DEFINITION, READ_PDF_DEFINITION, EDIT_PDF_DEFINITION, CREATE_DOCX_DEFINITION"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/document_tools.py
git commit -m "refactor: extract document_tools.py (12 document create/read/edit tools)"
```

---

### Task 10: Create agents/core.py

**Files:**
- Create: `agents/core.py`

**Step 1: Create agents/core.py**

Extract from `agents.py`:
- `AgentState` TypedDict (lines 3761-3773)
- `Agent` class (lines 3776-4811) — the entire class with all methods:
  - `__init__`, `_build_graph`, `chat_once`, `execute_dry_run`, `run`, `_process_response_simple`, `_execute_tool_by_name`, `_dicts_to_messages`, `_strip_orphaned_tool_calls`, `_messages_to_dicts`, `_summarize_tool_call`, `_generate_plan_summary`, `_convert_tools_to_openai_format`, `_trim_messages`, `_summarize_messages`, `_detect_interrupted_task`, `generate_code`
- `main()` function (lines 3698-3758)

File needs these imports:
```python
import json
from typing import Dict, List, Any, Optional, TypedDict

from openai import OpenAI
from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, END

from agents.control import AgentControlState, ToolDefinition, ApprovalAwareTool, tool_definition_to_langchain
from agents.helpers import is_prompt_injection
```

Note: `main()` references all the DEFINITION objects. It should import them from `agents` package itself (i.e., `from agents.file_tools import ...`, etc.) or we can move `main()` to `__init__.py`. Best approach: keep `main()` in core.py and import definitions there.

Add at bottom of core.py imports (for `main()` function only):
```python
from agents.file_tools import (
    SEARCH_FILE_DEFINITION, READ_FILE_DEFINITION, LIST_FILES_DEFINITION,
    CREATE_AND_EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION, RENAME_FILE_DEFINITION,
    FIND_FILE_BROADLY_DEFINITION, FIND_DIRECTORY_BROADLY_DEFINITION,
    CHANGE_WORKING_DIRECTORY_DEFINITION,
)
from agents.code_tools import RUN_CODE_DEFINITION, CHECK_SYNTAX_DEFINITION, RUN_TESTS_DEFINITION, LINT_CODE_DEFINITION
from agents.github_tools import (
    GITHUB_CREATE_BRANCH_DEFINITION, GITHUB_COMMIT_FILE_DEFINITION,
    GITHUB_COMMIT_LOCAL_FILE_DEFINITION, GITHUB_MCP_DEFINITION, CREATE_GITHUB_ISSUE_DEFINITION,
)
from agents.email_tools import OPEN_GMAIL_AND_COMPOSE_DEFINITION, PLAYWRIGHT_MCP_DEFINITION
from agents.multimedia_tools import RECOGNIZE_IMAGE_DEFINITION, RECOGNIZE_VIDEO_DEFINITION, RECOGNIZE_AUDIO_DEFINITION
from agents.travel_tools import (
    SEARCH_FLIGHTS_DEFINITION, BOOK_TRAVEL_DEFINITION, GET_BOOKING_DEFINITION,
    LIST_BOOKINGS_DEFINITION, CANCEL_BOOKING_DEFINITION,
)
from agents.document_tools import (
    CREATE_PDF_DEFINITION, CREATE_DOCX_DEFINITION, CREATE_EXCEL_DEFINITION, CREATE_PPTX_DEFINITION,
    READ_PDF_DEFINITION, READ_DOCX_DEFINITION, READ_EXCEL_DEFINITION, READ_PPTX_DEFINITION,
    EDIT_PDF_DEFINITION, EDIT_DOCX_DEFINITION, EDIT_EXCEL_DEFINITION, EDIT_PPTX_DEFINITION,
)
```

**Step 2: Verify core.py imports work**

Run: `python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); django.setup(); from agents.core import Agent, AgentState, main"`
Expected: No errors

**Step 3: Commit**

```bash
git add agents/core.py
git commit -m "refactor: extract core.py (Agent class, LangGraph, main)"
```

---

### Task 11: Write agents/__init__.py and delete agents.py

**Files:**
- Modify: `agents/__init__.py`
- Delete: `agents.py`

**Step 1: Write agents/__init__.py with all re-exports**

```python
"""Javelin AI Agent package.

This package was refactored from a single agents.py file.
All public names are re-exported here for backward compatibility.
"""

from agents.control import (
    AgentControlState,
    ToolDefinition,
    ApprovalAwareTool,
    tool_definition_to_langchain,
)

from agents.helpers import (
    find_file_broadly,
    find_directory_broadly,
    _normalize_url,
    is_prompt_injection,
)

from agents.file_tools import (
    search_file_tool,
    read_file_tool,
    list_files_tool,
    delete_file_tool,
    create_and_edit_file_tool,
    create_new_file,
    rename_file_tool,
    find_file_broadly_tool,
    find_directory_broadly_tool,
    change_working_directory_tool,
    SEARCH_FILE_DEFINITION,
    READ_FILE_DEFINITION,
    LIST_FILES_DEFINITION,
    DELETE_FILE_DEFINITION,
    CREATE_AND_EDIT_FILE_DEFINITION,
    RENAME_FILE_DEFINITION,
    FIND_FILE_BROADLY_DEFINITION,
    FIND_DIRECTORY_BROADLY_DEFINITION,
    CHANGE_WORKING_DIRECTORY_DEFINITION,
)

from agents.code_tools import (
    run_code_tool,
    check_syntax_tool,
    run_tests_tool,
    lint_code_tool,
    RUN_CODE_DEFINITION,
    CHECK_SYNTAX_DEFINITION,
    RUN_TESTS_DEFINITION,
    LINT_CODE_DEFINITION,
)

from agents.github_tools import (
    github_create_branch_tool,
    github_create_pr_tool,
    github_commit_file_tool,
    github_commit_local_file_tool,
    create_github_issue_tool,
    GITHUB_CREATE_BRANCH_DEFINITION,
    GITHUB_COMMIT_FILE_DEFINITION,
    GITHUB_COMMIT_LOCAL_FILE_DEFINITION,
    GITHUB_MCP_DEFINITION,
    CREATE_GITHUB_ISSUE_DEFINITION,
)

from agents.email_tools import (
    open_gmail_and_compose_tool,
    playwright_mcp_tool,
    OPEN_GMAIL_AND_COMPOSE_DEFINITION,
    PLAYWRIGHT_MCP_DEFINITION,
)

from agents.multimedia_tools import (
    recognize_image_tool,
    recognize_video_tool,
    recognize_audio_tool,
    RECOGNIZE_IMAGE_DEFINITION,
    RECOGNIZE_VIDEO_DEFINITION,
    RECOGNIZE_AUDIO_DEFINITION,
)

from agents.travel_tools import (
    search_flights_tool,
    book_travel_tool,
    get_booking_tool,
    cancel_booking_tool,
    list_bookings_tool,
    SEARCH_FLIGHTS_DEFINITION,
    BOOK_TRAVEL_DEFINITION,
    GET_BOOKING_DEFINITION,
    CANCEL_BOOKING_DEFINITION,
    LIST_BOOKINGS_DEFINITION,
)

from agents.document_tools import (
    create_pdf,
    create_docx,
    create_excel,
    create_pptx,
    read_pdf_tool,
    read_docx_tool,
    read_excel_tool,
    read_pptx_tool,
    edit_pdf_tool,
    edit_docx_tool,
    edit_excel_tool,
    edit_pptx_tool,
    CREATE_PDF_DEFINITION,
    CREATE_DOCX_DEFINITION,
    CREATE_EXCEL_DEFINITION,
    CREATE_PPTX_DEFINITION,
    READ_PDF_DEFINITION,
    READ_DOCX_DEFINITION,
    READ_EXCEL_DEFINITION,
    READ_PPTX_DEFINITION,
    EDIT_PDF_DEFINITION,
    EDIT_DOCX_DEFINITION,
    EDIT_EXCEL_DEFINITION,
    EDIT_PPTX_DEFINITION,
)

from agents.core import Agent, AgentState, main
```

**Step 2: Delete the old agents.py**

```bash
rm agents.py
```

**Step 3: Verify all existing imports still work**

Run each of these:
```bash
python -c "from agents import Agent, SEARCH_FILE_DEFINITION, READ_FILE_DEFINITION, _normalize_url"
python -c "import agents as agents_module; print(agents_module.Agent)"
python -c "from agents import is_prompt_injection"
```
Expected: All succeed with no errors

**Step 4: Run existing tests**

```bash
python -m pytest tests/test_normalize_url.py -v
python -m pytest tests/test_mcp_navigate.py -v
```
Expected: All tests pass

**Step 5: Commit**

```bash
git add agents/__init__.py
git rm agents.py
git commit -m "refactor: complete agents/ package, delete monolithic agents.py"
```

---

### Task 12: Extract CSS from index.html

**Files:**
- Create: `chat/static/chat/css/chat.css`
- Modify: `chat/templates/chat/index.html`

**Step 1: Create static directories**

```bash
mkdir -p chat/static/chat/css
mkdir -p chat/static/chat/js
```

**Step 2: Create chat/static/chat/css/chat.css**

Extract everything between `<style>` (line 14) and `</style>` (line 653) from `chat/templates/chat/index.html`. Copy the CSS content verbatim — no changes.

**Step 3: Replace the style block in index.html**

In `chat/templates/chat/index.html`:
- Add `{% load static %}` as the very first line (before `<!DOCTYPE html>`)
- Replace lines 14-653 (the `<style>...</style>` block) with:
  ```html
  <link rel="stylesheet" href="{% static 'chat/css/chat.css' %}">
  ```

**Step 4: Commit**

```bash
git add chat/static/chat/css/chat.css chat/templates/chat/index.html
git commit -m "refactor: extract CSS from index.html to chat.css"
```

---

### Task 13: Extract JavaScript from index.html

**Files:**
- Create: `chat/static/chat/js/chat.js`
- Modify: `chat/templates/chat/index.html`

**Step 1: Create chat/static/chat/js/chat.js**

Extract everything between `<script>` (line 701 in original, now a different line after CSS extraction) and `</script>` (line 1616 in original) from `chat/templates/chat/index.html`. Copy the JavaScript content verbatim — no changes.

**Step 2: Replace the script block in index.html**

In `chat/templates/chat/index.html`, replace the inline `<script>...</script>` block with:
```html
<script src="{% static 'chat/js/chat.js' %}"></script>
```

Keep the external `<script src="...marked...">` and `<script src="...mermaid...">` tags — only replace the inline script block.

**Step 3: Verify the final index.html is under 1000 lines**

```bash
wc -l chat/templates/chat/index.html
```
Expected: Under 200 lines

**Step 4: Commit**

```bash
git add chat/static/chat/js/chat.js chat/templates/chat/index.html
git commit -m "refactor: extract JavaScript from index.html to chat.js"
```

---

### Task 14: Final verification

**Files:**
- None (verification only)

**Step 1: Verify no file exceeds 1000 lines**

```bash
find . -name "*.py" -not -path "./.venv/*" -not -path "./node_modules/*" -not -path "./.git/*" | xargs wc -l | sort -rn | head -20
wc -l chat/templates/chat/index.html
wc -l chat/static/chat/js/chat.js
wc -l chat/static/chat/css/chat.css
```
Expected: All files under 1000 lines

**Step 2: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All tests pass

**Step 3: Verify Django can start**

```bash
python manage.py check
```
Expected: System check identified no issues

**Step 4: Verify tui.py imports work**

```bash
python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); django.setup(); from tui import ALL_TOOLS; print(f'{len(ALL_TOOLS)} tools loaded')"
```
Expected: `42 tools loaded` (or whatever the actual count is)

**Step 5: Final commit if any fixes were needed**

```bash
git status
```
If clean, done. If fixes were needed, commit them.
