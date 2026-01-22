import os
import json
import sys
import time
import django
from pathlib import Path
from django.conf import settings
from dotenv import load_dotenv
from openai import OpenAI

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Setup minimal Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        INSTALLED_APPS=[
            'chat',
        ],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3'),
            }
        },
        BASE_DIR=Path(__file__).resolve().parent.parent,
    )
    django.setup()
    
# Import Agent and tools from local agents.py
import agents as agents_module

Agent = agents_module.Agent
READ_FILE_DEFINITION = agents_module.READ_FILE_DEFINITION
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
SEARCH_FILE_DEFINITION = agents_module.SEARCH_FILE_DEFINITION
FIND_FILE_BROADLY_DEFINITION = agents_module.FIND_FILE_BROADLY_DEFINITION
FIND_DIRECTORY_BROADLY_DEFINITION = agents_module.FIND_DIRECTORY_BROADLY_DEFINITION

def run_evals(output_file='results.json'):
    # Load tasks
    tasks_path = os.path.join(os.path.dirname(__file__), 'tasks.json')
    with open(tasks_path, 'r') as f:
        tasks = json.load(f)

    # Initialize Agent with ALL tools
    tools = [
        READ_FILE_DEFINITION,
        SEARCH_FILE_DEFINITION,
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
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    model_name = 'gpt-4o'
    
    # We don't need a real get_user_message for chat_once
    agent = Agent(client, model_name, lambda: ("", False), tools)
    
    results = []
    total_start_time = time.time()
    
    for task in tasks:
        print(f"Running task {task['id']}: {task['prompt']}")
        
        task_start_time = time.time()
        
        # Track tool calls by checking history before/after (or assuming chat_once does it)
        # For more accuracy, we could wrap the tool execution or inspect history
        initial_history_len = 0 # Placeholder if we were tracking across turns
        
        response_data = agent.chat_once(conversation_history=[], message=task['prompt'])
        
        # Handle auto-approval for eval runner
        while isinstance(response_data, dict) and response_data.get('status') == 'pending':
            history = response_data.get('history', [])
            pending_tools = response_data.get('pending_tools', [])
            
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
            
            # Continue chat with the updated history
            response_data = agent.chat_once(conversation_history=history)

        duration = time.time() - task_start_time
        
        # In the current implementation of chat_once, it returns a dict or string
        if isinstance(response_data, dict):
            response = response_data.get('response', '')
            history = response_data.get('history', [])
        else:
            response = str(response_data)
            history = []

        # Count tool calls in history
        tool_calls_count = sum(1 for msg in history if msg.get('role') == 'tool')
        
        # More robust status check
        lower_resp = response.lower()
        is_error = (
            response.startswith("Error:") or 
            response.startswith("Exception:") or 
            "\nerror:" in lower_resp or 
            "\nexception:" in lower_resp or
            "task failed" in lower_resp
        )
        status = "failed" if is_error else "completed"
        
        result = {
            "id": task['id'],
            "category": task['category'],
            "prompt": task['prompt'],
            "response": response,
            "status": status,
            "duration_seconds": round(duration, 2),
            "tool_calls": tool_calls_count
        }
        results.append(result)
        print(f"Status: {status} | Duration: {result['duration_seconds']}s | Tool Calls: {tool_calls_count}")
        
        # Add a delay to avoid rate limiting
        if task != tasks[-1]:
            time.sleep(2)

    total_duration = time.time() - total_start_time
    
    # Calculate aggregate metrics
    completed_tasks = sum(1 for r in results if r['status'] == 'completed')
    total_tasks = len(results)
    accuracy = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    
    avg_speed = sum(r['duration_seconds'] for r in results) / total_tasks if total_tasks > 0 else 0
    total_tool_calls = sum(r['tool_calls'] for r in results)
    tool_efficiency = total_tool_calls / completed_tasks if completed_tasks > 0 else 0

    summary = {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "accuracy_percent": round(accuracy, 2),
        "average_task_duration_seconds": round(avg_speed, 2),
        "total_duration_seconds": round(total_duration, 2),
        "total_tool_calls": total_tool_calls,
        "tool_calls_per_completed_task": round(tool_efficiency, 2)
    }

    final_output = {
        "summary": summary,
        "results": results
    }

    # Save results
    results_path = os.path.join(os.path.dirname(__file__), output_file)
    with open(results_path, 'w') as f:
        json.dump(final_output, f, indent=2)
    
    print("\n" + "="*30)
    print("EVALUATION SUMMARY")
    print("="*30)
    for k, v in summary.items():
        print(f"{k.replace('_', ' ').title()}: {v}")
    print("="*30)
    print(f"Results saved to {results_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else 'results.json'
    run_evals(out_file)
