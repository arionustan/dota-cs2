import json, struct, numpy as np
CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
class GLB:
    def __init__(s, path):
        d = open(path, 'rb').read()
        n = struct.unpack_from('<I', d, 12)[0]
        s.j = json.loads(d[20:20 + n])
        off = 20 + n
        bl = struct.unpack_from('<I', d, off)[0]
        s.bin = d[off + 8: off + 8 + bl]
    def acc(s, i):
        a = s.j['accessors'][i]; bv = s.j['bufferViews'][a['bufferView']]
        dt = np.dtype(CT[a['componentType']]); nc = NC[a['type']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', 0) or dt.itemsize * nc
        raw = np.frombuffer(s.bin, dtype=np.uint8, count=stride * (a['count'] - 1) + dt.itemsize * nc, offset=start)
        out = np.lib.stride_tricks.as_strided(raw, shape=(a['count'], dt.itemsize * nc), strides=(stride, 1))
        arr = np.ascontiguousarray(out).view(dt).reshape(a['count'], nc)
        if a.get('normalized'):
            arr = arr.astype(np.float32) / np.iinfo(dt).max
        return arr
