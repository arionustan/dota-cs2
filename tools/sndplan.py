import re,pickle,json
EV=["Hero_Pudge.Attack","Hero_Pudge.AttackHookExtend","Hero_Pudge.AttackHookImpact","Hero_Pudge.AttackHookRetract","Hero_Pudge.Rot","Hero_Pudge.Dismember.Cast","Hero_Pudge.Dismember","Hero_Pudge.Death","Hero_Pudge.Eject",
"Creep_Good_Range.Attack","Creep_Good_Melee.Attack","Creep_Good_Engine.Attack","Creep_Bad_Range.Attack","Creep_Bad_Melee.Attack","Creep_Bad_Engine.Attack",
"n_creep_Melee.Attack","n_creep_Ranged.Attack","Roshan.Attack","Roshan.Death","Roshan.Grunt","Roshan.Bash","Roshan.Slam",
"n_creep_kobolds.Death","n_creep_trollCommon.Death","n_creep_SatyrCommon.Death","n_creep_gnoll.Death","n_creep_ogres.Death","n_creep_harpy.Death","n_creep_centaurKhan.Death","n_creep_Worg.Death","n_creep_golemRock.Death","n_creep_blackdragon.Death","n_creep_blackdrake.Death","n_creep_furbolgUrsa.Death","n_creep_Wildkin.Death","n_creep_Thunderlizard_Big.Death","n_creep_ghost.Death","n_creep_fellbeast.Death","n_creep_junglestalkerCommon.Death","n_creep_dragonspawnOverseer.Death",
"Tower.HeroImpact","Building_RadiantTower.Destruction","Building_DireTower.Destruction","Damage_Projectile.Player","General.Attack"]
txt=""
for f in ["snd/soundevents/game_sounds.vsndevts","snd/soundevents/game_sounds_creeps.vsndevts","snd/soundevents/game_sounds_heroes/game_sounds_pudge.vsndevts"]: txt+=open(f).read()+"\n"
e=pickle.load(open('pe.pkl','rb')); d=e[0] if isinstance(e,tuple) else e
plan={}
for ev in EV:
    m=re.search(r'\n\s*"?'+re.escape(ev)+r'"?\s*=\s*\n?\s*\{',txt)
    if not m: print("MISSING",ev); continue
    i=m.end(); dep=1; j=i
    while dep: 
        c=txt[j]; dep+= (c=='{')-(c=='}'); j+=1
    blk=txt[i:j]
    files=re.findall(r'"(sounds/[^"]+\.vsnd)"',blk)
    vol=re.search(r'\bvolume\s*=\s*([\d.]+)',blk)
    files=[f for f in files if f.lower()+'_c' in d]
    if not files: print("NOFILES",ev, blk[:300].replace('\n',' ')); continue
    plan[ev]={'files':files[:4],'vol':float(vol.group(1)) if vol else 1.0}
json.dump(plan,open('sndplan.json','w'),indent=1)
arcs=sorted({d[f.lower()+'_c'][0] for p in plan.values() for f in p['files']})
print(len(plan),'events', sum(len(p['files']) for p in plan.values()),'files arcs',arcs)
