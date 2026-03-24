# evals/validators.py
"""Ground-truth validators for EATP evaluation tasks.

Two tiers:
- Lightweight: single-condition checks (file exists, response keyword)
- Full: composite checks verifying correct approach (tool ordering + output)
"""
import os
import subprocess


def file_exists(path):
    """Validator: file was created at path (relative to workdir)."""
    def check(result, workdir):
        return os.path.exists(os.path.join(workdir, path))
    return check


def file_contains(path, substring):
    """Validator: file exists and contains substring."""
    def check(result, workdir):
        fpath = os.path.join(workdir, path)
        if not os.path.exists(fpath):
            return False
        try:
            with open(fpath, 'r', errors='replace') as f:
                return substring in f.read()
        except Exception:
            return False
    return check


def response_mentions(keyword):
    """Validator: agent response contains keyword (case-insensitive)."""
    def check(result, workdir):
        response = result.get('response', '')
        return keyword.lower() in response.lower()
    return check


def tool_was_called(tool_name):
    """Validator: tool appears in execution history."""
    def check(result, workdir):
        history = result.get('history', [])
        return any(
            m.get('name') == tool_name
            for m in history if m.get('role') == 'tool'
        )
    return check


def script_runs(path):
    """Validator: Python script executes with return code 0."""
    def check(result, workdir):
        fpath = os.path.join(workdir, path)
        if not os.path.exists(fpath):
            return False
        try:
            r = subprocess.run(
                ['python', fpath],
                capture_output=True, cwd=workdir, timeout=15
            )
            return r.returncode == 0
        except Exception:
            return False
    return check


def tool_called_before(before_tool, after_tool):
    """Validator: before_tool appears earlier in history than after_tool."""
    def check(result, workdir):
        called = [
            m.get('name') for m in result.get('history', [])
            if m.get('role') == 'tool'
        ]
        if before_tool not in called or after_tool not in called:
            return False
        return called.index(before_tool) < called.index(after_tool)
    return check


def correct_tool_order(*expected_tools):
    """Validator: tools appear in specified order (not necessarily adjacent)."""
    def check(result, workdir):
        called = [
            m.get('name') for m in result.get('history', [])
            if m.get('role') == 'tool'
        ]
        idx = 0
        for tool in called:
            if idx < len(expected_tools) and tool == expected_tools[idx]:
                idx += 1
        return idx == len(expected_tools)
    return check


def composite(*validators):
    """Validator: all inner validators must pass."""
    def check(result, workdir):
        return all(v(result, workdir) for v in validators)
    return check


def default_validator(result, workdir):
    """Default: at least one tool called and response doesn't start with Error."""
    history = result.get('history', [])
    has_tool = any(m.get('role') == 'tool' for m in history)
    response = result.get('response', '')
    no_error = not response.startswith("Error")
    return has_tool and no_error


# ── Validator Registry ──────────────────────────────────────────────
# Populated in Task 7 after tasks.json is finalized.
# Keys are task IDs, values are validator callables.
VALIDATORS = {}
