import discord
from discord.ext import commands, tasks
from factorio_rcon import RCONClient
import asyncio
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/discord_to_server.log')

class DiscordToServerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.rcon_client = None
        self.rcon_host = self.config_manager.get('factorio_server.rcon_host')
        self.rcon_port = self.config_manager.get('factorio_server.default_rcon_port')
        self.rcon_password = self.config_manager.get('factorio_server.default_rcon_password')
        # Updated to use factorio_general_id
        self.channel_id = self.config_manager.get('discord.factorio_general_id')
        if not self.channel_id:
            # Fallback to old config key if exists
            self.channel_id = self.config_manager.get('discord.channel_id')
            logger.warning("Using legacy channel_id configuration")
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10  # seconds
        logger.info(f"DiscordToServerCog initialized with channel ID: {self.channel_id}")

    async def connect_rcon(self):
        try:
            self.rcon_client = RCONClient(self.rcon_host, self.rcon_port, self.rcon_password)
            await self.bot.loop.run_in_executor(None, self.rcon_client.connect)
            logger.info("RCON client connected successfully.")
            self.reconnect_attempts = 0  # Reset reconnect attempts on success
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
                return
            self.reconnect_attempts += 1
            await asyncio.sleep(self.reconnect_delay)

        logger.error("Max RCON reconnection attempts reached. Giving up.")

    async def disconnect_rcon(self):
        if self.rcon_client:
            try:
                await self.bot.loop.run_in_executor(None, self.rcon_client.close)
                logger.info("RCON client disconnected.")
            except Exception as e:
                logger.error(f"Error disconnecting RCON: {str(e)}")
            finally:
                self.rcon_client = None

    @commands.Cog.listener()
    async def on_ready(self):
        if self.channel_id:
            try:
                channel = self.bot.get_channel(int(self.channel_id))
                if channel:
                    logger.info(f"Successfully connected to channel: {channel.name}")
                else:
                    logger.error(f"Could not find channel with ID: {self.channel_id}")
            except ValueError:
                logger.error(f"Invalid channel ID format: {self.channel_id}")
        else:
            logger.error("No channel ID configured")
        logger.info("DiscordToServerCog is ready.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.id != int(self.channel_id):
            return

        server_management_cog = self.bot.get_cog('ServerManagementCog')
        if not server_management_cog or not server_management_cog.is_server_running():
            await message.channel.send("The Factorio server is not running. Please start the server before sending messages.")
            return

        rcon_command = f"/cchat {message.author.display_name}: {message.content}"
        
        # Try to send message up to 2 times
        for attempt in range(2):
            if not self.rcon_client:
                await self.reconnect_rcon()
                if not self.rcon_client:
                    await message.channel.send("Failed to establish RCON connection. Please try again later.")
                    return

            try:
                response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, rcon_command)
                logger.info(f"RCON command sent: {rcon_command}")
                logger.info(f"RCON response: {response}")
                return  # Success, exit the function
            except Exception as e:
                logger.error(f"Error sending RCON command (Attempt {attempt + 1}): {str(e)}")
                await self.disconnect_rcon()
                if attempt == 0:  # Only wait and retry on first attempt
                    await self.reconnect_rcon()
                    await asyncio.sleep(1)  # Small delay before retry

    async def cog_unload(self):
        await self.disconnect_rcon()
        logger.info("DiscordToServerCog unloaded")

async def setup(bot):
    await bot.add_cog(DiscordToServerCog(bot))
    logger.info("DiscordToServerCog added to bot")