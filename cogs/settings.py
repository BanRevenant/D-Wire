import discord
from discord.ext import commands
from discord import app_commands
import json

class SettingsModal(discord.ui.Modal):
    def __init__(self, settings):
        super().__init__(title="Factorio Server Settings")
        self.settings = settings

        self.add_item(discord.ui.TextInput(
            label="token",
            placeholder="(hidden)",
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="username",
            placeholder=settings.get("username", ""),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="max_players",
            placeholder=str(settings.get("max_players", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="autosave_interval",
            placeholder=str(settings.get("autosave_interval", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="autosave_slots",
            placeholder=str(settings.get("autosave_slots", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        updated_settings = self.settings.copy()

        for child in self.children:
            if child.label == "token" and child.value.strip() == "":
                # If the token value is empty, keep the existing token value
                pass
            elif child.label in ["max_players", "autosave_interval", "autosave_slots"]:
                try:
                    updated_settings[child.label] = int(child.value)
                except ValueError:
                    # If the value is not a valid integer, keep the existing value
                    pass
            else:
                updated_settings[child.label] = child.value

        # Write the updated settings back to the settings file
        with open(interaction.client.config['factorio_server']['server_settings_file'], 'w') as f:
            json.dump(updated_settings, f, indent=2)

        await interaction.response.send_message("Server settings updated successfully.")

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='settings', description='Modify admin settings responsible server visibility, saving and player counts.')
    async def settings(self, interaction: discord.Interaction):
        # Read the current settings from the settings file
        with open(self.bot.config['factorio_server']['server_settings_file'], 'r') as f:
            settings = json.load(f)

        modal = SettingsModal(settings)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(SettingsCog(bot))