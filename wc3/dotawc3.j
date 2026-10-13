//===========================================================================
// DotaWC3: Warcraft III side of the Dota 2 x WC3 bridge.
// Every 0.1 s the map writes Documents\Warcraft III\CustomMapData\DotaWC3\out.txt (our hero, hits)
// and reads DotaWC3\in.txt written by bridge_wc3.py (Dota heroes, hook/stun/damage on our hero).
//===========================================================================
function DWC_Tok takes nothing returns string
    local integer st
    loop
        exitwhen udg_dwc_p >= udg_dwc_len
        exitwhen SubString(udg_dwc_s, udg_dwc_p, udg_dwc_p + 1) != " "
        set udg_dwc_p = udg_dwc_p + 1
    endloop
    set st = udg_dwc_p
    loop
        exitwhen udg_dwc_p >= udg_dwc_len
        exitwhen SubString(udg_dwc_s, udg_dwc_p, udg_dwc_p + 1) == " "
        exitwhen SubString(udg_dwc_s, udg_dwc_p, udg_dwc_p + 1) == ";"
        set udg_dwc_p = udg_dwc_p + 1
    endloop
    return SubString(udg_dwc_s, st, udg_dwc_p)
endfunction

function DWC_EndLine takes nothing returns nothing
    loop
        exitwhen udg_dwc_p >= udg_dwc_len
        if SubString(udg_dwc_s, udg_dwc_p, udg_dwc_p + 1) == ";" then
            set udg_dwc_p = udg_dwc_p + 1
            return
        endif
        set udg_dwc_p = udg_dwc_p + 1
    endloop
endfunction

function DWC_Slot takes integer id returns integer
    local integer i = 0
    loop
        exitwhen i >= udg_dwc_n
        if udg_dwc_id[i] == id then
            return i
        endif
        set i = i + 1
    endloop
    set udg_dwc_id[udg_dwc_n] = id
    set udg_dwc_u[udg_dwc_n] = null
    set udg_dwc_n = udg_dwc_n + 1
    return udg_dwc_n - 1
endfunction

function DWC_OnProxyDamaged takes nothing returns nothing
    local unit u = GetTriggerUnit()
    local integer i = 0
    loop
        exitwhen i >= udg_dwc_n
        if udg_dwc_u[i] == u then
            set udg_dwc_hits = udg_dwc_hits + "D " + I2S(udg_dwc_id[i]) + " " + I2S(R2I(GetEventDamage())) + " 0 blademaster;"
            // the real HP lives in Dota: undo the damage here, Dota sends the new HP back
            call SetWidgetLife(u, GetWidgetLife(u) + GetEventDamage())
        endif
        set i = i + 1
    endloop
    set u = null
endfunction

function DWC_Proxy takes integer s, real x, real y returns unit
    if udg_dwc_u[s] == null or GetUnitTypeId(udg_dwc_u[s]) == 0 then
        set udg_dwc_u[s] = CreateUnit(Player(1), 'h000', x, y, 0.0)
        call SetUnitPathing(udg_dwc_u[s], false)
        call TriggerRegisterUnitEvent(udg_dwc_dmg, udg_dwc_u[s], EVENT_UNIT_DAMAGED)
        set udg_dwc_tx[s] = x
        set udg_dwc_ty[s] = y
        set udg_dwc_anim[s] = ""
        call DisplayTextToPlayer(Player(0), 0, 0, "|cffff4040Пудж из Доты появился в Варкрафте|r")
    endif
    return udg_dwc_u[s]
endfunction

function DWC_SetAnim takes integer s, string a returns nothing
    if udg_dwc_anim[s] != a then
        set udg_dwc_anim[s] = a
        call SetUnitAnimation(udg_dwc_u[s], a)
        if a == "walk" or a == "stand" or a == "stand channel" then
            call QueueUnitAnimation(udg_dwc_u[s], a)
        endif
    endif
endfunction

