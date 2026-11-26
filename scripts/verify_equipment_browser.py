"""Local Edge/CDP verification of real equipment pages and GET form interactions.
No login, device access, or external browser navigation. Screenshots stay private.
"""
import base64
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data/research/runtime.private/python'))
from websockets.sync.client import connect
BASE = 'http://127.0.0.1:3101'
out = ROOT / 'data/research/runtime.private/browser-qa'
out.mkdir(exist_ok=True)
edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
p = subprocess.Popen([edge, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                      '--remote-debugging-port=9223', '--remote-debugging-address=127.0.0.1',
                      '--user-data-dir=' + str(out / 'cdp-profile'), 'about:blank'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
results, runtime_errors, completed = [], [], False
try:
    for attempt in range(40):
        try:
            tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9223/json', timeout=1))
            break
        except Exception:
            time.sleep(.5)
    else:
        raise RuntimeError('Edge CDP did not start')
    tab = next(t for t in tabs if t['type'] == 'page')
    ws = connect(tab['webSocketDebuggerUrl'], max_size=20*1024*1024)
    sequence = 0
    def call(method, params=None):
        global sequence
        sequence += 1
        current = sequence
        ws.send(json.dumps({'id': current, 'method': method, 'params': params or {}}))
        while True:
            msg = json.loads(ws.recv(timeout=45))
            if msg.get('method') == 'Runtime.exceptionThrown':
                runtime_errors.append(msg['params']['exceptionDetails'].get('text', 'exception'))
            if msg.get('id') == current:
                if 'error' in msg:
                    raise RuntimeError(str(msg['error']))
                return msg.get('result', {})
    def evaluate(expression):
        result = call('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in result:
            raise RuntimeError(str(result['exceptionDetails']))
        return result['result'].get('value')
    def wait_for(expression):
        for attempt in range(160):
            if evaluate(expression):
                return
            time.sleep(.2)
        raise RuntimeError('Browser condition timed out: ' + expression)
    def ready(text):
        wait_for('document.readyState === "complete" && !!document.querySelector(".page-main") && document.body.innerText.includes(' + json.dumps(text) + ')')
    def snapshot(name, width, expected=(), checks=None):
        evaluate('document.fonts.ready.then(()=>true)')
        images_ready = evaluate('Promise.all(Array.from(document.images).map(async img=>{img.loading="eager";try{await img.decode();return img.naturalWidth>0}catch{return false}})).then(xs=>xs.every(Boolean))')
        metrics = evaluate('({viewport:innerWidth,scroll:document.documentElement.scrollWidth,text:document.body.innerText,html:document.documentElement.outerHTML,url:location.href,ids:Array.from(document.querySelectorAll(".verified-gear-card code")).map(x=>x.textContent)})')
        checks = checks or {}
        checks.update({x: x in metrics['text'] for x in expected})
        checks['noHorizontalOverflow'] = metrics['scroll'] <= metrics['viewport'] == width
        checks['imagesLoaded'] = images_ready
        checks['noImageHotlinks'] = evaluate('Array.from(document.images).every(img=>new URL(img.src).origin===location.origin)')
        checks['noPrivateFields'] = not any(x in metrics['html'] for x in ['objectAddress', 'runtime.private', 'managerAddress', 'rawRecordSha256', 'gradeCipherFile', '01fd5270'])
        checks['noUnboundDescription'] = '{$' not in metrics['text'] and '<#78ff00>' not in metrics['text']
        checks['noLiteralSlashN'] = chr(92) + 'n' not in metrics['text']
        png = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True})
        (out / (name + '.png')).write_bytes(base64.b64decode(png['data']))
        result = {'case': name, 'url': metrics['url'], 'width': width, 'scrollWidth': metrics['scroll'], 'checks': checks, 'visibleIds': metrics['ids']}
        results.append(result)
        if not all(checks.values()):
            raise RuntimeError('Browser check failed: ' + json.dumps(result, ensure_ascii=True))
        return metrics
    def navigate(path, width, expected):
        call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 844 if width < 600 else 1000, 'deviceScaleFactor': 1, 'mobile': width < 600})
        call('Page.navigate', {'url': BASE + path})
        ready(expected)

    call('Page.enable')
    call('Runtime.enable')
    target = '/gear/eq_2202_amr_06_nm'
    navigate(target, 390, '閃避機率')
    snapshot('target-mobile-base', 390, ['6 星', 'ARMOR', '日暮永遠的制服', '尚未解析', '+5.0 ～ +8.0%', '+1.5 ～ +3.0%', 'Rangerbook / WarmyCat'])
    evaluate('document.querySelector(".reference-level select").value="5"; document.querySelector(".reference-level").requestSubmit(); true')
    wait_for('location.search.includes("level=5") && document.body.innerText.includes("+30.0 ～ +48.0%")')
    snapshot('target-mobile-max-submit', 390, ['+30.0 ～ +48.0%', '+9.0 ～ +18.0%', '尚未解析'])
    call('Page.reload')
    ready('+30.0 ～ +48.0%')
    snapshot('target-mobile-max-reload', 390, ['6 星', 'ARMOR'], {'selectRetained': evaluate('document.querySelector(".reference-level select").value === "5"')})
    navigate('/gear/eq_2202_wpn_17_nm?level=5', 1440, '木屬性Ranger')
    snapshot('advanced-desktop', 1440, ['7 星', 'WEAPON', '+16.2 ～ +18.0%', '+355.0 ～ +400.0%'])
    navigate('/gear/eq_2607_acc_29_nm?level=5', 390, '爆擊傷害提升')
    snapshot('spec-mobile', 390, ['Skill+', 'Spec+ · +5', '使用1次增益技能時', '+80.0 ～ +90.0%', '+3 秒', '50～60%'])

    navigate('/gear', 1440, '953 筆結果')
    evaluate('document.querySelector("input[name=q]").value="eq_2202_amr_06"; document.querySelector("select[name=star]").value="6"; document.querySelector("select[name=type]").value="ARMOR"; document.querySelector(".gear-filters").requestSubmit(); true')
    wait_for('location.search.includes("q=eq_2202_amr_06") && document.querySelectorAll(".verified-gear-card").length === 1')
    snapshot('search-form-desktop', 1440, ['1 筆結果', '6 星'], {'correctId': evaluate('document.querySelector(".verified-gear-card code").textContent === "eq_2202_amr_06"')})
    evaluate('document.querySelector(".gear-filters a").click(); true')
    wait_for('location.search === "" && document.querySelector("input[name=q]")?.value === "" && document.body.innerText.includes("953 筆結果")')
    snapshot('clear-filters-desktop', 1440, ['953 筆結果'])

    preview = json.loads((ROOT / 'data/normalized/equipment-reference-preview.json').read_text(encoding='utf8'))['records']
    a, b = 'EQUIP:GEAR_FILTER_AVD_PROB_MUL_nm', 'EQUIP:GEAR_FILTER_SKLAVD_PROB_MUL_nm'
    # Independent check using only the reference's ordinary basic/high option structures.
    def matches(row, effects, conditions, mode):
        keys = {e['optionKey'] for e in row['normalOptions']}
        condition_keys = set()
        if row['advanced']:
            high = row['advanced']
            keys.update(e['optionKey'] for e in [high['defaultOption'], *high['switchOptions']])
            condition_keys.add(high['condition']['key'])
        tests = [k in keys for k in effects] + [k in condition_keys for k in conditions]
        return all(tests) if mode == 'AND' else any(tests)
    for mode in ['AND', 'OR']:
        conditions = ['CUSTOM:EQUIP_RANGER_TYPE_WATER']
        expected = sorted(r['itemCode'] for r in preview if matches(r, [a, b], conditions, mode))
        query = urllib.parse.urlencode({'effect': [a, b], 'condition': conditions, 'mode': mode}, doseq=True)
        navigate('/gear?' + query, 390, str(len(expected)) + ' 筆結果')
        actual = evaluate('Array.from(document.querySelectorAll(".verified-gear-card code")).map(x=>x.textContent)')
        snapshot('filters-' + mode.lower() + '-mobile', 390, [str(len(expected)) + ' 筆結果'], {'expectedFirstPageIds': actual == expected[:24], 'multiSelectPreserved': evaluate('document.querySelector("select[name=effect]").selectedOptions.length === 2')})
    navigate('/gear?star=7&type=WEAPON&page=2', 390, '第 2／')
    snapshot('pagination-mobile', 390, ['7 星', '第 2／'], {'pageLimit24': evaluate('document.querySelectorAll(".verified-gear-card").length === 24')})
    completed = True
    ws.close()
    (ROOT / 'reports/website-browser-validation.json').write_text(json.dumps({'cases': results, 'runtimeErrors': runtime_errors, 'passed': not runtime_errors}, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'cases': len(results), 'passed': not runtime_errors, 'runtimeErrors': runtime_errors}, ensure_ascii=True))
    if runtime_errors:
        raise SystemExit('Browser JavaScript exceptions detected')
finally:
    if results:
        (ROOT / 'reports/website-browser-validation.json').write_text(json.dumps({'cases': results, 'runtimeErrors': runtime_errors, 'passed': completed and all(all(r['checks'].values()) for r in results) and not runtime_errors}, ensure_ascii=False, indent=2), encoding='utf8')
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
