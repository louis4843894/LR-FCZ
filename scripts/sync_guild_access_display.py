"""Upload the validated guild display models to the private Supabase table."""

import argparse
import gzip
import hashlib
import json
import os
import re

from export_site_display import ROOT, assert_safe
from import_supabase import anon_client, rpc, service_client, SupabaseApiError


def load_guild_models():
    folder = ROOT / "data/site-display"
    manifest = json.loads((folder / "manifest.json").read_bytes())
    models = []
    for record in manifest["files"]:
        name = record["name"]
        if not re.fullmatch(r"guilds|guild-[a-f0-9]{20}", name):
            continue
        snapshot = (folder / f"{name}.json.gz").read_bytes()
        if hashlib.sha256(snapshot).hexdigest() != record["sha256"]:
            raise ValueError(f"Guild display checksum mismatch: {name}")
        model = json.loads(gzip.decompress(snapshot))
        if (model["kind"], model["schemaVersion"], model["name"]) != ("lr-site-display", 1, name):
            raise ValueError(f"Invalid guild display snapshot: {name}")
        assert_safe(model)
        models.append({"name": name, "model": model["data"]})
    index = next(row["model"] for row in models if row["name"] == "guilds")
    expected = {"guild-" + guild["alias"] for guild in index["guilds"]} | {"guilds"}
    if len(models) != 101 or {row["name"] for row in models} != expected:
        raise ValueError("Guild display export is incomplete")
    return models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    models = load_guild_models()
    if not args.apply:
        print(f"Validated {len(models)} guild display models. No remote changes.")
        return

    if not os.environ.get("SUPABASE_SECRET_KEY"):
        raise SystemExit("Load the local sync credentials before using --apply.")
    endpoint = "/rest/v1/guild_private_display"
    client = service_client()
    public = anon_client()
    for operation in (lambda: public.request("GET", endpoint), lambda: rpc(public, "guild_access_display", {"p_name": "guilds"})):
        try:
            operation()
        except SupabaseApiError as error:
            if error.status not in (401, 403, 404):
                raise
        else:
            raise RuntimeError("Anonymous guild data access was not denied")
    saved = client.request("POST", endpoint, params={"on_conflict": "name", "select": "name"},
                           payload=models, prefer="resolution=merge-duplicates,return=representation")
    if {row["name"] for row in saved} != {row["name"] for row in models}:
        raise RuntimeError("Upload receipt did not match the guild display export")
    print(f"Published {len(saved)} guild display models. Anonymous access denied.")


if __name__ == "__main__":
    main()
