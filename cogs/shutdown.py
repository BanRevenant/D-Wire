import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from logger import setup_logger

logger = setup_logger(__name__, 'logs/shutdown.log')

class ShutdownCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("ShutdownCog initialized")

    @app_commands.command(name="shutdown", description="Terminate the running Factorio Server Manager Discord Bot")
    async def shutdown(self, interaction: discord.Interaction):
        user = interaction.user
        await interaction.response.send_message(f"{user.mention}, shutting down the bot...")  # Mention the user
        logger.info(f"Shutdown command used by {user} (User ID: {user.id}). Bot is shutting down.")

        await asyncio.sleep(2)  # Wait for the message to be sent before shutting down
        await self.bot.close()  # Shutdown the bot

async def setup(bot):
    if bot.get_cog("ShutdownCog") is None:
        await bot.add_cog(ShutdownCog(bot))
        logger.info("ShutdownCog added to bot")
    else:
        logger.warning("ShutdownCog is already loaded")
