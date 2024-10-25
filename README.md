# D-Wire Factorio Server Manager Discord Bot

### Updated and ready for Space Age DLC!

### A tool for managing a Factorio server without the need of any other software or tools.
This discord bot enables the ability to manage your factorio server directly from your discord channel of choice while giving some many other desired features. The only thing required during the setup process is a discord token. Everything else is processed in discord.

### Invite the bot to your discord.
https://discord.com/oauth2/authorize?client_id=[APPLICATION-ID]&permissions=8&scope=bot 

8 = Administration (At the momement this is not fully utiliized later it will be required as the bot will handle player bans, user nicknames, creating events etc)

## Features
* Allows control of the Factorio Server, starting and stopping the Factorio binary along with some parameters.
* Allows the management of save files, upload, download and delete saves. (Downloads limited by discord 8MB)
* Manage installed mods Download, Enable, Disable, Remove.
* Allow viewing of the server logs and current configuration.
* Manage important settings of the server inside of discord. No need for manual file edits.
* Shows online players by changing the status of the bot itself, DND for server running, Idle for server offline.
* Manages and Tracks users stats for killing biters.
* Send chat between the discord server and the factorio server.
* Registration system which allows you to bind discord accounts to factorio accounts.
* Server status command which shows important server information.
* Country tracking of players joining the server.
* Ability to create your own cogs, manage them by enable, disable, upload and remove them. Allows for a simple way to manage features provided by D-Wire.
* Automatically augment a new save-game file with softmod code to provide massive amounts of new factorio utility.
* Ban, Kick, Mute players.
* Change player spawn locations on the map.
* Enable and disable cheats with auto researching.
* A self management system which enables and disables local features.
* Recharting game map while server is running.
* Outputs server status , pids, base versions, on command.
* Upload server log files directly to discord.

## Known Issues and improvements.
* Registration code expiration is currently handled inappropriately.
* Better way to handle file uploads that are larger than 8mb.
* Save game creator.
* Not all of the FW Softcode is created yet.
* If a cog itself has a traceback that prevents its operation its not output by the bot error handler.

## Development
All of the above features work entirely, any in development features will probably cause you issues. Recommend disabling cogs that are in development. If you have any questions on functionality or want to see the discord bot in action hit up our discord. I usually respond within the hour.

## Authors
* BanRevenant - Discord : revenantplays
https://discord.gg/EwESfeyEs8
