# Rasterizes the Dota terrain mesh into a top-surface height field on a 32-unit grid (641x641, origin -10240).
import numpy as np
T = np.load('/tmp/dx/terrain_tris.npy').astype(np.float64)
O, S, N = -10240.0, 32.0, 641
H = np.full((N, N), -1e9)
a, b, c = T[:, 0], T[:, 1], T[:, 2]
# keep only upward-facing triangles (skip vertical cliff walls / undersides)
nz = (b[:, 0]-a[:, 0])*(c[:, 1]-a[:, 1]) - (b[:, 1]-a[:, 1])*(c[:, 0]-a[:, 0])
keep = np.abs(nz) > 1e-6
a, b, c, nz = a[keep], b[keep], c[keep], nz[keep]
mn = np.minimum(np.minimum(a, b), c); mx = np.maximum(np.maximum(a, b), c)
i0 = np.ceil((mn[:, 0]-O)/S).astype(int); i1 = np.floor((mx[:, 0]-O)/S).astype(int)
j0 = np.ceil((mn[:, 1]-O)/S).astype(int); j1 = np.floor((mx[:, 1]-O)/S).astype(int)
span = max((i1-i0).max(), (j1-j0).max()) + 1
print('tris', len(a), 'max span', span)
for di in range(span):
    for dj in range(span):
        ii = i0 + di; jj = j0 + dj
        m = (ii <= i1) & (jj <= j1) & (ii >= 0) & (ii < N) & (jj >= 0) & (jj < N)
        if not m.any(): continue
        A, B, C, I, J, NZ = a[m], b[m], c[m], ii[m], jj[m], nz[m]
        px = O + I*S; py = O + J*S
        w0 = ((B[:, 0]-px)*(C[:, 1]-py) - (B[:, 1]-py)*(C[:, 0]-px))/NZ
        w1 = ((C[:, 0]-px)*(A[:, 1]-py) - (C[:, 1]-py)*(A[:, 0]-px))/NZ
        w2 = 1 - w0 - w1
        ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        z = w0*A[:, 2] + w1*B[:, 2] + w2*C[:, 2]
        np.maximum.at(H, (I[ins], J[ins]), z[ins])
miss = H < -1e8
print('missing', miss.sum())
# fill holes with nearest neighbour average
from scipy import ndimage
if miss.any():
    idx = ndimage.distance_transform_edt(miss, return_distances=False, return_indices=True)
    H = H[tuple(idx)]
np.save('/tmp/w3/gen/hf32.npy', H)   # H[ix, iy]
print(np.percentile(H, [1, 5, 25, 50, 75, 95, 99]))
h, e = np.histogram(H, bins=np.arange(-512, 1100, 64)); print(list(zip(e[:-1].astype(int), h)))
