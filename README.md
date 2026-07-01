# Finguard

Password-protected FastAPI service with two endpoints:

1. **`POST /upload_doc`** — upload an original document (max 2 MB). The file is stored in a public Supabase Storage bucket and its link + metadata are recorded in the `upload_doc` table.
2. **`POST /analyzed_doc`** — upload the analyzed version (a file) of a previously uploaded document. It is stored in the same bucket and recorded in the `analyzed_doc` table, linked to the original via a foreign key.

Both endpoints require the password in the `X-API-Password` header (default `Finguard123`).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

### Database + bucket (one-time)

1. **Tables** — Supabase dashboard → SQL Editor → run `schema.sql` (fresh project) or `migration_storage.sql` (upgrading an older base64 `documents` table).
2. **Bucket** — `.venv\Scripts\python setup_storage.py`

## Run

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Usage

### Upload an original document

```bash
curl -X POST http://127.0.0.1:8000/upload_doc \
  -H "X-API-Password: Finguard123" \
  -F "file=@document.pdf"
```

```json
{
  "id": "b1e6...",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "file_url": "https://<ref>.supabase.co/storage/v1/object/public/documents/<uuid>/document.pdf",
  "storage_path": "<uuid>/document.pdf",
  "uploaded_at": "2026-07-01T09:00:00+00:00"
}
```

### Upload its analyzed version

Pass the `id` from the response above as `upload_doc_id`:

```bash
curl -X POST http://127.0.0.1:8000/analyzed_doc \
  -H "X-API-Password: Finguard123" \
  -F "upload_doc_id=b1e6..." \
  -F "file=@analyzed.pdf"
```

```json
{
  "id": "9f2c...",
  "upload_doc_id": "b1e6...",
  "filename": "analyzed.pdf",
  "content_type": "application/pdf",
  "size_bytes": 20480,
  "file_url": "https://<ref>.supabase.co/storage/v1/object/public/documents/analyzed/<uuid>/analyzed.pdf",
  "storage_path": "analyzed/<uuid>/analyzed.pdf",
  "created_at": "2026-07-01T09:05:00+00:00"
}
```

Status codes: `201` created, `401` bad/missing password, `413` file over 2 MB, `422` invalid body, `404` unknown `upload_doc_id`.

## Project layout

```
app/
  config.py     env + settings
  db.py         cached Supabase client
  storage.py    bucket + file upload
  main.py       FastAPI app and endpoints
schema.sql             fresh database setup
migration_storage.sql  upgrade an older base64 table
setup_storage.py       create the public bucket
```

## Security notes

- The storage bucket is public: anyone with a `file_url` can open that file.
- The `service_role` key bypasses RLS. It lives only in `.env` (gitignored) and is used server-side. Since it was shared in plaintext, rotate it (Supabase → Settings → API) before production.
