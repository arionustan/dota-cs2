-- DotaCS: game modes and "CS or Dota" choice
--
-- Modes (host picks on the hero selection screen):
--   "versus" = Dota vs CS: Radiant plays Dota heroes, Dire plays CS
--   "mixed"  = every player chooses for himself
--
-- A CS player still picks any hero on the pick screen; after spawning
-- the hero is replaced with the CS player.

CS_MODE_DEFAULT = "mixed"

function CDotaCS:InitPick()
    self.mode = CS_MODE_DEFAULT
    self.wantsCS = {}       -- [pid] = true/false (mixed mode)
    self.firstSpawnDone = {}

    CustomGameEventManager:RegisterListener("cs_pick_request", function(_, d) self:SendPickState(d.PlayerID) end)
    CustomGameEventManager:RegisterListener("cs_set_mode", function(_, d) self:OnSetMode(d) end)
    CustomGameEventManager:RegisterListener("cs_set_role", function(_, d) self:OnSetRole(d) end)
end

function CDotaCS:PickLocked()
    return GameRules:State_Get() >= DOTA_GAMERULES_STATE_GAME_IN_PROGRESS
end

function CDotaCS:ShouldBeCS(pid)
    if self.mode == "versus" then
        return PlayerResource:GetTeam(pid) == DOTA_TEAM_BADGUYS
    end
    return self.wantsCS[pid] == true
end

function CDotaCS:BuildPickState()
    local roles = {}
    for pid = 0, DOTA_MAX_TEAM_PLAYERS - 1 do
        if PlayerResource:IsValidPlayerID(pid) then
            roles[tostring(pid)] = self:ShouldBeCS(pid) and 1 or 0
        end
    end
    return { mode = self.mode, roles = roles, locked = self:PickLocked() and 1 or 0 }
end

function CDotaCS:SendPickState(pid)
    local player = pid and PlayerResource:GetPlayer(pid)
    if player then
        CustomGameEventManager:Send_ServerToPlayer(player, "cs_pick_state", self:BuildPickState())
    end
end

function CDotaCS:BroadcastPickState()
    CustomGameEventManager:Send_ServerToAllClients("cs_pick_state", self:BuildPickState())
end

function CDotaCS:OnSetMode(data)
    if self:PickLocked() then return end
    local player = PlayerResource:GetPlayer(data.PlayerID)
    if not player or not GameRules:PlayerHasCustomGameHostPrivileges(player) then return end
    if data.mode ~= "versus" and data.mode ~= "mixed" then return end
    self.mode = data.mode
    self:BroadcastPickState()
end

function CDotaCS:OnSetRole(data)
    if self:PickLocked() or self.mode ~= "mixed" then return end
    self.wantsCS[data.PlayerID] = (data.cs == 1)
    self:BroadcastPickState()
end

-- called from OnNPCSpawned for every real hero
function CDotaCS:CheckFirstSpawn(hero)
    local pid = hero:GetPlayerOwnerID()
    if pid == nil or pid < 0 then return end
    if self.firstSpawnDone[pid] or self.csPlayers[pid] then return end
    self.firstSpawnDone[pid] = true

    if self:ShouldBeCS(pid) then
        -- replace the hero a moment later (not inside the spawn event)
        GameRules:GetGameModeEntity():SetContextThink("cs_make_" .. pid, function()
            self:MakeCSPlayer(pid)
            return nil
        end, 0.1)
    end
end
