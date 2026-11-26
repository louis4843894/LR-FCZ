"""Check real local catalogue filters, pagination and mobile navigation."""
import json
import time
from browser_session import Browser, ROOT


def main():
    cases = []
    with Browser('catalog-tools', protocol_timeout=120) as b:
        def visit(path, width=1440):
            b.navigate('http://127.0.0.1:3101'+path, width, 'document.querySelector("main h1")?.getBoundingClientRect().height>0')
            b.evaluate('new Promise(r=>setTimeout(r,350))')

        def record(name, checks):
            checks['noOverflow'] = b.evaluate('document.documentElement.scrollWidth<=innerWidth')
            checks['noExternalBranding'] = b.evaluate('!document.querySelector("main").innerText.toLowerCase().includes("rangerbook")')
            b.screenshot(name)
            cases.append({'case': name, 'checks': checks})
            if not all(checks.values()):
                raise ValueError('UI check failed: '+name)

        for width in (1440, 390):
            visit('/', width)
            b.evaluate('document.querySelector(".home-search select").value="/gear";document.querySelector(".home-search select").dispatchEvent(new Event("change",{bubbles:true}))')
            b.evaluate('new Promise(r=>setTimeout(r,100))')
            record('home-'+str(width), {'quickSearchTargetsGear': b.evaluate('document.querySelector(".home-search").getAttribute("action")==="/gear"')})
            if width == 390:
                b.evaluate('document.querySelector(".nav-toggle").click()')
                b.evaluate('new Promise(r=>setTimeout(r,100))')
                opened = b.evaluate('document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="true"')
                b.call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape'})
                b.evaluate('new Promise(r=>setTimeout(r,100))')
                record('mobile-menu', {'opens': opened, 'escapeClosesAndRestoresFocus': b.evaluate('document.querySelector(".nav-toggle").getAttribute("aria-expanded")==="false"&&document.activeElement===document.querySelector(".nav-toggle")')})

            visit('/characters?star=9&sort=star-desc&page=2', width)
            record('characters-'+str(width), {
                'coverageCollapsed': b.evaluate('!document.querySelector(".catalog-coverage").open'),
                'realStars': b.evaluate('Array.from(document.querySelectorAll(".catalog-grid .verified-gear-card p:first-of-type")).every(p=>p.innerText.startsWith("9 星"))'),
                'pageAndFiltersPreserved': b.evaluate('document.querySelector(".catalog-page-number[aria-current=page]").innerText==="2"&&Array.from(document.querySelectorAll(".catalog-page-number")).every(a=>new URL(a.href).searchParams.get("star")==="9")'),
                'removalResetsPage': b.evaluate('!new URL(document.querySelector(".catalog-filter-chip").href).searchParams.has("page")'),
            })
            visit('/gear?type=ARMOR&star=6', width)
            record('gear-'+str(width), {
                'actualFilters': b.evaluate('Array.from(document.querySelectorAll(".catalog-grid .verified-gear-card p:first-of-type")).every(p=>p.innerText==="6 星 · 防具")'),
                'chips': b.evaluate('document.querySelectorAll(".catalog-filter-chip").length===2'),
                'touchPicker': b.evaluate('document.querySelectorAll(".catalog-option-picker input[type=checkbox]").length>2&&document.querySelectorAll("select[multiple]").length===0'),
            })

        # Use the actual form controls. A picker search must not lose checked,
        # temporarily hidden options from the submitted repeated query values.
        effect = b.evaluate('document.querySelector("input[name=effect]").value')
        visit('/gear?effect='+__import__('urllib.parse', fromlist=['quote']).quote(effect)+'&mode=OR', 390)
        b.evaluate('const input=document.querySelector(".catalog-option-search input");Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(input,"no-matching-option-xyz");input.dispatchEvent(new Event("input",{bubbles:true}))')
        b.evaluate('new Promise(r=>setTimeout(r,150))')
        record('gear-picker-preserves-hidden', {
            'selectionRetained': b.evaluate('new FormData(document.querySelector(".catalog-search-form")).getAll("effect").length===1'),
            'orModeRetained': b.evaluate('new FormData(document.querySelector(".catalog-search-form")).get("mode")==="OR"'),
            'emptySearchHint': b.evaluate('document.querySelector(".catalog-option-list").innerText.includes("已選項目仍會保留")'),
        })
        b.evaluate('document.querySelector(".catalog-option-search button").click()')
        b.evaluate('new Promise(r=>setTimeout(r,100))')
        record('gear-clear-picker', {'clearsOnlyGroup': b.evaluate('new FormData(document.querySelector(".catalog-search-form")).getAll("effect").length===0')})
        for path, name in [('/characters?q=no-such-character-xyz', 'characters-empty'), ('/gear?q=no-such-gear-xyz', 'gear-empty')]:
            visit(path, 390)
            record(name, {'helpfulEmpty': b.evaluate('!!document.querySelector(".catalog-empty .button")&&!document.querySelector(".catalog-pagination")')})
        visit('/gear/eq_2202_amr_06_nm', 390)
        record('detail-breadcrumb', {'parentLink': b.evaluate('Array.from(document.querySelectorAll(".site-breadcrumbs a")).some(a=>a.getAttribute("href")==="/gear")'), 'sixStars': '6 星' in b.evaluate('document.querySelector("main").innerText')})
        errors = b.errors
    report = {'passed': not errors and all(all(c['checks'].values()) for c in cases), 'cases': cases, 'runtimeErrors': errors}
    (ROOT/'reports/catalog-tools-ui-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'passed': report['passed'], 'cases': len(cases), 'runtimeErrors': errors}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
