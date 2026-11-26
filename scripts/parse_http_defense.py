"""Parse the proven normal PVP response; preserve unsupported effect semantics.

Source relationship: 0174720c -> 015eab84 -> 015eac0c -> 0113d984 /
0113e138. JSON currentEnchant/invenId/slot are cross-checked against the already
verified native object copies before this acquisition path is accepted.
"""
import argparse,hashlib,json,re
from pathlib import Path
from native_layouts import NEW_SHA
from import_defense_teams import normalize

SLOTS={'WEAPON':'weapon','ARMOR':'armor','ACC':'accessory'}


def integer(value,name,positive=False):
    if type(value) is not int or not (1 if positive else 0)<=value<=0xffffffffffffffff:raise ValueError('invalid HTTP '+name)
    return value


def parse_response(directory):
    source=directory/'response.private.json';raw=source.read_bytes();data=json.loads(raw)
    if (data.get('sourceKind')!='verified-normal-pvp-http-branch' or data.get('moduleSha256')!=NEW_SHA
            or data.get('identityMatch')!='exact-native-ranking-uid'):raise ValueError('unverified normal PVP response')
    player=data['result']['player'];uid=player['uid'];selected=player.get('usePvPTeamNo')
    if not isinstance(uid,str) or not uid or type(selected) is not int or selected not in (1,2):raise ValueError('unknown HTTP owner or selected defense team')
    groups=data['result']['playerUnitTeamGroupMap']['pvpteam']
    if not isinstance(groups,dict) or set(groups)-{'1','2'}:raise ValueError('unsupported PVP group keys')
    teams=[]
    for group,units in sorted(groups.items()):
        if not isinstance(units,list) or len(units)>5:raise ValueError('unsupported PVP position bounds')
        positions=set();identities=set();members=[]
        for unit in units:
            position=integer(unit['slot'],'slot');inven=integer(unit['invenId'],'unit invenId',True)
            if position>=5 or position in positions or inven in identities or unit['teamNo']!=int(group):raise ValueError('duplicate or inconsistent HTTP unit placement')
            positions.add(position);identities.add(inven)
            code=unit['unitCode']
            if not isinstance(code,str) or not re.fullmatch('[A-Za-z0-9_-]+',code):raise ValueError('invalid HTTP unit template')
            mapping=unit.get('equipMap');equipment={}
            if mapping is not None and (not isinstance(mapping,dict) or set(mapping)-set(SLOTS)):raise ValueError('unsupported HTTP equipment map')
            for native,slot in SLOTS.items():
                if mapping is None:equipment[slot]={'state':'unknown','equipmentId':None};continue
                if native not in mapping:equipment[slot]={'state':'not_equipped','equipmentId':None};continue
                gear=mapping[native]
                if not isinstance(gear,dict) or not gear:equipment[slot]={'state':'unknown','equipmentId':None};continue
                item=gear['equipItemCode']
                if not re.fullmatch('eq_[A-Za-z0-9_]+',item) or gear['itemCode']!=item or gear['equipType']!=native:raise ValueError('HTTP gear template/type differs')
                instance=integer(gear['invenId'],'equipment invenId',True);owner=integer(gear['unitInvenId'],'unitInvenId')
                if owner and owner!=inven:raise ValueError('HTTP equipment owner differs')
                enhancement=integer(gear['currentEnchant'],'currentEnchant');grade=integer(gear['currentGrade'],'currentGrade')
                entries=[]
                for prefix in ['attr1','attr2','attr3','attr4','attr5','skillPlusAttr1']:
                    key=prefix+'No';grade_key=prefix+'ValueGrade'
                    if key not in gear:continue
                    attr=integer(gear[key],key);value_grade=integer(gear[grade_key],grade_key)
                    # Zero is retained in the raw source; its activation/meaning
                    # is not promoted to an active effect or an invented ID.
                    if attr:
                        entries.append({'index':len(entries),'attributeId':attr,'valueGradeRaw':value_grade,
                                        'attributeTypeRaw':None,'value':None,'unit':None,'sourceField':key})
                equipment[slot]={'state':'equipped','equipmentId':item,'enhancement':enhancement,'instanceGrade':grade,
                    'equipmentInstanceIdentity':{'value':str(instance),'namespace':'player-owned-equipment','sourceField':'equipMap.*.invenId'},
                    'ownerAssociationStatus':'verified-native' if owner else 'unknown',
                    'actualEffects':{'status':'identifiers_only','entries':entries,'numericalValuesVerified':False} if entries else None,
                    'attributeReadState':'captured' if entries else 'empty_observed_semantics_unknown',
                    'fieldEvidence':{'enhancement':'normal /player/units/team/equip response currentEnchant; cross-checked against native instance+0x58',
                                     'instanceGrade':'currentGrade; native instance+0x50; not assumed template stars',
                                     'equipmentInstanceIdentity':'equipMap.*.invenId; native instance+0x68',
                                     'actualEffects':'instance attrNNo/attrNValueGrade and skillPlusAttr1No; type/unit/value/activation remain unknown'}}
            members.append({'memberIndex':position,'characterState':'present','characterId':code,
                            'characterInstanceIdentity':{'value':str(inven),'namespace':'player-owned-unit','sourceField':'playerUnitTeamGroupMap.pvpteam.*.invenId'},'equipment':equipment})
        teams.append({'snapshotId':directory.name+'-pvp-'+group,'teamId':'pvpteam/'+group,
                      'playerId':uid,'playerDisplayName':player.get('userName'),'purpose':'pvp_defense','status':'success',
                      'retrievedAt':data['capturedAt'],'isSelected':int(group)==selected,'gameVersion':'12.4.2',
                      'unobservedPositionIndices':sorted(set(range(5))-positions),'verification':None,
                      'members':sorted(members,key=lambda m:m['memberIndex'])})
    # An empty returned map is a real, owner-verified response without team
    # records. It is unavailable data, not five invented empty positions.
    doc={'schemaVersion':1,'recordScope':'player-team-observations','sourceId':directory.name,'memberships':[],
         'parserVersion':'normal-pvp-http-v1-identifiers','snapshots':teams,
         'captureEvidence':{'method':'native-normal-request-json-v1','responseCopySha256':hashlib.sha256(raw).hexdigest(),
                            'credentialsPersisted':False,'moduleSha256':NEW_SHA,'visualVerification':False,
                            'teamReadState':'not_returned' if not teams else 'selected_group_missing' if not any(t['isSelected'] for t in teams) else 'returned'}}
    normalize(doc,hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest())
    return doc


