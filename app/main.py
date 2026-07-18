import base64
import binascii
import json
import secrets
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Body, Depends, FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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


class GovernmentUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_no: str = Field(min_length=1, max_length=255)
    doc_name: str = Field(min_length=1, max_length=255)
    base64: str = Field(min_length=1, description="The raw document as standard Base64.")

    @field_validator("reference_no", "doc_name")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        if any(ord(character) < 32 for character in normalized):
            raise ValueError("must not contain control characters")
        return normalized


class GovernmentUploadResponse(BaseModel):
    doc_id: str


class RawDocumentResponse(BaseModel):
    reference_no: str
    doc_name: str
    base64: str


class AnalysisScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fieldMatchingScore: float
    aiAnalysisScore: float
    patternAnalysisScore: float
    totalMatchesFound: int
    matchingMethod: str


class AnalysisHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    referenceNo: str
    billType: str
    docId: UUID
    processedAt: datetime
    duplicate: bool
    decision: str
    reason: str
    totalPages: int
    analysis: AnalysisScores


class AnalysisMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uploadedReferenceNo: str
    uploadeddocId: str
    uploadedPageNumber: int
    matchedReferenceNo: str
    matcheddocId: str
    matchedPageNumber: int
    similarityScore: float
    riskTier: str


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: AnalysisHeader
    topMatch: AnalysisMatch | None
    otherMatches: list[AnalysisMatch]


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


def _parse_analysis(
    contents: bytes,
    document_id: UUID,
    invalid_status: int,
) -> AnalysisResponse:
    try:
        data = json.loads(contents.decode("utf-8"))
        analysis = AnalysisResponse.model_validate(data)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=invalid_status,
            detail="The analyzed document must contain valid JSON matching the analysis response schema.",
        ) from exc

    if analysis.header.docId != document_id:
        raise HTTPException(
            status_code=invalid_status,
            detail="The analysis header docId must match the document_id in the endpoint URL.",
        )
    return analysis


@app.post(
    "/govt/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=GovernmentUploadResponse,
    tags=["Government"],
)
def upload_raw_document(
    request: GovernmentUploadRequest,
    _: None = Depends(require_govt_password),
) -> GovernmentUploadResponse:
    contents = _decode_payload(request.base64)
    try:
        document_id = storage.create_document(
            contents,
            prefix=config.UPLOAD_PREFIX,
            metadata={
                "reference_no": request.reference_no,
                "doc_name": request.doc_name,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload the raw document: {exc}",
        ) from exc
    return GovernmentUploadResponse(doc_id=document_id)


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
    response_model=AnalysisResponse,
    tags=["Government"],
)
def get_analyzed_document_for_govt(
    document_id: UUID,
    _: None = Depends(require_govt_password),
) -> AnalysisResponse:
    contents = _get_document(document_id, config.RESPONSE_PREFIX, "analyzed")
    return _parse_analysis(contents, document_id, status.HTTP_502_BAD_GATEWAY)


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
    response_model=RawDocumentResponse,
    tags=["Finguard"],
)
def get_raw_document_for_finguard(
    document_id: UUID,
    _: None = Depends(require_finguard_password),
) -> RawDocumentResponse:
    try:
        stored_document = storage.get_document_with_metadata(
            str(document_id),
            prefix=config.UPLOAD_PREFIX,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to read the raw document from storage: {exc}",
        ) from exc

    if stored_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The raw document for '{document_id}' was not found.",
        )

    contents, metadata = stored_document
    return RawDocumentResponse(
        reference_no=str(metadata.get("reference_no") or ""),
        doc_name=str(metadata.get("doc_name") or ""),
        base64=_encode(contents),
    )


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
    _parse_analysis(contents, document_id, status.HTTP_400_BAD_REQUEST)
    try:
        storage.store_document(
            contents,
            str(document_id),
            prefix=config.RESPONSE_PREFIX,
            content_type="application/json",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to upload the analyzed document: {exc}",
        ) from exc
    return DocumentIdResponse(document_id=document_id)
