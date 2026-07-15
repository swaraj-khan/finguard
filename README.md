# Finguard Backend

This repository contains a password-protected FastAPI service that transfers Base64-encoded documents between two teams:

- **Government** uploads the original document and later retrieves its analyzed version.
- **Finguard** lists documents awaiting processing, retrieves each original, and uploads the analyzed result.

This README is the backend contract and implementation guide for developers and AI coding tools such as Claude and Cursor. Before changing an endpoint, read the **Backend invariants** and the complete contract for that endpoint.

## System model

One generated UUID links the original and analyzed versions for the entire workflow:

```text
Government upload
       │
       ▼
doc_id = b99ccf84-21dd-4e4c-90de-e11c4f915a1f
       │
       ├── uploaded_docs/{doc_id}/document.bin   original bytes
       │
       └── response_docs/{doc_id}/document.bin   analyzed bytes
```

The analyzed document must always be uploaded with the UUID of its original document. Do not generate a second UUID for the analyzed version.

The configured Supabase bucket is private. The API reads and writes objects using the service-role key; clients never receive a storage URL.

## Backend invariants

Future changes must preserve these rules unless the API contract is intentionally versioned:

1. The government upload generates the only document UUID.
2. Raw and analyzed objects use the same UUID and the fixed filename `document.bin`.
3. Raw objects live under `UPLOAD_PREFIX`; analyzed objects live under `RESPONSE_PREFIX`.
4. Government endpoints use `GOVT_API_PASSWORD`; Finguard endpoints use `FINGUARD_API_PASSWORD`.
5. Both teams send their password through `X-API-Password`.
6. Base64 is strictly validated before storage. Data URLs, whitespace, and non-Base64 characters are rejected.
7. The decoded-size limit is 2 MiB per document.
8. Any decoded binary content is allowed; documents do not need to be PDFs.
9. An analyzed upload is accepted only when its raw UUID exists.
10. Existing analyzed documents are not overwritten; a duplicate upload returns `409`.
11. `reference_no` and `doc_name` are metadata. The UUID—not either metadata value—is the raw/analyzed relationship key.

## Source layout

```text
app/
├── main.py      FastAPI models, authentication, validation, and routes
├── storage.py   Supabase object paths and storage operations
├── config.py    Environment-backed application settings
├── db.py        Cached Supabase client
└── __init__.py
.env.example     Required environment variable template
requirements.txt Runtime dependencies
```

When modifying behavior:

- Change request/response models and HTTP behavior in `app/main.py`.
- Change bucket paths or storage operations in `app/storage.py`.
- Add environment-backed settings in `app/config.py` and `.env.example` together.
- Update this README whenever an endpoint, field, status code, path, or invariant changes.

## Environment and deployment

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
GOVT_API_PASSWORD=your-government-secret
FINGUARD_API_PASSWORD=your-finguard-secret
STORAGE_BUCKET=documents
UPLOAD_PREFIX=uploaded_docs
RESPONSE_PREFIX=response_docs
```

Use different team passwords in production. The legacy `API_PASSWORD` variable is accepted as a fallback for both teams, but relying on it removes role separation.

Run locally:

```bash
uvicorn app.main:app --reload
```

Render start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- Local Swagger: `http://127.0.0.1:8000/docs`
- Deployed Swagger: `https://finguard-81qn.onrender.com/docs`
- Production base URL: `https://finguard-81qn.onrender.com`

## API conventions

### Authentication

Every endpoint requires:

```http
X-API-Password: TEAM_PASSWORD
```

Government endpoints reject the Finguard password and Finguard endpoints reject the government password when separate secrets are configured. An invalid or missing password returns:

```http
401 Unauthorized
Content-Type: application/json
```

```json
{
  "detail": "Invalid or missing government password (send it in the 'X-API-Password' header)."
}
```

### Base64 validation

- Use standard Base64 text, such as `SGVsbG8sIFdvcmxkIQ==`.
- Do not send a `data:application/pdf;base64,` prefix.
- Do not include line breaks or spaces inside the encoded value.
- Characters such as `#` and `$` are invalid Base64.
- Empty decoded content is rejected.
- The decoded content must be no larger than `2 * 1024 * 1024` bytes.

### Error shape

Application errors generally use FastAPI's standard JSON shape:

```json
{
  "detail": "Human-readable error message"
}
```

Request-schema validation errors use FastAPI's `detail` array and return `422`.

## Endpoint summary

