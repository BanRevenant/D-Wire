-- register.lua - Simple registration command handler for Factorio

-- registration.lua
local function smart_print(player, message)
    if player then
        player.print(message)
    else
        game.print(message)
    end
end

commands.add_command("register", "<code> (Requires a registration code from discord)", function(param)
    if param and param.player_index then
        local player = game.players[param.player_index]

        if param.parameter and player and player.valid then
            print("[ACCESS] " .. player.name .. " " .. param.parameter)
            smart_print(player, "Sending registration code...")
            return
        end
        smart_print(player, "You need to provide a registration code!")
        return
    end
    smart_print(nil, "I don't think the console needs to use this command...")
end)

script.on_init(register_command)
script.on_load(register_command)