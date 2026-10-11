# extract props + missing textures from staged pak chunks
import sys,os,glob,pickle,collections,json
sys.path.insert(0,'/tmp/dx')
from vpk import *
pe=pickle.load(open('/tmp/dx/pe.pkl','rb'))
OUT='/tmp/dx/game'
KEEP=('vmdl_c','vmesh_c','vmat_c','vtex_c','vphys_c','vmorf_c','vnmskel_c','vanim_c','vagrp_c','vseq_c','vanmgrph_c')
SKIPPAT=('_normal','_refl','_spec','_mask','_rim','_detail','_fresnel','_selfillum','_metal','_tintmask','_tint_mask','_warp','_orm','_rough','_ao_','g_tnormal','g_tspecular')
state_f='/tmp/dx/state3.json'
st=json.load(open(state_f)) if os.path.exists(state_f) else {'done':[]}
done=set(st['done'])
roots=set(m+'_c' for m in json.load(open('/tmp/dx/unitplan.json'))['models'] if '_mega' not in m)
chunks={int(os.path.basename(c)[6:9]):c for c in glob.glob('/mnt/user-data/uploads/dota/pak01_[0-9][0-9][0-9].vpk')}
JUNK=('cube','winter','snow','_spring','wind','materials/default/','crownfall','courier','lion_','promotional','specmask','shopkeeper/','shopkeeper_dire/','team_banner_artifact','consumable','gem_')
def skip(r):
    return any(j in r for j in JUNK) or (r.endswith('.vtex_c') and any(s in r for s in SKIPPAT))
need=set(r for r in roots if r in pe and not skip(r))
_dd=None
changed=True
while changed:
    changed=False
    for n in list(need):
        p=os.path.join(OUT,n)
        if os.path.exists(p):
            done.add(n)
            for r in rerl(open(p,'rb').read()):
                r=r.lower()+'_c'
                if r in pe and r.endswith(KEEP) and not skip(r) and r not in need:
                    need.add(r); changed=True
        elif pe[n][0] in chunks or pe[n][0]==0x7fff:
            if pe[n][0]!=0x7fff: data=get(pe,None,None,n,'/mnt/user-data/uploads/dota')
            else:
                if _dd is None: _,_dd=read_dir('/mnt/user-data/uploads/dota/pak01_dir.vpk')
                data=get(pe,_dd,None,n,None)
            os.makedirs(os.path.dirname(p),exist_ok=True)
            open(p,'wb').write(data); done.add(n); changed=True
for c in chunks.values():
    try: os.remove(c)
    except Exception as e: print('rm fail',c,e)
st['done']=sorted(done); json.dump(st,open(state_f,'w'))
todo=[n for n in need if not os.path.exists(os.path.join(OUT,n))]
arcs=collections.Counter(pe[n][0] for n in todo)
print('need',len(need),'todo',len(todo),'chunks',len(arcs))
open('/tmp/dx/last3.txt','w').write(' '.join(str(a) for a,_ in sorted(arcs.items(), key=lambda x:-x[1])))
print(open('/tmp/dx/last3.txt').read())
