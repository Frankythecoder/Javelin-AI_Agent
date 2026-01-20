import os
import boto3
import importlib.util
from botocore.exceptions import ClientError
from django.conf import settings
try:
    from decouple import config
except ImportError:
    # Fallback if decouple is not installed in the environment where this is run
    def config(key, default=None):
        return os.environ.get(key, default)

def load_module_from_s3(bucket_name, s3_key, local_path=None):
    if local_path is None:
        local_path = os.path.join(settings.BASE_DIR, 'agents.py')

    # Try downloading from S3 first
    if bucket_name and s3_key:
        print(f"[INFO] Attempting to download '{s3_key}' from S3 bucket '{bucket_name}' to '{local_path}'")
        s3 = boto3.client(
            's3',
            aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'),
            region_name=config('AWS_S3_REGION_NAME', default='us-east-1')
        )
        try:
            s3.download_file(bucket_name, s3_key, local_path)
            print(f"[INFO] Successfully downloaded module from S3 to: {local_path}")
        except ClientError as error:
            print(f"[WARN] Could not download from S3 ({error}). Falling back to local 'agents.py' if present.")
        except Exception as error:
            print(f"[WARN] Unexpected error downloading from S3: {error}. Falling back to local 'agents.py' if present.")

    if not os.path.exists(local_path):
        raise FileNotFoundError(f"agents.py not found at {local_path} and S3 download failed. Provide a local file or configure S3 correctly.")
    
    print(f"[INFO] Loading module: {local_path}")
    spec = importlib.util.spec_from_file_location("agents", local_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
