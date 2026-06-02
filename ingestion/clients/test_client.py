# test_client.py

from supabase_client import (
    get_supabase_client
)

try:
    supabase = get_supabase_client()

    print("Connected successfully")
    print(type(supabase))

except Exception as e:
    print("Failed:", e)