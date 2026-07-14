# Finguard

Password-protected Base64 document handoff API for two teams:

- The government team uploads raw documents.
- The Finguard team retrieves pending raw documents, preprocesses them, and uploads analyzed versions.
- The government team retrieves the analyzed version using the original document ID.

Both versions share one UUID, so an analyzed document cannot be confused with another raw document:

```text
documents bucket
├── uploaded_docs/{document_id}/document.bin   raw government upload
└── response_docs/{document_id}/document.bin   matching Finguard response
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the Supabase credentials and two different team passwords. The `documents` bucket must exist and should be private.

For Render, configure the same values under **Environment** and use:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Local Swagger UI: http://127.0.0.1:8000/docs

Deployed Swagger UI: https://finguard-81qn.onrender.com/docs

## Base64 contract

- Request document bodies use `text/plain` and contain only standard Base64.
- Do not add quotes, JSON, whitespace, or a `data:...;base64,` prefix.
- Any decoded content is accepted; it does not need to be a PDF.
- The 2 MB limit applies to decoded bytes.

## Workflow

All examples below use `https://finguard-81qn.onrender.com` as the base URL.

### 1. Government uploads a raw document

```bash
curl -X POST "https://finguard-81qn.onrender.com/govt/documents?bill_number=123&document_name=abc456" \
  -H "X-API-Password: GOVERNMENT_PASSWORD" \
  -H "Content-Type: text/plain" \
  --data-binary "SGVsbG8sIFdvcmxkIQ=="
```

Response:

```json
{
  "document_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f",
  "reference": "123/abc456"
}
```

`bill_number` must be a non-negative integer. `document_name` can contain up to 255 characters but cannot contain `/`, `\`, or control characters. Leading and trailing whitespace is removed.

The government team must retain the UUID to retrieve the matching analyzed document. `reference` is the human-facing bill/document identifier. The raw bytes are stored at `uploaded_docs/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/document.bin`, with the bill number, document name, and reference saved as object metadata.

The government team can also list all of its uploaded document IDs:

```bash
curl "https://finguard-81qn.onrender.com/govt/documents" \
  -H "X-API-Password: GOVERNMENT_PASSWORD"
```

### 2. Finguard lists documents awaiting analysis

```bash
curl "https://finguard-81qn.onrender.com/finguard/documents/pending" \
  -H "X-API-Password: FINGUARD_PASSWORD"
```

Response:

```json
[
  "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
]
```

An ID disappears from this list after its analyzed version is uploaded.

### 3. Finguard retrieves one raw document

```bash
curl "https://finguard-81qn.onrender.com/finguard/documents/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/raw" \
  -H "X-API-Password: FINGUARD_PASSWORD"
```

Response body:

```text
SGVsbG8sIFdvcmxkIQ==
```

### 4. Finguard uploads the analyzed version

Finguard uses the same ID from the raw document:

```bash
curl -X POST "https://finguard-81qn.onrender.com/finguard/documents/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/analyzed" \
  -H "X-API-Password: FINGUARD_PASSWORD" \
  -H "Content-Type: text/plain" \
  --data-binary "UFJFUFJPQ0VTU0VEX0RPQ1VNRU5U"
```

Response:

```json
{
  "document_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

The response is stored at `response_docs/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/document.bin`.

The API returns `404` if Finguard uses an ID that has no matching raw document and `409` if an analyzed version already exists.

### 5. Government retrieves the correct analyzed document

The government team calls the analyzed endpoint with the same ID received in step 1:

```bash
curl "https://finguard-81qn.onrender.com/govt/documents/b99ccf84-21dd-4e4c-90de-e11c4f915a1f/analyzed" \
  -H "X-API-Password: GOVERNMENT_PASSWORD"
```

Response body:

```text
UFJFUFJPQ0VTU0VEX0RPQ1VNRU5U
```

Until Finguard uploads the matching analyzed version, this endpoint returns `404`.

## Endpoint summary

| Team | Method | Endpoint | Purpose |
|---|---|---|---|
| Government | `POST` | `/govt/documents?bill_number={number}&document_name={name}` | Upload raw Base64 and receive an ID and reference |
| Government | `GET` | `/govt/documents` | List every uploaded raw document ID |
| Government | `GET` | `/govt/documents/{id}/analyzed` | Retrieve the matching analyzed Base64 |
| Finguard | `GET` | `/finguard/documents/pending` | List raw IDs without analyzed responses |
| Finguard | `GET` | `/finguard/documents/{id}/raw` | Retrieve one raw Base64 document |
| Finguard | `POST` | `/finguard/documents/{id}/analyzed` | Store analyzed Base64 under the same ID |

## Security notes

- Set different `GOVT_API_PASSWORD` and `FINGUARD_API_PASSWORD` values in production.
- Keep the Supabase bucket private.
- Keep `SUPABASE_SERVICE_ROLE_KEY` secret; it bypasses RLS.
- Base64 is encoding, not encryption.
