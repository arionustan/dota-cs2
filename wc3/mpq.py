# Minimal MPQ v1 reader/writer for Warcraft III (read: encryption, zlib, bzip2, pkware explode; write: uncompressed or zlib).
import struct, zlib, bz2, os

def _crypt_table():
    t = [0] * 0x500
    seed = 0x00100001
    for i in range(0x100):
        idx = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            hi = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            lo = seed & 0xFFFF
            t[idx] = hi | lo
            idx += 0x100
    return t
CT = _crypt_table()

def hash_str(s, t):
    s = s.upper().replace('/', '\\')
    s1, s2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in s.encode('latin-1', 'ignore'):
        v = CT[(t << 8) + ch]
        s1 = (v ^ (s1 + s2)) & 0xFFFFFFFF
        s2 = (ch + s1 + s2 + (s2 << 5) + 3) & 0xFFFFFFFF
    return s1

def decrypt(data, key):
    n = len(data) // 4
    vals = struct.unpack('<%dI' % n, data[:n * 4])
    out = []
    s2 = 0xEEEEEEEE
    for v in vals:
        s2 = (s2 + CT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        d = (v ^ (key + s2)) & 0xFFFFFFFF
        out.append(d)
        key = ((~key << 0x15) + 0x11111111 | (key >> 0x0B)) & 0xFFFFFFFF
        s2 = (d + s2 + (s2 << 5) + 3) & 0xFFFFFFFF
    return struct.pack('<%dI' % n, *out) + data[n * 4:]

def encrypt(data, key):
    n = len(data) // 4
    vals = struct.unpack('<%dI' % n, data[:n * 4])
    out = []
    s2 = 0xEEEEEEEE
    for v in vals:
        s2 = (s2 + CT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        out.append((v ^ (key + s2)) & 0xFFFFFFFF)
        key = ((~key << 0x15) + 0x11111111 | (key >> 0x0B)) & 0xFFFFFFFF
        s2 = (v + s2 + (s2 << 5) + 3) & 0xFFFFFFFF
    return struct.pack('<%dI' % n, *out) + data[n * 4:]

# ---------------------------------------------------------------- PKWARE DCL explode
_LenBits = [3,2,3,3,4,4,4,5,5,5,5,6,6,6,7,7]
_LenCode = [5,3,1,6,10,2,12,20,4,24,8,48,16,32,64,0]
_ExLenBits = [0,0,0,0,0,0,0,0,1,2,3,4,5,6,7,8]
_LenBase = [0,1,2,3,4,5,6,7,8,10,14,22,38,70,134,262]
_DistBits = [2,4,4,5,5,5,5,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8]
_DistCode = [0x03,0x0D,0x05,0x19,0x09,0x11,0x01,0x3E,0x1E,0x2E,0x0E,0x36,0x16,0x26,0x06,0x3A,0x1A,0x2A,0x0A,0x32,0x12,0x22,0x42,0x02,0x7C,0x3C,0x5C,0x1C,0x6C,0x2C,0x4C,0x0C,0x74,0x34,0x54,0x14,0x64,0x24,0x44,0x04,0x78,0x38,0x58,0x18,0x68,0x28,0x48,0x08,0xF0,0x70,0xB0,0x30,0xD0,0x50,0x90,0x10,0xE0,0x60,0xA0,0x20,0xC0,0x40,0x80,0x00]

def _rev_lookup(bits, codes):
    d = {}
    for i, (b, c) in enumerate(zip(bits, codes)):
        d[(b, c)] = i
    return d
_LenLookup = _rev_lookup(_LenBits, _LenCode)
_DistLookup = _rev_lookup(_DistBits, _DistCode)

def explode(data):
    ctype, dsize_bits = data[0], data[1]
    if ctype != 0:
        raise NotImplementedError('pkware ascii mode')
    pos = 2; bitbuf = 0; nbits = 0; out = bytearray()
    def bits(n):
        nonlocal pos, bitbuf, nbits
        while nbits < n:
            if pos >= len(data): raise EOFError
            bitbuf |= data[pos] << nbits; pos += 1; nbits += 8
        v = bitbuf & ((1 << n) - 1); bitbuf >>= n; nbits -= n
        return v
    def decode(lookup, maxbits):
        code = 0
        for n in range(1, maxbits + 1):
            code |= bits(1) << (n - 1)
            if (n, code) in lookup: return lookup[(n, code)]
        raise ValueError('bad code')
    try:
        while True:
            if bits(1) == 0:
                out.append(bits(8)); continue
            li = decode(_LenLookup, 7)
            length = _LenBase[li] + (bits(_ExLenBits[li]) if _ExLenBits[li] else 0)
            if length == 519: break
            length += 2
            di = decode(_DistLookup, 8)
            if length == 2: dist = (di << 2) | bits(2)
            else: dist = (di << dsize_bits) | bits(dsize_bits)
            dist += 1
            for _ in range(length): out.append(out[-dist])
    except EOFError:
        pass
    return bytes(out)

def _decompress(sector, usize):
    if len(sector) == usize: return sector
    mask = sector[0]; d = sector[1:]
    if mask & 0x10: d = bz2.decompress(d)
    if mask & 0x08: d = explode(d)
    if mask & 0x02: d = zlib.decompress(d)
    if mask & ~(0x10 | 0x08 | 0x02): raise NotImplementedError('compression %x' % mask)
    return d

class MPQ:
    def __init__(self, path):
        self.f = open(path, 'rb'); data = self.f.read(); self.data = data
        off = 0
        while True:
            if data[off:off + 4] == b'MPQ\x1a': break
            off += 512
            if off > len(data): raise ValueError('no MPQ header')
        self.base = off
        _, hsize, asize, ver, sshift, htpos, btpos, htn, btn = struct.unpack_from('<4sIIHHIIII', data, off)
        self.sector = 512 << sshift
        ht = decrypt(data[off + htpos: off + htpos + htn * 16], hash_str('(hash table)', 3))
        bt = decrypt(data[off + btpos: off + btpos + btn * 16], hash_str('(block table)', 3))
        self.hash = [struct.unpack_from('<IIHHI', ht, i * 16) for i in range(htn)]
        self.block = [struct.unpack_from('<IIII', bt, i * 16) for i in range(btn)]

    def find(self, name):
        n = len(self.hash); i = hash_str(name, 0) % n
        a, b = hash_str(name, 1), hash_str(name, 2)
        for _ in range(n):
            h = self.hash[i]
            if h[4] == 0xFFFFFFFF: return None
            if h[0] == a and h[1] == b and h[4] < len(self.block): return h[4]
            i = (i + 1) % n
        return None

    def read(self, name):
        bi = self.find(name)
        if bi is None: return None
        pos, csize, usize, flags = self.block[bi]
        if not flags & 0x80000000: return None
        raw = self.data[self.base + pos: self.base + pos + csize]
        key = 0
        if flags & 0x00010000:
            key = hash_str(name.replace('/', '\\').split('\\')[-1], 3)
            if flags & 0x00020000: key = ((key + pos) ^ usize) & 0xFFFFFFFF
        if flags & 0x01000000:  # single unit
            if flags & 0x00010000: raw = decrypt(raw, key)
            if flags & 0x00000200: return _decompress(raw, usize)
            if flags & 0x00000100: return explode(raw) if len(raw) < usize else raw
            return raw
        if not flags & 0x00000300:
            if flags & 0x00010000:
                out = bytearray()
                for s in range(0, len(raw), self.sector):
                    out += decrypt(raw[s:s + self.sector], (key + s // self.sector) & 0xFFFFFFFF)
                return bytes(out)
            return raw
        ns = (usize + self.sector - 1) // self.sector
        tbl = raw[:(ns + 1) * 4]
        if flags & 0x00010000: tbl = decrypt(tbl, (key - 1) & 0xFFFFFFFF)
        offs = struct.unpack('<%dI' % (ns + 1), tbl)
        out = bytearray()
        for s in range(ns):
            sec = raw[offs[s]:offs[s + 1]]
            if flags & 0x00010000: sec = decrypt(sec, (key + s) & 0xFFFFFFFF)
            exp = min(self.sector, usize - s * self.sector)
            if flags & 0x00000200: sec = _decompress(sec, exp)
            elif flags & 0x00000100 and len(sec) < exp: sec = explode(sec)
            out += sec
        return bytes(out)

    def listfile(self):
        d = self.read('(listfile)')
        return [l for l in d.decode('latin-1').replace('\r', '').split('\n') if l] if d else []


def write_mpq(path, files, header_prefix=b''):
    """files: dict name -> bytes. Writes MPQ v1 with zlib-compressed, unencrypted files, plus (listfile)."""
    names = list(files.keys())
    if '(listfile)' not in files:
        files = dict(files); files['(listfile)'] = ('\r\n'.join(names) + '\r\n').encode('latin-1')
        names.append('(listfile)')
    n = 1
    while n < len(names) * 2: n *= 2
    n = max(n, 16)
    sector = 4096
    body = bytearray(); blocks = []
    hdr_size = 32
    for name in names:
        data = files[name]
        ns = max(1, (len(data) + sector - 1) // sector)
        secs = []
        for s in range(ns):
            chunk = data[s * sector:(s + 1) * sector]
            c = b'\x02' + zlib.compress(chunk, 9)
            secs.append(c if len(c) < len(chunk) else chunk)
        offs = [(ns + 1) * 4]
        for c in secs: offs.append(offs[-1] + len(c))
        blob = struct.pack('<%dI' % (ns + 1), *offs) + b''.join(secs)
        pos = hdr_size + len(body)
        body += blob
        blocks.append((pos, len(blob), len(data), 0x80000000 | 0x00000200))
    ht = [(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFF, 0xFFFF, 0xFFFFFFFF)] * n
    for bi, name in enumerate(names):
        i = hash_str(name, 0) % n
        while ht[i][4] != 0xFFFFFFFF: i = (i + 1) % n
        ht[i] = (hash_str(name, 1), hash_str(name, 2), 0, 0, bi)
    htb = b''.join(struct.pack('<IIHHI', *h) for h in ht)
    btb = b''.join(struct.pack('<IIII', *b) for b in blocks)
    htpos = hdr_size + len(body); btpos = htpos + len(htb)
    total = btpos + len(btb)
    hdr = struct.pack('<4sIIHHIIII', b'MPQ\x1a', 32, total, 0, 3, htpos, btpos, n, len(blocks))
    with open(path, 'wb') as f:
        f.write(header_prefix)
        f.write(hdr); f.write(body)
        f.write(encrypt(htb, hash_str('(hash table)', 3)))
        f.write(encrypt(btb, hash_str('(block table)', 3)))


def _pack_file(data, sector):
    ns = max(1, (len(data) + sector - 1) // sector)
    secs = []
    for s in range(ns):
        chunk = data[s * sector:(s + 1) * sector]
        c = b'\x02' + zlib.compress(chunk, 9)
        secs.append(c if len(c) < len(chunk) else chunk)
    offs = [(ns + 1) * 4]
    for c in secs: offs.append(offs[-1] + len(c))
    return struct.pack('<%dI' % (ns + 1), *offs) + b''.join(secs)


def patch_mpq(src, out, replace):
    """Copies an MPQ byte for byte (keeps files whose names are unknown, e.g. protected maps)
    and replaces or adds the named files. replace: dict name -> bytes."""
    a = MPQ(src)
    data = a.data; base = a.base
    _, hsize, asize, ver, sshift, htpos, btpos, htn, btn = struct.unpack_from('<4sIIHHIIII', data, base)
    body = bytearray(data[base:])        # everything after the prefix, offsets stay valid
    hdr_len = 32
    hashes = [list(h) for h in a.hash]; blocks = [list(b) for b in a.block]
    for name, d in replace.items():
        blob = _pack_file(d, a.sector)
        pos = len(body); body += blob
        entry = [pos, len(blob), len(d), 0x80000000 | 0x00000200]
        bi = a.find(name)
        if bi is not None:
            blocks[bi] = entry
            continue
        blocks.append(entry); bi = len(blocks) - 1
        i = hash_str(name, 0) % htn
        for _ in range(htn):
            if hashes[i][4] in (0xFFFFFFFF, 0xFFFFFFFE): break
            i = (i + 1) % htn
        else:
            raise ValueError('hash table full')
        hashes[i] = [hash_str(name, 1), hash_str(name, 2), 0, 0, bi]
    htb = b''.join(struct.pack('<IIHHI', *h) for h in hashes)
    btb = b''.join(struct.pack('<IIII', *b) for b in blocks)
    new_ht = len(body); body += encrypt(htb, hash_str('(hash table)', 3))
    new_bt = len(body); body += encrypt(btb, hash_str('(block table)', 3))
    struct.pack_into('<4sIIHHIIII', body, 0, b'MPQ\x1a', hdr_len, len(body), 0, sshift, new_ht, new_bt, htn, len(blocks))
    with open(out, 'wb') as f:
        f.write(data[:base]); f.write(body)
