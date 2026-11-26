"""Whitelist public character/skill reference fields for local development only."""
import hashlib,json,math,re
from pathlib import Path
from build_equipment_reference_preview import ReferenceLabels
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/research/external-reference'
def build():
    source=json.loads((SOURCE/'rangers.json').read_text(encoding='utf8'))
    if source.get('schemaVersion')!=2:raise ValueError('unsupported reference schema')
    catalogs={}
    for name in ['official-locales.json','custom-locales.json']:
        for r in json.loads((SOURCE/name).read_text(encoding='utf8')):catalogs[r['key']]=r.get('zh_TW') or r.get('en') or r['key']
    labels=ReferenceLabels(catalogs)
    def text(ref):
        return re.sub(r'<#(?:[0-9a-f]+)>|<->','',labels.render(ref),flags=re.I) if ref else None
    def number(value):
        if value is None:return None
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('invalid source number')
        return value
    rows=[];seen=set();missing_names=[]
    for r in source['rangers']:
        code=r['rangerCode']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',code) or code in seen:raise ValueError('invalid/duplicate character ID')
        seen.add(code)
        if type(r['starGrade']) is not int or not 1<=r['starGrade']<=9:raise ValueError('unsupported source starGrade')
        if not catalogs.get(r['nameKey']):missing_names.append(code)
        skills=[]
        for s in r['skillSet']:
            skills.append({'skillCode':s['skillCode'],'name':text(s.get('nameKey')),'description':text(s.get('descriptionKey')),
                           'activationRatePercent':number(s.get('activationRate')),'cooldownSeconds':number(s.get('cooldownSeconds')),
                           'effects':[{'effectCode':e['effectCode'],'name':text('CUSTOM:'+e['effectCode'])} for e in s.get('effects',[])]})
        rows.append({'characterId':code,'name':text(r['nameKey']) if catalogs.get(r['nameKey']) else None,
                     'description':text(r.get('descriptionKey')),'starGrade':r['starGrade'],'evolution':r['evolution'],
                     'roleType':r['roleType'],'elementType':r['elementType'],'releaseDate':r.get('releaseDate'),
                     'skills':skills,'abilityCodes':r.get('abilityCodes',[]),'sourceKind':'external-user-confirmed','localVerification':False})
    manifest=json.loads((SOURCE/'rangers-source.json').read_text(encoding='utf8'))
    result={'schemaVersion':1,'sourceKind':'external-user-confirmed','publicationAllowed':False,'localVerification':False,
            'retrievedAt':manifest['retrievedAt'],'sourceUrl':manifest['url'],'sourceSha256':manifest['sha256'],
            'resourceVersion':None,'recordCount':len(rows),'missingNameCount':len(missing_names),'records':rows}
    (ROOT/'data/normalized/character-reference-preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'reports/character-reference-validation.json').write_text(json.dumps({k:v for k,v in result.items() if k!='records'}|{'withSkillsCount':sum(bool(r['skills']) for r in rows),'missingNameIds':missing_names,'recordIdentityUnique':True},ensure_ascii=False,indent=2),encoding='utf8')
    print('CHARACTER_REFERENCE',len(rows),'with skills',sum(bool(r['skills']) for r in rows),'missing names',len(missing_names))
    return result
if __name__=='__main__':build()
