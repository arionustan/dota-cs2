# Generates Warcraft III terrain files that copy the Dota 2 7.41 map 1:1 (same world coordinates).
# Output: dict of map files (w3e, wpm, shd, doo, w3i, minimap) plus a JASS snippet with buildings.
import struct, json, math, random
import numpy as np

O, CELLS = -10240.0, 160          # same grid as a 160x160 melee map, origin -10240
MARGIN = 10                        # unplayable border cells on each side
PLAY_LO = O + MARGIN * 128         # -8960
PLAY_HI = O + (CELLS - MARGIN) * 128
TILES = [b'Lgrs', b'Lgrd', b'Ldrg', b'Ldro', b'Ldrt', b'Lrok', b'Cgrs', b'Cdrt', b'Cdrd', b'Crck']
T = {t.decode(): i for i, t in enumerate(TILES)}
Z0 = 128.0                         # Dota lowground (128) becomes WC3 height 0
WATER_Z = 80.0                     # Dota river water surface
rng = random.Random(741)

def load():
    H = np.load('/tmp/w3/gen/hf32.npy')                 # H[ix, iy], 32-unit grid, 641x641
    ents = json.load(open('/tmp/dx/ents/ents.json'))
    return H, ents

def lanes(ents):
    pc = {x.get('targetname'): x for x in ents if x.get('classname') == 'path_corner'}
    segs = []
    for x in pc.values():
        t = pc.get(x.get('target'))
        if t: segs.append((x['origin'][:2], t['origin'][:2]))
    return segs

def dist_to_segs(px, py, segs):
    d = np.full(px.shape, 1e9)
    for (ax, ay), (bx, by) in segs:
        vx, vy = bx - ax, by - ay; L = vx * vx + vy * vy or 1.0
        t = np.clip(((px - ax) * vx + (py - ay) * vy) / L, 0, 1)
        d = np.minimum(d, np.hypot(px - (ax + t * vx), py - (ay + t * vy)))
    return d

