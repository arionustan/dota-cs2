import bpy, sys, os, json, re
a=sys.argv[sys.argv.index('--')+1:]; src,out,name=a[0],a[1],a[2]
os.makedirs(out,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for o in list(bpy.data.objects):
    if o.name.startswith('Icosphere'): bpy.data.objects.remove(o, do_unlink=True)
arms=[o for o in bpy.data.objects if o.type=='ARMATURE']
if not arms: print('NOARM'); sys.exit(0)
arm=arms[0]
for b in arm.pose.bones: b.custom_shape=None
for o in bpy.data.objects:
    if o.type=='MESH' and o.data.shape_keys: 
        bpy.context.view_layer.objects.active=o; o.shape_key_clear()
acts=list(bpy.data.actions); names=[x.name for x in acts]
def pick(keys, bad=()):
    c=[x for x in acts if any(k in x.name.lower() for k in keys) and not any(b in x.name.lower() for b in bad)]
    c.sort(key=lambda x:(len(x.name), x.name)); return c[0] if c else None
sel={'idle':pick(['idle'],['injured','rare','haste','alt','flail']),'run':pick(['run','walk'],['injured','haste','sprint','alt']),
     'attack':pick(['attack'],['alt','haste','anim_2','post','pre_','cast']),'death':pick(['death','die','dying'],['alt'])}
if not sel['idle']: sel['idle']=acts[0] if acts else None
def exp(path, anim):
    bpy.ops.export_scene.fbx(filepath=path, use_selection=anim, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
        bake_anim=anim, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, add_leaf_bones=False,
        path_mode='STRIP', embed_textures=False, mesh_smooth_type='FACE', use_mesh_modifiers=False, object_types={'ARMATURE','MESH'} if not anim else {'ARMATURE'})
if not arm.animation_data: arm.animation_data_create()
arm.animation_data.action=None
exp(os.path.join(out,name+'_ref.fbx'), False)
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active=arm
got={}
for k,act in sel.items():
    if not act: continue
    arm.animation_data.action=act
    fr=act.frame_range; bpy.context.scene.frame_start=int(fr[0]); bpy.context.scene.frame_end=max(int(fr[1]),int(fr[0])+1)
    exp(os.path.join(out,name+'_'+k+'.fbx'), True); got[k]=act.name
mats={}
for m in bpy.data.materials:
    if not m.use_nodes: continue
    for n in m.node_tree.nodes:
        if n.type=='BSDF_PRINCIPLED':
            l=n.inputs['Base Color'].links
            if l and l[0].from_node.type=='TEX_IMAGE' and l[0].from_node.image:
                mats[m.name]=os.path.basename(l[0].from_node.image.filepath or l[0].from_node.image.name)
json.dump({'anims':got,'all':names,'mats':mats},open(os.path.join(out,'info.json'),'w'),indent=1)
print('UNIT',name,got,len(mats))
