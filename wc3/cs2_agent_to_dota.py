# Converts a CS2 agent (exported by Source2Viewer to glTF: mesh + separate animation clips) into
# SMD + vmdl + vmat for Dota 2. Skinning comes from the model's own skeleton (vmdl DATA dump),
# the clips are retargeted by world-space matching against the clip skeleton's bind pose.
import sys, os, json, numpy as np
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glb import GLB
from vmdlskel import parse
from wc3_to_dota import write_vmdl
from PIL import Image

FPS = 30
MESHES = ('thirdperson_body', 'thirdperson_default_gloves')

def mat(t, q):
    M = np.eye(4); M[:3, :3] = Rot.from_quat(q).as_matrix(); M[:3, 3] = t; return M

def ortho(M):
    u, _, vt = np.linalg.svd(M[:3, :3]); O = M.copy(); O[:3, :3] = u @ vt; return O

def euler(Rm):
    return Rot.from_matrix(Rm).as_euler('xyz')        # SMD: R = Rz * Ry * Rx

# mesh glTF (meters, as exported) -> source inches; found by matching weighted vertices to bones
MESH_AX = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], float)
WPN_FIX = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], float)   # found by aligning the barrel with the aim

def clip_worlds(g, times):
    nodes = g.j['nodes']
    trs = [[np.array(n.get('translation', [0, 0, 0]), float), np.array(n.get('rotation', [0, 0, 0, 1]), float),
            np.array(n.get('scale', [1, 1, 1]), float)] for n in nodes]
    chans = []
    for an in g.j.get('animations', []):
        for ch in an['channels']:
            s = an['samplers'][ch['sampler']]
            chans.append((ch['target']['node'], ch['target']['path'], g.acc(s['input']).ravel(), g.acc(s['output'])))
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []): parent[c] = i
    out = []
    for t in times:
        cur = [[a.copy() for a in x] for x in trs]
        for ni, path, ti, vo in chans:
            k = {'translation': 0, 'rotation': 1, 'scale': 2}[path]
            if len(ti) == 1: v = vo[0]
            else:
                j = np.searchsorted(ti, t)
                if j <= 0: v = vo[0]
                elif j >= len(ti): v = vo[-1]
                else:
                    f = (t - ti[j - 1]) / (ti[j] - ti[j - 1]); a, b = vo[j - 1], vo[j]
                    if k == 1 and np.dot(a, b) < 0: b = -b
                    v = a * (1 - f) + b * f
                    if k == 1: v = v / np.linalg.norm(v)
            cur[ni][k] = np.array(v, float)
        W = {}
        def w(i):
            if i in W: return W[i]
            L = mat(cur[i][0], cur[i][1]) @ np.diag(list(cur[i][2]) + [1])
            W[i] = (w(parent[i]) @ L) if i in parent else L
            return W[i]
        out.append({nodes[i]['name']: w(i) for i in range(len(nodes))})
    return out

def duration(g):
    m = 0.0
    for an in g.j.get('animations', []):
        for s in an['samplers']: m = max(m, float(g.acc(s['input']).max()))
    return m