def build():
    H, ents = load()
    trees = [x for x in ents if x.get('classname') == 'ent_dota_tree']
    N = CELLS + 1
    gx = O + 128.0 * np.arange(N)
    PX, PY = np.meshgrid(gx, gx, indexing='ij')           # [i, j] = x index, y index
    Hc = H[::4, ::4]                                       # heights at tilepoints
    # local roughness: max height difference in the surrounding 32-unit samples
    pad = np.pad(H, 4, mode='edge')
    rough = np.zeros((N, N))
    for di in range(-4, 5, 2):
        for dj in range(-4, 5, 2):
            rough = np.maximum(rough, np.abs(pad[4 + di::4, 4 + dj::4][:N, :N] - Hc))
    dire = (PX + PY + 300 * np.sin(PX / 900.0) * np.cos(PY / 1100.0)) > 0
    segs = lanes(ents)
    dl = dist_to_segs(PX, PY, segs)
    tp = np.array([t['origin'][:2] for t in trees])
    dens = np.zeros((N, N))
    ti = np.clip(np.round((tp[:, 0] - O) / 128).astype(int), 0, N - 1)
    tj = np.clip(np.round((tp[:, 1] - O) / 128).astype(int), 0, N - 1)
    np.add.at(dens, (ti, tj), 1)
    from scipy import ndimage
    dens = ndimage.uniform_filter(dens, 5)
    water = Hc < WATER_Z - 8
    tex = np.where(dire, T['Cgrs'], T['Lgrs'])
    tex = np.where(dens > 0.12, np.where(dire, T['Cgrs'], T['Lgrd']), tex)
    noise = np.random.RandomState(7).rand(N, N)
    tex = np.where((dens < 0.04) & (noise < 0.25), np.where(dire, T['Cdrt'], T['Ldrg']), tex)
    tex = np.where(dl < 260, np.where(dire, T['Cdrd'], T['Ldro']), tex)
    tex = np.where(dl < 150, np.where(dire, T['Cdrt'], T['Ldrt']), tex)
    tex = np.where(rough > 70, np.where(dire, T['Crck'], T['Lrok']), tex)
    tex = np.where(water, T['Ldrt'], tex)

    # ---- war3map.w3e
    out = bytearray(b'W3E!') + struct.pack('<iBi', 11, ord('L'), 1)
    out += struct.pack('<i', len(TILES)) + b''.join(TILES)
    out += struct.pack('<i', 2) + b'CLgrCLdi'
    out += struct.pack('<iiff', N, N, O, O)
    wz = np.clip(Hc - Z0, -2000, 2000)
    # WC3 cliff layers: Dota height levels (128 apart, same as WC3) quantized; ramps stay smooth because
    # the per-point height offset cancels the layer step there, real Dota cliffs show WC3 cliff models
    lay = np.clip(np.round(wz / 128.0) + 2, 0, 15)
    lay = ndimage.median_filter(lay, size=3)  # no single-point cliff blips
    for _ in range(40):                       # cliff models only exist for steps of up to 2 layers
        ch = False
        for ax in (0, 1):
            for sh in (1, -1):
                nb = np.roll(lay, sh, axis=ax)
                bad = lay > nb + 2
                if bad.any(): lay[bad] = nb[bad] + 2; ch = True
        if not ch: break
    hv = np.clip(np.round(0x2000 + (wz - (lay - 2) * 128) * 4), 0, 0x3FFF).astype(int)
    ctex = np.where(dire, 1, 0)
    wv = int(round(0x2000 + (WATER_Z - Z0 + 89.6) * 4))
    var_choices = [0, 0, 4, 8, 12, 16, 17]
    for j in range(N):             # rows bottom to top, x fastest
        for i in range(N):
            w = wv
            if i < MARGIN or i > CELLS - MARGIN or j < MARGIN or j > CELLS - MARGIN: w |= 0x4000
            flags = 0x40 if water[i, j] else 0
            out += struct.pack('<hHBBB', int(hv[i, j]), w, flags | int(tex[i, j]),
                               rng.choice(var_choices), (int(ctex[i, j]) << 4) | int(lay[i, j]))
    w3e = bytes(out)

    # ---- war3map.wpm (32-unit pathing cells)
    P = CELLS * 4
    c00, c10, c01, c11 = H[:-1, :-1], H[1:, :-1], H[:-1, 1:], H[1:, 1:]
    step = np.maximum.reduce([np.abs(c00 - c10), np.abs(c00 - c01), np.abs(c11 - c10), np.abs(c11 - c01), np.abs(c00 - c11)])
    cliff = step > 40
    cliff = ndimage.binary_dilation(cliff, iterations=1)
    cz = (c00 + c10 + c01 + c11) / 4
    cx = O + 32 * (np.arange(P) + 0.5)
    CX, CY = np.meshgrid(cx, cx, indexing='ij')
    outside = (np.abs(CX) > 8448) | (np.abs(CY) > 8448)
    wp = np.full((P, P), 0x40, np.uint8)
    wp[cz < WATER_Z - 8] = 0x08                     # shallow water, walkable
    wp[cliff] = 0xCA
    wp[outside] = 0xCE
    border = (CX < PLAY_LO) | (CX > PLAY_HI) | (CY < PLAY_LO) | (CY > PLAY_HI)
    wp[border] = 0xCE
    wpm = b'MP3W' + struct.pack('<iii', 0, P, P) + wp.T.tobytes()   # rows by y, x fastest
    shd = bytes(P * P)

    # ---- war3map.doo (trees)
    doo = bytearray(b'W3do') + struct.pack('<iii', 8, 11, len(trees))
    for k, t in enumerate(trees):
        x, y = t['origin'][:2]
        i = int(np.clip(round((x - O) / 32), 0, 640)); j = int(np.clip(round((y - O) / 32), 0, 640))
        side_dire = (x + y + 300 * math.sin(x / 900.0) * math.cos(y / 1100.0)) > 0
        tid, nv = (b'CTtr', 5) if side_dire else (b'LTlt', 10)
        s = float(t.get('scales', [1])[0]) * rng.uniform(0.95, 1.15)
        s = max(0.8, min(1.3, s))
        doo += tid + struct.pack('<ifffffffBBiii', rng.randrange(nv), x, y, float(H[i, j] - Z0),
                                 rng.uniform(0, 6.283), s, s, s, 2, 100, -1, 0, k)
    doo += struct.pack('<ii', 0, 0)

    # ---- minimap (256x256)
    from PIL import Image
    col = {T['Lgrs']: (70, 120, 40), T['Lgrd']: (40, 90, 30), T['Ldrg']: (100, 110, 50), T['Ldro']: (130, 105, 70),
           T['Ldrt']: (140, 115, 80), T['Lrok']: (110, 105, 100), T['Cgrs']: (70, 60, 80), T['Cdrt']: (85, 70, 60),
           T['Cdrd']: (100, 80, 65), T['Crck']: (80, 75, 85)}
    img = np.zeros((N, N, 3), np.uint8)
    for k, c in col.items(): img[tex == k] = c
    img[water] = (40, 80, 140)
    shade = np.clip(1 + (Hc - 256) / 1200, 0.6, 1.3)[..., None]
    img = np.clip(img * shade, 0, 255).astype(np.uint8)
    for x, y in tp:
        i = int((x - O) / 128); j = int((y - O) / 128)
        if 0 <= i < N and 0 <= j < N: img[i, j] = (img[i, j] * 0.5).astype(np.uint8)
    mm = Image.fromarray(np.transpose(img, (1, 0, 2))[::-1]).resize((256, 256), Image.LANCZOS)
    return {'w3e': w3e, 'wpm': wpm, 'shd': shd, 'doo': bytes(doo), 'minimap': mm}

