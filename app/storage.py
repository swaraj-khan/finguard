import uuid

from . import config
from .db import get_supabase

_DOCUMENT_FILENAME = "document.bin"


def ensure_bucket() -> None:
    client = get_supabase()
    options = {"public": False, "file_size_limit": config.MAX_FILE_SIZE}
    try:
        client.storage.create_bucket(config.STORAGE_BUCKET, options=options)
    except Exception as exc:
        if "already exists" in str(exc).lower():
            client.storage.update_bucket(config.STORAGE_BUCKET, options=options)
        else:
            raise


def _document_key(document_id: str, prefix: str = "") -> str:
    folder = f"{prefix.strip('/')}/" if prefix else ""
    return f"{folder}{document_id}/{_DOCUMENT_FILENAME}"


def upload_document(contents: bytes, prefix: str = "") -> str:
    document_id = str(uuid.uuid4())
    key = _document_key(document_id, prefix)
    get_supabase().storage.from_(config.STORAGE_BUCKET).upload(
        path=key,
        file=contents,
        file_options={"content-type": "application/octet-stream", "upsert": "false"},
    )
    return document_id


def get_document(document_id: str, prefix: str = "") -> bytes | None:
    key = _document_key(document_id, prefix)
    bucket = get_supabase().storage.from_(config.STORAGE_BUCKET)
    if not bucket.exists(key):
        return None
    return bucket.download(key)
