import os
import json
import google.generativeai as genai
from typing import Dict, List, Callable, Any
from django.conf import settings


class ToolDefinition:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], function: Callable[[Dict[str, Any]], str]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function


def read_file_tool(args: Dict[str, Any]) -> str:
    """Read the contents of a given relative file path."""
    try:
        path = args.get('path', '')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


def list_files_tool(args: Dict[str, Any]) -> str:
    """List files and directories at a given path."""
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
    """Create a new file with the given content."""
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
    """Delete a file in the current working directory by name."""
    try:
        filename = args.get('path', '')  # still using 'path' as param for consistency

        if not filename:
            return "Error: no filename provided"

        # Ensure only file name, not directory traversal
        if os.path.basename(filename) != filename:
            return "Error: only file names allowed, not paths"

        # Resolve to current working directory
        file_path = os.path.join(os.getcwd(), filename)

        if not os.path.exists(file_path):
            return f"Error: file {filename} does not exist in current directory"

        if os.path.isdir(file_path):
            return f"Error: {filename} is a directory, not a file"

        os.remove(file_path)
        return f"Successfully deleted file {filename}"

    except Exception as e:
        return f"Error deleting file: {str(e)}"



def edit_file_tool(args: Dict[str, Any]) -> str:
    """Make edits to a text file by replacing old_str with new_str."""
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


# Define the read_file tool
READ_FILE_DEFINITION = ToolDefinition(
    name="read_file",
    description="Read the contents of a given relative file path. Use this when you want to see what's inside a file. Do not use this with directory names.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The relative path of a file in the working directory."
            }
        },
        "required": ["path"]
    },
    function=read_file_tool
)

# Define the list_files tool
LIST_FILES_DEFINITION = ToolDefinition(
    name="list_files",
    description="List files and directories at a given path. If no path is provided, lists files in the current directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional relative path to list files from. Defaults to current directory if not provided."
            }
        },
        "required": []
    },
    function=list_files_tool
)


DELETE_FILE_DEFINITION = ToolDefinition(
    name="delete_file",
    description="Delete a file in the current working directory by filename.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The name of the file in the current working directory to delete."
            }
        },
        "required": ["path"]
    },
    function=delete_file_tool
)


# Define the edit_file tool
EDIT_FILE_DEFINITION = ToolDefinition(
    name="edit_file",
    description="""Make edits to a text file.

Replaces 'old_str' with 'new_str' in the given file. 'old_str' and 'new_str' MUST be different from each other.

If the file specified with path doesn't exist, it will be created.""",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the file"
            },
            "old_str": {
                "type": "string",
                "description": "Text to search for - must match exactly and must only have one match exactly"
            },
            "new_str": {
                "type": "string",
                "description": "Text to replace old_str with"
            }
        },
        "required": ["path", "old_str", "new_str"]
    },
    function=edit_file_tool
)


def main():
    # Configure Gemini with API key
    genai.configure(api_key=settings.GENAI_API_KEY)

    # Create the model with tools
    tools = [READ_FILE_DEFINITION, LIST_FILES_DEFINITION, EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION]
    model = genai.GenerativeModel('gemini-2.0-flash')

    def get_user_message():
        try:
            line = input()
            return line, True
        except EOFError:
            return "", False

    agent = Agent(model, get_user_message, tools)
    try:
        agent.run()
    except Exception as e:
        print(f"Error: {str(e)}")


