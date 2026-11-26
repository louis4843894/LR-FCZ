"""Isolated local Edge session for UI checks; no existing browser profile."""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data/research/runtime.private/python'))
from websockets.sync.client import connect


class Browser:
    def __init__(self,label,protocol_timeout=60,extra_origins=()):
        if not 1<=protocol_timeout<=180:raise ValueError('browser protocol time bound')
        self.protocol_timeout=protocol_timeout
        self.extra_origins=frozenset(extra_origins)
        if self.extra_origins-{'https://lr-fcz.vercel.app'}:
            raise ValueError('extra preview origin is outside the user-provided deployment')
        self.folder=ROOT/'data/research/runtime.private/browser-ui'/label
        self.folder.mkdir(parents=True,exist_ok=True)
        profile=self.folder/('profile-'+uuid.uuid4().hex[:10])
        self.process=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
            '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
            '--user-data-dir='+str(profile),'about:blank'],stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,creationflags=0x08000000)
        self.ws=None;self.sequence=0;self.errors=[];self.document_loader=None
        try:
            for _ in range(60):
                try:
                    port=int((profile/'DevToolsActivePort').read_text().splitlines()[0])
                    tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1))
                    tab=next(t for t in tabs if t['type']=='page');break
                except (OSError,ValueError,StopIteration):time.sleep(.25)
            else:raise RuntimeError('isolated Edge startup failed')
            self.ws=connect(tab['webSocketDebuggerUrl'],max_size=30*1024*1024)
            self.call('Runtime.enable');self.call('Page.enable')
        except Exception:
            self.close();raise

    def call(self,method,params=None):
        self.sequence+=1;identity=self.sequence
        self.ws.send(json.dumps({'id':identity,'method':method,'params':params or {}}))
        while True:
            message=json.loads(self.ws.recv(timeout=self.protocol_timeout))
            if message.get('method')=='Page.frameNavigated':
                frame=message['params']['frame']
                if not frame.get('parentId'):self.document_loader=frame.get('loaderId')
            if message.get('method')=='Runtime.exceptionThrown':
                self.errors.append(message['params']['exceptionDetails'].get('text','exception'))
            if message.get('id')==identity:
                if 'error' in message:raise RuntimeError('browser protocol error: '+method)
                return message.get('result',{})

    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result:raise RuntimeError('browser evaluation failed')
        return result['result'].get('value')

    def navigate(self,url,width=1440,ready=None):
        parsed=urllib.parse.urlparse(url)
        if not ((parsed.hostname in ('127.0.0.1','localhost') and parsed.scheme=='http' and parsed.port==3101)
                or (parsed.hostname=='rangerbook.warmycat.com' and parsed.scheme=='https')
                or (f'{parsed.scheme}://{parsed.netloc}' in self.extra_origins)):
            raise ValueError('UI probe origin is outside the requested scope')
        self.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':960,'deviceScaleFactor':1,'mobile':width<700})
        navigation=self.call('Page.navigate',{'url':url});loader=navigation.get('loaderId')
        expression='document.readyState==="complete"'+(' && ('+ready+')' if ready else '')
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            ready_document=self.evaluate(expression)
            if ready_document and (not loader or self.document_loader==loader):break
            time.sleep(.2)
        else:raise RuntimeError('page did not become ready')
        self.evaluate('document.fonts.ready.then(()=>true)')

    def screenshot(self,name):
        import base64
        image=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
        path=self.folder/(name+'.png');path.write_bytes(base64.b64decode(image['data']));return path

    def close(self):
        if self.ws:
            try:self.ws.send(json.dumps({'id':999999,'method':'Browser.close'}));self.ws.close()
            except Exception:pass
        if self.process.poll() is None:
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.terminate()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
