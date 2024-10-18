import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import shutil
import requests
import zipfile
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/mods.log')

class ModsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.mod_portal_username = self.config_manager.get('factorio_mod_portal.username')
        self.mod_portal_token = self.config_manager.get('factorio_mod_portal.token')
        self.mod_portal_api_url = 'https://mods.factorio.com/api'
        self.mod_path = self.config_manager.get('factorio_mod_portal.mod_path')
        self.mod_list_file = os.path.join(self.mod_path, 'mod-list.json')
        logger.info("ModsCog initialized")

    async def get_mod_details(self, mod_name):
        """Retrieve mod details from the Factorio mod portal API."""
        url = f"{self.mod_portal_api_url}/mods/{mod_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Failed to retrieve mod details for {mod_name}. Status code: {response.status}")
                    return None

    def update_mod_list(self, mod_name, action):
        """Update the mod-list.json file based on the action performed."""
        try:
            with open(self.mod_list_file, 'r') as file:
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

            with open(self.mod_list_file, 'w') as file:
                json.dump(mod_list, file, indent=4)
            logger.info(f"Updated mod list: {action} {mod_name}")
        except Exception as e:
            logger.error(f"Error updating mod list: {str(e)}")

    def get_mod_name_from_zip(self, file_path):
        """Extract the mod name from the mod zip file."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                for file_name in zip_file.namelist():
                    if file_name.endswith('info.json'):
                        with zip_file.open(file_name) as info_file:
                            info_data = json.load(info_file)
                            return info_data.get('name')
            logger.warning(f"Could not find mod name in zip file: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting mod name from zip: {str(e)}")
            return None

    @app_commands.command(name="mods", description="Manage mods using a dropdown menu")
    async def mods(self, interaction: discord.Interaction):
        mods_list = self.get_installed_mods()

        if not mods_list:
            await interaction.response.send_message("No mods found on the server.", ephemeral=True)
            logger.info("No mods found on the server")
            return

        # Split the mods_list into chunks of 25 mods
        mod_chunks = [mods_list[i:i + 25] for i in range(0, len(mods_list), 25)]

        install_button = discord.ui.Button(label="Install", style=discord.ButtonStyle.primary, custom_id="install_button")
        install_button.callback = lambda interaction: interaction.response.send_modal(InstallModal(self.config_manager, self.update_mod_list, self.get_mod_name_from_zip))

        async def select_callback(interaction: discord.Interaction, selected_mod):
            enable_button = discord.ui.Button(label="Enable", style=discord.ButtonStyle.success, custom_id="enable_button")
            disable_button = discord.ui.Button(label="Disable", style=discord.ButtonStyle.secondary, custom_id="disable_button")
            remove_button = discord.ui.Button(label="Remove", style=discord.ButtonStyle.danger, custom_id="remove_button")

            async def enable_callback(interaction: discord.Interaction):
                with open(self.mod_list_file, 'r') as file:
                    mod_list = json.load(file)
                    mod_info = next((mod for mod in mod_list["mods"] if mod["name"] == selected_mod), None)
                    if mod_info and mod_info['enabled']:
                        await interaction.response.edit_message(content=f"Mod {selected_mod} is already enabled.", view=view)
                        logger.info(f"Mod {selected_mod} is already enabled")
                        return

                self.update_mod_list(selected_mod, 'enable')
                await interaction.response.edit_message(content=f"Enabled mod: {selected_mod}", view=view)
                logger.info(f"Enabled mod: {selected_mod}")

            async def disable_callback(interaction: discord.Interaction):
                with open(self.mod_list_file, 'r') as file:
                    mod_list = json.load(file)
                    mod_info = next((mod for mod in mod_list["mods"] if mod["name"] == selected_mod), None)
                    if mod_info and not mod_info['enabled']:
                        await interaction.response.edit_message(content=f"Mod {selected_mod} is already disabled.", view=view)
                        logger.info(f"Mod {selected_mod} is already disabled")
                        return

                self.update_mod_list(selected_mod, 'disable')
                await interaction.response.edit_message(content=f"Disabled mod: {selected_mod}", view=view)
                logger.info(f"Disabled mod: {selected_mod}")

            async def remove_callback(interaction: discord.Interaction):
                self.update_mod_list(selected_mod, 'remove')
                mod_file = os.path.join(self.mod_path, f"{selected_mod}.zip")
                if os.path.exists(mod_file):
                    os.remove(mod_file)
                    logger.info(f"Removed mod file: {mod_file}")
                await interaction.response.edit_message(content=f"Removed mod: {selected_mod}", view=view)
                logger.info(f"Removed mod: {selected_mod}")

            enable_button.callback = enable_callback
            disable_button.callback = disable_callback
            remove_button.callback = remove_callback

            view = discord.ui.View()
            view.add_item(enable_button)
            view.add_item(disable_button)
            view.add_item(remove_button)
            view.add_item(install_button)

            await interaction.response.edit_message(content=f"Selected mod: {selected_mod}", view=view)
            logger.info(f"Selected mod: {selected_mod}")

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
                logger.info(f"Moved to previous page: {current_page + 1}")

            async def next_callback(interaction: discord.Interaction):
                nonlocal current_page
                current_page += 1
                await interaction.response.edit_message(view=update_view(current_page))
                logger.info(f"Moved to next page: {current_page + 1}")

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
            logger.info("Mod selection menu displayed")
        else:
            await interaction.response.send_message("No mods found on the server.", ephemeral=True)
            logger.info("No mods found on the server")

    def get_installed_mods(self):
        if os.path.exists(self.mod_list_file):
            with open(self.mod_list_file, 'r') as file:
                mod_list = json.load(file)
                return [mod["name"] for mod in mod_list["mods"]]
        else:
            logger.warning(f"Mod list file not found: {self.mod_list_file}")
            return []

class InstallModal(discord.ui.Modal):
    def __init__(self, config_manager, update_mod_list_func, get_mod_name_from_zip_func):
        super().__init__(title="Install Addon")
        self.config_manager = config_manager
        self.update_mod_list = update_mod_list_func
        self.get_mod_name_from_zip = get_mod_name_from_zip_func
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
        parts = addon_url.split('/')
        mod_name = parts[-1]

        mod_details = await self.get_mod_details(mod_name)
        if mod_details is None:
            await interaction.response.send_message(f"Failed to retrieve mod details for {mod_name}.", ephemeral=True)
            logger.warning(f"Failed to retrieve mod details for {mod_name}")
            return

        latest_release = mod_details['releases'][-1]
        download_url = latest_release['download_url']
        file_name = latest_release['file_name']
        version = latest_release['version']

        download_url = f"https://mods.factorio.com{download_url}?username={self.config_manager.get('factorio_mod_portal.username')}&token={self.config_manager.get('factorio_mod_portal.token')}"
        
        try:
            with requests.get(download_url, stream=True) as req:
                if req.status_code == 200:
                    target_file = os.path.join(self.config_manager.get('factorio_mod_portal.mod_path'), file_name)
                    with open(target_file, "wb") as target:
                        shutil.copyfileobj(req.raw, target)
                        target.flush()
                    mod_name = self.get_mod_name_from_zip(target_file)
                    if mod_name:
                        self.update_mod_list(mod_name, 'add')
                        await interaction.response.send_message(f"Mod {mod_name} downloaded and installed successfully.", ephemeral=True)
                        logger.info(f"Mod {mod_name} downloaded and installed successfully")
                    else:
                        await interaction.response.send_message(f"Failed to extract mod name from the downloaded file.", ephemeral=True)
                        logger.error(f"Failed to extract mod name from the downloaded file: {file_name}")
                else:
                    await interaction.response.send_message(f"Failed to download mod. Status code: {req.status_code}", ephemeral=True)
                    logger.error(f"Failed to download mod. Status code: {req.status_code}")
        except Exception as e:
            await interaction.response.send_message(f"An error occurred while downloading the mod: {str(e)}", ephemeral=True)
            logger.error(f"Error downloading mod: {str(e)}")

    async def get_mod_details(self, mod_name):
        url = f"https://mods.factorio.com/api/mods/{mod_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Failed to retrieve mod details for {mod_name}. Status code: {response.status}")
                    return None

async def setup(bot):
    await bot.add_cog(ModsCog(bot))
    logger.info("ModsCog added to bot")