| Team | Method | Endpoint | Request body | Success response |
|---|---|---|---|---|
| Government | `POST` | `/govt/documents` | JSON metadata and Base64 | `201` JSON with `doc_id` |
| Government | `GET` | `/govt/documents` | None | `200` JSON UUID array |
| Government | `GET` | `/govt/documents/{document_id}/analyzed` | None | `200` Base64 as `text/plain` |
| Finguard | `GET` | `/finguard/documents/pending` | None | `200` JSON UUID array |
| Finguard | `GET` | `/finguard/documents/{document_id}/raw` | None | `200` Base64 as `text/plain` |
| Finguard | `POST` | `/finguard/documents/{document_id}/analyzed` | Base64 as `text/plain` | `201` JSON with `document_id` |

## Complete endpoint contracts

### 1. Government uploads an original document

```http
POST /govt/documents
X-API-Password: GOVERNMENT_PASSWORD
Content-Type: application/json
```

Request body:

```json
{
  "reference_no": "20261234",
  "doc_name": "Test_file",
  "base64": "SGVsbG8sIFdvcmxkIQ=="
}
```

| Field | Type | Required | Validation | Meaning |
|---|---|---|---|---|
| `reference_no` | string | Yes | Input length 1–255; trimmed value must be nonblank; no control characters | External government reference |
| `doc_name` | string | Yes | Input length 1–255; trimmed value must be nonblank; no control characters | Human-readable document name |
| `base64` | string | Yes | Valid standard Base64; non-empty decoded bytes; decoded size ≤ 2 MiB | Original document content |

Unknown JSON fields are rejected with `422`.

Success:

```http
201 Created
Content-Type: application/json
```

```json
{
  "doc_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

Storage effect:

```text
uploaded_docs/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/document.bin
```

The raw object metadata contains:

```json
{
  "reference_no": "20261234",
  "doc_name": "Test_file"
}
```

Example:

```bash
curl -X POST "https://finguard-81qn.onrender.com/govt/documents" \
  -H "X-API-Password: GOVERNMENT_PASSWORD" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "reference_no": "20261234",
    "doc_name": "Test_file",
    "base64": "SGVsbG8sIFdvcmxkIQ=="
  }'
