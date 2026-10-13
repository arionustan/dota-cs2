# Dota 2 Pudge (Blender scene) -> Warcraft III MDX (v800) with BLP textures. Run with bpy available.
import bpy, sys, os, math, json
import numpy as np
from mathutils import Matrix, Vector
sys.path.insert(0, '/tmp/w3')
import mdx, blp
from PIL import Image

OUT = sys.argv[-1] if sys.argv[-1].startswith('/') else '/tmp/w3/out/pudge_wc3'
os.makedirs(OUT, exist_ok=True)
SCALE = 45.0
G = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Scale(SCALE, 4)   # Dota faces -Y here, WC3 faces +X
Ginv = G.inverted()
TEXDIR = '/tmp/dx/pudge'
PREFIX = 'war3mapImported\\'
PART_TEX = {'pudge_model': 'body', 'part_back_0': 'apron', 'part_belt_0': 'waist', 'part_bracer_0': 'bracer',
            'part_hair_0': 'hair', 'part_leftarm_0': 'armleft', 'part_leftweapon_0': 'chopper', 'part_righthook_0': 'hook'}
SEQS = [('pudge_idle_anim', 'Stand', 0, 0.0), ('pudge_walkN_anim', 'Walk', 0, 250.0), ('pudge_attack1_anim', 'Attack', 0, 0.0),
        ('pudge_meathook_start_anim', 'Spell', 1, 0.0), ('pudge_stun_anim', 'Stand Channel', 0, 0.0),
        ('pudge_run_haste_anim', 'Walk Fast', 0, 400.0), ('pudge_death', 'Death', 1, 0.0)]
FPS = 24.0

bpy.ops.wm.open_mainfile(filepath='/tmp/dx/pudge3.blend')
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
AW = arm.matrix_world.copy(); AWi = AW.inverted()
bones = list(arm.data.bones)
bidx = {b.name: i for i, b in enumerate(bones)}

arm.data.pose_position = 'REST'
bpy.context.view_layer.update()

def gm(m):  # armature-world matrix -> WC3 model space
    return G @ m @ Ginv

pivots = [tuple(G @ (AW @ b.head_local)) for b in bones]

# ---------------------------------------------------------------- textures
tex_files, tex_alpha = [], {}
def tex_for(part):
    key = PART_TEX[part]
    src = [f for f in os.listdir(TEXDIR) if f.startswith('pudge2_%s_color' % key)][0]
    name = 'DotaPudge_%s.blp' % key
    if name not in tex_files:
        im = Image.open(os.path.join(TEXDIR, src))
        if im.size[0] < 8: im = Image.new('RGBA', (8, 8), (58, 40, 30, 255))   # hair uses a special Dota shader, give it a plain colour
        tex_alpha[name] = blp.save_blp1(im, os.path.join(OUT, name))
        tex_files.append(name)
    return tex_files.index(name)

