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

MOD_PORTAL_USERNAME = config['factorio_mod_portal']['username']
MOD_PORTAL_TOKEN = config['factorio_mod_portal']['token']
MOD_PORTAL_API_URL = 'https://mods.factorio.com/api'
MOD_PATH = config['factorio_mod_portal']['mod_path']
MOD_LIST_FILE = os.path.join(MOD_PATH, 'mod-list.json')

async def get_mod_details(mod_name):
    """Retrieve mod details from the Factorio mod portal API."""
    url = f"{MOD_PORTAL_API_URL}/mods/{mod_name}"
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

        # Download the mod
        download_url = f"https://mods.factorio.com{download_url}?username={MOD_PORTAL_USERNAME}&token={MOD_PORTAL_TOKEN}"
        with requests.get(download_url, stream=True) as req:
            if req.status_code == 200:
                target_file = os.path.join(MOD_PATH, file_name)
                with open(target_file, "wb") as target:
                    shutil.copyfileobj(req.raw, target)
                    target.flush()
                mod_name = get_mod_name_from_zip(target_file)
                if mod_name:
                    update_mod_list(mod_name, 'add')
                    await interaction.response.send_message(f"Mod {mod_name} downloaded and installed successfully.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Failed to extract mod name from the downloaded file.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Failed to download mod. Status code: {req.status_code}", ephemeral=True)

class ModsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_installed_mods(self):
        if os.path.exists(MOD_LIST_FILE):
            with open(MOD_LIST_FILE, 'r') as file:
                mod_list = json.load(file)
                return [mod["name"] for mod in mod_list["mods"]]
        else:
            return []

    @app_commands.command(name="mods", description="Manage mods using a dropdown menu")
    async def mods(self, interaction: discord.Interaction):
        mods_list = self.get_installed_mods()

        if not mods_list:
            await interaction.response.send_message("No mods found on the server.", ephemeral=True)
            return

        # Split the mods_list into chunks of 25 mods
        mod_chunks = [mods_list[i:i + 25] for i in range(0, len(mods_list), 25)]

        install_button = discord.ui.Button(label="Install", style=discord.ButtonStyle.primary, custom_id="install_button")
        install_button.callback = lambda interaction: interaction.response.send_modal(InstallModal())

        async def select_callback(interaction: discord.Interaction, selected_mod):
            enable_button = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, custom_id="enable_button")
            disable_button = discord.ui.Button(label="Disable", style=discord.ButtonStyle.secondary, custom_id="disable_button")
            remove_button = discord.ui.Button(label="Remove", style=discord.ButtonStyle.danger, custom_id="remove_button")

            async def enable_callback(interaction: discord.Interaction):
                # Check the current state of the mod
                with open(MOD_LIST_FILE, 'r') as file:
                    mod_list = json.load(file)
                    mod_info = next((mod for mod in mod_list["mods"] if mod["name"] == selected_mod), None)
                    if mod_info and mod_info['enabled']:
                        await interaction.response.edit_message(content=f"Mod {selected_mod} is already enabled.", view=view)
                        return

                # Enable the mod
                update_mod_list(selected_mod, 'enable')
                await interaction.response.edit_message(content=f"Enabled mod: {selected_mod}", view=view)

            async def disable_callback(interaction: discord.Interaction):
                # Check the current state of the mod
                with open(MOD_LIST_FILE, 'r') as file:
                    mod_list = json.load(file)
                    mod_info = next((mod for mod in mod_list["mods"] if mod["name"] == selected_mod), None)
                    if mod_info and not mod_info['enabled']:
                        await interaction.response.edit_message(content=f"Mod {selected_mod} is already disabled.", view=view)
                        return

                # Disable the mod
                update_mod_list(selected_mod, 'disable')
                await interaction.response.edit_message(content=f"Disabled mod: {selected_mod}", view=view)

            async def remove_callback(interaction: discord.Interaction):
                # Remove the mod from the mod list and delete the mod file
                update_mod_list(selected_mod, 'remove')
                mod_file = os.path.join(MOD_PATH, f"{selected_mod}.zip")
                if os.path.exists(mod_file):
                    os.remove(mod_file)
                await interaction.response.edit_message(content=f"Removed mod: {selected_mod}", view=view)

            enable_button.callback = enable_callback
            disable_button.callback = disable_callback
            remove_button.callback = remove_callback

            view = discord.ui.View()
            view.add_item(enable_button)
            view.add_item(disable_button)
            view.add_item(remove_button)
            view.add_item(install_button)  # Add the install button to the view

            await interaction.response.edit_message(content=f"Selected mod: {selected_mod}", view=view)

        current_page = 0
        views = []

        def update_view(current_page):
            mod_chunk = mod_chunks[current_page]
            options = [discord.SelectOption(label=mod_name, value=mod_name) for mod_name in mod_chunk]
            select = discord.ui.Select(placeholder=f"Select a mod (Page {current_page + 1}/{len(mod_chunks)})", options=options)
            select.callback = lambda interaction: select_callback(interaction, select.values[0])

            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="prev_button", disabled=current_page == 0)
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next_button", disabled=current_page == len(mod_chunks) - 1)

            async def prev_callback(interaction: discord.Interaction):
                nonlocal current_page
                current_page -= 1
                await interaction.response.edit_message(view=update_view(current_page))

            async def next_callback(interaction: discord.Interaction):
                nonlocal current_page
                current_page += 1
                await interaction.response.edit_message(view=update_view(current_page))

            prev_button.callback = prev_callback
            next_button.callback = next_callback

            view = discord.ui.View()
            view.add_item(select)
            view.add_item(install_button)
            view.add_item(prev_button)
            view.add_item(next_button)
            return view

        if mod_chunks:
            await interaction.response.send_message("Please select a mod:", view=update_view(current_page))
        else:
            await interaction.response.send_message("No mods found on the server.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModsCog(bot))