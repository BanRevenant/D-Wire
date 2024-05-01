import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import tarfile
import json

class UpdateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='update', description='Update the Factorio server to the latest version')
    @commands.has_permissions(administrator=True)
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Check if the server is running
        server_management_cog = self.bot.get_cog('ServerManagementCog')
        if server_management_cog.is_server_running():
            await interaction.followup.send('The Factorio server is currently running. Please stop the server before updating.')
            return

        # Read the config file
        install_location = self.bot.config['factorio_server']['factorio_install_location']

        # Create the install directory if it doesn't exist
        os.makedirs(install_location, exist_ok=True)

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

                    # Extract the downloaded file
                    with tarfile.open(file_path, 'r:xz') as tar:
                        tar.extractall(install_location)

                    # Remove the downloaded file
                    os.remove(file_path)

                    # Set the executable permission for the Factorio executable
                    factorio_exe = os.path.join(install_location, 'factorio', 'bin', 'x64', 'factorio')
                    os.chmod(factorio_exe, 0o755)

                    await interaction.followup.send('Factorio server updated successfully.')
                else:
                    await interaction.followup.send('Failed to download the latest Factorio server file.')

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))