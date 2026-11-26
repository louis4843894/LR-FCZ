"""Use the expressly authorized existing game session in RAM only.

Reads only the native HTTP context and the exact LF_AC preference. Does not
write credentials/keys, change the device, attach, inject, or disable TLS.
Never print this module's returned context or an underlying request exception.
"""
import base64,hashlib,re,struct,time,xml.etree.ElementTree as ET
from dataclasses import dataclass,field
from pathlib import Path
import sys
from bounded_equipment_reader import Reader
from equipment_memory import ROOT,GBASE,u64
from read_defense_team import typed
sys.path.insert(0,str(ROOT/'scripts'))
from native_elf import NativeELF
from native_layouts import NEW_SHA
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from cryptography.hazmat.primitives.padding import PKCS7


class SessionUnavailable(ValueError):
    """Messages are constant codes, never credential data."""


@dataclass(repr=False)
class RuntimeSession:
    headers:dict=field(repr=False)
    base_url:str='https://rangers-api.line-apps.com/v12.4'

    def request_headers(self):
        now=str(int(time.time()*1000))
        return {**self.headers,'x-linegame-timestamp':now,'timeid':now}


def load_session(reader,*,authorized=False):
    if authorized is not True:raise SessionUnavailable('explicit_session_authorization_required')
    if reader.module_sha!=NEW_SHA:raise SessionUnavailable('unverified_runtime_module')
    elf=NativeELF(ROOT/'data/research/runtime.private/modules/libgame-12.4.2-pull.so')
    if elf.sha256!=NEW_SHA:raise SessionUnavailable('unverified_static_module')
    def singleton(address,ap):
        ptr=u64(reader.read(reader.base+address-GBASE,8));typed(reader,ptr,8,ap);return ptr
    def string(address):return reader.string(reader.read(address,24),0)
    def ccstring(address):
        if not address:raise SessionUnavailable('missing_native_context_string')
        raw=reader.read(address,0x30);ap=u64(raw)-reader.base+GBASE
        if elf.type_name(ap)!='N7cocos2d8CCStringE':raise SessionUnavailable('native_context_string_type_differs')
        return reader.string(raw,0x18)
    native=singleton(0x20419b0,0x1f64fe0)
    crypt=singleton(0x20418c0,0x1f64ee0)
    main=singleton(0x1fe94f0,0x1e4efc0)
    profile=u64(reader.read(main+0x50,8));typed(reader,profile,8,0x1e53688)
    uid=string(profile+0x30).decode('utf8')
    fields=reader.read_many([(native+0x18,24),(crypt+0x18,8)])
    udid,agent,language=[ccstring(u64(fields[0],i)).decode('utf8') for i in (0,8,16)]
    key=ccstring(u64(fields[1]))
    if len(key) not in (16,32):raise SessionUnavailable('native_cipher_key_length_differs')
    # 01a33288 calls MD5; 01a33304 renders sixteen bytes with "%02X".
    preference=hashlib.md5(b'LF_AC').hexdigest().upper()
    path='/data/data/com.linecorp.LGRGS/shared_prefs/Cocos2dxPrefsFile.xml'
    # Return only this exact entry, including when the XML is a single line.
    # The shell command contains only a static hash/name, never a secret.
    pattern='<string name="'+preference+'"[^>]*>[^<]*</string>'
    selected=reader.shell("grep -o '"+pattern+"' "+path+" 2>/dev/null")
    if not 1<=len(selected)<=8192:raise SessionUnavailable('exact_session_preference_missing_or_oversized')
    try:
        element=ET.fromstring(selected)
        if element.tag!='string' or element.attrib!={'name':preference}:raise ValueError()
        encrypted=base64.b64decode(element.text or '',validate=True)
        if len(encrypted)<32 or (len(encrypted)-16)%16:raise ValueError()
        # Verified 01a32a94: prefix IV, AES-CBC with 16/32-byte native key;
        # EVP_DecryptFinal_ex uses its default PKCS#7 padding.
        decryptor=Cipher(algorithms.AES(key),modes.CBC(encrypted[:16])).decryptor()
        padded=decryptor.update(encrypted[16:])+decryptor.finalize()
        unpad=PKCS7(128).unpadder();cookie=(unpad.update(padded)+unpad.finalize()).decode('ascii')
        if not re.fullmatch(r'[A-Za-z0-9%._~+/=\-]{1,4096}',cookie):raise ValueError()
    except Exception:raise SessionUnavailable('session_preference_format_not_verified') from None
    # Normal context only. No token, key or UDID is emitted by callers.
    headers={'Cookie':f'LF_AC={cookie}; udid={udid};','uid':uid,
             'User-Agent':agent,'accept-language':language,
             'Content-Type':'application/json; charset=utf-8','Accept-Encoding':'gzip',
             'x-linegame-mcc':string(native+0x1f0).decode('utf8'),
             'x-linegame-mnc':string(native+0x208).decode('utf8')}
    # 01a38090 calls snprintf at 01a38114 with version constants 12,4,2;
    # exact native format: "%s/%s;%s/%s"; platform literal "android".
    version_words=struct.unpack_from('<3I',elf.data,elf.offset(0x1a38108))
    if version_words!=(0x52800183,0x52800084,0x52800045):
        raise SessionUnavailable('native_version_header_instructions_differ')
    headers['app-version']=string(native+0x90).decode('utf8')+'/12.4.2;android/'+string(native+0x78).decode('utf8')
    if any('\r' in v or '\n' in v for v in headers.values()):raise SessionUnavailable('native_context_contains_invalid_header')
    return RuntimeSession(headers)
