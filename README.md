# D-Wire Factorio Server Manager Discord Bot

### A tool for managing a Factorio server without the need of any other software or tools.
This discord bot enables the ability to manage your factorio server directly from your discord channel of choice while giving some many other desired features. The only thing required during the setup process is a discord token. Everything else is processed in discord.

# Quick Start
### Download the script
curl -O https://raw.githubusercontent.com/BanRevenant/D-Wire/master/deploy_bot.sh
### Make the script executable and run it
chmod +x deploy_bot.sh && ./deploy_bot.sh

### Invite the bot to your discord.
https://discord.com/oauth2/authorize?client_id=[APPLICATION-ID]&permissions=8&scope=bot 

8 = Administration (At the momement this is not fully utiliized later it will be required as the bot will handle player bans, user nicknames, creating events etc)


## Features
* Allows control of the Factorio Server, starting and stopping the Factorio binary.
* Allows the management of save files, upload, download and delete saves.
* Manage installed mods Download, Enable, Disable, Remove.
* Allow viewing of the server logs and current configuration.
* Manage important settings of the server inside of discord. No need for manual file edits.
* Shows online players by changing the status of the bot itself, DND for server running, Idle for server offline.
* (in development) Manages and Tracks users stats for killing biters
* Send chat between the discord server and the factorio server
* (in development)(working) registration system which allows you to bind discord accounts to factorio accounts.
* Server status command which shows important server information
* Country tracking of players joining the server
* Ability to create your own cogs, manage them by enable, disable, upload and remove them. Allows for a simple way to manage features provided by D-Wire


## Development
All of the above features work entirely, any in development features will probably cause you issues. Recommend disabling cogs that are in development. If you have any questions on functionality or want to see the discord bot in action hit up our discord. I usually respond within the hour.

## Authors
* BanRevenant - Discord : revenantplays
https://discord.gg/EwESfeyEs8
