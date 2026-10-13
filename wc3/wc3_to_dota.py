# Converts a Warcraft III MDX model into SMD meshes/animations + vmdl + vmat for a Dota 2 custom game.
# usage: python3 wc3_to_dota.py <model.mdx> <outdir> <name> <texdir-with-blps>
import sys, os, re, math, json
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdx

FPS = 30

ACT = [  # (WC3 sequence name regex, Dota activity, looping)
    (r'^stand$', 'ACT_DOTA_IDLE', True),
    (r'^stand - \d+$', 'ACT_DOTA_IDLE_RARE', False),
    (r'^stand ready$', 'ACT_DOTA_IDLE', True),
    (r'^walk$', 'ACT_DOTA_RUN', True),
    (r'^attack( \d+)?$', 'ACT_DOTA_ATTACK', False),
    (r'^attack slam$', 'ACT_DOTA_CAST_ABILITY_2', False),
    (r'spin', 'ACT_DOTA_CAST_ABILITY_1', True),
    (r'^spell', 'ACT_DOTA_CAST_ABILITY_3', False),
    (r'^death$', 'ACT_DOTA_DIE', False),
    (r'^stand victory$', 'ACT_DOTA_VICTORY', True),
    (r'^stand channel$', 'ACT_DOTA_CHANNEL_ABILITY_4', True),
]

def quat_mat(q):
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])

def slerp(a, b, t):
    a = np.array(a); b = np.array(b)
    d = float(np.dot(a, b))
    if d < 0: b = -b; d = -d
    if d > 0.9995:
        r = a + t * (b - a); return r / np.linalg.norm(r)
    th = math.acos(d)
    return (math.sin((1 - t) * th) * a + math.sin(t * th) * b) / math.sin(th)

def eval_track(tr, t, seq, glbs, default):
    if tr is None: return default
    keys = tr['keys']
    if tr['gs'] >= 0 and tr['gs'] < len(glbs) and glbs[tr['gs']] > 0:
        t = (t - seq['start']) % glbs[tr['gs']]
    else:
        keys = [k for k in keys if seq['start'] <= k[0] <= seq['end']]
    if not keys: return default
    if t <= keys[0][0]: return keys[0][1]
    if t >= keys[-1][0]: return keys[-1][1]
    for i in range(len(keys) - 1):
        f0, v0 = keys[i][0], keys[i][1]; f1, v1 = keys[i + 1][0], keys[i + 1][1]
        if f0 <= t <= f1:
            if tr['interp'] == 0: return v0
            u = (t - f0) / max(1, f1 - f0)
            if len(v0) == 4: return tuple(slerp(v0, v1, u))
            return tuple(a + (b - a) * u for a, b in zip(v0, v1))
    return keys[-1][1]

def world_mats(m, t, seq):
    piv = m['pivots']; out = {}
    def get(i):
        if i in out: return out[i]
        n = m['nodes'][i]
        p = np.array(piv[i]) if i < len(piv) else np.zeros(3)
        tr = n['tracks']
        T = np.array(eval_track(tr.get('KGTR'), t, seq, m['glbs'], (0, 0, 0)))
        Q = eval_track(tr.get('KGRT'), t, seq, m['glbs'], (0, 0, 0, 1))
        S = np.array(eval_track(tr.get('KGSC'), t, seq, m['glbs'], (1, 1, 1)))
        L = np.eye(4)
        RS = quat_mat(Q) @ np.diag(S)
        L[:3, :3] = RS
        L[:3, 3] = p + T - RS @ p
        par = n['parent']
        W = (get(par) @ L) if par >= 0 and par in m['nodes'] else L
        out[i] = W
        return W
    for i in m['nodes']: get(i)
    return out

def mat_euler(R):
    # Source SMD: rotation (x, y, z) radians, R = Rz * Ry * Rx
    sy = -R[2, 0]
    y = math.asin(max(-1, min(1, sy)))
    if abs(sy) < 0.9999:
        x = math.atan2(R[2, 1], R[2, 2]); z = math.atan2(R[1, 0], R[0, 0])
    else:
        x = math.atan2(-R[1, 2], R[1, 1]); z = 0.0
    return x, y, z

