import re,os,glob,shutil,subprocess,json
exec(open('/tmp/dx/wild_build.py').read().split("wl=json.load")[0])
O='/mnt/user-data/outputs/dotafx'
MODELS=['models/props_gameplay/rune_haste01.vmdl','models/props_gameplay/rune_doubledamage01.vmdl','models/props_gameplay/rune_regeneration01.vmdl',
 'models/props_gameplay/rune_invisibility01.vmdl','models/props_gameplay/rune_arcane.vmdl','models/props_gameplay/rune_shield01.vmdl',
 'models/props_gameplay/rune_goldxp.vmdl','models/props_gameplay/rune_water.vmdl',
 'models/props_gameplay/fountain_of_life/fountain_of_life_update.vmdl','models/props_gameplay/fountain_of_life/fountain_of_life_consumable.vmdl']
done=[]
for model in MODELS:
    n=os.path.basename(model)[:-5]; od=O+'/'+n; os.makedirs(od,exist_ok=True)
    meshes,anims=parse(decompile(model))
    meshes=[m for m in meshes if '_lod' not in m]
    base='models/dota_fx/%s/'%n
    a=pick(anims,'idle') or (anims[0] if anims else None)
    rm='';mt=''
    for m in meshes:
        shutil.copy(G+'/'+m,od+'/'+os.path.basename(m))
        mt+='{\n_class = "RenderMeshFile"\nfilename = "%s%s"\nimport_translation = [ 0.0, 0.0, 0.0 ]\nimport_rotation = [ 0.0, 0.0, 0.0 ]\nimport_scale = 1.0\nalign_origin_x_type = "None"\nalign_origin_y_type = "None"\nalign_origin_z_type = "None"\nparent_bone = ""\nimport_filter = \n{\nexclude_by_default = false\nexception_list = [  ]\n}\n},\n'%(base,os.path.basename(m))
        for mp in mtl_paths(G+'/'+m):
            mp=mp.decode(); png=mat_png(mp,od); vm=os.path.basename(mp)
            if not png: continue
            glow='rune' in n
            body='\tshader "csgo_complex.vfx"\n'+('\tF_SELF_ILLUM 1\n\tg_flSelfIllumScale "2.5"\n\tTextureSelfIllumMask "%s%s"\n'%(base,png) if glow else '')
            open(od+'/'+vm,'w').write('// DotaCS\nLayer0\n{\n%s\tTextureColor "%s%s"\n}\n'%(body,base,png))
            rm+='{\nfrom = "%s"\nto = "%s%s"\n},\n'%(mp,base,vm)
    at=''
    if a:
        shutil.copy(G+'/'+a[1],od+'/'+os.path.basename(a[1])); at=animblock('idle',base+os.path.basename(a[1]),True)
    v=open('/mnt/user-data/outputs/units2/roshan/roshan.vmdl').read()
    v=re.sub(r'remaps = \n\[\n.*?\]\nuse_global_default','remaps = \n[\n'+rm+']\nuse_global_default',v,flags=re.S)
    v=re.sub(r'global_default_material = "[^"]*"','global_default_material = "materials/default/default.vmat"',v)
    v=re.sub(r'(_class = "RenderMeshList"\nchildren = \n\[\n).*?(\]\n\},\n\{\n_class = "AnimationList")',lambda m_: m_.group(1)+mt+m_.group(2),v,flags=re.S)
    v=re.sub(r'(_class = "AnimationList"\nchildren = \n\[\n).*?(\]\ndefault_root_bone_name = ""\n\},\n)',lambda m_: m_.group(1)+at+m_.group(2),v,flags=re.S)
    open(od+'/'+n+'.vmdl','w').write(v); done.append(n)
    print('FX',n,len(meshes),a[0] if a else None, rm.count('from'), [x[0] for x in anims][:6])
json.dump(done,open(O+'/list.json','w'))
