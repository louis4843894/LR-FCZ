"""Read ELF64 metadata and explicit ARM64 address references, without analysis.
Only static module bytes are read. No process access or guessed game fields.
"""
import hashlib,struct,bisect
from pathlib import Path

class NativeELF:
    image_base=0x100000
    def __init__(self,path):
        self.data=Path(path).read_bytes();b=self.data
        if b[:6]!=b'\x7fELF\x02\x01':raise ValueError('requires little-endian ELF64')
        self.sha256=hashlib.sha256(b).hexdigest();self.loads=[];self.relative={}
        ph=struct.unpack_from('<Q',b,32)[0];es,n=struct.unpack_from('<HH',b,54)
        for i in range(n):
            kind,flags,off,va,_,size,_,_=struct.unpack_from('<IIQQQQQQ',b,ph+i*es)
            if kind==1:self.loads.append((va+self.image_base,va+self.image_base+size,off,flags))
        sh=struct.unpack_from('<Q',b,40)[0];es,n=struct.unpack_from('<HH',b,58)
        sections=[struct.unpack_from('<IIQQQQIIQQ',b,sh+i*es) for i in range(n)]
        self.sections=sections
        for section in sections:
            if section[1]==4:
                for off in range(section[4],section[4]+section[5],section[9]):
                    address,info,addend=struct.unpack_from('<QQq',b,off)
                    if info&0xffffffff==1027:self.relative[address+self.image_base]=addend+self.image_base
                    elif info&0xffffffff in (257,1025,1026):
                        symbols=sections[section[6]];index=info>>32
                        if index*24<symbols[5]:
                            value=struct.unpack_from('<Q',b,symbols[4]+index*24+8)[0]
                            if value:self.relative[address+self.image_base]=value+addend+self.image_base
    def offset(self,address):
        for start,end,off,_ in self.loads:
            if start<=address<end:return off+address-start
        raise ValueError('address outside file-backed LOAD segments')
    def address(self,off):
        for start,end,base,_ in self.loads:
            if base<=off<base+end-start:return start+off-base
        raise ValueError('offset outside LOAD segments')
    def ptr(self,address):
        if address in self.relative:return self.relative[address]
        value=struct.unpack_from('<Q',self.data,self.offset(address))[0]
        return value+self.image_base if value else 0
    def cstring(self,address):
        off=self.offset(address);end=self.data.find(b'\0',off,off+512)
        if end<0:raise ValueError('unbounded native string')
        return self.data[off:end].decode('utf8')
    def type_name(self,vtable):return self.cstring(self.ptr(self.ptr(vtable-8)+8))
    def function_start(self,address):
        """Look up an explicit code address in the ELF unwind index; no analysis."""
        if not hasattr(self,'_unwind_starts'):
            b=self.data;sh=struct.unpack_from('<Q',b,40)[0];es,n,strings_index=struct.unpack_from('<HHH',b,58)
            strings=self.sections[strings_index];names=b[strings[4]:strings[4]+strings[5]]
            section=next((s for s in self.sections if names[s[0]:names.find(b'\0',s[0])]==b'.eh_frame_hdr'),None)
            if not section:raise ValueError('ELF unwind index absent')
            start,size=section[4],section[5]
            if b[start:start+4]!=bytes([1,0x1b,3,0x3b]):raise ValueError('unsupported unwind index encoding')
            count=struct.unpack_from('<I',b,start+8)[0]
            if count>1000000 or 12+count*8>size:raise ValueError('unwind index bounds')
            base=section[3]+self.image_base
            starts=[base+struct.unpack_from('<i',b,start+12+i*8)[0] for i in range(count)]
            if starts!=sorted(set(starts)):raise ValueError('unwind code starts are not unique/sorted')
            self._unwind_starts=starts
        index=bisect.bisect_right(self._unwind_starts,address)-1
        if index<0 or address-self._unwind_starts[index]>0x20000:raise ValueError('code address outside bounded unwind function')
        return self._unwind_starts[index]
    def direct_call_references(self,target):
        """Exact ARM64 BL target matches within this module's executable LOADs."""
        result=[]
        for start,end,offset,flags in self.loads:
            if not flags&1:continue
            for index,(word,) in enumerate(struct.iter_unpack('<I',self.data[offset:offset+(end-start)//4*4])):
                if word&0xfc000000!=0x94000000:continue
                imm=word&0x3ffffff
                if imm&0x2000000:imm-=0x4000000
                pc=start+index*4
                if pc+imm*4==target:result.append({'call':pc,'functionStart':self.function_start(pc)})
        return result
    def adr_references(self,target):
        """Exact PC-relative ADR references, including linker-relaxed callbacks.

        Kept separate from ADRP+ADD references so existing consumers never
        mistake the ADR instruction address for a two-instruction pair.
        """
        result=[]
        for start,end,offset,flags in self.loads:
            if not flags&1:continue
            for index,(word,) in enumerate(struct.iter_unpack('<I',self.data[offset:offset+(end-start)//4*4])):
                if word&0x9f000000!=0x10000000:continue
                imm=((word>>5)&0x7ffff)<<2 | ((word>>29)&3)
                if imm&0x100000:imm-=0x200000
                pc=start+index*4
                if pc+imm==target:result.append({'adr':pc,'functionStart':self.function_start(pc)})
        return result
    def class_vtables(self,name):
        needle=name.encode()+b'\0';off=self.data.find(needle)
        if off<0:raise ValueError('exact RTTI name absent')
        address=self.address(off);types={a-8 for a,v in self.relative.items() if v==address}
        return sorted(a+8 for a,v in self.relative.items() if v in types and self.ptr(a-8)==0)
    def address_references(self,target):
        page=target&~4095;low=target&4095;result=[];b=self.data
        for start,end,base,flags in self.loads:
            if not flags&1:continue
            for off in range(base,base+end-start-28,4):
                w=struct.unpack_from('<I',b,off)[0]
                if w&0x9f000000!=0x90000000:continue
                pc=start+off-base;imm=((w>>5)&0x7ffff)<<2 | ((w>>29)&3)
                if imm&(1<<20):imm-=1<<21
                if (pc&~4095)+(imm<<12)!=page:continue
                register=w&31
                for j in range(1,7):
                    add=struct.unpack_from('<I',b,off+j*4)[0]
                    if add&0xffc00000==0x91000000 and (add>>5)&31==register and (add>>10)&4095==low:
                        prologues=[]
                        for p in range(max(base,off-128),off,4):
                            ins=struct.unpack_from('<I',b,p)[0]
                            if ins&0xffc003ff==0xd10003ff or ins&0xffc003e0==0xa98003e0:prologues.append(start+p-base)
                        result.append({'adrp':pc,'add':pc+j*4,'entryCandidate':prologues[-1] if prologues else None})
                        break
                    # A matching page/low pair is only a candidate while the
                    # ADRP value survives. In 010c4564..010c4578 x0 is first
                    # changed by ADD, then a call and another ADRP; pairing the
                    # first ADRP with the last ADD invented deckInfoJson xrefs.
                    if add&0xfc000000==0x94000000 and register<19:break
                    if add&0xfc000000==0x14000000 or add&0xfffffc1f in (0xd61f0000,0xd65f0000):break
                    if add&31==register and (add&0x9f000000 in (0x90000000,0x10000000)
                        or add&0x1f000000 in (0x11000000,0x12000000,0x0a000000,0x0b000000)
                        or add&0x3b000000==0x39000000 and add&0x00400000):break
        return result
    def load_references(self,target):
        """Exact ARM64 ADRP + unsigned LDR64 references to one known global."""
        page=target&~4095;low=target&4095;result=[]
        for start,end,base,flags in self.loads:
            if not flags&1:continue
            for off in range(base,base+end-start-28,4):
                w=struct.unpack_from('<I',self.data,off)[0]
                if w&0x9f000000!=0x90000000:continue
                pc=start+off-base;imm=((w>>5)&0x7ffff)<<2 | ((w>>29)&3)
                if imm&(1<<20):imm-=1<<21
                if (pc&~4095)+(imm<<12)!=page:continue
                register=w&31
                for j in range(1,7):
                    load=struct.unpack_from('<I',self.data,off+j*4)[0]
                    if load&0xffc00000==0xf9400000 and (load>>5)&31==register and ((load>>10)&4095)*8==low:
                        result.append({'adrp':pc,'load':pc+j*4,'functionStart':self.function_start(pc)})
        return result
