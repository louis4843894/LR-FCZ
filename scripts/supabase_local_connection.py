"""Load only the existing Supabase settings locally, without printing or saving secrets."""
import os
from pathlib import Path
from import_supabase import service_client,anon_client

ROOT=Path(__file__).resolve().parents[1]

def load_settings():
    allowed={'SUPABASE_URL','NEXT_PUBLIC_SUPABASE_URL','SUPABASE_SECRET_KEY','NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'}
    file=ROOT/'.env.local'
    if file.exists():
        for line in file.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:continue
            key,value=line.split('=',1);key=key.strip();value=value.strip()
            if key in allowed and value:
                if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
                os.environ.setdefault(key,value)

def existing_service_client():
    load_settings();return service_client()

def existing_anon_client():
    load_settings();return anon_client()
