# generate CS2 vmats (+ png textures) for world + prop materials, with Dota tints
import os,re,sys,glob,json,subprocess
sys.path.insert(0,'/tmp/dx'); from matparams import params
from PIL import Image
import numpy as np
OUT='/tmp/dx/cs2'; os.makedirs(OUT+'/models/dota_map',exist_ok=True); os.makedirs(OUT+'/materials/dota_map',exist_ok=True)
VRF='/tmp/vrf/Source2Viewer-CLI'
vmats={}
for p in glob.glob('/tmp/dx/game/materials/**/*.vmat_c',recursive=True):
    vmats.setdefault(os.path.basename(p)[:-7],p)
def tex_png(vtex):
    # vtex: 'materials/....vtex' -> png path under OUT/materials/dota_map, or None
    src='/tmp/dx/game/'+vtex.lower()+'_c'
    base=os.path.basename(vtex)[:-5]
    dst=OUT+'/materials/dota_map/'+base+'.png'
    if os.path.exists(dst): return dst
    if not os.path.exists(src): return None
    subprocess.run([VRF,'-i',src,'-d','-o',OUT+'/materials/dota_map/'+base+'.png'],capture_output=True)
    if not os.path.exists(dst): return None
    im=Image.open(dst)
    if im.size[0]<4: os.remove(dst); return None
    return dst
def write_vmat(name, color_png, tint=None, alpha=False, alpharef=0.5):
    rel='materials/dota_map/'+os.path.basename(color_png)
    lines=['// DotaCS: generated from Dota 2','','Layer0','{','\tshader "csgo_complex.vfx"','','\tTextureColor "%s"'%rel]
    if tint and any(abs(t-1)>0.01 for t in tint[:3]):
        t=[min(1.0,c*1.6) for c in tint[:3]]
        lines.append('\tg_vColorTint "[%.3f %.3f %.3f 0.000]"'%tuple(t))
    if alpha:
        im=Image.open(color_png)
        if im.mode=='RGBA':
            ap=color_png[:-4]+'_alpha.png'
            if not os.path.exists(ap):
                a=im.getchannel('A'); Image.merge('RGB',(a,a,a)).save(ap)
            lines+=['\tF_ALPHA_TEST 1','\tTextureTranslucency "materials/dota_map/%s"'%os.path.basename(ap),'\tg_flAlphaTestReference "%.2f"'%alpharef]
    lines.append('}')
    open(OUT+'/models/dota_map/%s.vmat'%name,'w').write('\n'.join(lines)+'\n')
def gen(name, prefer_tex=None):
    src=vmats.get(name)
    if not src: return 'NOSRC'
    p=params(src)
    colors=[(k,v) for k,v in p.items() if isinstance(v,str) and re.match(r'g_tColor\d?$',k)]
    chosen=None
    if prefer_tex:
        for k,v in colors:
            if os.path.basename(v)[:-5]==prefer_tex: chosen=(k,v)
    if not chosen:
        order=sorted(colors,key=lambda kv: {'g_tColor':0,'g_tColor1':1,'g_tColor0':2,'g_tColor2':3,'g_tColor3':4}.get(kv[0],9))
        for k,v in order:
            if tex_png(v): chosen=(k,v); break
    if not chosen: return 'NOTEX'
    png=tex_png(chosen[1])
    if not png: return 'NOPNG'
    idx=chosen[0][len('g_tColor'):]
    tint=p.get('g_vColorTint'+idx) or p.get('g_vColorTint')
    if not isinstance(tint,list): tint=None
    alpha=bool(p.get('F_ALPHA_TEST') or p.get('F_TRANSLUCENT') or p.get('F_OVERLAY') or p.get('F_ALPHA_TEST_SHADOWS'))
    write_vmat(name,png,tint,alpha,(p.get('g_flAlphaTestReference') if isinstance(p.get('g_flAlphaTestReference'),float) and p.get('g_flAlphaTestReference')>0 else 0.5))
    return 'OK %s %s %s'%(os.path.basename(png),tint and [round(x,2) for x in tint[:3]],alpha)
names=set(sys.argv[1:])
res={}
# world materials: keep earlier texture choice
for v in glob.glob('/tmp/dx/cs/models/dota_map/*.vmat'):
    n=os.path.basename(v)[:-5]
    m=re.search(r'TextureColor "materials/dota_map/([^"]+)\.png"',open(v).read())
    res[n]=gen(n, m.group(1) if m else None)
for n in names:
    if n not in res: res[n]=gen(n)
json.dump(res,open('/tmp/dx/gen_mats.json','w'),indent=1)
for k,v in sorted(res.items()): print(k,v)
