# SECURITY WARNING:
# The file tools below accept absolute and relative paths and searches files broadly in 
# common folders like 
# (Downloads, Documents, C:/Users/yourusername, C:/Users/yourusername/anysubfolder, Videos, Pictures, Pictures/Screeshots, 
# etc) if paths are not provided in the user prompts.
# This allows reading, writing, deleting, and renaming files anywhere on the system
# that the process has permission for. Use with caution!

import os
import langchain
import json
import base64
import webbrowser
import imaplib
import time
import re
import subprocess
import platform
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
        old_str = args.get('old_str', '')
        new_str = args.get('new_str', '')

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
    description="""Create or edit any file at any path (absolute or relative) by replacing old_str with new_str, or writing new_str if the file does not exist. Supports all file types, including code files such as .cpp, .py, .js, etc.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path to the file (any file type allowed)"
            },
            "old_str": {
                "type": "string",
                "description": "Text to search for - must match exactly and must only have one match exactly"
            },
            "new_str": {
                "type": "string",
                "description": "Text to replace old_str with, or to write if creating a new file"
            }
        },
        "required": ["path", "old_str", "new_str"]
    },
    function=create_and_edit_file_tool,
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
        FIND_FILE_BROADLY_DEFINITION,
        FIND_DIRECTORY_BROADLY_DEFINITION
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
        6. Use absolute or relative paths as provided. Default to the current working directory ('.') if no path is explicitly specified. Do not assume previous paths from history apply to new, unrelated tasks.
        7. If you cannot find a file or directory in the current directory, use the 'search_file' tool or simply use 'read_file', 'list_files', or 'create_and_edit_file' with the name; the system will automatically search common directories (Desktop, Documents, Pictures, etc.) for you.
        8. If 'read_file' indicates a file is an image, use 'recognize_image' to analyze its contents.
        9. Do not ask for permission to perform an action; just execute the necessary steps to complete the task.
        10. In your final summary, avoid using the words "Error" or "Exception" if the task was completed successfully, as these words are used for automated failure detection. Use words like "issue", "problem", or "fault" if you must refer to them.
        11. ALWAYS report the actual output from tool executions. Never hallucinate or skip reporting the execution results.
        """

    def chat_once(self, conversation_history=None, message=None):
        """
        Handle a single chat interaction for Django/API usage.
        
        Args:
            conversation_history: List of previous messages (optional)
            message: Single message string to process
            
        Returns:
            Dict containing status and response/tool info
        """
        try:
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
                messages.append({"role": "user", "content": message})
            
            # Send the message and get response
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self._trim_messages(messages),
                tools=self.openai_tools,
                tool_choice="auto"
            )
            
            # Process the response and return the final text
            return self._process_response_for_api(response, messages)
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _process_response_for_api(self, response, messages):
        """
        Process response for API usage - returns structured response.
        """
        try:
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
                pending_tools = []
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Check if tool requires approval
                    tool_def = next((t for t in self.tools if t.name == function_name), None)
                    if tool_def and tool_def.requires_approval:
                        pending_tools.append({
                            "id": tool_call.id,
                            "name": function_name,
                            "arguments": function_args
                        })
                    else:
                        # Execute the tool immediately if it doesn't require approval
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
                        "response": message.content or "I need your approval to perform the following actions:",
                        "history": messages
                    }
                
                # If all tools were executed (none were pending), get follow-up
                follow_up = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self._trim_messages(messages),
                    tools=self.openai_tools,
                    tool_choice="auto"
                )
                return self._process_response_for_api(follow_up, messages)
                
            return {"status": "success", "response": message.content or "No response generated", "history": messages}
            
        except Exception as e:
            return {"status": "error", "message": f"Error processing response: {str(e)}"}

    def run(self):
        print("Chat with OpenAI (use 'ctrl-c' or type 'quit' to exit)")

        self.messages = [
            {"role": "system", "content": self.system_instruction}
        ]

        while True:
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
                    
                    print(f"\033[92mtool\033[0m: {function_name}({json.dumps(function_args)})")
                    
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
        from chat.models import ToolLog
        print(f"\033[96mTool Call:\033[0m {name}({json.dumps(args)})")
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