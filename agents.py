# SECURITY WARNING:
# The file tools below accept absolute and relative paths and searches files broadly in 
# common folders like 
# (Downloads, Documents, C:/Users/yourusername, C:/Users/yourusername/anysubfolder, Videos, Pictures, Pictures/Screeshots, 
# etc) if paths are not provided in the user prompts.
# This allows reading, writing, deleting, and renaming files anywhere on the system
# that the process has permission for. Use with caution!

import os
import langchain
import threading
import requests
import json
import base64
import webbrowser
import imaplib
import time
import re
import subprocess
import platform
import uuid
import cv2
import shutil
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid
from email.policy import SMTP
from urllib.parse import quote
from openai import OpenAI
from typing import Dict, List, Callable, Any
from django.conf import settings
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from docx import Document
from openpyxl import Workbook
from pptx import Presentation

class AgentControlState:
    def __init__(self):
        self.stopped = False
        self.tools_enabled = True
        self.lock = threading.Lock()

    def stop(self):
        with self.lock:
            self.stopped = True

    def disable_tools(self):
        with self.lock:
            self.tools_enabled = False

    def enable_tools(self):
        with self.lock:
            self.tools_enabled = True

class ToolDefinition:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], function: Callable[[Dict[str, Any]], str], requires_approval: bool = False):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function
        self.requires_approval = requires_approval


def find_file_broadly(filename: str) -> str:
    """Attempt to find a file by name in common user directories."""
    if not filename:
        return None
        
    if os.path.isabs(filename):
        return filename if os.path.exists(filename) else None
        
    # Handle nested paths by resolving the base directory first
    normalized_path = filename.replace('\\', '/')
    if '/' in normalized_path:
        parts = normalized_path.split('/')
        base_dir = find_directory_broadly(parts[0])
        if base_dir and os.path.isabs(base_dir):
            return find_file_broadly(os.path.join(base_dir, *parts[1:]))

    # Check for well-known folders directly if filename is one of them
    user_home = os.path.expanduser("~")
    well_known = {
        "frank": user_home,
        "documents": os.path.join(user_home, "Documents"),
        "desktop": os.path.join(user_home, "Desktop"),
        "downloads": os.path.join(user_home, "Downloads"),
        "pictures": os.path.join(user_home, "Pictures"),
        "videos": os.path.join(user_home, "Videos"),
    }
    if filename.lower() in well_known:
        path = well_known[filename.lower()]
        if os.path.exists(path):
            return path

    # Search in current directory
    if os.path.exists(filename):
        return os.path.abspath(filename)
        
    # Define common search paths
    user_home = os.path.expanduser("~")
    search_dirs = [
        user_home,
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "OneDrive", "Documents"),
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Pictures"),
        os.path.join(user_home, "Pictures", "Screenshots"),
        os.path.join(user_home, "Videos"),
        os.path.join(user_home, "projects"),
        os.path.join(user_home, "repos"),
        os.path.join(user_home, "work"),
        os.getcwd(),
    ]
    
    # Filter out non-existent directories and ensure uniqueness
    search_dirs = list(dict.fromkeys(d for d in search_dirs if os.path.exists(d)))
    
    # Search for exact match first
    for directory in search_dirs:
        # Check direct children
        try:
            for entry in os.listdir(directory):
                if entry.lower() == filename.lower() or os.path.splitext(entry)[0].lower() == filename.lower():
                    full_path = os.path.join(directory, entry)
                    if os.path.isfile(full_path):
                        return full_path
        except Exception:
            continue
            
    # Search recursively with limited depth if not found
    for directory in search_dirs:
        try:
            for root, dirs, files in os.walk(directory):
                # Limit depth to avoid performance issues
                try:
                    rel = os.path.relpath(root, directory)
                    depth = 0 if rel == '.' else len(rel.replace('\\', '/').split('/'))
                except ValueError:
                    depth = 0
                if depth >= 4:
                    del dirs[:] # Don't go deeper
                
                for file in files:
                    if file.lower() == filename.lower() or os.path.splitext(file)[0].lower() == filename.lower() or filename.lower() in file.lower():
                        return os.path.join(root, file)
        except Exception:
            continue
            
    return None
    
    
def find_directory_broadly(dirname: str) -> str:
    """Attempt to find a directory by name in common user directories."""
    if not dirname:
        return None
        
    if os.path.isabs(dirname):
        return dirname if os.path.isdir(dirname) else None
        
    # Handle nested paths by resolving the base directory first
    normalized_path = dirname.replace('\\', '/')
    if '/' in normalized_path:
        parts = normalized_path.split('/')
        base_dir = find_directory_broadly(parts[0])
        if base_dir and os.path.isabs(base_dir):
            return os.path.abspath(os.path.join(base_dir, *parts[1:]))

    # Check for well-known folders directly if dirname is one of them
    user_home = os.path.expanduser("~")
    well_known = {
        "frank": user_home,
        "documents": os.path.join(user_home, "Documents"),
        "desktop": os.path.join(user_home, "Desktop"),
        "downloads": os.path.join(user_home, "Downloads"),
        "pictures": os.path.join(user_home, "Pictures"),
        "videos": os.path.join(user_home, "Videos"),
    }
    if dirname.lower() in well_known:
        path = well_known[dirname.lower()]
        if os.path.exists(path):
            return path

    # Search in current directory
    if os.path.isdir(dirname):
        return os.path.abspath(dirname)
        
    # Define common search paths
    user_home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "OneDrive", "Documents"),
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Pictures"),
        os.path.join(user_home, "Videos"),
        os.path.join(user_home, "projects"),
        os.path.join(user_home, "repos"),
        os.path.join(user_home, "work"),
        user_home,
        os.getcwd(),
    ]
    
    # Filter out non-existent directories and ensure uniqueness
    search_dirs = list(dict.fromkeys(d for d in search_dirs if os.path.exists(d)))
    
    # Search for exact match first
    for directory in search_dirs:
        try:
            for entry in os.listdir(directory):
                full_path = os.path.join(directory, entry)
                if os.path.isdir(full_path) and entry.lower() == dirname.lower():
                    return full_path
        except Exception:
            continue
            
    # Search recursively with limited depth if not found
    for directory in search_dirs:
        try:
            for root, dirs, files in os.walk(directory):
                # Limit depth to avoid performance issues
                try:
                    rel = os.path.relpath(root, directory)
                    depth = 0 if rel == '.' else len(rel.replace('\\', '/').split('/'))
                except ValueError:
                    depth = 0
                if depth >= 4:
                    del dirs[:] # Don't go deeper
                    
                for d in dirs:
                    if d.lower() == dirname.lower() or dirname.lower() in d.lower():
                        return os.path.join(root, d)
        except Exception:
            continue
            
    return None


def find_file_broadly_tool(args: Dict[str, Any]) -> str:
    """Attempt to find a file by name in common user directories."""
    filename = args.get('filename', '')
    if not filename:
        return "Error: No filename provided."
    found_path = find_file_broadly(filename)
    if found_path:
        return f"File found at: {found_path}"
    else:
        return f"Could not find file '{filename}' in common directories."


def find_directory_broadly_tool(args: Dict[str, Any]) -> str:
    """Attempt to find a directory by name in common user directories."""
    dirname = args.get('dirname', '')
    if not dirname:
        return "Error: No directory name provided."
    found_path = find_directory_broadly(dirname)
    if found_path:
        return f"Directory found at: {found_path}"
    else:
        return f"Could not find directory '{dirname}' in common directories."


def search_file_tool(args: Dict[str, Any]) -> str:
    """Search for a file by name across common directories and return its absolute path."""
    filename = args.get('filename', '')
    if not filename:
        return "Error: No filename provided."
        
    found_path = find_file_broadly(filename)
    if found_path:
        return f"File found at: {found_path}"
    else:
        return f"Could not find file '{filename}' in common directories."


