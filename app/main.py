import base64
import binascii
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.responses import PlainTextResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from . import config, storage

app = FastAPI(title="Finguard Document Processing API", version="4.0.0")

_govt_password_header = APIKeyHeader(
    name="X-API-Password",
    scheme_name="GovernmentPassword",
    auto_error=False,
)
_finguard_password_header = APIKeyHeader(
    name="X-API-Password",
    scheme_name="FinguardPassword",
    auto_error=False,
)


class DocumentIdResponse(BaseModel):
    document_id: UUID


class GovernmentUploadResponse(DocumentIdResponse):
    reference: str


def _require_team_password(password: str | None, expected: str, team: str) -> None:
    if not password or not secrets.compare_digest(password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or missing {team} password (send it in the 'X-API-Password' header).",
        )


def require_govt_password(
    password: str | None = Security(_govt_password_header),
) -> None:
    _require_team_password(password, config.GOVT_API_PASSWORD, "government")


def require_finguard_password(
    password: str | None = Security(_finguard_password_header),
) -> None:
    _require_team_password(password, config.FINGUARD_API_PASSWORD, "Finguard")


def _decode_payload(payload: str) -> bytes:
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The Base64 payload is empty.")

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


def _build_reference(bill_number: int, document_name: str) -> tuple[str, str]:
    normalized_name = document_name.strip()
    if not normalized_name:
        raise HTTPException(
            status_code=422,
            detail="The document name cannot be blank.",
        )
    if "/" in normalized_name or "\\" in normalized_name:
        raise HTTPException(
            status_code=422,
            detail="The document name cannot contain '/' or '\\'.",
        )
    if any(ord(character) < 32 for character in normalized_name):
        raise HTTPException(
            status_code=422,
            detail="The document name cannot contain control characters.",
        )
    return normalized_name, f"{bill_number}/{normalized_name}"


def _get_document(document_id: UUID, prefix: str, version: str) -> bytes:
    try:
        contents = storage.get_document(str(document_id), prefix=prefix)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to read the {version} document from storage: {exc}",
        ) from exc

    if contents is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The {version} document for '{document_id}' was not found.",
        )
    return contents


def _document_exists(document_id: UUID, prefix: str) -> bool:
    try:
        return storage.document_exists(str(document_id), prefix=prefix)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to check document storage: {exc}",
        ) from exc


def _base64_body(description: str) -> dict:
    return {
        status.HTTP_200_OK: {
            "content": {
                "text/plain": {
                    "schema": {
                        "type": "string",
                        "description": description,
                    }
                }
            }
        }
    }


@app.post(
    "/govt/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=GovernmentUploadResponse,
    tags=["Government"],
)
def upload_raw_document(
    bill_number: Annotated[
        int,
        Query(ge=0, description="The government bill number."),
    ],
    document_name: Annotated[
        str,
        Query(min_length=1, max_length=255, description="The document name used in the reference."),
    ],
    payload: Annotated[
        str,
        Body(
            media_type="text/plain",
            description="A raw document encoded as plain standard Base64 (no data-URL prefix).",
        ),
    ],
    _: None = Depends(require_govt_password),
) -> GovernmentUploadResponse:
    normalized_name, reference = _build_reference(bill_number, document_name)
    contents = _decode_payload(payload)
    try:
        document_id = storage.create_document(
            contents,
            prefix=config.UPLOAD_PREFIX,
            metadata={
                "bill_number": bill_number,
                "document_name": normalized_name,
                "reference": reference,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload the raw document: {exc}",
        ) from exc
    return GovernmentUploadResponse(document_id=document_id, reference=reference)


@app.get(
    "/govt/documents",
    response_model=list[UUID],
    tags=["Government"],
)
def list_government_document_ids(
    _: None = Depends(require_govt_password),
) -> list[UUID]:
    try:
        document_ids = storage.list_document_ids(prefix=config.UPLOAD_PREFIX)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list government documents: {exc}",
        ) from exc
    return [UUID(document_id) for document_id in document_ids]


@app.get(
    "/govt/documents/{document_id}/analyzed",
    response_class=PlainTextResponse,
    responses=_base64_body("The analyzed document as a standard Base64 string."),
    tags=["Government"],
)
def get_analyzed_document_for_govt(
    document_id: UUID,
    _: None = Depends(require_govt_password),
) -> PlainTextResponse:
    contents = _get_document(document_id, config.RESPONSE_PREFIX, "analyzed")
    return PlainTextResponse(_encode(contents))


@app.get(
    "/finguard/documents/pending",
    response_model=list[UUID],
    tags=["Finguard"],
)
def list_pending_documents(
    _: None = Depends(require_finguard_password),
) -> list[UUID]:
    try:
        raw_ids = set(storage.list_document_ids(prefix=config.UPLOAD_PREFIX))
        analyzed_ids = set(storage.list_document_ids(prefix=config.RESPONSE_PREFIX))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list pending documents: {exc}",
        ) from exc

    return [UUID(document_id) for document_id in sorted(raw_ids - analyzed_ids)]


@app.get(
    "/finguard/documents/{document_id}/raw",
    response_class=PlainTextResponse,
    responses=_base64_body("The raw government document as a standard Base64 string."),
    tags=["Finguard"],
)
def get_raw_document_for_finguard(
    document_id: UUID,
    _: None = Depends(require_finguard_password),
) -> PlainTextResponse:
    contents = _get_document(document_id, config.UPLOAD_PREFIX, "raw")
    return PlainTextResponse(_encode(contents))


@app.post(
    "/finguard/documents/{document_id}/analyzed",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentIdResponse,
    tags=["Finguard"],
)
def upload_analyzed_document(
    document_id: UUID,
    payload: Annotated[
        str,
        Body(
            media_type="text/plain",
            description="The analyzed document encoded as plain standard Base64 (no data-URL prefix).",
        ),
    ],
    _: None = Depends(require_finguard_password),
) -> DocumentIdResponse:
    if not _document_exists(document_id, config.UPLOAD_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The raw document '{document_id}' was not found.",
        )
    if _document_exists(document_id, config.RESPONSE_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An analyzed document already exists for '{document_id}'.",
        )

    contents = _decode_payload(payload)
    try:
        storage.store_document(contents, str(document_id), prefix=config.RESPONSE_PREFIX)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload the analyzed document: {exc}",
        ) from exc
    return DocumentIdResponse(document_id=document_id)