class Agent:
    def __init__(self, model, get_user_message, tools: List[ToolDefinition]):
        self.model = model
        self.get_user_message = get_user_message
        self.tools = tools
        self.chat = None  # Store chat instance
        
        # Initialize tools for Django usage
        self.gemini_tools = self._convert_tools_to_gemini_format()
        self.model_with_tools = genai.GenerativeModel('gemini-2.0-flash', tools=self.gemini_tools)

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
            # Create a new chat session for each request to avoid state issues
            chat = self.model_with_tools.start_chat()
            
            # If we have conversation history, replay it
            if conversation_history:
                for msg in conversation_history[:-1]:  # All but the last message
                    if msg.get('role') == 'user':
                        parts = msg.get('parts', [])
                        if parts and isinstance(parts[0], str):
                            chat.send_message(parts[0])
                
                # Process the latest message
                latest_msg = conversation_history[-1]
                if latest_msg.get('role') == 'user':
                    parts = latest_msg.get('parts', [])
                    if parts and isinstance(parts[0], str):
                        message = parts[0]
            
            # If no message provided, return error
            if not message:
                return "No message provided"
            
            # Send the message and get response
            response = chat.send_message(message)
            
            # Process the response and return the final text
            return self._process_response_for_api(response, chat)
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _process_response_for_api(self, response, chat):
        """
        Process response for API usage - returns final text response.
        """
        try:
            collected_responses = []
            
            # Process the initial response
            collected_responses.extend(self._handle_single_response(response, chat))
            
            return "\n".join(collected_responses) if collected_responses else "No response generated"
            
        except Exception as e:
            return f"Error processing response: {str(e)}"
    
    def _handle_single_response(self, response, chat):
        """
        Handle a single response, executing function calls and collecting text responses.
        Returns a list of text responses.
        """
        responses = []
        
        try:
            if (hasattr(response, 'candidates') and response.candidates and 
                hasattr(response.candidates[0], 'content') and 
                hasattr(response.candidates[0].content, 'parts')):
                
                candidate = response.candidates[0]
                function_responses = []
                
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Execute the function call and collect response
                        func_response = self._execute_function_call(part.function_call)
                        function_responses.append(func_response)
                    elif hasattr(part, 'text') and part.text:
                        responses.append(part.text)
                
                # If we have function calls, send their responses back and get follow-up
                if function_responses:
                    try:
                        follow_up = chat.send_message(function_responses)
                        # Recursively process the follow-up response
                        follow_up_responses = self._handle_single_response(follow_up, chat)
                        responses.extend(follow_up_responses)
                    except Exception as e:
                        responses.append(f"Error processing function response: {str(e)}")
            
            elif hasattr(response, 'text'):
                responses.append(response.text)
            
        except Exception as e:
            responses.append(f"Error handling response: {str(e)}")
        
        return responses

    def run(self):
        print("Chat with Gemini (use 'ctrl-c' or type 'quit' to exit)")

        # Initialize chat with tools
        gemini_tools = self._convert_tools_to_gemini_format()
        model_with_tools = genai.GenerativeModel('gemini-2.0-flash', tools=gemini_tools)
        self.chat = model_with_tools.start_chat()

        while True:
            print("\033[94mYou\033[0m: ", end="")
            user_input, ok = self.get_user_message()
            if not ok:
                break

            # Check for quit command
            if user_input.lower().strip() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            try:
                response = self.chat.send_message(user_input)
                self._process_response_simple(response)
            except Exception as e:
                print(f"Error: {str(e)}")
                # Print more detailed error information
                import traceback
                print(f"Traceback: {traceback.format_exc()}")

    def _process_response_simple(self, response):
        """Simplified response processing."""
        try:
            # Handle function calls first
            if (hasattr(response, 'candidates') and response.candidates and 
                hasattr(response.candidates[0], 'content') and 
                hasattr(response.candidates[0].content, 'parts')):
                
                candidate = response.candidates[0]
                
                # Process function calls
                function_responses = []
                text_parts = []
                
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Execute the function call
                        func_response = self._execute_function_call(part.function_call)
                        function_responses.append(func_response)
                    elif hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                
                # Print any text response
                if text_parts:
                    print(f"\033[93mGemini\033[0m: {''.join(text_parts)}")
                
                # If we have function calls, send their responses back
                if function_responses:
                    try:
                        # Send function responses back to continue the conversation
                        follow_up = self.chat.send_message(function_responses)
                        # Process the follow-up response recursively
                        self._process_response_simple(follow_up)
                            
                    except Exception as e:
                        print(f"Error processing function response: {str(e)}")
                        import traceback
                        print(f"Traceback: {traceback.format_exc()}")
            
            elif hasattr(response, 'text'):
                print(f"\033[93mGemini\033[0m: {response.text}")
            else:
                print(f"\033[93mGemini\033[0m: No response generated")
                
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

    def _execute_function_call(self, function_call):
        """Execute a function call and return the response."""
        function_name = function_call.name
        function_args = {}

        # Extract arguments
        if hasattr(function_call, 'args'):
            function_args = dict(function_call.args)

        print(f"\033[92mtool\033[0m: {function_name}({json.dumps(function_args)})")

        # Find and execute the tool
        result = None
        for tool in self.tools:
            if tool.name == function_name:
                try:
                    result = tool.function(function_args)
                    break
                except Exception as e:
                    result = f"Error executing tool: {str(e)}"
                    break

        if result is None:
            result = f"Tool '{function_name}' not found"

        # Return the function response
        return genai.protos.Part(
            function_response=genai.protos.FunctionResponse(
                name=function_name,
                response={'result': result}
            )
        )

    def _convert_tools_to_gemini_format(self):
        """Convert tools to Gemini format."""
        gemini_tools = []
        for tool in self.tools:
            gemini_tools.append({
                'function_declarations': [{
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.parameters
                }]
            })
        return gemini_tools

    def execute_tool(self, function_call):
        """Legacy method - kept for compatibility."""
        function_name = function_call.name
        function_args = {}

        if hasattr(function_call, 'args'):
            function_args = dict(function_call.args)

        for tool in self.tools:
            if tool.name == function_name:
                try:
                    result = tool.function(function_args)
                    return genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_name,
                            response={'result': result}
                        )
                    )
                except Exception as e:
                    return genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_name,
                            response={'error': str(e)}
                        )
                    )

        return genai.protos.Part(
            function_response=genai.protos.FunctionResponse(
                name=function_name,
                response={'error': 'Tool not found'}
            )
        )


if __name__ == "__main__":
    main()