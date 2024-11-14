import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import json
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/reboot.log')

class RebootCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        logger.info("RebootCog initialized")

    @app_commands.command(name="discordrestart", description="Restart the Discord bot")
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)
    async def discordrestart(self, interaction: discord.Interaction):
        logger.info(f"Discord bot restart initiated by {interaction.user.name}")
        await interaction.response.send_message("Restarting the Discord bot...")
        
        try:
            logger.info("Attempting to restart the Discord bot")
            os.execv(sys.executable, ['python'] + sys.argv)
        except Exception as e:
            logger.error(f"Error during bot restart: {str(e)}")
            await interaction.followup.send(f"An error occurred while restarting the bot: {str(e)}")

async def setup(bot):
    await bot.add_cog(RebootCog(bot))
    logger.info("RebootCog added to bot")