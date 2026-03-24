# Project File Reorganization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize root-level files into `config/`, `mcp/`, `samples/`, and `assets/` directories so the project root is clean and follows standard Django conventions.

**Architecture:** Move Django config files (`settings.py`, `urls.py`, `asgi.py`, `wsgi.py`, `__init__.py`) into `config/` package. Move MCP servers into `mcp/` package (renaming to drop the `mcp_` prefix). Move sample/test files into `samples/`. Move logo into `assets/`. Update all import references. Delete the `nul` artifact.

**Tech Stack:** Python, Django

---

### Task 1: Create config/ package and move Django config files

**Files:**
- Create: `config/` directory
- Move: `settings.py` -> `config/settings.py`
- Move: `urls.py` -> `config/urls.py`
- Move: `asgi.py` -> `config/asgi.py`
- Move: `wsgi.py` -> `config/wsgi.py`
- Move: `__init__.py` -> `config/__init__.py`

**Step 1: Create the directory and move files**

```bash
mkdir -p config
git mv settings.py config/settings.py
git mv urls.py config/urls.py
git mv asgi.py config/asgi.py
git mv wsgi.py config/wsgi.py
git mv __init__.py config/__init__.py
```

**Step 2: Update `config/settings.py` — 3 changes**

Line 27-28 — update comment and BASE_DIR (settings.py is now one level deeper):
```python
# OLD:
# In flat layout, settings.py is in project root, so parent is the project root
BASE_DIR = Path(__file__).resolve().parent

# NEW:
# settings.py is in config/, so parent.parent is the project root
BASE_DIR = Path(__file__).resolve().parent.parent
```

Line 66 — update ROOT_URLCONF:
```python
# OLD:
ROOT_URLCONF = 'urls'

# NEW:
ROOT_URLCONF = 'config.urls'
```

Line 84 — update WSGI_APPLICATION:
```python
# OLD:
WSGI_APPLICATION = 'wsgi.application'

# NEW:
WSGI_APPLICATION = 'config.wsgi.application'
```

**Step 3: Update `manage.py` line 9**

```python
# OLD:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# NEW:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```

**Step 4: Update `tui.py` line 11**

```python
# OLD:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# NEW:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```

**Step 5: Update `config/asgi.py` line 14**

```python
# OLD:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# NEW:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```

**Step 6: Update `config/wsgi.py` line 14**

```python
# OLD:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# NEW:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
```

**Step 7: Verify Django check passes**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced)`

**Step 8: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All 16 tests pass

**Step 9: Commit**

```bash
git add manage.py tui.py config/
git commit -m "refactor: move Django config files into config/ package"
```

---

### Task 2: Create mcp/ package and move MCP server files

**Files:**
- Create: `mcp/__init__.py`
- Move: `mcp_github_server.py` -> `mcp/github_server.py`
- Move: `mcp_playwright_server.py` -> `mcp/playwright_server.py`
- Modify: `agents/email_tools.py:32`
- Modify: `agents/github_tools.py:17-18`
- Modify: `tests/test_mcp_navigate.py:6`

**Step 1: Create directory, init file, and move files**

```bash
mkdir -p mcp
touch mcp/__init__.py
git mv mcp_github_server.py mcp/github_server.py
git mv mcp_playwright_server.py mcp/playwright_server.py
git add mcp/__init__.py
```

**Step 2: Update `agents/email_tools.py` line 32**

This is inside a function body (runtime import). Change:
```python
# OLD:
    from mcp_playwright_server import _toggle_www

# NEW:
    from mcp.playwright_server import _toggle_www
```

**Step 3: Update `agents/github_tools.py` lines 17-18**

The current code uses `__file__` (which is `agents/github_tools.py`) to find the MCP server. The path needs to go up one level to project root, then into `mcp/`:

```python
# OLD:
            args=["-B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_github_server.py")],
            cwd=os.path.dirname(os.path.abspath(__file__))

