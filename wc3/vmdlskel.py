import re, numpy as np
def parse(path):
    t = open(path).read()
    def block(key):
        i = t.index(key); j = t.index('[', i); depth = 0
        for k in range(j, len(t)):
            if t[k] == '[': depth += 1
            elif t[k] == ']':
                depth -= 1
                if depth == 0: return t[j:k + 1]
    names = re.findall(r'"([^"]+)"', block('m_boneName'))
    par = [int(x) for x in re.findall(r'-?\d+', block('m_nParent'))]
    pos = np.array([[float(v) for v in m] for m in re.findall(r'\[\s*([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+)\s*\]', block('m_bonePosParent'))])
    rot = np.array([[float(v) for v in m] for m in re.findall(r'\[\s*([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+)\s*\]', block('m_boneRotParent'))])
    remap = [int(x) for x in re.findall(r'-?\d+', block('m_remappingTable '))] if 'm_remappingTable ' in t else None
    starts = [int(x) for x in re.findall(r'-?\d+', block('m_remappingTableStarts'))]
    return names, par, pos, rot, remap, starts
