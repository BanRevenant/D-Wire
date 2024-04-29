import os
import re
import discord
from discord.ext import commands, tasks
from geoip2.database import Reader
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

IP_PATTERN = r"from\(IP ADDR:\((\{[0-9.]+:[0-9]+\})\)\)"
JOIN_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[JOIN\] (.+) joined the game"
RESEARCH_PATTERN = r"\[MSG\] Research (.+) completed\."
CHAT_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[CHAT\] (.+): (.+)"
LEAVE_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[LEAVE\] (.+) left the game"
DEATH_PATTERN = r"\[MSG\] (\w+) was killed by (.+) at \[gps"

def load_geo_database():
    database_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'GeoLite2-Country.mmdb')
    try:
        reader = Reader(database_path)
        logger.debug(f"GeoLite2 Country database loaded successfully from {database_path}")
        return reader
    except Exception as e:
        logger.error(f"Error loading GeoLite2 Country database from {database_path}, Error: {str(e)}")
        return None

def get_location_from_ip(ip_address, reader):
    if reader is None:
        return "Unknown"
    try:
        response = reader.country(ip_address.strip('{}').split(':')[0])
        logger.debug(f"IP Address: {ip_address}, Country: {response.country.name}")
        return response.country.name
    except Exception as e:
        logger.error(f"Error getting location for IP Address: {ip_address}, Error: {str(e)}")
        return "Unknown"

class ReadLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_file = "/opt/factorio/factorio-server-console.log"
        self.last_position = self.get_last_position()
        self.geo_reader = load_geo_database()
        self.ip_to_username = {}

    def cog_unload(self):
        self.check_log.cancel()

    def get_last_position(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(0, os.SEEK_END)
                last_position = file.tell()
                return last_position
        except FileNotFoundError:
            return 0

    @tasks.loop(seconds=1)
    async def check_log(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                if new_lines:
                    channel_id = self.bot.config['discord']['channel_id']
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        for line in new_lines:
                            ip_match = re.search(IP_PATTERN, line)
                            if ip_match:
                                ip_address = ip_match.group(1)
                                location = get_location_from_ip(ip_address, self.geo_reader)
                                logger.debug(f"Cached IP Address: {ip_address}, Location: {location}")
                                self.ip_to_username[ip_address] = (None, location)

                            join_match = re.search(JOIN_PATTERN, line)
                            if join_match:
                                username = join_match.group(2)
                                ip_address = next((ip for ip, (user, _) in self.ip_to_username.items() if user is None), None)
                                if ip_address:
                                    self.ip_to_username[ip_address] = (username, self.ip_to_username[ip_address][1])
                                    location = self.ip_to_username[ip_address][1]
                                    logger.debug(f"Join Event - Username: {username}, IP Address: {ip_address}, Location: {location}")
                                    message = f"**{username}** has joined the game from the **{location}**."
                                    await channel.send(message)
                                else:
                                    logger.debug(f"Join Event - Username: {username}, IP Address: Not Found")
                                    message = f"**{username}** has joined the game."
                                    await channel.send(message)

                            research_match = re.search(RESEARCH_PATTERN, line)
                            chat_match = re.search(CHAT_PATTERN, line)
                            leave_match = re.search(LEAVE_PATTERN, line)
                            death_match = re.search(DEATH_PATTERN, line)

                            if research_match:
                                message = f"**Research Completed:** {research_match.group(1)}"
                                await channel.send(message)
                            elif chat_match:
                                message = f"**{chat_match.group(2)}** says: {chat_match.group(3)}"
                                await channel.send(message)
                            elif leave_match:
                                message = f"**{leave_match.group(2)}** left the game."
                                await channel.send(message)
                            elif death_match:
                                message = f"**{death_match.group(1)}** was killed by {death_match.group(2)}"
                                await channel.send(message)

        except FileNotFoundError:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_log.start()

async def setup(bot):
    await bot.add_cog(ReadLogCog(bot))