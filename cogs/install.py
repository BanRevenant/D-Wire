import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
import re
import json  # Added this import
import tarfile
import subprocess
from typing import Optional, Dict
from logger import setup_logger

logger = setup_logger(__name__, 'logs/install.log')

FACTORIO_STABLE_URL = "https://factorio.com/get-download/stable/headless/linux64"
FACTORIO_LATEST_URL = "https://factorio.com/get-download/latest/headless/linux64"

class InstallModal(discord.ui.Modal, title='Installation Location'):
    def __init__(self, default_path: str):
        super().__init__()
        self.install_path = discord.ui.TextInput(
            label='Installation Path',
            placeholder='Enter the installation path...',
            default=default_path,
            style=discord.TextStyle.long,
            required=True,
            max_length=1024
        )
        self.add_item(self.install_path)
        self.user_path = None

    async def on_submit(self, interaction: discord.Interaction):
        self.user_path = self.install_path.value
        await interaction.response.defer()

class ConfirmLocationView(discord.ui.View):
    def __init__(self, install_path: str):
        super().__init__()
        self.install_path = install_path
        self.confirmed = None

    @discord.ui.button(label='Yes, location is correct', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.disable_all_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label='No, change location', style=discord.ButtonStyle.red)
    async def change(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        modal = InstallModal(self.install_path)
        await interaction.response.send_modal(modal)
        await modal.wait()
        self.install_path = modal.user_path
        self.disable_all_buttons()
        await interaction.message.edit(view=self)
        self.stop()

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

class VersionSelectView(discord.ui.View):
    def __init__(self, versions: Dict[str, str]):
        super().__init__()
        self.selected_version = None
        self.versions = versions

        # Add version buttons
        self.add_item(discord.ui.Button(
            label=f"Stable ({versions['stable']})",
            style=discord.ButtonStyle.green,
            custom_id="stable"
        ))
        self.add_item(discord.ui.Button(
            label=f"Latest ({versions['latest']})",
            style=discord.ButtonStyle.primary,  # Changed from blue to primary
            custom_id="latest"
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        button_id = interaction.data["custom_id"]
        if button_id in ["stable", "latest"]:
            self.selected_version = button_id
            self.disable_all_buttons()
            await interaction.response.edit_message(view=self)
            self.stop()
        return True

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

class InstallCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.installing = False
        logger.info("InstallCog initialized")

    async def check_url_version(self, url: str) -> Optional[str]:
        """Check URL and extract version number."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}  # Use a standard user agent
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=False, headers=headers) as response:
                    if response.status == 302:  # We want the redirect URL
                        redirect_url = response.headers.get('Location', '')
                        logger.debug(f"Redirect URL: {redirect_url}")
                        # Extract version from factorio-headless_linux_X.X.XX.tar.xz
                        version_match = re.search(r'factorio-headless_linux_([0-9.]+)\.tar\.xz', redirect_url)
                        if version_match:
                            version = version_match.group(1)
                            logger.info(f"Found version: {version}")
                            return version
                    else:
                        logger.error(f"Expected redirect, got status {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error checking version for URL {url}: {str(e)}")
            return None

    async def get_versions(self) -> Dict[str, str]:
        """Get available versions for both stable and latest."""
        try:
            stable = await self.check_url_version(FACTORIO_STABLE_URL)
            latest = await self.check_url_version(FACTORIO_LATEST_URL)
            
            if not stable and not latest:
                logger.error("Failed to get any versions")
                return {'stable': None, 'latest': None}
            
            versions = {
                'stable': stable,
                'latest': latest
            }
            
            logger.info(f"Retrieved versions: {versions}")
            return versions
        except Exception as e:
            logger.error(f"Error getting versions: {str(e)}")
            return {'stable': None, 'latest': None}
    
    def check_permissions(self, path: str) -> bool:
        """Check if we have permissions to write to the specified path."""
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, '.permission_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"Permission check failed for path {path}: {str(e)}")
            return False

    def check_dependencies(self) -> tuple[bool, list[str]]:
        """Check if required system utilities are available."""
        required_utils = ['curl', 'tar']
        missing = []
        
        for util in required_utils:
            try:
                subprocess.run(['which', util], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                missing.append(util)
        
        return len(missing) == 0, missing

    async def download_with_progress(self, url: str, path: str, message_func) -> bool:
        """Download file with progress updates."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download: HTTP {response.status}")
                        return False

                    file_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    chunk_size = 1024 * 1024  # 1MB chunks
                    
                    message = await message_func()
                    last_update_time = 0  # Track last update time
                    
                    embed = discord.Embed(
                        title="Downloading Factorio Server",
                        description="Download in progress...",
                        color=discord.Color.blue()
                    )
                    await message.edit(embed=embed)

                    with open(path, 'wb') as f:
                        last_update = 0
                        async for chunk in response.content.iter_chunked(chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress every 5% and not more often than every second
                            current_time = asyncio.get_event_loop().time()
                            if file_size and (current_time - last_update_time >= 1.0):
                                progress = (downloaded / file_size) * 100
                                if progress - last_update >= 5:
                                    last_update = progress
                                    last_update_time = current_time
                                    embed.description = f"Downloaded: {downloaded / 1024 / 1024:.1f}MB / {file_size / 1024 / 1024:.1f}MB ({progress:.1f}%)"
                                    try:
                                        await message.edit(embed=embed)
                                    except Exception as e:
                                        logger.error(f"Error updating progress: {e}")

            logger.info("Download completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during download: {str(e)}")
            return False

    async def extract_with_progress(self, tar_path: str, extract_path: str, message_func) -> bool:
        """Extract tar file with progress updates."""
        try:
            message = await message_func()
            last_update_time = 0
            
            embed = discord.Embed(
                title="Extracting Factorio Server",
                description="Preparing for extraction...",
                color=discord.Color.blue()
            )
            await message.edit(embed=embed)

            # Clear the destination directory if it exists
            if os.path.exists(extract_path):
                import shutil
                shutil.rmtree(extract_path)
                
            os.makedirs(extract_path, exist_ok=True)

            with tarfile.open(tar_path, 'r:xz') as tar:
                members = tar.getmembers()
                total_members = len(members)
                
                for i, member in enumerate(members, 1):
                    # Extract directly to the target directory without the extra factorio folder
                    if not member.name.startswith('factorio/'):
                        continue
                    
                    # Modify the path to remove the 'factorio/' prefix entirely
                    member.name = member.name[8:]  # Remove 'factorio/' completely
                    
                    if member.name:  # Only extract if there's a name left
                        tar.extract(member, extract_path)
                        
                    current_time = asyncio.get_event_loop().time()
                    if (i % 50 == 0 or i == total_members) and (current_time - last_update_time >= 1.0):
                        progress = (i / total_members) * 100
                        embed.description = f"Extracted {i} / {total_members} files ({progress:.1f}%)"
                        try:
                            await message.edit(embed=embed)
                            last_update_time = current_time
                        except Exception as e:
                            logger.error(f"Error updating extraction progress: {e}")

            logger.info("Extraction completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during extraction: {str(e)}")
            return False

    async def create_server_settings(self, config_path: str, message_func) -> bool:
        """Create server-settings.json with default settings."""
        try:
            message = await message_func()
            embed = discord.Embed(
                title="Creating Server Settings",
                description="Writing server configuration...",
                color=discord.Color.blue()
            )
            await message.edit(embed=embed)

            settings = {
                "name": "D-Wire Server",
                "description": "For help or information on D-Wire setup, see Floor Wardens Discord",
                "tags": ["Softmodded", "D-Wire"],
                "max_players": 0,
                "visibility": {
                    "public": True,
                    "lan": True
                },
                "username": "",
                "token": "",
                "game_password": "",
                "require_user_verification": True,
                "max_upload_in_kilobytes_per_second": 0,
                "max_upload_slots": 5,
                "minimum_latency_in_ticks": 0,
                "ignore_player_limit_for_returning_players": False,
                "allow_commands": "admins-only",
                "autosave_interval": 10,
                "autosave_slots": 5,
                "afk_autokick_interval": 0,
                "auto_pause": True,
                "only_admins_can_pause_the_game": True,
                "autosave_only_on_server": True,
                "non_blocking_saving": False,
                "minimum_segment_size": 25,
                "minimum_segment_size_peer_count": 20,
                "maximum_segment_size": 100,
                "maximum_segment_size_peer_count": 10
            }

            # Get RCON settings from config
            rcon_settings = {
                "port": self.config_manager.get('factorio_server.default_rcon_port'),
                "password": self.config_manager.get('factorio_server.default_rcon_password')
            }
            settings.update(rcon_settings)

            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(settings, f, indent=2)

            embed.description = "Server configuration created successfully!"
            await message.edit(embed=embed)
            logger.info("Server settings created successfully")
            return True

        except Exception as e:
            logger.error(f"Error creating server settings: {str(e)}")
            return False

    @app_commands.command(name="install", description="Install the Factorio server")
    @app_commands.default_permissions(administrator=True)
    async def install(self, interaction: discord.Interaction):
        # Check if user is owner or has required role
        required_roles = ['Factorio-Admin', 'Factorio-Mod']
        if not (str(interaction.user.id) == self.bot.config_manager.get('discord.owner_id') or 
                any(role.name in required_roles for role in interaction.user.roles)):
            await interaction.response.send_message(
                "You need to be the bot owner or have the Factorio-Admin/Mod role to use this command.",
                ephemeral=True
            )
            return

        try:
            self.installing = True
            
            # Check dependencies
            deps_ok, missing_deps = self.check_dependencies()
            if not deps_ok:
                await interaction.response.send_message(
                    f"Missing required utilities: {', '.join(missing_deps)}. Please install them first.",
                    ephemeral=True
                )
                return

            # Get bot's directory and set install location
            bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            install_path = os.path.join(bot_dir, "factorio")
            
            # Update config with new install location
            self.config_manager.set('factorio_server.install_location', install_path)
            self.config_manager.save()

            # Create and send location confirmation view
            location_view = ConfirmLocationView(install_path)
            embed = discord.Embed(
                title="Confirm Installation Location",
                description=f"The server will be installed at:\n`{install_path}`\n\nIs this location correct?",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, view=location_view)
            
            # Wait for location confirmation
            await location_view.wait()
            
            if not hasattr(location_view, 'confirmed'):
                embed.description = "Installation timed out."
                await interaction.edit_original_response(embed=embed, view=None)
                return
                
            if not location_view.confirmed:
                install_path = location_view.install_path
                logger.info(f"Installation path changed to: {install_path}")

            # Check permissions
            if not self.check_permissions(install_path):
                embed = discord.Embed(
                    title="Installation Error",
                    description=f"Cannot write to `{install_path}`. Please check permissions.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            # Get versions
            versions = await self.get_versions()
            if not all(versions.values()):
                embed = discord.Embed(
                    title="Installation Error",
                    description="Failed to fetch Factorio versions. Please try again later.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            # Show version selection
            version_view = VersionSelectView(versions)
            embed = discord.Embed(
                title="Select Factorio Version",
                description="Choose which version to install:",
                color=discord.Color.blue()
            )
            await interaction.edit_original_response(embed=embed, view=version_view)
            await version_view.wait()

            if not version_view.selected_version:
                embed.description = "Installation cancelled."
                embed.color = discord.Color.red()
                await interaction.edit_original_response(embed=embed, view=None)
                return



            # Start installation
            selected_url = FACTORIO_STABLE_URL if version_view.selected_version == "stable" else FACTORIO_LATEST_URL
            version = versions[version_view.selected_version]
            
            # Download
            bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            download_path = os.path.join(bot_dir, f"factorio_{version}.tar.xz")
            if not await self.download_with_progress(selected_url, download_path, interaction.original_response):
                embed = discord.Embed(
                    title="Installation Error",
                    description="Failed to download Factorio server.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            # Extract
            if not await self.extract_with_progress(download_path, install_path, interaction.original_response):
                embed = discord.Embed(
                    title="Installation Error",
                    description="Failed to extract Factorio server.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Create server settings in the installed factorio directory
            config_path = os.path.join(install_path, "config/server-settings.json")
            logger.info(f"Creating server settings at: {config_path}")
            if not await self.create_server_settings(config_path, interaction.original_response):
                embed = discord.Embed(
                    title="Installation Error",
                    description="Failed to create server settings.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            # Create server settings
            config_path = os.path.join(install_path, 'factorio/config/server-settings.json')
            if not await self.create_server_settings(config_path, interaction.original_response):
                embed = discord.Embed(
                    title="Installation Error",
                    description="Failed to create server settings.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return

            # Clean up
            try:
                os.remove(download_path)
                logger.info(f"Cleaned up download file: {download_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up download file: {str(e)}")

            # Installation complete
            embed = discord.Embed(
                title="Installation Complete",
                description=(
                    f"Factorio server version {version} has been installed successfully!\n\n"
                    "You can now use the following commands:\n"
                    "• `/startserver` - Start the Factorio server\n"
                    "• `/stopserver` - Stop the Factorio server\n\n"
                    "Make sure to check the server settings in the config files if needed."
                ),
                color=discord.Color.green()
            )
            await interaction.edit_original_response(embed=embed, view=None)
            logger.info("Installation completed successfully")

        except Exception as e:
            logger.error(f"Unexpected error during installation: {str(e)}")
            embed = discord.Embed(
                title="Installation Error",
                description=f"An unexpected error occurred:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)
        
        finally:
            self.installing = False

async def setup(bot):
    await bot.add_cog(InstallCog(bot))
    logger.info("InstallCog loaded")