def convert(agent_glb, vmdl_dump, clips, outdir, name, folder, texdir, weapon=None):
    os.makedirs(outdir, exist_ok=True)
    names, par, bpos, brot, _, _ = parse(vmdl_dump)
    nb = len(names)
    bind = []
    for i in range(nb):
        L = mat(bpos[i], brot[i]); bind.append(L if par[i] < 0 else bind[par[i]] @ L)
    bind_local = [mat(bpos[i], brot[i]) for i in range(nb)]
    WPN = weapon is not None
    if WPN:     # the rifle hangs on the clip skeleton's "wpn" bone, added as a child of the root
        names = list(names) + ['wpn']; par = list(par) + [0]
        nb += 1
        bind.append(np.eye(4)); bind_local.append(np.eye(4))

    nodes_txt = 'nodes\n' + ''.join('%d "%s" %d\n' % (i, names[i], par[i]) for i in range(nb)) + 'end\n'

    def frame(fi, worlds):
        s = 'time %d\n' % fi
        for i in range(nb):
            L = worlds[i] if par[i] < 0 else np.linalg.inv(worlds[par[i]]) @ worlds[i]
            x, y, z = euler(L[:3, :3]); tx, ty, tz = L[:3, 3]
            s += '%d %.6f %.6f %.6f %.6f %.6f %.6f\n' % (i, tx, ty, tz, x, y, z)
        return s

    state = {}; anim_files = []
    # ---------- animations
    anims = []
    for fname, path, act, loop, speed in clips:
        cg = GLB(path)
        skin = cg.j['skins'][0]
        ibm = cg.acc(skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)
        jn = [cg.j['nodes'][k]['name'] for k in skin['joints']]
        cbind = {n: np.linalg.inv(ibm[i]) for i, n in enumerate(jn)}
        common = [n for n in jn if n in names and n != 'wpn']
        # clip glTF space -> source: signed axis permutation + inches, found from the bind positions
        A = np.array([cbind[n][:3, 3] for n in common]) / 0.0254
        B = np.array([bind[names.index(n)][:3, 3] for n in common])
        import itertools
        best = None
        for perm in itertools.permutations(range(3)):
            for sg in itertools.product([1, -1], repeat=3):
                M = np.zeros((3, 3))
                for i in range(3): M[i, perm[i]] = sg[i]
                e = np.abs(A @ M.T - B).mean()
                if best is None or e < best[0]: best = (e, M)
        AX = best[1]

        def conv(G):
            S = np.eye(4); S[:3, :3] = AX @ ortho(G)[:3, :3] @ AX.T; S[:3, 3] = AX @ G[:3, 3] / 0.0254
            return S
        K = {n: np.linalg.inv(conv(cbind[n])) @ bind[names.index(n)] for n in common}
        dur = max(duration(cg), 1.0 / FPS)
        nf = max(2, int(round(dur * FPS)) + 1)
        times = np.linspace(0, dur, nf)
        frames = clip_worlds(cg, times)
        root = names[0]
        sk = ['skeleton\n']
        for fi, Wd in enumerate(frames):
            S = {}
            for n in common: S[n] = conv(Wd[n]) @ K[n]
            if WPN and 'wpn' in Wd: S['wpn'] = conv(Wd['wpn'])
            if root in S:      # keep the model in place (Dota moves the unit itself)
                fix = bind[0] @ np.linalg.inv(S[root])
                for n in S: S[n] = fix @ S[n]
            if WPN and fi == 0 and 'wpn_ref' not in state:
                state['wpn_ref'] = S.get('wpn', np.eye(4)); state['hand_ref'] = S.get('hand_R')
            worlds = []
            for i in range(nb):
                if names[i] in S: worlds.append(S[names[i]])
                else: worlds.append(bind_local[i] if par[i] < 0 else worlds[par[i]] @ bind_local[i])
            sk.append(frame(fi, worlds))
        sk.append('end\n')
        anim_files.append(('%s_%s.smd' % (name, fname), ''.join(sk)))
        anims.append((fname, act, loop))
        print(fname, 'frames', nf, 'axis err', round(best[0], 2), 'bones', len(common))
    # ---------- reference mesh
    g = GLB(agent_glb); j = g.j
    mats = {}
    tri = ['triangles\n']
    for mesh in j['meshes']:
        if not any(mesh['name'].endswith(m) for m in MESHES): continue
        for pr in mesh['primitives']:
            a = pr['attributes']
            P = g.acc(a['POSITION']) @ MESH_AX.T / 0.0254
            N = g.acc(a['NORMAL']) @ MESH_AX.T
            UV = g.acc(a['TEXCOORD_0']); J = g.acc(a['JOINTS_0']).astype(int); Wt = g.acc(a['WEIGHTS_0']).astype(float)
            idx = g.acc(pr['indices']).ravel()
            mt = j['materials'][pr['material']]; mname = mt['name']
            if mname.endswith('lenses'): continue           # glass, renders badly without its shader
            if mname not in mats:
                bt = mt.get('pbrMetallicRoughness', {}).get('baseColorTexture')
                src = None
                if bt is not None:
                    src = j['images'][j['textures'][bt['index']]['source']]['uri']
                # pick the real colour map, not AO/mask
                cands = [im['uri'] for im in j['images'] if im['uri'].startswith(mname) and '_color' in im['uri']]
                if cands: src = cands[0]
                png = name + '_' + mname
                if src and os.path.exists(os.path.join(texdir, src)):
                    im = Image.open(os.path.join(texdir, src)).convert('RGB')
                    if max(im.size) > 1024: im = im.resize((1024, 1024), Image.LANCZOS)
                    im.save(os.path.join(outdir, png + '.png'))
                else:
                    Image.new('RGB', (8, 8), (60, 64, 60)).save(os.path.join(outdir, png + '.png'))
                mats[mname] = (png, False)
            mn = mats[mname][0]
            for t in range(0, len(idx), 3):
                tri.append(mn + '\n')
                for vi in idx[t:t + 3]:
                    ws = [(int(J[vi][k]), Wt[vi][k]) for k in range(4) if Wt[vi][k] > 0.001]
                    tot = sum(w for _, w in ws) or 1.0
                    links = ' '.join('%d %.4f' % (b, w / tot) for b, w in ws)
                    p, n, u = P[vi], N[vi], UV[vi]
                    tri.append('%d %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f %d %s\n' % (
                        ws[0][0], p[0], p[1], p[2], n[0], n[1], n[2], u[0], 1 - u[1], len(ws), links))
    if WPN:
        wg = GLB(weapon[0]); wb = state.get('wpn_ref', np.eye(4)); wi = nb - 1
        for mesh in wg.j['meshes']:
            if not mesh['name'].endswith(weapon[1]): continue
            for pr in mesh['primitives']:
                a = pr['attributes']
                WF = WPN_FIX @ MESH_AX          # weapon model axes -> "wpn" bone frame
                P = wg.acc(a['POSITION']) @ WF.T / 0.0254
                P = (wb[:3, :3] @ P.T).T + wb[:3, 3]
                if state.get('hand_ref') is not None:   # put the pistol grip into the right hand
                    lo, hi = P.min(0), P.max(0)
                    grip = np.array([lo[0] + 0.33 * (hi[0] - lo[0]), (lo[1] + hi[1]) / 2, lo[2] + 0.25 * (hi[2] - lo[2])])
                    P = P + (state['hand_ref'][:3, 3] - grip)
                N = (wb[:3, :3] @ (wg.acc(a['NORMAL']) @ WF.T).T).T
                UV = wg.acc(a['TEXCOORD_0']); idx = wg.acc(pr['indices']).ravel()
                png = name + '_weapon'
                Image.open(weapon[2]).convert('RGB').resize((1024, 1024)).save(os.path.join(outdir, png + '.png'))
                mats['weapon'] = (png, False)
                for t in range(0, len(idx), 3):
                    tri.append(png + '\n')
                    for vi in idx[t:t + 3]:
                        p, n, u = P[vi], N[vi], UV[vi]
                        tri.append('%d %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f 1 %d 1.0\n' % (wi, p[0], p[1], p[2], n[0], n[1], n[2], u[0], 1 - u[1], wi))
    tri.append('end\n')
    open(os.path.join(outdir, name + '_ref.smd'), 'w').write('version 1\n' + nodes_txt + 'skeleton\n' + frame(0, bind[:-1] + [state.get('wpn_ref', np.eye(4))] if WPN else bind) + 'end\n' + ''.join(tri))

    for fn, body in anim_files:
        open(os.path.join(outdir, fn), 'w').write('version 1\n' + nodes_txt + body)
    write_vmdl(outdir, name, folder, {k: v for k, v in mats.items()}, anims)
    return mats, anims

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/ct/out/cs_ct'
    clips = [('idle', '/tmp/ct/clip_idle_rifle.glb', 'ACT_DOTA_IDLE', True, 1),
             ('run', '/tmp/ct/clip_run_n_rifle.glb', 'ACT_DOTA_RUN', True, 1),
             ('attack', '/tmp/ct/clip_shootna.glb', 'ACT_DOTA_ATTACK', False, 1),
             ('death', '/tmp/ct/clip_death.glb', 'ACT_DOTA_DIE', False, 1)]
    weapon = ('/tmp/ct/wpn/m4.glb', 'body_legacy', '/tmp/ct/wpn/m4a4_default_color_psd_3b0b391e.png')
    print(convert('/tmp/ct/agent.glb', '/tmp/ct/vmdl_data.txt', clips, out, 'cs_ct', 'models/cs/cs_ct', '/tmp/ct', weapon))
