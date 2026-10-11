import re,os,glob,shutil,subprocess,json
exec(open('/tmp/dx/dmx_units.py').read().split("if __name__=='__main__':")[0])
G='/tmp/dx/game'; O='/mnt/user-data/outputs/wild'
def mat_png(mp, od):
    vc=G+'/'+mp+'_c'
    if not os.path.exists(vc): return None
    subprocess.run(['/tmp/vrf/Source2Viewer-CLI','-i',vc,'-d','-o',os.path.dirname(vc)],capture_output=True)
    t=open(vc[:-2]).read() if os.path.exists(vc[:-2]) else ''
    m=re.search(r'"g_tColor"\s+"([^"]+\.vtex)"',t) or re.search(r'"g_tColor\w*"\s+"([^"]+\.vtex)"',t)
    if not m: return None
    tc=G+'/'+m.group(1)+'_c'
    if not os.path.exists(tc): return None
    subprocess.run(['/tmp/vrf/Source2Viewer-CLI','-i',tc,'-o',od],capture_output=True)
    b=os.path.basename(m.group(1))[:-5]
    pngs=glob.glob(od+'/'+b+'*.png')+glob.glob(os.path.dirname(tc)+'/'+b+'*.png')
    if not pngs: return None
    if not pngs[0].startswith(od): shutil.copy(pngs[0],od)
    return os.path.basename(pngs[0])
wl=json.load(open('/tmp/dx/wildlife.json'))
done=[]
for model in sorted({w['model'] for w in wl}):
    n=os.path.basename(model)[:-5]; od=O+'/'+n; os.makedirs(od,exist_ok=True)
    if not os.path.exists(G+'/'+model+'_c'): print('MISS',n); continue
    meshes,anims=parse(decompile(model))
    meshes=[m for m in meshes if '_lod' not in m]
    base='models/dota_wild/%s/'%n
    want=[w['anim'] for w in wl if w['model']==model][0].lower()
    a=next((x for x in anims if x[0].lower()==want),None) or pick(anims,'idle') or (anims[0] if anims else None)
    rm='';mt=''
    for m in meshes:
        shutil.copy(G+'/'+m,od+'/'+os.path.basename(m))
        mt+='{\n_class = "RenderMeshFile"\nfilename = "%s%s"\nimport_translation = [ 0.0, 0.0, 0.0 ]\nimport_rotation = [ 0.0, 0.0, 0.0 ]\nimport_scale = 1.0\nalign_origin_x_type = "None"\nalign_origin_y_type = "None"\nalign_origin_z_type = "None"\nparent_bone = ""\nimport_filter = \n{\nexclude_by_default = false\nexception_list = [  ]\n}\n},\n'%(base,os.path.basename(m))
        for mp in mtl_paths(G+'/'+m):
            mp=mp.decode(); png=mat_png(mp,od)
            vm=os.path.basename(mp)
            if png:
                open(od+'/'+vm,'w').write('// DotaCS wildlife\nLayer0\n{\n\tshader "csgo_complex.vfx"\n\tTextureColor "%s%s"\n}\n'%(base,png))
                rm+='{\nfrom = "%s"\nto = "%s%s"\n},\n'%(mp,base,vm)
    at=''
    if a:
        shutil.copy(G+'/'+a[1],od+'/'+os.path.basename(a[1])); at=animblock('idle',base+os.path.basename(a[1]),True)
    v=open('/mnt/user-data/outputs/units2/roshan/roshan.vmdl').read()
    v=re.sub(r'remaps = \n\[\n.*?\]\nuse_global_default','remaps = \n[\n'+rm.replace('\\','\\\\')+']\nuse_global_default',v,flags=re.S)
    v=re.sub(r'global_default_material = "[^"]*"','global_default_material = "materials/default/default.vmat"',v)
    v=re.sub(r'(_class = "RenderMeshList"\nchildren = \n\[\n).*?(\]\n\},\n\{\n_class = "AnimationList")',lambda m_: m_.group(1)+mt+m_.group(2),v,flags=re.S)
    v=re.sub(r'(_class = "AnimationList"\nchildren = \n\[\n).*?(\]\ndefault_root_bone_name)',lambda m_: m_.group(1)+at+m_.group(2),v,flags=re.S)
    open(od+'/'+n+'.vmdl','w').write(v); done.append(n)
    print('WILD',n,len(meshes),a[0] if a else None, rm.count('from'))
json.dump(done,open(O+'/list.json','w'))
