import os

from dotenv import load_dotenv

load_dotenv()

API_PASSWORD = os.getenv("API_PASSWORD", "Finguard123")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "documents")
UPLOAD_PREFIX = os.getenv("UPLOAD_PREFIX", "uploaded_docs")
MAX_FILE_SIZE = 2 * 1024 * 1024

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
        "Copy .env.example to .env and fill in the values."
    )
