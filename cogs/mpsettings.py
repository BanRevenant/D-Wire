import discord
from discord.ext import commands
from discord import app_commands
import json

class MPSettingsModal(discord.ui.Modal):
    def __init__(self, settings):
        super().__init__(title="Factorio Server Settings")
        self.settings = settings

        self.add_item(discord.ui.TextInput(
            label="name",
            placeholder=settings.get("name", "")[:100],
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="description",
            placeholder=settings.get("description", "")[:100],
            style=discord.TextStyle.long,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="game_password",
            placeholder=settings.get("game_password", ""),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="admins",
            placeholder=", ".join(settings.get("admins", []))[:100],
            style=discord.TextStyle.long,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="tags",
            placeholder=", ".join(settings.get("tags", []))[:100],
            style=discord.TextStyle.long,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        updated_settings = self.settings.copy()

        for child in self.children:
            if child.label in ["admins", "tags"]:
                updated_settings[child.label] = [name.strip() for name in child.value.split(",")]
            else:
                updated_settings[child.label] = child.value

        # Write the updated settings back to the settings file
        with open(interaction.client.config['factorio_server']['server_settings_file'], 'w') as f:
            json.dump(updated_settings, f, indent=2)

        await interaction.response.send_message("Server settings updated successfully.")

class MPSettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='mpsettings', description='Multiplayer Factorio server presence settings.')
    async def mpsettings(self, interaction: discord.Interaction):
        # Read the current settings from the settings file
        with open(self.bot.config['factorio_server']['server_settings_file'], 'r') as f:
            settings = json.load(f)

        modal = MPSettingsModal(settings)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(MPSettingsCog(bot))