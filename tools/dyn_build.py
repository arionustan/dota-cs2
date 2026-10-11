import re,os,glob,shutil,subprocess,json
exec(open('/tmp/dx/wild_build.py').read().split("wl=json.load")[0])
O='/mnt/user-data/outputs/dyn'
D=json.load(open('/tmp/dx/instances_dyn.json'))
# trunk collision: 12-sided cylinder, radius 26, height 320 (model units = Dota units)
cyl=['v %.3f %.3f %.3f'%(26*__import__('math').sin(a*0.5236), z, 26*__import__('math').cos(a*0.5236)) for z in (0,320) for a in range(12)]
cf=['f %d %d %d'%(i+1,(i+1)%12+1,i+13) for i in range(12)]+['f %d %d %d'%((i+1)%12+1,(i+1)%12+13,i+13) for i in range(12)]
cf+=['f 1 %d %d'%(i+2,i+1) for i in range(1,11)]+['f 13 %d %d'%(i+13,i+14) for i in range(1,11)]
done=[]
for model in sorted({e['model'] for e in D}):
    n=os.path.basename(model)[:-5]; od=O+'/'+n; os.makedirs(od,exist_ok=True)
    meshes,anims=parse(decompile(model))
    meshes=[m for m in meshes if '_lod' not in m]
    base='models/dota_dyn/%s/'%n
    a=pick(anims,'idle') or (anims[0] if anims else None)
    rm='';mt=''
    for m in meshes:
        shutil.copy(G+'/'+m,od+'/'+os.path.basename(m))
        mt+='{\n_class = "RenderMeshFile"\nfilename = "%s%s"\nimport_translation = [ 0.0, 0.0, 0.0 ]\nimport_rotation = [ 0.0, 0.0, 0.0 ]\nimport_scale = 1.0\nalign_origin_x_type = "None"\nalign_origin_y_type = "None"\nalign_origin_z_type = "None"\nparent_bone = ""\nimport_filter = \n{\nexclude_by_default = false\nexception_list = [  ]\n}\n},\n'%(base,os.path.basename(m))
        for mp in mtl_paths(G+'/'+m):
            mp=mp.decode(); png=mat_png(mp,od); vm=os.path.basename(mp)
            if not png: continue
            leafy=any(k in vm for k in ('leaves','frond','leaf','moss','cattail','lily','007c'))
            if leafy:
                body='\tshader "csgo_foliage.vfx"\n\tF_ALPHA_TEST 1\n\tF_RENDER_BACKFACES 1\n\tF_VERTEX_ANIMATION 1\n\tg_flAlphaTestReference "0.5"\n\tg_flFlutterAmount "1.2"\n\tg_flFlutterFalloff "1.5"\n\tg_flFlutterNoiseScale "1.6"\n\tg_flFlutterSpeed "0.35"\n\tg_flSwayAmount "0.0"\n'
            else:
                body='\tshader "csgo_complex.vfx"\n'
            open(od+'/'+vm,'w').write('// DotaCS\nLayer0\n{\n%s\tTextureColor "%s%s"\n}\n'%(body,base,png))
            rm+='{\nfrom = "%s"\nto = "%s%s"\n},\n'%(mp,base,vm)
    at=''
    if a:
        shutil.copy(G+'/'+a[1],od+'/'+os.path.basename(a[1])); at=animblock('idle',base+os.path.basename(a[1]),True)
    phys=''
    if 'props_tree' in model:
        open(od+'/trunk.obj','w').write('o trunk\n'+'\n'.join(cyl)+'\nusemtl wood\n'+'\n'.join(cf)+'\n')
        phys='{\n_class = "PhysicsShapeList"\nchildren = \n[\n{\n_class = "PhysicsHullFile"\nname = "trunk"\nparent_bone = ""\nsurface_prop = "wood"\ncollision_tags = "solid"\nrecenter_on_parent_bone = false\noffset_origin = [ 0.0, 0.0, 0.0 ]\noffset_angles = [ 0.0, 0.0, 0.0 ]\nalign_origin_x_type = "None"\nalign_origin_y_type = "None"\nalign_origin_z_type = "None"\nfilename = "%strunk.obj"\nimport_scale = 1.0\nmaxMeshVertices = 0\nqemError = 0.0\nimport_filter = \n{\nexclude_by_default = false\nexception_list = [  ]\n}\n},\n]\n},\n'%base
    v=open('/mnt/user-data/outputs/units2/roshan/roshan.vmdl').read()
    v=re.sub(r'remaps = \n\[\n.*?\]\nuse_global_default','remaps = \n[\n'+rm+']\nuse_global_default',v,flags=re.S)
    v=re.sub(r'global_default_material = "[^"]*"','global_default_material = "materials/default/default.vmat"',v)
    v=re.sub(r'(_class = "RenderMeshList"\nchildren = \n\[\n).*?(\]\n\},\n\{\n_class = "AnimationList")',lambda m_: m_.group(1)+mt+m_.group(2),v,flags=re.S)
    v=re.sub(r'(_class = "AnimationList"\nchildren = \n\[\n).*?(\]\ndefault_root_bone_name = ""\n\},\n)',lambda m_: m_.group(1)+at+m_.group(2)+phys,v,flags=re.S)
    open(od+'/'+n+'.vmdl','w').write(v); done.append(n)
    print('DYN',n,len(meshes),a[0] if a else None, rm.count('from'), 'phys' if phys else '')
json.dump(done,open(O+'/list.json','w'))
