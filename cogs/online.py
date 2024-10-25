import discord
from discord.ext import commands
from discord import app_commands
import re
import asyncio
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/online.log')

ONLINE_PATTERN = r"\[ONLINE2\]"

class OnlineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.last_online_message = ""
        self.readlog_cog = None
        logger.info("OnlineCog initialized")

    def cog_unload(self):
        if self.readlog_cog:
            self.readlog_cog.unsubscribe("ONLINE2", self.process_online)
        logger.info("OnlineCog unloaded")

    async def ensure_readlog_cog(self):
        """Ensure connection to ReadLogCog"""
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            self.readlog_cog = self.bot.get_cog('ReadLogCog')
            if self.readlog_cog:
                self.readlog_cog.subscribe("ONLINE2", self.process_online)
                logger.info("Successfully connected to ReadLogCog.")
                return True
            attempt += 1
            logger.warning(f"ReadLogCog not found (Attempt {attempt}/{max_attempts}). Retrying in 2 seconds...")
            await asyncio.sleep(2)
        
        logger.error("ReadLogCog not found. Online tracking will not work.")
        return False

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_readlog_cog()
        logger.info("OnlineCog is ready.")

    async def process_online(self, line):
        if "[ONLINE2]" in line:
            self.last_online_message = line.strip()
            logger.debug(f"Updated last online message: {self.last_online_message}")

    @app_commands.command(name="online", description="Show currently online players and their stats")
    async def online(self, interaction: discord.Interaction):
        logger.info(f"Online command called by {interaction.user.name}")

        if self.last_online_message:
            player_info = self.parse_player_data(self.last_online_message)
            embed = discord.Embed(title="Online Players", description="Here are the currently online players and their stats:", color=0x00ff00)
            for line in player_info.split('\n'):
                if line:
                    parts = line.split(" - ")
                    username = parts[0].strip()
                    details = " - ".join(parts[1:])
                    embed.add_field(name=f"**{username}**", value=details, inline=False)
            await interaction.response.send_message(embed=embed)
            logger.info("Online players information sent successfully")
        else:
            await interaction.response.send_message("No recent online data available.")
            logger.info("No recent online data available")

    def parse_player_data(self, log_entry):
        try:
            player_data = log_entry.split("[ONLINE2]")[-1].strip()
            player_entries = player_data.split(";")
            response_lines = []
            for entry in player_entries:
                if entry.strip():
                    parts = entry.split(",")
                    if len(parts) < 4:
                        logger.warning(f"Incomplete player data: {entry}")
                        continue  # Skip if there aren't enough data parts to parse
                    username = parts[0]
                    score = parts[1]
                    time_minutes = parts[2]
                    rank = parts[3].strip()
                    hours_played = int(time_minutes) // 60  # Convert minutes to hours
                    afk_time = ""
                    if len(parts) > 4 and parts[4].strip():  # Check if the AFK time is present and not empty
                        afk_time = f", AFK for {parts[4].strip()}"
                    player_info = f"{username} - **Score**: {score}, **Time Played**: {hours_played} hours, **Rank**: {rank}{afk_time}"
                    response_lines.append(player_info)
            return "\n".join(response_lines) if response_lines else "No players online."
        except Exception as e:
            logger.error(f"Error parsing player data: {str(e)}")
            return "Error processing player data."

async def setup(bot):
    await bot.add_cog(OnlineCog(bot))
    logger.info("OnlineCog added to bot")