import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os

with open('config.json') as config_file:
    config = json.load(config_file)

API_URL = config['factorio_server_manager']['api_url']
SAVES_DIRECTORY = "/opt/factorio/saves"

async def send_api_command(endpoint, method='POST', data=None, cookie=None):
    """Send commands to the Factorio Server Manager API using aiohttp."""
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bearer {cookie}'}
        url = f"{API_URL}{endpoint}"
        
        async with session.post(url, data=data, headers=headers) as response:
            if response.status == 200:
                return await response.text(), None
            else:
                return None, {'error': f"Failed with status {response.status}: {await response.text()}"}

class SaveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='save', description='Upload a save file to the Factorio server')
    async def upload_save(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload a save file to the Factorio server."""
        if file.filename.endswith('.zip'):
            await interaction.response.defer()
            
            file_path = os.path.join(SAVES_DIRECTORY, file.filename)
            
            # Check if the file already exists
            if os.path.exists(file_path):
                confirm_view = ConfirmButtonView(interaction.user)
                await interaction.followup.send(f"A save file named `{file.filename}` already exists. Do you want to overwrite it?", view=confirm_view)
                await confirm_view.wait()
                
                if confirm_view.value is None:
                    await interaction.followup.send("Confirmation timed out. Save file upload canceled.")
                    return
                elif not confirm_view.value:
                    await interaction.followup.send("Save file upload canceled.")
                    return
            
            # Download the uploaded file
            await file.save(file_path)
            
            # Upload the save file to the Factorio server
            with open(file_path, 'rb') as save_file:
                data = aiohttp.FormData()
                data.add_field('file', save_file, filename=file.filename)
                response, error = await send_api_command('/saves/upload', data=data, cookie=self.bot.cookie)
                
            if error:
                await interaction.followup.send(f"Error uploading save file: {error['error']}")
            else:
                await interaction.followup.send(f"Save file `{file.filename}` uploaded successfully!")
            
            # Remove the temporary file
            os.remove(file_path)
        else:
            await interaction.response.send_message("Invalid file type. Please upload a zip file.", ephemeral=True)

class ConfirmButtonView(discord.ui.View):
    def __init__(self, user):
        super().__init__()
        self.value = None
        self.user = user

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.user:
            self.value = True
            self.stop()
        else:
            await interaction.response.send_message("Only the user who initiated the command can confirm.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.user:
            self.value = False
            self.stop()
        else:
            await interaction.response.send_message("Only the user who initiated the command can cancel.", ephemeral=True)

    async def on_timeout(self):
        self.value = None
        self.stop()

async def setup(bot):
    await bot.add_cog(SaveCog(bot))