import sys,os
src,dst=sys.argv[1],sys.argv[2]
for f in sorted(os.listdir(src)):
    if not f.endswith('.obj'): continue
    out=[]
    for line in open(os.path.join(src,f)):
        if line.startswith('v '):
            p=line.split(); x,y,z=float(p[1]),float(p[2]),float(p[3])
            out.append('v %.2f %.2f %.2f\n'%(y,z,x))
        elif line.startswith('vn '):
            p=line.split(); x,y,z=float(p[1]),float(p[2]),float(p[3])
            out.append('vn %.3f %.3f %.3f\n'%(y,z,x))
        elif line.startswith('vt '):
            p=line.split(); out.append('vt %.4f %.4f\n'%(float(p[1]),float(p[2])))
        elif line.startswith(('o ','s ','mtllib','#')): continue
        else: out.append(line)
    open(os.path.join(dst,f),'w').writelines(out)
    print(f, os.path.getsize(os.path.join(dst,f))//1000000,'MB')
