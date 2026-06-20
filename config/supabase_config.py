import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_supabase_client = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("⚠️ .env に SUPABASE_URL と SUPABASE_KEY を設定してください")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client