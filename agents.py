# SECURITY WARNING:
# The file tools below now accept absolute and relative paths.
# This allows reading, writing, deleting, and renaming files anywhere on the system
# that the process has permission for. Use with caution!

import os
import json
import webbrowser
import imaplib
import time
import re
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
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], function: Callable[[Dict[str, Any]], str]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function


def read_file_tool(args: Dict[str, Any]) -> str:
    """Read the contents of a given file path (absolute or relative)."""
    path = args.get('path', '')
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return content
    except UnicodeDecodeError:
        try:
            # Attempt to read the file in binary mode if it's not a text file
            with open(path, 'rb') as f:
                content = f.read()
            return content.decode('utf-8', errors='replace')  # Attempt to decode, replacing non-decodable bytes
        except Exception as e:
            return f"Error reading binary file: {str(e)}"
    except Exception as e:
        return f"General error reading file: {str(e)}"


def list_files_tool(args: Dict[str, Any]) -> str:
    """List files and directories at a given path (absolute or relative)."""
    try:
        path = args.get('path', '.')
        if not path:
            path = '.'

        files = []
        for root, dirs, filenames in os.walk(path):
            # Get relative path from the starting directory
            rel_root = os.path.relpath(root, path)

            # Add directories with trailing slash
            for dirname in dirs:
                if rel_root == '.':
                    files.append(f"{dirname}/")
                else:
                    files.append(f"{rel_root}/{dirname}/")

            # Add files
            for filename in filenames:
                if rel_root == '.':
                    files.append(filename)
                else:
                    files.append(f"{rel_root}/{filename}")

        # Remove duplicates and sort
        files = sorted(list(set(files)))

        return json.dumps(files)
    except Exception as e:
        return f"Error listing files: {str(e)}"


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
        return f"Failed to create file: {str(e)}"


def delete_file_tool(args: Dict[str, Any]) -> str:
    """Delete a file at any path (absolute or relative)."""
    try:
        file_path = args.get('path', '')
        if not file_path:
            return "Error: no file path provided"
        if not os.path.exists(file_path):
            return f"Error: file {file_path} does not exist"
        if os.path.isdir(file_path):
            return f"Error: {file_path} is a directory, not a file"
        os.remove(file_path)
        return f"Successfully deleted file {file_path}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"


def create_and_edit_file_tool(args: Dict[str, Any]) -> str:
    """Create or edit any file at any path (absolute or relative) by replacing old_str with new_str, or writing new_str if the file does not exist."""
    try:
        path = args.get('path', '')
        old_str = args.get('old_str', '')
        new_str = args.get('new_str', '')

        # Validate input parameters
        if not path or old_str == new_str:
            return "Error: invalid input parameters"

        # Try to read the existing file
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            # If file doesn't exist and old_str is empty, create new file
            if old_str == "":
                return create_new_file(path, new_str)
            else:
                return f"Error: file {path} not found"
        except Exception as e:
            return f"Error reading file: {str(e)}"

        # Replace old_str with new_str
        new_content = content.replace(old_str, new_str)

        # Check if replacement actually happened
        if content == new_content and old_str != "":
            return "Error: old_str not found in file"

        # Write the modified content back to file
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return "OK"
        except Exception as e:
            return f"Error writing file: {str(e)}"

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
        return f"Error renaming file: {str(e)}"


