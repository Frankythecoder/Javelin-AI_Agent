import os
import json
import shutil
import sys
import tempfile
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
    
# Import Agent and dynamically discover all tool definitions
import agents as agents_module

Agent = agents_module.Agent

# Dynamically collect all tool definitions (with type guard)
tools = [
    obj for name in sorted(dir(agents_module))
    if name.endswith('_DEFINITION')
    and isinstance(obj := getattr(agents_module, name), agents_module.ToolDefinition)
]

if not tools:
    raise RuntimeError("No tool definitions discovered — check agents package imports")

def run_evals(output_file='results.json', eatp_mode='cold', correction_policy_file=None):
    # Load tasks
    tasks_path = os.path.join(os.path.dirname(__file__), 'tasks.json')
    with open(tasks_path, 'r') as f:
        tasks = json.load(f)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    model_name = 'gpt-4.1'

    # We don't need a real get_user_message for chat_once
    agent = Agent(client, model_name, lambda: ("", False), tools, light_model_name='gpt-4.1-mini')

    # Mock external API tools for deterministic eval
    from evals.mocks import MOCK_REGISTRY
    original_execute = agent._execute_tool_by_name
    def mock_aware_execute(name, args):
        if name in MOCK_REGISTRY:
            return MOCK_REGISTRY[name](args)
        return original_execute(name, args)
    agent._execute_tool_by_name = mock_aware_execute

    # EATP: Configure experience store mode
    if eatp_mode == 'cold':
        # Clear experience store for baseline measurement
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        if os.path.exists(experience_dir):
            shutil.rmtree(experience_dir)
        from agents.experience_store import ExperienceStore
        agent.experience_store = ExperienceStore(persist_dir=experience_dir)
    elif eatp_mode == 'warm':
        # Use existing experience store (populated from Phase B)
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        from agents.experience_store import ExperienceStore
        agent.experience_store = ExperienceStore(persist_dir=experience_dir)
    elif eatp_mode == 'off':
        # Disable EATP entirely — no retrieval, no logging, no pollution
        agent.experience_store = None
    elif eatp_mode == 'static-fewshot':
        agent.experience_store = None
        from evals.static_fewshot import STATIC_EXAMPLES
        agent.system_instruction += "\n\n" + STATIC_EXAMPLES
    elif eatp_mode == 'warm-successes':
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        from agents.experience_store import ExperienceStore
        agent.experience_store = ExperienceStore(persist_dir=experience_dir)
        original_format = agent.experience_store.format_for_prompt
        def format_without_corrections(records):
            for r in records:
                r.user_corrections = []
            return original_format(records)
        agent.experience_store.format_for_prompt = format_without_corrections

    # Load correction policy for Phase B
    correction_policy = {}
    if correction_policy_file:
        policy_path = os.path.join(os.path.dirname(__file__), correction_policy_file)
        if os.path.exists(policy_path):
            with open(policy_path, 'r') as f:
                correction_policy = json.load(f)

    results = []
    total_start_time = time.time()
    
    for task in tasks:
        print(f"Running task {task['id']}: {task['prompt']}")

        task_start_time = time.time()

        # Clear session feedback from previous task
        agent.clear_session_feedback()

        # Create isolated workspace for this task
        task_workdir = tempfile.mkdtemp(prefix=f"eatp_eval_{task['id']}_")
        seed_files = task.get('seed_files', [])
        seeds_base = os.path.join(os.path.dirname(__file__), 'seeds')
        for sf in seed_files:
            src = os.path.join(seeds_base, sf['source'])
            dst = os.path.join(task_workdir, sf['name'])
            if os.path.exists(src):
                shutil.copy2(src, dst)

        # Point agent to task workspace
        try:
            agent._execute_tool_by_name('change_working_directory', {'path': task_workdir})
        except Exception:
            pass  # Tool may not exist in all configs

        response_data = agent.chat_once(conversation_history=[], message=task['prompt'])

        # Handle dry_run and pending statuses — keep looping until we get a terminal status
        task_policy = correction_policy.get(task['id']) or correction_policy.get(task.get('category'))
        max_turns = 15  # Safety limit to prevent infinite loops
        turn = 0
        while isinstance(response_data, dict) and turn < max_turns:
            status = response_data.get('status')
            turn += 1

            if status == 'dry_run':
                # chat_once defaults to dry-run mode — agent proposed a plan, we need to execute it
                plan = response_data.get('dry_run_plan', [])
                history = response_data.get('history', [])

                # Check correction policy: deny a tool from the plan if policy says so
                if task_policy:
                    denied_tool = task_policy.get('deny')
                    if any(t['name'] == denied_tool for t in plan):
                        correction_text = task_policy.get('correction', f'User denied {denied_tool}.')
                        agent.record_denial(denied_tool, "denied")
                        agent.record_correction(f"User denied {denied_tool}. {correction_text}")
                        # Remove denied tool from plan
                        plan = [t for t in plan if t['name'] != denied_tool]
                        # Inject correction as user message so agent learns the right approach
                        history.append({
                            "role": "user",
                            "content": f"I denied the use of {denied_tool}. {correction_text}"
                        })
                        task_policy = None  # Only apply once per task

                        if plan:
                            # Execute remaining tools, then agent continues with correction context
                            response_data = agent.execute_dry_run(plan, history)
                        else:
                            # All tools denied — let agent re-plan with correction
                            response_data = agent.chat_once(conversation_history=history)
                        continue

                # No correction needed — auto-approve entire plan
                if plan:
                    response_data = agent.execute_dry_run(plan, history)
                else:
                    break  # Empty plan, nothing to do

            elif status == 'pending':
                # Per-tool approval mode (used after execute_dry_run for follow-up calls)
                history = response_data.get('history', [])
                pending_tools = response_data.get('pending_tools', [])

                for tool_call in pending_tools:
                    tool_name = tool_call.get('name')
                    # Check correction policy for pending tools too
                    if task_policy and tool_name == task_policy.get('deny'):
                        correction_text = task_policy.get('correction', f'User denied {tool_name}.')
                        agent.record_denial(tool_name, "denied")
                        agent.record_correction(f"User denied {tool_name}. {correction_text}")
                        history.append({
                            "role": "user",
                            "content": f"I denied the use of {tool_name}. {correction_text}"
                        })
                        task_policy = None
                    else:
                        # Auto-approve
                        result = agent._execute_tool_by_name(tool_name, tool_call.get('arguments'))
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.get('id'),
                            "name": tool_name,
                            "content": result
                        })

                response_data = agent.chat_once(conversation_history=history)

            else:
                # Terminal status: success, error, stopped
                break

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

        # Run ground-truth validator
        from evals.validators import VALIDATORS, default_validator
        validator = VALIDATORS.get(task['id'], default_validator)
        try:
            result_data = {"response": response, "history": history}
            validated = validator(result_data, task_workdir)
        except Exception:
            validated = False
        result["validated"] = validated

        results.append(result)
        print(f"Status: {status} | Validated: {validated} | Duration: {result['duration_seconds']}s | Tool Calls: {tool_calls_count}")

        # Cleanup workspace
        try:
            shutil.rmtree(task_workdir)
        except Exception:
            pass

        # Add a delay to avoid rate limiting
        if task != tasks[-1]:
            time.sleep(2)

    total_duration = time.time() - total_start_time
    
    # Calculate aggregate metrics
    completed_tasks = sum(1 for r in results if r['status'] == 'completed')
    validated_tasks = sum(1 for r in results if r.get('validated', False))
    total_tasks = len(results)
    accuracy = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0

    avg_speed = sum(r['duration_seconds'] for r in results) / total_tasks if total_tasks > 0 else 0
    total_tool_calls = sum(r['tool_calls'] for r in results)
    tool_efficiency = total_tool_calls / completed_tasks if completed_tasks > 0 else 0

    summary = {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "validated_tasks": validated_tasks,
        "validated_percent": round((validated_tasks / total_tasks) * 100, 2) if total_tasks > 0 else 0,
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results.json')
    parser.add_argument('--eatp-mode', choices=['cold', 'warm', 'off', 'static-fewshot', 'warm-successes'], default='off')
    parser.add_argument('--correction-policy', default=None)
    args = parser.parse_args()
    run_evals(args.output, args.eatp_mode, args.correction_policy)
