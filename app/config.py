import os

from dotenv import load_dotenv

load_dotenv()

API_PASSWORD = os.getenv("API_PASSWORD", "Finguard123")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
UPLOAD_DOC_TABLE = os.getenv("UPLOAD_DOC_TABLE", "upload_doc")
ANALYZED_DOC_TABLE = os.getenv("ANALYZED_DOC_TABLE", "analyzed_doc")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "documents")
MAX_FILE_SIZE = 2 * 1024 * 1024

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
        "Copy .env.example to .env and fill in the values."
    )
