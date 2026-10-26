# DotaCS: port real Dota particles to CS2 as SOURCE files that CS2's resourcecompiler builds itself.
# Compiled Dota particles do not load in CS2 (different shaders/materials), but VRF can decompile a particle
# (vpcf_c -> vpcf text) and a texture (vtex_c -> vtex + png), and CS2 compiles those fine.
# Renderers that need Dota-only materials or models (projected decals, model renderers...) are removed.
#
#   python3 dota_fx_port.py plan            -> writes /tmp/fxport/plan.json (roots + ability mapping)
#   python3 dota_fx_port.py extract         -> extracts what is needed, prints missing VPK chunks
#   python3 dota_fx_port.py build           -> decompiles + sanitizes into /tmp/fxport/src, writes lists
import sys, os, re, json, subprocess, glob
sys.path.insert(0, '/tmp/dx'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vpk import read_dir, get, rerl

DOTA = '/mnt/user-data/uploads/dota'; CS2DIR = '/mnt/user-data/uploads/csgo/pak01_dir.vpk'
G = '/tmp/dx/game'; W = '/tmp/fxport'; SRC = W + '/src'; VRF = '/tmp/vrf/Source2Viewer-CLI'
os.makedirs(W, exist_ok=True)

HEROES = ['pudge', 'axe', 'juggernaut', 'sniper', 'crystal_maiden', 'lina', 'phantom_assassin', 'drow_ranger', 'nevermore',
          'earthshaker', 'zuus', 'lion', 'invoker', 'slark', 'windrunner', 'sven', 'legion_commander', 'faceless_void', 'antimage',
          'queenofpain', 'mirana', 'riki', 'bloodseeker', 'viper', 'witch_doctor', 'kunkka', 'skeleton_king', 'dragon_knight',
          'tidehunter', 'ursa', 'bristleback', 'ogre_magi', 'huskar', 'necrolyte', 'shadow_shaman', 'troll_warlord']
# effects that are not spells but everyone sees in Dota
EXTRA = {
    'item_blink': [('particles/items_fx/blink_dagger_start.vpcf', 'caster'), ('particles/items_fx/blink_dagger_end.vpcf', 'point')],
    '@stun': [('particles/generic_gameplay/generic_stunned.vpcf', 'head')],
    '@levelup': [('particles/generic_hero_status/hero_levelup.vpcf', 'caster')],
    '@death': [('particles/generic_gameplay/generic_death.vpcf', 'caster')] if False else [],
}
DROP_RENDER = ('C_OP_RenderProjected', 'C_OP_RenderModels', 'C_OP_RenderStatusEffect', 'C_OP_RenderStatusEffectCitadel',
               'C_OP_RenderClothForce', 'C_OP_RenderScreenShake', 'C_OP_RenderScreenVelocityRotate', 'C_OP_RenderSound',
               'C_OP_RenderOmni2Light', 'C_OP_RenderPostProcessing', 'C_OP_RenderVRHapticEvent', 'C_OP_RenderStandardLight')
BAD_NAME = ('_ti', 'immortal', 'arcana', 'persona', 'golden', 'crimson', 'econ', 'alt', '_gold', 'kisses', 'prestige', 'crownfall', 'ward_')


def entries():
    E, D = read_dir(DOTA + '/pak01_dir.vpk')
    return E, D


def kv_values(path, key):
    out = []
    try:
        t = open(path, encoding='utf-8', errors='ignore').read()
        out = re.findall(r'"%s"\s+"([^"]+)"' % key, t)
    except Exception:
        pass
    return out


def plan():
    E, D = entries()
    allp = [k[:-2] for k in E if k.startswith('particles/') and k.endswith('.vpcf_c')]
    roots = set()
    # A. every ranged attack projectile of heroes and units
    for f in glob.glob(G + '/scripts/npc/heroes/*.txt') + [G + '/scripts/npc/npc_units.txt', G + '/scripts/npc/npc_heroes.txt']:
        for v in kv_values(f, 'ProjectileModel'):
            v = v.lower().replace('\\', '/')
            if v.endswith('.vpcf') and v + '_c' in E: roots.add(v)
    proj = sorted(roots)
    # B. hero spells: best root particle per ability by name
    mapping = {}
    for h in HEROES:
        f = G + '/scripts/npc/heroes/npc_dota_hero_%s.txt' % h
        abil = [a for a in kv_values(f, r'Ability\d+') if a.startswith(h.split('_')[0]) or a.startswith(h)]
        if not abil:
            abil = [a for a in kv_values(f, r'Ability\d+') if not a.startswith(('generic', 'special_bonus', 'attribute'))]
        # the hero's particle folder (hero_drow, hero_skeletonking, hero_witchdoctor...)
        hfold = sorted(set(re.match(r'particles/units/heroes/(hero_[^/]+)/', p).group(1) for p in allp if re.match(r'particles/units/heroes/hero_[^/]+/', p)))
        norm = lambda x: x.replace('hero_', '').replace('_', '')
        hn = h.replace('_', '')
        cand = [x for x in hfold if norm(x) == hn] or [x for x in hfold if hn.startswith(norm(x)) or norm(x).startswith(hn)]
        hf = cand[0] if cand else 'hero_' + h
        files = [p for p in allp if p.startswith('particles/units/heroes/%s/' % hf)]
        children = set()
        for p in files:
            try:
                arc = E[p + '_c'][0]
                if arc != 0x7fff and not os.path.exists(DOTA + '/pak01_%03d.vpk' % arc): continue
            except KeyError:
                continue
        for a in abil:
            short = a
            for pre in (h + '_', h.split('_')[0] + '_'):
                if short.startswith(pre): short = short[len(pre):]; break
            toks = [t for t in short.split('_') if len(t) >= 3]
            if not toks: continue
            best, bs = None, 0
            for p in files:
                n = os.path.basename(p)[:-5]
                if any(b in n for b in BAD_NAME): continue
                s = sum(1 for t in toks if t in n)
                if s == 0: continue
                # prefer the main effect: fewer extra words, "spell"/"cast"/no suffix
                extra = len(n.split('_')) - s
                score = s * 10 - extra + (3 if 'spell' in n or n.endswith(short) else 0) - (4 if re.search(r'_(b|c|d|e|f|g|glow|light|trail|sparks|child|debuff|buff|overhead|status|model|ground|core)$', n) else 0)
                if score > bs: best, bs = p, score
            if best and bs >= 8:
                mapping[a] = [(best, None)]
                roots.add(best)
    for k, v in EXTRA.items():
        if v: mapping[k] = [(p, m) for p, m in v]
        for p, _ in v: roots.add(p)
    json.dump({'roots': sorted(roots), 'proj': proj, 'map': mapping}, open(W + '/plan.json', 'w'), indent=1)
    print('roots', len(roots), 'projectiles', len(proj), 'abilities', len(mapping))


def extract():
    E, D = entries()
    pl = json.load(open(W + '/plan.json'))
    todo = [r + '_c' for r in pl['roots']]; seen = set(); missing = {}; got = []
    while todo:
        n = todo.pop()
        if n in seen: continue
        seen.add(n)
        if n not in E: continue
        out = os.path.join(G, n)
        if os.path.exists(out): buf = open(out, 'rb').read()
        else:
            arc = E[n][0]
            if arc != 0x7fff and not os.path.exists(DOTA + '/pak01_%03d.vpk' % arc):
                missing.setdefault(arc, []).append(n); continue
            buf = get(E, D, None, n, DOTA)
            os.makedirs(os.path.dirname(out), exist_ok=True); open(out, 'wb').write(buf)
        got.append(n)
        for r in rerl(buf):
            r = r.lower()
            if r.endswith(('.vpcf', '.vtex')): todo.append(r + '_c')
    json.dump(got, open(W + '/got.json', 'w'))
    print('got', len(got), 'missing', sum(len(v) for v in missing.values()), 'chunks:', ' '.join('%03d' % k for k in sorted(missing)))


def blocks_sanitize(text):
    """drop array entries ({ ... },) whose _class is a Dota-only renderer or that point at a vmat/vmdl"""
    lines = text.split('\n'); out = []; i = 0; dropped = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^(\t+)\{$', ln)
        if m and i + 1 < len(lines) and lines[i + 1].startswith(m.group(1) + '\t_class = '):
            ind = m.group(1); j = i + 1
            while j < len(lines) and not (lines[j] == ind + '},' or lines[j] == ind + '}'): j += 1
            blk = lines[i:j + 1]; cls = re.search(r'_class = "([^"]+)"', blk[1]).group(1)
            body = '\n'.join(blk)
            if cls in DROP_RENDER or '.vmat"' in body or '.vmdl"' in body:
                dropped += 1; i = j + 1; continue
        out.append(ln); i += 1
    return '\n'.join(out), dropped


def cp_mode(text):
    if re.search(r'C_INIT_VelocityFromCP[^}]*?m_nControlPoint = 1\b', text, re.S) or re.search(r'C_OP_RemapTransformToVelocity', text): return 'vel'
    if re.search(r'C_OP_AttractToControlPoint[^}]*?m_nControlPointNumber = 1\b', text, re.S): return 'track'
    if re.search(r'PF_TYPE_CONTROL_POINT_COMPONENT[^}]*?m_nControlPoint = 1\b', text, re.S): return 'radius'
    return 'pos'


def build():
    E, D = entries()
    C, _ = read_dir(CS2DIR)
    got = json.load(open(W + '/got.json')); pl = json.load(open(W + '/plan.json'))
    texts = {}; nd = 0; nt = 0; files = []
    for n in got:
        src = G + '/' + n; dst = SRC + '/' + n[:-2]
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if n.endswith('.vpcf_c'):
            if not os.path.exists(dst):
                subprocess.run([VRF, '-i', src, '-d', '-o', dst], capture_output=True, timeout=300)
            if not os.path.exists(dst): print('no vpcf', n); continue
            t = open(dst, encoding='utf-8', errors='ignore').read()
            t2, d = blocks_sanitize(t); nd += d
            open(dst, 'w').write(t2); texts[n[:-2]] = t2; files.append(n[:-2])
        elif n.endswith('.vtex_c'):
            if n in C: continue                     # CS2 has this texture already
            if not os.path.exists(dst):
                subprocess.run([VRF, '-i', src, '-d', '-o', dst], capture_output=True, timeout=300)
            if not os.path.exists(dst): print('no vtex', n); continue
            v = open(dst).read()
            # VRF writes the source image (png, or an .mks sheet with frames) next to dst; point the vtex at it relatively
            m = re.search(r'"m_fileName" "string" "([^"]*)"', v)
            if not m or 'materials/' not in m.group(1): print('bad vtex', n); continue
            rel = m.group(1)[m.group(1).index('materials/'):]
            if not os.path.exists(SRC + '/' + rel): print('no image', n, rel); continue
            v = v.replace(m.group(0), '"m_fileName" "string" "%s"' % rel)
            open(dst, 'w').write(v); nt += 1
    # modes: a root's mode is decided by itself and its children
    def tree(p, seen):
        if p in seen or p not in texts: return ''
        seen.add(p)
        return texts[p] + ''.join(tree(c, seen) for c in re.findall(r'resource:"(particles/[^"]+\.vpcf)"', texts[p]))
    lines = []
    for a, lst in pl['map'].items():
        for p, m in lst:
            if p not in texts: continue
            lines.append('%s|%s|%s' % (a, p, m or cp_mode(tree(p, set()))))
    roots = [r for r in pl['roots'] if r in texts]
    open(W + '/dota_ported_2.txt', 'w').write('\n'.join(roots) + '\n')
    open(W + '/dota_abilities.txt', 'w').write('\n'.join(lines) + '\n')
    json.dump(files, open(W + '/files.json', 'w'))
    print('particles', len(texts), 'textures', nt, 'renderers dropped', nd, 'roots', len(roots), 'ability lines', len(lines))


if __name__ == '__main__':
    {'plan': plan, 'extract': extract, 'build': build}[sys.argv[1]]()
