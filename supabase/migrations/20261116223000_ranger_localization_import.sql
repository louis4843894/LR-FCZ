BEGIN;

CREATE TABLE IF NOT EXISTS public.ranger_dataset_versions (
    snapshot_id text PRIMARY KEY
        CHECK (snapshot_id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'),
    package_name text NOT NULL,
    source_version text NOT NULL,
    source_manifest_sha256 text NOT NULL
        CHECK (source_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    source_file text NOT NULL,
    source_file_sha256 text NOT NULL
        CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    content_sha256 text NOT NULL
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    record_count integer NOT NULL CHECK (record_count > 0),
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    CHECK (
        (status = 'draft' AND published_at IS NULL)
        OR (status IN ('published', 'archived') AND published_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS ranger_one_published_dataset
    ON public.ranger_dataset_versions ((status))
    WHERE status = 'published';

CREATE TABLE IF NOT EXISTS public.ranger_equip_localizations (
    snapshot_id text NOT NULL
        REFERENCES public.ranger_dataset_versions(snapshot_id) ON DELETE RESTRICT,
    data_code text NOT NULL CHECK (length(data_code) > 0),
    language text NOT NULL CHECK (length(language) > 0),
    msg_type text,
    message text,
    source_file text NOT NULL,
    source_archive_member text NOT NULL,
    source_file_sha256 text NOT NULL
        CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    source_record_identity jsonb NOT NULL
        CHECK (jsonb_typeof(source_record_identity) = 'object'),
    validation_status text NOT NULL,
    parse_warnings jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(parse_warnings) = 'array'),
    raw_record jsonb NOT NULL CHECK (jsonb_typeof(raw_record) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_id, data_code, language),
    CHECK (
        source_record_identity->>'dataCode' IS NOT DISTINCT FROM data_code
    ),
    CHECK (
        source_record_identity->>'language' IS NOT DISTINCT FROM language
    ),
    CHECK (raw_record->>'snapshotId' IS NOT DISTINCT FROM snapshot_id)
);

COMMENT ON TABLE public.ranger_dataset_versions IS
    'Versioned snapshots of verified, normalized LINE Rangers data.';
COMMENT ON TABLE public.ranger_equip_localizations IS
    'Verified lang_equip localization rows; these are not equipment item records.';

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

ALTER TABLE public.ranger_dataset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ranger_equip_localizations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ranger_versions_read_published
    ON public.ranger_dataset_versions;
CREATE POLICY ranger_versions_read_published
    ON public.ranger_dataset_versions
    FOR SELECT
    TO anon, authenticated
    USING (status = 'published');

DROP POLICY IF EXISTS ranger_equip_localizations_read_published
    ON public.ranger_equip_localizations;
CREATE POLICY ranger_equip_localizations_read_published
    ON public.ranger_equip_localizations
    FOR SELECT
    TO anon, authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.ranger_dataset_versions AS version
            WHERE version.snapshot_id = ranger_equip_localizations.snapshot_id
              AND version.status = 'published'
        )
    );

REVOKE ALL ON TABLE public.ranger_dataset_versions
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON TABLE public.ranger_equip_localizations
    FROM PUBLIC, anon, authenticated;
REVOKE SELECT (
    source_manifest_sha256, source_file, source_file_sha256, content_sha256
) ON TABLE public.ranger_dataset_versions FROM PUBLIC, anon, authenticated;
REVOKE SELECT (
    source_file, source_archive_member, source_file_sha256,
    source_record_identity, validation_status, parse_warnings, raw_record
) ON TABLE public.ranger_equip_localizations FROM PUBLIC, anon, authenticated;
GRANT SELECT (
    snapshot_id, package_name, source_version, record_count, status, published_at
) ON TABLE public.ranger_dataset_versions TO anon, authenticated;
GRANT SELECT (
    snapshot_id, data_code, language, msg_type, message
) ON TABLE public.ranger_equip_localizations TO anon, authenticated;
GRANT ALL ON TABLE public.ranger_dataset_versions TO service_role;
GRANT ALL ON TABLE public.ranger_equip_localizations TO service_role;

CREATE OR REPLACE FUNCTION public.ranger_ensure_equip_localization_draft(
    p_snapshot_id text,
    p_package_name text,
    p_source_version text,
    p_source_manifest_sha256 text,
    p_source_file text,
    p_source_file_sha256 text,
    p_content_sha256 text,
    p_record_count integer
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    existing_version public.ranger_dataset_versions%ROWTYPE;
BEGIN
    IF p_record_count <= 0 THEN
        RAISE EXCEPTION 'record count must be positive';
    END IF;

    INSERT INTO public.ranger_dataset_versions (
        snapshot_id,
        package_name,
        source_version,
        source_manifest_sha256,
        source_file,
        source_file_sha256,
        content_sha256,
        record_count,
        status
    )
    VALUES (
        p_snapshot_id,
        p_package_name,
        p_source_version,
        p_source_manifest_sha256,
        p_source_file,
        p_source_file_sha256,
        p_content_sha256,
        p_record_count,
        'draft'
    )
    ON CONFLICT (snapshot_id) DO NOTHING;

    SELECT *
    INTO existing_version
    FROM public.ranger_dataset_versions
    WHERE snapshot_id = p_snapshot_id
    FOR UPDATE;

    IF existing_version.content_sha256 IS DISTINCT FROM p_content_sha256
       OR existing_version.package_name IS DISTINCT FROM p_package_name
       OR existing_version.source_version IS DISTINCT FROM p_source_version
       OR existing_version.source_manifest_sha256
            IS DISTINCT FROM p_source_manifest_sha256
       OR existing_version.source_file IS DISTINCT FROM p_source_file
       OR existing_version.source_file_sha256 IS DISTINCT FROM p_source_file_sha256
       OR existing_version.record_count IS DISTINCT FROM p_record_count THEN
        RAISE EXCEPTION
            'snapshot ID already exists with different source or normalized content';
    END IF;

    IF existing_version.status = 'published' THEN
        RETURN 'published';
    END IF;

    UPDATE public.ranger_dataset_versions
    SET status = 'draft',
        published_at = NULL
    WHERE snapshot_id = p_snapshot_id;

    RETURN 'draft';
END;
$$;

CREATE OR REPLACE FUNCTION public.ranger_publish_equip_localization_snapshot(
    p_snapshot_id text
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    target_version public.ranger_dataset_versions%ROWTYPE;
    actual_count bigint;
BEGIN
    SELECT *
    INTO target_version
    FROM public.ranger_dataset_versions
    WHERE snapshot_id = p_snapshot_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'snapshot does not exist';
    END IF;

    IF target_version.status = 'published' THEN
        RETURN 'published';
    END IF;

    IF target_version.status <> 'draft' THEN
        RAISE EXCEPTION 'only a draft snapshot can be published';
    END IF;

    SELECT count(*)
    INTO actual_count
    FROM public.ranger_equip_localizations
    WHERE snapshot_id = p_snapshot_id;

    IF actual_count <> target_version.record_count THEN
        RAISE EXCEPTION
            'row count mismatch: expected %, found %',
            target_version.record_count,
            actual_count;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.ranger_equip_localizations AS localization
        WHERE localization.snapshot_id = p_snapshot_id
          AND (
              localization.validation_status <> 'source-row-verified'
              OR localization.source_file_sha256
                    <> target_version.source_file_sha256
              OR localization.source_record_identity->>'dataCode'
                    IS DISTINCT FROM localization.data_code
              OR localization.source_record_identity->>'language'
                    IS DISTINCT FROM localization.language
              OR localization.raw_record->>'snapshotId'
                    IS DISTINCT FROM p_snapshot_id
          )
    ) THEN
        RAISE EXCEPTION 'snapshot contains unverified or inconsistent rows';
    END IF;

    UPDATE public.ranger_dataset_versions
    SET status = 'archived'
    WHERE status = 'published'
      AND snapshot_id <> p_snapshot_id;

    UPDATE public.ranger_dataset_versions
    SET status = 'published',
        published_at = now()
    WHERE snapshot_id = p_snapshot_id;

    RETURN 'published';
END;
$$;

CREATE OR REPLACE FUNCTION public.ranger_search_equip_localizations(
    p_snapshot_id text,
    p_language text,
    p_query text,
    p_page integer,
    p_page_size integer
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
    normalized_query text := NULLIF(btrim(p_query), '');
BEGIN
    IF p_snapshot_id IS NULL OR p_language IS NULL
       OR p_page IS NULL OR p_page_size IS NULL
       OR p_page < 1 OR p_page > 1000000
       OR p_page_size < 1 OR p_page_size > 50
       OR length(normalized_query) > 100 THEN
        RAISE EXCEPTION 'invalid search or pagination parameters';
    END IF;

    RETURN (
        WITH filtered AS (
            SELECT
                localization.snapshot_id,
                localization.data_code,
                localization.language,
                localization.msg_type,
                localization.message
            FROM public.ranger_equip_localizations AS localization
            WHERE localization.snapshot_id = p_snapshot_id
              AND localization.language = p_language
              AND (
                  normalized_query IS NULL
                  OR strpos(
                      lower(localization.data_code),
                      lower(normalized_query)
                  ) > 0
                  OR strpos(
                      lower(COALESCE(localization.message, '')),
                      lower(normalized_query)
                  ) > 0
              )
        )
        SELECT jsonb_build_object(
            'totalCount',
            (SELECT count(*) FROM filtered),
            'items',
            COALESCE(
                (
                    SELECT jsonb_agg(
                        to_jsonb(page_rows)
                        ORDER BY page_rows.data_code
                    )
                    FROM (
                        SELECT *
                        FROM filtered
                        ORDER BY data_code
                        LIMIT p_page_size
                        OFFSET ((p_page::bigint - 1) * p_page_size)
                    ) AS page_rows
                ),
                '[]'::jsonb
            )
        )
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.ranger_assert_public_data_access()
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    table_name text;
    role_name text;
BEGIN
    IF NOT (
        SELECT relrowsecurity
        FROM pg_class
        WHERE oid = 'public.ranger_dataset_versions'::regclass
    ) OR NOT (
        SELECT relrowsecurity
        FROM pg_class
        WHERE oid = 'public.ranger_equip_localizations'::regclass
    ) THEN
        RAISE EXCEPTION 'RLS must be enabled on both data tables';
    END IF;

    FOREACH table_name IN ARRAY ARRAY[
        'public.ranger_dataset_versions',
        'public.ranger_equip_localizations'
    ]
    LOOP
        FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
        LOOP
            IF has_any_column_privilege(role_name, table_name, 'INSERT')
               OR has_any_column_privilege(role_name, table_name, 'UPDATE')
               OR has_any_column_privilege(role_name, table_name, 'REFERENCES')
               OR has_table_privilege(role_name, table_name, 'DELETE')
               OR has_table_privilege(role_name, table_name, 'TRUNCATE')
               OR has_table_privilege(role_name, table_name, 'TRIGGER') THEN
                RAISE EXCEPTION
                    'role % has a write privilege on %',
                    role_name,
                    table_name;
            END IF;
        END LOOP;
    END LOOP;

    IF has_column_privilege(
           'anon',
           'public.ranger_equip_localizations',
           'raw_record',
           'SELECT'
       )
       OR has_column_privilege(
           'anon',
           'public.ranger_equip_localizations',
           'source_file',
           'SELECT'
       )
       OR has_column_privilege(
           'anon',
           'public.ranger_dataset_versions',
           'source_manifest_sha256',
           'SELECT'
       ) THEN
        RAISE EXCEPTION 'private provenance columns are exposed to anon';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename IN (
              'ranger_dataset_versions',
              'ranger_equip_localizations'
          )
          AND cmd <> 'SELECT'
    ) THEN
        RAISE EXCEPTION 'unexpected non-SELECT policy found';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'ranger_dataset_versions'
          AND cmd = 'SELECT'
          AND roles @> ARRAY['anon']::name[]
          AND qual ILIKE '%published%'
    ) OR NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'ranger_equip_localizations'
          AND cmd = 'SELECT'
          AND roles @> ARRAY['anon']::name[]
          AND qual ILIKE '%published%'
    ) THEN
        RAISE EXCEPTION 'published-only SELECT policies are missing';
    END IF;

    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION public.ranger_ensure_equip_localization_draft(
    text, text, text, text, text, text, text, integer
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ranger_ensure_equip_localization_draft(
    text, text, text, text, text, text, text, integer
) TO service_role;

REVOKE ALL ON FUNCTION public.ranger_publish_equip_localization_snapshot(text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ranger_publish_equip_localization_snapshot(text)
    TO service_role;

REVOKE ALL ON FUNCTION public.ranger_search_equip_localizations(
    text, text, text, integer, integer
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ranger_search_equip_localizations(
    text, text, text, integer, integer
) TO anon, authenticated;

REVOKE ALL ON FUNCTION public.ranger_assert_public_data_access()
    FROM PUBLIC, authenticated;
GRANT EXECUTE ON FUNCTION public.ranger_assert_public_data_access()
    TO anon, service_role;

COMMIT;
