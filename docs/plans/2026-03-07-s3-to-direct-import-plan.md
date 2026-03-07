# S3 to Direct Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Switch `chat/views.py` from downloading a monolithic `agents.py` from S3 to importing directly from the local `agents/` package, and remove the now-unused `utils.py`.

**Architecture:** Replace the dynamic S3-based module loading with standard Python imports matching the pattern already used by `tui.py`. Delete `utils.py` since its only function (`load_module_from_s3`) is no longer needed.

**Tech Stack:** Python, Django

---

### Task 1: Update chat/views.py to use direct imports

**Files:**
- Modify: `chat/views.py:1-63`

**Step 1: Replace the import block**

Replace lines 1-63 of `chat/views.py` (everything from imports through the `agents_module.X` extractions) with direct imports. The new imports section should be:

```python
import os
import sys
import signal
import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from django.conf import settings
from .models import ChatSession

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
```

What was removed:
- `from decouple import config` (line 10) — no longer needed, was only used for `AWS_STORAGE_BUCKET_NAME`
- `from utils import load_module_from_s3` (line 12) — the S3 loader is being removed
- Lines 18-21 (`bucket_name`, `s3_key`, `agents_module = load_module_from_s3(...)`) — the S3 download mechanism
- Lines 23-63 (all `X = agents_module.X` extractions) — replaced by direct imports above

What was NOT changed:
- Lines 65-393 (everything from `# Initialize OpenAI agent` onward) — completely untouched
- The `from agents import (...)` block uses the exact same names that were previously extracted from `agents_module`

**Step 2: Verify the import works**

Run: `python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); django.setup(); from chat.views import agent; print(f'Agent loaded: {type(agent)}')" `
Expected: `Agent loaded: <class 'agents.core.Agent'>` (no S3 download messages)

**Step 3: Verify Django check passes**

Run: `python manage.py check`
Expected: `System check identified no issues` — and crucially, NO `[INFO] Attempting to download` messages

**Step 4: Commit**

```bash
git add chat/views.py
git commit -m "refactor: switch views.py from S3 download to direct agents/ package imports"
```

---

### Task 2: Delete utils.py

**Files:**
- Delete: `utils.py`

**Step 1: Verify nothing else imports from utils.py**

Run: `grep -rn "from utils import\|import utils" --include="*.py" .`
Expected: No matches (views.py no longer imports it after Task 1)

**Step 2: Delete utils.py**

```bash
git rm utils.py
```

**Step 3: Verify Django still works without utils.py**

Run: `python manage.py check`
Expected: `System check identified no issues`

**Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All 16 tests pass

**Step 5: Commit**

```bash
git commit -m "chore: remove utils.py (load_module_from_s3 no longer needed)"
```

---

### Task 3: Clean up any leftover agents.py from S3

**Files:**
- None (cleanup only)

**Step 1: Check if S3 left behind an agents.py in the project root**

Run: `ls -la agents.py 2>/dev/null || echo "No stale agents.py found"`
Expected: `No stale agents.py found` (it was already deleted in the refactoring branch)

If `agents.py` exists in the project root, it was downloaded by a previous `runserver` session. Delete it:

```bash
rm agents.py
```

**Step 2: Verify the agents/ package takes precedence**

Run: `python -c "import agents; print(agents.__file__)"`
Expected: Path ending in `agents/__init__.py` (not `agents.py`)

**Step 3: Final verification — start Django and confirm no S3 download**

Run: `python manage.py check`
Expected: Clean output with NO `[INFO] Attempting to download` or `[INFO] Successfully downloaded` messages
