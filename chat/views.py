import os
import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from decouple import config
from django.conf import settings
from utils import load_module_from_s3

# Configure OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Load Agent and tools dynamically
bucket_name = config('AWS_STORAGE_BUCKET_NAME', default=None)
s3_key = 'ai_agent/agents.py'  # Update if your file is in a subdirectory like 'scripts/agents.py'
agents_module = load_module_from_s3(bucket_name, s3_key)

Agent = agents_module.Agent
READ_FILE_DEFINITION = agents_module.READ_FILE_DEFINITION
SEARCH_FILE_DEFINITION = agents_module.SEARCH_FILE_DEFINITION
LIST_FILES_DEFINITION = agents_module.LIST_FILES_DEFINITION
CREATE_AND_EDIT_FILE_DEFINITION = agents_module.CREATE_AND_EDIT_FILE_DEFINITION
DELETE_FILE_DEFINITION = agents_module.DELETE_FILE_DEFINITION
RENAME_FILE_DEFINITION = agents_module.RENAME_FILE_DEFINITION
RUN_CODE_DEFINITION = agents_module.RUN_CODE_DEFINITION
CHECK_SYNTAX_DEFINITION = agents_module.CHECK_SYNTAX_DEFINITION
RUN_TESTS_DEFINITION = agents_module.RUN_TESTS_DEFINITION
LINT_CODE_DEFINITION = agents_module.LINT_CODE_DEFINITION
OPEN_GMAIL_AND_COMPOSE_DEFINITION = agents_module.OPEN_GMAIL_AND_COMPOSE_DEFINITION
RECOGNIZE_IMAGE_DEFINITION = agents_module.RECOGNIZE_IMAGE_DEFINITION
RECOGNIZE_VIDEO_DEFINITION = agents_module.RECOGNIZE_VIDEO_DEFINITION
FIND_FILE_BROADLY_DEFINITION = agents_module.FIND_FILE_BROADLY_DEFINITION
FIND_DIRECTORY_BROADLY_DEFINITION = agents_module.FIND_DIRECTORY_BROADLY_DEFINITION
CHANGE_WORKING_DIRECTORY_DEFINITION = agents_module.CHANGE_WORKING_DIRECTORY_DEFINITION
CREATE_PDF_DEFINITION = agents_module.CREATE_PDF_DEFINITION
CREATE_DOCX_DEFINITION = agents_module.CREATE_DOCX_DEFINITION
CREATE_EXCEL_DEFINITION = agents_module.CREATE_EXCEL_DEFINITION
CREATE_PPTX_DEFINITION = agents_module.CREATE_PPTX_DEFINITION
GITHUB_CREATE_BRANCH_DEFINITION = agents_module.GITHUB_CREATE_BRANCH_DEFINITION
GITHUB_COMMIT_FILE_DEFINITION = agents_module.GITHUB_COMMIT_FILE_DEFINITION
GITHUB_COMMIT_LOCAL_FILE_DEFINITION = agents_module.GITHUB_COMMIT_LOCAL_FILE_DEFINITION
GITHUB_MCP_DEFINITION = agents_module.GITHUB_MCP_DEFINITION
PLAYWRIGHT_MCP_DEFINITION = agents_module.PLAYWRIGHT_MCP_DEFINITION

# Initialize OpenAI agent
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
    PLAYWRIGHT_MCP_DEFINITION
]

model_name = 'gpt-4o'
agent = Agent(client, model_name, get_user_message=None, tools=tools)

def chat_page(request):
    return render(request, 'chat/index.html')

@csrf_exempt
def chat_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            history = data.get('history', [])
            status = data.get('status')
            pending_tools = data.get('pending_tools', [])
            if status == 'approved':
                pending_tools = data.get('pending_tools', [])
                for tool_call in pending_tools:
                    # Execute tool and get result
                    result = agent._execute_tool_by_name(tool_call.get('name'), tool_call.get('arguments'))
                    # Append tool result to history
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get('id'),
                        "name": tool_call.get('name'),
                        "content": result
                    })
                agent.control.reset()
                # Continue chat with the updated history
                response_data = agent.chat_once(conversation_history=history)
                return JsonResponse(response_data)
            
            elif status == 'denied':
                # User denied the tool calls
                pending_tools = data.get('pending_tools', [])
                for tool_call in pending_tools:
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get('id'),
                        "name": tool_call.get('name'),
                        "content": "The user has denied this tool call/action."
                    })
                if agent.control.cancelled:
                    agent.control.reset()

                response_data = agent.chat_once(
                    conversation_history=history,
                    message=user_message
                )
                return JsonResponse(response_data)

            if not user_message and not status:
                return JsonResponse({'error': 'No message provided'}, status=400)
            if agent.control.cancelled:
                agent.control.reset()


            response_data = agent.chat_once(conversation_history=history, message=user_message)
            return JsonResponse(response_data)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=405)
@csrf_exempt
@require_POST
def agent_control_api(request):
    try:
        data = json.loads(request.body)
        action = data.get("action")

        if not action:
            return JsonResponse({"error": "No action provided"}, status=400)

        if action == "pause":
            agent.control.pause()
        elif action == "resume":
            agent.control.resume()
        elif action == "cancel":
            agent.control.cancel()
        elif action == "disable_tools":
            agent.control.disable_tools()
        elif action == "enable_tools":
            agent.control.enable_tools()
        elif action == "reset":
            agent.control.reset()
        else:
            return JsonResponse({"error": "Unknown action"}, status=400)

        message = None
        if action == "pause":
            message = "⏸️ Execution paused."
        elif action == "resume":
            message = "▶️ Execution resumed."
        elif action == "cancel":
            message = "⛔ Execution cancelled."
        elif action == "disable_tools":
            message = "🔒 Tool execution disabled."
        elif action == "enable_tools":
            message = "🔓 Tool execution enabled."

        return JsonResponse({
            "message": message,
            "paused": agent.control.paused,
            "cancelled": agent.control.cancelled,
            "tools_enabled": agent.control.tools_enabled
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