function DWC_ReadLine takes nothing returns nothing
    local string k = DWC_Tok()
    local integer s
    local unit u
    local real x
    local real y
    local real fx
    local real fy
    local real hp
    local real mhp
    local string alive
    local string act
    local lightning l
    if k == "H" then
        set s = DWC_Slot(S2I(DWC_Tok()))
        set x = S2R(DWC_Tok())
        set y = S2R(DWC_Tok())
        set fx = S2R(DWC_Tok())
        set fy = S2R(DWC_Tok())
        set hp = S2R(DWC_Tok())
        set mhp = S2R(DWC_Tok())
        set alive = DWC_Tok()
        set act = DWC_Tok()
        set u = DWC_Proxy(s, x, y)
        if alive == "1" then
            if not UnitAlive(u) then
                call RemoveUnit(u)
                set udg_dwc_u[s] = null
                set u = DWC_Proxy(s, x, y)
            endif
            set udg_dwc_tx[s] = x
            set udg_dwc_ty[s] = y
            set udg_dwc_tf[s] = Atan2(fy, fx) * bj_RADTODEG
            if mhp > 0 then
                call SetUnitState(u, UNIT_STATE_LIFE, RMaxBJ(1.0, GetUnitState(u, UNIT_STATE_MAX_LIFE) * hp / mhp))
            endif
            set udg_dwc_act[s] = act
        elseif UnitAlive(u) then
            call SetUnitAnimation(u, "death")
            call KillUnit(u)
        endif
    elseif k == "T" then
        call DWC_Tok()
        set x = S2R(DWC_Tok())
        set y = S2R(DWC_Tok())
        if udg_dwc_bm != null and UnitAlive(udg_dwc_bm) then
            call SetUnitX(udg_dwc_bm, x)
            call SetUnitY(udg_dwc_bm, y)
        endif
    elseif k == "S" then
        call DWC_Tok()
        set udg_dwc_stun = RMaxBJ(udg_dwc_stun, udg_dwc_time + S2R(DWC_Tok()))
    elseif k == "K" then
        call DWC_Tok()
        set hp = S2R(DWC_Tok())
        set s = S2I(DWC_Tok())
        if s > udg_dwc_lastK and udg_dwc_bm != null and UnitAlive(udg_dwc_bm) then
            set udg_dwc_lastK = s
            if GetWidgetLife(udg_dwc_bm) - hp <= 0.405 then
                call KillUnit(udg_dwc_bm)
            else
                call SetWidgetLife(udg_dwc_bm, GetWidgetLife(udg_dwc_bm) - hp)
            endif
        endif
    elseif k == "V" then
        call DWC_Tok()
        call SetUnitMoveSpeed(udg_dwc_bm, GetUnitDefaultMoveSpeed(udg_dwc_bm) * S2R(DWC_Tok()))
    elseif k == "L" then
        call DWC_Tok()
        set s = DWC_Slot(S2I(DWC_Tok()))
        if udg_dwc_u[s] != null and udg_dwc_bm != null then
            if udg_dwc_chain == null then
                set udg_dwc_chain = AddLightningEx("LEAS", false, GetUnitX(udg_dwc_u[s]), GetUnitY(udg_dwc_u[s]), 120.0, GetUnitX(udg_dwc_bm), GetUnitY(udg_dwc_bm), 80.0)
            else
                call MoveLightningEx(udg_dwc_chain, false, GetUnitX(udg_dwc_u[s]), GetUnitY(udg_dwc_u[s]), 120.0, GetUnitX(udg_dwc_bm), GetUnitY(udg_dwc_bm), 80.0)
            endif
            set udg_dwc_chainEnd = udg_dwc_time + 0.3
        endif
    endif
    call DWC_EndLine()
    set u = null
endfunction

function DWC_Exchange takes nothing returns nothing
    local string tok
    local integer seq
    local real hp
    set udg_dwc_time = udg_dwc_time + 0.1
    // ---- read what the bridge wrote
    call BlzSetAbilityTooltip('AHbz', "", 0)
    call Preloader("DotaWC3\\in.txt")
    set udg_dwc_s = BlzGetAbilityTooltip('AHbz', 0)
    set udg_dwc_len = StringLength(udg_dwc_s)
    set udg_dwc_p = 0
    if udg_dwc_len > 1 then
        set tok = DWC_Tok()
        set seq = S2I(SubString(tok, 1, StringLength(tok)))
        call DWC_EndLine()
        if seq != udg_dwc_seq then
            set udg_dwc_seq = seq
            loop
                exitwhen udg_dwc_p >= udg_dwc_len
                call DWC_ReadLine()
            endloop
        endif
    endif
    // ---- write our hero
    set udg_dwc_out = udg_dwc_out + 1
    call PreloadGenClear()
    call PreloadGenStart()
    call Preload("S " + I2S(udg_dwc_out) + " " + I2S(udg_dwc_lastK))
    if udg_dwc_bm != null and UnitAlive(udg_dwc_bm) then
        set hp = GetWidgetLife(udg_dwc_bm)
        call Preload("P 0 " + R2S(GetUnitX(udg_dwc_bm)) + " " + R2S(GetUnitY(udg_dwc_bm)) + " 0 " + R2S(Cos(GetUnitFacing(udg_dwc_bm) * bj_DEGTORAD)) + " " + R2S(Sin(GetUnitFacing(udg_dwc_bm) * bj_DEGTORAD)) + " 0 " + I2S(R2I(hp)) + " WC3_Blademaster")
    endif
    if udg_dwc_hits != "" then
        call Preload(udg_dwc_hits)
        set udg_dwc_hits = ""
    endif
    call PreloadGenEnd("DotaWC3\\out.txt")
