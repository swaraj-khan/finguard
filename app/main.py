import base64
import binascii
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Body, Depends, FastAPI, HTTPException, Security, status
from fastapi.responses import PlainTextResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from . import config, storage

app = FastAPI(title="Finguard Base64 Document API", version="3.0.0")

_password_header = APIKeyHeader(name="X-API-Password", auto_error=False)


class UploadResponse(BaseModel):
    document_id: UUID


def require_password(password: str | None = Security(_password_header)) -> None:
    if not password or not secrets.compare_digest(password, config.API_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing password (send it in the 'X-API-Password' header).",
        )


def _decode_payload(payload: str) -> bytes:
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The Base64 payload is empty.")

    # Reject oversized input before decoding it. Standard Base64 uses four
    # characters for every three decoded bytes.
    max_encoded_size = ((config.MAX_FILE_SIZE + 2) // 3) * 4
    if len(payload) > max_encoded_size:
        raise HTTPException(
            status_code=413,
            detail=f"The decoded document exceeds the {config.MAX_FILE_SIZE // (1024 * 1024)} MB limit.",
        )

    try:
        contents = base64.b64decode(payload.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The request body must be a plain, valid standard Base64 string.",
        ) from None

    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The decoded document is empty.")
    if len(contents) > config.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"The decoded document exceeds the {config.MAX_FILE_SIZE // (1024 * 1024)} MB limit.",
        )
    return contents


def _encode(contents: bytes) -> str:
    return base64.b64encode(contents).decode("ascii")


@app.post("/upload", status_code=status.HTTP_201_CREATED, response_model=UploadResponse)
def upload(
    payload: Annotated[
        str,
        Body(
            media_type="text/plain",
            description="Any document or value encoded as plain standard Base64 (no data-URL prefix).",
        ),
    ],
    _: None = Depends(require_password),
) -> UploadResponse:
    contents = _decode_payload(payload)
    try:
        document_id = storage.upload_document(contents, prefix=config.UPLOAD_PREFIX)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload to storage: {exc}",
        ) from exc

    return UploadResponse(document_id=document_id)


@app.get("/files", response_model=list[UUID])
def list_uploaded_file_ids(_: None = Depends(require_password)) -> list[UUID]:
    try:
        document_ids = storage.list_document_ids(prefix=config.UPLOAD_PREFIX)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list documents from storage: {exc}",
        ) from exc

    return [UUID(document_id) for document_id in document_ids]


@app.get(
    "/files/{document_id}",
    response_class=PlainTextResponse,
    responses={
        status.HTTP_200_OK: {
            "content": {
                "text/plain": {
                    "schema": {
                        "type": "string",
                        "description": "The requested document as a standard Base64 string.",
                    }
                }
            }
        }
    },
)
def get_uploaded_file(
    document_id: UUID,
    _: None = Depends(require_password),
) -> PlainTextResponse:
    try:
        contents = storage.get_document(str(document_id), prefix=config.UPLOAD_PREFIX)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to read from storage: {exc}",
        ) from exc

    if contents is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )
    return PlainTextResponse(_encode(contents))
