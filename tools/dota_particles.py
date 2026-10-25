import sys, os, json; sys.path.insert(0,'/tmp/dx')
from vpk import read_dir, get, rerl
E,D=read_dir('/mnt/user-data/uploads/dota/pak01_dir.vpk')
CH='/mnt/user-data/uploads/dota'; G='/tmp/dx/game'
todo=[a.lower() if a.endswith('_c') else a.lower()+'_c' for a in sys.argv[1:]]; seen=set(); missing={}; got=[]
while todo:
    n=todo.pop()
    if n in seen: continue
    seen.add(n)
    if n not in E: print('NOENTRY',n); continue
    out=os.path.join(G,n)
    if os.path.exists(out): buf=open(out,'rb').read()
    else:
        arc=E[n][0]
        if arc!=0x7fff and not os.path.exists(os.path.join(CH,'pak01_%03d.vpk'%arc)):
            missing.setdefault(arc,[]).append(n); continue
        buf=get(E,D,None,n,CH); os.makedirs(os.path.dirname(out),exist_ok=True); open(out,'wb').write(buf)
    got.append(n)
    for r in rerl(buf):
        r=r.lower()
        if r.endswith(('.vpcf','.vtex','.vmat','.vmdl','.vmesh','.vsnd')): todo.append(r+'_c')
json.dump(got,open('/tmp/hero/pfx_got.json','w'))
print('got',len(got),'missing chunks:',' '.join('%03d'%k for k in sorted(missing)), sum(len(v) for v in missing.values()))
