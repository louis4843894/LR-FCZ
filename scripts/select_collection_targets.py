"""Set local collection targets only; never touches the game or remote database."""
import argparse,json
from local_game_database import connect,stamp,DEFAULT_DB
from pathlib import Path

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--guild',required=True);p.add_argument('--database',type=Path,default=DEFAULT_DB);a=p.parse_args()
    if not a.guild.strip() or len(a.guild)>100:p.error('invalid guild name')
    db=connect(a.database)
    try:
        with db:
            db.execute("INSERT INTO collection_targets VALUES ('guild',?,'user',?) ON CONFLICT(module) DO UPDATE SET target_name=excluded.target_name,source=excluded.source,selected_at=excluded.selected_at",(a.guild,stamp()))
            db.execute("INSERT INTO collection_targets VALUES ('pvp','rankings','user',?) ON CONFLICT(module) DO UPDATE SET target_name=excluded.target_name,source=excluded.source,selected_at=excluded.selected_at",(stamp(),))
        print(json.dumps({'guildSelectionSaved':True,'pvpSource':'rankings','gameOrRemoteDatabaseModified':False}))
    finally:db.close()