# NEW:
            args=["-B", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp", "github_server.py")],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

Note: `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` navigates from `agents/github_tools.py` -> `agents/` -> project root.

**Step 4: Update `tests/test_mcp_navigate.py` line 6**

```python
# OLD:
from mcp_playwright_server import _toggle_www

# NEW:
from mcp.playwright_server import _toggle_www
```

**Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All 16 tests pass (especially `test_mcp_navigate.py`)

**Step 6: Verify Django check passes**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced)`

**Step 7: Commit**

```bash
git add agents/email_tools.py agents/github_tools.py tests/test_mcp_navigate.py mcp/
git commit -m "refactor: move MCP servers into mcp/ package"
```

---

### Task 3: Move sample files into samples/ directory

**Files:**
- Create: `samples/` directory
- Move: `simple_shooter.py` -> `samples/simple_shooter.py`
- Move: `oddnumbers.java` -> `samples/oddnumbers.java`
- Move: `test_imap.py` -> `samples/test_imap.py`
- Move: `test_image.jpg` -> `samples/test_image.jpg`
- Move: `test_video.mp4` -> `samples/test_video.mp4`

**Step 1: Create directory and move files**

```bash
mkdir -p samples
git mv simple_shooter.py samples/simple_shooter.py
git mv oddnumbers.java samples/oddnumbers.java
git mv test_imap.py samples/test_imap.py
git mv test_image.jpg samples/test_image.jpg
git mv test_video.mp4 samples/test_video.mp4
```

**Step 2: Verify nothing references these files**

Run: `grep -rn "simple_shooter\|oddnumbers\|test_imap\|test_image\|test_video" --include="*.py" . | grep -v samples/ | grep -v evals/`
Expected: No matches (these are standalone files not imported anywhere in core code). Eval results files may reference them by name in stored outputs — that's fine, those are just saved text.

**Step 3: Commit**

```bash
git add samples/
git commit -m "refactor: move sample and test files into samples/ directory"
```

---

### Task 4: Move logo into assets/ and clean up nul file

**Files:**
- Create: `assets/` directory
- Move: `javelin.png` -> `assets/javelin.png`
- Modify: `chat/views.py:361`
- Delete: `nul`

**Step 1: Create directory and move logo**

```bash
mkdir -p assets
git mv javelin.png assets/javelin.png
```

**Step 2: Update `chat/views.py` line 361**

```python
# OLD:
    logo_path = os.path.join(settings.BASE_DIR, 'javelin.png')

# NEW:
    logo_path = os.path.join(settings.BASE_DIR, 'assets', 'javelin.png')
```

**Step 3: Delete the `nul` artifact**

```bash
git rm nul 2>/dev/null || rm -f nul
```

If `nul` is not tracked by git, just delete it with `rm`.

**Step 4: Verify Django check passes**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced)`

**Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All 16 tests pass

**Step 6: Commit**

```bash
git add chat/views.py assets/
git status  # check if nul deletion needs staging
git commit -m "refactor: move logo to assets/, delete nul artifact"
```

---

### Task 5: Final verification

**Files:**
- None (verification only)

**Step 1: Verify the project root is clean**

Run: `ls -1 *.py *.java *.jpg *.mp4 *.png 2>/dev/null`
Expected: Only `manage.py` and `tui.py` should show as `.py` files. No `.java`, `.jpg`, `.mp4`, or `.png` files.

**Step 2: Verify project structure**

Run: `find . -maxdepth 1 -type f | sort`
Expected:
```
./.env
./.gitignore
./db.sqlite3
./Dockerfile.sandbox
./manage.py
./pyproject.toml
./README.md
./requirements.txt
./tui.py
```

**Step 3: Verify all directories**

Run: `find . -maxdepth 1 -type d | sort`
Expected:
```
.
./agents
./assets
./chat
./config
./docs
./evals
./mcp
./samples
./tests
```
(Plus `.git`, `__pycache__`, `.pytest_cache`, `ai_agent.egg-info` if present)

**Step 4: Run Django check**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced)`

**Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All 16 tests pass

**Step 6: Verify TUI imports work**

Run: `python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); import django; django.setup(); from tui import ALL_TOOLS; print(f'{len(ALL_TOOLS)} tools loaded')"`
Expected: `40 tools loaded`
