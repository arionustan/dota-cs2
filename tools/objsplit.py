# fix usemtl suffixes, split OBJ files bigger than LIMIT into parts (reindexed)
import sys,os,re
src,dst=sys.argv[1],sys.argv[2]; LIMIT=19_000_000
for f in sorted(os.listdir(src)):
    if not f.endswith('.obj'): continue
    V=[];VT=[];VN=[];faces=[]  # faces: (mtl, [(v,vt,vn)...])
    mtl=None
    for line in open(os.path.join(src,f)):
        if line.startswith('v '): V.append(line)
        elif line.startswith('vt '): VT.append(line)
        elif line.startswith('vn '): VN.append(line)
        elif line.startswith('usemtl'): mtl=re.sub(r'\.\d{3}$','',(line.split()+['tree_gnarly001'])[1])
        elif line.startswith('f '):
            faces.append((mtl,[tuple(int(x) if x else 0 for x in c.split('/')) for c in line.split()[1:]]))
    size=os.path.getsize(os.path.join(src,f))
    n=max(1,-(-size//LIMIT))
    base=f[:-4]
    for k in range(n):
        part=faces[k*len(faces)//n:(k+1)*len(faces)//n]
        mv={};mt={};mn={};out=[];fl=[];cur=None
        def idx(m,arr,i):
            if i==0: return ''
            if i not in m: m[i]=len(m)+1
            return str(m[i])
        for mt_,cs in part:
            if mt_!=cur: fl.append('usemtl %s\n'%mt_); cur=mt_
            fl.append('f '+' '.join('%s/%s/%s'%(idx(mv,V,c[0]),idx(mt,VT,c[1]) if len(c)>1 else '',idx(mn,VN,c[2]) if len(c)>2 else '') for c in cs)+'\n')
        out+= [V[i-1] for i in sorted(mv,key=mv.get)]
        out+= [VT[i-1] for i in sorted(mt,key=mt.get)]
        out+= [VN[i-1] for i in sorted(mn,key=mn.get)]
        name=base+('' if n==1 else chr(97+k))+'.obj'
        open(os.path.join(dst,name),'w').writelines(out+fl)
        print(name, os.path.getsize(os.path.join(dst,name))//1000000,'MB')