def patch_w3i(w3i):
    p = 12
    for _ in range(4): p = w3i.index(b'\0', p) + 1
    L, B, R, Tp = PLAY_LO, PLAY_LO, PLAY_HI, PLAY_HI
    cam = (L + 512, B + 256, R - 512, Tp - 256, L + 512, Tp - 256, R - 512, B + 256)
    w = CELLS - 2 * MARGIN
    return w3i[:p] + struct.pack('<8f4i2i', *cam, MARGIN, MARGIN, MARGIN, MARGIN, w, w) + w3i[p + 32 + 16 + 8:]

def jass_bounds():
    L = PLAY_LO; R = PLAY_HI
    return ('call SetCameraBounds( %.1f + GetCameraMargin(CAMERA_MARGIN_LEFT), %.1f + GetCameraMargin(CAMERA_MARGIN_BOTTOM), '
            '%.1f - GetCameraMargin(CAMERA_MARGIN_RIGHT), %.1f - GetCameraMargin(CAMERA_MARGIN_TOP), '
            '%.1f + GetCameraMargin(CAMERA_MARGIN_LEFT), %.1f - GetCameraMargin(CAMERA_MARGIN_TOP), '
            '%.1f - GetCameraMargin(CAMERA_MARGIN_RIGHT), %.1f + GetCameraMargin(CAMERA_MARGIN_BOTTOM) )') % (L, L, R, R, L, R, R, L)

def jass_buildings():
    b = json.load(open('/tmp/dx/buildings.json'))
    ents = json.load(open('/tmp/dx/ents/ents.json'))
    lines = []
    def add(uid, x, y, f):
        lines.append("    call DWC_Deco('%s', %.1f, %.1f, %.1f)" % (uid, x, y, f))
    for cls, name, _, x, y in b:
        good = 'goodguys' in name
        f = 45.0 if good else 225.0
        if cls == 'npc_dota_tower': add('hgtw' if good else 'uzg1', x, y, f)
        elif cls == 'npc_dota_barracks': add(('hbar' if good else 'usep') if 'melee' in name else ('hars' if good else 'utod'), x, y, f)
        elif cls == 'npc_dota_fort': add('etoe' if good else 'unp2', x, y, f)
        elif cls == 'npc_dota_building': add('hhou' if good else 'uzig', x, y, f)
        elif cls == 'npc_dota_watch_tower': add('hwtw', x, y, 270.0)
        elif cls == 'ent_dota_fountain': add('nfoh' if x < 0 else 'ndfl', x, y, f)
    for e in ents:
        c = e.get('classname'); x, y = e['origin'][:2]
        if c == 'ent_dota_shop': add('ngme', x, y, 270.0)
        elif c == 'npc_dota_unit_twin_gate': add('nwgt', x, y, 270.0)
    return lines

def start_locs(ents):
    g = [e['origin'][:2] for e in ents if e.get('classname') == 'info_player_start_goodguys']
    b = [e['origin'][:2] for e in ents if e.get('classname') == 'info_player_start_badguys']
    return g[0], b[0]

if __name__ == '__main__':
    r = build()
    r['minimap'].save('/tmp/w3/gen/minimap.png')
    print({k: len(v) for k, v in r.items() if isinstance(v, bytes)})
    print(len(jass_buildings()), jass_bounds()[:80])
