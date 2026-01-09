import os
import json
import sys
import time
import django
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
        INSTALLED_APPS=[],
    )
    django.setup()

from agents import Agent, READ_FILE_DEFINITION, LIST_FILES_DEFINITION, CREATE_AND_EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION, RENAME_FILE_DEFINITION, RUN_CODE_DEFINITION

def run_evals(output_file='results.json'):
    # Load tasks
    tasks_path = os.path.join(os.path.dirname(__file__), 'tasks.json')
    with open(tasks_path, 'r') as f:
        tasks = json.load(f)

    # Initialize Agent
    tools = [
        READ_FILE_DEFINITION, 
        LIST_FILES_DEFINITION, 
        CREATE_AND_EDIT_FILE_DEFINITION, 
        DELETE_FILE_DEFINITION, 
        RENAME_FILE_DEFINITION,
        RUN_CODE_DEFINITION
    ]
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    model_name = 'gpt-4o'
    
    # We don't need a real get_user_message for chat_once
    agent = Agent(client, model_name, lambda: ("", False), tools)
    
    results = []
    
    for task in tasks:
        print(f"Running task {task['id']}: {task['prompt']}")
        
        # Process the latest message and determine status
        response = agent.chat_once(message=task['prompt'])
        
        status = "failed" if "Error:" in response or "Exception:" in response else "completed"
        
        result = {
            "id": task['id'],
            "category": task['category'],
            "prompt": task['prompt'],
            "response": response,
            "status": status
        }
        results.append(result)
        print(f"Response: {response[:100]}...")
        
        # Add a delay to avoid rate limiting on free tier (15 RPM)
        if task != tasks[-1]:
            print("Waiting 5 seconds for rate limit cooldown...")
            time.sleep(5)

    # Save results
    results_path = os.path.join(os.path.dirname(__file__), output_file)
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nEvaluation complete. Results saved to {results_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else 'results.json'
    run_evals(out_file)
