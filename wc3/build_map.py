# Builds DotaWC3_Test.w3x from a melee map: our script, a custom Pudge unit and the imported Pudge model.
import sys, os, struct, re
sys.path.insert(0, '/tmp/w3')
from mpq import MPQ, write_mpq

SRC = '/mnt/user-data/uploads/Warcraft III/Maps/FrozenThrone/(4)TwistedMeadows.w3x'
OUT = '/tmp/w3/out/DotaWC3_741.w3x'
MODEL_DIR = '/tmp/w3/out/pudge_wc3'

GLOBALS = '''    // DotaWC3
    string udg_dwc_s = ""
    integer udg_dwc_p = 0
    integer udg_dwc_len = 0
    integer udg_dwc_n = 0
    integer array udg_dwc_id
    unit array udg_dwc_u
    real array udg_dwc_tx
    real array udg_dwc_ty
    real array udg_dwc_tf
    string array udg_dwc_anim
    string array udg_dwc_act
    string udg_dwc_hits = ""
    trigger udg_dwc_dmg = null
    unit udg_dwc_bm = null
    real udg_dwc_time = 0.0
    real udg_dwc_stun = 0.0
    boolean udg_dwc_paused = false
    real udg_dwc_reviveAt = 0.0
    lightning udg_dwc_chain = null
    real udg_dwc_chainEnd = 0.0
    integer udg_dwc_seq = -1
    integer udg_dwc_out = 0
    integer udg_dwc_lastK = 0
    real udg_dwc_lastSig = 0.0
    real udg_dwc_lastWrite = 0.0
    integer udg_dwc_tick = 0
    gamecache udg_dwc_gc = null
    integer udg_dwc_rseq = 0
'''

def w3u():
    def mod(fid, typ, val):
        b = fid.encode() + struct.pack('<i', typ)
        if typ == 0: b += struct.pack('<i', val)
        elif typ in (1, 2): b += struct.pack('<f', val)
        else: b += val.encode('utf-8') + b'\0'
        return b + b'\0\0\0\0'
    mods = [mod('unam', 3, 'Pudge (Dota 2)'), mod('umdl', 3, 'war3mapImported\\DotaPudge.mdx'),
            mod('uico', 3, 'ReplaceableTextures\\CommandButtons\\BTNAbomination.blp'),
            mod('uhpm', 0, 5000), mod('uaen', 0, 0), mod('umvs', 0, 400), mod('usca', 1, 1.0),
            mod('uabi', 3, ''), mod('ushu', 3, 'ShadowFlyer'), mod('ucol', 1, 32.0)]
    return struct.pack('<ii', 2, 0) + struct.pack('<i', 1) + b'hfoo' + b'h000' + struct.pack('<i', len(mods)) + b''.join(mods)

def main():
    raw = open(SRC, 'rb').read()
    a = MPQ(SRC)
    files = {n: a.read(n) for n in a.listfile() if a.read(n) is not None}
    j = files['war3map.j'].decode('utf-8', 'replace')
    j = j.replace('globals\n', 'globals\n' + GLOBALS, 1) if 'globals\n' in j else j.replace('globals\r\n', 'globals\r\n' + GLOBALS, 1)
    j = j.replace('endglobals', 'endglobals\nnative UnitAlive takes unit id returns boolean', 1)
    import gen_dota_map as G
    from blp import save_blp1
    _, ents = G.load()
    deco = ['function DWC_Deco takes integer id, real x, real y, real f returns nothing',
            '    local unit u = CreateUnit(Player(PLAYER_NEUTRAL_PASSIVE), id, x, y, f)',
            "    call UnitAddAbility(u, 'Avul')",
            '    set u = null', 'endfunction', '',
            'function DWC_Buildings takes nothing returns nothing'] + G.jass_buildings() + ['endfunction', '']
    code = '\n'.join(deco) + open('/tmp/w3/dotawc3.j', encoding='utf-8').read()
    code = code.replace('    set udg_dwc_bm = CreateUnit(', '    call DWC_Buildings()\n    set udg_dwc_bm = CreateUnit(', 1)
    j = re.sub(r'call SetCameraBounds\([^\n]*', G.jass_bounds().replace('\\', '\\\\'), j, 1)
    (gx, gy), (bx, by) = G.start_locs(ents)
    for k, (x, y) in enumerate([(bx, by), (gx, gy), (bx, by), (gx, gy)]):  # WC3 hero is the enemy of the Dota hero (Radiant), starts at Dire
        j = re.sub(r'call DefineStartLocation\( %d, [^)]*\)' % k, 'call DefineStartLocation( %d, %.1f, %.1f )' % (k, x, y), j)
    j = re.sub(r'call CreateAllUnits\(\s*\)', '', j)
    r = G.build()
    files['war3map.w3e'] = r['w3e']; files['war3map.wpm'] = r['wpm']; files['war3map.shd'] = r['shd']; files['war3map.doo'] = r['doo']
    files['war3map.w3i'] = G.patch_w3i(files['war3map.w3i'])
    save_blp1(r['minimap'], '/tmp/w3/gen/war3mapMap.blp', 256)
    files['war3mapMap.blp'] = open('/tmp/w3/gen/war3mapMap.blp', 'rb').read()
    for k in ('war3mapUnits.doo', 'war3map.w3r', 'war3map.w3c', 'war3map.mmp'): files.pop(k, None)
    i = j.index('function main takes nothing returns nothing')
    j = j[:i] + code + '\n' + j[i:]
    j = re.sub(r'call InitCustomTriggers\(\s*\)', 'call DWC_Init()', j)
    j = re.sub(r'call RunInitializationTriggers\(\s*\)', '', j)
    files['war3map.j'] = j.encode('utf-8')
    files.pop('war3map.w3u', None)
    wts = files['war3map.wts'].decode('utf-8', 'replace')
    wts = wts.replace('STRING 1\r\n{\r\n', 'STRING 1\r\n{\r\nDotaWC3 LAN MAP_TITLE', 1) if 'STRING 1\r\n{' in wts else wts.replace('STRING 1\n{\n', 'STRING 1\n{\nDotaWC3 LAN MAP_TITLE', 1)
    import re as _re
    wts = _re.sub(r'DotaWC3 LAN MAP_TITLE[^\r\n]*', 'DotaWC3 7.41', wts, 1)
    files['war3map.wts'] = wts.encode('utf-8')
    for f in os.listdir(MODEL_DIR):
        files['war3mapImported\\' + f] = open(os.path.join(MODEL_DIR, f), 'rb').read()
    # Dota Pudge replaces the Abomination model in this map only
    files['Units\\Undead\\Abomination\\Abomination.mdx'] = open(os.path.join(MODEL_DIR, 'DotaPudge.mdx'), 'rb').read()
    for k in [k for k in files if k in ('war3map.wtg', 'war3map.wct')]:
        del files[k]   # editor-only trigger data, would not match the new script
    write_mpq(OUT, files, header_prefix=raw[:512])
    print('written', OUT, os.path.getsize(OUT), sorted(files)[:30])

if __name__ == '__main__':
    main()
