import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get AWS credentials
aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
region = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')

# File paths
local_file = 'agents.py'
s3_key = 'ai_agent/agents.py'

print(f"Uploading {local_file} to s3://{bucket_name}/{s3_key}...")

try:
    # Create S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=region
    )

    # Upload file
    s3_client.upload_file(local_file, bucket_name, s3_key)

    print(f"SUCCESS: Uploaded {local_file} to S3!")
    print(f"Location: s3://{bucket_name}/{s3_key}")

    # Verify upload by getting object metadata
    response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
    file_size = response['ContentLength']
    print(f"File size: {file_size:,} bytes")
    print(f"Last modified: {response['LastModified']}")

except Exception as e:
    print(f"ERROR: Failed to upload file: {str(e)}")
    exit(1)
