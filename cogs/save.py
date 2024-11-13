import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/save.log')

class SaveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.saves_directory = self.config_manager.get('factorio_server.saves_directory')
        logger.info("SaveCog initialized")

    @app_commands.command(name='save', description='Upload a save file to the Factorio server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)
    async def upload_save(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload a save file to the Factorio server."""
        if file.filename.endswith('.zip'):
            await interaction.response.defer()
            
            file_path = os.path.join(self.saves_directory, file.filename)
            
            # Check if the file already exists
            if os.path.exists(file_path):
                confirm_view = ConfirmButtonView(interaction.user)
                await interaction.followup.send(f"A save file named `{file.filename}` already exists. Do you want to overwrite it?", view=confirm_view)
                await confirm_view.wait()
                
                if confirm_view.value is None:
                    await interaction.followup.send("Confirmation timed out. Save file upload canceled.")
                    logger.info(f"Save file upload for {file.filename} timed out")
                    return
                elif not confirm_view.value:
                    await interaction.followup.send("Save file upload canceled.")
                    logger.info(f"Save file upload for {file.filename} canceled by user")
                    return
            
            try:
                # Download the uploaded file
                await file.save(file_path)
                
                await interaction.followup.send(f"Save file `{file.filename}` uploaded successfully!")
                logger.info(f"Save file {file.filename} uploaded successfully by {interaction.user.name}")
            except Exception as e:
                await interaction.followup.send(f"An error occurred while saving the file: {str(e)}")
                logger.error(f"Error saving file {file.filename}: {str(e)}")
        else:
            await interaction.response.send_message("Invalid file type. Please upload a zip file.", ephemeral=True)
            logger.warning(f"Invalid file type attempted to be uploaded by {interaction.user.name}: {file.filename}")

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
            logger.info(f"User {self.user.name} confirmed file overwrite")
        else:
            await interaction.response.send_message("Only the user who initiated the command can confirm.", ephemeral=True)
            logger.warning(f"User {interaction.user.name} attempted to confirm file overwrite for {self.user.name}'s upload")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.user:
            self.value = False
            self.stop()
            logger.info(f"User {self.user.name} canceled file overwrite")
        else:
            await interaction.response.send_message("Only the user who initiated the command can cancel.", ephemeral=True)
            logger.warning(f"User {interaction.user.name} attempted to cancel file overwrite for {self.user.name}'s upload")

    async def on_timeout(self):
        self.value = None
        self.stop()
        logger.info("File overwrite confirmation timed out")

async def setup(bot):
    await bot.add_cog(SaveCog(bot))
    logger.info("SaveCog added to bot")