alter table if exists public.documents rename to upload_doc;

alter table public.upload_doc
    add column if not exists storage_path text,
    add column if not exists file_url     text;

alter table public.upload_doc drop column if exists content_base64;

create table if not exists public.analyzed_doc (
    id            uuid        primary key default gen_random_uuid(),
    upload_doc_id uuid        not null references public.upload_doc(id) on delete cascade,
    filename      text        not null,
    content_type  text,
    size_bytes    bigint      not null,
    storage_path  text,
    file_url      text,
    created_at    timestamptz not null default now()
);

create index if not exists analyzed_doc_upload_doc_id_idx on public.analyzed_doc(upload_doc_id);

alter table public.upload_doc   enable row level security;
alter table public.analyzed_doc enable row level security;
