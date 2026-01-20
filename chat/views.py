import os
import json
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
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
LIST_FILES_DEFINITION = agents_module.LIST_FILES_DEFINITION
CREATE_AND_EDIT_FILE_DEFINITION = agents_module.CREATE_AND_EDIT_FILE_DEFINITION
DELETE_FILE_DEFINITION = agents_module.DELETE_FILE_DEFINITION
RENAME_FILE_DEFINITION = agents_module.RENAME_FILE_DEFINITION
OPEN_GMAIL_AND_COMPOSE_DEFINITION = agents_module.OPEN_GMAIL_AND_COMPOSE_DEFINITION

# Initialize OpenAI agent
tools = [READ_FILE_DEFINITION, LIST_FILES_DEFINITION, CREATE_AND_EDIT_FILE_DEFINITION, DELETE_FILE_DEFINITION, RENAME_FILE_DEFINITION, OPEN_GMAIL_AND_COMPOSE_DEFINITION]
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
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if not user_message:
            return JsonResponse({'error': 'No message provided'}, status=400)

        response_text = agent.chat_once(message=user_message)
        return JsonResponse({'response': response_text})

    return JsonResponse({'error': 'Invalid request'}, status=405)
