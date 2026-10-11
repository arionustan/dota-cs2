import struct, os, sys
def read_dir(path):
    f=open(path,'rb'); data=f.read()
    sig,ver,tree=struct.unpack_from('<III',data,0)
    assert sig==0x55aa1234, hex(sig)
    off = 12 if ver==1 else 28
    end=off+tree
    entries={}
    p=off
    def rs():
        nonlocal p
        e=data.index(b'\0',p); s=data[p:e].decode('utf-8','replace'); p=e+1; return s
    while True:
        ext=rs()
        if not ext: break
        while True:
            d=rs()
            if not d: break
            while True:
                n=rs()
                if not n: break
                crc,pre,arc,eoff,elen,term=struct.unpack_from('<IHHIIH',data,p); p+=18
                predata=data[p:p+pre]; p+=pre
                full=(d+'/' if d.strip()!='' else '')+n+'.'+ext
                entries[full.lower()]=(arc,eoff,elen,pre,predata, end if arc==0x7fff else None)
    return entries,data
def get(entries,data,dirpath,name,chunkdir):
    arc,eoff,elen,pre,predata,base=entries[name]
    if arc==0x7fff:
        return predata+data[base+eoff:base+eoff+elen]
    fn=os.path.join(chunkdir,'pak01_%03d.vpk'%arc)
    with open(fn,'rb') as f:
        f.seek(eoff); return predata+f.read(elen)
def rerl(buf):
    try:
        fsize,hv,v,boff,bcount=struct.unpack_from('<IHHII',buf,0)
        p=8+boff
        out=[]
        for i in range(bcount):
            t=buf[p:p+4]; o,s=struct.unpack_from('<II',buf,p+4)
            if t==b'RERL':
                b=p+4+o
                ro,rc=struct.unpack_from('<II',buf,b)
                rb=b+ro
                for j in range(rc):
                    ep=rb+16*j
                    no,=struct.unpack_from('<Q',buf,ep+8)
                    sp=ep+8+no
                    e=buf.index(b'\0',sp); out.append(buf[sp:e].decode('utf-8','replace'))
            p+=12
        return out
    except Exception as ex:
        return []
