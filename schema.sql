create extension if not exists "pgcrypto";

create table if not exists public.upload_doc (
    id           uuid        primary key default gen_random_uuid(),
    filename     text        not null,
    content_type text,
    size_bytes   bigint      not null,
    storage_path text,
    file_url     text,
    uploaded_at  timestamptz not null default now()
);

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
