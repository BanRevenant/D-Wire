import os
import zipfile
import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import re
import shutil
import tempfile
from datetime import datetime
from logger import setup_logger

logger = setup_logger(__name__, 'logs/augment.log')

class SaveSelectModal(discord.ui.Modal, title='Select Save File'):
    def __init__(self, save_names):
        super().__init__()
        self.save_names = save_names
        self.selected_save = None

        self.save_input = discord.ui.TextInput(
            label='Save File Name',
            placeholder='Enter the save name (without .zip)',
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.add_item(self.save_input)

    async def on_submit(self, interaction: discord.Interaction):
        input_name = self.save_input.value
        valid_name = f"{input_name}.zip"
        
        if valid_name in self.save_names:
            self.selected_save = valid_name
            await interaction.response.defer()
        else:
            available_saves = "\n".join(f"• {save[:-4]}" for save in self.save_names)
            await interaction.response.send_message(
                f"Save file not found. Available saves:\n```\n{available_saves}\n```",
                ephemeral=True
            )

class AugmentationError(Exception):
    """Custom exception for augmentation errors"""
    pass

class AugmentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.softmod_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "softmod")
        self.augmenting = False
        self.backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "save_backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        logger.info("AugmentCog initialized")

    def create_backup(self, save_path: str) -> str:
        """Create a backup of the save file before modification."""
        save_name = os.path.basename(save_path)
        backup_name = f"BeforeAug_{save_name}"
        # Use backup_dir instead of saves directory
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        try:
            shutil.copy2(save_path, backup_path)
            logger.info(f"Created backup at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            raise AugmentationError(f"Failed to create backup: {str(e)}")

    def validate_lua_file(self, file_path: str) -> tuple[bool, str]:
        """Basic validation of Lua file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Just check if file is empty
            if not content.strip():
                return False, "File is empty"
                
            return True, "Valid"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    def validate_save_structure(self, zip_path: str) -> tuple[bool, str, str | None]:
        """Validate the save file structure and find control.lua."""
        try:
            logger.debug(f"Validating save structure for: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                logger.debug(f"Files in save: {file_list}")
                
                # Find control.lua
                control_path = None
                for path in file_list:
                    logger.debug(f"Checking path: {path}")
                    if path.endswith('control.lua'):
                        control_path = path
                        logger.debug(f"Found control.lua at: {control_path}")
                        break
                
                if not control_path:
                    logger.debug("No control.lua found in save file")
                    # Create control.lua if it doesn't exist
                    # Get the first directory in the save
                    save_dirs = [name for name in file_list if name.endswith('/')]
                    if save_dirs:
                        main_dir = save_dirs[0]
                        control_path = os.path.join(main_dir, 'control.lua')
                        logger.debug(f"Will create control.lua at: {control_path}")
                        return True, "Will create control.lua", control_path
                    else:
                        logger.debug("No valid save directory structure found")
                        return False, "Invalid save file structure - no save directory found", None
                
                return True, "Valid save structure", control_path
                    
        except zipfile.BadZipFile:
            logger.error("File is not a valid zip file")
            return False, "Invalid or corrupted zip file", None
        except Exception as e:
            logger.error(f"Error during save validation: {str(e)}")
            return False, f"Error validating save file: {str(e)}", None

    def get_softmod_files(self) -> tuple[list[str], list[tuple[str, str]]]:
        """Get list of valid .lua files in softmod directory."""
        valid_files = []
        invalid_files = []
        
        try:
            if not os.path.exists(self.softmod_dir):
                raise AugmentationError("Softmod directory not found")
                
            files = [f for f in os.listdir(self.softmod_dir) if f.endswith('.lua')]
            
            for file in files:
                file_path = os.path.join(self.softmod_dir, file)
                is_valid, error = self.validate_lua_file(file_path)
                
                if is_valid:
                    valid_files.append(file)
                else:
                    invalid_files.append((file, error))
                    logger.warning(f"Invalid Lua file {file}: {error}")
                    
            return valid_files, invalid_files
            
        except Exception as e:
            logger.error(f"Error processing softmod files: {str(e)}")
            raise AugmentationError(f"Error processing softmod files: {str(e)}")

    async def update_save_file(self, save_path: str, progress_message: discord.Message) -> tuple[bool, list[str], str]:
        """Update the save file with softmod content."""
        temp_dir = None
        try:
            # Get and validate softmod files first
            valid_files, invalid_files = self.get_softmod_files()
            if not valid_files:
                if invalid_files:
                    error_details = "\n".join(f"• {file}: {error}" for file, error in invalid_files)
                    raise AugmentationError(f"No valid softmod files found. Issues:\n{error_details}")
                else:
                    raise AugmentationError("No softmod files found")

            # Create new save name with Dwire_ prefix
            save_dir = os.path.dirname(save_path)
            old_save_name = os.path.basename(save_path)
            new_save_name = f"Dwire_{old_save_name}"
            new_save_path = os.path.join(save_dir, new_save_name)
            
            temp_dir = tempfile.mkdtemp()
            
            async def update_progress(status: str):
                embed = discord.Embed(
                    title="Augmenting Save File",
                    description=status,
                    color=discord.Color.blue()
                )
                await progress_message.edit(embed=embed)

            # Validate save structure
            await update_progress("Validating save file structure...")
            is_valid, error_msg, control_path = self.validate_save_structure(save_path)
            if not is_valid:
                raise AugmentationError(error_msg)

            # Initial control.lua content
            init_control_content = """local fw_stats = require("fw_stats")

    -- Register events directly without conditions
    script.on_event(defines.events.on_entity_died, fw_stats.events[defines.events.on_entity_died])
    script.on_event(defines.events.on_player_died, fw_stats.events[defines.events.on_player_died])

    """

            # Prepare requires block (without softmod folder)
            requires_block = [
                "\n-- BEGIN D-WIRE SOFTMOD",
                "-- Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                *[f'require("{os.path.splitext(file)[0]}")' for file in valid_files],
                "-- END D-WIRE SOFTMOD\n"
            ]

            # Create the new save file
            with zipfile.ZipFile(save_path, 'r') as src_zip:
                with zipfile.ZipFile(new_save_path, 'w', compression=zipfile.ZIP_DEFLATED) as dest_zip:
                    # Copy all existing files except ones we're updating
                    for item in src_zip.infolist():
                        if not any(item.filename.endswith(f) for f in valid_files + ['control.lua']):
                            data = src_zip.read(item.filename)
                            dest_zip.writestr(item, data)

                    # Add/update Lua files in game folder
                    save_dir = os.path.dirname(control_path)
                    for file in valid_files:
                        with open(os.path.join(self.softmod_dir, file), 'rb') as f:
                            dest_zip.writestr(
                                os.path.join(save_dir, file),
                                f.read()
                            )

                    # Create new control.lua
                    try:
                        existing_control = src_zip.read(control_path).decode('utf-8')
                        # Remove any existing D-WIRE block
                        if "-- BEGIN D-WIRE SOFTMOD" in existing_control:
                            pattern = r"-- BEGIN D-WIRE SOFTMOD.*?-- END D-WIRE SOFTMOD\n"
                            existing_control = re.sub(pattern, "", existing_control, flags=re.DOTALL)
                    except KeyError:
                        existing_control = ""

                    # Combine control.lua content
                    if "fw_stats" not in existing_control:
                        new_content = init_control_content + existing_control + "\n".join(requires_block)
                    else:
                        new_content = existing_control + "\n".join(requires_block)

                    dest_zip.writestr(control_path, new_content.encode('utf-8'))

            return True, valid_files, new_save_name

        except Exception as e:
            logger.error(f"Error updating save file: {str(e)}")
            raise AugmentationError(f"Error updating save file: {str(e)}")
            
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    @app_commands.command(name="augment", description="Augment a Factorio save with softmod files")
    @app_commands.default_permissions(administrator=True)
    async def augment(self, interaction: discord.Interaction):
        """Augment a Factorio save with softmod files."""
        # Check if user has required role
        if not any(role.name == 'Factorio-Admin' for role in interaction.user.roles):
            await interaction.response.send_message(
                "You need the Factorio-Admin role to use this command.",
                ephemeral=True
            )
            return

        # Check if already augmenting
        if self.augmenting:
            await interaction.response.send_message(
                "An augmentation is already in progress.",
                ephemeral=True
            )
            return

        try:
            # Get install location and build saves path
            install_location = self.config_manager.get('factorio_server.install_location')
            saves_dir = os.path.join(install_location, 'saves')
            
            logger.debug(f"Install location: {install_location}")
            logger.debug(f"Looking for saves in: {saves_dir}")
            logger.debug(f"Directory exists: {os.path.exists(saves_dir)}")

            if not os.path.exists(saves_dir):
                await interaction.response.send_message(
                    f"Saves directory not found at {saves_dir}",
                    ephemeral=True
                )
                return

            # Get list of save files
            saves = [f for f in os.listdir(saves_dir) if f.endswith('.zip')]
            if not saves:
                await interaction.response.send_message(
                    "No save files found.",
                    ephemeral=True
                )
                return

            # Show save selection modal
            modal = SaveSelectModal(saves)
            await interaction.response.send_modal(modal)
            await modal.wait()

            if not modal.selected_save:
                return

            self.augmenting = True
            save_path = os.path.join(saves_dir, modal.selected_save)

            # Send initial status message
            embed = discord.Embed(
                title="Augmenting Save File",
                description=f"Starting augmentation of: {modal.selected_save}",
                color=discord.Color.blue()
            )
            status_message = await interaction.followup.send(embed=embed, wait=True)

            # Create backup
            backup_path = self.create_backup(save_path)
            backup_name = os.path.basename(backup_path)

            # Update save file
            success, added_files, new_save_name = await self.update_save_file(
                save_path,
                status_message
            )

            # Create final embed
            if success:
                embed = discord.Embed(
                    title="Augmentation Complete",
                    description=(
                        f"Successfully created: {new_save_name}\n"
                        f"From original save: {modal.selected_save}\n"
                        f"Backup created as: {backup_name}"
                    ),
                    color=discord.Color.green()
                )
                
                if added_files:
                    files_list = "\n".join([f"• {file}" for file in added_files])
                    embed.add_field(
                        name="Added/Updated Files",
                        value=f"```\n{files_list}\n```",
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="Augmentation Failed",
                    description="Failed to modify save file. Check logs for details.",
                    color=discord.Color.red()
                )

            await status_message.edit(embed=embed)

        except AugmentationError as e:
            logger.error(f"Augmentation error: {str(e)}")
            embed = discord.Embed(
                title="Augmentation Error",
                description=str(e),
                color=discord.Color.red()
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            embed = discord.Embed(
                title="Unexpected Error",
                description=f"An unexpected error occurred:\n```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)

        finally:
            self.augmenting = False

async def setup(bot):
    await bot.add_cog(AugmentCog(bot))
    logger.info("AugmentCog loaded")