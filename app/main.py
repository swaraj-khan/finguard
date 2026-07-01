import secrets
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile, status
from fastapi.security import APIKeyHeader

from . import config, storage
from .db import get_supabase

app = FastAPI(title="Finguard Document API", version="0.1.0")

_password_header = APIKeyHeader(name="X-API-Password", auto_error=False)


def require_password(password: str | None = Security(_password_header)) -> None:
    if not password or not secrets.compare_digest(password, config.API_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing password (send it in the 'X-API-Password' header).",
        )


async def _read_capped(file: UploadFile, limit: int) -> bytes:
    chunk_size = 64 * 1024
    total = 0
    buffer = bytearray()
    while chunk := await file.read(chunk_size):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {limit // (1024 * 1024)} MB limit.",
            )
        buffer.extend(chunk)
    if not buffer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    return bytes(buffer)


def _store_file(contents: bytes, file: UploadFile, table: str, prefix: str, extra: dict) -> dict:
    client = get_supabase()
    try:
        object_key, file_url = storage.upload_file(contents, file.filename, file.content_type, prefix=prefix)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload file to storage: {exc}",
        )

    row = {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "storage_path": object_key,
        "file_url": file_url,
        **extra,
    }
    try:
        resp = client.table(table).insert(row).execute()
    except Exception as exc:
        try:
            client.storage.from_(config.STORAGE_BUCKET).remove([object_key])
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to store metadata in Supabase: {exc}",
        )
    return resp.data[0] if resp.data else row


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload_doc", status_code=status.HTTP_201_CREATED)
async def upload_doc(
    file: UploadFile = File(...),
    _: None = Depends(require_password),
) -> dict:
    contents = await _read_capped(file, config.MAX_FILE_SIZE)
    saved = _store_file(contents, file, config.UPLOAD_DOC_TABLE, prefix="", extra={})
    return {
        "id": saved.get("id"),
        "filename": saved.get("filename"),
        "content_type": saved.get("content_type"),
        "size_bytes": saved.get("size_bytes"),
        "file_url": saved.get("file_url"),
        "storage_path": saved.get("storage_path"),
        "uploaded_at": saved.get("uploaded_at"),
    }


@app.post("/analyzed_doc", status_code=status.HTTP_201_CREATED)
async def upload_analyzed_doc(
    upload_doc_id: UUID = Form(...),
    file: UploadFile = File(...),
    _: None = Depends(require_password),
) -> dict:
    doc_id = str(upload_doc_id)
    found = get_supabase().table(config.UPLOAD_DOC_TABLE).select("id").eq("id", doc_id).limit(1).execute()
    if not found.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No upload_doc found with id {doc_id}.",
        )

    contents = await _read_capped(file, config.MAX_FILE_SIZE)
    saved = _store_file(
        contents, file, config.ANALYZED_DOC_TABLE, prefix="analyzed", extra={"upload_doc_id": doc_id}
    )
    return {
        "id": saved.get("id"),
        "upload_doc_id": saved.get("upload_doc_id", doc_id),
        "filename": saved.get("filename"),
        "content_type": saved.get("content_type"),
        "size_bytes": saved.get("size_bytes"),
        "file_url": saved.get("file_url"),
        "storage_path": saved.get("storage_path"),
        "created_at": saved.get("created_at"),
    }
