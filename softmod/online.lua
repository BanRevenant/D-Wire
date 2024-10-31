-- online.lua - Track and report online players

-- Use local storage for the scenario level
local storage = {
    player_list = {},
    player_count = 0,
    lastonlinestring = ""
}

-- Function to update and show online players
local function update_player_list()
    local buf = "[ONLINE2] "
    local count = 0
    
    for i, target in pairs(storage.player_list) do
        if target and target.victim and target.victim.connected then
            buf = buf .. target.victim.name .. "," .. 
                  math.floor(target.score / 60 / 60) .. "," ..
                  math.floor(target.time / 60 / 60) .. "," .. 
                  target.type .. "," .. target.afk .. ";"
        end
    end
    
    -- Don't send unless there is a change
    if storage.lastonlinestring ~= buf then
        storage.lastonlinestring = buf
        print(buf)
    end
end

-- Update player list when someone joins
script.on_event(defines.events.on_player_joined_game, function(event)
    local player = game.players[event.player_index]
    if player and player.valid then
        if not storage.player_list[event.player_index] then
            storage.player_list[event.player_index] = {
                victim = player,
                score = 0,
                time = 0,
                type = "player",
                afk = ""
            }
        end
        storage.player_count = storage.player_count + 1
        update_player_list()
    end
end)

-- Update when someone leaves
script.on_event(defines.events.on_player_left_game, function(event)
    if storage.player_count > 0 then
        storage.player_count = storage.player_count - 1
    end
    update_player_list()
end)

-- Periodic update for time and AFK status
script.on_nth_tick(3600, function(event)
    for i, target in pairs(storage.player_list) do
        if target and target.victim and target.victim.connected then
            target.time = target.time + 60 -- Add one minute
            -- Update AFK status
            if target.victim.afk_time and target.victim.afk_time > 300 then
                target.afk = "AFK"
            else
                target.afk = ""
            end
        end
    end
    update_player_list()
end)

-- Return an empty table to make require() happy
return {}