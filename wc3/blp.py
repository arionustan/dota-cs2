# BLP1 writer (paletted, optional 8-bit alpha) for Warcraft III.
import struct
from PIL import Image

def save_blp1(img, path, size=512):
    img = img.convert('RGBA')
    if max(img.size) > size:
        img = img.resize((size, size), Image.LANCZOS)
    w, h = img.size
    alpha = img.getchannel('A')
    has_alpha = alpha.getextrema()[0] < 250
    rgb = img.convert('RGB').quantize(256, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = rgb.getpalette()[:768]
    pal += [0] * (768 - len(pal))
    mips = []
    cw, ch = w, h
    pimg, aimg = rgb, alpha
    while True:
        data = bytes(pimg.getdata())
        if has_alpha: data += bytes(aimg.getdata())
        mips.append(data)
        if cw == 1 and ch == 1 or len(mips) == 16: break
        cw, ch = max(1, cw // 2), max(1, ch // 2)
        small = img.resize((cw, ch), Image.LANCZOS)
        pimg = small.convert('RGB').quantize(palette=rgb, dither=Image.NONE)
        aimg = small.getchannel('A')
    hdr_len = 4 + 4 * 6 + 64 + 64 + 1024
    offs, sizes, pos = [], [], hdr_len
    for d in mips: offs.append(pos); sizes.append(len(d)); pos += len(d)
    offs += [0] * (16 - len(offs)); sizes += [0] * (16 - len(sizes))
    out = b'BLP1' + struct.pack('<6I', 1, 8 if has_alpha else 0, w, h, 4 if has_alpha else 5, 1)
    out += struct.pack('<16I', *offs) + struct.pack('<16I', *sizes)
    out += b''.join(struct.pack('<4B', pal[i * 3 + 2], pal[i * 3 + 1], pal[i * 3], 0) for i in range(256))
    out += b''.join(mips)
    open(path, 'wb').write(out)
    return has_alpha
