import glob,sys
KEEP=('temple_stairs','stone_wall','cliff_wall','radiant_wall','good_base_wall','cathedral','statue','wood_walls','wood_fence','log002','ground_rock','river_rocks','campfire_rocks','neutral_creep_camp','urn0','water_creep_camp_huts','bad_shop','good_shop','secretshop','radiant_barracks','fountain_')
out=open('/tmp/dx/struct_raw.obj','w'); n=0; nf=0
for fn in sorted(glob.glob('/mnt/user-data/outputs/csaddon3/world_[0-3][0-3].obj')):
    V=[]; keep=False; vmap={}
    for line in open(fn):
        if line.startswith('v '): V.append(line); continue
        if line.startswith('usemtl'): keep=any(k in line for k in KEEP); continue
        if keep and line.startswith('f '):
            idx=[]
            for t in line.split()[1:]:
                i=int(t.split('/')[0]); i=i if i>0 else len(V)+1+i
                if i not in vmap: n+=1; vmap[i]=n; out.write(V[i-1])
                idx.append(vmap[i])
            out.write('f '+' '.join(map(str,idx))+'\n'); nf+=1
print('faces',nf)
