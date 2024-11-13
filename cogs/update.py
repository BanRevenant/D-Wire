import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os
import tarfile
import asyncio
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
        self.rcon_host = self.config_manager.get('factorio_server.rcon_host')
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
        url = "https://www.factorio.com/get-download/stable/headless/linux64"
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as response:
                return response.headers.get("Last-Modified")

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
            {"name": "Game Save", "value": "⏳ Connecting to server...", "inline": False},
            {"name": "Server Shutdown", "value": "⏳ Waiting...", "inline": False},
            {"name": "Server Update", "value": "⏳ Waiting...", "inline": False},
            {"name": "Server Startup", "value": "⏳ Waiting...", "inline": False}
        ])

        # Update embed with all fields
        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        # Step 1: Save the game via RCON
        server_management = self.bot.get_cog('ServerManagementCog')
        if not server_management or not server_management.is_server_running():
            status_fields[0]["value"] = "❌ Server is not running"
            embed.clear_fields()
            for field in status_fields:
                embed.add_field(**field)
            await message.edit(embed=embed)
            logger.warning("Update attempted while server was not running")
            return

        if not self.rcon_client:
            logger.info("Attempting to establish RCON connection")
            await self.reconnect_rcon()

        if self.rcon_client:
            try:
                status_fields[0]["value"] = "🔄 Saving game..."
                embed.clear_fields()
                for field in status_fields:
                    embed.add_field(**field)
                await message.edit(embed=embed)

                response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, "/server-save")
                logger.info(f"RCON command sent: /server-save")
                logger.info(f"RCON response: {response}")
                status_fields[0]["value"] = "✅ Game saved successfully"
            except Exception as e:
                status_fields[0]["value"] = f"❌ Failed to save game: {str(e)}"
                logger.error(f"Failed to save game: {str(e)}")
        else:
            status_fields[0]["value"] = "❌ Failed to connect to server"
            logger.error("Failed to establish RCON connection")

        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)
        await asyncio.sleep(5)
        await self.disconnect_rcon()

        # Step 2: Stop the server
        status_fields[1]["value"] = "🔄 Stopping server..."
        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        if server_management:
            server_pid = server_management.server_pid
            stop_result = await server_management.stop_server()
            status_fields[1]["value"] = f"✅ Server stopped (PID: {server_pid})" if "successfully" in stop_result else f"❌ {stop_result}"
            logger.info(f"Server stop attempt completed with result: {stop_result}")
        else:
            status_fields[1]["value"] = "❌ Server management not available"
            logger.error("Server management cog not available")

        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        # Step 3: Update the server
        install_location = self.config_manager.get('factorio_server.factorio_install_location')
        os.makedirs(install_location, exist_ok=True)
        logger.info(f"Ensuring install location exists: {install_location}")

        try:
            status_fields[2]["value"] = "🔄 Downloading update..."
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

                        status_fields[2]["value"] = "✅ Download complete\n🔄 Extracting files..."
                        embed.clear_fields()
                        for field in status_fields:
                            embed.add_field(**field)
                        await message.edit(embed=embed)

                        # Extract files
                        logger.info("Extracting update files")
                        with tarfile.open(file_path, 'r:xz') as tar:
                            tar.extractall(install_location)

                        # Set permissions
                        factorio_exe = os.path.join(install_location, 'factorio', 'bin', 'x64', 'factorio')
                        os.chmod(factorio_exe, 0o755)
                        logger.info(f"Set executable permissions on: {factorio_exe}")

                        # Clean up
                        os.remove(file_path)
                        logger.info("Cleaned up download file")

                        status_fields[2]["value"] = "✅ Update completed successfully"
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
        status_fields[3]["value"] = "🔄 Starting server..."
        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)

        if server_management:
            start_result = await server_management.start_server()
            if "successfully" in start_result:
                new_pid = server_management.server_pid
                status_fields[3]["value"] = f"✅ Server started successfully (PID: {new_pid})"
                logger.info(f"Server started with new PID: {new_pid}")
            else:
                status_fields[3]["value"] = f"❌ {start_result}"
                logger.error(f"Failed to start server: {start_result}")
        else:
            status_fields[3]["value"] = "❌ Server management not available"
            logger.error("Server management not available for startup")

        embed.color = discord.Color.green()
        embed.clear_fields()
        for field in status_fields:
            embed.add_field(**field)
        await message.edit(embed=embed)
        logger.info("Update sequence completed")
        return message

    @app_commands.command(name='testupdate', description='Test the automatic update process')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    async def testupdate(self, interaction: discord.Interaction):
        """Test the automatic update process"""
        await interaction.response.defer()
        logger.info(f"Test update initiated by {interaction.user.name}")
        await self.perform_update_sequence(interaction)

    @app_commands.command(name='update', description='Update the Factorio server to the latest version')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        logger.info(f"Update command initiated by {interaction.user.name}")
        await self.perform_update_sequence(interaction)

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))
    logger.info("UpdateCog added to bot")