import discord
from discord.ext import commands
from discord import app_commands
import re
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/status.log')

class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.server_log_file = self.config_manager.get('factorio_server.server_log_file')
        logger.info("StatusCog initialized")

    @app_commands.command(name='serverstatus', description='Get the current status of the Factorio server')
    async def serverstatus(self, interaction: discord.Interaction):
        """Get the current status of the Factorio server."""
        await interaction.response.defer()
        logger.info(f"Server status requested by {interaction.user.name}")

        server_management_cog = self.bot.get_cog('ServerManagementCog')
        if server_management_cog is None:
            logger.error("ServerManagementCog not found")
            await interaction.followup.send("Unable to get server status. ServerManagementCog not found.")
            return

        server_status = "Online" if server_management_cog.is_server_running() else "Offline"
        
        if server_status == "Offline":
            embed = discord.Embed(title="Factorio Server Status", description="Server is currently offline.", color=discord.Color.red())
            logger.info("Server status: Offline")
        else:
            try:
                with open(self.server_log_file, 'r') as log_file:
                    log_content = log_file.read()

                if "Goodbye" in log_content:
                    embed = discord.Embed(title="Factorio Server Status", description="Server is shutting down.", color=discord.Color.orange())
                    logger.info("Server status: Shutting down")
                else:
                    save_file_match = re.search(r'Loading map (.+?\.zip)', log_content)
                    save_file = save_file_match.group(1) if save_file_match else "Unknown"

                    port_match = re.search(r'Hosting game at IP ADDR:\({.+?:(\d+)}\)', log_content)
                    port = port_match.group(1) if port_match else "Unknown"

                    ip_match = re.search(r'Own address is IP ADDR:\({(.+?:\d+)}\)', log_content)
                    ip_address = ip_match.group(1) if ip_match else "Unknown"

                    version_match = re.search(r'Factorio (\d+\.\d+\.\d+)', log_content)
                    factorio_version = version_match.group(1) if version_match else "Unknown"

                    base_mod_match = re.search(r'Loading mod base (\d+\.\d+\.\d+)', log_content)
                    base_mod_version = base_mod_match.group(1) if base_mod_match else "Unknown"

                    embed = discord.Embed(title="Factorio Server Status", color=discord.Color.green())
                    embed.add_field(name="Status", value=server_status, inline=False)
                    embed.add_field(name="Save File", value=save_file, inline=False)
                    embed.add_field(name="Port", value=port, inline=False)
                    embed.add_field(name="IP Address", value=ip_address, inline=False)
                    embed.add_field(name="Factorio Version", value=factorio_version, inline=False)
                    embed.add_field(name="Base Mod Version", value=base_mod_version, inline=False)
                    logger.info(f"Server status: Online (Port: {port}, IP: {ip_address}, Version: {factorio_version})")
            except Exception as e:
                logger.error(f"Error reading server log file: {str(e)}")
                embed = discord.Embed(title="Factorio Server Status", description="Error reading server status.", color=discord.Color.red())
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StatusCog(bot))
    logger.info("StatusCog added to bot")