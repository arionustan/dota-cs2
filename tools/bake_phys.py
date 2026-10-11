# Blender: low-poly collision for props: trees -> 8-sided trunks, others -> decimated mesh
import bpy, sys, os, json, math, mathutils, bmesh
args=sys.argv[sys.argv.index('--')+1:]
inst_file, glbdir, out = args[0], args[1], args[2]
inst=json.load(open(inst_file))
bpy.ops.wm.read_factory_settings(use_empty=True)
R=mathutils.Matrix.Rotation(math.radians(90),4,'Z')
SKIP=('props_nature','props_teams','logo','banner','flag','lily','cattails')
templates={}
def trunk():
    bm=bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.45, radius2=0.35, depth=6.0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0,0,3.0))
    me=bpy.data.meshes.new('trunk'); bm.to_mesh(me); return me
def load(model):
    name=os.path.basename(model).replace('.vmdl','')
    if 'props_tree' in model: return trunk()
    path=os.path.join(glbdir,name+'.glb')
    if not os.path.exists(path): return None
    before=set(bpy.data.objects)
    try: bpy.ops.import_scene.gltf(filepath=path)
    except Exception: return None
    new=[o for o in bpy.data.objects if o not in before]
    bm=bmesh.new()
    for o in new:
        if o.type=='MESH' and not o.name.startswith('Icosphere'):
            me=o.data.copy(); me.transform(R @ o.matrix_world); bm.from_mesh(me)
    for o in new: bpy.data.objects.remove(o, do_unlink=True)
    me=bpy.data.meshes.new(name+'_phys'); bm.to_mesh(me)
    ob=bpy.data.objects.new('tmp',me); bpy.context.scene.collection.objects.link(ob)
    if ob.data.shape_keys: ob.shape_key_clear()
    tris=sum(len(p.vertices)-2 for p in me.polygons)
    if tris>600:
        bpy.context.view_layer.objects.active=ob
        m=ob.modifiers.new('d','DECIMATE'); m.ratio=600/tris; m.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier='d')
    me=ob.data; bpy.data.objects.remove(ob)
    return me
bm=bmesh.new()
for e in inst:
    m=e['model']
    if any(s in m for s in SKIP): continue
    if m not in templates: templates[m]=load(m)
    t=templates[m]
    if t is None: continue
    ox,oy,oz=[v*0.0254 for v in e['origin']]
    p,y,r=[math.radians(a) for a in e.get('angles',[0,0,0])]
    s=e.get('scales',[1,1,1])
    M=(mathutils.Matrix.Translation((ox,oy,oz)) @ mathutils.Matrix.Rotation(y,4,'Z') @ mathutils.Matrix.Rotation(p,4,'Y')
       @ mathutils.Matrix.Rotation(r,4,'X') @ mathutils.Matrix.Diagonal((s[0],s[1],s[2],1)))
    me=t.copy(); me.transform(M); bm.from_mesh(me); bpy.data.meshes.remove(me)
me=bpy.data.meshes.new('props_phys'); bm.to_mesh(me)
ob=bpy.data.objects.new('props_phys',me); bpy.context.scene.collection.objects.link(ob)
mat=bpy.data.materials.new('tree_gnarly001'); me.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True)
bpy.ops.wm.obj_export(filepath=out, forward_axis='Y', up_axis='Z', global_scale=39.3701, export_selected_objects=True,
    export_materials=True, export_uv=False, export_normals=False, path_mode='STRIP')
print('PHYS',sum(len(p.vertices)-2 for p in me.polygons))
