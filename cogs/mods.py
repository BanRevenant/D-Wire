import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import shutil
import requests
import zipfile

with open('config.json') as config_file:
    config = json.load(config_file)

# Login URL and credentials
LOGIN_URL = config['factorio_server_manager']['login_url']
API_URL = config['factorio_server_manager']['api_url']
USERNAME = config['factorio_server_manager']['username']
PASSWORD = config['factorio_server_manager']['password']
MOD_PORTAL_USERNAME = config['factorio_mod_portal']['username']
MOD_PORTAL_TOKEN = config['factorio_mod_portal']['token']
MOD_PORTAL_API_URL = 'https://mods.factorio.com/api'
MOD_PATH = config['factorio_mod_portal']['mod_path']
MOD_LIST_FILE = os.path.join(MOD_PATH, 'mod-list.json')

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

async def get_mod_details(mod_name):
    """Retrieve mod details from the Factorio mod portal API."""
    url = f"{MOD_PORTAL_API_URL}/mods/{mod_name}"
    print(f"Sending GET request to: {url}")  # Debugging
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Failed to retrieve mod details. Status code: {response.status}")
                return None

def update_mod_list(mod_name, action):
    """Update the mod-list.json file based on the action performed."""
    with open(MOD_LIST_FILE, 'r') as file:
        mod_list = json.load(file)

    if action == 'add':
        mod_entry = {'name': mod_name, 'enabled': True}
        mod_list['mods'].append(mod_entry)
    elif action == 'remove':
        mod_list['mods'] = [mod for mod in mod_list['mods'] if mod['name'] != mod_name]
    elif action == 'enable':
        for mod in mod_list['mods']:
            if mod['name'] == mod_name:
                mod['enabled'] = True
                break
    elif action == 'disable':
        for mod in mod_list['mods']:
            if mod['name'] == mod_name:
                mod['enabled'] = False
                break

    with open(MOD_LIST_FILE, 'w') as file:
        json.dump(mod_list, file, indent=4)

def get_mod_name_from_zip(file_path):
    """Extract the mod name from the mod zip file."""
    with zipfile.ZipFile(file_path, 'r') as zip_file:
        for file_name in zip_file.namelist():
            if file_name.endswith('info.json'):
                with zip_file.open(file_name) as info_file:
                    info_data = json.load(info_file)
                    return info_data.get('name')
    return None

class InstallModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Install Addon")
        self.addon_url = discord.ui.TextInput(
            label="Addon URL",
            placeholder="Enter the URL of the addon from the Factorio mod portal",
            style=discord.TextStyle.short,
            required=True,
            min_length=1,
            max_length=200
        )
        self.add_item(self.addon_url)

    async def on_submit(self, interaction: discord.Interaction):
        addon_url = self.addon_url.value
        # Extract the mod name from the addon URL
        parts = addon_url.split('/')
        mod_name = parts[-1]

        # Retrieve mod details from the Factorio mod portal API
        mod_details = await get_mod_details(mod_name)
        if mod_details is None:
            await interaction.response.send_message(f"Failed to retrieve mod details for {mod_name}.", ephemeral=True)
            return

        # Get the latest release download URL
        latest_release = mod_details['releases'][-1]
        download_url = latest_release['download_url']
        file_name = latest_release['file_name']
        version = latest_release['version']

        print(f"Addon URL: {addon_url}")  # Debugging
        print(f"Mod Name: {mod_name}")  # Debugging
        print(f"Download URL: {download_url}")  # Debugging
        print(f"File Name: {file_name}")  # Debugging
        print(f"Version: {version}")  # Debugging

        # Check if the mod is already installed
        installed_mods_response = await send_api_command("/mods/list", cookie=interaction.client.cookie)
        installed_mods = [mod["name"] for mod in installed_mods_response if "name" in mod]

        if mod_name in installed_mods:
            # Mod is already installed, validate the version
            installed_version = next(mod["version"] for mod in installed_mods_response if mod["name"] == mod_name)
            if installed_version == version:
                await interaction.response.send_message(f"Mod {mod_name} is already installed with the latest version.", ephemeral=True)
                return
            else:
                message = f"Updating {mod_name} to version {version}"
        else:
            message = f"Installing mod {mod_name} version {version}"

        # Download the mod
        creds = {"username": MOD_PORTAL_USERNAME, "token": MOD_PORTAL_TOKEN}
        download_url = f"https://mods.factorio.com{download_url}?username={MOD_PORTAL_USERNAME}&token={MOD_PORTAL_TOKEN}"
        print(f"Sending GET request to: {download_url}")  # Debugging
        with requests.get(download_url, stream=True) as req:
            print(f"Response status code: {req.status_code}")  # Debugging
            print(f"Response headers: {req.headers}")  # Debugging
            print(f"Response URL: {req.url}")  # Debugging
            if req.status_code == 200:
                target_file = os.path.join(MOD_PATH, file_name)
                with open(target_file, "wb") as target:
                    shutil.copyfileobj(req.raw, target)
                    target.flush()
                mod_name = get_mod_name_from_zip(target_file)
                if mod_name:
                    update_mod_list(mod_name, 'add')
                    await interaction.response.send_message(f"{message}\nMod {mod_name} downloaded successfully.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Failed to extract mod name from the downloaded file.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Failed to download mod. Status code: {req.status_code}", ephemeral=True)

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

            enable_button = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, custom_id="enable_button")
            disable_button = discord.ui.Button(label="Disable", style=discord.ButtonStyle.secondary, custom_id="disable_button")
            remove_button = discord.ui.Button(label="Remove", style=discord.ButtonStyle.danger, custom_id="remove_button")

            async def enable_callback(interaction: discord.Interaction):
                # Check the current state of the mod
                response = await send_api_command("/mods/list", cookie=self.bot.cookie)
                if 'error' not in response:
                    mod_info = next((mod for mod in response if mod["name"] == selected_mod), None)
                    if mod_info and mod_info['enabled']:
                        await interaction.response.edit_message(content=f"Mod {selected_mod} is already enabled.", view=view)
                        return

                # Send the API request to enable the mod
                response = await send_api_command("/mods/toggle", method='POST', payload={"name": selected_mod}, cookie=self.bot.cookie)
                if isinstance(response, bool):
                    if response:
                        update_mod_list(selected_mod, 'enable')
                        await interaction.response.edit_message(content=f"Enabled mod: {selected_mod}", view=view)
                    else:
                        await interaction.response.edit_message(content=f"Failed to enable mod: {selected_mod}", view=view)
                elif 'error' in response:
                    await interaction.response.edit_message(content=f"Failed to enable mod: {response['error']}", view=view)
                else:
                    await interaction.response.edit_message(content=f"Unexpected response from the API: {response}", view=view)

            async def disable_callback(interaction: discord.Interaction):
                # Check the current state of the mod
                response = await send_api_command("/mods/list", cookie=self.bot.cookie)
                if 'error' not in response:
                    mod_info = next((mod for mod in response if mod["name"] == selected_mod), None)
                    if mod_info and not mod_info['enabled']:
                        await interaction.response.edit_message(content=f"Mod {selected_mod} is already disabled.", view=view)
                        return

                # Send the API request to disable the mod
                response = await send_api_command("/mods/toggle", method='POST', payload={"name": selected_mod}, cookie=self.bot.cookie)
                if isinstance(response, bool):
                    if not response:
                        update_mod_list(selected_mod, 'disable')
                        await interaction.response.edit_message(content=f"Disabled mod: {selected_mod}", view=view)
                    else:
                        await interaction.response.edit_message(content=f"Failed to disable mod: {selected_mod}", view=view)
                elif 'error' in response:
                    await interaction.response.edit_message(content=f"Failed to disable mod: {response['error']}", view=view)
                else:
                    await interaction.response.edit_message(content=f"Unexpected response from the API: {response}", view=view)

            async def remove_callback(interaction: discord.Interaction):
                response = await send_api_command("/mods/delete", method='POST', payload={"name": selected_mod}, cookie=self.bot.cookie)
                if 'error' not in response:
                    update_mod_list(selected_mod, 'remove')
                    await interaction.response.edit_message(content=f"Removed mod: {selected_mod}", view=view)
                else:
                    await interaction.response.edit_message(content=f"Failed to remove mod: {response['error']}", view=view)

            enable_button.callback = enable_callback
            disable_button.callback = disable_callback
            remove_button.callback = remove_callback

            view = discord.ui.View()
            view.add_item(select)
            view.add_item(enable_button)
            view.add_item(disable_button)
            view.add_item(remove_button)
            view.add_item(install_button)  # Add the install button to the view

            await interaction.response.edit_message(content=f"Selected mod: {selected_mod}", view=view)

        select.callback = select_callback

        async def install_callback(interaction: discord.Interaction):
            modal = InstallModal()
            await interaction.response.send_modal(modal)

        install_button = discord.ui.Button(label="Install", style=discord.ButtonStyle.primary, custom_id="install_button")
        install_button.callback = install_callback

        view = discord.ui.View()
        view.add_item(select)
        view.add_item(install_button)

        await interaction.response.send_message("Please select a mod:", view=view)

async def setup(bot):
    await bot.add_cog(ModsCog(bot))