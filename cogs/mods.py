import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json

with open('config.json') as config_file:
    config = json.load(config_file)

# Login URL and credentials
LOGIN_URL = config['factorio_server_manager']['login_url']
API_URL = config['factorio_server_manager']['api_url']
USERNAME = config['factorio_server_manager']['username']
PASSWORD = config['factorio_server_manager']['password']

async def send_api_command(endpoint, method='GET', payload=None, cookie=None):
    """Send commands to the Factorio Server Manager API using aiohttp."""
    async with aiohttp.ClientSession() as session:
        headers = {'Content-Type': 'application/json'}
        url = f"{API_URL}{endpoint}"
        print(f"Sending {method} request to: {url}")  # Debugging
        if method == 'POST':
            async with session.post(url, json=payload, cookies={'authentication': cookie}, headers=headers) as response:
                if response.status == 200:
                    print(f"Received response from {url}: {await response.json()}")  # Debugging
                    return await response.json()
                else:
                    print(f"Failed request to {url} with status {response.status}: {await response.text()}")  # Debugging
                    return {'error': f"Failed with status {response.status}: {await response.text()}"}
        else:
            async with session.get(url, cookies={'authentication': cookie}, headers=headers) as response:
                if response.status == 200:
                    print(f"Received response from {url}: {await response.json()}")  # Debugging
                    return await response.json()
                else:
                    print(f"Failed request to {url} with status {response.status}: {await response.text()}")  # Debugging
                    return {'error': f"Failed with status {response.status}: {await response.text()}"}

class InstallModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Install Addon", *args, **kwargs)
        self.add_item(discord.ui.InputText(label="Addon URL"))

    async def callback(self, interaction: discord.Interaction):
        addon_url = self.children[0].value
        # Code to download the addon using the provided URL
        await interaction.response.send_message(f"Installing addon from URL: {addon_url}", ephemeral=True)

class ModsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def login(self):
        payload = {'username': USERNAME, 'password': PASSWORD}
        print(f"Logging in with payload: {payload}")  # Debugging
        async with aiohttp.ClientSession() as session:
            async with session.post(LOGIN_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    self.bot.cookie = data['token']  # Assuming the token is returned in the 'token' field
                    print(f"Logged in successfully. Received token: {self.bot.cookie}")  # Debugging
                else:
                    print(f"Login failed with status {response.status}: {await response.text()}")  # Debugging

    async def get_mods_list(self):
        response = await send_api_command("/mods/list", cookie=self.bot.cookie)
        if 'error' not in response:
            print(f"Mods list response: {response}")  # Debugging
            return [mod["name"] for mod in response if "name" in mod]  # Return the "name" of each mod
        else:
            print(f"Failed to get mods list: {response['error']}")
            return []

    @app_commands.command(name="mods", description="Manage mods using a dropdown menu")
    async def mods(self, interaction: discord.Interaction):
        if not hasattr(self.bot, 'cookie') or not self.bot.cookie:
            await self.login()

        mods_list = await self.get_mods_list()
        print(f"Mods list: {mods_list}")  # Debugging

        if not mods_list:
            await interaction.response.send_message("No mods found on the server.", ephemeral=True)
            return

        options = [discord.SelectOption(label=mod_name, value=mod_name) for mod_name in mods_list]

        select = discord.ui.Select(placeholder="Select a mod", options=options)

        async def select_callback(interaction: discord.Interaction):
            selected_mod = select.values[0]
            # Comment out the "Selected mod:" message
            # await interaction.response.send_message(f"Selected mod: {selected_mod}")

        select.callback = select_callback

        async def enable_callback(interaction: discord.Interaction):
            selected_mod = select.values[0]
            response = await send_api_command("/mods/toggle", method='POST', payload={"name": selected_mod}, cookie=self.bot.cookie)
            if isinstance(response, bool) and response:
                await interaction.response.send_message(f"Enabled mod: {selected_mod}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Failed to enable mod: {response['error']}", ephemeral=True)

        async def disable_callback(interaction: discord.Interaction):
            selected_mod = select.values[0]
            response = await send_api_command("/mods/toggle", method='POST', payload={"name": selected_mod}, cookie=self.bot.cookie)
            if isinstance(response, bool) and not response:
                await interaction.response.send_message(f"Disabled mod: {selected_mod}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Failed to disable mod: {response['error']}", ephemeral=True)

        async def remove_callback(interaction: discord.Interaction):
            selected_mod = select.values[0]
            response = await send_api_command("/mods/delete", method='POST', payload={"name": selected_mod}, cookie=self.bot.cookie)
            if 'error' not in response:
                await interaction.response.send_message(f"Removed mod: {selected_mod}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Failed to remove mod: {response['error']}", ephemeral=True)

        async def install_callback(interaction: discord.Interaction):
            modal = InstallModal()
            await interaction.response.send_modal(modal)

        enable_button = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, custom_id="enable_button")
        enable_button.callback = enable_callback

        disable_button = discord.ui.Button(label="Disable", style=discord.ButtonStyle.secondary, custom_id="disable_button")
        disable_button.callback = disable_callback

        remove_button = discord.ui.Button(label="Remove", style=discord.ButtonStyle.danger, custom_id="remove_button")
        remove_button.callback = remove_callback

        install_button = discord.ui.Button(label="Install", style=discord.ButtonStyle.primary, custom_id="install_button")
        install_button.callback = install_callback

        view = discord.ui.View()
        view.add_item(select)
        view.add_item(enable_button)
        view.add_item(disable_button)
        view.add_item(remove_button)
        view.add_item(install_button)

        await interaction.response.send_message("Please select a mod:", view=view)

async def setup(bot):
    await bot.add_cog(ModsCog(bot))