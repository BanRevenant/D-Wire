import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os
import tarfile
import asyncio
import re
from datetime import datetime
from factorio_rcon import RCONClient
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/update.log')

class UpdateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.last_modified = None
        self.check_for_updates.start()
        self.update_channel_id = self.config_manager.get('discord.channel_id')
        self.rcon_client = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10  # seconds
        
        # RCON configuration
        self.rcon_host = self.config_manager.get('factorio_server.default_bind_address')
        self.rcon_port = self.config_manager.get('factorio_server.default_rcon_port')
        self.rcon_password = self.config_manager.get('factorio_server.default_rcon_password')
        logger.info("UpdateCog initialized")

    def cog_unload(self):
        self.check_for_updates.cancel()
        logger.info("Update check task cancelled")

    async def connect_rcon(self):
        try:
            self.rcon_client = RCONClient(self.rcon_host, self.rcon_port, self.rcon_password)
            await self.bot.loop.run_in_executor(None, self.rcon_client.connect)
            logger.info("RCON client connected successfully.")
            self.reconnect_attempts = 0  # Reset attempts on successful connection
            return True
        except Exception as e:
            logger.error(f"Error connecting to RCON: {str(e)}")
            self.rcon_client = None
            return False

    async def reconnect_rcon(self):
        while self.reconnect_attempts < self.max_reconnect_attempts:
            logger.info(f"Attempting to reconnect RCON (Attempt {self.reconnect_attempts + 1})...")
            success = await self.connect_rcon()
            if success:
                return True
            self.reconnect_attempts += 1
            await asyncio.sleep(self.reconnect_delay)
        
        logger.error("Max RCON reconnection attempts reached. Giving up.")
        return False

    async def disconnect_rcon(self):
        if self.rcon_client:
            try:
                await self.bot.loop.run_in_executor(None, self.rcon_client.close)
                logger.info("RCON client disconnected.")
            except Exception as e:
                logger.error(f"Error disconnecting RCON: {str(e)}")
            finally:
                self.rcon_client = None

    async def check_version(self):
        """Check for new version of Factorio"""
        url = "https://www.factorio.com/get-download/stable/headless/linux64"
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as response:
                return response.headers.get("Last-Modified")
            
    async def get_server_version(self):
        """Get the current server version from the log file"""
        try:
            base_path = self.config_manager.get('factorio_server.install_location')
            log_file = os.path.join(base_path, "logs/verbose.log")
            
            if not os.path.exists(log_file):
                logger.warning("Server log file not found")
                return "Version Unknown (Log not found)"
                
            with open(log_file, 'r') as f:
                for line in f:
                    match = re.search(r'Factorio (\d+\.\d+\.\d+) \(build (\d+)', line)
                    if match:
                        version, build = match.groups()
                        return f"{version} (build {build})"
            logger.warning("Version information not found in log file")
            return "Version Unknown (Not found in log)"
        except Exception as e:
            logger.error(f"Error reading server version: {str(e)}")
            return f"Version Unknown (Error: {str(e)})"


    @tasks.loop(hours=1)
    async def check_for_updates(self):
        try:
            current_version = await self.check_version()
            if self.last_modified is None:
                self.last_modified = current_version
                logger.info("Initial version check completed")
            elif current_version != self.last_modified:
                logger.info("New Factorio version detected")
                channel = self.bot.get_channel(int(self.update_channel_id))
                if channel:
                    await channel.send("🔄 New Factorio version detected! Starting automatic update process...")
                    logger.info("Starting automatic update process")
                    await self.perform_update_sequence()
                self.last_modified = current_version
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()
        logger.info("Update check task is ready to start")

    async def perform_update_sequence(self, interaction: discord.Interaction = None):
        # Get initial server version
        initial_version = await self.get_server_version()
        
        embed = discord.Embed(
            title="Factorio Server Auto-Update Status",
            description="Starting update process...",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if interaction:
            message = await interaction.followup.send(embed=embed)
            logger.info(f"Update sequence started by user interaction")
        else:
            channel = self.bot.get_channel(int(self.update_channel_id))
            message = await channel.send(embed=embed)
            logger.info("Automatic update sequence started")

        status_fields = []

        # Initialize all fields with pending status
        status_fields.extend([
            {"name": "Detected Server Version", "value": initial_version, "inline": False},
            {"name": "Game Save", "value": "⏳ Checking server status...", "inline": False},
            {"name": "Server Shutdown", "value": "⏳ Waiting...", "inline": False},
            {"name": "Server Update", "value": "⏳ Waiting...", "inline": False},
            {"name": "Server Startup", "value": "⏳ Waiting...", "inline": False}
        ])
        
        # Update embed with all fields
        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        # Step 1: Check server status and save if running
        server_management = self.bot.get_cog('ServerManagementCog')
        server_running = server_management and server_management.is_server_running()

        if server_running:
            status_fields[1]["value"] = "🔄 Saving game..."
            embed.clear_fields()
            for field in status_fields:
                embed.add_field(**field)
            await message.edit(embed=embed)

            save_response = None
            for attempt in range(2):
                if not self.rcon_client:
                    await self.connect_rcon()
                try:
                    save_response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, "/server-save")
                    break
                except Exception as e:
                    logger.error(f"Error sending RCON command (Attempt {attempt + 1}): {str(e)}")
                    await self.disconnect_rcon()
                    if attempt == 0:
                        await asyncio.sleep(1)

            if save_response is not None:
                status_fields[1]["value"] = "✅ Game saved successfully"
                logger.info("Game saved successfully")
            else:
                status_fields[1]["value"] = "❌ Failed to save game"
                logger.error("Failed to save game")
        else:
            status_fields[1]["value"] = "ℹ️ Server not running - skipping save"
            logger.info("Server not running - skipping save step")

        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)
        await asyncio.sleep(2)

        # Step 2: Stop the server (if running)
        status_fields[2]["value"] = "🔄 Checking server status..."
        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        if server_running:
            if server_management:
                server_pid = server_management.server_pid
                stop_result = await server_management.stop_server()
                status_fields[2]["value"] = f"✅ Server stopped (PID: {server_pid})" if "successfully" in stop_result else f"❌ {stop_result}"
                logger.info(f"Server stop attempt completed with result: {stop_result}")
            else:
                status_fields[2]["value"] = "❌ Server management not available"
                logger.error("Server management cog not available")
        else:
            status_fields[2]["value"] = "ℹ️ Server already stopped"
            logger.info("Server already stopped - skipping stop step")

        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        # Step 3: Update the server
        install_location = self.config_manager.get('factorio_server.install_location')
        os.makedirs(install_location, exist_ok=True)
        logger.info(f"Ensuring install location exists: {install_location}")

        try:
            status_fields[3]["value"] = "🔄 Downloading update..."
            embed.clear_fields()
            for field in status_fields:
                embed.add_field(**field)
            await message.edit(embed=embed)

            download_url = 'https://www.factorio.com/get-download/stable/headless/linux64'
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        file_name = 'factorio-headless-linux64.tar.xz'
                        file_path = os.path.join(install_location, file_name)
                        logger.info(f"Downloading update to: {file_path}")

                        with open(file_path, 'wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                f.write(chunk)

                        status_fields[3]["value"] = "🔄 Extracting files..."
                        embed.clear_fields()
                        for field in status_fields:
                            embed.add_field(**field)
                        await message.edit(embed=embed)

                        # Extract files
                        logger.info("Extracting update files")
                        with tarfile.open(file_path, 'r:xz') as tar:
                            for member in tar.getmembers():
                                if member.name.startswith('factorio/'):
                                    member.name = member.name[9:]  # Remove 'factorio/' prefix
                                    tar.extract(member, install_location)

                        status_fields[3]["value"] = "✅ Update completed successfully"
                        embed.clear_fields()
                        for field in status_fields:
                            embed.add_field(**field)
                        await message.edit(embed=embed)

                        # Extract files
                        logger.info("Extracting update files")
                        with tarfile.open(file_path, 'r:xz') as tar:
                            for member in tar.getmembers():
                                if member.name.startswith('factorio/'):
                                    member.name = member.name[9:]  # Remove 'factorio/' prefix
                                    tar.extract(member, install_location)

                        # Set permissions
                        factorio_exe = os.path.join(install_location, 'bin', 'x64', 'factorio')
                        os.chmod(factorio_exe, 0o755)
                        logger.info(f"Set executable permissions on: {factorio_exe}")

                        # Clean up
                        os.remove(file_path)
                        logger.info("Cleaned up download file")

                        status_fields[3]["value"] = "✅ Update completed successfully"  # Changed from [2] to [3]
                        
                        # If update was successful, get and display new version
                        await asyncio.sleep(2)  # Give a moment for the server to update its log
                        new_version = await self.get_server_version()
                        status_fields[0]["value"] = f"{initial_version} → {new_version}"
                    else:
                        status_fields[2]["value"] = f"❌ Download failed (Status: {response.status})"
                        logger.error(f"Download failed with status: {response.status}")
        except Exception as e:
            status_fields[2]["value"] = f"❌ Update failed: {str(e)}"
            logger.error(f"Update failed: {str(e)}")
            logger.error(f"Stack trace: ", exc_info=True)

        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

    # Step 4: Start the server
        if server_running:  # Only try to start if it was running before
            status_fields[4]["value"] = "🔄 Starting server..."
            embed.clear_fields()
            for field in status_fields:
                embed.add_field(**field)
            await message.edit(embed=embed)

            if server_management:
                start_result = await server_management.start_server()
                logger.info(f"Start result: {start_result}")
                
                if "successfully" in start_result:
                    new_pid = server_management.server_pid
                    logger.info(f"Setting status fields - PID: {new_pid}")
                    
                    # Log current value
                    logger.info(f"Current startup field value: {status_fields[4]['value']}")
                    
                    status_fields[4]["value"] = f"🔄 Server started, waiting for initialization..."
                    logger.info(f"Set startup field to: {status_fields[4]['value']}")
                    
                    embed.clear_fields()
                    for field in status_fields:
                        embed.add_field(**field)
                    await message.edit(embed=embed)

                    # Wait for server to initialize and create log file
                    await asyncio.sleep(5)
                    
                    # Get new version after server has started
                    new_version = await self.get_server_version()
                    logger.info(f"New version detected: {new_version}")
                    
                    status_fields[0]["value"] = f"{initial_version} → {new_version}"
                    status_fields[4]["value"] = f"✅ Server started successfully (PID: {new_pid})"
                    logger.info(f"Updated startup field to: {status_fields[4]['value']}")
                    
                    # Update embed immediately after setting status
                    logger.info("Updating embed with final server status")
                    embed.clear_fields()
                    for field in status_fields:
                        embed.add_field(**field)
                    await message.edit(embed=embed)
                else:
                    status_fields[4]["value"] = f"❌ {start_result}"
                    logger.error(f"Failed to start server: {start_result}")
            else:
                status_fields[3]["value"] = "❌ Server management not available"
                logger.error("Server management not available for startup")
        else:
            status_fields[3]["value"] = "ℹ️ Server was not running - skipping start"
            logger.info("Server was not running - skipping start step")

        # Final color update only
        await asyncio.sleep(1)  # Small delay to ensure previous update is complete
        embed.color = discord.Color.green()
        await message.edit(embed=embed)
        logger.info("Update sequence completed")
        return message

    @app_commands.command(name='testupdate', description='Test the automatic update process')
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    async def testupdate(self, interaction: discord.Interaction):
        """Test the automatic update process"""
        await interaction.response.defer()
        logger.info(f"Test update initiated by {interaction.user.name}")
        await self.perform_update_sequence(interaction)

    @app_commands.command(name='update', description='Update the Factorio server to the latest version')
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        logger.info(f"Update command initiated by {interaction.user.name}")
        await self.perform_update_sequence(interaction)

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))
    logger.info("UpdateCog added to bot")