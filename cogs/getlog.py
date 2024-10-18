import os
import discord
from discord.ext import commands
from discord import app_commands
import io
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/getlog.log')

class GetLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.log_file = self.config_manager.get('factorio_server.verbose_log_file')
        logger.info("GetLogCog initialized")

    @app_commands.command(name='verbose', description='Upload the Factorio verbose log file')
    async def verbose(self, interaction: discord.Interaction):
        logger.info(f"User {interaction.user.name} requested verbose log file")
        if os.path.isfile(self.log_file):
            try:
                with open(self.log_file, 'rb') as f:
                    log_data = f.read()
                    
                file_size = len(log_data)
                if file_size > 8 * 1024 * 1024:  # 8 MB in bytes
                    logger.warning(f"Verbose log file is too large to upload ({file_size / (1024 * 1024):.2f} MB)")
                    await interaction.response.send_message(f"The log file is too large to upload ({file_size / (1024 * 1024):.2f} MB). Discord has a file size limit of 8 MB.")
                else:
                    await interaction.response.send_message(file=discord.File(io.BytesIO(log_data), filename='verbose.log'))
                    logger.info("Verbose log file uploaded successfully")
            except Exception as e:
                logger.error(f"Error reading log file: {str(e)}")
                await interaction.response.send_message(f"An error occurred while reading the log file: {str(e)}")
        else:
            logger.warning(f"Log file {self.log_file} doesn't exist")
            await interaction.response.send_message(f"The log file {self.log_file} doesn't exist.")

async def setup(bot):
    await bot.add_cog(GetLogCog(bot))
    logger.info("GetLogCog added to bot")