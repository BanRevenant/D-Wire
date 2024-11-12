-- https://lua-api.factorio.com/latest/events.html#on_player_died
local function player_died(event)
    local player = game.players[event.player_index]
    
    -- Handle case where there's no cause
    if not event.cause then
        print("[STATS-D3] [" .. player.name .. "] died from unknown cause")
        return
    end
    
    -- Handle case where cause exists but force might not
    local force_name = "unknown"
    if event.cause.force then
        force_name = event.cause.force.name
    end
    
    -- Check if killed by player
    if event.cause.is_player and event.cause.is_player() then
        print("[STATS-D1] [" .. player.name .. "] killed by player [" .. event.cause.player.name .. "] force [" .. force_name .. "]")
        return
    end

    print("[STATS-D2] [" .. player.name .. "] killed by [" .. event.cause.name .. "] force [" .. force_name .. "]")
end

local function get_weapon_name(player)
    if player and player.character then
        local character_guns = player.character.get_inventory(defines.inventory.character_guns)
        if character_guns then
            local weapon = character_guns[player.character.selected_gun_index]
            if weapon and weapon.valid_for_read then
                return weapon.name
            end
        end
    end
    return "unknown"
end

-- https://lua-api.factorio.com/latest/events.html#on_entity_died
local function entity_died(event)
    if not event.cause then
        return
    end

    local player
    if event.cause.type == "character" then
        player = event.cause.player
        if player then
            local weapon_name = get_weapon_name(player)
            print("[STATS-E1] [" .. player.name .. "] killed [" .. event.entity.name .. "] with [" .. weapon_name .. "]")
        end

    elseif event.cause.name and event.entity and event.entity.name and event.entity.name ~= "character" then
        print("[STATS-E2] [" .. event.cause.name .. "] killed [" .. event.entity.name .. "]")
    end
end

local stats = {}
stats.events = {
    [defines.events.on_entity_died] = entity_died,
    [defines.events.on_player_died] = player_died,
}
return stats