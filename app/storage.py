import os
import re
import uuid

from . import config
from .db import get_supabase


def ensure_bucket() -> None:
    client = get_supabase()
    options = {"public": True, "file_size_limit": config.MAX_FILE_SIZE}
    try:
        client.storage.create_bucket(config.STORAGE_BUCKET, options=options)
    except Exception as exc:
        if "already exists" in str(exc).lower():
            client.storage.update_bucket(config.STORAGE_BUCKET, options=options)
        else:
            raise


def _make_object_key(filename: str | None, prefix: str = "") -> str:
    base = os.path.basename(filename or "file")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base) or "file"
    folder = f"{prefix.strip('/')}/" if prefix else ""
    return f"{folder}{uuid.uuid4()}/{safe}"


def upload_file(
    contents: bytes, filename: str | None, content_type: str | None, prefix: str = ""
) -> tuple[str, str]:
    client = get_supabase()
    key = _make_object_key(filename, prefix)
    client.storage.from_(config.STORAGE_BUCKET).upload(
        path=key,
        file=contents,
        file_options={
            "content-type": content_type or "application/octet-stream",
            "upsert": "false",
        },
    )
    public_url = client.storage.from_(config.STORAGE_BUCKET).get_public_url(key)
    return key, public_url.rstrip("?")
