# Finguard

Password-protected FastAPI service that uploads one or more PDFs to a public Supabase Storage bucket and lists them back.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

Create the storage bucket once:

```bash
.venv\Scripts\python setup_storage.py
```

## Run

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

## Usage

`POST /upload` — send one or more PDFs (max 2 MB each) in the `files` field, with the password in the `X-API-Password` header.

```bash
curl -X POST http://127.0.0.1:8000/upload \
  -H "X-API-Password: Finguard123" \
  -F "files=@report1.pdf" \
  -F "files=@report2.pdf"
```

```json
{
  "count": 2,
  "files": [
    {"filename": "report1.pdf", "size_bytes": 12345, "file_url": "https://<ref>.supabase.co/storage/v1/object/public/documents/uploaded_docs/<uuid>/report1.pdf"},
    {"filename": "report2.pdf", "size_bytes": 24680, "file_url": "https://<ref>.supabase.co/storage/v1/object/public/documents/uploaded_docs/<uuid>/report2.pdf"}
  ]
}
```

If any file is not a PDF or is too large, the whole request is rejected and nothing is uploaded.

### List uploaded files

`GET /files` — returns every file in the bucket with its public URL, newest first.

```bash
curl http://127.0.0.1:8000/files -H "X-API-Password: Finguard123"
```

```json
{
  "count": 2,
  "files": [
    {"filename": "report1.pdf", "path": "uploaded_docs/<uuid>/report1.pdf", "size_bytes": 12345, "uploaded_at": "2026-07-03T10:00:00Z", "file_url": "https://<ref>.supabase.co/storage/v1/object/public/documents/uploaded_docs/<uuid>/report1.pdf"}
  ]
}
```

Open a `file_url` in a browser to view the PDF.

Status codes: `201` created, `401` bad/missing password, `400` non-PDF or empty file, `413` file over 2 MB, `422` no files.

## Project layout

```
app/
  config.py     env + settings
  db.py         cached Supabase client
  storage.py    bucket + file upload
  main.py       FastAPI app: /upload and /files
setup_storage.py  create the public bucket
```

## Security notes

- The storage bucket is public: anyone with a `file_url` can open that file.
- The `service_role` key bypasses RLS. It lives only in `.env` (gitignored) and is used server-side. Since it was shared in plaintext, rotate it (Supabase → Settings → API) before production.
