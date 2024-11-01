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

    async def connect_rcon(self):
        try:
            self.rcon_client = RCONClient(self.rcon_host, self.rcon_port, self.rcon_password)
            await self.bot.loop.run_in_executor(None, self.rcon_client.connect)
            logger.info("RCON client connected successfully.")
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
        url = "https://www.factorio.com/get-download/latest/headless/linux64"
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as response:
                return response.headers.get("Last-Modified")

    @tasks.loop(hours=1)
    async def check_for_updates(self):
        try:
            current_version = await self.check_version()
            if self.last_modified is None:
                self.last_modified = current_version
            elif current_version != self.last_modified:
                logger.info("New Factorio version detected")
                channel = self.bot.get_channel(int(self.update_channel_id))
                if channel:
                    await channel.send("A new Factorio version is available! Use `/update` to update the server.")
                self.last_modified = current_version
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    async def perform_update_sequence(self, interaction: discord.Interaction = None):
        embed = discord.Embed(
            title="Factorio Server Auto-Update Status",
            description="Starting update process...",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if interaction:
            message = await interaction.followup.send(embed=embed)
        else:
            channel = self.bot.get_channel(int(self.update_channel_id))
            message = await channel.send(embed=embed)

        # Step 1: Save the game via RCON
        embed.add_field(
            name="Game Save",
            value="🔄 Connecting to server...",
            inline=False
        )
        await message.edit(embed=embed)

        server_management = self.bot.get_cog('ServerManagementCog')
        if not server_management or not server_management.is_server_running():
            embed.set_field_at(
                0,
                name="Game Save",
                value="❌ Server is not running",
                inline=False
            )
            await message.edit(embed=embed)
            return

        if not self.rcon_client:
            await self.reconnect_rcon()

        if self.rcon_client:
            try:
                response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, "/server-save")
                logger.info(f"RCON command sent: /server-save")
                logger.info(f"RCON response: {response}")
                embed.set_field_at(
                    0,
                    name="Game Save",
                    value="✅ Game saved successfully",
                    inline=False
                )
            except Exception as e:
                embed.set_field_at(
                    0,
                    name="Game Save",
                    value=f"❌ Failed to save game: {str(e)}",
                    inline=False
                )
                logger.error(f"Failed to save game: {str(e)}")
        else:
            embed.set_field_at(
                0,
                name="Game Save",
                value="❌ Failed to connect to server",
                inline=False
            )

        await message.edit(embed=embed)
        await asyncio.sleep(5)
        await self.disconnect_rcon()

        # Step 2: Stop the server
        embed.add_field(
            name="Server Shutdown",
            value="🔄 Stopping server...",
            inline=False
        )
        await message.edit(embed=embed)

        if server_management:
            server_pid = server_management.server_pid
            stop_result = await server_management.stop_server()
            embed.set_field_at(
                1,
                name="Server Shutdown",
                value=f"✅ Server stopped (PID: {server_pid})" if "successfully" in stop_result else f"❌ {stop_result}",
                inline=False
            )
        else:
            embed.set_field_at(
                1,
                name="Server Shutdown",
                value="❌ Server management not available",
                inline=False
            )
        await message.edit(embed=embed)

        # Step 3: Update the server
        embed.add_field(
            name="Server Update",
            value="🔄 Downloading update...",
            inline=False
        )
        await message.edit(embed=embed)

        install_location = self.config_manager.get('factorio_server.factorio_install_location')
        os.makedirs(install_location, exist_ok=True)

        try:
            download_url = 'https://www.factorio.com/get-download/latest/headless/linux64'
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        file_name = 'factorio-headless-linux64.tar.xz'
                        file_path = os.path.join(install_location, file_name)

                        with open(file_path, 'wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                f.write(chunk)

                        embed.set_field_at(
                            2,
                            name="Server Update",
                            value="✅ Download complete\n🔄 Extracting files...",
                            inline=False
                        )
                        await message.edit(embed=embed)

                        # Extract files
                        with tarfile.open(file_path, 'r:xz') as tar:
                            tar.extractall(install_location)

                        # Set permissions
                        factorio_exe = os.path.join(install_location, 'factorio', 'bin', 'x64', 'factorio')
                        os.chmod(factorio_exe, 0o755)

                        # Clean up
                        os.remove(file_path)

                        embed.set_field_at(
                            2,
                            name="Server Update",
                            value="✅ Update completed successfully",
                            inline=False
                        )
                    else:
                        embed.set_field_at(
                            2,
                            name="Server Update",
                            value=f"❌ Download failed (Status: {response.status})",
                            inline=False
                        )
        except Exception as e:
            embed.set_field_at(
                2,
                name="Server Update",
                value=f"❌ Update failed: {str(e)}",
                inline=False
            )
            logger.error(f"Update failed: {str(e)}")

        await message.edit(embed=embed)

        # Step 4: Start the server
        embed.add_field(
            name="Server Startup",
            value="🔄 Starting server...",
            inline=False
        )
        await message.edit(embed=embed)

        if server_management:
            start_result = await server_management.start_server()
            embed.set_field_at(
                3,
                name="Server Startup",
                value="✅ Server started successfully" if "successfully" in start_result else f"❌ {start_result}",
                inline=False
            )
        else:
            embed.set_field_at(
                3,
                name="Server Startup",
                value="❌ Server management not available",
                inline=False
            )

        embed.color = discord.Color.green()
        await message.edit(embed=embed)
        return message

    @app_commands.command(name='testupdate', description='Test the automatic update process')
    @app_commands.checks.has_permissions(administrator=True)
    async def testupdate(self, interaction: discord.Interaction):
        """Test the automatic update process"""
        await interaction.response.defer()
        logger.info(f"Test update initiated by {interaction.user.name}")
        await self.perform_update_sequence(interaction)

    @app_commands.command(name='update', description='Update the Factorio server to the latest version')
    @app_commands.checks.has_permissions(administrator=True)
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        logger.info(f"Update command initiated by {interaction.user.name}")
        await self.perform_update_sequence(interaction)

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))
    logger.info("UpdateCog added to bot")