def compare_native(document,native):
    old={t['teamId']:t for t in native['snapshots']};checked={'teams':0,'characters':0,'equipped':0,'emptySlots':0,'attributes':0}
    for team in document['snapshots']:
        previous=old[team['teamId']]
        if team['playerId']!=previous['playerId'] or team['isSelected']!=previous['isSelected']:raise ValueError('cross-check owner/selected team differs')
        checked['teams']+=1
        units={u['memberIndex']:u for u in previous['members']}
        for member in team['members']:
            before=units[member['memberIndex']]
            if member['characterId']!=before['characterId'] or member['characterInstanceIdentity']['value']!=before['characterInstanceIdentity']['value']:raise ValueError('cross-check character instance/position differs')
            checked['characters']+=1
            for slot,gear in member['equipment'].items():
                prior=before['equipment'][slot]
                if gear['state']!=prior['state'] or gear['equipmentId']!=prior['equipmentId']:raise ValueError('cross-check equipment slot/template differs')
                if gear['state']=='not_equipped':checked['emptySlots']+=1;continue
                if gear['state']!='equipped':continue
                if (any(gear[k]!=prior[k] for k in ['enhancement','instanceGrade'])
                        or gear['equipmentInstanceIdentity']['value']!=prior['equipmentInstanceIdentity']['value']):raise ValueError('cross-check equipment instance/current enhancement differs')
                checked['equipped']+=1
                # Skill+ can be represented by a dependency object instead of
                # an ordinary GearStat ID; do not claim that relation here.
                for entry in (gear.get('actualEffects') or {}).get('entries',[]):
                    if entry['sourceField'].startswith('skillPlus'):continue
                    candidates=[e for e in (prior.get('actualEffects') or {}).get('entries',[]) if e['attributeId']==entry['attributeId'] and e['valueGradeRaw']==entry['valueGradeRaw']]
                    if not candidates:raise ValueError('cross-check ordinary effect ID/grade differs')
                    checked['attributes']+=1
    return checked


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--compare-native',type=Path)
    args=parser.parse_args();doc=parse_response(args.capture)
    if args.compare_native:print(json.dumps(compare_native(doc,json.loads(args.compare_native.read_text(encoding='utf8')))))
    (args.capture/'observations.private.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
