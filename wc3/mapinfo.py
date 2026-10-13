# Computes what a WC3 LAN host must announce about a map: size, CRC32, "xoro" map CRC, SHA1, playable size, slots.
import sys, os, struct, zlib, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mpq import MPQ

def rotl(v, n): return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF

def xoro(data):
    v = 0; i = 0; n = len(data)
    if n > 3:
        while i < n - 3:
            v = rotl(v ^ struct.unpack_from('<I', data, i)[0], 3); i += 4
    while i < n:
        v = rotl(v ^ data[i], 3); i += 1
    return v

def map_info(map_path, common_j, blizzard_j):
    raw = open(map_path, 'rb').read()
    a = MPQ(map_path)
    val = xoro(common_j) ^ xoro(blizzard_j)
    val = rotl(val, 3)
    val = rotl(val ^ 0x03F1379E, 3)
    sha = hashlib.sha1(); sha.update(common_j); sha.update(blizzard_j); sha.update(struct.pack('>I', 0x9E37F103))
    for name in ['war3map.j', 'war3map.w3e', 'war3map.wpm', 'war3map.doo', 'war3map.w3u', 'war3map.w3b', 'war3map.w3d', 'war3map.w3a', 'war3map.w3q']:
        d = a.read(name)
        if d is None and name == 'war3map.j': d = a.read('scripts\\war3map.j')
        if d is None: continue
        val = rotl(val ^ xoro(d), 3); sha.update(d)
    w3i = a.read('war3map.w3i'); p = 12
    def rstr():
        nonlocal p
        e = w3i.index(b'\0', p); s = w3i[p:e]; p = e + 1; return s
    for _ in range(4): rstr()
    p += 32 + 16
    width, height, flags = struct.unpack_from('<iiI', w3i, p)
    return {'size': len(raw), 'crc32': zlib.crc32(raw) & 0xFFFFFFFF, 'xoro': val, 'sha1': sha.hexdigest(),
            'width': width, 'height': height, 'w3i_flags': flags}

if __name__ == '__main__':
    m, cj, bj, out = sys.argv[1:5]
    info = map_info(m, open(cj, 'rb').read(), open(bj, 'rb').read())
    info['path'] = 'Maps/' + os.path.basename(m)
    json.dump(info, open(out, 'w'), indent=1)
    print(info)
