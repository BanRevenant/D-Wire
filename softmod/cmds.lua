-- server_chat.lua

-- Function to send a message to all players
local function message_allp(message)
    for _, player in pairs(game.connected_players) do
        player.print(message)
    end
end

-- Function to send a message to a specific player
local function smart_print(player, message)
    if player and player.valid then
        player.print(message)
    else
        log("Attempted to send a message to an invalid or disconnected player.")
    end
end

-- Function to update the player list (dummy implementation to prevent crashes)
local function update_player_list()
    log("Player list updated (placeholder function).")
end

-- Function to show the list of players to a specific player
local function show_players(player)
    if player and player.valid then
        local online_players = {}
        for _, p in pairs(game.connected_players) do
            table.insert(online_players, p.name)
        end
        player.print("Online players: " .. (next(online_players) and table.concat(online_players, ", ") or "No players online"))
    else
        log("Attempted to show online players to an invalid or disconnected player.")
    end
end

-- Add a custom command for server use only (chat)
commands.add_command("cchat", "Server use only - Sends a message to all players.", function(param)
    -- Restrict usage to non-players (e.g., server/RCON)
    if param and param.player_index then
        local player = game.players[param.player_index]
        smart_print(player, "This command is for system use only.")
        return
    end

    -- Send the message to all players if a parameter is provided
    if param.parameter then
        message_allp(param.parameter)
    else
        log("cchat command invoked without a parameter.")
    end
end)

-- Add a custom command to see who is online
commands.add_command("online", "See who is online", function(param)
    local victim

    -- Check if the command is invoked by a player
    if param and param.player_index then
        victim = game.players[param.player_index]
    end

    -- Update the player list
    update_player_list()

    -- Show the list of players to the player who invoked the command
    if victim then
        show_players(victim)
    end
end)
