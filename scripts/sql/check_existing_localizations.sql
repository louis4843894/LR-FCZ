SELECT
  (SELECT count(*) FROM public.ranger_equip_localizations) AS localization_rows,
  (SELECT md5(string_agg(md5(to_jsonb(row_value)::text), '' ORDER BY snapshot_id,data_code,language))
     FROM public.ranger_equip_localizations row_value) AS localization_digest,
  (SELECT jsonb_agg(jsonb_build_object('snapshot_id',snapshot_id,'status',status,
      'content_sha256',content_sha256,'record_count',record_count) ORDER BY snapshot_id)
     FROM public.ranger_dataset_versions) AS existing_versions;
