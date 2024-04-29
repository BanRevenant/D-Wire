import os
import re
import discord
from discord.ext import commands, tasks
import geoip2.database
import logging
import time

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

IP_PATTERN = r"from\(IP ADDR:\((\{[0-9.]+:[0-9]+\})\)\)"
JOIN_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[JOIN\] (.+) joined the game"
RESEARCH_PATTERN = r"\[MSG\] Research (.+) completed\."
CHAT_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[CHAT\] (.+): (.+)"
LEAVE_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[LEAVE\] (.+) left the game"
DEATH_PATTERN = r"\[MSG\] (\w+) was killed by (.+) at \[gps"
CONNECTION_REFUSED_PATTERN = r"Refusing connection for address \(IP ADDR:\((\{[0-9.]+:[0-9]+\})\)\), username \((.+)\). UserVerificationMissing"

TIMEOUT_SECONDS = 10  # Time after which an unjoined user's IP address will be removed from the cache

def load_geo_database():
    database_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'GeoLite2-City.mmdb')
    try:
        reader = geoip2.database.Reader(database_path)
        logger.debug(f"GeoLite2 City database loaded successfully from {database_path}")
        return reader
    except Exception as e:
        logger.error(f"Error loading GeoLite2 City database from {database_path}, Error: {str(e)}")
        return None

def get_location_from_ip(ip_address, reader):
    if reader is None:
        return "Unknown", "Unknown"
    try:
        response = reader.city(ip_address.strip('{}').split(':')[0])
        country = response.country.name
        state = response.subdivisions.most_specific.name
        logger.debug(f"IP Address: {ip_address}, Country: {country}, State: {state}")
        return country, state
    except Exception as e:
        logger.error(f"Error getting location for IP Address: {ip_address}, Error: {str(e)}")
        return "Unknown", "Unknown"

class ReadLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_file = "/opt/factorio/factorio-server-console.log"
        self.last_position = self.get_last_position()
        self.geo_reader = load_geo_database()
        self.ip_to_username = {}
        self.ip_timestamps = {}

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
                                country, state = get_location_from_ip(ip_address, self.geo_reader)
                                logger.debug(f"Cached IP Address: {ip_address}, Location: {country}, {state}")
                                self.ip_to_username[ip_address] = (None, country, state)
                                self.ip_timestamps[ip_address] = time.time()

                            connection_refused_match = re.search(CONNECTION_REFUSED_PATTERN, line)
                            if connection_refused_match:
                                ip_address = connection_refused_match.group(1)
                                username = connection_refused_match.group(2)
                                if ip_address in self.ip_to_username:
                                    logger.debug(f"Removing cached IP Address: {ip_address}, Location: {self.ip_to_username[ip_address][1]}, {self.ip_to_username[ip_address][2]} for Username: {username}")
                                    del self.ip_to_username[ip_address]
                                    del self.ip_timestamps[ip_address]

                            join_match = re.search(JOIN_PATTERN, line)
                            if join_match:
                                username = join_match.group(2)
                                ip_address = next((ip for ip, (user, _, _) in self.ip_to_username.items() if user is None), None)
                                if ip_address:
                                    self.ip_to_username[ip_address] = (username, self.ip_to_username[ip_address][1], self.ip_to_username[ip_address][2])
                                    country, state = self.ip_to_username[ip_address][1], self.ip_to_username[ip_address][2]
                                    logger.debug(f"Join Event - Username: {username}, IP Address: {ip_address}, Location: {country}, {state}")
                                    message = f"**{username}** has joined the game from **{state}, {country}**."
                                    await channel.send(message)
                                    del self.ip_timestamps[ip_address]  # Remove the timestamp since the user has joined
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

                        # Remove IP addresses that have timed out
                        current_time = time.time()
                        for ip_address, timestamp in list(self.ip_timestamps.items()):
                            if current_time - timestamp > TIMEOUT_SECONDS:
                                logger.debug(f"Removing timed out IP Address: {ip_address}, Location: {self.ip_to_username[ip_address][1]}, {self.ip_to_username[ip_address][2]}")
                                del self.ip_to_username[ip_address]
                                del self.ip_timestamps[ip_address]

        except FileNotFoundError:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_log.start()

async def setup(bot):
    await bot.add_cog(ReadLogCog(bot))