def run_code_tool(args: Dict[str, Any]) -> str:
    """Execute code in a sandboxed-like environment (local shell)."""
    import subprocess
    try:
        command = args.get('command', '')
        if not command:
            return "Error: no command provided"
        
        # Security: In a real sandboxed environment, we would restrict commands
        # For this research project, we allow local execution for testing
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing code: {str(e)}"


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
                    return f"Error reading attachment {path}: {str(file_err)}"
            else:
                return f"Error: Attachment file not found at {path}"

        # Connect to Gmail IMAP
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(user, password)
        except imaplib.IMAP4.error as auth_err:
            return f"Authentication failed. Please ensure: 1. Your GMAIL_PASSWORD in .env is a 16-character App Password. 2. IMAP is enabled. Original error: {str(auth_err)}"
        except Exception as conn_err:
            return f"Failed to connect to Gmail IMAP: {str(conn_err)}"

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
                return f"IMAP APPEND failed: {res} - {str(detail)}"
        except Exception as append_err:
            return f"Exception during IMAP APPEND to '{draft_folder}': {str(append_err)}"
            
        imap.logout()
        return "OK"
    except Exception as e:
        return f"Error creating draft: {str(e)}"


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
                webbrowser.open_new_tab(drafts_url)
                return f"A draft with the attachments has been created in your Gmail Drafts ({user}). I've opened your Drafts folder in the browser. Please review and send it."
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
                webbrowser.open_new_tab(compose_url)
                return f"{fallback_msg} I've opened the standard compose window for you instead. Please attach the files manually and send."
            except:
                return f"{fallback_msg} Please open this link to compose manually: {compose_url}"

    query = [f"to={quote(recipient)}"]
    if subject:
        query.append(f"su={quote(subject)}")
    if body:
        query.append(f"body={quote(body)}")
    compose_url = f"{base_url}?view=cm&fs=1&tf=1&" + "&".join(query)

    try:
        opened = webbrowser.open_new_tab(compose_url)
        if opened:
            return f"Gmail compose window for {user} opened in your browser. Log in if prompted, review the message, and press Send."
        return f"Open this link manually to compose the email: {compose_url}"
    except Exception as e:
        return f"Error launching browser automatically ({str(e)}). Open this link manually: {compose_url}"


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
    description="Delete a file at any path (absolute or relative).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path of the file to delete."
            }
        },
        "required": ["path"]
    },
    function=delete_file_tool
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
    function=create_and_edit_file_tool
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
    function=rename_file_tool
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
    function=run_code_tool
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


def main():
    # Configure OpenAI with API key
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Create the model with tools
    tools = [
        READ_FILE_DEFINITION, 
        LIST_FILES_DEFINITION, 
        CREATE_AND_EDIT_FILE_DEFINITION, 
        DELETE_FILE_DEFINITION, 
        RENAME_FILE_DEFINITION, 
        RUN_CODE_DEFINITION,
        OPEN_GMAIL_AND_COMPOSE_DEFINITION
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
    def __init__(self, client, model_name, get_user_message, tools: List[ToolDefinition]):
        self.client = client
        self.model_name = model_name
        self.get_user_message = get_user_message
        self.tools = tools
        
        # Initialize tools for OpenAI usage
        self.openai_tools = self._convert_tools_to_openai_format()
        
        # System instruction for agentic behavior
        self.system_instruction = """
        You are an expert AI software engineer. When performing tasks:
        1. Always verify the state of the filesystem before and after your actions.
        2. If a tool returns an error, analyze the cause and try a different approach.
        3. Use the 'run_code' tool to verify that any code you generate or edit is syntactically correct and performs as expected.
        4. Be concise but thorough.
        5. You have FULL ACCESS to the local filesystem using absolute or relative paths. Do not claim you cannot access or retrieve files; instead, use the provided tools (like 'read_file', 'list_files', or specifying paths in tool arguments) to interact with them.
        """

    def chat_once(self, conversation_history=None, message=None):
        """
        Handle a single chat interaction for Django/API usage.
        
        Args:
            conversation_history: List of previous messages (optional)
            message: Single message string to process
            
        Returns:
            String response from the model
        """
        try:
            messages = [
                {"role": "system", "content": self.system_instruction}
            ]
            
            # If we have conversation history, add it
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get('role')
                    content = msg.get('content')
                    # Convert Gemini-style history if needed
                    if not content and 'parts' in msg:
                        parts = msg.get('parts', [])
                        if parts and isinstance(parts[0], str):
                            content = parts[0]
                    
                    if role and content:
                        messages.append({"role": role, "content": content})
            
            # If a new message is provided, append it
            if message:
                messages.append({"role": "user", "content": message})
            
            # Send the message and get response
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.openai_tools,
                tool_choice="auto"
            )
            
            # Process the response and return the final text
            return self._process_response_for_api(response, messages)
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _process_response_for_api(self, response, messages):
        """
        Process response for API usage - returns final text response.
        """
        try:
            message = response.choices[0].message
            messages.append(message)
            
            responses = []
            if message.content:
                responses.append(message.content)
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute the tool
                    result = self._execute_tool_by_name(function_name, function_args)
                    
                    # Append tool response
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": result,
                    })
                
                # Get follow-up
                follow_up = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.openai_tools,
                    tool_choice="auto"
                )
                follow_up_text = self._process_response_for_api(follow_up, messages)
                responses.append(follow_up_text)
                
            return "\n".join(responses) if responses else "No response generated"
            
        except Exception as e:
            return f"Error processing response: {str(e)}"

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
                    messages=self.messages,
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
                        messages=self.messages,
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
        for tool in self.tools:
            if tool.name == name:
                try:
                    return tool.function(args)
                except Exception as e:
                    return f"Error executing tool: {str(e)}"
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