import os
import json
import shutil
from typing import Dict, Any
from agents.helpers import find_file_broadly, find_directory_broadly
from agents.control import ToolDefinition


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
