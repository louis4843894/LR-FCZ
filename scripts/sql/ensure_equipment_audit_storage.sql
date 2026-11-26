-- Only create missing equipment audit storage; existing objects/data/policies are untouched.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $equipment_audit$
BEGIN
    IF to_regclass('public.ranger_research_snapshots') IS NULL THEN
        create table if not exists public.ranger_research_snapshots (
            snapshot_id text not null,
            module text not null check (
                module in ('characters', 'equipment', 'abilities', 'pvp', 'guild')
            ),
            source_kind text not null check (source_kind in ('static', 'dynamic')),
            source_version text,
            captured_at timestamptz not null,
            source_manifest_sha256 text not null,
            content_sha256 text not null check (content_sha256 ~ '^[0-9a-fA-F]{64}$'),
            record_count integer not null check (record_count >= 0),
            source_metadata jsonb not null default '{}'::jsonb,
            expected_counts jsonb not null default '{}'::jsonb
                check (jsonb_typeof(expected_counts) = 'object'),
            is_complete boolean not null default false,
            status text not null default 'draft'
                check (status in ('draft', 'published', 'archived', 'failed')),
            published_at timestamptz,
            created_at timestamptz not null default now(),
            primary key (snapshot_id, module),
            check (
                source_manifest_sha256 ~ '^[0-9a-fA-F]{64}$'
            )
        );
        ALTER TABLE public.ranger_research_snapshots ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.ranger_research_snapshots FROM public, anon, authenticated;
        GRANT ALL ON public.ranger_research_snapshots TO service_role;
    END IF;
    IF to_regclass('public.ranger_research_records') IS NULL THEN
        create table if not exists public.ranger_research_records (
            snapshot_id text not null,
            module text not null,
            source_record_identity jsonb not null,
            source_file text not null,
            source_file_sha256 text not null check (
                source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
            ),
            source_record_locator text,
            raw_record jsonb not null,
            normalized_record jsonb,
            record_sha256 text not null check (record_sha256 ~ '^[0-9a-fA-F]{64}$'),
            validation_status text not null,
            parse_warnings jsonb not null default '[]'::jsonb
                check (jsonb_typeof(parse_warnings) = 'array'),
            primary key (snapshot_id, module, source_record_identity),
            foreign key (snapshot_id, module)
                references public.ranger_research_snapshots (snapshot_id, module)
                on delete restrict
        );
        ALTER TABLE public.ranger_research_records ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.ranger_research_records FROM public, anon, authenticated;
        GRANT ALL ON public.ranger_research_records TO service_role;
    END IF;
    IF to_regclass('public.ranger_equipment') IS NULL THEN
        create table if not exists public.ranger_equipment (
            snapshot_id text not null,
            module text not null default 'equipment' check (module = 'equipment'),
            game_id text,
            language text,
            source_record_identity jsonb not null,
            source_file text not null,
            source_file_sha256 text not null check (
                source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
            ),
            payload jsonb not null,
            validation_status text not null,
            primary key (snapshot_id, source_record_identity),
            foreign key (snapshot_id, module)
                references public.ranger_research_snapshots (snapshot_id, module)
                on delete restrict
        );
        ALTER TABLE public.ranger_equipment ENABLE ROW LEVEL SECURITY;
        REVOKE ALL ON public.ranger_equipment FROM public, anon, authenticated;
        GRANT ALL ON public.ranger_equipment TO service_role;
    END IF;
END;
$equipment_audit$;
NOTIFY pgrst, 'reload schema';
COMMIT;