```

Expected errors:

| Status | Condition |
|---|---|
| `400` | Invalid Base64 or decoded content is empty |
| `401` | Missing or invalid government password |
| `413` | Decoded content exceeds 2 MiB |
| `422` | Missing field, wrong type, blank metadata, malformed JSON, or extra JSON field |
| `502` | Supabase upload failure |

Important compatibility detail: this endpoint returns the field name `doc_id`, not `document_id`.

### 2. Government lists uploaded document IDs

```http
GET /govt/documents
X-API-Password: GOVERNMENT_PASSWORD
```

There are no query parameters and no request body.

Success:

```http
200 OK
Content-Type: application/json
```

```json
[
  "70719f8b-1d36-4b03-8b6a-1acccc665432",
  "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
]
```

The endpoint lists UUID-named folders under `UPLOAD_PREFIX`. Non-UUID storage entries are ignored. Storage listing is paginated in batches of 1000.

Expected errors:

| Status | Condition |
|---|---|
| `401` | Missing or invalid government password |
| `502` | Supabase listing failure |

This endpoint currently returns IDs only. It does not return `reference_no`, `doc_name`, processing state, or Base64 content.

### 3. Government retrieves an analyzed document

```http
GET /govt/documents/{document_id}/analyzed
X-API-Password: GOVERNMENT_PASSWORD
```

Path parameter:

| Parameter | Type | Meaning |
|---|---|---|
| `document_id` | UUID string | The `doc_id` returned by the original government upload |

Success:

```http
200 OK
Content-Type: text/plain; charset=utf-8
```

```text
UFJFUFJPQ0VTU0VEX0RPQ1VNRU5U
```

The response body is only the analyzed document's Base64 string. It is not a JSON object and is not the decoded file bytes.

Storage read:

```text
response_docs/{document_id}/document.bin
```

Expected errors:

| Status | Condition |
|---|---|
| `401` | Missing or invalid government password |
| `404` | Finguard has not uploaded the analyzed version for this UUID |
| `422` | `document_id` is not a valid UUID |
| `502` | Supabase existence check or download failure |

The government client should retain `doc_id` from endpoint 1 and poll this endpoint if the workflow is asynchronous. A `404` means “not available yet” or “unknown analyzed UUID”; it does not trigger processing automatically.

### 4. Finguard lists documents pending analysis

```http
GET /finguard/documents/pending
X-API-Password: FINGUARD_PASSWORD
```

There are no query parameters and no request body.

Success:

```http
200 OK
Content-Type: application/json
```

```json
[
  "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
]
```

Pending IDs are calculated as:

```text
UUID folders in uploaded_docs - UUID folders in response_docs
```

The returned list is sorted lexicographically. An ID disappears after an analyzed object exists under `RESPONSE_PREFIX`.

Expected errors:

| Status | Condition |
|---|---|
| `401` | Missing or invalid Finguard password |
| `502` | Supabase listing failure |

Current limitation: this is a derived pending list, not a queue or claim/lock mechanism. Multiple workers can read the same pending ID concurrently.

### 5. Finguard retrieves one original document

```http
GET /finguard/documents/{document_id}/raw
X-API-Password: FINGUARD_PASSWORD
```

Path parameter:

| Parameter | Type | Meaning |
|---|---|---|
| `document_id` | UUID string | An ID returned by the pending endpoint |

Success:

```http
200 OK
Content-Type: text/plain; charset=utf-8
```

```text
SGVsbG8sIFdvcmxkIQ==
```

The response body is only the original document's Base64 string. Decode it before preprocessing.

Storage read:

```text
uploaded_docs/{document_id}/document.bin
```

Expected errors:

| Status | Condition |
|---|---|
| `401` | Missing or invalid Finguard password |
| `404` | No raw object exists for this UUID |
| `422` | `document_id` is not a valid UUID |
| `502` | Supabase existence check or download failure |

### 6. Finguard uploads the analyzed document

```http
POST /finguard/documents/{document_id}/analyzed
X-API-Password: FINGUARD_PASSWORD
Content-Type: text/plain
```

Path parameter:

| Parameter | Type | Meaning |
|---|---|---|
| `document_id` | UUID string | The UUID of the raw document that was processed |

Request body:

```text
UFJFUFJPQ0VTU0VEX0RPQ1VNRU5U
```

The body must be the analyzed document as plain Base64. Do not wrap it in JSON.

Success:

```http
201 Created
Content-Type: application/json
```

```json
{
  "document_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

Storage effect:

```text
response_docs/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/document.bin
```

Expected errors:

| Status | Condition |
|---|---|
| `400` | Invalid Base64 or decoded content is empty |
| `401` | Missing or invalid Finguard password |
| `404` | Matching raw UUID does not exist under `UPLOAD_PREFIX` |
| `409` | An analyzed object already exists under `RESPONSE_PREFIX` |
| `413` | Decoded analyzed content exceeds 2 MiB |
| `422` | Invalid UUID or missing/incorrectly typed body |
| `502` | Supabase existence check or upload failure |

Important compatibility detail: unlike the government upload response, this endpoint returns `document_id`, not `doc_id`.

## End-to-end example

Given a government upload response:

```json
{
  "doc_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

The full handoff is:

```text
1. GET  /finguard/documents/pending
2. GET  /finguard/documents/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/raw
3. Finguard decodes, preprocesses, and Base64-encodes the result
4. POST /finguard/documents/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/analyzed
5. GET  /govt/documents/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/analyzed
```

No endpoint in this repository performs the actual document preprocessing. That work belongs to the external Finguard processor.

## Guidance for Claude, Cursor, and other coding agents

Use this checklist before making backend changes:

1. Read `app/main.py`, `app/storage.py`, `app/config.py`, and this README.
2. Identify which team's contract is changing and preserve the other team's authentication boundary.
3. Keep request content types explicit. Government upload is JSON; Finguard analyzed upload is plain text.
4. Preserve the same-UUID relationship between raw and analyzed objects.
5. Never use `reference_no` or `doc_name` as an object path without explicit sanitization and a migration plan.
6. Never expose `SUPABASE_SERVICE_ROLE_KEY` or generate public storage URLs.
7. Preserve `upsert: false` unless overwrite/version behavior is explicitly requested.
8. When adding a field, update the Pydantic model, storage metadata if needed, OpenAPI behavior, examples, and this README.
9. When adding a setting, update both `app/config.py` and `.env.example`.
10. Compile the app and test success, authentication, validation, not-found, duplicate, size-limit, and storage-failure paths.
11. Run `git diff --check` and avoid altering unrelated user changes.

Suggested verification commands:

```bash
python -m compileall -q app
git diff --check
```

This repository currently has no committed automated test suite. Add focused tests when changing behavior. If a `tests/` directory is added, run it with:

```bash
python -m unittest discover -s tests -v
```

There is currently no durable queue, database metadata table, processing lease, retry state, callback, deletion endpoint, or analyzed-document version history. If a requested change needs one of these capabilities, design it explicitly instead of inferring it from the storage folders.

## Security notes

- Store secrets only in `.env` locally and Render environment variables in deployment.
- Keep `.env` out of version control.
- Use separate team passwords in production.
- Keep the Supabase bucket private.
- The Supabase service-role key bypasses RLS and must never reach clients.
- Base64 is encoding, not encryption.