def read_file_tool(args: Dict[str, Any]) -> str:
    """Read the contents of a given file path (absolute or relative) with enhanced error handling for binary files and size limits."""
    path = args.get('path', '')
    offset = args.get('offset', 0)
    limit = args.get('limit', 10000)  # Reduced default limit to 10k characters to prevent rate limits and save tokens

    if not path:
        return "No path provided."

    # Try to find the file if it doesn't exist at the given path
    actual_path = path
    if not os.path.exists(path):
        found_path = find_file_broadly(path)
        if found_path:
            actual_path = found_path
        else:
            return f"Error: File '{path}' does not exist and could not be found in common directories."

    if os.path.isdir(actual_path):
        return f"'{actual_path}' is a directory, not a file."

    try:
        # Read initial bytes to determine file type
        with open(actual_path, 'rb') as f:
            initial_bytes = f.read(1024)
            # Character set to check for non-text files
            text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
            is_binary = bool(initial_bytes.translate(None, text_characters))

            if is_binary:
                # If it's binary, check if it's an image we can recognize
                ext = os.path.splitext(actual_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png']:
                    return f"The file '{actual_path}' appears to be an image. Use 'recognize_image' tool to analyze it."
                return f"The file '{actual_path}' appears to be binary and cannot be read as text."

        # If the file is text, proceed to read it with limit and offset
        file_size = os.path.getsize(actual_path)
        with open(actual_path, 'r', encoding='utf-8', errors='replace') as f:
            if offset > 0:
                f.seek(offset)
            content = f.read(limit)
        
        result = f"Content of {actual_path}:\n\n" + content
        if file_size > (offset + limit):
            result += f"\n\n[... Output truncated. File size: {file_size} bytes. Read {limit} characters from offset {offset}. Use 'limit' and 'offset' to read more ...]"
        
        return result
    except IOError as e:
        return f"File access issue: {e}"
    except UnicodeDecodeError:
        return "The file contains non-UTF-8 characters and appears to be binary."
    except Exception as e:
        return f"An unexpected problem occurred: {e}"


def list_files_tool(args: Dict[str, Any]) -> str:
    """List files and directories at a given path (absolute or relative)."""
    try:
        path = args.get('path', '.')
        if not path:
            path = '.'

        actual_path = path
        if not os.path.exists(path):
            found_path = find_directory_broadly(path)
            if found_path:
                actual_path = found_path
            else:
                return f"Error: Path '{path}' does not exist and could not be found in common directories."
        
        if not os.path.isdir(actual_path):
            return f"Error: Path '{actual_path}' is not a directory."

        entries = os.listdir(actual_path)
        files = []
        for entry in entries:
            full_path = os.path.join(actual_path, entry)
            if os.path.isdir(full_path):
                files.append(f"{entry}/")
            else:
                files.append(entry)

        return json.dumps(sorted(files))
    except Exception as e:
        return f"Error: {str(e)}"
    
def playwright_mcp_tool(args):
    import asyncio
    import sys
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    async def _call():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_playwright_server.py")],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("navigate", args)
                return result.content[0].text if result.content else ""

    try:
        return asyncio.run(_call())
    except Exception as e:
        return f"Playwright MCP error: {e}"

def change_working_directory_tool(args: Dict[str, Any]) -> str:
    """Change the current working directory of the agent to a different project or folder."""
    path = args.get('path', '')
    if not path:
        return "Error: No path provided."
    
    actual_path = path
    if not os.path.exists(path):
        found_path = find_directory_broadly(path)
        if found_path:
            actual_path = found_path
        else:
            return f"Error: Directory '{path}' not found and could not be located in common directories."
    
    if not os.path.isdir(actual_path):
        return f"Error: '{actual_path}' is not a directory."
    
    try:
        os.chdir(actual_path)
        return f"Successfully changed working directory to: {os.getcwd()}"
    except Exception as e:
        return f"Error changing directory: {str(e)}"


def create_new_file(file_path: str, content: str) -> str:
    """Create a new file with the given content at any path (absolute or relative)."""
    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and directory != '.':
            os.makedirs(directory, exist_ok=True)

        # Write the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully created file {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"


def delete_file_tool(args: Dict[str, Any]) -> str:
    """Delete a file or directory at any path (absolute or relative)."""
    try:
        path = args.get('path', '')
        if not path:
            return "Error: no path provided"
            
        actual_path = path
        if not os.path.exists(path):
            # Try to find a directory first if the user mentions "folder" or if it ends in /
            found_path = None
            if path.endswith('/') or path.endswith('\\'):
                found_path = find_directory_broadly(path.rstrip('/\\'))
            
            if not found_path:
                found_path = find_directory_broadly(path)
            if not found_path:
                found_path = find_file_broadly(path)
            
            if found_path:
                actual_path = found_path
            else:
                return f"Error: '{path}' does not exist and could not be found in common directories."

        if os.path.isdir(actual_path):
            shutil.rmtree(actual_path)
            return f"Successfully deleted directory {actual_path}"
        else:
            os.remove(actual_path)
            return f"Successfully deleted file {actual_path}"
    except Exception as e:
        return f"Error: {str(e)}"


def create_and_edit_file_tool(args: Dict[str, Any]) -> str:
    """Create or edit any file at any path (absolute or relative) by replacing old_str with new_str, or writing new_str if the file does not exist."""
    try:
        path = args.get('path', '')
        old_str = args.get('old_str', '').replace('\\n', '\n')
        new_str = args.get('new_str', '').replace('\\n', '\n')

        if not path:
            return "Error: No path provided."
        
        actual_path = path
        if not os.path.exists(path):
            # If path doesn't exist, check if the parent directory exists or can be found
            parent_dir = os.path.dirname(path)
            filename = os.path.basename(path)
            
            if parent_dir and not os.path.exists(parent_dir):
                found_parent = find_directory_broadly(parent_dir)
                if found_parent:
                    actual_path = os.path.join(found_parent, filename)
        
        if old_str == new_str:
            return "Error: old_str and new_str are the same; no changes made."

        # Try to read the existing file
        if not os.path.exists(actual_path):
            if old_str == "":
                return create_new_file(actual_path, new_str)
            else:
                return f"Error: File '{actual_path}' not found and no content provided to create it."

        with open(actual_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Replace old_str with new_str
        if old_str not in content and old_str != "":
            return f"Error: old_str not found in '{actual_path}'"

        new_content = content.replace(old_str, new_str) if old_str != "" else new_str

        # Write the modified content back to file
        with open(actual_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return f"Successfully updated '{actual_path}'"

    except Exception as e:
        return f"Error editing file: {str(e)}"


def rename_file_tool(args: Dict[str, Any]) -> str:
    """Rename a file at any path (absolute or relative). Args: old_path (str), new_path (str)."""
    try:
        old_path = args.get('old_path', '')
        new_path = args.get('new_path', '')
        if not old_path or not new_path:
            return "Error: old_path and new_path are required."
        if not os.path.exists(old_path):
            return f"Error: file {old_path} does not exist."
        if os.path.exists(new_path):
            return f"Error: file {new_path} already exists."
        os.rename(old_path, new_path)
        return f"Successfully renamed {old_path} to {new_path}"
    except Exception as e:
        return f"Error: {str(e)}"


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
            text=True, 
            timeout=30
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
        return "Error: Command timed out after 30 seconds"
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

def _github_mcp_call(tool_name, args):
    import asyncio
    import sys
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    async def _call():
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-B", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_github_server.py")],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                return result.content[0].text if result.content else ""

    try:
        return asyncio.run(_call())
    except Exception as e:
        return f"GitHub MCP error: {e}"


def github_create_pr_tool(args):
    return _github_mcp_call("create_pull_request", args)


def github_create_branch_tool(args):
    return _github_mcp_call("create_branch", args)


def github_commit_file_tool(args):
    return _github_mcp_call("commit_file", args)


def github_commit_local_file_tool(args):
    return _github_mcp_call("commit_local_file", args)


def create_github_issue_tool(args: Dict[str, Any]) -> str:
    """Create a GitHub issue on the configured repository."""
    try:
        title = args.get('title', '')
        body = args.get('body', '')
        labels = args.get('labels', [])
        assignees = args.get('assignees', [])

        if not title:
            return "Error: Issue title is required."

        # Get GitHub credentials from settings
        github_token = getattr(settings, 'GITHUB_TOKEN', None)
        github_repo = getattr(settings, 'GITHUB_REPO', None)

        if not github_token or not github_repo:
            return "Error: GITHUB_TOKEN or GITHUB_REPO not configured in settings."

        # GitHub API endpoint
        url = f"https://api.github.com/repos/{github_repo}/issues"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        payload = {
            "title": title,
            "body": body
        }

        if labels:
            payload["labels"] = labels if isinstance(labels, list) else [labels]
        if assignees:
            payload["assignees"] = assignees if isinstance(assignees, list) else [assignees]

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            issue_data = response.json()
            issue_number = issue_data.get('number')
            issue_url = issue_data.get('html_url')
            return f"Successfully created issue #{issue_number}: {issue_url}"
        else:
            return f"Error creating issue: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Error: {str(e)}"


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


def create_gmail_draft(recipient: str, subject: str, body: str, attachments: List[str]) -> str:
    """Create a draft in Gmail via IMAP."""
    user = getattr(settings, 'GMAIL_SENDER_ADDRESS', None)
    password = getattr(settings, 'GMAIL_APP_PASSWORD', None)

    if not user or not password:
        return "Error: GMAIL_SENDER_ADDRESS or GMAIL_APP_PASSWORD not configured in settings."

    try:
        # Create message with robust structure
        msg = MIMEMultipart('mixed')
        msg['To'] = recipient
        msg['From'] = user
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()
        
        # Create the body container (multipart/alternative)
        body_part = MIMEMultipart('alternative')
        
        # Add plain text version
        body_part.attach(MIMEText(body, 'plain'))
        
        # Add HTML version (simple conversion)
        html_body = body.replace('\n', '<br>')
        body_part.attach(MIMEText(f"<html><body>{html_body}</body></html>", 'html'))
        
        # Attach body container to the main message
        msg.attach(body_part)

        for path in attachments:
            if os.path.exists(path):
                filename = os.path.basename(path)
                part = MIMEBase('application', "octet-stream")
                try:
                    with open(path, 'rb') as file:
                        part.set_payload(file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(part)
                except Exception as file_err:
                    return f"Error: Reading attachment {path} failed: {str(file_err)}"
            else:
                return f"Error: Attachment file not found at {path}"

        # Connect to Gmail IMAP
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(user, password)
        except imaplib.IMAP4.error as auth_err:
            return f"Error: Authentication failed. Please ensure: 1. Your GMAIL_PASSWORD in .env is a 16-character App Password. 2. IMAP is enabled. Original error: {str(auth_err)}"
        except Exception as conn_err:
            return f"Error: Failed to connect to Gmail IMAP: {str(conn_err)}"

        # Try to find the Drafts folder
        status, folders = imap.list()
        draft_folder = None
        if status == 'OK':
            for folder in folders:
                folder_str = folder.decode('utf-8')
                # Gmail drafts folder has the \Drafts attribute
                if '\\Drafts' in folder_str:
                    # The folder name is usually the last quoted string
                    matches = re.findall(r'"([^"]+)"', folder_str)
                    if matches:
                        draft_folder = matches[-1]
                    break
        
        if not draft_folder:
            # Fallback for some configurations
            draft_folder = "[Gmail]/Drafts"

        # Append to drafts
        try:
            # Ensure draft_folder is quoted if it contains spaces or special characters
            quoted_folder = draft_folder
            if not draft_folder.startswith('"') and any(c in draft_folder for c in ' []/'):
                quoted_folder = f'"{draft_folder}"'

            # Use CRLF for line endings as required by IMAP
            msg_bytes = msg.as_bytes(policy=SMTP)
            res, detail = imap.append(quoted_folder, r'(\Draft)', imaplib.Time2Internaldate(time.time()), msg_bytes)
            if res != 'OK':
                return f"Error: IMAP APPEND failed: {res} - {str(detail)}"
        except Exception as append_err:
            return f"Error: Exception during IMAP APPEND to '{draft_folder}': {str(append_err)}"
            
        imap.logout()
        return "OK"
    except Exception as e:
        return f"Error: {str(e)}"


def find_chrome_profile_for_email(email: str) -> str:
    """Attempt to find the Chrome profile name associated with a specific email."""
    if not email:
        return "Default"
    
    system = platform.system()
    if system == "Windows":
        base_path = os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data")
    elif system == "Darwin":
        base_path = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        base_path = os.path.expanduser("~/.config/google-chrome")

    if not os.path.exists(base_path):
        return "Default"

    try:
        profiles = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and (d == "Default" or d.startswith("Profile"))]
        
        for profile in profiles:
            pref_path = os.path.join(base_path, profile, "Preferences")
            if os.path.exists(pref_path):
                try:
                    with open(pref_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if email.lower() in content.lower():
                            return profile
                except Exception:
                    continue
    except Exception:
        pass
        
    return "Default"


def open_url_in_chrome_profile(url: str, email: str = None) -> bool:
    """Attempt to open a URL in a specific Chrome profile."""
    # Priority: 1. Explicitly configured directory, 2. Auto-discovered directory, 3. Default
    profile = getattr(settings, 'CHROME_PROFILE_DIRECTORY', None)
    if not profile or profile == "Default":
        profile = find_chrome_profile_for_email(email)
    
    system = platform.system()
    
    try:
        if system == "Windows":
            # Common paths for Chrome on Windows
            chrome_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    subprocess.Popen([path, f"--profile-directory={profile}", url])
                    return True
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", "-a", "Google Chrome", "--args", f"--profile-directory={profile}", url])
            return True
        elif system == "Linux":
            subprocess.Popen(["google-chrome", f"--profile-directory={profile}", url])
            return True
    except Exception:
        pass
    
    # Fallback to default browser
    return webbrowser.open_new_tab(url)


def open_gmail_and_compose_tool(args: Dict[str, Any]) -> str:
    user = getattr(settings, 'GMAIL_SENDER_ADDRESS', '')
    recipient = args.get('recipient', '').strip()
    subject = args.get('subject', '')
    body = args.get('body', '')
    attachments = args.get('attachments', [])
    if not recipient:
        return "Error: recipient is required"

    if isinstance(attachments, str):
        attachments = [attachments]

    # Use user-specific URL if available
    base_url = f"https://mail.google.com/mail/u/{user}/" if user else "https://mail.google.com/mail/"

    # If there are attachments, we create a draft via IMAP because web URL doesn't support them
    if attachments:
        draft_result = create_gmail_draft(recipient, subject, body, attachments)
        if draft_result == "OK":
            drafts_url = f"{base_url}#drafts"
            try:
                opened = open_url_in_chrome_profile(drafts_url, user)
                if opened:
                    return f"A draft with the attachments has been created in your Gmail Drafts ({user}). I've opened your Drafts folder in the browser (Profile: {find_chrome_profile_for_email(user)}). Please review and send it."
                return f"A draft with the attachments has been created in your Gmail Drafts ({user}). Please open {drafts_url} to review and send it."
            except:
                return f"A draft with the attachments has been created in your Gmail Drafts ({user}). Please open {drafts_url} to review and send it."
        else:
            # If draft fails, we still want to open the compose window as a fallback
            fallback_msg = f"Failed to create draft with attachments: {draft_result}."
            
            query = [f"to={quote(recipient)}"]
            if subject:
                query.append(f"su={quote(subject)}")
            if body:
                query.append(f"body={quote(body)}")
            compose_url = f"{base_url}?view=cm&fs=1&tf=1&" + "&".join(query)
            
            try:
                opened = open_url_in_chrome_profile(compose_url, user)
                if opened:
                    return f"{fallback_msg} I've opened the standard compose window for you instead (Profile: {find_chrome_profile_for_email(user)}). Please attach the files manually and send."
                return f"{fallback_msg} Please open this link to compose manually: {compose_url}"
            except:
                return f"{fallback_msg} Please open this link to compose manually: {compose_url}"

    query = [f"to={quote(recipient)}"]
    if subject:
        query.append(f"su={quote(subject)}")
    if body:
        query.append(f"body={quote(body)}")
    compose_url = f"{base_url}?view=cm&fs=1&tf=1&" + "&".join(query)

    try:
        opened = open_url_in_chrome_profile(compose_url, user)
        if opened:
            return f"Gmail compose window for {user} opened in your browser (Profile: {find_chrome_profile_for_email(user)}). Log in if prompted, review the message, and press Send."
        return f"Open this link manually to compose the email: {compose_url}"
    except Exception as e:
        return f"Error launching browser automatically ({str(e)}). Open this link manually: {compose_url}"


def recognize_image_tool(args: Dict[str, Any]) -> str:
    """Use GPT-4o vision to recognize contents of an image (jpg, png)."""
    path = args.get('path', '')
    prompt = args.get('prompt', 'What is in this image? Provide a detailed description.')

    if not path or not os.path.exists(path):
        return f"Error: File '{path}' not found."

    try:
        # Read and encode image to base64
        with open(path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                    ],
                }
            ],
            max_tokens=500,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error during image recognition: {str(e)}"