def ortho(M):
    U, _, Vt = np.linalg.svd(M[:3, :3]); R = U @ Vt
    if np.linalg.det(R) < 0: U[:, -1] *= -1; R = U @ Vt
    out = M.copy(); out[:3, :3] = R
    return out

def blp_to_png(src, dst, team_rgb=None):
    im = Image.open(src).convert('RGBA')
    if team_rgb is not None:
        bg = Image.new('RGBA', im.size, team_rgb + (255,))
        im = Image.alpha_composite(bg, im)
    im.save(dst)

def convert(mdx_path, outdir, name, texdir, scale=1.0, keep_filters=(0, 1, 2)):
    m = mdx.load(open(mdx_path, 'rb').read())
    os.makedirs(outdir, exist_ok=True)
    ids = sorted(m['nodes'])
    bname = {}
    for i in ids:
        nm = re.sub(r'[^A-Za-z0-9_]', '_', m['nodes'][i]['name']) or 'node'
        bname[i] = '%s_%d' % (nm, i)
    # bones in an order where parents come first
    order = []
    def add(i):
        if i in order: return
        p = m['nodes'][i]['parent']
        if p >= 0 and p in m['nodes']: add(p)
        order.append(i)
    for i in ids: add(i)
    smd_id = {i: k for k, i in enumerate(order)}
    piv = m['pivots']
    def pv(i): return np.array(piv[i]) if i < len(piv) else np.zeros(3)

    nodes_txt = 'nodes\n' + ''.join('%d "%s" %d\n' % (smd_id[i], bname[i], smd_id[m['nodes'][i]['parent']] if m['nodes'][i]['parent'] in m['nodes'] else -1) for i in order) + 'end\n'

    def skel_frame(fi, worlds):
        s = 'time %d\n' % fi
        for i in order:
            W = worlds[i]; par = m['nodes'][i]['parent']
            Pw = worlds[par] if par in m['nodes'] else np.eye(4)
            Lc = np.linalg.inv(Pw) @ W
            x, y, z = mat_euler(Lc[:3, :3])
            tx, ty, tz = Lc[:3, 3] * scale
            s += '%d %.6f %.6f %.6f %.6f %.6f %.6f\n' % (smd_id[i], tx, ty, tz, x, y, z)
        return s

    bind = {i: (lambda M: (M.__setitem__((slice(0, 3), 3), pv(i)), M)[1])(np.eye(4)) for i in order}

    # ---------------- materials and textures
    tex_png = {}
    for ti, t in enumerate(m['textures']):
        if t['file']:
            base = os.path.splitext(t['file'].split('\\')[-1])[0].lower()
            src = os.path.join(texdir, t['file'].split('\\')[-1])
            if os.path.exists(src): tex_png[ti] = base
    mats = {}
    for mi, mt in enumerate(m['materials']):
        L = [l for l in mt['layers'] if l['filter'] in keep_filters and l['texture'] in tex_png]
        if not L: continue
        team = any(l['texture'] < len(m['textures']) and m['textures'][l['texture']]['replaceable'] == 1 for l in mt['layers'])
        top = L[-1]; base = tex_png[top['texture']]
        png = base + ('_team' if team else '') + '.png'
        blp_to_png(os.path.join(texdir, m['textures'][top['texture']]['file'].split('\\')[-1]), os.path.join(outdir, png), (180, 20, 20) if team else None)
        mats[mi] = (png[:-4], top['filter'] == 1 and not team)

    # ---------------- reference mesh
    tri = 'triangles\n'; kept = 0
    for g in m['geosets']:
        if g['material'] not in mats: continue
        kept += 1
        groups = []; k = 0
        for c in g['mtgc']: groups.append(g['mats'][k:k + c]); k += c
        uv = g['uvs'][0]; matname = mats[g['material']][0]
        f = g['faces']
        for t0 in range(0, len(f) - 2, 3):
            tri += matname + '\n'
            for vi in (f[t0], f[t0 + 1], f[t0 + 2]):
                v = np.array(g['verts'][vi]) * scale; n = g['normals'][vi]; u = uv[vi]
                bones = [b for b in groups[g['gndx'][vi]] if b in smd_id] or [order[0]]
                w = 1.0 / len(bones)
                links = ' '.join('%d %.4f' % (smd_id[b], w) for b in bones)
                tri += '%d %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %d %s\n' % (smd_id[bones[0]], v[0], v[1], v[2], n[0], n[1], n[2], u[0], 1 - u[1], len(bones), links)
    tri += 'end\n'
    ref = 'version 1\n' + nodes_txt + 'skeleton\n' + skel_frame(0, bind) + 'end\n' + tri
    open(os.path.join(outdir, name + '_ref.smd'), 'w').write(ref)

    # ---------------- animations
    anims = []
    for s in m['seqs']:
        low = s['name'].lower().strip()
        hit = next(((a, lp) for rx, a, lp in ACT if re.search(rx, low)), None)
        if not hit: continue
        act, loop = hit
        fname = re.sub(r'[^a-z0-9]+', '_', low).strip('_')
        dur = max(1, s['end'] - s['start'])
        nf = max(2, int(round(dur / 1000.0 * FPS)) + 1)
        sk = 'skeleton\n'
        for fi in range(nf):
            t = s['start'] + dur * fi / (nf - 1)
            W = world_mats(m, t, s)
            worlds = {i: ortho(W[i] @ bind[i]) for i in order}
            sk += skel_frame(fi, worlds)
        sk += 'end\n'
        open(os.path.join(outdir, '%s_%s.smd' % (name, fname)), 'w').write('version 1\n' + nodes_txt + sk)
        anims.append((fname, act, loop))
    return mats, anims, kept

