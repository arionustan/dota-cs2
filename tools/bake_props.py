# Blender: bake Dota buildings/trees into tiled OBJ files in Dota coordinates (inches after export scale)
import bpy, sys, os, json, math, mathutils
args=sys.argv[sys.argv.index('--')+1:]
inst_file, glbdir, outdir = args[0], args[1], args[2]
TREE_TRIS=int(os.environ.get('TREE_TRIS','700')); BIG_TRIS=int(os.environ.get('BIG_TRIS','40000'))
inst=json.load(open(inst_file))   # [{model, origin, angles, scales}]
bpy.ops.wm.read_factory_settings(use_empty=True)
R=mathutils.Matrix.Rotation(math.radians(90),4,'Z')
templates={}
def load_template(model):
    name=os.path.basename(model).replace('.vmdl','')
    path=os.path.join(glbdir,name+'.glb')
    if not os.path.exists(path): print('NOGLB',name); return None
    before=set(bpy.data.objects)
    try: bpy.ops.import_scene.gltf(filepath=path)
    except Exception as ex: print('BADGLB',name,ex); return None
    new=[o for o in bpy.data.objects if o not in before]
    meshes=[]
    for o in new:
        if o.type=='MESH' and not o.name.startswith('Icosphere'):
            mw=R @ o.matrix_world
            me=o.data.copy()
            if me.shape_keys:
                tmp=bpy.data.objects.new('tmp',me); tmp.shape_key_clear(); bpy.data.objects.remove(tmp)
            me.transform(mw)
            ob=bpy.data.objects.new(name+'_part',me); bpy.context.scene.collection.objects.link(ob)
            meshes.append(ob)
    for o in new: bpy.data.objects.remove(o, do_unlink=True)
    if not meshes: print('NOMESH',name); return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes: o.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    if len(meshes)>1: bpy.ops.object.join()
    t=bpy.context.view_layer.objects.active; t.name='T_'+name
    if t.data.shape_keys: t.shape_key_clear()
    tris=sum(len(p.vertices)-2 for p in t.data.polygons)
    target=TREE_TRIS if 'props_tree' in model else BIG_TRIS
    if tris>target:
        m=t.modifiers.new('dec','DECIMATE'); m.ratio=target/tris; m.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier='dec')
    print('TEMPLATE',name,tris,'->',sum(len(p.vertices)-2 for p in t.data.polygons))
    t.hide_set(True)
    return t
tiles={}
for e in inst:
    m=e['model']
    if m not in templates: templates[m]=load_template(m)
    t=templates[m]
    if t is None: continue
    ox,oy,oz=[v*0.0254 for v in e['origin']]
    p,y,r=[math.radians(a) for a in e.get('angles',[0,0,0])]
    s=e.get('scales',[1,1,1])
    M=(mathutils.Matrix.Translation((ox,oy,oz)) @ mathutils.Matrix.Rotation(y,4,'Z') @ mathutils.Matrix.Rotation(p,4,'Y')
       @ mathutils.Matrix.Rotation(r,4,'X') @ mathutils.Matrix.Diagonal((s[0],s[1],s[2],1)))
    me=t.data.copy(); me.transform(M)
    ob=bpy.data.objects.new('I',me); bpy.context.scene.collection.objects.link(ob)
    tx=min(3,max(0,int((e['origin'][0]+8500)//4250))); ty=min(3,max(0,int((e['origin'][1]+8500)//4250)))
    tiles.setdefault((tx,ty),[]).append(ob)
for t in templates.values():
    if t: bpy.data.objects.remove(t, do_unlink=True)
for (tx,ty),obs in sorted(tiles.items()):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active=obs[0]
    bpy.ops.object.join()
    o=bpy.context.view_layer.objects.active
    out=os.path.join(outdir,'props_%d%d.obj'%(tx,ty))
    bpy.ops.wm.obj_export(filepath=out, forward_axis='Y', up_axis='Z', global_scale=39.3701, export_selected_objects=True,
        export_materials=True, export_uv=True, export_normals=True, path_mode='STRIP')
    print('TILE',out,sum(len(p.vertices)-2 for p in o.data.polygons))
    bpy.data.objects.remove(o, do_unlink=True)
