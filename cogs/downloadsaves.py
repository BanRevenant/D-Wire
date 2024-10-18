import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/downloadsaves.log')

class SavesDropdown(discord.ui.Select):
    def __init__(self, saves):
        options = [discord.SelectOption(label=save) for save in saves]
        super().__init__(placeholder='Select a save file', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_save = self.values[0]
        await interaction.response.edit_message(content=f"Selected save file: `{selected_save}`")
        logger.info(f"User {interaction.user.name} selected save file: {selected_save}")

class SavesManagementView(discord.ui.View):
    def __init__(self, saves, config_manager):
        super().__init__()
        self.add_item(SavesDropdown(saves))
        self.config_manager = config_manager

    @discord.ui.button(label='Download', style=discord.ButtonStyle.green)
    async def download(self, interaction: discord.Interaction, button: discord.ui.Button):
        dropdown = next((item for item in self.children if isinstance(item, SavesDropdown)), None)
        if dropdown is None:
            await interaction.response.send_message("No save files found.")
            logger.warning("Download attempted but no save files found")
            return

        selected_save = dropdown.values[0]
        save_path = os.path.join(self.config_manager.get('factorio_server.saves_directory'), selected_save)
        if os.path.exists(save_path):
            file_size = os.path.getsize(save_path)
            if file_size > 8388608:  # 8 MB in bytes
                await interaction.response.send_message(f"The selected save file (`{selected_save}`) is too large to upload ({file_size / (1024 * 1024):.2f} MB). Discord has a file size limit of 8 MB.")
                logger.warning(f"Save file {selected_save} is too large to upload ({file_size / (1024 * 1024):.2f} MB)")
            else:
                await interaction.response.send_message(file=discord.File(save_path))
                logger.info(f"User {interaction.user.name} downloaded save file: {selected_save}")
        else:
            await interaction.response.send_message("The selected save file no longer exists.")
            logger.warning(f"Save file {selected_save} no longer exists")

    @discord.ui.button(label='Remove', style=discord.ButtonStyle.red)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        dropdown = next((item for item in self.children if isinstance(item, SavesDropdown)), None)
        if dropdown is None:
            await interaction.response.send_message("No save files found.")
            logger.warning("Remove attempted but no save files found")
            return

        selected_save = dropdown.values[0]
        save_path = os.path.join(self.config_manager.get('factorio_server.saves_directory'), selected_save)
        if os.path.exists(save_path):
            os.remove(save_path)
            await interaction.response.edit_message(content=f"Save file `{selected_save}` has been removed.")
            logger.info(f"User {interaction.user.name} removed save file: {selected_save}")
            dropdown.options = [option for option in dropdown.options if option.label != selected_save]
            if not dropdown.options:
                self.stop()
        else:
            await interaction.response.send_message("The selected save file no longer exists.")
            logger.warning(f"Save file {selected_save} no longer exists")

class DownloadSavesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        logger.info("DownloadSavesCog initialized")

    @app_commands.command(name='downloadsaves', description='Lists all save files on the Factorio server for download')
    async def downloadsaves(self, interaction: discord.Interaction):
        """Lists all save files on the Factorio server for download."""
        await interaction.response.defer()
        saves_directory = self.config_manager.get('factorio_server.saves_directory')
        saves = [file for file in os.listdir(saves_directory) if file.endswith('.zip')]
        if not saves:
            await interaction.followup.send("No save files found on the Factorio server.")
            logger.info("No save files found on the Factorio server")
            return

        view = SavesManagementView(saves, self.config_manager)
        await interaction.followup.send("Select a save file to download or remove:", view=view)
        logger.info(f"User {interaction.user.name} requested save files list")

async def setup(bot):
    await bot.add_cog(DownloadSavesCog(bot))
    logger.info("DownloadSavesCog added to bot")