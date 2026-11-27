create schema guild_access_private;
revoke all on schema guild_access_private from public, anon, authenticated;

create table guild_access_private.owner (
  singleton boolean primary key default true check (singleton),
  email text not null check (email = lower(btrim(email))),
  user_id uuid references auth.users on delete set null,
  activation_digest bytea,
  activation_expires_at timestamptz
);

create table guild_access_private.applications (
  user_id uuid primary key references auth.users on delete cascade,
  username text not null check (char_length(btrim(username)) between 1 and 40),
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'revoked')),
  requested_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users on delete set null
);

alter table guild_access_private.owner enable row level security;
alter table guild_access_private.applications enable row level security;

create table public.guild_private_display (
  name text primary key check (name ~ '^(guilds|guild-[a-f0-9]{20})$'),
  model jsonb not null check (jsonb_typeof(model) = 'object')
);
alter table public.guild_private_display enable row level security;
revoke all on public.guild_private_display from public, anon, authenticated;
grant select, insert, update on public.guild_private_display to service_role;

create function guild_access_private.is_owner()
returns boolean language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from guild_access_private.owner o
    join auth.users u on u.id = o.user_id
    where u.id = auth.uid() and lower(u.email) = o.email
      and u.email_confirmed_at is not null
  );
$$;

create function public.guild_access_current()
returns text language plpgsql security definer set search_path = ''
as $$
declare
  caller auth.users%rowtype;
  display_name text;
  application_status text;
begin
  select * into caller from auth.users where id = auth.uid();
  if caller.id is null or caller.email is null or caller.email_confirmed_at is null then
    return 'unverified';
  end if;

  if guild_access_private.is_owner() then
    return 'admin';
  end if;

  display_name := btrim(caller.raw_user_meta_data ->> 'guild_username');
  if char_length(display_name) between 1 and 40 and display_name !~ '[[:cntrl:]]' then
    insert into guild_access_private.applications (user_id, username)
      values (caller.id, display_name) on conflict (user_id) do nothing;
  end if;

  select status into application_status
    from guild_access_private.applications where user_id = caller.id;
  return coalesce(application_status, 'unregistered');
end;
$$;

create function public.guild_access_activate(p_code text)
returns boolean language plpgsql security definer set search_path = ''
as $$
begin
  if p_code is null or p_code !~ '^[a-f0-9]{64}$' then
    return false;
  end if;
  update guild_access_private.owner o
    set user_id = u.id, activation_digest = null, activation_expires_at = null
    from auth.users u
    where u.id = auth.uid() and u.email_confirmed_at is not null
      and lower(u.email) = o.email and o.user_id is null
      and o.activation_expires_at > now()
      and o.activation_digest = sha256(convert_to(p_code, 'UTF8'));
  if not found then
    return false;
  end if;
  delete from guild_access_private.applications where user_id = auth.uid();
  return true;
end;
$$;

create function public.guild_access_review_queue(p_status text, p_offset integer)
returns table (
  user_id uuid, username text, email text, status text,
  requested_at timestamptz, reviewed_at timestamptz
)
language plpgsql stable security definer set search_path = ''
as $$
begin
  if not guild_access_private.is_owner() then
    raise exception 'Guild administrator required' using errcode = '42501';
  end if;
  return query
    select a.user_id, a.username, u.email::text, a.status, a.requested_at, a.reviewed_at
    from guild_access_private.applications a
    join auth.users u on u.id = a.user_id
    where a.status = p_status
    order by a.requested_at desc, a.user_id
    offset greatest(p_offset, 0) limit 26;
end;
$$;

create function public.guild_access_review(p_user uuid, p_expected text, p_decision text)
returns boolean language plpgsql security definer set search_path = ''
as $$
begin
  if not guild_access_private.is_owner() then
    raise exception 'Guild administrator required' using errcode = '42501';
  end if;
  if (
    (p_expected = 'pending' and p_decision in ('approved', 'rejected')) or
    (p_expected = 'approved' and p_decision = 'revoked') or
    (p_expected in ('rejected', 'revoked') and p_decision = 'approved')
  ) is not true then
    return false;
  end if;

  update guild_access_private.applications
    set status = p_decision, reviewed_by = auth.uid(), reviewed_at = now()
    where user_id = p_user and status = p_expected;
  return found;
end;
$$;

create function public.guild_access_display(p_name text)
returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  if not guild_access_private.is_owner() and not exists (
    select 1 from guild_access_private.applications a
    join auth.users u on u.id = a.user_id
    where a.user_id = auth.uid() and a.status = 'approved'
      and u.email_confirmed_at is not null
  ) then
    raise exception 'Approved guild access required' using errcode = '42501';
  end if;
  return (select model from public.guild_private_display where name = p_name);
end;
$$;

revoke execute on function guild_access_private.is_owner() from public, anon, authenticated;
revoke execute on function public.guild_access_current() from public, anon, authenticated;
revoke execute on function public.guild_access_activate(text) from public, anon, authenticated;
revoke execute on function public.guild_access_review_queue(text, integer) from public, anon, authenticated;
revoke execute on function public.guild_access_review(uuid, text, text) from public, anon, authenticated;
revoke execute on function public.guild_access_display(text) from public, anon, authenticated;
grant execute on function public.guild_access_current(), public.guild_access_activate(text),
  public.guild_access_review_queue(text, integer), public.guild_access_review(uuid, text, text),
  public.guild_access_display(text)
  to authenticated;
