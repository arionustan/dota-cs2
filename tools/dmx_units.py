import re,os,glob,shutil,subprocess,json,sys
G='/tmp/dx/game'; O='/mnt/user-data/outputs/units2'
def decompile(vmdl):
    p=G+'/'+vmdl+'_c'; base=p[:-len('.vmdl_c')]
    if not os.path.exists(base+'.vmdl'):
        subprocess.run(['/tmp/vrf/Source2Viewer-CLI','-i',p,'-d','-o',os.path.dirname(p)],capture_output=True,timeout=900)
    return base+'.vmdl'
def parse(vm):
    t=open(vm).read()
    meshes=re.findall(r'_class = "RenderMeshFile".*?filename = "([^"]+)"',t,re.S)
    anims=[]
    for b in re.findall(r'_class = "AnimFile"(.*?)\n\t*\}',t,re.S):
        n=re.search(r'name = "([^"]+)"',b); f=re.search(r'source_filename = "([^"]+)"',b); a=re.search(r'activity_name = "([^"]*)"',b)
        lp=re.search(r'looping = (\w+)',b)
        if n and f: anims.append((n.group(1),f.group(1),a.group(1) if a else '', lp and lp.group(1)=='true'))
    return meshes,anims
WANT={'idle':(['ACT_DOTA_IDLE'],['idle']),'run':(['ACT_DOTA_RUN'],['run','walk']),'attack':(['ACT_DOTA_ATTACK'],['attack']),
      'death':(['ACT_DOTA_DIE'],['death','die']),'hook':(['ACT_DOTA_OVERRIDE_ABILITY_1','ACT_DOTA_CAST_ABILITY_1'],['hook']),'stun':(['ACT_DOTA_DISABLED'],['stun'])}
def pick(anims,key):
    acts,words=WANT[key]
    BAD=('injured','ti7','ti10','hh_','_alt','debug','overkilled','persona','arcana','loadout')
    c=[a for a in anims if a[2] in acts and not a[0].startswith('@') and not any(x in a[0].lower() for x in BAD)]
    if c: return c[0]
    c=[a for a in anims if a[2] in acts and not a[0].startswith('@')]
    if not c: c=[a for a in anims if any(w in a[0].lower() for w in words) and not a[0].startswith('@')]
    if not c: c=[a for a in anims if any(w in a[0].lower() for w in words)]
    c.sort(key=lambda a:(len(a[0]),a[0])); return c[0] if c else None
def mtl_paths(dmx):
    return set(re.findall(rb'(materials/[A-Za-z0-9_/\-.]+\.vmat)',open(dmx,'rb').read()))
def animblock(name,fn,loop):
    return '{\n_class = "AnimFile"\nname = "%s"\nactivity_name = ""\nactivity_weight = 1\nweight_list_name = ""\nfade_in_time = 0.2\nfade_out_time = 0.2\nlooping = %s\ndelta = false\nworldSpace = false\nhidden = false\nanim_markup_ordered = false\ndisable_compression = false\nsource_filename = "%s"\nstart_frame = -1\nend_frame = -1\nframerate = -1.0\ntake = 0\nreverse = false\n},\n'%(name,'true' if loop else 'false',fn)
def build(n, vmdls, matdir, keys, outbase):
    od=O+'/'+n; os.makedirs(od,exist_ok=True)
    meshes=[];anims=None
    for i,v in enumerate(vmdls):
        ms,an=parse(decompile(v))
        meshes+=[x for x in ms if '_lod' not in x]
        if i==0: anims=an
    vm={os.path.splitext(os.path.basename(f))[0].lower():os.path.basename(f) for f in glob.glob(matdir+'/*.vmat')}
    for f in glob.glob(matdir+'/*'):
        if not f.endswith(('.fbx','.vmdl')): shutil.copy(f,od)
    rm=''; first=None; seen=set()
    meshtxt=''
    for m in meshes:
        src=G+'/'+m; dst=os.path.basename(m); shutil.copy(src,od+'/'+dst)
        meshtxt+='{\n_class = "RenderMeshFile"\nfilename = "%s%s"\nimport_translation = [ 0.0, 0.0, 0.0 ]\nimport_rotation = [ 0.0, 0.0, 0.0 ]\nimport_scale = 1.0\nalign_origin_x_type = "None"\nalign_origin_y_type = "None"\nalign_origin_z_type = "None"\nparent_bone = ""\nimport_filter = \n{\nexclude_by_default = false\nexception_list = [  ]\n}\n},\n'%(outbase,dst)
        for mp in mtl_paths(src):
            mp=mp.decode()
            if mp in seen: continue
            seen.add(mp); b=os.path.splitext(os.path.basename(mp))[0].lower()
            tgt=vm.get(b) or next((v for k,v in vm.items() if b in k or k in b),None)
            if tgt:
                rm+='{\nfrom = "%s"\nto = "%s%s"\n},\n'%(mp,outbase,tgt); first=first or outbase+tgt
    at=''; got={}
    for k in keys:
        a=pick(anims,k) or pick(anims,'idle')
        if not a: continue
        dst=os.path.basename(a[1]); shutil.copy(G+'/'+a[1],od+'/'+dst)
        at+=animblock(k,outbase+dst,k in ('idle','run')); got[k]=a[0]
    v='''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc29:version{3cec427c-1b0e-4d48-a90a-0436f33a6041} -->
{
rootNode = 
{
_class = "RootNode"
children = 
[
{
_class = "MaterialGroupList"
children = 
[
{
_class = "DefaultMaterialGroup"
remaps = 
[
%s]
use_global_default = false
global_default_material = "%s"
},
]
},
{
_class = "BoneMarkupList"
bone_cull_type = "None"
children = [  ]
},
{
_class = "RenderMeshList"
children = 
[
%s]
},
{
_class = "AnimationList"
children = 
[
%s]
default_root_bone_name = ""
},
]
model_archetype = ""
primary_associated_entity = ""
anim_graph_name = ""
base_model_name = ""
}
}
'''%(rm, first or 'materials/default/default.vmat', meshtxt, at)
    open(od+'/'+n+'.vmdl','w').write(v)
    print('UNIT',n,len(meshes),'meshes',got,'remaps',rm.count('from'),'/',len(seen))
if __name__=='__main__':
    which=sys.argv[1:]
    plan=json.load(open('/tmp/dx/unitplan.json'))['models']
    for m in plan:
        if '_mega' in m: continue
        n=os.path.basename(m)[:-5]
        if which and n not in which: continue
        if not os.path.exists('/mnt/user-data/outputs/units/'+n): continue
        try: build(n,[m],'/mnt/user-data/outputs/units/'+n,['idle','run','attack','death'],'models/dota_units/%s/'%n)
        except Exception as e: print('FAIL',n,e)
