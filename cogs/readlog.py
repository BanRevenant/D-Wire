import os
import re
import discord
from discord.ext import commands, tasks
from discord import app_commands
import geoip2.database
import logging
import traceback
import time
import json
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/readlog.log')

# Debug flags - can be controlled via config.json
DEBUG_CONFIG = {
    'debug_stats': True,      # For stats processing
    'debug_commands': True,   # For command processing
    'debug_chat': False,      # For chat messages
    'debug_connections': False # For player connections/disconnections
}

def debug_log(category, message):
    """Centralized debug logging with category control"""
    if DEBUG_CONFIG.get(category, False):
        logger.debug(f"[{category.upper()}] {message}")

def load_geo_database(config_manager):
    database_path = config_manager.get('geo_database_path', 'GeoLite2-City.mmdb')
    try:
        reader = geoip2.database.Reader(database_path)
        logger.info(f"GeoLite2 City database loaded successfully from {database_path}")
        return reader
    except Exception as e:
        logger.error(f"Error loading GeoLite2 City database from {database_path}, Error: {str(e)}")
        return None

def get_location_from_ip(ip_address, reader):
    if reader is None:
        return "Unknown", "Unknown"
    try:
        clean_ip = ip_address.strip('{}').split(':')[0]
        response = reader.city(clean_ip)
        country = response.country.name or "Unknown"
        state = response.subdivisions.most_specific.name if response.subdivisions else "Unknown"
        debug_log('connections', f"IP Address: {clean_ip}, Country: {country}, State: {state}")
        return country, state
    except Exception as e:
        logger.error(f"Error getting location for IP Address: {ip_address}, Error: {str(e)}")
        return "Unknown", "Unknown"

# Pattern definitions
IP_PATTERN = r"from\(IP ADDR:\((\{[0-9.]+:[0-9]+\})\)\)"
JOIN_PATTERNS = [
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[JOIN\] (.+) joined the game",
    r"Player (.+) joined the game",
    r"(.+) has joined the game"
]
RESEARCH_PATTERN = r"\[MSG\] Research (.+) completed\."
CHAT_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[CHAT\] (.+): (.+)"
LEAVE_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[LEAVE\] (.+) left the game"
DEATH_PATTERN = r"\[MSG\] (\w+) was killed by (.+) at \[gps"
CONNECTION_REFUSED_PATTERN = r"Refusing connection for address \(IP ADDR:\((\{[0-9.]+:[0-9]+\})\)\), username \((.+)\). UserVerificationMissing"
GPS_PATTERN = r"\[gps=[-+]?\d*\.\d+,[-+]?\d*\.\d+\]"
COMMAND_PATTERN = r"\[CMD\] NAME: ([^,]+), COMMAND: ([^,]+), ARGS: (.+)"
STATS_KILL_PATTERN = r"\[STATS-E1\] \[([^]]+)\] ([^[]+) \[([^]]+)\] with \[([^]]+)\]"
STATS_DEATH_PATTERN = r"\[STATS-D2\] \[([^]]+)\] killed by \[([^]]+)\] force \[enemy\]"
STATS_PLACE_PATTERN = r"\[ACT\] ([^[\]]+) placed"
ONLINE_PATTERN = r"\[ONLINE2\] (.*)"

TIMEOUT_SECONDS = 30

class ReadLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.log_file = self.config_manager.get('factorio_server.server_log_file')
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.position_file = os.path.join(self.parent_dir, "last_position.txt")
        self.location_prefs_file = os.path.join(self.parent_dir, "location_prefs.json")
        
        # Ensure location_prefs.json exists
        if not os.path.exists(self.location_prefs_file):
            try:
                with open(self.location_prefs_file, 'w') as f:
                    json.dump({}, f)
                logger.info(f"Created new location preferences file: {self.location_prefs_file}")
            except Exception as e:
                logger.error(f"Error creating location preferences file: {str(e)}")
        
        try:
            with open(self.position_file, 'r') as f:
                self.last_position = int(f.read().strip())
        except:
            self.last_position = 0
            
        self.geo_reader = load_geo_database(self.config_manager)
        self.ip_to_username = {}
        self.ip_timestamps = {}
        self.connected_players = set()
        self.location_preferences = self.load_location_preferences()
        self.message_subscribers = {
            "CHAT": set(),
            "CHAT_STATS": set(),
            "JOIN": set(),
            "LEAVE": set(),
            "CMD": set(),
            "ONLINE2": set(),
            "STATS-E1": set(),
            "STATS-D2": set(),
            "ACT": set()
        }
        
        if self.config_manager.get('debug_mode', False):
            DEBUG_CONFIG.update({
                'debug_stats': True,
                'debug_commands': True,
                'debug_chat': True,
                'debug_connections': True
            })
        
        logger.info("ReadLogCog initialized")

    def load_location_preferences(self):
        """Load location display preferences from JSON file"""
        try:
            with open(self.location_prefs_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading location preferences: {str(e)}")
            return {}

    def save_location_preferences(self):
        """Save location display preferences to JSON file"""
        try:
            with open(self.location_prefs_file, 'w') as f:
                json.dump(self.location_preferences, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving location preferences: {str(e)}")

    def get_factorio_username(self, discord_id):
        """Get Factorio username from registrations file"""
        registrations_file = os.path.join(self.parent_dir, "registrations.json")
        try:
            with open(registrations_file, 'r') as f:
                registrations = json.load(f)
                return registrations.get(str(discord_id))
        except Exception as e:
            logger.error(f"Error reading registrations file: {str(e)}")
            return None

    @app_commands.command(name="disablelocation", description="Enable or disable location display when joining the server")
    @app_commands.describe(
        setting="Choose whether to show or hide your location"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable")
    ])
    async def disablelocation(self, interaction: discord.Interaction, setting: app_commands.Choice[str]):
        # Check if user is registered
        factorio_username = self.get_factorio_username(interaction.user.id)
        if not factorio_username:
            await interaction.response.send_message(
                "You must be registered on the Factorio server to use this command. "
                "Please use `/register` first.", 
                ephemeral=True
            )
            return

        # Update preference
        self.location_preferences[str(interaction.user.id)] = {
            "show_location": setting.value == "enable",
            "factorio_username": factorio_username
        }
        self.save_location_preferences()

        status = "enabled" if setting.value == "enable" else "disabled"
        await interaction.response.send_message(
            f"Location display has been {status}. This will take effect the next time you join the server.",
            ephemeral=True
        )
        logger.info(f"Updated location preference for user {interaction.user.id} ({factorio_username}): {status}")

    def subscribe(self, message_type, callback):
        if message_type in self.message_subscribers:
            self.message_subscribers[message_type].add(callback)
            logger.info(f"Added subscriber for {message_type} messages: {callback.__qualname__}")
        else:
            logger.warning(f"Attempted to subscribe to unknown message type: {message_type}")

    def unsubscribe(self, message_type, callback):
        if message_type in self.message_subscribers:
            self.message_subscribers[message_type].discard(callback)
            logger.info(f"Removed subscriber for {message_type} messages: {callback.__qualname__}")
        else:
            logger.warning(f"Attempted to unsubscribe from unknown message type: {message_type}")

    async def notify_subscribers(self, message_type, line):
        if message_type in self.message_subscribers:
            for callback in self.message_subscribers[message_type]:
                try:
                    debug_log('debug_stats' if 'STATS' in message_type else 'debug_commands', 
                             f"Notifying subscriber {callback.__qualname__} for {message_type}")
                    await callback(line)
                except Exception as e:
                    logger.error(f"Error in subscriber callback {callback.__qualname__}: {str(e)}")
                    logger.error(traceback.format_exc())

    def get_last_position(self):
        """Get the last read position from the position file"""
        try:
            with open(self.position_file, "r") as file:
                return int(file.read().strip())
        except FileNotFoundError:
            logger.error(f"Position file not found: {self.position_file}")
            return 0
        except Exception as e:
            logger.error(f"Error reading position file: {str(e)}")
            return 0

    def cog_unload(self):
        try:
            with open(self.position_file, 'w') as f:
                f.write(str(self.last_position))
        except Exception as e:
            logger.error(f"Error saving last position during unload: {str(e)}")
        self.check_log.cancel()
        logger.info("ReadLogCog unloaded")

    @tasks.loop(seconds=1)
    async def check_log(self):
        try:
            if not os.path.exists(self.log_file):
                logger.warning(f"Log file does not exist: {self.log_file}")
                return

            if os.path.getsize(self.log_file) < self.last_position:
                logger.info("Log file has been reset. Starting from the beginning.")
                self.last_position = 0

            with open(self.log_file, "r") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                try:
                    with open(self.position_file, 'w') as f:
                        f.write(str(self.last_position))
                except Exception as e:
                    logger.error(f"Error saving last position: {str(e)}")

                if new_lines:
                    channel_id = self.config_manager.get('discord.channel_id')
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        for line in new_lines:
                            try:
                                await self.process_log_line(line, channel)
                            except Exception as e:
                                logger.error(f"Error processing log line: {line}, Error: {str(e)}")
                                logger.error(traceback.format_exc())

                        # Clean up old IP addresses
                        current_time = time.time()
                        for ip_address, timestamp in list(self.ip_timestamps.items()):
                            if current_time - timestamp > TIMEOUT_SECONDS:
                                if ip_address in self.ip_to_username:
                                    debug_log('connections', f"Removing timed out IP Address: {ip_address}")
                                    del self.ip_to_username[ip_address]
                                if ip_address in self.ip_timestamps:
                                    del self.ip_timestamps[ip_address]

        except FileNotFoundError:
            logger.error(f"Log file not found: {self.log_file}")
        except Exception as e:
            logger.error(f"Error checking log file: {str(e)}")
            logger.error(traceback.format_exc())

    async def process_log_line(self, line, channel):
        try:
            # Match the chat pattern and detect if it's the !statsme command
            chat_match = re.search(CHAT_PATTERN, line)
            if chat_match:
                timestamp, username, message = chat_match.groups()
                if message.strip() == '!statsme':
                    player_name = username
                    logger.info(f"Processing !statsme command for player: {player_name}")
                    await self.notify_subscribers("CHAT_STATS", line)
                    return

            # Existing chat handling code
            if chat_match and not any(pattern in chat_match.group(3) for pattern in ['!statsme', '/register']):
                # Only skip sending to Discord if it contains GPS coordinates
                if "[gps" not in chat_match.group(3):
                    message = f"**{chat_match.group(2)}** says: {chat_match.group(3)}"
                    await channel.send(message)
                else:
                    debug_log('debug_chat', f"Skipping GPS message for Discord: {chat_match.group(3)}")
                
                # Still notify chat subscribers regardless of GPS content
                await self.notify_subscribers("CHAT", line)
                debug_log('debug_chat', f"Chat Message - {chat_match.group(2)}: {chat_match.group(3)}")

            ip_match = re.search(IP_PATTERN, line)
            if ip_match:
                ip_address = ip_match.group(1)
                country, state = get_location_from_ip(ip_address, self.geo_reader)
                debug_log('connections', f"Cached IP Address: {ip_address}, Location: {country}, {state}")
                self.ip_to_username[ip_address] = (None, country, state)
                self.ip_timestamps[ip_address] = time.time()

            connection_refused_match = re.search(CONNECTION_REFUSED_PATTERN, line)
            if connection_refused_match:
                ip_address = connection_refused_match.group(1)
                username = connection_refused_match.group(2)
                if ip_address in self.ip_to_username:
                    debug_log('connections', f"Removing cached IP Address: {ip_address} for Username: {username}")
                    del self.ip_to_username[ip_address]
                    del self.ip_timestamps[ip_address]

            for pattern in JOIN_PATTERNS:
                join_match = re.search(pattern, line)
                if join_match:
                    username = join_match.group(2) if len(join_match.groups()) > 1 else join_match.group(1)
                    if username not in self.connected_players:
                        self.connected_players.add(username)
                        ip_address = next((ip for ip, (user, _, _) in self.ip_to_username.items() if user is None), None)

                        # Check user's location display preference
                        show_location = True
                        for user_id, prefs in self.location_preferences.items():
                            if prefs.get('factorio_username') == username:
                                show_location = prefs.get('show_location', True)
                                break

                        if ip_address:
                            self.ip_to_username[ip_address] = (username, self.ip_to_username[ip_address][1], self.ip_to_username[ip_address][2])
                            
                            if show_location:
                                country, state = self.ip_to_username[ip_address][1], self.ip_to_username[ip_address][2]
                                message = f"**{username}** has joined the game from **{state}, {country}**."
                            else:
                                message = f"**{username}** has joined the game. (Location Hidden)"
                        else:
                            message = f"**{username}** has joined the game."
                        
                        await channel.send(message)
                        await self.notify_subscribers("JOIN", line)
                        debug_log('connections', f"Join Event - Username: {username}, IP Address: {ip_address if ip_address else 'Not Found'}")
                        break

            research_match = re.search(RESEARCH_PATTERN, line)
            leave_match = re.search(LEAVE_PATTERN, line)
            death_match = re.search(DEATH_PATTERN, line)

            if research_match:
                message = f"**Research Completed:** {research_match.group(1)}"
                await channel.send(message)
                logger.info(f"Research Completed: {research_match.group(1)}")
            elif leave_match:
                username = leave_match.group(2)
                if username in self.connected_players:
                    self.connected_players.remove(username)
                message = f"**{username}** left the game."
                await channel.send(message)
                await self.notify_subscribers("LEAVE", line)
                debug_log('connections', f"Leave Event - Username: {username}")
            elif death_match:
                message = f"**{death_match.group(1)}** was killed by {death_match.group(2)}"
                await channel.send(message)
                logger.info(f"Death Event - {death_match.group(1)} killed by {death_match.group(2)}")

            # Process other event patterns
            if "[STATS-E1]" in line:
                debug_log('debug_stats', f"Found STATS-E1 message: {line.strip()}")
                await self.notify_subscribers("STATS-E1", line)
                return
            
            if "[STATS-D2]" in line:
                debug_log('debug_stats', f"Found STATS-D2 message: {line.strip()}")
                await self.notify_subscribers("STATS-D2", line)
                return

            if "[ACT]" in line and "placed" in line:
                debug_log('debug_stats', f"Found placement message: {line.strip()}")
                await self.notify_subscribers("ACT", line)
                return

            if "[ONLINE2]" in line:
                debug_log('debug_stats', f"Found ONLINE2 message: {line.strip()}")
                await self.notify_subscribers("ONLINE2", line)
                return

            # Process command messages
            command_match = re.search(COMMAND_PATTERN, line)
            if command_match:
                debug_log('debug_commands', f"Found command message: {line.strip()}")
                await self.notify_subscribers("CMD", line)
                return

        except Exception as e:
            logger.error(f"Error in process_log_line: {str(e)}")
            logger.error(traceback.format_exc())

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_log.is_running():
            self.check_log.start()
            logger.info("ReadLogCog is ready and log checking has started")
        else:
            logger.info("ReadLogCog log checking was already running")

async def setup(bot):
    await bot.add_cog(ReadLogCog(bot))
    logger.info("ReadLogCog added to bot")