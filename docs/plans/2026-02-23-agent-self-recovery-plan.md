# Agent Self-Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the agent auto-recover from errors (missing dependencies, code bugs, command failures) instead of stopping and reporting failure.

**Architecture:** System prompt-only change in `agents.py`. Strengthen existing rule 2 and add new rule 20 with a structured self-recovery protocol. No changes to tools, graph logic, or error handling code.

**Tech Stack:** Python, LangGraph (existing agent framework)

---

### Task 1: Strengthen Rule 2 — Error Recovery Instruction

**Files:**
- Modify: `agents.py:3766`

**Step 1: Edit rule 2 in the system prompt**

In `agents.py`, find line 3766 which currently reads:

```python
        2. If a tool returns an error, analyze the cause and try a different approach.
```

Replace it with:

```python
        2. If a tool returns an error, analyze the cause, fix the issue (install missing dependencies, correct code, resolve path issues), and retry. NEVER stop and report an error as your final response if you have not yet attempted to fix it.
```

**Step 2: Verify the edit**

Run: `python -c "import ast; ast.parse(open('agents.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: strengthen rule 2 to require error recovery before reporting"
```

---

### Task 2: Add Rule 20 — Self-Recovery and Persistence

**Files:**
- Modify: `agents.py:3801` (insert after rule 19, before the closing `"""`)

**Step 1: Add rule 20 to the system prompt**

In `agents.py`, find line 3801 which currently reads:

```python
        19. PROGRESS REPORTING: When executing a multi-step plan (Phase 3 of rule 18), after each major step report: what you just completed, and what the next step is. Keep progress updates to 1-2 sentences. Example: "Step 2 complete: created models.py with User schema. Next: adding API routes in views.py."
```

Insert the following new rule AFTER rule 19 (before the closing `"""`):

```python
        20. SELF-RECOVERY AND PERSISTENCE — When you encounter ANY error during task execution, you MUST NOT stop and report failure to the user. Instead, follow this recovery protocol:
           - MISSING DEPENDENCIES: If a tool returns a ModuleNotFoundError, ImportError, 'No module named', 'command not found', or similar missing-package error, immediately use 'run_code' to install it (e.g. 'pip install <package>', 'npm install <package>') and retry the failed action. Do NOT ask the user to install it — install it yourself.
           - CODE ERRORS: If code you wrote or executed produces syntax errors, runtime exceptions, type errors, logical bugs, or test failures, analyze the error output, fix the code using 'create_and_edit_file', and re-run it. Do NOT report the error as a final answer — fix it.
           - COMMAND FAILURES: If a shell command fails, read the error output, determine the cause (wrong flags, missing tools, permission issues), and try an alternative command or approach.
           - PERSISTENT ISSUES: If your first fix attempt fails, try a fundamentally different approach. For example: if a library cannot be installed, find an alternative library that provides the same functionality; if a file path is wrong, use 'search_file' to find the correct one; if a command is unavailable, find an equivalent.
           - ESCALATION: Only report failure to the user AFTER you have made at least 3 genuine attempts to resolve the issue using different approaches. When you do report failure, explain what you tried and why each approach failed.
           - NEVER say "I cannot complete this because X is not installed" or "this requires X which is not available." You have 'run_code' — use it to install X and continue.
```

**Step 2: Verify the edit**

Run: `python -c "import ast; ast.parse(open('agents.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add rule 20 for self-recovery and persistence"
```

---

### Task 3: Verify Complete System Prompt

**Step 1: Print the system prompt to verify both changes**

Run: `python -c "exec(open('agents.py').read().split('self.system_instruction = \"\"\"')[1].split('\"\"\"')[0])" 2>&1 || python -c "import agents; print('Import OK')"`

Manually verify:
- Rule 2 now contains "NEVER stop and report an error"
- Rule 20 exists with all 6 sub-points (MISSING DEPENDENCIES, CODE ERRORS, COMMAND FAILURES, PERSISTENT ISSUES, ESCALATION, NEVER say)
- The closing `"""` is intact
- No other rules were changed

**Step 2: Final commit (if any fixups needed)**

```bash
git add agents.py
git commit -m "fix: finalize self-recovery system prompt"
```