def recognize_video_tool(args: Dict[str, Any]) -> str:
    """Use GPT-4o vision to recognize contents of a video (mp4) by extracting frames."""
    path = args.get('path', '')
    prompt = args.get('prompt', 'These are frames from a video. What is happening? Provide a summary and details.')
    max_frames = args.get('max_frames', 10)

    if not path or not os.path.exists(path):
        return f"Error: File '{path}' not found."

    try:
        video = cv2.VideoCapture(path)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        
        if total_frames <= 0:
            return "Error: Could not read frames from video."

        # Sample frames evenly
        interval = max(1, total_frames // max_frames)
        base64_frames = []
        
        count = 0
        while video.isOpened():
            success, frame = video.read()
            if not success or len(base64_frames) >= max_frames:
                break
            
            if count % interval == 0:
                _, buffer = cv2.imencode(".jpg", frame)
                base64_frames.append(base64.b64encode(buffer).decode("utf-8"))
            
            count += 1
        
        video.release()

        if not base64_frames:
            return "Error: No frames extracted from video."

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        content = [{"type": "text", "text": prompt}]
        for base64_frame in base64_frames:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_frame}"
                }
            })

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_tokens=1000,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error during video recognition: {str(e)}"


def recognize_audio_tool(args: Dict[str, Any]) -> str:
    """Use GPT-4o to analyze and summarize an audio file, including speech, music, and sounds."""
    path = args.get('path', '')
    prompt = args.get('prompt', 'Analyze this audio file. Describe everything you hear: transcribe any speech, identify any music (genre, instruments, mood), and note any ambient or other sounds.')

    SUPPORTED_FORMATS = ('.wav', '.mp3', '.ogg', '.flac', '.webm', '.m4a', '.mp4', '.aac', '.wma', '.opus')

    if not path or not os.path.exists(path):
        return f"Error: File '{path}' not found."

    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        return f"Error: Unsupported audio format '{ext}'. Supported formats: {', '.join(SUPPORTED_FORMATS)}"

    converted_path = None
    try:
        # GPT-4o audio input only accepts wav and mp3; convert other formats
        if ext in ('.wav', '.mp3'):
            audio_path = path
            audio_format = ext[1:]  # strip the leading dot
        else:
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(path)
            converted_path = os.path.splitext(path)[0] + '_temp_converted.wav'
            audio_segment.export(converted_path, format='wav')
            audio_path = converted_path
            audio_format = 'wav'

        with open(audio_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode('utf-8')

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64_audio,
                                "format": audio_format
                            }
                        }
                    ],
                }
            ],
            max_tokens=1000,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error during audio recognition: {str(e)}"
    finally:
        if converted_path and os.path.exists(converted_path):
            os.remove(converted_path)

SEARCH_FILE_DEFINITION = ToolDefinition(
    name="search_file",
    description="Search for a file by name across common directories (Desktop, Documents, Downloads, Pictures, etc.) and return its absolute path.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The name of the file to search for (e.g., 'my meetings.png')."
            }
        },
        "required": ["filename"]
    },
    function=search_file_tool
)


# Define the read_file tool
READ_FILE_DEFINITION = ToolDefinition(
    name="read_file",
    description="Read the contents of a given file path (absolute or relative). Use this when you want to see what's inside a file. Do not use this with directory names.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path of a file."
            },
            "offset": {
                "type": "integer",
                "description": "The character offset to start reading from."
            },
            "limit": {
                "type": "integer",
                "description": "The maximum number of characters to read."
            }
        },
        "required": ["path"]
    },
    function=read_file_tool
)

# Define the list_files tool
LIST_FILES_DEFINITION = ToolDefinition(
    name="list_files",
    description="List files and directories at a given path (absolute or relative). If no path is provided, lists files in the current directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional absolute or relative path to list files from. Defaults to current directory if not provided."
            }
        },
        "required": []
    },
    function=list_files_tool
)


DELETE_FILE_DEFINITION = ToolDefinition(
    name="delete_file",
    description="Delete a file or directory at any path (absolute or relative).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path of the file or directory to delete."
            }
        },
        "required": ["path"]
    },
    function=delete_file_tool,
    requires_approval=True
)


