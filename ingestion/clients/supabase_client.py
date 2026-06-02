"""
Supabase Client

Kết nối Supabase qua official Python SDK.

Dùng để:
    - Ghi ingestion logs
    - Lưu metadata catalog
    - Track pipeline run history
"""

import os
import logging

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """
    Khởi tạo Supabase client.

    Required environment variables:
        SUPABASE_URL
        SUPABASE_KEY
    """

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url:
        raise ValueError("Missing SUPABASE_URL")

    if not key:
        raise ValueError("Missing SUPABASE_KEY")

    return create_client(url, key)


def validate_supabase_credentials() -> bool:
    """Check Supabase credentials có đủ trong .env không."""
    return all([
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY"),
    ])

