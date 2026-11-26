"""Check console hydration errors and SSR/first-client structure on three entries."""
import argparse
import gzip
import json
import re
import time
import urllib.request
from browser_session import Browser, ROOT

HYDRATION=re.compile(r'hydrat|server rendered|server-rendered|did not match|Minified React error #(418|419|421|422|423|425)',re.I)
STRUCTURE='''(()=>{const main=document.querySelector('main.character-detail-page');if(!main)return null;const shell=main.parentElement;const skip=document.querySelector('.skip-navigation');return {children:Array.from(shell.children).map(e=>({tag:e.tagName.toLowerCase(),className:e.className})),skipCount:document.querySelectorAll('.skip-navigation').length,skipParent:skip?.parentElement.tagName.toLowerCase(),skipBeforeHeader:!!skip&&!!(skip.compareDocumentPosition(shell.querySelector('header'))&Node.DOCUMENT_POSITION_FOLLOWING),headerCount:shell.querySelectorAll('header.site-header').length,skipNestedInButton:!!document.querySelector('button button,button header'),mainCount:shell.querySelectorAll('main').length}})()'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--origin',choices=['http://127.0.0.1:3000','http://127.0.0.1:3101','https://lr-fcz.vercel.app'],default='http://127.0.0.1:3101')
    parser.add_argument('--phase',default='after')
    args=parser.parse_args()
    character='u1216e-towa'
    document=json.loads(gzip.decompress((ROOT/'data/site-display/character-details.json.gz').read_bytes()))['data']
    if character not in document:character=next(k for k,v in document.items() if v['details'] and v['details']['skills'])
    path='/characters/'+character
    origin=args.origin
    ready='document.querySelector("main.character-detail-page h1")?.getBoundingClientRect().height>0'
    cases=[]
    extras=[] if origin.endswith(':3101') else [origin]
    with Browser('character-hydration-'+args.phase+'-'+origin.split(':')[-1].replace('/',''),protocol_timeout=180,extra_origins=extras) as b:
        b.call('Network.enable')
        b.call('Emulation.setScriptExecutionDisabled',{'value':True})
        b.navigate(origin+path,390,'!!document.querySelector("main.character-detail-page")')
        server=b.evaluate(STRUCTURE)
        b.call('Emulation.setScriptExecutionDisabled',{'value':False})
        for entry in ['direct','reload','from-list']:
            b.console_errors.clear();b.console_warnings.clear();b.errors.clear()
            if entry=='direct':b.navigate(origin+path,390,ready)
            elif entry=='reload':
                b.call('Page.reload',{'ignoreCache':False})
                deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    if b.evaluate('document.readyState==="complete"&&('+ready+')'):break
                    time.sleep(.2)
            else:
                b.navigate(origin+'/characters?q='+character,390,'document.querySelector("main h1")?.getBoundingClientRect().height>0')
                b.evaluate('new Promise(r=>setTimeout(r,500))')
                b.evaluate('document.querySelector(".character-catalog-grid a").click()')
                deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    if b.evaluate(ready):break
                    time.sleep(.2)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if b.evaluate('Object.keys(document.querySelector(".nav-toggle")??{}).some(k=>k.startsWith("__reactProps"))'):break
                time.sleep(.2)
            b.evaluate('new Promise(r=>setTimeout(r,500))')
            client=b.evaluate(STRUCTURE)
            b.evaluate('document.querySelector(".skip-navigation").click()')
            skip_works=b.evaluate('document.activeElement===document.querySelector("main")')
            errors=[s for s in b.console_errors+b.console_warnings if HYDRATION.search(s)]
            checks={'sameInitialStructure':server==client,'skipAndHeaderPresent':client is not None and client['skipCount']==1 and client['headerCount']==1,'skipInStableLayout':args.phase=='before' or client is not None and client['skipParent']=='body' and client['skipBeforeHeader'],'validNesting':client is not None and not client['skipNestedInButton'] and client['mainCount']==1,'skipFocusesMain':skip_works,'noHydrationConsoleErrors':not errors,'noRuntimeExceptions':not b.errors}
            b.screenshot(entry)
            cases.append({'entry':entry,'checks':checks,'serverStructure':server,'clientStructure':client,'hydrationConsoleErrors':errors,'consoleErrors':b.console_errors,'runtimeErrors':b.errors})
    passed=all(all(c['checks'].values()) for c in cases)
    label='deployed' if origin.startswith('https:') else origin.rsplit(':',1)[1]
    report={'passed':passed,'origin':origin,'characterId':character,'phase':args.phase,'cases':cases}
    (ROOT/'reports'/f'character-hydration-{args.phase}-{label}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'origin':origin,'cases':len(cases),'hydrationErrors':sum(len(c['hydrationConsoleErrors']) for c in cases),'failedChecks':[{c['entry']:[k for k,v in c['checks'].items() if not v]} for c in cases if not all(c['checks'].values())]}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