# Define the edit_file tool
CREATE_AND_EDIT_FILE_DEFINITION = ToolDefinition(
    name="create_and_edit_file",
    description="""Create or edit any file at any path (absolute or relative) by replacing old_str with new_str, or writing new_str if the file does not exist. Supports all file types, including code files such as .cpp, .py, .js, etc. IMPORTANT: Always provide the full code with proper indentation and newlines. Avoid writing code in a single line.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path to the file (any file type allowed)"
            },
            "old_str": {
                "type": "string",
                "description": "Text to search for - must match exactly and must only have one match exactly. If you want to replace the entire file content, you can first read it and then provide it here, or use old_str='' to overwrite/create."
            },
            "new_str": {
                "type": "string",
                "description": "Text to replace old_str with, or to write if creating a new file. Ensure you use actual newline characters (\\n) and proper indentation for code files."
            }
        },
        "required": ["path", "old_str", "new_str"]
    },
    function=create_and_edit_file_tool,
    requires_approval=True
)

GITHUB_CREATE_BRANCH_DEFINITION = ToolDefinition(
    name="github_create_branch",
    description="Step 1 of 3: Create a new branch on the configured GitHub repository. Call this FIRST before committing files or creating a PR. Do NOT use run_code with git for GitHub operations — use these MCP tools instead.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the new branch"},
            "source": {"type": "string", "description": "Branch to create from (default: main)"}
        },
        "required": ["name"]
    },
    function=github_create_branch_tool,
    requires_approval=True
)

GITHUB_COMMIT_FILE_DEFINITION = ToolDefinition(
    name="github_commit_file",
    description="Step 2 of 3: Commit a file with given content to a branch on the configured GitHub repository. Use when file content is provided in the prompt. Call AFTER github_create_branch, BEFORE github_create_pr.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path in the repo"},
            "content": {"type": "string", "description": "Full file content to commit"},
            "message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Target branch"}
        },
        "required": ["path", "content", "message", "branch"]
    },
    function=github_commit_file_tool,
    requires_approval=True
)

GITHUB_COMMIT_LOCAL_FILE_DEFINITION = ToolDefinition(
    name="github_commit_local_file",
    description="Step 2 of 3: Read a local file and commit it to a branch on the configured GitHub repository. Use when committing an existing local file. Call AFTER github_create_branch, BEFORE github_create_pr.",
    parameters={
        "type": "object",
        "properties": {
            "local_path": {"type": "string", "description": "Local file path to read"},
            "message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Target branch"},
            "remote_path": {"type": "string", "description": "Path in repo (defaults to filename)"}
        },
        "required": ["local_path", "message", "branch"]
    },
    function=github_commit_local_file_tool,
    requires_approval=True
)

GITHUB_MCP_DEFINITION = ToolDefinition(
    name="github_create_pr",
    description="Step 3 of 3: Create a GitHub pull request on the configured repository. ONLY call this AFTER a branch has been created (github_create_branch) and at least one file committed to it (github_commit_file or github_commit_local_file). Do NOT use run_code with git for any GitHub operations.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Title for the pull request"},
            "head": {"type": "string", "description": "The source branch with changes"},
            "base": {"type": "string", "description": "The target branch (default: main)"},
            "body": {"type": "string", "description": "Pull request description"}
        },
        "required": ["title", "head"]
    },
    function=github_create_pr_tool,
    requires_approval=True
)


CREATE_GITHUB_ISSUE_DEFINITION = ToolDefinition(
    name="create_github_issue",
    description="Create a GitHub issue on the configured repository. Use this to track bugs, feature requests, tasks, or automatically create tickets when code execution fails or tests fail. Issues can be labeled and assigned.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the issue (required). Keep it concise and descriptive."
            },
            "body": {
                "type": "string",
                "description": "The body/description of the issue. Supports markdown formatting. Include error details, stack traces, reproduction steps, etc."
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional array of label names to apply (e.g., ['bug', 'high-priority', 'test-failure'])."
            },
            "assignees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional array of GitHub usernames to assign the issue to."
            }
        },
        "required": ["title"]
    },
    function=create_github_issue_tool,
    requires_approval=True
)


PLAYWRIGHT_MCP_DEFINITION = ToolDefinition(
    name="playwright_navigate",
    description="Navigate websites using Playwright MCP server",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "screenshot": {"type": "string"}
        },
        "required": ["url"]
    },
    function=playwright_mcp_tool,
    requires_approval=True
)


# ─── Travel Search Tools ─────────────────────────────────────────────

def _launch_travel_browser():
    """
    Launch a headless Chromium browser via sync_playwright with
    anti-detection settings suitable for interacting with Google
    Flights / Hotels.

    Returns (playwright_instance, browser, context, page).
    The caller MUST close browser and stop playwright when done.
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()

    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
    )

    # Block heavy resources to speed up loading
    context.route(
        re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|woff2?|ttf|otf|mp4|webm)$", re.I),
        lambda route: route.abort(),
    )

    page = context.new_page()

    # Remove the webdriver navigator flag that sites use to detect automation
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
    """)

    return pw, browser, context, page


def _dismiss_consent_banners(page):
    """Try to dismiss Google consent / cookie banners."""
    for sel in [
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Reject all')",
    ]:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(1000)
                break
        except Exception:
            continue


def _parse_flights_from_text(body, origin, destination, dep_date):
    """
    Parse raw body text from Google Flights into structured flight dicts.
    Anchors on price lines ($XXX) and walks backwards to extract
    airline, times, duration, stops, and route codes.
    """
    def _to_24h(t):
        if not t:
            return ""
        t = t.strip().upper()
        m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", t)
        if not m:
            return ""
        h, mi, ap = int(m[1]), int(m[2]), m[3]
        if ap == "PM" and h != 12:
            h += 12
        if ap == "AM" and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}"

    def _dur_to_display(text):
        m = re.search(r"(\d+)\s*h(?:r|our)?s?\s*(?:(\d+)\s*m(?:in)?)?", text, re.I)
        if not m:
            m2 = re.search(r"(\d+)\s*m(?:in)?", text, re.I)
            if m2:
                total = int(m2[1])
                return f"{total // 60}h {total % 60}m"
            return ""
        h = m[1]
        mi = m[2] or "0"
        return f"{h}h {mi}m"

    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    flights = []
    i = 0

    while i < len(lines):
        price_match = re.match(r"^\$[\d,]+$", lines[i])
        if not price_match:
            i += 1
            continue

        price = lines[i].replace("$", "").replace(",", "")
        window = lines[max(0, i - 12): i]
        window_text = "\n".join(window)

        # Time pattern: "5:00 AM – 1:30 PM"
        time_m = re.search(
            r"(\d{1,2}:\d{2}\s*[AP]M)\s*[\u2013\-\u2014]+\s*(\d{1,2}:\d{2}\s*[AP]M)",
            window_text, re.I
        )
        dep_time = _to_24h(time_m[1]) if time_m else ""
        arr_time = _to_24h(time_m[2]) if time_m else ""

        duration = _dur_to_display(window_text)

        nonstop = bool(re.search(r"non\s*-?\s*stop", window_text, re.I))
        stops_m = re.search(r"(\d+)\s+stop", window_text, re.I)
        stops = 0 if nonstop else (int(stops_m[1]) if stops_m else 0)

        airline = "Airline"
        for ln in window:
            if (
                len(ln) > 2
                and len(ln) < 50
                and not re.search(r"[\$\d]{2}", ln)
                and "\u2013" not in ln and "-" not in ln
                and "stop" not in ln.lower()
                and "hr" not in ln.lower()
                and "min" not in ln.lower()
                and "AM" not in ln
                and "PM" not in ln
            ):
                airline = ln
                break

        route_m = re.search(r"([A-Z]{3})\s*[\u2013\-\u2014]\s*([A-Z]{3})", window_text)
        dep_apt = route_m[1] if route_m else origin.upper()
        arr_apt = route_m[2] if route_m else destination.upper()

        flights.append({
            'price': price,
            'currency': 'USD',
            'airline': airline,
            'departure_time': dep_time,
            'arrival_time': arr_time,
            'departure_airport': dep_apt,
            'arrival_airport': arr_apt,
            'duration': duration,
            'stops': stops,
        })

        i += 1

    # De-duplicate by price + airline
    seen = set()
    unique = []
    for f in flights:
        key = (f["price"], f["airline"])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique



# Currency symbols and codes that Google Hotels may use depending on locale
_CURRENCY_SYMBOLS = {
    '$': 'USD', '\u20b9': 'INR', '\u20ac': 'EUR', '\u00a3': 'GBP',
    '\u00a5': 'JPY', '\u20a9': 'KRW', 'R$': 'BRL', 'A$': 'AUD',
    'C$': 'CAD', 'HK$': 'HKD', 'S$': 'SGD', '\u20b1': 'PHP',
    '\u20ba': 'TRY', '\u20bd': 'RUB', 'kr': 'SEK', 'zł': 'PLN',
    '\u20aa': 'ILS', '\u0e3f': 'THB', 'RM': 'MYR', 'Rp': 'IDR',
}

# Regex pattern that matches any common currency symbol followed by a number
_PRICE_PATTERN = re.compile(
    r'(?:R\$|A\$|C\$|HK\$|S\$|[$\u20b9\u20ac\u00a3\u00a5\u20a9\u20b1\u20ba\u20bd\u20aa\u0e3f]|kr|z[łl]|RM|Rp)\s?(\d[\d,]*)'
)


def _detect_currency(body):
    """Detect the currency used on the page by finding the most common currency symbol."""
    counts = {}
    for sym in _CURRENCY_SYMBOLS:
        c = body.count(sym)
        if c > 0:
            counts[sym] = c
    if not counts:
        return '$', 'USD'
    best_sym = max(counts, key=counts.get)
    return best_sym, _CURRENCY_SYMBOLS[best_sym]


def _parse_hotels_from_text(body, city_code, check_in, check_out):
    """
    Parse raw body text from Google Hotels into structured hotel dicts.
    Handles multiple currencies ($, ₹, €, £, ¥, etc.) and price formats
    like "$189", "₹7,665", "€150/night", "From $189", etc.
    """
    currency_sym, currency_code = _detect_currency(body)

    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    hotels = []
    i = 0

    while i < len(lines):
        # Match prices with any currency symbol
        price_m = _PRICE_PATTERN.search(lines[i])
        if not price_m:
            i += 1
            continue

        # Skip lines that are clearly not hotel prices
        line_lower = lines[i].lower()
        if any(skip in line_lower for skip in ['tax', 'fee', 'off', 'save', 'was ', 'cancel']):
            i += 1
            continue

        price = price_m.group(1).replace(",", "")

        # Skip very small prices (likely fees, not hotel rates)
        try:
            if int(price) < 20:
                i += 1
                continue
        except ValueError:
            i += 1
            continue

        window = lines[max(0, i - 10): i]
        window_text = "\n".join(window)

        # Hotel name - find a line that looks like an actual hotel name,
        # skipping amenity/feature lines that Google shows between name and price
        _amenity_keywords = {
            'wi-fi', 'wifi', 'breakfast', 'parking', 'pool', 'spa',
            'gym', 'fitness', 'restaurant', 'bar', 'lounge',
            'kid-friendly', 'kid friendly', 'pet-friendly', 'pet friendly',
            'free cancellation', 'free wi-fi', 'free wifi', 'free parking',
            'free breakfast', 'air conditioning', 'air-conditioning',
            'kitchen', 'laundry', 'shuttle', 'concierge', 'room service',
            'balcony', 'terrace', 'garden', 'beach', 'rooftop',
            'accessible', 'wheelchair', 'no smoking', 'non-smoking',
            'ev charger', 'ev charging', 'outdoor', 'indoor',
            'hot tub', 'sauna', 'jacuzzi', 'minibar',
            'check-in', 'check-out', 'checkout', 'checkin',
        }
        name = "Hotel"
        for ln in window:
            ln_lower = ln.lower().strip()
            # Skip amenity/feature lines
            if any(kw in ln_lower for kw in _amenity_keywords):
                continue
            if (
                len(ln) > 3
                and len(ln) < 80
                and not re.match(r"^[\d\.\$\(\),\s]+$", ln)
                and not _PRICE_PATTERN.search(ln)
                and "star" not in ln_lower
                and "rating" not in ln_lower
                and "review" not in ln_lower
                and "night" not in ln_lower
                and "price" not in ln_lower
                and "deal" not in ln_lower
                and "sponsored" not in ln_lower
                and "amenit" not in ln_lower
                and "facilit" not in ln_lower
                and not re.match(r"^\d[\.\d]*$", ln)
                and not re.match(r"^\([\d,]+\)$", ln)
            ):
                name = ln
                break

        # Star rating
        star_m = re.search(r"(\d)[- ]star", window_text, re.I)
        rating = star_m[1] if star_m else ""

        hotels.append({
            'name': name,
            'rating': rating,
            'price': price,
            'currency': currency_code,
        })

        i += 1

    # De-duplicate by name
    seen = set()
    unique = []
    for h in hotels:
        if h["name"] not in seen:
            seen.add(h["name"])
            unique.append(h)

    return unique


def search_flights_tool(args: Dict[str, Any]) -> str:
    """Search for flights by interacting with Google Flights via Playwright."""

    origin = args.get('origin', '').strip()
    destination = args.get('destination', '').strip()
    departure_date = args.get('departure_date', '').strip()
    return_date = args.get('return_date', '').strip() if args.get('return_date') else ''
    adults = int(args.get('adults', 1))

    if not origin or not destination or not departure_date:
        return "Error: origin, destination, and departure_date are required."

    pw = browser = None
    try:
        pw, browser, ctx, page = _launch_travel_browser()

        # Strategy A: URL-based approach (most reliable)
        query_parts = f"flights from {origin} to {destination} on {departure_date}"
        if return_date:
            query_parts += f" return {return_date}"
        url = (
            "https://www.google.com/travel/flights?q="
            + query_parts.replace(" ", "+")
            + "&curr=USD"
        )

        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)

        _dismiss_consent_banners(page)
        page.wait_for_timeout(2000)

        body_text = page.inner_text("body")

        # Strategy B: If URL approach yields no results, try form interaction
        if not re.search(r'\$\d+', body_text):
            page.goto("https://www.google.com/travel/flights", timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            _dismiss_consent_banners(page)

            # Fill origin field
            try:
                from_input = page.locator('[aria-label*="Where from"], [aria-label*="departure"], [placeholder*="Where from"]').first
                from_input.click()
                page.wait_for_timeout(500)
                page.keyboard.press("Control+a")
                page.keyboard.type(origin, delay=80)
                page.wait_for_timeout(1000)
                page.keyboard.press("Enter")
                page.wait_for_timeout(800)
            except Exception:
                pass

            # Fill destination field
            try:
                to_input = page.locator('[aria-label*="Where to"], [aria-label*="destination"], [placeholder*="Where to"]').first
                to_input.click()
                page.wait_for_timeout(500)
                page.keyboard.type(destination, delay=80)
                page.wait_for_timeout(1000)
                page.keyboard.press("Enter")
                page.wait_for_timeout(800)
            except Exception:
                pass

            # Fill departure date
            try:
                dep_date_input = page.locator('[aria-label*="Departure"], [data-placeholder*="Departure"]').first
                dep_date_input.click()
                page.wait_for_timeout(500)
                page.keyboard.type(departure_date, delay=50)
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Fill return date if provided
            if return_date:
                try:
                    ret_date_input = page.locator('[aria-label*="Return"], [data-placeholder*="Return"]').first
                    ret_date_input.click()
                    page.wait_for_timeout(500)
                    page.keyboard.type(return_date, delay=50)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(500)
                except Exception:
                    pass

            # Click Search button
            try:
                search_btn = page.locator('button:has-text("Search"), button:has-text("Explore"), button[aria-label*="Search"]').first
                search_btn.click()
                page.wait_for_timeout(8000)
            except Exception:
                pass

            body_text = page.inner_text("body")

        # Parse results
        flights = _parse_flights_from_text(body_text, origin, destination, departure_date)

        if not flights:
            return (
                f"No flights found from {origin.upper()} to {destination.upper()} "
                f"on {departure_date}. Google may have blocked the automated search, "
                f"or no results are available for these dates."
            )

        flights.sort(key=lambda f: float(f.get('price', 9999)))

        lines = [
            f"Found {len(flights)} flight(s) from {origin.upper()} to "
            f"{destination.upper()} on {departure_date}:\n"
        ]
        for i, f in enumerate(flights[:15], 1):
            airline = f.get('airline', 'Unknown')
            dep_time = f.get('departure_time', '')
            arr_time = f.get('arrival_time', '')
            dep_apt = f.get('departure_airport', origin.upper())
            arr_apt = f.get('arrival_airport', destination.upper())
            stops = f.get('stops', 0)
            stops_text = 'Nonstop' if stops == 0 else f'{stops} stop{"s" if stops > 1 else ""}'
            duration = f.get('duration', '')
            price = f.get('price', '?')
            currency = f.get('currency', 'USD')

            lines.append(
                f"{i}. **{airline}** | {dep_apt} {dep_time} \u2192 {arr_apt} {arr_time} | "
                f"{duration} | {stops_text} | **${price} {currency}**"
            )

        return '\n'.join(lines)

    except Exception as exc:
        return f"Flight search error: {exc}"
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass


SEARCH_FLIGHTS_DEFINITION = ToolDefinition(
    name="search_flights",
    description=(
        "Search for flight offers between airports. Returns a list of available flights with "
        "airlines, times, duration, stops, and prices. Use IATA airport codes (e.g. LAX, JFK, SYD). "
        "Dates must be in YYYY-MM-DD format."
    ),
    parameters={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin IATA airport code (e.g. 'LAX', 'SYD', 'LHR')."
            },
            "destination": {
                "type": "string",
                "description": "Destination IATA airport code (e.g. 'JFK', 'NRT', 'CDG')."
            },
            "departure_date": {
                "type": "string",
                "description": "Departure date in YYYY-MM-DD format."
            },
            "return_date": {
                "type": "string",
                "description": "Optional return date in YYYY-MM-DD format for round trips."
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers (default 1)."
            }
        },
        "required": ["origin", "destination", "departure_date"]
    },
    function=search_flights_tool,
    requires_approval=False
)



# Common IATA city codes to full city names for Google Hotels
_CITY_CODE_TO_NAME = {
    "NYC": "New York City", "LAX": "Los Angeles", "SFO": "San Francisco",
    "CHI": "Chicago", "MIA": "Miami", "LAS": "Las Vegas",
    "SEA": "Seattle", "BOS": "Boston", "DFW": "Dallas",
    "ATL": "Atlanta", "DEN": "Denver", "PHX": "Phoenix",
    "IAH": "Houston", "MSP": "Minneapolis", "DTW": "Detroit",
    "PHL": "Philadelphia", "CLT": "Charlotte", "SAN": "San Diego",
    "TPA": "Tampa", "MCO": "Orlando", "AUS": "Austin",
    "PDX": "Portland", "SLC": "Salt Lake City", "BNA": "Nashville",
    "LON": "London", "PAR": "Paris", "ROM": "Rome",
    "BCN": "Barcelona", "MAD": "Madrid", "BER": "Berlin",
    "AMS": "Amsterdam", "VIE": "Vienna", "PRG": "Prague",
    "LIS": "Lisbon", "DUB": "Dublin", "ZRH": "Zurich",
    "MIL": "Milan", "BRU": "Brussels", "CPH": "Copenhagen",
    "OSL": "Oslo", "STO": "Stockholm", "HEL": "Helsinki",
    "WAW": "Warsaw", "BUD": "Budapest", "ATH": "Athens",
    "IST": "Istanbul", "TYO": "Tokyo", "OSA": "Osaka",
    "SEL": "Seoul", "ICN": "Seoul", "PEK": "Beijing",
    "BJS": "Beijing", "SHA": "Shanghai", "HKG": "Hong Kong",
    "SIN": "Singapore", "BKK": "Bangkok", "KUL": "Kuala Lumpur",
    "DEL": "New Delhi", "BOM": "Mumbai", "SYD": "Sydney",
    "MEL": "Melbourne", "AKL": "Auckland", "DXB": "Dubai",
    "DOH": "Doha", "CAI": "Cairo", "JNB": "Johannesburg",
    "CPT": "Cape Town", "NBO": "Nairobi", "CAS": "Casablanca",
    "MEX": "Mexico City", "CUN": "Cancun", "BOG": "Bogota",
    "LIM": "Lima", "SCL": "Santiago", "GRU": "Sao Paulo",
    "EZE": "Buenos Aires", "YTO": "Toronto", "YVR": "Vancouver",
    "YMQ": "Montreal", "HAV": "Havana", "SJU": "San Juan",
    "HNL": "Honolulu", "JFK": "New York City", "LHR": "London",
    "CDG": "Paris", "NRT": "Tokyo", "FCO": "Rome",
    "FRA": "Frankfurt", "MUC": "Munich", "ORD": "Chicago",
}


def search_hotels_tool(args: Dict[str, Any]) -> str:
    """Search for hotels by interacting with Google Hotels via Playwright."""

    city_code = args.get('city_code', '').strip().upper()
    check_in = args.get('check_in', '').strip()
    check_out = args.get('check_out', '').strip()
    adults = int(args.get('adults', 1))
    rooms = int(args.get('rooms', 1))

    if not city_code or not check_in or not check_out:
        return "Error: city_code, check_in, and check_out are required."

    # Resolve IATA code to full city name for Google Hotels
    city_name = _CITY_CODE_TO_NAME.get(city_code, city_code)

    pw = browser = None
    try:
        pw, browser, ctx, page = _launch_travel_browser()

        # Strategy A: URL-based approach with proper Google Hotels parameters
        from urllib.parse import quote
        url = (
            f"https://www.google.com/travel/hotels/{quote(city_name)}"
            f"?q={quote(city_name + ' hotels')}"
            f"&hl=en-US&gl=us"
            f"&checkin={check_in}&checkout={check_out}"
            f"&curr=USD"
        )

        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        _dismiss_consent_banners(page)
        page.wait_for_timeout(2000)

        body_text = page.inner_text("body")

        # Strategy B: If no price patterns found, try form interaction
        if not _PRICE_PATTERN.search(body_text):
            page.goto("https://www.google.com/travel/hotels", timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            _dismiss_consent_banners(page)

            # Type full city name into the search field
            try:
                search_input = page.locator(
                    '[aria-label*="Search"], [aria-label*="destination"], '
                    '[placeholder*="Search"], input[type="text"]'
                ).first
                search_input.click()
                page.wait_for_timeout(500)
                page.keyboard.press("Control+a")
                page.keyboard.type(city_name, delay=80)
                page.wait_for_timeout(1500)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
            except Exception:
                pass

            # Fill check-in date
            try:
                checkin_input = page.locator('[aria-label*="Check-in"], [data-placeholder*="Check-in"]').first
                checkin_input.click()
                page.wait_for_timeout(500)
                page.keyboard.type(check_in, delay=50)
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Fill check-out date
            try:
                checkout_input = page.locator('[aria-label*="Check-out"], [data-placeholder*="Check-out"]').first
                checkout_input.click()
                page.wait_for_timeout(500)
                page.keyboard.type(check_out, delay=50)
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)
            except Exception:
                pass

            # Click search
            try:
                search_btn = page.locator('button:has-text("Search"), button:has-text("Explore")').first
                search_btn.click()
                page.wait_for_timeout(8000)
            except Exception:
                pass

            body_text = page.inner_text("body")

        # Parse results
        hotels = _parse_hotels_from_text(body_text, city_code, check_in, check_out)

        if not hotels:
            # Include a snippet of the page text for debugging
            snippet = body_text[:500].replace('\n', ' ').strip() if body_text else "(empty page)"
            return (
                f"No hotels found in {city_code.upper()} ({city_name}) for {check_in} to {check_out}. "
                f"Google may have blocked the automated search, or no results are available.\n\n"
                f"**Page preview:** {snippet}"
            )

        hotels.sort(key=lambda h: float(h.get('price', 9999)))

        lines = [
            f"Found {len(hotels)} hotel(s) in {city_code.upper()} "
            f"({check_in} to {check_out}):\n"
        ]
        for i, h in enumerate(hotels[:15], 1):
            name = h.get('name', 'Unknown Hotel')
            rating = h.get('rating', '')
            stars_text = f' {"*" * int(rating)}' if rating else ''
            price = h.get('price', '?')
            currency = h.get('currency', 'USD')
            sym = next((s for s, c in _CURRENCY_SYMBOLS.items() if c == currency), '$')

            lines.append(
                f"{i}. **{name}**{stars_text} | **{sym}{price} {currency}** total"
            )

        return '\n'.join(lines)

    except Exception as exc:
        return f"Hotel search error: {exc}"
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass


SEARCH_HOTELS_DEFINITION = ToolDefinition(
    name="search_hotels",
    description=(
        "Search for hotel offers in a city. Returns a list of available hotels with "
        "names, star ratings, prices, and room details. Use IATA city codes (e.g. NYC, LON, PAR). "
        "Dates must be in YYYY-MM-DD format."
    ),
    parameters={
        "type": "object",
        "properties": {
            "city_code": {
                "type": "string",
                "description": "IATA city code (e.g. 'NYC', 'LON', 'PAR', 'SYD')."
            },
            "check_in": {
                "type": "string",
                "description": "Check-in date in YYYY-MM-DD format."
            },
            "check_out": {
                "type": "string",
                "description": "Check-out date in YYYY-MM-DD format."
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult guests (default 1)."
            },
            "rooms": {
                "type": "integer",
                "description": "Number of rooms (default 1)."
            }
        },
        "required": ["city_code", "check_in", "check_out"]
    },
    function=search_hotels_tool,
    requires_approval=False
)


def book_travel_tool(args: Dict[str, Any]) -> str:
    """Create a mock travel booking (flight or hotel) and return a confirmation.
    No database storage -- generates a UUID reference in memory."""

    booking_type = args.get('booking_type', '')
    passenger_name = args.get('passenger_name', '')
    passenger_email = args.get('passenger_email', '')
    total_price = args.get('total_price', 0)
    currency = args.get('currency', 'USD')

    # Payment fields
    card_last_four = args.get('card_last_four', '')
    card_holder_name = args.get('card_holder_name', '')

    # Flight-specific fields
    airline = args.get('airline', '')
    flight_number = args.get('flight_number', '')
    origin = args.get('origin', '')
    destination = args.get('destination', '')
    departure_date = args.get('departure_date', '')
    return_date = args.get('return_date', '')
    departure_time = args.get('departure_time', '')
    arrival_time = args.get('arrival_time', '')
    stops = args.get('stops', 0)
    duration = args.get('duration', '')
    booking_class = args.get('booking_class', 'ECONOMY')

    # Hotel-specific fields
    hotel_name = args.get('hotel_name', '')
    check_in = args.get('check_in', '')
    check_out = args.get('check_out', '')
    rating = args.get('rating', '')
    room_type = args.get('room_type', '')

    # Validation
    if not booking_type or booking_type not in ('flight', 'hotel'):
        return "Error: booking_type must be 'flight' or 'hotel'."
    if not passenger_name:
        return "Error: passenger_name is required."
    if not passenger_email:
        return "Error: passenger_email is required."
    if not total_price or float(total_price) <= 0:
        return "Error: total_price must be a positive number."
    if not card_last_four:
        return "Error: card_last_four is required for payment."

    # Generate a mock booking reference
    booking_ref = uuid.uuid4().hex[:10].upper()

    # Build confirmation message
    lines = [
        "## Booking Confirmed!",
        "",
        f"**Booking Reference:** `{booking_ref}`",
        f"**Status:** Confirmed",
        f"**Passenger:** {passenger_name} ({passenger_email})",
        f"**Payment:** Card ending in ****{card_last_four}",
    ]
    if card_holder_name:
        lines.append(f"**Card Holder:** {card_holder_name}")
    lines.append(f"**Type:** {booking_type.title()}")

    if booking_type == 'flight':
        lines.append(f"**Flight:** {airline} {flight_number}")
        lines.append(f"**Route:** {origin} \u2192 {destination}")
        if departure_time:
            lines.append(f"**Departure:** {departure_date} {departure_time}")
        if arrival_time:
            lines.append(f"**Arrival:** {arrival_time}")
        if duration:
            lines.append(f"**Duration:** {duration}")
        stops_int = int(stops) if stops else 0
        stops_text = 'Nonstop' if stops_int == 0 else f'{stops_int} stop{"s" if stops_int > 1 else ""}'
        lines.append(f"**Stops:** {stops_text}")
        lines.append(f"**Class:** {booking_class}")
    else:
        lines.append(f"**Hotel:** {hotel_name}")
        if rating:
            r = int(rating)
            filled = '\u2605' * r
            empty = '\u2606' * (5 - r)
            lines.append(f"**Rating:** {filled}{empty}")
        lines.append(f"**Dates:** {check_in} to {check_out}")
        if room_type:
            lines.append(f"**Room:** {room_type}")

    lines.append(f"**Total Price:** ${float(total_price):.2f} {currency}")
    lines.append("")
    lines.append("*This is a mock booking for demonstration purposes.*")

    return '\n'.join(lines)


BOOK_TRAVEL_DEFINITION = ToolDefinition(
    name="book_travel",
    description=(
        "Create a mock booking for a flight or hotel. Use this AFTER searching with "
        "search_flights or search_hotels. Extract the relevant details (airline, price, "
        "times, hotel name, etc.) from the search results.\n\n"
        "IMPORTANT - You MUST collect the passenger's booking details STEP BY STEP in this exact order. "
        "Ask ONE question at a time, wait for the user's response, then ask the next:\n"
        "  Step 1: Ask for the passenger's full name.\n"
        "  Step 2: Ask for their card details (card number, expiry date, and CVV). "
        "Store only the last 4 digits of the card number as card_last_four and the name on the card as card_holder_name.\n"
        "  Step 3: Ask for their email address.\n"
        "  Step 4: Only after collecting ALL the above, call this tool with the complete information.\n\n"
        "Do NOT ask for multiple details in the same message. Do NOT call this tool until all 3 steps are completed. "
        "Returns a booking confirmation with a unique reference code."
    ),
    parameters={
        "type": "object",
        "properties": {
            "booking_type": {
                "type": "string",
                "description": "Type of booking: 'flight' or 'hotel'."
            },
            "passenger_name": {
                "type": "string",
                "description": "Full name of the passenger (e.g. 'John Doe')."
            },
            "passenger_email": {
                "type": "string",
                "description": "Email address of the passenger."
            },
            "card_last_four": {
                "type": "string",
                "description": "Last 4 digits of the payment card number (e.g. '4242')."
            },
            "card_holder_name": {
                "type": "string",
                "description": "Name on the payment card."
            },
            "total_price": {
                "type": "number",
                "description": "Total price for the booking."
            },
            "currency": {
                "type": "string",
                "description": "Currency code (default 'USD')."
            },
            "airline": {
                "type": "string",
                "description": "Airline name (flights only)."
            },
            "flight_number": {
                "type": "string",
                "description": "Flight number (flights only)."
            },
            "origin": {
                "type": "string",
                "description": "Departure airport code (flights only)."
            },
            "destination": {
                "type": "string",
                "description": "Arrival airport code (flights only)."
            },
            "departure_date": {
                "type": "string",
                "description": "Departure date YYYY-MM-DD (flights only)."
            },
            "return_date": {
                "type": "string",
                "description": "Return date YYYY-MM-DD (flights only, if round trip)."
            },
            "departure_time": {
                "type": "string",
                "description": "Departure time e.g. '08:30' (flights only)."
            },
            "arrival_time": {
                "type": "string",
                "description": "Arrival time e.g. '14:45' (flights only)."
            },
            "stops": {
                "type": "integer",
                "description": "Number of stops (flights only)."
            },
            "duration": {
                "type": "string",
                "description": "Flight duration e.g. '5h 30m' (flights only)."
            },
            "booking_class": {
                "type": "string",
                "description": "Cabin class e.g. 'ECONOMY', 'BUSINESS' (flights only)."
            },
            "hotel_name": {
                "type": "string",
                "description": "Hotel name (hotels only)."
            },
            "check_in": {
                "type": "string",
                "description": "Check-in date YYYY-MM-DD (hotels only)."
            },
            "check_out": {
                "type": "string",
                "description": "Check-out date YYYY-MM-DD (hotels only)."
            },
            "rating": {
                "type": "string",
                "description": "Star rating e.g. '4' (hotels only)."
            },
            "room_type": {
                "type": "string",
                "description": "Room type/category (hotels only)."
            }
        },
        "required": ["booking_type", "passenger_name", "passenger_email", "card_last_four", "total_price"]
    },
    function=book_travel_tool,
    requires_approval=True
)


RENAME_FILE_DEFINITION = ToolDefinition(
    name="rename_file",
    description="Rename a file at any path (absolute or relative). Args: old_path (str), new_path (str).",
    parameters={
        "type": "object",
        "properties": {
            "old_path": {
                "type": "string",
                "description": "The current absolute or relative file path."
            },
            "new_path": {
                "type": "string",
                "description": "The new absolute or relative file path (with new extension/type)."
            }
        },
        "required": ["old_path", "new_path"]
    },
    function=rename_file_tool,
    requires_approval=True
)


RUN_CODE_DEFINITION = ToolDefinition(
    name="run_code",
    description="Execute a shell command or run a script (e.g., 'python script.py'). Use this to test code or perform system checks.",
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
    description="Check the syntax of a code file (supports .py and .java).",
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
    description="Run static analysis (linting) on a code file (supports .py and .java).",
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


OPEN_GMAIL_AND_COMPOSE_DEFINITION = ToolDefinition(
    name="open_gmail_and_compose",
    description="Open Gmail in a browser and compose an email. If attachments are provided, a draft will be created automatically for you to review and send.",
    parameters={
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Email address to populate in the compose window."
            },
            "subject": {
                "type": "string",
                "description": "Optional subject line to insert."
            },
            "body": {
                "type": "string",
                "description": "Optional body text to type into the message editor."
            },
            "attachments": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of absolute or relative file paths to be attached automatically via a draft. You have access to the entire filesystem."
            }
        },
        "required": ["recipient"]
    },
    function=open_gmail_and_compose_tool
)


RECOGNIZE_IMAGE_DEFINITION = ToolDefinition(
    name="recognize_image",
    description="Analyze the contents of an image (jpg, png) using GPT-4o vision. Provide a path and optional prompt.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the image file."
            },
            "prompt": {
                "type": "string",
                "description": "What you want to know about the image."
            }
        },
        "required": ["path"]
    },
    function=recognize_image_tool
)


RECOGNIZE_VIDEO_DEFINITION = ToolDefinition(
    name="recognize_video",
    description="Analyze the contents of a video (mp4) using GPT-4o vision by extracting frames. Provide a path and optional prompt.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the video file."
            },
            "prompt": {
                "type": "string",
                "description": "What you want to know about the video."
            },
            "max_frames": {
                "type": "integer",
                "description": "Maximum number of frames to extract and analyze (default 10)."
            }
        },
        "required": ["path"]
    },
    function=recognize_video_tool
)


RECOGNIZE_AUDIO_DEFINITION = ToolDefinition(
    name="recognize_audio",
    description="Analyze an audio file (wav, mp3, ogg, flac, webm, m4a, mp4, aac, wma, opus) using GPT-4o. Identifies and summarizes speech, music, and ambient sounds in the file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the audio file."
            },
            "prompt": {
                "type": "string",
                "description": "What you want to know about the audio. Default analyzes speech, music, and sounds."
            }
        },
        "required": ["path"]
    },
    function=recognize_audio_tool
)


FIND_FILE_BROADLY_DEFINITION = ToolDefinition(
    name="find_file_broadly",
    description="Search for a file by name across common directories and return its absolute path.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The name of the file to search for."
            }
        },
        "required": ["filename"]
    },
    function=find_file_broadly_tool
)


FIND_DIRECTORY_BROADLY_DEFINITION = ToolDefinition(
    name="find_directory_broadly",
    description="Search for a directory by name across common directories and return its absolute path.",
    parameters={
        "type": "object",
        "properties": {
            "dirname": {
                "type": "string",
                "description": "The name of the directory to search for."
            }
        },
        "required": ["dirname"]
    },
    function=find_directory_broadly_tool
)


CHANGE_WORKING_DIRECTORY_DEFINITION = ToolDefinition(
    name="change_working_directory",
    description="Change the current working directory of the agent to a different project or folder. Use this when you need to work on a different project that is located elsewhere on the system.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path to the new directory. If only a folder name is provided, the agent will attempt to find it in common project directories."
            }
        },
        "required": ["path"]
    },
    function=change_working_directory_tool,
    requires_approval=True
)


CREATE_PDF_DEFINITION = ToolDefinition(
    name="create_pdf",
    description="Create a PDF file with improved layout, structure, and diagrams. Supports custom title, introduction, and additional content.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The path and filename for the PDF file to create."
            },
            "title": {
                "type": "string",
                "description": "The title to display at the top of the PDF."
            },
            "introduction": {
                "type": "string",
                "description": "The introduction text to include in the PDF."
            },
            "content": {
                "type": "string",
                "description": "Additional content to include in the PDF."
            }
        },
        "required": ["filename"]
    },
    function=lambda args: create_pdf(
        args.get('filename'),
        args.get('title', "AI Agent Project Report"),
        args.get('introduction', "The AI Agent is a dynamic system built with Django framework, integrating advanced AI capabilities."),
        args.get('content', "")
    )
)


CREATE_DOCX_DEFINITION = ToolDefinition(
    name="create_docx",
    description="Create a DOCX file with improved layout, structure, and diagrams. Supports custom title, introduction, and additional content.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The path and filename for the DOCX file to create."
            },
            "title": {
                "type": "string",
                "description": "The title to display at the top of the document."
            },
            "introduction": {
                "type": "string",
                "description": "The introduction text to include in the document."
            },
            "content": {
                "type": "string",
                "description": "Additional content to include in the document."
            }
        },
        "required": ["filename"]
    },
    function=lambda args: create_docx(
        args.get('filename'),
        args.get('title', "AI Agent Project Report"),
        args.get('introduction', "The AI Agent is a dynamic system built with Django framework, integrating advanced AI capabilities."),
        args.get('content', "")
    )
)


CREATE_EXCEL_DEFINITION = ToolDefinition(
    name="create_excel",
    description="Create an XLSX file with improved layout, structure, and diagrams. Supports custom title and data.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The path and filename for the XLSX file to create."
            },
            "title": {
                "type": "string",
                "description": "The title to display at the top of the spreadsheet."
            },
            "data": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "description": "Array of arrays representing rows of data to include in the spreadsheet."
            }
        },
        "required": ["filename"]
    },
    function=lambda args: create_excel(
        args.get('filename'),
        args.get('title', "AI Agent Project Report"),
        args.get('data')
    )
)


CREATE_PPTX_DEFINITION = ToolDefinition(
    name="create_pptx",
    description="Create a PPTX file with improved layout, structure, and diagrams. Supports custom title and subtitle.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "The path and filename for the PPTX file to create."
            },
            "title": {
                "type": "string",
                "description": "The title for the presentation."
            },
            "subtitle": {
                "type": "string",
                "description": "The subtitle for the presentation."
            }
        },
        "required": ["filename"]
    },
    function=lambda args: create_pptx(
        args.get('filename'),
        args.get('title', "AI Agent Project"),
        args.get('subtitle', "Integration of advanced AI capabilities with Django")
    )
)


def create_pdf(filename: str, title: str = "AI Agent Project Report", introduction: str = "The AI Agent is a dynamic system built with Django framework, integrating advanced AI capabilities.", content: str = "") -> str:
    """Create a PDF file with improved layout, structure, and diagrams."""
    try:
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, height - 50, title)

        # Introduction
        c.setFont("Helvetica", 12)
        y_position = height - 100
        for line in introduction.split('\n'):
            c.drawString(50, y_position, line)
            y_position -= 15

        # Additional content
        if content:
            c.setFont("Helvetica", 10)
            y_position -= 20
            for line in content.split('\n'):
                if y_position < 50:
                    c.showPage()
                    y_position = height - 50
                c.drawString(50, y_position, line)
                y_position -= 12

        # Simple diagram (rectangle)
        c.setStrokeColorRGB(0, 0, 1)
        c.rect(50, 100, 200, 100)
        c.drawString(60, 180, "AI Agent Architecture")
        c.drawString(60, 160, "- Django Backend")
        c.drawString(60, 140, "- OpenAI Integration")
        c.drawString(60, 120, "- File Processing")

        c.save()
        return f"Successfully created PDF: {filename}"
    except Exception as e:
        return f"Error creating PDF: {str(e)}"


def create_docx(filename: str, title: str = "AI Agent Project Report", introduction: str = "The AI Agent is a dynamic system built with Django framework, integrating advanced AI capabilities.", content: str = "") -> str:
    """Create a DOCX file with improved layout, structure, and diagrams."""
    try:
        doc = Document()
        doc.add_heading(title, 0)

        doc.add_heading('Introduction', level=1)
        doc.add_paragraph(introduction)

        if content:
            doc.add_heading('Details', level=1)
            doc.add_paragraph(content)

        # Add a table
        table = doc.add_table(rows=1, cols=2)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Component'
        hdr_cells[1].text = 'Description'
        row_cells = table.add_row().cells
        row_cells[0].text = 'Django Framework'
        row_cells[1].text = 'Backend for web application'
        row_cells = table.add_row().cells
        row_cells[0].text = 'OpenAI API'
        row_cells[1].text = 'AI capabilities integration'

        doc.save(filename)
        return f"Successfully created DOCX: {filename}"
    except Exception as e:
        return f"Error creating DOCX: {str(e)}"


def create_excel(filename: str, title: str = "AI Agent Project Report", data: List[List[str]] = None) -> str:
    """Create an XLSX file with improved layout, structure, and diagrams."""
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"

        # Title
        ws['A1'] = title
        ws['A1'].font = ws['A1'].font.copy(bold=True, size=14)

        # Default data if not provided
        if not data:
            data = [
                ["Section", "Description"],
                ["Introduction", "The AI Agent integrates advanced AI capabilities with Django."],
                ["Features", "File creation, tool execution, AI chat"],
                ["Technologies", "Python, Django, OpenAI, ReportLab"]
            ]

        for row in data:
            ws.append(row)

        # Add some formatting
        from openpyxl.styles import Border, Side
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        for row in ws.iter_rows():
            for cell in row:
                cell.border = thin_border

        wb.save(filename)
        return f"Successfully created XLSX: {filename}"
    except Exception as e:
        return f"Error creating XLSX: {str(e)}"


def create_pptx(filename: str, title: str = "AI Agent Project", subtitle: str = "Integration of advanced AI capabilities with Django") -> str:
    """Create a PPTX file with improved layout, structure, and diagrams."""
    try:
        prs = Presentation()

        # Title slide
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        title_placeholder = slide.shapes.title
        subtitle_placeholder = slide.placeholders[1]
        title_placeholder.text = title
        subtitle_placeholder.text = subtitle

        # Content slide
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        title_shape.text = 'Key Features'
        tf = body_shape.text_frame
        tf.text = 'Advanced AI Integration'
        p = tf.add_paragraph()
        p.text = 'Django Backend'
        p.level = 1
        p = tf.add_paragraph()
        p.text = 'File Processing Tools'
        p.level = 1

        # Diagram slide (simple shapes)
        slide_layout = prs.slide_layouts[5]  # Blank slide
        slide = prs.slides.add_slide(slide_layout)
        shapes = slide.shapes
        shapes.title.text = 'Architecture Diagram'
        left = top = width = height = 1.5 * 914400  # Inches to EMU
        shape = shapes.add_shape(1, left, top, width, height)  # Rectangle
        shape.text = 'AI Agent System'

        prs.save(filename)
        return f"Successfully created PPTX: {filename}"
    except Exception as e:
        return f"Error creating PPTX: {str(e)}"


def is_prompt_injection(text: str) -> bool:
    """Detect potential prompt injection attempts using basic heuristics."""
    if not text:
        return False

    injection_patterns = [
        # Instruction override attempts
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?earlier\s+commands",
        r"system\s+override",
        r"new\s+instructions\s+follow",
        r"stop\s+being\s+an\s+assistant",
        r"you\s+must\s+now",

        # Privilege escalation prompts
        r"you\s+are\s+now\s+(an\s+)?admin",
        r"act\s+as\s+root",
        r"bypass\s+restrictions",
        r"enable\s+developer\s+mode",
        r"grant\s+(administrative|admin)\s+access",
        r"sudo\s+",
        r"execute\s+as\s+root"
    ]

    text_lower = text.lower()
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            return True

    return False


def main():
    # Configure OpenAI with API key
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Create the model with tools
    tools = [
        SEARCH_FILE_DEFINITION,
        READ_FILE_DEFINITION,
        LIST_FILES_DEFINITION,
        CREATE_AND_EDIT_FILE_DEFINITION,
        DELETE_FILE_DEFINITION,
        RENAME_FILE_DEFINITION,
        RUN_CODE_DEFINITION,
        CHECK_SYNTAX_DEFINITION,
        RUN_TESTS_DEFINITION,
        LINT_CODE_DEFINITION,
        OPEN_GMAIL_AND_COMPOSE_DEFINITION,
        RECOGNIZE_IMAGE_DEFINITION,
        RECOGNIZE_VIDEO_DEFINITION,
        RECOGNIZE_AUDIO_DEFINITION,
        FIND_FILE_BROADLY_DEFINITION,
        FIND_DIRECTORY_BROADLY_DEFINITION,
        CHANGE_WORKING_DIRECTORY_DEFINITION,
        CREATE_PDF_DEFINITION,
        CREATE_DOCX_DEFINITION,
        CREATE_EXCEL_DEFINITION,
        CREATE_PPTX_DEFINITION,
        GITHUB_CREATE_BRANCH_DEFINITION,
        GITHUB_COMMIT_FILE_DEFINITION,
        GITHUB_COMMIT_LOCAL_FILE_DEFINITION,
        GITHUB_MCP_DEFINITION,
        CREATE_GITHUB_ISSUE_DEFINITION,
        PLAYWRIGHT_MCP_DEFINITION,
        SEARCH_FLIGHTS_DEFINITION,
        BOOK_TRAVEL_DEFINITION,
        SEARCH_HOTELS_DEFINITION,
    ]
    model_name = 'gpt-4o'

    def get_user_message():
        try:
            line = input()
            return line, True
        except EOFError:
            return "", False

    agent = Agent(client, model_name, get_user_message, tools)
    try:
        agent.run()
    except Exception as e:
        print(f"Error: {str(e)}")


class Agent:
    def __init__(self, client, model_name, get_user_message, tools: List[ToolDefinition], max_history: int = 15):
        self.client = client
        self.model_name = model_name
        self.get_user_message = get_user_message
        self.tools = tools
        self.max_history = max_history
        self.control = AgentControlState()

        
        # Initialize tools for OpenAI usage
        self.openai_tools = self._convert_tools_to_openai_format()
        
        # System instruction for agentic behavior
        self.system_instruction = """
        You are an expert AI software engineer. When performing tasks:
        1. Always verify the state of the filesystem before and after your actions.
        2. If a tool returns an error, analyze the cause and try a different approach.
        3. Use the 'check_syntax', 'run_tests', and 'lint_code' tools to identify and fix errors:
           - Syntax Errors: Use 'check_syntax' to catch compile-time or parse errors.
           - Logical Errors: Use 'run_tests' to verify behavior against expectations.
           - Static Analysis: Use 'lint_code' to find code smells and potential bugs.
        4. Be concise but thorough.
        5. You have FULL ACCESS to the local filesystem using absolute or relative paths. Do not claim you cannot access or retrieve files; instead, use the provided tools (like 'read_file', 'list_files', or specifying paths in tool arguments) to interact with them.
        6. Use absolute or relative paths as provided. Default to the current working directory ('.') if no path is explicitly specified. Do not assume previous paths from history apply to new, unrelated tasks. If you need to switch to a different project or directory, use the 'change_working_directory' tool.
        7. If you cannot find a file or directory in the current directory, use the 'search_file' tool or simply use 'read_file', 'list_files', or 'create_and_edit_file' with the name; the system will automatically search common directories (Desktop, Documents, Pictures, projects, repos, etc.) for you.
        8. If 'read_file' indicates a file is an image, use 'recognize_image' to analyze its contents.
        9. When writing code inside any and all types of code files, write multi-line code and avoid single-line writes.
        10. Do not ask for permission to perform an action; just execute the necessary steps to complete the task.
        11. In your final summary, avoid using the words "Error" or "Exception" if the task was completed successfully, as these words are used for automated failure detection. Use words like "issue", "problem", or "fault" if you must refer to them.
        12. ALWAYS report the actual output from tool executions. Never hallucinate or skip reporting the execution results.
        13. If the user denies a tool call or action, explicitly state in your response that you could not finish the task because the user denied it.
        14. For ALL GitHub operations (creating branches, committing files, raising pull requests), use ONLY the github_create_branch, github_commit_file, github_commit_local_file, and github_create_pr MCP tools. NEVER use run_code with git commands for GitHub operations. The workflow is: Step 1: github_create_branch -> Step 2: github_commit_file or github_commit_local_file -> Step 3: github_create_pr.
        """

    def chat_once(self, conversation_history=None, message=None, use_pending=False):
        """
        Handle a single chat interaction for Django/API usage.

        Args:
            conversation_history: List of previous messages (optional)
            message: Single message string to process
            use_pending: If True the model's tool calls go through per-tool
                         approval (status="pending").  If False (the default,
                         used for every fresh user message) all tool calls are
                         collected into a single dry-run plan first.

        Returns:
            Dict containing status and response/tool info
        """
        try:
            # Reset stopped flag for new messages to allow continuation
            if message is not None:
                self.control.stopped = False

            if self.control.stopped:
                return {
                    "status": "stopped",
                    "response": "⛔ Agent execution was stopped."
                }

            messages = [
                {"role": "system", "content": self.system_instruction}
            ]
            
            # If we have conversation history, add it
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get('role')
                    # Skip existing system messages in history to avoid duplication
                    if role == 'system':
                        continue
                        
                    content = msg.get('content')
                    tool_calls = msg.get('tool_calls')
                    tool_call_id = msg.get('tool_call_id')
                    name = msg.get('name')
                    
                    # Construct message dict based on what's available
                    msg_dict = {"role": role}
                    if content is not None: msg_dict["content"] = content
                    if tool_calls: msg_dict["tool_calls"] = tool_calls
                    if tool_call_id: msg_dict["tool_call_id"] = tool_call_id
                    if name: msg_dict["name"] = name
                    
                    messages.append(msg_dict)
            
            # If a new message is provided, append it
            if message:
                if is_prompt_injection(message):
                    return {"status": "error", "message": "Security Warning: Potential prompt injection detected. Message blocked."}
                messages.append({"role": "user", "content": message})
            
            # Send the message and get response
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self._trim_messages(messages),
                tools=self.openai_tools,
                tool_choice="auto"
            )
            
            # Process the response and return the final text
            return self._process_response_for_api(response, messages, use_pending=use_pending)

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _process_response_for_api(self, response, messages, use_pending=False):
        """
        Process response for API usage - returns structured response.

        use_pending=False  →  dry-run mode: every tool call is collected into
                              a plan and returned as status="dry_run" without
                              executing anything.
        use_pending=True   →  per-tool mode: tools whose definition has
                              requires_approval=True are held as
                              status="pending"; all others execute immediately.
                              This is the mode used after the initial dry-run
                              plan has been approved.
        """
        try:
            if self.control.stopped:
                return {
                    "status": "stopped",
                    "response": "⛔ Execution stopped mid-response."
                }
            message = response.choices[0].message
            
            # Convert message to dict for storage/history
            message_dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            
            messages.append(message_dict)
            
            if message.tool_calls:
                if use_pending:
                    # --- per-tool approval mode (plan already approved) ---
                    pending_tools = []
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        tool_def = next((t for t in self.tools if t.name == function_name), None)
                        if tool_def and tool_def.requires_approval:
                            pending_tools.append({
                                "id": tool_call.id,
                                "name": function_name,
                                "arguments": function_args
                            })
                        else:
                            # Read-only / low-risk tool — execute immediately
                            result = self._execute_tool_by_name(function_name, function_args)
                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": result,
                            })

                    if pending_tools:
                        return {
                            "status": "pending",
                            "pending_tools": pending_tools,
                            "response": message.content or "Approve the next action:",
                            "history": messages
                        }

                    # All tools were low-risk and already executed; ask the model
                    # for a follow-up, staying in per-tool mode.
                    follow_up = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=self._trim_messages(messages),
                        tools=self.openai_tools,
                        tool_choice="auto"
                    )
                    return self._process_response_for_api(follow_up, messages, use_pending=True)

                else:
                    # --- dry-run mode (fresh task, nothing approved yet) ---
                    dry_run_plan = []
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        dry_run_plan.append({
                            "id": tool_call.id,
                            "name": function_name,
                            "arguments": function_args,
                            "summary": self._summarize_tool_call(function_name, function_args)
                        })

                    # Pull the most recent user message so the summary
                    # prompt is grounded in what was actually asked.
                    user_request = ""
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            user_request = msg.get("content", "")
                            break

                    return {
                        "status": "dry_run",
                        "dry_run_plan": dry_run_plan,
                        "response": self._generate_plan_summary(dry_run_plan, user_request),
                        "history": messages
                    }
                
            return {"status": "success", "response": message.content or "No response generated", "history": messages}
            
        except Exception as e:
            return {"status": "error", "message": f"Error processing response: {str(e)}"}

    def _summarize_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        """Return a one-line, human-readable description of a tool call for the dry-run plan."""
        summaries = {
            'read_file':                lambda a: f"Read file: {a.get('path', '')}",
            'list_files':               lambda a: f"List files in: {a.get('path', '.')}",
            'search_file':              lambda a: f"Search for file: {a.get('filename', '')}",
            'find_file_broadly':        lambda a: f"Find file: {a.get('filename', '')}",
            'find_directory_broadly':   lambda a: f"Find directory: {a.get('dirname', '')}",
            'create_and_edit_file':     lambda a: f"Edit/create file: {a.get('path', '')}",
            'delete_file':              lambda a: f"Delete: {a.get('path', '')}",
            'rename_file':              lambda a: f"Rename {a.get('old_path', '')} \u2192 {a.get('new_path', '')}",
            'run_code':                 lambda a: f"Run command: {a.get('command', '')}",
            'check_syntax':             lambda a: f"Check syntax of: {a.get('path', '')}",
            'run_tests':                lambda a: f"Run tests: {a.get('command', 'auto-detect')}",
            'lint_code':                lambda a: f"Lint: {a.get('path', '')}",
            'change_working_directory': lambda a: f"Change directory to: {a.get('path', '')}",
            'create_pdf':               lambda a: f"Create PDF: {a.get('filename', '')}",
            'create_docx':              lambda a: f"Create DOCX: {a.get('filename', '')}",
            'create_excel':             lambda a: f"Create Excel: {a.get('filename', '')}",
            'create_pptx':              lambda a: f"Create PPTX: {a.get('filename', '')}",
            'open_gmail_and_compose':   lambda a: f"Compose email to: {a.get('recipient', '')}",
            'recognize_image':          lambda a: f"Analyze image: {a.get('path', '')}",
            'recognize_video':          lambda a: f"Analyze video: {a.get('path', '')}",
            'recognize_audio':          lambda a: f"Analyze audio: {a.get('path', '')}",
            'github_create_branch':     lambda a: f"Create GitHub branch: {a.get('name', '')}",
            'github_commit_file':       lambda a: f"Commit to GitHub branch '{a.get('branch', '')}': {a.get('path', '')}",
            'github_commit_local_file': lambda a: f"Commit local file to GitHub branch '{a.get('branch', '')}': {a.get('local_path', '')}",
            'github_create_pr':         lambda a: f'Create GitHub PR: "{a.get("title", "")}"',
            'playwright_navigate':      lambda a: f"Navigate to: {a.get('url', '')}",
        }
        summarizer = summaries.get(name)
        return summarizer(args) if summarizer else f"Call '{name}' with: {json.dumps(args)}"

    def _generate_plan_summary(self, dry_run_plan: List[Dict[str, Any]], user_request: str = "") -> str:
        """Ask the model to produce a plain-English, start-to-finish summary
        of the dry-run plan.  The user's original request is included so the
        summary stays grounded.  Falls back to a generic string on any failure
        so the card still renders."""
        steps = "\n".join(
            f"{i + 1}. {step['summary']}  —  {step['name']}({json.dumps(step['arguments'])})"
            for i, step in enumerate(dry_run_plan)
        )
        user_ctx = f"The user asked: \"{user_request}\"\n\n" if user_request else ""

        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are about to execute an action plan on behalf of the user. "
                            "Summarise the plan below in 2-4 clear sentences of plain English. "
                            "Describe what will happen from start to finish and what the end "
                            "result will be. Do not repeat raw tool names or JSON — translate "
                            "everything into natural language."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"{user_ctx}Planned actions:\n\n{steps}\n\nSummarise what this plan will do:"
                    }
                ]
            )
            summary = resp.choices[0].message.content
            if summary and summary.strip():
                return summary.strip()
        except Exception as e:
            print(f"[dry_run] summary generation failed: {e}")

        return "Here is the planned action(s). Review and approve or deny before execution:"

    def execute_dry_run(self, dry_run_plan: List[Dict[str, Any]], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute every tool in an approved dry-run plan, then fetch the model follow-up.

        The follow-up is processed with use_pending=True so any further tool
        calls the model issues go through per-tool approval rather than
        surfacing as another dry-run round.
        """
        try:
            for tool_call in dry_run_plan:
                if self.control.stopped:
                    return {"status": "stopped", "response": "\u26d4 Agent execution was stopped."}

                result = self._execute_tool_by_name(tool_call['name'], tool_call['arguments'])
                history.append({
                    "tool_call_id": tool_call['id'],
                    "role": "tool",
                    "name": tool_call['name'],
                    "content": result,
                })

            follow_up = self.client.chat.completions.create(
                model=self.model_name,
                messages=self._trim_messages(history),
                tools=self.openai_tools,
                tool_choice="auto"
            )
            return self._process_response_for_api(follow_up, history, use_pending=True)
        except Exception as e:
            return {"status": "error", "message": f"Error executing dry run: {str(e)}"}

    def run(self):
        print("Chat with OpenAI (use 'ctrl-c' or type 'quit' to exit)")

        self.messages = [
            {"role": "system", "content": self.system_instruction}
        ]

        while True:
            if self.control.stopped:
                print("⛔ Agent execution stopped.")
                break

            print("\033[94mYou\033[0m: ", end="")
            user_input, ok = self.get_user_message()
            if not ok:
                break

            # Check for quit command
            if user_input.lower().strip() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            self.messages.append({"role": "user", "content": user_input})

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self._trim_messages(self.messages),
                    tools=self.openai_tools,
                    tool_choice="auto"
                )
                self._process_response_simple(response)
            except Exception as e:
                print(f"Error: {str(e)}")
                # Print more detailed error information
                import traceback
                print(f"Traceback: {traceback.format_exc()}")

    def _process_response_simple(self, response):
        """Simplified response processing for OpenAI."""
        try:
            message = response.choices[0].message
            self.messages.append(message)

            # Handle text response
            if message.content:
                print(f"\033[93mOpenAI\033[0m: {message.content}")

            # Handle tool calls
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    args_str = json.dumps(function_args).replace('\\\\n', '\\n').replace('\\n', '\n')
                    print(f"\033[92mtool\033[0m: {function_name}({args_str})")
                    
                    # Execute the tool
                    result = self._execute_tool_by_name(function_name, function_args)
                    
                    # Append tool response to messages
                    self.messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": result,
                    })

                # Get follow-up response from OpenAI
                try:
                    follow_up = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=self._trim_messages(self.messages),
                        tools=self.openai_tools,
                        tool_choice="auto"
                    )
                    self._process_response_simple(follow_up)
                except Exception as e:
                    print(f"Error processing follow-up: {str(e)}")
                    
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

    def _execute_tool_by_name(self, name, args):
        """Find and execute a tool by name."""
        if self.control.stopped:
            return "⛔ Agent execution stopped."

        if not self.control.tools_enabled:
            return "🔒 Tool execution disabled by kill switch."

        from chat.models import ToolLog
        args_str = json.dumps(args).replace('\\\\n', '\\n').replace('\\n', '\n')
        print(f"\033[96mTool Call:\033[0m {name}({args_str})")
        for tool in self.tools:
            if tool.name == name:
                try:
                    result = tool.function(args)
                    # Save log to database
                    ToolLog.objects.create(
                        tool_name=name,
                        input_args=json.dumps(args),
                        output_result=str(result)
                    )
                    return result
                except Exception as e:
                    error_msg = f"Error executing tool: {str(e)}"
                    # Save error log to database
                    ToolLog.objects.create(
                        tool_name=name,
                        input_args=json.dumps(args),
                        output_result=error_msg
                    )
                    return error_msg
        return f"Tool '{name}' not found"

    def _convert_tools_to_openai_format(self):
        """Convert tools to OpenAI format."""
        openai_tools = []
        for tool in self.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return openai_tools

    def _trim_messages(self, messages: List[Any]) -> List[Any]:
        """
        Trim message history to stay within token limits.
        Keeps the system message and ensures tool messages are not separated from their tool_calls.
        """
        if len(messages) <= self.max_history + 1:
            return messages
            
        system_message = messages[0] if messages[0].get("role") == "system" else None
        
        # Keep the most recent messages
        start_index = len(messages) - self.max_history
        
        # Ensure we don't start in the middle of a tool response sequence
        # A 'tool' role message MUST be preceded by an 'assistant' message with 'tool_calls'
        while start_index > 1 and messages[start_index].get("role") == "tool":
            start_index -= 1
            
        recent_messages = messages[start_index:]
        
        trimmed = []
        if system_message:
            trimmed.append(system_message)
        trimmed.extend(recent_messages)
        
        return trimmed

    def generate_code(self, task_description: str, language: str = "python", stepwise: bool = True) -> str:
        """
        Generate complex code using OpenAI with advanced prompt engineering.
        Args:
            task_description (str): Description of the code to generate.
            language (str): Programming language for the code.
            stepwise (bool): Whether to use a stepwise prompt for better results.
        Returns:
            str: Generated code.
        """
        if is_prompt_injection(task_description):
            return "Security Warning: Potential prompt injection detected in task description. Generation blocked."

        if stepwise:
            prompt = (
                f"""
                Write a complete, well-structured {language} program for the following task:
                {task_description}
                
                Please follow these steps:
                1. Start by outlining the main components or functions needed.
                2. Implement each component step by step, with clear comments.
                3. At the end, provide the full code in a single code block.
                4. Ensure the code is ready to run and includes all necessary parts (imports, main function, etc.).
                """
            )
        else:
            prompt = f"Write a complete {language} program for the following task: {task_description}"
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()


if __name__ == "__main__":
    main()