# ---------------------------------------------------------------- geosets
geosets, materials = [], []
allv = []
for o in [o for o in bpy.data.objects if o.type == 'MESH']:
    part = o.name.split('.')[-1]
    me = o.data
    me.calc_loop_triangles()
    uvl = me.uv_layers.active.data
    try: cn = me.corner_normals
    except AttributeError: me.calc_normals_split(); cn = None
    vgname = {g.index: g.name for g in o.vertex_groups}
    OW = o.matrix_world
    NW = (G @ OW).to_3x3().inverted().transposed()
    verts, norms, uvs, gndx, faces = [], [], [], [], []
    groups, gmap, vmap = [], {}, {}
    for lt in me.loop_triangles:
        for li in lt.loops:
            vi = me.loops[li].vertex_index
            uv = tuple(uvl[li].uv)
            n = tuple(cn[li].vector) if cn is not None else tuple(me.loops[li].normal)
            key = (vi, round(uv[0], 5), round(uv[1], 5), round(n[0], 3), round(n[1], 3), round(n[2], 3))
            if key not in vmap:
                v = me.vertices[vi]
                ws = sorted(((g.weight, vgname[g.group]) for g in v.groups if vgname.get(g.group) in bidx), reverse=True)
                if not ws: grp = (0,)
                else:
                    top = ws[0][0]
                    grp = tuple(sorted(bidx[n2] for w, n2 in ws[:3] if w >= max(0.25, top * 0.4)))
                if grp not in gmap: gmap[grp] = len(groups); groups.append(grp)
                vmap[key] = len(verts)
                p = G @ (OW @ v.co)
                verts.append(tuple(p)); allv.append(tuple(p))
                nn = (NW @ Vector(n)).normalized(); norms.append(tuple(nn))
                uvs.append((uv[0], 1.0 - uv[1])); gndx.append(gmap[grp])
            faces.append(vmap[key])
    assert len(groups) <= 256, part
    va = np.array(verts)
    materials.append([(1 if tex_alpha.get('DotaPudge_%s.blp' % PART_TEX[part], False) else 0, 0x10, tex_for(part), 1.0)])
    # alpha known only after tex_for; fix the filter now
    tname = 'DotaPudge_%s.blp' % PART_TEX[part]
    materials[-1] = [(1 if tex_alpha[tname] else 0, 0x10, tex_files.index(tname), 1.0)]
    geosets.append({'verts': verts, 'normals': norms, 'uvs': uvs, 'faces': faces, 'gndx': gndx,
                    'mtgc': [len(g) for g in groups], 'mats': [b for g in groups for b in g],
                    'material': len(materials) - 1, 'extent': (tuple(va.min(0)), tuple(va.max(0)))})
    print(part, len(verts), 'verts', len(faces) // 3, 'tris', len(groups), 'groups')

# ---------------------------------------------------------------- animations
arm.data.pose_position = 'POSE'
arm.animation_data_create()
rest_inv = [ (AW @ b.matrix_local).inverted() for b in bones ]
keys_t = {i: [] for i in range(len(bones))}
keys_r = {i: [] for i in range(len(bones))}
seqs = []
t0 = 0
for act, wname, nonloop, speed in SEQS:
    a = bpy.data.actions.get(act)
    if not a: continue
    arm.animation_data.action = a
    f0, f1 = a.frame_range
    nfr = int(math.ceil(f1 - f0)) + 1
    start = t0 + 100
    for k in range(nfr):
        f = f0 + k
        bpy.context.scene.frame_set(int(f), subframe=f - int(f))
        D = {}
        for i, b in enumerate(bones):
            pb = arm.pose.bones[b.name]
            D[i] = gm((AW @ pb.matrix) @ rest_inv[i])
        ms = start + int(round(k / FPS * 1000))
        for i, b in enumerate(bones):
            par = bidx[b.parent.name] if b.parent else -1
            L = (D[par].inverted() @ D[i]) if par >= 0 else D[i]
            p = Vector(pivots[i])
            M3 = L.to_3x3()
            t = L.translation - p + M3 @ p
            q = L.to_quaternion()
            if par < 0 and wname.startswith('Walk'): t.x = 0.0; t.y = 0.0   # WC3 walk cycles stay in place
            keys_t[i].append((ms, (t.x, t.y, t.z)))
            keys_r[i].append((ms, (q.x, q.y, q.z, q.w)))
    end = start + int(round((nfr - 1) / FPS * 1000))
    seqs.append((wname, start, end, speed, nonloop))
    t0 = end
    print('seq', wname, start, end)

bones_out = []
for i, b in enumerate(bones):
    bones_out.append({'name': b.name, 'parent': bidx[b.parent.name] if b.parent else -1,
                      'tracks': [mdx.w_track('KGTR', keys_t[i]), mdx.w_track('KGRT', keys_r[i])]})

def att(name, bone, dz=0.0):
    i = bidx[bone]; p = pivots[i]
    return {'name': name, 'parent': i, 'pivot': (p[0], p[1], p[2] + dz)}
atts = [att('Origin Ref', 'root'), att('Overhead Ref', 'head', 60.0), att('Head Ref', 'head'), att('Chest Ref', 'spine3'),
        att('Hand Left Ref', 'wrist_L'), att('Hand Right Ref', 'wrist_R'), att('Weapon Ref', 'weapon_lf_2')]
for j, a in enumerate(atts): a['attid'] = j

va = np.array(allv)
model = {'name': 'DotaPudge', 'extent': (tuple(va.min(0)), tuple(va.max(0))), 'seqs': seqs,
         'textures': [(0, PREFIX + t) for t in tex_files], 'materials': materials, 'geosets': geosets,
         'bones': bones_out, 'attachments': atts, 'pivots': pivots + [a['pivot'] for a in atts]}
open(os.path.join(OUT, 'DotaPudge.mdx'), 'wb').write(mdx.save(model))
print('extent', va.min(0), va.max(0), 'textures', tex_files, tex_alpha)
