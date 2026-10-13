# MDX (Warcraft III, version 800) reader and writer.
import struct

def cstr(b):
    return b.split(b'\0', 1)[0].decode('latin-1')

def pad(s, n):
    b = s.encode('latin-1')[:n - 1]
    return b + b'\0' * (n - len(b))

TRACK_SIZE = {'KGTR': 3, 'KGRT': 4, 'KGSC': 3, 'KGAO': 1, 'KGAC': 3, 'KMTA': 1, 'KMTF': 1, 'KATV': 1,
              'KP2V': 1, 'KP2E': 1, 'KP2W': 1, 'KP2N': 1, 'KP2S': 1, 'KP2L': 1, 'KP2R': 1, 'KP2G': 1,
              'KRVS': 1, 'KRHA': 1, 'KRHB': 1, 'KRAL': 1, 'KRCO': 3, 'KRTX': 1, 'KLAS': 1, 'KLAE': 1,
              'KLAC': 3, 'KLIC': 3, 'KLAI': 1, 'KLBI': 1, 'KLBC': 3, 'KLAV': 1, 'KTAT': 3, 'KTAR': 4,
              'KTAS': 3, 'KCTR': 3, 'KTTR': 3, 'KCRL': 1, 'KPEV': 1, 'KPPA': 1, 'KPPC': 3, 'KPPE': 1,
              'KPPL': 1, 'KPPS': 1, 'KPPV': 1, 'KPPR': 1, 'KPPT': 1, 'KPPX': 1, 'KMTE': 3, 'KMTI': 1}

class R:
    def __init__(self, b, p=0): self.b = b; self.p = p
    def u32(self): v = struct.unpack_from('<I', self.b, self.p)[0]; self.p += 4; return v
    def i32(self): v = struct.unpack_from('<i', self.b, self.p)[0]; self.p += 4; return v
    def f(self, n=1):
        v = struct.unpack_from('<%df' % n, self.b, self.p); self.p += 4 * n
        return v if n > 1 else v[0]
    def raw(self, n): v = self.b[self.p:self.p + n]; self.p += n; return v
    def tag(self): return self.raw(4).decode('latin-1')

def read_track(r, tag):
    n = r.u32(); interp = r.u32(); gs = r.i32(); sz = TRACK_SIZE[tag]
    keys = []
    for _ in range(n):
        fr = r.i32(); v = r.f(sz)
        v = v if isinstance(v, tuple) else (v,)
        it = ot = None
        if interp > 1:
            it = r.f(sz); ot = r.f(sz)
        keys.append((fr, v, it, ot))
    return {'interp': interp, 'gs': gs, 'keys': keys}

def read_node(r):
    start = r.p; size = r.u32()
    n = {'name': cstr(r.raw(80)), 'id': r.u32(), 'parent': r.i32(), 'flags': r.u32(), 'tracks': {}}
    while r.p < start + size:
        t = r.tag(); n['tracks'][t] = read_track(r, t)
    return n

