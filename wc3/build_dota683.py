# Builds DotaWC3_683.w3x: the real DotA 6.83d map (terrain, trees, shops, towers) with the DotaWC3 bridge script.
# The DotA archive is copied byte for byte (protected map, most file names unknown); only the script,
# w3i and our Pudge model are replaced or added. Dota 2 <-> DotA coordinates are converted by the LAN bridge.
import sys, os, re, json, struct
import numpy as np
sys.path.insert(0, '/tmp/w3'); sys.path.insert(0, '/tmp/w3/gen')
from mpq import MPQ, patch_mpq
import build_map as BM

SRC = '/tmp/w3/dota683.w3x'
TM = '/mnt/user-data/uploads/Warcraft III/Maps/FrozenThrone/(4)TwistedMeadows.w3x'
OUT = '/tmp/w3/out/DotaWC3_683.w3x'
MODEL_DIR = '/tmp/w3/out/pudge_wc3'

# landmarks: Dota 2 7.41 -> DotA 6.83d (fountains, ancients, tier 1 towers)
D2 = [(-7456, -6938), (7408, 6848), (-5920, -5352), (5528, 5000),
      (-6336, 1856), (4860, -6379), (-1544, -1408), (-5275, 6036), (6269, -2240), (524, 652)]
W3 = [(-7296, -7200), (6784, 6368), (-5632, -6144), (5184, 4864),
      (-6112, 1568), (4960, -6752), (-1504, -1824), (-4704, 5920), (6240, -2080), (1056, -96)]
SKIP = {'e00D', 'e00B', 'e00A', 'e008', 'e001', 'n01F', 'H00Y'}   # invisible dummies

def fit_affine():
    A = np.array([[x, y, 1] for x, y in D2], float)
    M, *_ = np.linalg.lstsq(A, np.array(W3, float), rcond=None)   # [3,2]
    return M.T                                                     # wc = M @ [x, y, 1]

def to_wc3(M, x, y):
    v = M @ np.array([x, y, 1.0]); return float(v[0]), float(v[1])

def w3i_from(tm_w3i, dota_w3i):
    def body_off(b):
        p = 12
        for _ in range(4): p = b.index(b'\0', p) + 1
        return p
    pt, pd = body_off(tm_w3i), body_off(dota_w3i)
    dims = dota_w3i[pd:pd + 56]                          # camera bounds, margins, width, height
    out = bytearray(tm_w3i[:pt] + dims + tm_w3i[pt + 56:])
    out[pt + 56 + 4] = dota_w3i[pd + 56 + 4]             # tileset letter
    return bytes(out)

def main():
    d = MPQ(SRC); tm = MPQ(TM)
    M = fit_affine()
    units = json.load(open('/tmp/w3/gen/dota683_units.json'))
    ents = json.load(open('/tmp/dx/ents/ents.json'))
    deco = ['function DWC_Deco takes integer id, real x, real y, real f returns nothing',
            '    local unit u = CreateUnit(Player(PLAYER_NEUTRAL_PASSIVE), id, x, y, f)',
            "    call UnitAddAbility(u, 'Avul')",
            '    set u = null', 'endfunction', '',
            'function DWC_Buildings takes nothing returns nothing']
    for pl, uid, x, y, f, name in units:
        if uid in SKIP: continue
        deco.append("    call DWC_Deco('%s', %.1f, %.1f, %.1f)" % (uid, x, y, f))
    for e in ents:   # 7.41 additions: twin gates and outposts
        c = e.get('classname')
        if c in ('npc_dota_unit_twin_gate', 'npc_dota_watch_tower'):
            x, y = to_wc3(M, *e['origin'][:2])
            deco.append("    call DWC_Deco('%s', %.1f, %.1f, 270.0)" % ('nwgt' if 'gate' in c else 'hwtw', x, y))
    deco += ['endfunction', '']

    j = open('/tmp/w3/TwistedMeadows.j', encoding='utf-8', errors='replace').read()
    j = j.replace('globals\n', 'globals\n' + BM.GLOBALS, 1) if 'globals\n' in j else j.replace('globals\r\n', 'globals\r\n' + BM.GLOBALS, 1)
    j = j.replace('endglobals', 'endglobals\nnative UnitAlive takes unit id returns boolean', 1)
    code = '\n'.join(deco) + open('/tmp/w3/dotawc3.j', encoding='utf-8').read()
    code = code.replace('    set udg_dwc_bm = CreateUnit(', '    call DWC_Buildings()\n    set udg_dwc_bm = CreateUnit(', 1)
    i = j.index('function main takes nothing returns nothing')
    j = j[:i] + code + '\n' + j[i:]
    j = re.sub(r'call InitCustomTriggers\(\s*\)', 'call DWC_Init()', j)
    j = re.sub(r'call RunInitializationTriggers\(\s*\)', '', j)
    j = re.sub(r'call CreateAllUnits\(\s*\)', '', j)
    cam = re.search(r'call SetCameraBounds\([^\n\r]*', open('/tmp/w3/dota683n.j', encoding='latin1').read()).group(0)
    j = re.sub(r'call SetCameraBounds\([^\n]*', cam.replace('\\', '\\\\'), j, 1)
    j = j.replace('DNCLordaeron\\\\DNCLordaeronTerrain\\\\DNCLordaeronTerrain', 'DNCFelwood\\\\DNCFelwoodTerrain\\\\DNCFelwoodTerrain')
    j = j.replace('DNCLordaeron\\\\DNCLordaeronUnit\\\\DNCLordaeronUnit', 'DNCFelwood\\\\DNCFelwoodUnit\\\\DNCFelwoodUnit')
    j = j.replace('"LordaeronSummerDay"', '"FelwoodDay"').replace('"LordaeronSummerNight"', '"FelwoodNight"')
    j = j.replace('call SetMapName( "TRIGSTR_001" )', 'call SetMapName( "DotaWC3 6.83" )')
    j = j.replace('call SetMapDescription( "TRIGSTR_003" )', 'call SetMapDescription( "" )')
    # WC3 hero fights the Dota (Radiant) hero, so it starts at the Scourge fountain
    starts = [(6550.0, 6150.0), (-7000.0, -6900.0), (6550.0, 6150.0), (-7000.0, -6900.0)]
    for k, (x, y) in enumerate(starts):
        j = re.sub(r'call DefineStartLocation\( %d, [^)]*\)' % k, 'call DefineStartLocation( %d, %.1f, %.1f )' % (k, x, y), j)

    rep = {'scripts\\war3map.j': j.encode('utf-8'),
           'war3map.w3i': w3i_from(tm.read('war3map.w3i'), d.read('war3map.w3i'))}
    for f in os.listdir(MODEL_DIR):
        rep['war3mapImported\\' + f] = open(os.path.join(MODEL_DIR, f), 'rb').read()
    rep['units\\undead\\Abomination\\Abomination.mdx'] = open(os.path.join(MODEL_DIR, 'DotaPudge.mdx'), 'rb').read()
    patch_mpq(SRC, OUT, rep)
    x = MPQ(OUT)
    assert x.read('scripts\\war3map.j') == rep['scripts\\war3map.j'] and x.read('war3map.w3e') == d.read('war3map.w3e')
    xf = {'a': M[0].tolist(), 'b': M[1].tolist()}
    json.dump(xf, open('/tmp/w3/out/xform_683.json', 'w'))
    print('written', OUT, os.path.getsize(OUT), 'xform', xf, 'deco', len(deco))

if __name__ == '__main__':
    main()
