"""Version-specific native layouts backed by targeted constructor/setter evidence.
Unknown module hashes are rejected; offsets are never selected by a version label.
"""
OLD_SHA='8795d855d2f0aff223c93d6ee7ea3cadd01859dbbbaa15846a07dbfcf07b5d97'
NEW_SHA='1185e119efeb6a67d30d289f8a183b36aebe53126a4765698509cd7a822a42a0'
LAYOUTS={
 OLD_SHA:{'version':'12.4.0','characterGlobal':0x1fd3b98,'characterManager':0x1e4d558,'unitVtable':0x1e34de0,'unitSize':0x8d0,'category':0x6f8,'identity':0x6fc,'unitType':0x430,'element':0x738,'dictionaryVtable':0x1f6a040,'uintVtable':0x1f65b70,'arrayVtable':0x1f6a1a8,'gearVtable':0x1e986a8,'equipMapVtable':0x1e989a8,'ownUnitGlobal':0x1fe99c0,'ownUnitManager':0x1e4f680,'excludedProhibitedWordGlobal':0x1fe9400,'excludedProhibitedWordManager':0x1e4f150},
 NEW_SHA:{'version':'12.4.2','characterGlobal':0x1fd41e8,'characterManager':0x1e4db98,'unitVtable':0x1e35410,'unitSize':0x8e8,'category':0x710,'identity':0x714,'unitType':0x430,'element':0x750,'dictionaryVtable':0x1f6a690,'uintVtable':0x1f661c0,'arrayVtable':0x1f6a7f8,'gearVtable':0x1e98ce8,'equipMapVtable':0x1e98fe8,'ownUnitGlobal':0x1fea010,'ownUnitManager':0x1e4fcc0,'excludedProhibitedWordGlobal':0x1fe9a50,'excludedProhibitedWordManager':0x1e4f790}
}
def layout_for_sha(sha):
    if sha not in LAYOUTS:raise ValueError('unverified native module SHA; refusing offsets')
    result=dict(LAYOUTS[sha]);result['primarySkill']=0x468 if sha==OLD_SHA else 0x480;result['primaryAbility']=0x500 if sha==OLD_SHA else 0x518
    # 12.4.2 inserts unitMoveType at +0x448 after the existing unitType.
    # Setter virtual+0x688/00c15428 still writes behavior at +0x430.
    result['unitType']=0x430
    if sha==NEW_SHA:result['unitMoveType']=0x448
    # RTTI proved this older candidate is ProhibitedWordManager, not a guild root.
    if sha==NEW_SHA:result.update({'guildWarGlobal':0x200a320,'guildWarManager':0x1eb5c00})
    result.update({'mainGlobal':0x1fe8ea0,'mainManager':0x1e4e980,'pvpGlobal':0x2028860,'pvpManager':0x1f15190,'profileVtable':0x1e53048,'attributeVtable':0x1e990c0} if sha==OLD_SHA else {'mainGlobal':0x1fe94f0,'mainManager':0x1e4efc0,'pvpGlobal':0x2028eb0,'pvpManager':0x1f157e0,'profileVtable':0x1e53688,'attributeVtable':0x1e99700})
    return result
