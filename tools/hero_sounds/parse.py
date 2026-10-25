import re,os,json,glob
P=json.load(open('/tmp/hs/plan.json'))
def events(path):
    t=open(path).read()
    ev={}
    for m in re.finditer(r'\n\t([A-Za-z0-9_.]+) = \n\t\{(.*?)\n\t\}',t,re.S):
        name,body=m.group(1),m.group(2)
        files=re.findall(r'"(sounds/[^"]+\.vsnd)"',body)
        vol=re.search(r'\n\t\tvolume = ([\d.]+)',body)
        ev[name]={'files':files,'vol':float(vol.group(1)) if vol else 1.0}
    return ev
def abilities(h):
    t=open('/tmp/hs/raw/scripts/npc/heroes/npc_dota_hero_%s.txt'%h,encoding='utf-8',errors='ignore').read()
    return [a for a in re.findall(r'"Ability\d"\s+"([a-z0-9_]+)"',t) if 'empty' not in a and 'hidden' not in a][:6]
norm=lambda s: re.sub(r'[^a-z0-9]','',s.lower())
plan={}
for h,s in P['H'].items():
    ev=events('/tmp/hs/raw/soundevents/game_sounds_heroes/game_sounds_%s.vsndevts.txt'%s)
    ev={k:v for k,v in ev.items() if v['files']}
    out={}
    att=[k for k in ev if k.lower().endswith('.attack')] or [k for k in ev if '.attack' in k.lower() and 'pre' not in k.lower()]
    if att: out['attack']=sorted(att,key=len)[0]
    dth=[k for k in ev if k.lower().endswith('.death') or k.lower().endswith('.die')]
    if dth: out['death']=sorted(dth,key=len)[0]
    abil={}
    for a in abilities(h):
        tail=a.split('_',1)[1] if '_' in a else a
        # drop hero name prefix variants
        toks=[t for t in tail.split('_') if t]
        key=norm(''.join(toks))
        cand=[k for k in ev if key and key in norm(k.split('.',1)[-1])]
        if not cand and len(toks)>1:
            cand=[k for k in ev if norm(toks[-1]) in norm(k.split('.',1)[-1]) and len(toks[-1])>3]
        good=[k for k in cand if not any(b in k.lower() for b in ('stop','fail','end','loop','arcana','hud','.attack','preattack'))]
        if good: cand=good
        if cand: abil[a]=sorted(cand,key=len)[0]
    out['abilities']=abil
    plan[h]={'events':out,'files':{k:ev[k]['files'][:3] for k in [out.get('attack'),out.get('death')]+list(abil.values()) if k},'vol':{k:ev[k]['vol'] for k in ev}}
    print(h, out.get('attack'), out.get('death'), abil)
json.dump(plan,open('/tmp/hs/sndplan.json','w'),indent=1)