endfunction

function DWC_Smooth takes nothing returns nothing
    local integer i = 0
    local unit u
    local real x
    local real y
    local real d
    loop
        exitwhen i >= udg_dwc_n
        set u = udg_dwc_u[i]
        if u != null and UnitAlive(u) then
            set x = GetUnitX(u)
            set y = GetUnitY(u)
            set d = SquareRoot((udg_dwc_tx[i] - x) * (udg_dwc_tx[i] - x) + (udg_dwc_ty[i] - y) * (udg_dwc_ty[i] - y))
            if d > 600.0 then
                call SetUnitX(u, udg_dwc_tx[i])
                call SetUnitY(u, udg_dwc_ty[i])
            else
                call SetUnitX(u, x + (udg_dwc_tx[i] - x) * 0.35)
                call SetUnitY(u, y + (udg_dwc_ty[i] - y) * 0.35)
            endif
            call SetUnitFacingTimed(u, udg_dwc_tf[i], 0.1)
            if udg_dwc_act[i] == "hook" or udg_dwc_act[i] == "cast" then
                call DWC_SetAnim(i, "spell")
            elseif udg_dwc_act[i] == "ult" then
                call DWC_SetAnim(i, "stand channel")
            elseif udg_dwc_act[i] == "attack" then
                call DWC_SetAnim(i, "attack")
            elseif d > 8.0 then
                call DWC_SetAnim(i, "walk")
            else
                call DWC_SetAnim(i, "stand")
            endif
        endif
        set i = i + 1
    endloop
    // stun from Dota (Dismember, hook)
    if udg_dwc_bm != null then
        if udg_dwc_time < udg_dwc_stun then
            if not udg_dwc_paused then
                call PauseUnit(udg_dwc_bm, true)
                set udg_dwc_paused = true
            endif
        elseif udg_dwc_paused then
            call PauseUnit(udg_dwc_bm, false)
            set udg_dwc_paused = false
        endif
        if not UnitAlive(udg_dwc_bm) and udg_dwc_reviveAt == 0.0 then
            set udg_dwc_reviveAt = udg_dwc_time + 5.0
        endif
        if udg_dwc_reviveAt > 0.0 and udg_dwc_time >= udg_dwc_reviveAt then
            set udg_dwc_reviveAt = 0.0
            call ReviveHero(udg_dwc_bm, GetStartLocationX(0), GetStartLocationY(0), true)
            call SelectUnitForPlayerSingle(udg_dwc_bm, Player(0))
        endif
    endif
    if udg_dwc_chain != null and udg_dwc_time > udg_dwc_chainEnd then
        call DestroyLightning(udg_dwc_chain)
        set udg_dwc_chain = null
    endif
    set u = null
endfunction

function DWC_Init takes nothing returns nothing
    local real x = GetStartLocationX(0)
    local real y = GetStartLocationY(0)
    call FogEnable(false)
    call FogMaskEnable(false)
    call SetPlayerAlliance(Player(1), Player(0), ALLIANCE_PASSIVE, false)
    set udg_dwc_bm = CreateUnit(Player(0), 'Obla', x, y, 0.0)
    call SetHeroLevel(udg_dwc_bm, 6, false)
    call SelectUnitForPlayerSingle(udg_dwc_bm, Player(0))
    call PanCameraToTimed(x, y, 0.0)
    set udg_dwc_dmg = CreateTrigger()
    call TriggerAddAction(udg_dwc_dmg, function DWC_OnProxyDamaged)
    call TimerStart(CreateTimer(), 0.1, true, function DWC_Exchange)
    call TimerStart(CreateTimer(), 0.03, true, function DWC_Smooth)
    call DisplayTextToPlayer(Player(0), 0, 0, "DotaWC3: запусти bridge_wc3.py и Доту. Ты Мастер клинка, в Доте ты тоже Мастер клинка.")
endfunction
