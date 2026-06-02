"""
Cloudflare R2 Client

Khởi tạo boto3 S3-compatible client để kết nối Cloudflare R2.
"""

import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()


def get_r2_client():
    """
    Create Cloudflare R2 client.

    Required environment variables:
        R2_ENDPOINT_URL
        R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY
    """

    endpoint_url = os.getenv("R2_ENDPOINT_URL")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not endpoint_url:
        raise ValueError("Missing R2_ENDPOINT_URL")

    if not access_key:
        raise ValueError("Missing R2_ACCESS_KEY_ID")

    if not secret_key:
        raise ValueError("Missing R2_SECRET_ACCESS_KEY")

    return boto3.client(
        service_name="s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            retries={
                "max_attempts": 3,
                "mode": "adaptive",
            },
        ),
    )
def validate_r2_credentials() -> bool:
    """Check R2 credentials có đủ trong .env không."""
    return all([
        os.getenv("R2_ENDPOINT_URL"),
        os.getenv("R2_ACCESS_KEY_ID"),
        os.getenv("R2_SECRET_ACCESS_KEY"),
        os.getenv("R2_BUCKET_NAME"),
    ])