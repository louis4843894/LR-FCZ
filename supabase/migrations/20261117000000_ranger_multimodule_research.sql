begin;

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

create unique index if not exists ranger_research_one_published_per_scope
    on public.ranger_research_snapshots (module, source_kind)
    where status = 'published';

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

create table if not exists public.ranger_characters (
    snapshot_id text not null,
    module text not null default 'characters' check (module = 'characters'),
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

create unique index if not exists ranger_characters_game_identity
    on public.ranger_characters (snapshot_id, game_id, coalesce(language, ''))
    where game_id is not null;

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

create unique index if not exists ranger_equipment_game_identity
    on public.ranger_equipment (snapshot_id, game_id, coalesce(language, ''))
    where game_id is not null;

create table if not exists public.ranger_abilities (
    snapshot_id text not null,
    module text not null default 'abilities' check (module = 'abilities'),
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

create unique index if not exists ranger_abilities_game_identity
    on public.ranger_abilities (snapshot_id, game_id, coalesce(language, ''))
    where game_id is not null;

create table if not exists public.ranger_players (
    player_id text primary key,
    first_observed_at timestamptz not null,
    last_observed_at timestamptz not null,
    source_record_identity jsonb not null,
    validation_status text not null
);

create table if not exists public.ranger_guilds (
    snapshot_id text not null,
    module text not null default 'guild' check (module = 'guild'),
    guild_id text not null,
    source_record_identity jsonb not null,
    source_file text not null,
    source_file_sha256 text not null check (
        source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
    ),
    payload jsonb not null,
    validation_status text not null,
    primary key (snapshot_id, guild_id),
    unique (snapshot_id, source_record_identity),
    foreign key (snapshot_id, module)
        references public.ranger_research_snapshots (snapshot_id, module)
        on delete restrict
);

create table if not exists public.ranger_guild_roster_snapshots (
    snapshot_id text not null,
    module text not null default 'guild' check (module = 'guild'),
    guild_id text not null,
    observed_at timestamptz not null,
    retrieval_status text not null check (
        retrieval_status in ('success', 'failed', 'unavailable')
    ),
    reported_member_count integer,
    source_record_identity jsonb not null,
    source_file text,
    source_file_sha256 text check (
        source_file_sha256 is null
        or source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
    ),
    primary key (snapshot_id, guild_id),
    unique (snapshot_id, module, guild_id),
    foreign key (snapshot_id, module)
        references public.ranger_research_snapshots (snapshot_id, module)
        on delete restrict,
    foreign key (snapshot_id, guild_id)
        references public.ranger_guilds (snapshot_id, guild_id)
        on delete restrict,
    check (
        (retrieval_status = 'success'
            and reported_member_count is not null
            and reported_member_count >= 0
            and source_file is not null
            and source_file_sha256 is not null)
        or (retrieval_status in ('failed', 'unavailable')
            and reported_member_count is null)
    )
);

create table if not exists public.ranger_guild_memberships (
    snapshot_id text not null,
    module text not null default 'guild' check (module = 'guild'),
    guild_id text not null,
    player_id text not null references public.ranger_players (player_id)
        on delete restrict,
    observed_at timestamptz not null,
    source_record_identity jsonb not null,
    source_file text not null,
    source_file_sha256 text not null check (
        source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
    ),
    validation_status text not null,
    primary key (snapshot_id, guild_id, player_id),
    unique (snapshot_id, source_record_identity),
    foreign key (snapshot_id, guild_id)
        references public.ranger_guilds (snapshot_id, guild_id)
        on delete restrict,
    foreign key (snapshot_id, guild_id)
        references public.ranger_guild_roster_snapshots (snapshot_id, guild_id)
        on delete restrict,
    foreign key (snapshot_id, module)
        references public.ranger_research_snapshots (snapshot_id, module)
        on delete restrict
);

create table if not exists public.ranger_team_snapshots (
    snapshot_id text not null,
    module text not null check (module in ('pvp', 'guild')),
    team_snapshot_id text not null,
    player_id text not null references public.ranger_players (player_id)
        on delete restrict,
    purpose text not null check (
        purpose in ('pvp_defense', 'guild_battle_defense', 'unknown')
    ),
    guild_id text,
    membership_snapshot_id text,
    retrieved_at timestamptz not null,
    retrieval_status text not null check (
        retrieval_status in ('success', 'failed', 'unavailable')
    ),
    reported_member_count integer,
    source_record_identity jsonb not null,
    source_file text,
    source_file_sha256 text check (
        source_file_sha256 is null
        or source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
    ),
    primary key (snapshot_id, module, team_snapshot_id),
    unique (snapshot_id, module, team_snapshot_id, player_id),
    unique (snapshot_id, module, source_record_identity),
    foreign key (snapshot_id, module)
        references public.ranger_research_snapshots (snapshot_id, module)
        on delete restrict,
    check (
        (purpose = 'guild_battle_defense'
            and module = 'guild'
            and guild_id is not null
            and membership_snapshot_id is not null)
        or (purpose = 'pvp_defense'
            and module = 'pvp'
            and guild_id is null
            and membership_snapshot_id is null)
        or purpose = 'unknown'
    ),
    check (
        (retrieval_status = 'success'
            and reported_member_count is not null
            and reported_member_count >= 0
            and source_file is not null
            and source_file_sha256 is not null)
        or (retrieval_status in ('failed', 'unavailable')
            and reported_member_count is null)
    )
);

create table if not exists public.ranger_team_members (
    snapshot_id text not null,
    module text not null check (module in ('pvp', 'guild')),
    team_snapshot_id text not null,
    player_id text not null,
    member_index integer not null check (member_index >= 0),
    character_state text not null check (
        character_state in ('present', 'not_present', 'unknown')
    ),
    character_id text,
    weapon_state text not null check (
        weapon_state in ('equipped', 'not_equipped', 'unknown')
    ),
    weapon_id text,
    armor_state text not null check (
        armor_state in ('equipped', 'not_equipped', 'unknown')
    ),
    armor_id text,
    accessory_state text not null check (
        accessory_state in ('equipped', 'not_equipped', 'unknown')
    ),
    accessory_id text,
    awakening jsonb,
    talents jsonb,
    source_record_identity jsonb not null,
    source_file text not null,
    source_file_sha256 text not null check (
        source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
    ),
    payload jsonb not null,
    primary key (snapshot_id, module, team_snapshot_id, member_index),
    unique (snapshot_id, module, team_snapshot_id, source_record_identity),
    foreign key (snapshot_id, module, team_snapshot_id, player_id)
        references public.ranger_team_snapshots
            (snapshot_id, module, team_snapshot_id, player_id)
        on delete restrict,
    check ((character_state = 'present' and character_id is not null)
        or (character_state <> 'present' and character_id is null)),
    check ((weapon_state = 'equipped' and weapon_id is not null)
        or (weapon_state <> 'equipped' and weapon_id is null)),
    check ((armor_state = 'equipped' and armor_id is not null)
        or (armor_state <> 'equipped' and armor_id is null)),
    check ((accessory_state = 'equipped' and accessory_id is not null)
        or (accessory_state <> 'equipped' and accessory_id is null))
);

create table if not exists public.ranger_pvp_rankings (
    snapshot_id text not null,
    module text not null default 'pvp' check (module = 'pvp'),
    player_id text not null references public.ranger_players (player_id)
        on delete restrict,
    rank_position integer check (rank_position is null or rank_position > 0),
    observed_at timestamptz not null,
    source_record_identity jsonb not null,
    source_file text not null,
    source_file_sha256 text not null check (
        source_file_sha256 ~ '^[0-9a-fA-F]{64}$'
    ),
    payload jsonb not null,
    validation_status text not null,
    primary key (snapshot_id, player_id, source_record_identity),
    foreign key (snapshot_id, module)
        references public.ranger_research_snapshots (snapshot_id, module)
        on delete restrict
);

create table if not exists public.ranger_usage_stats (
    snapshot_id text not null,
    module text not null check (module in ('pvp', 'guild')),
    sample_scope text not null check (
        sample_scope in ('top_10', 'top_30', 'top_50', 'top_100', 'all')
    ),
    metric_key text not null,
    numerator bigint not null check (numerator >= 0),
    denominator bigint not null check (denominator >= 0),
    computed_at timestamptz not null,
    source_snapshot_ids jsonb not null,
    primary key (snapshot_id, module, sample_scope, metric_key),
    foreign key (snapshot_id, module)
        references public.ranger_research_snapshots (snapshot_id, module)
        on delete restrict,
    check (jsonb_typeof(source_snapshot_ids) = 'array'),
    check (numerator <= denominator)
);

create or replace function public.ranger_publish_research_snapshot(
    p_snapshot_id text,
    p_module text
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
    target public.ranger_research_snapshots%rowtype;
    actual_counts jsonb;
begin
    select *
    into target
    from public.ranger_research_snapshots
    where snapshot_id = p_snapshot_id and module = p_module
    for update;

    if not found or target.status <> 'draft' then
        raise exception 'research snapshot is missing or not a draft';
    end if;
    if not target.is_complete then
        raise exception 'incomplete research snapshot cannot be published';
    end if;
    if exists (
        select 1
        from public.ranger_team_snapshots team
        where team.snapshot_id = p_snapshot_id
          and team.module = p_module
          and (
              (team.retrieval_status <> 'success' and exists (
                  select 1
                  from public.ranger_team_members member
                  where member.snapshot_id = team.snapshot_id
                    and member.module = team.module
                    and member.team_snapshot_id = team.team_snapshot_id
              ))
              or (team.retrieval_status = 'success' and team.reported_member_count <> (
                  select count(*)
                  from public.ranger_team_members member
                  where member.snapshot_id = team.snapshot_id
                    and member.module = team.module
                    and member.team_snapshot_id = team.team_snapshot_id
              ))
          )
    ) then
        raise exception 'team retrieval status or member count does not match stored members';
    end if;
    if p_module = 'guild' and exists (
        select 1
        from public.ranger_guild_roster_snapshots roster
        where roster.snapshot_id = p_snapshot_id
          and (
              (roster.retrieval_status <> 'success' and exists (
                  select 1
                  from public.ranger_guild_memberships membership
                  where membership.snapshot_id = roster.snapshot_id
                    and membership.guild_id = roster.guild_id
              ))
              or (roster.retrieval_status = 'success' and roster.reported_member_count <> (
                  select count(*)
                  from public.ranger_guild_memberships membership
                  where membership.snapshot_id = roster.snapshot_id
                    and membership.guild_id = roster.guild_id
              ))
          )
    ) then
        raise exception 'guild roster status or member count does not match stored memberships';
    end if;

    if p_module = 'characters' then
        select jsonb_build_object(
            'research_records', (select count(*) from public.ranger_research_records where snapshot_id = p_snapshot_id and module = p_module),
            'characters', count(*)
        ) into actual_counts
        from public.ranger_characters
        where snapshot_id = p_snapshot_id;
    elsif p_module = 'equipment' then
        select jsonb_build_object(
            'research_records', (select count(*) from public.ranger_research_records where snapshot_id = p_snapshot_id and module = p_module),
            'equipment', count(*)
        ) into actual_counts
        from public.ranger_equipment
        where snapshot_id = p_snapshot_id;
    elsif p_module = 'abilities' then
        select jsonb_build_object(
            'research_records', (select count(*) from public.ranger_research_records where snapshot_id = p_snapshot_id and module = p_module),
            'abilities', count(*)
        ) into actual_counts
        from public.ranger_abilities
        where snapshot_id = p_snapshot_id;
    elsif p_module = 'pvp' then
        select jsonb_build_object(
            'research_records', (select count(*) from public.ranger_research_records where snapshot_id = p_snapshot_id and module = p_module),
            'pvp_rankings', (select count(*) from public.ranger_pvp_rankings where snapshot_id = p_snapshot_id),
            'team_snapshots', (select count(*) from public.ranger_team_snapshots where snapshot_id = p_snapshot_id and module = 'pvp'),
            'team_members', (select count(*) from public.ranger_team_members where snapshot_id = p_snapshot_id and module = 'pvp'),
            'usage_stats', (select count(*) from public.ranger_usage_stats where snapshot_id = p_snapshot_id and module = 'pvp')
        ) into actual_counts;
    elsif p_module = 'guild' then
        select jsonb_build_object(
            'research_records', (select count(*) from public.ranger_research_records where snapshot_id = p_snapshot_id and module = p_module),
            'guilds', (select count(*) from public.ranger_guilds where snapshot_id = p_snapshot_id),
            'guild_roster_snapshots', (select count(*) from public.ranger_guild_roster_snapshots where snapshot_id = p_snapshot_id),
            'guild_memberships', (select count(*) from public.ranger_guild_memberships where snapshot_id = p_snapshot_id),
            'team_snapshots', (select count(*) from public.ranger_team_snapshots where snapshot_id = p_snapshot_id and module = 'guild'),
            'team_members', (select count(*) from public.ranger_team_members where snapshot_id = p_snapshot_id and module = 'guild'),
            'usage_stats', (select count(*) from public.ranger_usage_stats where snapshot_id = p_snapshot_id and module = 'guild')
        ) into actual_counts;
    else
        raise exception 'unsupported research module';
    end if;

    if actual_counts <> target.expected_counts then
        raise exception 'research snapshot row counts do not match expected counts';
    end if;
    if (actual_counts ->> 'research_records')::bigint <> target.record_count then
        raise exception 'research source record count does not match the snapshot';
    end if;
    if exists (
        select 1
        from public.ranger_research_records record
        where record.snapshot_id = p_snapshot_id
          and record.module = p_module
          and record.validation_status not in (
              'source-row-verified',
              'source-record-verified'
          )
    ) then
        raise exception 'research snapshot contains unverified source records';
    end if;
    if p_module = 'characters' and (actual_counts ->> 'characters')::bigint = 0 then
        raise exception 'character read model is empty';
    elsif p_module = 'equipment' and (actual_counts ->> 'equipment')::bigint = 0 then
        raise exception 'equipment read model is empty';
    elsif p_module = 'abilities' and (actual_counts ->> 'abilities')::bigint = 0 then
        raise exception 'ability read model is empty';
    elsif p_module = 'pvp' and (actual_counts ->> 'pvp_rankings')::bigint = 0 then
        raise exception 'PvP ranking read model is empty';
    elsif p_module = 'guild' and (
        (actual_counts ->> 'guilds')::bigint = 0
        or (actual_counts ->> 'guild_memberships')::bigint = 0
    ) then
        raise exception 'guild read model lacks a guild or member list';
    end if;

    update public.ranger_research_snapshots
    set status = 'archived'
    where module = p_module
      and source_kind = target.source_kind
      and status = 'published';

    update public.ranger_research_snapshots
    set status = 'published', published_at = now()
    where snapshot_id = p_snapshot_id and module = p_module;

    return 'published';
end;
$$;

revoke all on public.ranger_research_snapshots from public, anon, authenticated;
revoke all on public.ranger_research_records from public, anon, authenticated;
revoke all on public.ranger_characters from public, anon, authenticated;
revoke all on public.ranger_equipment from public, anon, authenticated;
revoke all on public.ranger_abilities from public, anon, authenticated;
revoke all on public.ranger_players from public, anon, authenticated;
revoke all on public.ranger_guilds from public, anon, authenticated;
revoke all on public.ranger_guild_roster_snapshots from public, anon, authenticated;
revoke all on public.ranger_guild_memberships from public, anon, authenticated;
revoke all on public.ranger_team_snapshots from public, anon, authenticated;
revoke all on public.ranger_team_members from public, anon, authenticated;
revoke all on public.ranger_pvp_rankings from public, anon, authenticated;
revoke all on public.ranger_usage_stats from public, anon, authenticated;

grant all on public.ranger_research_snapshots to service_role;
grant all on public.ranger_research_records to service_role;
grant all on public.ranger_characters to service_role;
grant all on public.ranger_equipment to service_role;
grant all on public.ranger_abilities to service_role;
grant all on public.ranger_players to service_role;
grant all on public.ranger_guilds to service_role;
grant all on public.ranger_guild_roster_snapshots to service_role;
grant all on public.ranger_guild_memberships to service_role;
grant all on public.ranger_team_snapshots to service_role;
grant all on public.ranger_team_members to service_role;
grant all on public.ranger_pvp_rankings to service_role;
grant all on public.ranger_usage_stats to service_role;
revoke all on function public.ranger_publish_research_snapshot(text, text)
    from public, anon, authenticated;
grant execute on function public.ranger_publish_research_snapshot(text, text)
    to service_role;

alter table public.ranger_research_snapshots enable row level security;
alter table public.ranger_research_records enable row level security;
alter table public.ranger_characters enable row level security;
alter table public.ranger_equipment enable row level security;
alter table public.ranger_abilities enable row level security;
alter table public.ranger_players enable row level security;
alter table public.ranger_guilds enable row level security;
alter table public.ranger_guild_roster_snapshots enable row level security;
alter table public.ranger_guild_memberships enable row level security;
alter table public.ranger_team_snapshots enable row level security;
alter table public.ranger_team_members enable row level security;
alter table public.ranger_pvp_rankings enable row level security;
alter table public.ranger_usage_stats enable row level security;

commit;
