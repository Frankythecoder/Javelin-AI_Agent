import os
import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from openai import OpenAI
from decouple import config
from django.conf import settings
from utils import load_module_from_s3
from .models import ChatSession

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
RECOGNIZE_AUDIO_DEFINITION = agents_module.RECOGNIZE_AUDIO_DEFINITION
FIND_FILE_BROADLY_DEFINITION = agents_module.FIND_FILE_BROADLY_DEFINITION
FIND_DIRECTORY_BROADLY_DEFINITION = agents_module.FIND_DIRECTORY_BROADLY_DEFINITION
CHANGE_WORKING_DIRECTORY_DEFINITION = agents_module.CHANGE_WORKING_DIRECTORY_DEFINITION
CREATE_PDF_DEFINITION = agents_module.CREATE_PDF_DEFINITION
CREATE_DOCX_DEFINITION = agents_module.CREATE_DOCX_DEFINITION
CREATE_EXCEL_DEFINITION = agents_module.CREATE_EXCEL_DEFINITION
CREATE_PPTX_DEFINITION = agents_module.CREATE_PPTX_DEFINITION
READ_PDF_DEFINITION = agents_module.READ_PDF_DEFINITION
READ_DOCX_DEFINITION = agents_module.READ_DOCX_DEFINITION
READ_EXCEL_DEFINITION = agents_module.READ_EXCEL_DEFINITION
READ_PPTX_DEFINITION = agents_module.READ_PPTX_DEFINITION
EDIT_PDF_DEFINITION = agents_module.EDIT_PDF_DEFINITION
EDIT_DOCX_DEFINITION = agents_module.EDIT_DOCX_DEFINITION
EDIT_EXCEL_DEFINITION = agents_module.EDIT_EXCEL_DEFINITION
EDIT_PPTX_DEFINITION = agents_module.EDIT_PPTX_DEFINITION
GITHUB_CREATE_BRANCH_DEFINITION = agents_module.GITHUB_CREATE_BRANCH_DEFINITION
GITHUB_COMMIT_FILE_DEFINITION = agents_module.GITHUB_COMMIT_FILE_DEFINITION
GITHUB_COMMIT_LOCAL_FILE_DEFINITION = agents_module.GITHUB_COMMIT_LOCAL_FILE_DEFINITION
GITHUB_MCP_DEFINITION = agents_module.GITHUB_MCP_DEFINITION
CREATE_GITHUB_ISSUE_DEFINITION = agents_module.CREATE_GITHUB_ISSUE_DEFINITION
PLAYWRIGHT_MCP_DEFINITION = agents_module.PLAYWRIGHT_MCP_DEFINITION
SEARCH_FLIGHTS_DEFINITION = agents_module.SEARCH_FLIGHTS_DEFINITION
SEARCH_HOTELS_DEFINITION = agents_module.SEARCH_HOTELS_DEFINITION
BOOK_TRAVEL_DEFINITION = agents_module.BOOK_TRAVEL_DEFINITION

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
    RECOGNIZE_AUDIO_DEFINITION,
    FIND_FILE_BROADLY_DEFINITION,
    FIND_DIRECTORY_BROADLY_DEFINITION,
    CHANGE_WORKING_DIRECTORY_DEFINITION,
    CREATE_PDF_DEFINITION,
    CREATE_DOCX_DEFINITION,
    CREATE_EXCEL_DEFINITION,
    CREATE_PPTX_DEFINITION,
    READ_PDF_DEFINITION,
    READ_DOCX_DEFINITION,
    READ_EXCEL_DEFINITION,
    READ_PPTX_DEFINITION,
    EDIT_PDF_DEFINITION,
    EDIT_DOCX_DEFINITION,
    EDIT_EXCEL_DEFINITION,
    EDIT_PPTX_DEFINITION,
    GITHUB_CREATE_BRANCH_DEFINITION,
    GITHUB_COMMIT_FILE_DEFINITION,
    GITHUB_COMMIT_LOCAL_FILE_DEFINITION,
    GITHUB_MCP_DEFINITION,
    CREATE_GITHUB_ISSUE_DEFINITION,
    PLAYWRIGHT_MCP_DEFINITION,
    SEARCH_FLIGHTS_DEFINITION,
    SEARCH_HOTELS_DEFINITION,
    BOOK_TRAVEL_DEFINITION,
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
                # Continue chat with the updated history — stay in per-tool
                # approval mode because the dry-run plan was already approved.
                response_data = agent.chat_once(conversation_history=history, use_pending=True)
                return JsonResponse(response_data)

            elif status == 'denied':
                # User denied one per-tool action but the overall plan is still
                # approved, so stay in per-tool approval mode.
                pending_tools = data.get('pending_tools', [])
                for tool_call in pending_tools:
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get('id'),
                        "name": tool_call.get('name'),
                        "content": "The user has denied this tool call/action."
                    })

                response_data = agent.chat_once(
                    conversation_history=history,
                    message=user_message,
                    use_pending=True
                )
                return JsonResponse(response_data)

            elif status == 'dry_run_approved':
                dry_run_plan = data.get('dry_run_plan', [])
                response_data = agent.execute_dry_run(dry_run_plan, history)
                return JsonResponse(response_data)

            elif status == 'dry_run_denied':
                dry_run_plan = data.get('dry_run_plan', [])
                for tool_call in dry_run_plan:
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get('id'),
                        "name": tool_call.get('name'),
                        "content": "The user denied this action during the dry run review."
                    })
                response_data = agent.chat_once(conversation_history=history)
                return JsonResponse(response_data)

            if not user_message and not status:
                return JsonResponse({'error': 'No message provided'}, status=400)


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

        if action == "stop":
            agent.control.stop()
        elif action == "disable_tools":
            agent.control.disable_tools()
        elif action == "enable_tools":
            agent.control.enable_tools()
        else:
            return JsonResponse({"error": "Unknown action"}, status=400)

        message = None
        if action == "stop":
            message = "⛔ Execution stopped."
        elif action == "disable_tools":
            message = "🔒 Tool execution disabled."
        elif action == "enable_tools":
            message = "🔓 Tool execution enabled."

        return JsonResponse({
            "message": message,
            "stopped": agent.control.stopped,
            "tools_enabled": agent.control.tools_enabled
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def chat_sessions_api(request):
    """List all saved chat sessions (GET) or save/update one (POST)."""
    try:
        if request.method == 'GET':
            sessions = ChatSession.objects.order_by('-updated_at').values(
                'id', 'title', 'created_at', 'updated_at'
            )
            session_list = []
            for s in sessions:
                session_list.append({
                    'id': s['id'],
                    'title': s['title'] or f"Chat {s['id']}",
                    'updated_at': s['updated_at'].strftime('%b %d, %Y %I:%M %p'),
                })
            return JsonResponse({'sessions': session_list})

        elif request.method == 'POST':
            data = json.loads(request.body)
            history = data.get('history', [])
            title = data.get('title', '')
            session_id = data.get('session_id')

            if not history:
                return JsonResponse({'error': 'Nothing to save'}, status=400)

            history_json = json.dumps(history)

            if session_id:
                try:
                    session = ChatSession.objects.get(id=session_id)
                    session.history = history_json
                    if title:
                        session.title = title
                    session.save()
                    return JsonResponse({'session_id': session.id, 'title': session.title})
                except ChatSession.DoesNotExist:
                    pass  # Session was deleted; fall through to create a new one

            session = ChatSession.objects.create(title=title, history=history_json)
            return JsonResponse({'session_id': session.id, 'title': session.title})

        return JsonResponse({'error': 'Invalid request'}, status=405)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def list_directory_files_api(request):
    """Return files in the agent's current working directory."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request'}, status=405)
    try:
        cwd = os.getcwd()
        entries = []
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env'}
        for dirpath, dirnames, filenames in os.walk(cwd):
            # Skip hidden/cache directories
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            rel_dir = os.path.relpath(dirpath, cwd)
            for fname in filenames:
                rel_path = fname if rel_dir == '.' else os.path.join(rel_dir, fname).replace('\\', '/')
                entries.append({
                    'name': fname,
                    'rel_path': rel_path,
                    'type': 'file',
                    'path': os.path.join(dirpath, fname),
                })
            for dname in dirnames:
                rel_path = dname if rel_dir == '.' else os.path.join(rel_dir, dname).replace('\\', '/')
                entries.append({
                    'name': dname,
                    'rel_path': rel_path,
                    'type': 'directory',
                    'path': os.path.join(dirpath, dname),
                })
        entries.sort(key=lambda e: e['rel_path'])
        return JsonResponse({'files': entries, 'cwd': cwd})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def chat_session_detail_api(request, session_id):
    """Load a chat session (GET) or delete it (DELETE)."""
    try:
        if request.method == 'GET':
            session = ChatSession.objects.get(id=session_id)
            return JsonResponse({
                'session_id': session.id,
                'title': session.title,
                'history': json.loads(session.history),
            })

        elif request.method == 'DELETE':
            ChatSession.objects.filter(id=session_id).delete()
            return JsonResponse({'deleted': True})

        return JsonResponse({'error': 'Invalid request'}, status=405)

    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Chat not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def serve_logo(request):
    """Serve the Javelin logo from the project root."""
    logo_path = os.path.join(settings.BASE_DIR, 'javelin.png')
    return FileResponse(open(logo_path, 'rb'), content_type='image/png')
