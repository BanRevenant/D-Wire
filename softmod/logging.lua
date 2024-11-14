-- logging.lua - Factorio logging module with standardized output patterns

-- Helper function for timestamp format
local function get_formatted_time()
    -- Use game.tick to calculate hours, minutes, seconds
    local total_seconds = game.tick / 60
    local hours = math.floor(total_seconds / 3600)
    local minutes = math.floor((total_seconds % 3600) / 60)
    local seconds = math.floor(total_seconds % 60)
    
    -- Format as HH:MM:SS
    return string.format("%02d:%02d:%02d", hours, minutes, seconds)
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
        game.print(get_formatted_time() .. " [MSG] Research " .. research.name .. " completed.")
    end
end)

-- Mining event
script.on_event(defines.events.on_pre_player_mined_item, function(event)
    if event and event.entity and event.player_index then
        local player = game.players[event.player_index]
        local obj = event.entity
        if obj and obj.valid and player and player.valid then
            local position = obj.position
            game.print(get_formatted_time() .. " [ACT] " .. player.name .. " mined " .. obj.name .. 
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
            game.print(get_formatted_time() .. " [ACT] " .. player.name .. " placed " .. obj.name)
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
            game.print(get_formatted_time() .. " [MSG] " .. player.name .. " was killed by " .. cause.name .. " at [gps=" ..
                      player.position.x .. "," .. player.position.y .. "]")
        else
            game.print(get_formatted_time() .. " [MSG] " .. player.name .. " died at [gps=" ..
                      player.position.x .. "," .. player.position.y .. "]")
        end
    end
end)

-- Chat event
script.on_event(defines.events.on_console_chat, function(event)
    if event.player_index then
        local player = game.players[event.player_index]
        if player and event.message then
            game.print(get_formatted_time() .. " [CHAT] " .. player.name .. ": " .. event.message)
        end
    end
end)

-- logs online players every minute
script.on_event(defines.events.on_tick, function(event)
    if event.tick % (60 * 60) == 0 then  -- Run once per minute (60 ticks/second)
        local players = {}
        for _, player in pairs(game.connected_players) do
            table.insert(players, player.name)
        end
        game.print("[ONLINE2] " .. table.concat(players, ", "))
    end
end)

-- Command logging
function on_console_command(event)
    if event and event.command and event.parameters then
        local command = ""
        local args = ""

        if event.command then
            command = event.command
        end

        if event.parameters then
            args = event.parameters
        end

        if event.player_index then
            local player = game.players[event.player_index]
            print(string.format("[CMD] NAME: %s, COMMAND: %s, ARGS: %s", player.name, command, args))
        elseif command ~= "time" and command ~= "online" and command ~= "server-save" and command ~= "p" then -- Ignore spammy console commands
            print(string.format("[CMD] NAME: CONSOLE, COMMAND: %s, ARGS: %s", command, args))
        end
    end
end

script.on_event(defines.events.on_console_command, on_console_command)