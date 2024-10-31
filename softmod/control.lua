require "logging" -- logging required for log reading in D-Wire
require "online" -- player logging
require "registration" -- provides required command to allow registration ingame

local fw_stats = require("fw_stats")

-- Register events directly without conditions
script.on_event(defines.events.on_entity_died, fw_stats.events[defines.events.on_entity_died])
script.on_event(defines.events.on_player_died, fw_stats.events[defines.events.on_player_died])
