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
        file_options={"content-type": content_type or "application/octet-stream", "upsert": "false"},
    )
    public_url = client.storage.from_(config.STORAGE_BUCKET).get_public_url(key)
    return key, public_url.rstrip("?")


def remove_files(keys: list[str]) -> None:
    if keys:
        get_supabase().storage.from_(config.STORAGE_BUCKET).remove(keys)


def _file_info(bucket, key: str, obj: dict) -> dict:
    meta = obj.get("metadata") or {}
    return {
        "filename": obj.get("name"),
        "path": key,
        "file_url": bucket.get_public_url(key).rstrip("?"),
        "size_bytes": meta.get("size"),
        "uploaded_at": obj.get("created_at"),
    }


def _walk(bucket, prefix: str, out: list) -> None:
    for entry in bucket.list(prefix, {"limit": 1000}):
        name = entry.get("name")
        if not name or name == ".emptyFolderPlaceholder":
            continue
        key = f"{prefix}/{name}" if prefix else name
        if entry.get("id") is None:
            _walk(bucket, key, out)
        else:
            out.append(_file_info(bucket, key, entry))


def list_files() -> list[dict]:
    bucket = get_supabase().storage.from_(config.STORAGE_BUCKET)
    files: list[dict] = []
    _walk(bucket, "", files)
    files.sort(key=lambda f: f.get("uploaded_at") or "", reverse=True)
    return files
