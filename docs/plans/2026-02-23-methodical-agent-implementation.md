# Methodical Agent Behavior — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the agent's system instruction so it asks clarifying questions and presents a plan before executing complex tasks, while keeping simple tasks unchanged.

**Architecture:** A single string edit to `self.system_instruction` in `agents.py`. Rule 10 gets a qualifier, and three new rules (17-19) are appended. No code, graph, or structural changes.

**Tech Stack:** Python, OpenAI GPT-4o (system prompt engineering).

---

### Task 1: Update Rule 10 to scope it to simple tasks

**Files:**
- Modify: `agents.py:3777`

**Step 1: Replace Rule 10**

Change line 3777 from:

```
        10. Do not ask for permission to perform an action; just execute the necessary steps to complete the task.
```

To:

```
        10. For SIMPLE tasks (single-step, clear intent, fewer than 3 tool calls): Do not ask for permission; just execute the necessary steps to complete the task. For COMPLEX tasks, follow rules 17-18 instead.
```

**Step 2: Verify the edit**

Run: `python -c "import agents; a = agents.Agent.__init__; print('OK')"`
Expected: No syntax errors.

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: scope rule 10 to simple tasks, reference complex task rules"
```

---

### Task 2: Add Rule 17 — Task Classification

**Files:**
- Modify: `agents.py:3790-3791` (after rule 16, before closing `"""`)

**Step 1: Add Rule 17 after rule 16**

Insert the following after the last line of rule 16 (`- Always confirm the total price and all details with the user before calling book_travel.`) and before the closing `"""`:

```
        17. TASK CLASSIFICATION — Before acting on any user request, classify it:
           - SIMPLE: The task has clear intent, requires fewer than 3 tool calls, and has no ambiguity in scope or approach (e.g. "read file X", "what is 2+2", "create a hello world script"). For simple tasks, execute immediately per rule 10.
           - COMPLEX: The task is multi-step (3+ tool calls), has ambiguity in scope/approach, touches multiple files, or requires architectural decisions (e.g. "build me a REST API", "refactor the auth system", "add a TUI to this project"). For complex tasks, follow rule 18.
           If unsure, treat it as complex. It is better to ask one unnecessary question than to waste effort building the wrong thing.
```

**Step 2: Verify the edit**

Run: `python -c "from agents import Agent; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add rule 17 — task classification (simple vs complex)"
```

---

### Task 3: Add Rule 18 — Complex Task Protocol

**Files:**
- Modify: `agents.py` (after Rule 17, before closing `"""`)

**Step 1: Add Rule 18**

Insert after rule 17:

```
        18. COMPLEX TASK PROTOCOL — When a task is classified as COMPLEX, follow these phases IN ORDER. Do NOT call any tools during phases 1 and 2; respond with text only.
           PHASE 1 — CLARIFY: Ask 1-3 focused questions to understand the user's requirements. Ask ONE question per response. Focus on: scope, constraints, preferred approach, and success criteria. Examples: "Should this include authentication?", "Which framework do you prefer?", "What files should I avoid changing?" Move to Phase 2 once you have enough context. SKIP this phase if the user explicitly says "just do it" or provides comprehensive details upfront.
           PHASE 2 — PLAN: Present a numbered step-by-step plan of what you will do. Include which files you will create or modify. End with "Ready to proceed?" and WAIT for the user to confirm before moving to Phase 3. If the user requests changes to the plan, revise and present again.
           PHASE 3 — EXECUTE: Carry out the plan step by step using tools. Follow all other rules (1-16) during execution. After completing each major step, briefly report what was done and what comes next.
           OVERRIDE: If at any point the user says "just do it", "skip the questions", or "go ahead", immediately move to Phase 3 and execute.
```

**Step 2: Verify the edit**

Run: `python -c "from agents import Agent; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add rule 18 — complex task protocol (clarify, plan, execute)"
```

---

### Task 4: Add Rule 19 — Progress Reporting

**Files:**
- Modify: `agents.py` (after Rule 18, before closing `"""`)

**Step 1: Add Rule 19**

Insert after rule 18:

```
        19. PROGRESS REPORTING: When executing a multi-step plan (Phase 3 of rule 18), after each major step report: what you just completed, and what the next step is. Keep progress updates to 1-2 sentences. Example: "Step 2 complete: created models.py with User schema. Next: adding API routes in views.py."
```

**Step 2: Verify the edit**

Run: `python -c "from agents import Agent; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add rule 19 — progress reporting during plan execution"
```

---

### Task 5: End-to-end verification

**Files:**
- No changes — verification only.

**Step 1: Verify full import**

Run: `python -c "from agents import Agent; print('OK')"`
Expected: `OK`

**Step 2: Verify system instruction contains all new rules**

Run: `python -c "from agents import Agent; from openai import OpenAI; from django.conf import settings; client = OpenAI(api_key=settings.OPENAI_API_KEY); a = Agent(client, 'gpt-4o', get_user_message=None, tools=[]); assert 'TASK CLASSIFICATION' in a.system_instruction; assert 'COMPLEX TASK PROTOCOL' in a.system_instruction; assert 'PROGRESS REPORTING' in a.system_instruction; assert 'For SIMPLE tasks' in a.system_instruction; print('All 4 rules verified')"`
Expected: `All 4 rules verified`

**Step 3: Verify no other files changed**

Run: `git diff HEAD -- tui.py chat/ settings.py urls.py manage.py requirements.txt utils.py`
Expected: No output (no changes to other files).

**Step 4: Verify TUI still works**

Run: `javelin --help`
Expected: Shows usage with --dir and --load options.
