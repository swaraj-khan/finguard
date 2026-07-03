import secrets

from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile, status
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader

from . import config, storage

app = FastAPI(title="Finguard PDF Upload API", version="1.0.0")

_password_header = APIKeyHeader(name="X-API-Password", auto_error=False)


def require_password(password: str | None = Security(_password_header)) -> None:
    if not password or not secrets.compare_digest(password, config.API_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing password (send it in the 'X-API-Password' header).",
        )


def _is_pdf(file: UploadFile) -> bool:
    return file.content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf")


async def _read_capped(file: UploadFile, limit: int) -> bytes:
    total = 0
    buffer = bytearray()
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"'{file.filename}' exceeds the {limit // (1024 * 1024)} MB limit.",
            )
        buffer.extend(chunk)
    if not buffer:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{file.filename}' is empty.")
    return bytes(buffer)


@app.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload(
    files: list[UploadFile] = File(...),
    _: None = Depends(require_password),
) -> dict:
    payloads = []
    for file in files:
        if not _is_pdf(file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{file.filename}' is not a PDF.",
            )
        payloads.append((file, await _read_capped(file, config.MAX_FILE_SIZE)))

    keys: list[str] = []
    uploaded = []
    try:
        for file, contents in payloads:
            key, file_url = storage.upload_file(contents, file.filename, "application/pdf", prefix=config.UPLOAD_PREFIX)
            keys.append(key)
            uploaded.append({"filename": file.filename, "size_bytes": len(contents), "file_url": file_url})
    except Exception as exc:
        try:
            storage.remove_files(keys)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload to storage: {exc}",
        )

    return {"count": len(uploaded), "files": uploaded}


@app.get("/files")
def list_uploaded_files(_: None = Depends(require_password)) -> dict:
    files = storage.list_files()
    return {"count": len(files), "files": files}


def _mark_binary(node) -> None:
    if isinstance(node, dict):
        if node.get("type") == "string" and node.pop("contentMediaType", None):
            node["format"] = "binary"
        for value in node.values():
            _mark_binary(value)
    elif isinstance(node, list):
        for value in node:
            _mark_binary(value)


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    _mark_binary(schema)
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi
