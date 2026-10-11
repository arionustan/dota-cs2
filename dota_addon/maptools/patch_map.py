# DotaCS: copies the built Dota map into CS2 (client and server) and puts a bot nav mesh into it.
import sys, os, struct, zlib, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo_addons\dotacs_arena\maps\dotacs_arena.vpk"
DSTS = [r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\maps\dotacs_arena.vpk",
        r"C:\cs2server\cs2\game\csgo\maps\dotacs_arena.vpk"]
NAV = os.path.join(HERE, "dotacs_arena.nav")

def read_vpk(path):
    data = open(path, 'rb').read()
    sig, ver, tree = struct.unpack_from('<III', data, 0)
    assert sig == 0x55aa1234
    off = 12 if ver == 1 else 28
    end = off + tree
    files = {}
    p = off
    def rs():
        nonlocal p
        e = data.index(b'\0', p); s = data[p:e].decode('utf-8'); p = e + 1; return s
    while True:
        ext = rs()
        if not ext: break
        while True:
            d = rs()
            if not d: break
            while True:
                n = rs()
                if not n: break
                crc, pre, arc, eoff, elen, term = struct.unpack_from('<IHHIIH', data, p); p += 18
                predata = data[p:p + pre]; p += pre
                full = (d + '/' if d.strip() else '') + n + ('.' + ext if ext.strip() else '')
                files[full] = predata + data[end + eoff:end + eoff + elen]
    return files

def write_vpk(files, out):
    by_ext = {}
    for p, data in files.items():
        d, n = os.path.split(p)
        name, ext = n.rsplit('.', 1) if '.' in n else (n, ' ')
        by_ext.setdefault(ext, {}).setdefault(d or ' ', []).append((name, data))
    tree = bytearray(); blob = bytearray()
    for ext in sorted(by_ext):
        tree += ext.encode() + b'\0'
        for d in sorted(by_ext[ext]):
            tree += d.encode() + b'\0'
            for name, data in sorted(by_ext[ext][d]):
                tree += name.encode() + b'\0'
                tree += struct.pack('<IHHIIH', zlib.crc32(data) & 0xffffffff, 0, 0x7fff, len(blob), len(data), 0xffff)
                blob += data
            tree += b'\0'
        tree += b'\0'
    tree += b'\0'
    header = struct.pack('<IIIIIII', 0x55aa1234, 2, len(tree), len(blob), 0, 48, 0)
    body = header + bytes(tree) + bytes(blob)
    tmd5 = hashlib.md5(bytes(tree)).digest(); amd5 = hashlib.md5(b'').digest()
    whole = hashlib.md5(body + tmd5 + amd5).digest()
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(body); f.write(tmd5); f.write(amd5); f.write(whole)
    os.replace(tmp, out)

if __name__ == '__main__':
    if not os.path.exists(SRC):
        print('No built map at', SRC); sys.exit(0)
    files = read_vpk(SRC)
    files['maps/dotacs_arena.nav'] = open(NAV, 'rb').read()
    for dst in DSTS:
        try:
            write_vpk(files, dst); print('Map ready:', dst)
        except Exception as ex:
            print('Could not write', dst, ex)
