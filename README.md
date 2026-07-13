# Finguard

Password-protected FastAPI service for storing arbitrary Base64 data in private Supabase Storage. Uploads return a document ID, and that ID can later retrieve the original Base64 value.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. The configured Supabase Storage bucket must exist and should be private.

## Run

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

## Base64 contract

- Encoding is standard Base64 with padding.
- Send only the encoded string. Do not add quotes, JSON, whitespace, or a `data:...;base64,` prefix.
- Any decoded content is accepted; it does not need to be a PDF.
- The 2 MB limit applies to the decoded bytes.
- One Base64 value is accepted per request.

### Upload Base64 data

`POST /upload` accepts a pasteable `text/plain` Base64 string and returns its generated document ID.

```bash
curl -X POST http://127.0.0.1:8000/upload \
  -H "X-API-Password: Finguard123" \
  -H "Content-Type: text/plain" \
  --data-binary "SGVsbG8sIFdvcmxkIQ=="
```

Response (`201 Created`):

```json
{
  "document_id": "b99ccf84-21dd-4e4c-90de-e11c4f915a1f"
}
```

### Retrieve a specific document

`GET /files/{document_id}` returns the stored value as a pure Base64 `text/plain` response.

```bash
curl http://127.0.0.1:8000/files/b99ccf84-21dd-4e4c-90de-e11c4f915a1f \
  -H "X-API-Password: Finguard123"
```

Response (`200 OK`):

```text
SGVsbG8sIFdvcmxkIQ==
```

Status codes: `201` created, `200` retrieved, `401` bad/missing password, `400` invalid or empty Base64, `404` unknown document ID, `413` decoded data over 2 MB, `422` missing body or invalid document ID, and `502` storage failure.

## Project layout

```text
app/
  config.py   environment settings
  db.py       cached Supabase client
  storage.py  private upload and ID-based download operations
  main.py     Base64 validation and API routes
```

## Security notes

- Keep the storage bucket private.
- The `service_role` key bypasses RLS. Keep it only in `.env`, which is gitignored.
- Base64 is an encoding, not encryption. Anyone who receives a Base64 response can decode its content.
