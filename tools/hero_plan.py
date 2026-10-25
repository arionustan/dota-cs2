H={
 'axe':('axe',['axe','axe_armor','axe_belt','axe_hair','axe_ponytail','axe_weapon']),
 'juggernaut':('juggernaut',['juggernaut','jugg_bracers','jugg_cape','jugg_mask','jugg_sword','juggernaut_pants']),
 'sniper':('sniper',['sniper','bracer','cape','headitem','shoulder','weapon']),
 'crystal_maiden':('crystal_maiden',['crystal_maiden','crystal_maiden_cape','crystal_maiden_cuffs','crystal_maiden_shoulders','crystal_maiden_staff']),
 'lina':('lina',['lina','lina_arms','lina_belt','lina_head','lina_neck']),
 'phantom_assassin':('phantom_assassin',['phantom_assassin','phantom_assassin_cape','phantom_assassin_helmet','phantom_assassin_shoulders','phantom_assassin_weapon']),
 'nevermore':('shadow_fiend',['shadow_fiend']),
 'drow_ranger':('drow',['drow_base','drow_armor','drow_bracer','drow_cape','drow_haircowl','drow_legs','drow_quiver','drow_weapon']),
 'earthshaker':('earthshaker',['earthshaker','belt','bracers','totem']),
 'zuus':('zeus',['zeus','zeus_belt','zeus_bracers','zeus_hair','zeus_vest']),
 'lion':('lion',['lion','lion_cape','lion_demonarm','lion_hat','lion_shoulder','lion_weapon']),
 'invoker':('invoker',['invoker','invoker_bracer','invoker_cape','invoker_dress','invoker_hair','invoker_head','invoker_shoulder']),
 'slark':('slark',['slark','bracer','cape','hood','shoulder','weapon']),
 'windrunner':('windrunner',['windrunner','windrunner_bow','windrunner_cape','windrunner_head','windrunner_quiver','windrunner_shoulderpads']),
 'sven':('sven',['sven','sven_belt','sven_gauntlet','sven_mask','sven_shoulder','sven_sword']),
 'legion_commander':('legion_commander',['legion_commander','legion_commander_arms','legion_commander_back','legion_commander_head','legion_commander_shoulders','legion_commander_weapon']),
 'faceless_void':('faceless_void',['faceless_void','faceless_void_belt','faceless_void_bracer','faceless_void_head','faceless_void_shoulder','faceless_void_weapon']),
 'antimage':('antimage',['antimage','antimage_arms','antimage_belt','antimage_chest','antimage_head','antimage_offhand_weapon','antimage_weapon']),
 'queenofpain':('queenofpain',['queenofpain','hair','queenofpain_legs','shoulders','wings','queenofpain_weapon']),
}
def vmdls(h):
    d,parts=H[h]; return ['models/heroes/%s/%s.vmdl'%(d,p) for p in parts]
