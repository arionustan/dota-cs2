# DotaCS: Dota 2 heroes (base model + default items) -> CS2 modeldoc models for the plugin.
# Needs the hero files extracted into /tmp/dx/game (tools/dota_extract.py) and Source2Viewer-CLI.
# Output: /tmp/hero/out/<unitname>/<unitname>.vmdl + DMX meshes/animations + color textures as PNG.
import os, re, sys, glob, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/tmp/hero'); sys.path.insert(0, '/tmp/dx')
import dmx_units as D
from matparams import params
from hero_plan import H, vmdls
from PIL import Image

G = '/tmp/dx/game'; OUT = '/tmp/hero/out'; VRF = '/tmp/vrf/Source2Viewer-CLI'
BAD = ('injured', 'haste', 'start', 'end', 'chase', 'versus', 'loadout', 'taunt', 'statue', 'portrait', 'alt', 'rare',
       'ti7', 'ti10', 'arcana', 'persona', 'debug', 'overkilled', 'blood_chaser', 'victory', 'spawn', 'teleport', 'flail', 'forcestaff')
WANT = {
    'idle': ['ACT_DOTA_IDLE'], 'run': ['ACT_DOTA_RUN'], 'attack': ['ACT_DOTA_ATTACK'], 'death': ['ACT_DOTA_DIE'],
    'cast': ['ACT_DOTA_CAST_ABILITY_1', 'ACT_DOTA_OVERRIDE_ABILITY_1', 'ACT_DOTA_CAST_ABILITY_2', 'ACT_DOTA_CAST_ABILITY_3', 'ACT_DOTA_RAZE_1'],
    'ult': ['ACT_DOTA_CAST_ABILITY_4', 'ACT_DOTA_OVERRIDE_ABILITY_4', 'ACT_DOTA_CAST_ABILITY_6', 'ACT_DOTA_CAST_ABILITY_1'],
    'stun': ['ACT_DOTA_DISABLED'],
}

def pick(anims, key):
    for act in WANT[key]:
        c = [a for a in anims if a[2] == act and not a[0].startswith('@') and not any(b in a[0].lower() for b in BAD)]
        if not c: c = [a for a in anims if a[2] == act and not a[0].startswith('@')]
        if c:
            c.sort(key=lambda a: (len(a[0]), a[0])); return c[0]
    return None

def tex_png(vtex, od):
    src = G + '/' + vtex.lower() + '_c'
    if not os.path.exists(src): return None
    base = os.path.basename(vtex)[:-5]
    dst = od + '/' + base + '.png'
    if not os.path.exists(dst):
        subprocess.run([VRF, '-i', src, '-d', '-o', dst], capture_output=True, timeout=300)
    if not os.path.exists(dst): return None
    im = Image.open(dst)
    if max(im.size) > 2048:   # keep the pack small
        im.thumbnail((2048, 2048)); im.save(dst)
    return dst

def make_vmat(dota_vmat, od, rel):
    src = G + '/' + dota_vmat.lower() + '_c'
    if not os.path.exists(src): return None
    p = params(src)
    col = p.get('g_tColor')
    if not isinstance(col, str): return None
    png = tex_png(col, od)
    if not png: return None
    name = os.path.splitext(os.path.basename(dota_vmat))[0]
    lines = ['// DotaCS hero material, from %s' % dota_vmat, 'Layer0', '{', '\tshader "csgo_complex.vfx"',
             '\tTextureColor "%s%s"' % (rel, os.path.basename(png))]
    if p.get('F_ALPHA_TEST') or p.get('F_TRANSLUCENT'):
        im = Image.open(png)
        if im.mode == 'RGBA':
            ap = png[:-4] + '_alpha.png'
            a = im.getchannel('A'); Image.merge('RGB', (a, a, a)).save(ap)
            lines += ['\tF_ALPHA_TEST 1', '\tTextureTranslucency "%s%s"' % (rel, os.path.basename(ap)), '\tg_flAlphaTestReference "0.5"']
    lines.append('}')
    open(od + '/' + name + '.vmat', 'w').write('\n'.join(lines) + '\n')
    return name + '.vmat'

def build(unit):
    od = OUT + '/' + unit; rel = 'models/dota_heroes/%s/' % unit
    if os.path.exists(od): shutil.rmtree(od)
    os.makedirs(od)
    meshes, anims = [], None
    for i, v in enumerate(vmdls(unit)):
        if not os.path.exists(G + '/' + v + '_c'): print('  no', v); continue
        ms, an = D.parse(D.decompile(v))
        meshes += [m for m in ms if not re.search(r'_lod[1-9]', m)]
        if i == 0: anims = an
    remaps, seen, first, meshtxt = '', set(), None, ''
    for m in meshes:
        dst = os.path.basename(m); shutil.copy(G + '/' + m, od + '/' + dst)
        meshtxt += ('{\n_class = "RenderMeshFile"\nfilename = "%s%s"\nimport_translation = [ 0.0, 0.0, 0.0 ]\nimport_rotation = [ 0.0, 0.0, 0.0 ]\n'
                    'import_scale = 1.0\nalign_origin_x_type = "None"\nalign_origin_y_type = "None"\nalign_origin_z_type = "None"\n'
                    'parent_bone = ""\nimport_filter = \n{\nexclude_by_default = false\nexception_list = [  ]\n}\n},\n') % (rel, dst)
        for mp in D.mtl_paths(G + '/' + m):
            mp = mp.decode()
            if mp in seen: continue
            seen.add(mp)
            vm = make_vmat(mp, od, rel)
            if vm:
                remaps += '{\nfrom = "%s"\nto = "%s%s"\n},\n' % (mp, rel, vm); first = first or rel + vm
    at, got = '', {}
    for k in ['idle', 'run', 'attack', 'death', 'cast', 'ult', 'stun']:
        a = pick(anims or [], k) or (pick(anims or [], 'idle') if k != 'idle' else None)
        if not a: continue
        dst = os.path.basename(a[1]); shutil.copy(G + '/' + a[1], od + '/' + dst)
        at += D.animblock(k, rel + dst, k in ('idle', 'run', 'stun')); got[k] = a[0]
    tpl = open(D.__file__).read()
    body = tpl[tpl.index("    v='''") + 9: tpl.index("'''%(rm, first")]
    open(od + '/' + unit + '.vmdl', 'w').write(body % (remaps, first or 'materials/default/default.vmat', meshtxt, at))
    print('HERO', unit, len(meshes), 'meshes', len(seen), 'mats', remaps.count('from'), 'remapped', got)

if __name__ == '__main__':
    for u in (sys.argv[1:] or list(H)):
        try: build(u)
        except Exception as e: print('FAIL', u, repr(e))
