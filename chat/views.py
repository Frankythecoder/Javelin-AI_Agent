import os
import json
import boto3
from botocore.exceptions import ClientError
import importlib.util
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from openai import OpenAI
from decouple import config
from django.conf import settings

from agents import RENAME_FILE_DEFINITION

# Configure OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Function to load agents module from S3 (best-effort) or local fallback
def load_module_from_s3(bucket_name, s3_key, local_path=None):
    if local_path is None:
        local_path = os.path.join(settings.BASE_DIR, 'agents.py')

    if not os.path.exists(local_path) and bucket_name and s3_key:
        print(f"[INFO] Downloading '{s3_key}' from S3 bucket '{bucket_name}' to '{local_path}'")
        s3 = boto3.client(
            's3',
            aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'),
            region_name=config('AWS_S3_REGION_NAME', default='us-east-1')
        )
        try:
            s3.download_file(bucket_name, s3_key, local_path)
            print(f"[INFO] Successfully downloaded module to: {local_path}")
        except ClientError as error:
            print(f"[WARN] Could not download from S3 ({error}). Falling back to local 'agents.py' if present.")
        except Exception as error:
            print(f"[WARN] Unexpected error downloading from S3: {error}. Falling back to local 'agents.py' if present.")

    if not os.path.exists(local_path):
        raise FileNotFoundError(f"agents.py not found at {local_path}. Provide a local file or configure S3 correctly.")
    else:
        print(f"[INFO] Using local module: {local_path}")

    spec = importlib.util.spec_from_file_location("agents", local_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

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
