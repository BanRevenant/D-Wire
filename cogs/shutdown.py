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
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @app_commands.describe(reason="Optional reason for shutting down the bot")
    async def shutdown(self, interaction: discord.Interaction, reason: str = None):
        """
        Shuts down the bot. Only administrators can use this command.
        Optional: Provide a reason for the shutdown.
        """
        shutdown_message = f"💤 {interaction.user.mention} initiated bot shutdown"
        if reason:
            shutdown_message += f"\nReason: {reason}"
        
        logger.info(f"Shutdown command used by {interaction.user} (ID: {interaction.user.id})")
        if reason:
            logger.info(f"Shutdown reason: {reason}")

        # Send shutdown message
        await interaction.response.send_message(shutdown_message)
        
        # Wait briefly to ensure message is sent
        await asyncio.sleep(2)
        
        # Shut down the bot
        await self.bot.close()

    # Error handler for permission check failures
    @shutdown.error
    async def shutdown_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need administrator permissions to shut down the bot.", 
                ephemeral=True  # Only the command user sees this message
            )
            logger.warning(f"Unauthorized shutdown attempt by {interaction.user} (ID: {interaction.user.id})")
        else:
            await interaction.response.send_message(
                "❌ An error occurred while processing the command.", 
                ephemeral=True
            )
            logger.error(f"Error in shutdown command: {str(error)}")

async def setup(bot):
    await bot.add_cog(ShutdownCog(bot))
    logger.info("ShutdownCog added to bot")