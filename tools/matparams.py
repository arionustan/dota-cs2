import subprocess,re,os,functools
VRF='/tmp/vrf/Source2Viewer-CLI'
@functools.lru_cache(None)
def params(path):
    out=subprocess.run([VRF,'-i',path,'-b','DATA'],capture_output=True,text=True).stdout
    p={}; cur=None; shader=None
    for line in out.splitlines():
        s=line.strip()
        m=re.match(r'm_shaderName = (?:resource:)?"([^"]+)"',s)
        if m: shader=m.group(1); continue
        if s=='{': cur={}; continue
        if s.startswith('}'):
            if cur is not None and 'n' in cur and 'v' in cur: p[cur['n']]=cur['v']
            cur=None; continue
        if cur is None: continue
        m=re.match(r'm_name = (?:resource:)?"([^"]+)"',s)
        if m: cur['n']=m.group(1); continue
        m=re.match(r'm_(nValue|flValue|value|pValue) = (.*)',s)
        if m:
            k,v=m.groups()
            if k=='pValue': v=re.sub(r'^resource(_name)?:','',v).strip('"')
            elif k=='value':
                try: v=[float(x) for x in v.strip('[] ').split(',')]
                except ValueError: v=v.strip('"')
            else:
                try: v=float(v)
                except ValueError: v=v
            cur['v']=v
    p['_shader']=shader
    return p
if __name__=='__main__':
    import sys,json
    print(json.dumps(params(sys.argv[1])))
