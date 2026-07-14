import uuid
from uuid import UUID

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


def _document_key(document_id: str, prefix: str) -> str:
    return f"{prefix.strip('/')}/{document_id}/{_DOCUMENT_FILENAME}"


def store_document(
    contents: bytes,
    document_id: str,
    prefix: str,
    metadata: dict | None = None,
) -> None:
    key = _document_key(document_id, prefix)
    file_options = {"content-type": "application/octet-stream", "upsert": "false"}
    if metadata:
        file_options["metadata"] = metadata
    get_supabase().storage.from_(config.STORAGE_BUCKET).upload(
        path=key,
        file=contents,
        file_options=file_options,
    )


def create_document(contents: bytes, prefix: str, metadata: dict | None = None) -> str:
    document_id = str(uuid.uuid4())
    store_document(contents, document_id, prefix, metadata=metadata)
    return document_id


def document_exists(document_id: str, prefix: str) -> bool:
    key = _document_key(document_id, prefix)
    return get_supabase().storage.from_(config.STORAGE_BUCKET).exists(key)


def get_document(document_id: str, prefix: str) -> bytes | None:
    key = _document_key(document_id, prefix)
    bucket = get_supabase().storage.from_(config.STORAGE_BUCKET)
    if not bucket.exists(key):
        return None
    return bucket.download(key)


def list_document_ids(prefix: str) -> list[str]:
    bucket = get_supabase().storage.from_(config.STORAGE_BUCKET)
    folder = prefix.strip("/")
    document_ids: list[str] = []
    limit = 1000
    offset = 0

    while True:
        entries = bucket.list(
            folder,
            {
                "limit": limit,
                "offset": offset,
                "sortBy": {"column": "name", "order": "asc"},
            },
        )
        for entry in entries:
            if entry.get("id") is not None:
                continue
            try:
                document_ids.append(str(UUID(entry.get("name", ""))))
            except (ValueError, AttributeError, TypeError):
                continue

        if len(entries) < limit:
            break
        offset += limit

    return document_ids