def load(data):
    assert data[:4] == b'MDLX'
    m = {'seqs': [], 'textures': [], 'materials': [], 'geosets': [], 'geoanims': [], 'nodes': {}, 'pivots': [], 'glbs': []}
    p = 4
    while p < len(data):
        tag = data[p:p + 4].decode('latin-1'); size = struct.unpack_from('<I', data, p + 4)[0]
        body = data[p + 8:p + 8 + size]; p += 8 + size
        r = R(body)
        if tag == 'VERS': m['version'] = r.u32()
        elif tag == 'MODL': m['name'] = cstr(r.raw(80))
        elif tag == 'SEQS':
            for _ in range(size // 132):
                name = cstr(r.raw(80)); s, e = r.u32(), r.u32(); spd = r.f(); fl = r.u32(); rar = r.f(); sync = r.u32(); ext = r.f(7)
                m['seqs'].append({'name': name, 'start': s, 'end': e, 'speed': spd, 'flags': fl, 'rarity': rar})
        elif tag == 'GLBS': m['glbs'] = list(struct.unpack('<%dI' % (size // 4), body))
        elif tag == 'TEXS':
            for _ in range(size // 268):
                rid = r.u32(); fn = cstr(r.raw(260)); fl = r.u32()
                m['textures'].append({'replaceable': rid, 'file': fn, 'flags': fl})
        elif tag == 'MTLS':
            while r.p < size:
                st = r.p; isz = r.u32(); prio = r.i32(); fl = r.u32(); assert r.tag() == 'LAYS'; nl = r.u32()
                layers = []
                for _ in range(nl):
                    ls = r.p; lsz = r.u32()
                    L = {'filter': r.u32(), 'shading': r.u32(), 'texture': r.u32(), 'tvertanim': r.i32(), 'coord': r.u32(), 'alpha': r.f(), 'tracks': {}}
                    while r.p < ls + lsz:
                        t = r.tag(); L['tracks'][t] = read_track(r, t)
                    layers.append(L)
                r.p = st + isz
                m['materials'].append({'layers': layers, 'flags': fl})
        elif tag == 'GEOS':
            while r.p < size:
                st = r.p; isz = r.u32(); g = {}
                assert r.tag() == 'VRTX'; n = r.u32(); g['verts'] = [r.f(3) for _ in range(n)]
                assert r.tag() == 'NRMS'; n = r.u32(); g['normals'] = [r.f(3) for _ in range(n)]
                assert r.tag() == 'PTYP'; n = r.u32(); g['ptyp'] = [r.u32() for _ in range(n)]
                assert r.tag() == 'PCNT'; n = r.u32(); g['pcnt'] = [r.u32() for _ in range(n)]
                assert r.tag() == 'PVTX'; n = r.u32(); g['faces'] = list(struct.unpack_from('<%dH' % n, body, r.p)); r.p += 2 * n
                assert r.tag() == 'GNDX'; n = r.u32(); g['gndx'] = list(body[r.p:r.p + n]); r.p += n
                assert r.tag() == 'MTGC'; n = r.u32(); g['mtgc'] = [r.u32() for _ in range(n)]
                assert r.tag() == 'MATS'; n = r.u32(); g['mats'] = [r.u32() for _ in range(n)]
                g['material'] = r.u32(); g['selgroup'] = r.u32(); g['selflags'] = r.u32()
                r.f(7); ne = r.u32(); r.raw(28 * ne)
                assert r.tag() == 'UVAS'; nuv = r.u32(); g['uvs'] = []
                for _ in range(nuv):
                    assert r.tag() == 'UVBS'; n = r.u32(); g['uvs'].append([r.f(2) for _ in range(n)])
                r.p = st + isz
                m['geosets'].append(g)
        elif tag == 'GEOA':
            while r.p < size:
                st = r.p; isz = r.u32(); a = {'alpha': r.f(), 'flags': r.u32(), 'color': r.f(3), 'geoset': r.u32(), 'tracks': {}}
                while r.p < st + isz:
                    t = r.tag(); a['tracks'][t] = read_track(r, t)
                m['geoanims'].append(a)
        elif tag in ('BONE', 'HELP'):
            while r.p < size:
                n = read_node(r); n['type'] = tag
                if tag == 'BONE': n['geoset'] = r.i32(); n['geoanim'] = r.i32()
                m['nodes'][n['id']] = n
        elif tag == 'ATCH':
            while r.p < size:
                st = r.p; isz = r.u32(); n = read_node(r); n['type'] = 'ATCH'
                n['path'] = cstr(r.raw(260)); n['attid'] = r.u32()
                while r.p < st + isz:
                    t = r.tag(); read_track(r, t)
                r.p = st + isz
                m['nodes'][n['id']] = n
        elif tag in ('PREM', 'PRE2', 'RIBB', 'LITE'):
            while r.p < size:
                st = r.p; isz = r.u32(); n = read_node(r); n['type'] = tag; m['nodes'][n['id']] = n
                r.p = st + isz
        elif tag == 'EVTS':
            while r.p < size:
                n = read_node(r); n['type'] = tag; m['nodes'][n['id']] = n
                if body[r.p:r.p + 4] == b'KEVT':
                    r.raw(4); k = r.u32(); r.i32(); r.raw(4 * k)
        elif tag == 'CLID':
            while r.p < size:
                n = read_node(r); n['type'] = tag; m['nodes'][n['id']] = n
                shape = r.u32(); r.f(3 if shape == 2 else 6)
                if shape in (2, 3): r.f(1)
        elif tag == 'PIVT':
            m['pivots'] = [struct.unpack_from('<3f', body, i * 12) for i in range(size // 12)]
    return m


# ---------------------------------------------------------------- writer
def w_track(tag, keys, interp=1, gs=-1):
    sz = TRACK_SIZE[tag]
    out = tag.encode() + struct.pack('<IIi', len(keys), interp, gs)
    for fr, v in keys:
        out += struct.pack('<i%df' % sz, fr, *v)
    return out

def w_node(name, oid, parent, flags, tracks):
    body = pad(name, 80) + struct.pack('<IiI', oid, parent, flags)
    for t in tracks: body += t
    return struct.pack('<I', len(body) + 4) + body

def chunk(tag, body):
    return tag.encode() + struct.pack('<I', len(body)) + body

def save(model):
    """model: dict(name, seqs[(name,start,end,speed,flags)], textures[(rid,file)], materials[[(filter,shading,tex,alpha)]],
    geosets[dict verts,normals,uvs,faces,gndx,mtgc,mats,material,extent], bones[dict name,parent,tracks,geoset],
    pivots[], attachments[dict name,parent,pivot,attid])"""
    out = b'MDLX' + chunk('VERS', struct.pack('<I', 800))
    mn, mx = model['extent']
    rad = max(abs(c) for c in mn + mx)
    out += chunk('MODL', pad(model['name'], 80) + pad('', 260) + struct.pack('<7fI', rad, *mn, *mx, 150))
    sb = b''
    for s in model['seqs']:
        sb += pad(s[0], 80) + struct.pack('<IIfIfI7f', s[1], s[2], s[3], s[4], 0.0, 0, rad, *mn, *mx)
    out += chunk('SEQS', sb)
    out += chunk('TEXS', b''.join(struct.pack('<I', rid) + pad(fn, 260) + struct.pack('<I', 0) for rid, fn in model['textures']))
    mb = b''
    for layers in model['materials']:
        lb = b''
        for (flt, shd, tex, alpha) in layers:
            l = struct.pack('<IIIiIf', flt, shd, tex, -1, 0, alpha)
            lb += struct.pack('<I', len(l) + 4) + l
        body = struct.pack('<iI', 0, 0) + b'LAYS' + struct.pack('<I', len(layers)) + lb
        mb += struct.pack('<I', len(body) + 4) + body
    out += chunk('MTLS', mb)
    gb = b''
    for g in model['geosets']:
        nv = len(g['verts'])
        b = b'VRTX' + struct.pack('<I', nv) + b''.join(struct.pack('<3f', *v) for v in g['verts'])
        b += b'NRMS' + struct.pack('<I', nv) + b''.join(struct.pack('<3f', *v) for v in g['normals'])
        b += b'PTYP' + struct.pack('<II', 1, 4)
        b += b'PCNT' + struct.pack('<II', 1, len(g['faces']))
        b += b'PVTX' + struct.pack('<I', len(g['faces'])) + struct.pack('<%dH' % len(g['faces']), *g['faces'])
        b += b'GNDX' + struct.pack('<I', nv) + bytes(g['gndx'])
        b += b'MTGC' + struct.pack('<I', len(g['mtgc'])) + struct.pack('<%dI' % len(g['mtgc']), *g['mtgc'])
        b += b'MATS' + struct.pack('<I', len(g['mats'])) + struct.pack('<%dI' % len(g['mats']), *g['mats'])
        gmn, gmx = g['extent']
        grad = max(abs(c) for c in gmn + gmx)
        b += struct.pack('<III', g['material'], 0, 0) + struct.pack('<7f', grad, *gmn, *gmx)
        b += struct.pack('<I', len(model['seqs'])) + b''.join(struct.pack('<7f', grad, *gmn, *gmx) for _ in model['seqs'])
        b += b'UVAS' + struct.pack('<I', 1) + b'UVBS' + struct.pack('<I', nv) + b''.join(struct.pack('<2f', *uv) for uv in g['uvs'])
        gb += struct.pack('<I', len(b) + 4) + b
    out += chunk('GEOS', gb)
    bb = b''
    for i, bn in enumerate(model['bones']):
        bb += w_node(bn['name'], i, bn['parent'], 0x100, bn['tracks']) + struct.pack('<ii', bn.get('geoset', -1), -1)
    out += chunk('BONE', bb)
    nb = len(model['bones'])
    if model.get('attachments'):
        ab = b''
        for j, a in enumerate(model['attachments']):
            node = w_node(a['name'], nb + j, a['parent'], 0x800, [])
            body = node + pad('', 260) + struct.pack('<I', a['attid'])
            ab += struct.pack('<I', len(body) + 4) + body
        out += chunk('ATCH', ab)
    out += chunk('PIVT', b''.join(struct.pack('<3f', *p) for p in model['pivots']))
    return out
