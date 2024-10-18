import discord
from discord.ext import commands
from discord import app_commands
import psutil
import datetime
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/uptime.log')

class UptimeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        logger.info("UptimeCog initialized")

    @app_commands.command(name='uptime', description='Show the uptime of the Factorio server')
    async def uptime(self, interaction: discord.Interaction):
        logger.info(f"Uptime command used by {interaction.user.name}")
        server_cog = self.bot.get_cog('ServerManagementCog')
        if server_cog is None:
            logger.error("ServerManagementCog not found")
            await interaction.response.send_message("Unable to get server uptime. ServerManagementCog not found.")
            return

        if not server_cog.is_server_running():
            await interaction.response.send_message("The server is not running.")
            logger.info("Uptime requested but server is not running")
        else:
            try:
                pid = server_cog.server_pid
                process = psutil.Process(pid)
                uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())

                embed = discord.Embed(title="Server Uptime", color=discord.Color.blue())
                embed.add_field(name="PID", value=str(pid), inline=False)
                embed.add_field(name="Uptime", value=str(uptime), inline=False)

                await interaction.response.send_message(embed=embed)
                logger.info(f"Server uptime reported: PID {pid}, Uptime {uptime}")
            except psutil.NoSuchProcess:
                await interaction.response.send_message("The server process was not found. It may have stopped unexpectedly.")
                logger.error(f"Server process with PID {server_cog.server_pid} not found")
            except Exception as e:
                await interaction.response.send_message(f"An error occurred while getting server uptime: {str(e)}")
                logger.error(f"Error getting server uptime: {str(e)}")

async def setup(bot):
    await bot.add_cog(UptimeCog(bot))
    logger.info("UptimeCog added to bot")