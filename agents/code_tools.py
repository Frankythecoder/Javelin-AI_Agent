import os
import subprocess
from typing import Dict, Any
from agents.control import ToolDefinition


def run_code_tool(args: Dict[str, Any]) -> str:
    """Execute code locally."""
    import subprocess
    import os
    try:
        command = args.get('command', '')
        if not command:
            return "Error: no command provided"

        print(f"\033[92mExecuting Command:\033[0m {command}")

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        stdout = result.stdout
        stderr = result.stderr

        limit = 10000
        if len(stdout) > limit:
            stdout = stdout[:limit] + f"\n\n[... STDOUT truncated. Total size: {len(result.stdout)} characters ...]"
        if len(stderr) > limit:
            stderr = stderr[:limit] + f"\n\n[... STDERR truncated. Total size: {len(result.stderr)} characters ...]"

        output = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out."
    except Exception as e:
        return f"Error: {str(e)}"


def check_syntax_tool(args: Dict[str, Any]) -> str:
    """Check the syntax of a code file."""
    path = args.get('path', '')
    if not path:
        return "Error: no path provided"

    ext = os.path.splitext(path)[1].lower()
    if ext == '.py':
        command = f"python3 -m py_compile {path}"
    elif ext == '.java':
        command = f"javac {path}"
    elif ext in ['.c']:
        command = f"gcc -fsyntax-only {path}"
    elif ext in ['.cpp', '.cc', '.cxx']:
        command = f"g++ -fsyntax-only {path}"
    elif ext == '.rs':
        if os.path.exists('Cargo.toml'):
            command = "cargo check"
        else:
            command = f"rustc --edition 2021 -o /dev/null --emit=dep-info {path}"
    elif ext in ['.js', '.jsx']:
        command = f"node --check {path}"
    elif ext in ['.ts', '.tsx']:
        command = f"tsc --noEmit {path}"
    elif ext == '.go':
        command = f"go build -o /dev/null {path}"
    elif ext == '.sql':
        command = f"sqlfluff lint {path} --dialect ansi"
    else:
        return f"Error: syntax check not supported for extension {ext}"

    return run_code_tool({'command': command})


def run_tests_tool(args: Dict[str, Any]) -> str:
    """Run tests for the project."""
    command = args.get('command', '')
    if not command:
        # Try to infer command
        if os.path.exists('pytest.ini') or os.path.exists('tests/'):
            command = "pytest"
        elif os.path.exists('Cargo.toml'):
            command = "cargo test"
        elif os.path.exists('package.json'):
            command = "npm test"
        elif os.path.exists('go.mod'):
            command = "go test ./..."
        elif os.path.exists('pom.xml'):
            command = "mvn test"
        elif os.path.exists('build.gradle'):
            command = "gradle test"
        elif os.path.exists('Makefile'):
            command = "make test"
        else:
            return "Error: no test command provided and could not infer one"

    return run_code_tool({'command': command})

def lint_code_tool(args: Dict[str, Any]) -> str:
    """Run static analysis (linting) on a code file."""
    path = args.get('path', '')
    if not path:
        return "Error: no path provided"

    ext = os.path.splitext(path)[1].lower()
    if ext == '.py':
        command = f"pylint {path}"
    elif ext == '.java':
        # Simple checkstyle-like check with javac warnings
        command = f"javac -Xlint:all {path}"
    elif ext in ['.c', '.cpp', '.cc', '.cxx']:
        command = f"cppcheck {path}"
    elif ext == '.rs':
        command = "cargo clippy" if os.path.exists('Cargo.toml') else f"rustc -W help"
    elif ext in ['.js', '.jsx', '.ts', '.tsx']:
        command = f"eslint {path}"
    elif ext == '.go':
        command = f"go vet {path}"
    elif ext == '.sql':
        command = f"sqlfluff lint {path} --dialect ansi"
    else:
        return f"Error: linting not supported for extension {ext}"

    return run_code_tool({'command': command})


RUN_CODE_DEFINITION = ToolDefinition(
    name="run_code",
    description="Execute a shell command or run a script. Supports Python, C (gcc), C++ (g++), Java (javac), and any other shell command. Use this to compile, run, test code, or perform system checks.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute."
            }
        },
        "required": ["command"]
    },
    function=run_code_tool,
    requires_approval=True
)


CHECK_SYNTAX_DEFINITION = ToolDefinition(
    name="check_syntax",
    description="Check the syntax of a code file (supports .py, .java, .c, .cpp, .rs, .js, .ts, .go, .sql).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the code file."
            }
        },
        "required": ["path"]
    },
    function=check_syntax_tool,
    requires_approval=True
)


RUN_TESTS_DEFINITION = ToolDefinition(
    name="run_tests",
    description="Run tests for the project. Automatically detects pytest if no command is provided.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Optional command to run tests."
            }
        },
        "required": []
    },
    function=run_tests_tool,
    requires_approval=True
)


LINT_CODE_DEFINITION = ToolDefinition(
    name="lint_code",
    description="Run static analysis (linting) on a code file (supports .py, .java, .c, .cpp, .rs, .js, .ts, .go, .sql).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the code file."
            }
        },
        "required": ["path"]
    },
    function=lint_code_tool,
    requires_approval=True
)
