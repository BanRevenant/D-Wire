import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import datetime
import re
from logger import setup_logger

logger = setup_logger(__name__, 'logs/lastseen.log')

class LastSeenCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.last_seen_file = os.path.join(self.parent_dir, "last_seen.json")
        self.load_registrations()
        self.load_last_seen()
        self.readlog_cog = None

    def load_registrations(self):
        try:
            with open(self.registrations_file, "r") as file:
                self.registrations = json.load(file)
            logger.info("Registrations loaded successfully.")
        except Exception as e:
            self.registrations = {}
            logger.error(f"Error loading registrations: {str(e)}")

    def load_last_seen(self):
        try:
            if os.path.exists(self.last_seen_file):
                with open(self.last_seen_file, "r") as file:
                    self.last_seen_data = json.load(file)
            else:
                self.last_seen_data = {}
            logger.info("Last seen data loaded successfully.")
        except Exception as e:
            self.last_seen_data = {}
            logger.error(f"Error loading last seen data: {str(e)}")

    def save_last_seen(self):
        try:
            with open(self.last_seen_file, "w") as file:
                json.dump(self.last_seen_data, file, indent=4)
            logger.info("Last seen data saved successfully.")
        except Exception as e:
            logger.error(f"Error saving last seen data: {str(e)}")

    def get_player_name(self, user_id):
        """Get the registered Factorio player name from Discord user ID."""
        user_id_str = str(user_id)
        return self.registrations.get(user_id_str)

    def update_last_seen(self, player_name):
        """Update the last seen time for a player."""
        self.last_seen_data[player_name] = datetime.datetime.now().isoformat()
        self.save_last_seen()

    @app_commands.command(name='lastseen', description='Get the last seen time of a Factorio player')
    @app_commands.describe(member='The registered Discord member to check')
    async def lastseen(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()

        # Check if the user is registered
        player_name = self.get_player_name(member.id)
        if not player_name:
            await interaction.followup.send(
                f"{member.mention} has not yet registered on the Factorio game server. They will need to /register before this function can be used on them.",
                ephemeral=True
            )
            return

        # Retrieve last seen time from last_seen_data
        last_seen_time = self.last_seen_data.get(player_name)
        if last_seen_time:
            last_seen_dt = datetime.datetime.fromisoformat(last_seen_time)
            
            # Create Discord timestamp
            discord_timestamp = f"<t:{int(last_seen_dt.timestamp())}:R>"

            await interaction.followup.send(
                f"{member.mention} ({player_name}) was last seen {discord_timestamp}."
            )
        else:
            await interaction.followup.send(
                f"{member.mention} ({player_name}) has not been seen online recently."
            )

    async def on_leave(self, line):
        """Handle player disconnection events."""
        leave_match = re.search(r"\[LEAVE\] (.+) left the game", line)
        if leave_match:
            player_name = leave_match.group(1)
            logger.debug(f"Processing leave event for player: {player_name}")
            self.update_last_seen(player_name)
            logger.info(f"Updated last seen time for {player_name}")
        else:
            logger.debug(f"Received line that does not match leave pattern: {line}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_readlog_cog()
        logger.info("LastSeenCog is ready.")

    async def ensure_readlog_cog(self):
        """Ensure connection to ReadLogCog."""
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            self.readlog_cog = self.bot.get_cog('ReadLogCog')
            if self.readlog_cog:
                self.readlog_cog.subscribe("LEAVE", self.on_leave)
                logger.info("Successfully connected to ReadLogCog.")
                return True
            attempt += 1
            logger.warning(f"ReadLogCog not found (Attempt {attempt}/{max_attempts}). Retrying in 2 seconds...")
            await asyncio.sleep(2)

        logger.error("Max attempts reached. LastSeen functionality may be limited.")

async def setup(bot):
    await bot.add_cog(LastSeenCog(bot))
    logger.info("LastSeenCog added to bot")
