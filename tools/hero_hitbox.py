import sys, os, subprocess, numpy as np, trimesh, json
sys.path.insert(0,'/tmp/hero'); sys.path.insert(0,'/tmp/dx')
from hero_plan import H, vmdls
G='/tmp/dx/game'; F=37.7
def meas(vm, scale):
    out='/tmp/hb/'+os.path.basename(vm)[:-5]+'.glb'
    if not os.path.exists(out):
        subprocess.run(['/tmp/vrf/Source2Viewer-CLI','-i',G+'/'+vm+'_c','-d','-o',out,'--gltf_export_format','glb'],capture_output=True,timeout=600)
    s=trimesh.load(out); 
    g=s.dump(concatenate=True) if hasattr(s,'dump') else s
    v=np.asarray(g.vertices)
    y=v[:,1]; base=np.percentile(y,0.5); top=np.percentile(y,99)
    cx,cz=np.median(v[:,0]),np.median(v[:,2])
    r=np.percentile(np.hypot(v[:,0]-cx,v[:,2]-cz),80)
    return round((top-base)*F*scale), round(r*F*scale), round(cx*F*scale), round(-cz*F*scale)
res={}
for u in list(H)+['pudge']:
    vm = vmdls(u)[0] if u!='pudge' else 'models/heroes/pudge/pudge.vmdl'
    try: res[u]=meas(vm, 0.95 if u=='pudge' else 0.75)
    except Exception as e: res[u]=repr(e)
    print(u,res[u])
json.dump(res,open('/tmp/hb/res.json','w'))