def write_vmdl(outdir, name, folder, mats, anims):
    def anim(a):
        fname, act, loop = a
        return '''{
_class = "AnimFile"
name = "%s"
activity_name = "%s"
activity_weight = 1
weight_list_name = ""
fade_in_time = 0.2
fade_out_time = 0.2
looping = %s
delta = false
worldSpace = false
hidden = false
anim_markup_ordered = false
disable_compression = false
source_filename = "%s/%s_%s.smd"
start_frame = -1
end_frame = -1
framerate = -1.0
take = 0
reverse = false
},''' % (fname, act, 'true' if loop else 'false', folder, name, fname)
    remaps = ''.join('{\nfrom = "%s.vmat"\nto = "%s/%s.vmat"\n},\n' % (mn, folder, mn) for mn, _ in mats.values())
    v = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc29:version{3cec427c-1b0e-4d48-a90a-0436f33a6041} -->
{
rootNode =
{
_class = "RootNode"
children =
[
{
_class = "MaterialGroupList"
children =
[
{
_class = "DefaultMaterialGroup"
remaps =
[
%s]
use_global_default = false
global_default_material = ""
},
]
},
{
_class = "RenderMeshList"
children =
[
{
_class = "RenderMeshFile"
filename = "%s/%s_ref.smd"
import_translation = [ 0.0, 0.0, 0.0 ]
import_rotation = [ 0.0, 0.0, 0.0 ]
import_scale = 1.0
align_origin_x_type = "None"
align_origin_y_type = "None"
align_origin_z_type = "None"
parent_bone = ""
import_filter =
{
exclude_by_default = false
exception_list = [  ]
}
},
]
},
{
_class = "AnimationList"
children =
[
%s
]
default_root_bone_name = ""
},
]
model_archetype = ""
primary_associated_entity = ""
anim_graph_name = ""
base_model_name = ""
}
}
''' % (remaps, folder, name, '\n'.join(anim(a) for a in anims))
    open(os.path.join(outdir, name + '.vmdl'), 'w').write(v)
    for mn, alpha in mats.values():
        vm = 'Layer0\n{\n\tshader "global_lit_simple.vfx"\n\n\tTextureColor "%s/%s.png"\n' % (folder, mn)
        if alpha: vm += '\tF_ALPHA_TEST 1\n\tg_flAlphaTestReference "0.5"\n'
        vm += '}\n'
        open(os.path.join(outdir, mn + '.vmat'), 'w').write(vm)

if __name__ == '__main__':
    src, out, name, texdir = sys.argv[1:5]
    folder = sys.argv[5] if len(sys.argv) > 5 else 'models/wc3/' + name
    mats, anims, kept = convert(src, out, name, texdir)
    write_vmdl(out, name, folder, mats, anims)
    print('geosets', kept, 'materials', mats, 'anims', anims)
