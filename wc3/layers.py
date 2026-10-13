# Plateau layers: tilepoints joined by gentle slopes share a WC3 cliff layer; real Dota cliffs become WC3 cliffs.
import numpy as np
H = np.load('/tmp/w3/gen/hf32.npy'); Hc = H[::4, ::4]; N = 161; Z0 = 128; T = 60
sx = np.stack([np.abs(np.diff(H[4*i:4*i+5, ::4], axis=0)).max(0) for i in range(N-1)])
sy = np.stack([np.abs(np.diff(H[::4, 4*j:4*j+5], axis=1)).max(1) for j in range(N-1)]).T
par = np.arange(N*N)
def f(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for i in range(N-1):
    for j in range(N):
        if sx[i, j] < T: par[f(i*N+j)] = f((i+1)*N+j)
for i in range(N):
    for j in range(N-1):
        if sy[i, j] < T: par[f(i*N+j)] = f(i*N+j+1)
root = np.array([f(k) for k in range(N*N)])
q = np.round((Hc - Z0) / 128).ravel()
u, inv, cnt = np.unique(root, return_inverse=True, return_counts=True); inv = inv.ravel()
lay = np.array([np.median(q[inv == k]) for k in range(len(u))])
L = np.round(lay[inv]).reshape(N, N)
print('components', len(u), 'sizes', sorted(cnt)[-8:])
print('layer range', L.min(), L.max(), 'max nb diff', np.abs(np.diff(L, axis=0)).max(), np.abs(np.diff(L, axis=1)).max())
print('cliff edges', (np.diff(L, axis=0) != 0).sum() + (np.diff(L, axis=1) != 0).sum())
np.save('/tmp/w3/gen/layers.npy', L)
