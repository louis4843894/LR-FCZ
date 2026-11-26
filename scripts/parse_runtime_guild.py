"""Validate saved guild objects offline; private identifiers never leave this file."""
import argparse,hashlib,json,struct
from datetime import datetime
from pathlib import Path
from native_layouts import NEW_SHA
ROOT=Path(__file__).resolve().parents[1]

def parse_capture(path,observation=None):
    path=Path(path);m=json.loads((path/'capture.private.json').read_text(encoding='utf8'))
    if m['sourceKind']!='native-visible-guild-members' or m['moduleSha256']!=NEW_SHA or not m['consistent']:raise ValueError('unverified guild capture')
    datetime.fromisoformat(m['capturedAt'])
    def blob(key):
        meta=m['files'][key];file=(path/meta['file']).resolve()
        if not file.is_relative_to(path.resolve()):raise ValueError('unsafe dependency path')
        b=file.read_bytes()
        if len(b)!=meta['length'] or hashlib.sha256(b).hexdigest()!=meta['sha256']:raise ValueError('guild dependency hash/length mismatch')
        return b
    def text(key):
        value=blob(key).decode('utf8')
        if not value or '\0' in value:raise ValueError('invalid required text')
        return value
    for key in m['files']:blob(key)
    raw=blob('guild');guild_id=text('guild-id');name=text('guild-name')
    if len(raw)!=0xa8 or struct.unpack_from('<Q',raw)[0]-m['moduleBase']+0x100000!=0x1eadb48:raise ValueError('guild object type mismatch')
    array_count,capacity=struct.unpack_from('<II',blob('array-data'))
    pointers=blob('member-pointers')
    if array_count!=m['loadedCount'] or array_count>capacity or len(pointers)!=array_count*8:raise ValueError('captured member container mismatch')
    entries=struct.unpack('<'+'Q'*array_count,pointers)
    if len(set(entries))!=array_count or 0 in entries:raise ValueError('duplicate/invalid member pointers')
    maximum,total=struct.unpack_from('<II',raw,0x9c)
    if not 0<=total<=maximum<=128:raise ValueError('invalid guild member count')
    rows=[];seen=set();indices=set()
    for member in m['members']:
        index=member['index'];prefix=f'member-{index:03d}'
        if index in indices or not 0<=index<array_count:raise ValueError('invalid member index')
        indices.add(index)
        if member['status']!='captured':continue
        raw_member=blob(prefix);uid=text(prefix+'-id')
        if len(raw_member)!=0x60 or struct.unpack_from('<Q',raw_member)[0]-m['moduleBase']+0x100000!=0x1eade20:raise ValueError('member object type mismatch')
        if text(prefix+'-guild-id')!=guild_id:raise ValueError('member guild identity mismatch')
        if uid in seen:raise ValueError('duplicate member identity')
        seen.add(uid)
        rows.append({'playerId':uid,'name':text(prefix+'-name'),'level':None,'levelRaw':struct.unpack_from('<I',raw_member,0x50)[0],
                     'retrievedAt':m['capturedAt'],'defenseStatus':'not_read','defenseFailureReason':None})
    if len(m['members'])!=m['loadedCount'] or len(rows)>total:raise ValueError('guild capture count mismatch')
    if observation:
        visit=json.loads(Path(observation).read_text(encoding='utf8'))
        if visit['sourceKind']!='visible-member-general-team-observation' or visit['rosterCapture']!=path.name or visit['mode']!=0 or visit['purpose']!='unknown':raise ValueError('unverified member visit')
        index=visit['memberIndex']
        if index>=len(rows) or rows[index]['name']!=visit['memberName']:raise ValueError('visible member association mismatch')
        rows[index].update(defenseFailureReason='only_general_team_visible',defenseObservedAt=visit['observedAt'])
    return {'schemaVersion':1,'sourceKind':'validated-native-guild-roster','gameVersion':m['gameVersion'],'capturedAt':m['capturedAt'],'level':struct.unpack_from('<I',raw,0x84)[0],
            'guildId':guild_id,'name':name,'observedMemberTotal':total,'memberCapacity':maximum,'loadedCount':m['loadedCount'],
            'membersRetrieved':len(rows),'membershipComplete':len(rows)==total and not m['errors'],'members':rows,
            'sourceCapture':str(path.relative_to(ROOT)),'moduleSha256':m['moduleSha256'],
            'fieldEvidence':{'guildIdentity':'GuildInfoModel +0x30/+0x38; parser 012e7e6c',
                             'counts':'max/currentMemberCount setters virtual+158/+168 -> +9c/+a0',
                             'memberIdentity':'012ebd64 uid/gid/name virtual+48/+58/+68 -> +30/+38/+40',
                             'level':'raw native level is not the visible tier level; display remains unknown'}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--observation');p.add_argument('--output',default='data/normalized/guild-roster.private.json');a=p.parse_args()
    result=parse_capture(Path(a.capture).resolve(),a.observation);output=ROOT/a.output
    if not result['membershipComplete'] and output.exists():raise ValueError('partial capture preserved separately; refusing to replace valid roster')
    temporary=output.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temporary.replace(output)
    print(json.dumps({k:result[k] for k in ['name','observedMemberTotal','membersRetrieved','membershipComplete']}))
