-- logging.lua - Factorio logging module with standardized output patterns

-- Helper function for timestamp format YYYY-MM-DD HH:MM:SS
local function get_formatted_time()
    -- Convert game.tick to seconds
    local total_seconds = game.tick / 60
    
    -- Get the starting time of the game and add elapsed seconds
    local current_time = os.time() - (game.tick_count / 60) + total_seconds
    
    -- Format as YYYY-MM-DD HH:MM:SS
    return os.date("%Y-%m-%d %H:%M:%S", math.floor(current_time))
end

-- Player disconnect/leave event
script.on_event(defines.events.on_player_left_game, function(event)
    local player = game.players[event.player_index]
    if player then
        game.print(get_formatted_time() .. " [LEAVE] " .. player.name .. " left the game")
    end
end)

-- Research completion
script.on_event(defines.events.on_research_finished, function(event)
    if event and event.research then
        local research = event.research
        game.print("[MSG] Research " .. research.name .. " completed.")
    end
end)

-- Mining event
script.on_event(defines.events.on_pre_player_mined_item, function(event)
    if event and event.entity and event.player_index then
        local player = game.players[event.player_index]
        local obj = event.entity
        if obj and obj.valid and player and player.valid then
            local position = obj.position
            game.print("[ACT] " .. player.name .. " mined " .. obj.name .. 
                      " [gps=" .. position.x .. "," .. position.y .. "]")
        end
    end
end)

-- Building placement
script.on_event(defines.events.on_built_entity, function(event)
    local player = game.players[event.player_index]
    local obj = event.entity
    if player and player.valid and obj and obj.valid then
        if obj.name ~= "entity-ghost" and 
           obj.name ~= "tile-ghost" and 
           obj.name ~= "tile" then
            game.print("[ACT] " .. player.name .. " placed " .. obj.name)
        end
    end
end)

-- Player join event
script.on_event(defines.events.on_player_joined_game, function(event)
    local player = game.players[event.player_index]
    if player then
        game.print(get_formatted_time() .. " [JOIN] " .. player.name .. " joined the game")
    end
end)

-- Player death event
script.on_event(defines.events.on_player_died, function(event)
    local player = game.players[event.player_index]
    local cause = event.cause
    
    if player then
        if cause then
            game.print("[MSG] " .. player.name .. " was killed by " .. cause.name .. " at [gps=" ..
                      player.position.x .. "," .. player.position.y .. "]")
        else
            game.print("[MSG] " .. player.name .. " died at [gps=" ..
                      player.position.x .. "," .. player.position.y .. "]")
        end
    end
end)

-- Chat event (requires additional setup to capture chat)
script.on_event(defines.events.on_console_chat, function(event)
    if event.player_index then
        local player = game.players[event.player_index]
        if player and event.message then
            game.print(get_formatted_time() .. " [CHAT] " .. player.name .. ": " .. event.message)
        end
    end
end)
