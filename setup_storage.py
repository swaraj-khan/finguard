from app import config
from app.storage import ensure_bucket

if __name__ == "__main__":
    ensure_bucket()
    print(f"Bucket '{config.STORAGE_BUCKET}' is ready (public).")
