# Agent Self-Recovery Design

## Problem

The agent stops mid-task and reports failure when it encounters recoverable errors like missing Python libraries, syntax errors in generated code, or failed commands. Instead of using its existing tools to fix the problem and continue, the LLM gives up and tells the user it cannot proceed.

## Solution: System Prompt Enhancement (Approach A)

Add a new rule (rule 20) to the system prompt in `agents.py` that instructs the LLM to never give up on recoverable errors. Instead, it must use its existing tools (`run_code`, `create_and_edit_file`, `check_syntax`, `run_tests`, `lint_code`) to self-recover.

No changes to tools, graph logic, or error handling code.

## Design

### Change 1: Strengthen Rule 2

Current rule 2:
> If a tool returns an error, analyze the cause and try a different approach.

Updated rule 2:
> If a tool returns an error, analyze the cause, fix the issue (install missing dependencies, correct code, resolve path issues), and retry. NEVER stop and report an error as your final response if you have not yet attempted to fix it.

### Change 2: Add Rule 20 — Self-Recovery and Persistence

```
20. SELF-RECOVERY AND PERSISTENCE — When you encounter ANY error during task execution, you MUST NOT stop and report failure to the user. Instead, follow this recovery protocol:
    - MISSING DEPENDENCIES: If a tool returns a ModuleNotFoundError, ImportError, No module named, command not found, or similar missing-package error, immediately use run_code to install it (e.g. pip install <package>, npm install <package>, apt-get install <package>) and retry the failed action.
    - CODE ERRORS: If code you wrote or executed produces syntax errors, runtime exceptions, type errors, logical bugs, or test failures, analyze the error output, fix the code using create_and_edit_file, and re-run it. Do NOT report the error as a final answer — fix it.
    - COMMAND FAILURES: If a shell command fails, read the error output, determine the cause (wrong flags, missing tools, permission issues), and try an alternative command or approach.
    - PERSISTENT ISSUES: If your first fix attempt fails, try a fundamentally different approach. For example: if a library cannot be installed, find an alternative library; if a file path is wrong, search for the correct one; if a command is unavailable, find an equivalent.
    - ESCALATION: Only report failure to the user AFTER you have made at least 3 genuine attempts to resolve the issue using different approaches. When reporting, explain what you tried and why each approach failed.
    - NEVER say "I cannot complete this because X is not installed" or "this requires X which is not available." Install X and continue. You have run_code — use it.
```

## Scope

- **File changed:** `agents.py` (system prompt only, lines ~3763-3802)
- **Tools changed:** None
- **Graph logic changed:** None
- **Error handling changed:** None

## Why This Works

This is exactly how Claude Code operates. The LLM already has the tools to install packages (`run_code`), fix code (`create_and_edit_file`), and debug (`check_syntax`, `run_tests`, `lint_code`). The only missing piece is the instruction telling it to use them for self-recovery instead of giving up. The existing 25-iteration recursion limit in LangGraph serves as the safety net against infinite loops.
