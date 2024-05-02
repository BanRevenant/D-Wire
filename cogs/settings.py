import discord
from discord.ext import commands
from discord import app_commands
import json

class SettingsDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Server Presence", description="Modify server presence settings"),
            discord.SelectOption(label="Save Settings", description="Modify save settings"),
            discord.SelectOption(label="Networking Settings", description="Modify networking settings"),
            discord.SelectOption(label="Master Settings", description="Modify master settings")
        ]
        super().__init__(placeholder="Select a settings category", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        settings_file = interaction.client.config['factorio_server']['server_settings_file']

        with open(settings_file, 'r') as f:
            settings = json.load(f)

        if selected_category == "Server Presence":
            modal = ServerPresenceModal(settings)
        elif selected_category == "Save Settings":
            modal = SaveSettingsModal(settings)
        elif selected_category == "Networking Settings":
            modal = NetworkingSettingsModal(settings)
        elif selected_category == "Master Settings":
            modal = MasterSettingsModal(settings)

        await interaction.response.send_modal(modal)

class ServerPresenceModal(discord.ui.Modal):
    def __init__(self, settings):
        super().__init__(title="Server Presence Settings")
        self.settings = settings

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
            label="max_players",
            placeholder=str(settings.get("max_players", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="name",
            placeholder=settings.get("name", "")[:100],
            style=discord.TextStyle.short,
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
            if child.label == "tags":
                updated_settings[child.label] = [tag.strip() for tag in child.value.split(",")]
            elif child.label == "max_players":
                try:
                    updated_settings[child.label] = int(child.value)
                except ValueError:
                    pass
            else:
                updated_settings[child.label] = child.value

        with open(interaction.client.config['factorio_server']['server_settings_file'], 'w') as f:
            json.dump(updated_settings, f, indent=2)

        await interaction.response.edit_message(content="Server presence settings updated successfully.")

class SaveSettingsModal(discord.ui.Modal):
    def __init__(self, settings):
        super().__init__(title="Save Settings")
        self.settings = settings

        self.add_item(discord.ui.TextInput(
            label="auto_pause",
            placeholder=str(settings.get("auto_pause", True)),
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
            label="autosave_only_on_server",
            placeholder=str(settings.get("autosave_only_on_server", True)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="autosave_slots",
            placeholder=str(settings.get("autosave_slots", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="only_admins_can_pause_the_game",
            placeholder=str(settings.get("only_admins_can_pause_the_game", True)),
            style=discord.TextStyle.short,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        updated_settings = self.settings.copy()

        for child in self.children:
            if child.label in ["auto_pause", "autosave_only_on_server", "only_admins_can_pause_the_game"]:
                updated_settings[child.label] = child.value.lower() == "true"
            elif child.label in ["autosave_interval", "autosave_slots"]:
                try:
                    updated_settings[child.label] = int(child.value)
                except ValueError:
                    pass

        with open(interaction.client.config['factorio_server']['server_settings_file'], 'w') as f:
            json.dump(updated_settings, f, indent=2)

        await interaction.response.edit_message(content="Save settings updated successfully.")

class NetworkingSettingsModal(discord.ui.Modal):
    def __init__(self, settings):
        super().__init__(title="Networking Settings")
        self.settings = settings

        self.add_item(discord.ui.TextInput(
            label="max_heartbeats_per_second",
            placeholder=str(settings.get("max_heartbeats_per_second", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="maximum_segment_size",
            placeholder=str(settings.get("maximum_segment_size", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="minimum_segment_size",
            placeholder=str(settings.get("minimum_segment_size", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="minimum_latency_in_ticks",
            placeholder=str(settings.get("minimum_latency_in_ticks", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="minimum_segment_size_peer_count",
            placeholder=str(settings.get("minimum_segment_size_peer_count", 0)),
            style=discord.TextStyle.short,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        updated_settings = self.settings.copy()

        for child in self.children:
            try:
                updated_settings[child.label] = int(child.value)
            except ValueError:
                pass

        with open(interaction.client.config['factorio_server']['server_settings_file'], 'w') as f:
            json.dump(updated_settings, f, indent=2)

        await interaction.response.edit_message(content="Networking settings updated successfully.")

class MasterSettingsModal(discord.ui.Modal):
    def __init__(self, settings):
        super().__init__(title="Master Settings")
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
            label="admins",
            placeholder=", ".join(settings.get("admins", []))[:100],
            style=discord.TextStyle.long,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="allow_commands",
            placeholder=settings.get("allow_commands", ""),
            style=discord.TextStyle.short,
            required=False
        ))

        self.add_item(discord.ui.TextInput(
            label="require_user_verification",
            placeholder=str(settings.get("require_user_verification", True)),
            style=discord.TextStyle.short,
            required=False
        ))

    async def on_submit(self, interaction: discord.Interaction):
        updated_settings = self.settings.copy()

        for child in self.children:
            if child.label == "token" and child.value.strip() == "":
                pass
            elif child.label == "admins":
                updated_settings[child.label] = [admin.strip() for admin in child.value.split(",")]
            elif child.label == "require_user_verification":
                updated_settings[child.label] = child.value.lower() == "true"
            else:
                updated_settings[child.label] = child.value

        with open(interaction.client.config['factorio_server']['server_settings_file'], 'w') as f:
            json.dump(updated_settings, f, indent=2)

        await interaction.response.edit_message(content="Master settings updated successfully.")

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='settings', description='Modify Factorio server settings.')
    async def settings(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(SettingsDropdown())

        await interaction.response.send_message("Select a settings category:", view=view)

async def setup(bot):
    await bot.add_cog(SettingsCog(bot))