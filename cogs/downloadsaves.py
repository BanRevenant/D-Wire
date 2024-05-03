import discord
from discord.ext import commands
from discord import app_commands
import os
import json

with open('config.json') as config_file:
    config = json.load(config_file)

SAVES_DIRECTORY = config['factorio_server']['saves_directory']

class SavesDropdown(discord.ui.Select):
    def __init__(self, saves):
        options = [discord.SelectOption(label=save) for save in saves]
        super().__init__(placeholder='Select a save file', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_save = self.values[0]
        await interaction.response.edit_message(content=f"Selected save file: `{selected_save}`")

class SavesManagementView(discord.ui.View):
    def __init__(self, saves):
        super().__init__()
        self.add_item(SavesDropdown(saves))

    @discord.ui.button(label='Download', style=discord.ButtonStyle.green)
    async def download(self, interaction: discord.Interaction, button: discord.ui.Button):
        dropdown = next((item for item in self.children if isinstance(item, SavesDropdown)), None)
        if dropdown is None:
            await interaction.response.send_message("No save files found.")
            return

        selected_save = dropdown.values[0]
        save_path = os.path.join(SAVES_DIRECTORY, selected_save)
        if os.path.exists(save_path):
            await interaction.response.send_message(file=discord.File(save_path))
        else:
            await interaction.response.send_message("The selected save file no longer exists.")

    @discord.ui.button(label='Remove', style=discord.ButtonStyle.red)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        dropdown = next((item for item in self.children if isinstance(item, SavesDropdown)), None)
        if dropdown is None:
            await interaction.response.send_message("No save files found.")
            return

        selected_save = dropdown.values[0]
        save_path = os.path.join(SAVES_DIRECTORY, selected_save)
        if os.path.exists(save_path):
            os.remove(save_path)
            await interaction.response.edit_message(content=f"Save file `{selected_save}` has been removed.")
            dropdown.options = [option for option in dropdown.options if option.label != selected_save]
            if not dropdown.options:
                self.stop()
        else:
            await interaction.response.send_message("The selected save file no longer exists.")

class DownloadSavesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='downloadsaves', description='Lists all save files on the Factorio server for download')
    async def downloadsaves(self, interaction: discord.Interaction):
        """Lists all save files on the Factorio server for download."""
        await interaction.response.defer()
        saves = [file for file in os.listdir(SAVES_DIRECTORY) if file.endswith('.zip')]
        if not saves:
            await interaction.followup.send("No save files found on the Factorio server.")
            return

        view = SavesManagementView(saves)
        await interaction.followup.send("Select a save file to download or remove:", view=view)

async def setup(bot):
    await bot.add_cog(DownloadSavesCog(bot))