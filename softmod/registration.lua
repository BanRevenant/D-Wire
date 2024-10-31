-- register.lua - Simple registration command handler for Factorio

-- Helper function for printing messages
local function smart_print(player, message)
    if player then
        player.print(message)
    else
        game.print(message)
    end
end

-- Register the command when the script loads
script.on_init(function()
    commands.add_command("register", "<code> (Requires a 6-digit registration code)", 
    function(param)
        -- Check if command is from a player
        if param and param.player_index then
            local player = game.players[param.player_index]
            
            -- Verify player and parameter exist
            if param.parameter and player and player.valid then
                -- Verify the parameter is a 6-digit number
                if string.match(param.parameter, "^%d%d%d%d%d%d$") then
                    -- Send registration attempt to console in the exact format needed
                    game.print("[CMD] NAME: " .. player.name .. ", COMMAND: register, ARGS: " .. param.parameter)
                    smart_print(player, "Sending registration code...")
                    return
                else
                    smart_print(player, "Please provide a valid 6-digit registration code!")
                    return
                end
            end
            
            smart_print(player, "You need to provide a registration code!")
            return
        end
        
        smart_print(nil, "I don't think the console needs to use this command...")
    end)
end)

-- Ensure command is registered when loading a save
script.on_load(function()
    commands.add_command("register", "<code> (Requires a 6-digit registration code)", 
    function(param)
        if param and param.player_index then
            local player = game.players[param.player_index]
            
            if param.parameter and player and player.valid then
                if string.match(param.parameter, "^%d%d%d%d%d%d$") then
                    game.print("[CMD] NAME: " .. player.name .. ", COMMAND: register, ARGS: " .. param.parameter)
                    smart_print(player, "Sending registration code...")
                    return
                else
                    smart_print(player, "Please provide a valid 6-digit registration code!")
                    return
                end
            end
            
            smart_print(player, "You need to provide a registration code!")
            return
        end
        
        smart_print(nil, "I don't think the console needs to use this command...")
    end)
end)