import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import tarfile
import json
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/update.log')

class UpdateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        logger.info("UpdateCog initialized")

    @app_commands.command(name='update', description='Update the Factorio server to the latest version')
    @app_commands.checks.has_permissions(administrator=True)
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        logger.info(f"Update command initiated by {interaction.user.name}")

        # Check if the server is running
        server_management_cog = self.bot.get_cog('ServerManagementCog')
        if server_management_cog is None:
            logger.error("ServerManagementCog not found")
            await interaction.followup.send("Unable to check server status. ServerManagementCog not found.")
            return

        if server_management_cog.is_server_running():
            await interaction.followup.send('The Factorio server is currently running. Please stop the server before updating.')
            logger.warning("Update attempted while server was running")
            return

        # Read the config file
        install_location = self.config_manager.get('factorio_server.factorio_install_location')

        # Create the install directory if it doesn't exist
        os.makedirs(install_location, exist_ok=True)
        logger.info(f"Install directory ensured: {install_location}")

        # Download the latest Factorio headless server file
        download_url = 'https://www.factorio.com/get-download/latest/headless/linux64'
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    file_name = 'factorio-headless-linux64.tar.xz'
                    file_path = os.path.join(install_location, file_name)

                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    logger.info(f"Downloaded latest Factorio server file to {file_path}")

                    # Extract the downloaded file
                    try:
                        with tarfile.open(file_path, 'r:xz') as tar:
                            tar.extractall(install_location)
                        logger.info(f"Extracted Factorio server files to {install_location}")
                    except Exception as e:
                        logger.error(f"Error extracting Factorio server files: {str(e)}")
                        await interaction.followup.send(f"An error occurred while extracting the Factorio server files: {str(e)}")
                        return

                    # Remove the downloaded file
                    os.remove(file_path)
                    logger.info(f"Removed downloaded file: {file_path}")

                    # Set the executable permission for the Factorio executable
                    factorio_exe = os.path.join(install_location, 'factorio', 'bin', 'x64', 'factorio')
                    try:
                        os.chmod(factorio_exe, 0o755)
                        logger.info(f"Set executable permissions for {factorio_exe}")
                    except Exception as e:
                        logger.error(f"Error setting executable permissions: {str(e)}")
                        await interaction.followup.send(f"An error occurred while setting executable permissions: {str(e)}")
                        return

                    await interaction.followup.send('Factorio server updated successfully.')
                    logger.info("Factorio server update completed successfully")
                else:
                    logger.error(f"Failed to download the latest Factorio server file. Status code: {response.status}")
                    await interaction.followup.send('Failed to download the latest Factorio server file.')

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))
    logger.info("UpdateCog added to bot")