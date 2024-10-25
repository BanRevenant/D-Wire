
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
        self.channel_id = self.config_manager.get('discord.channel_id')
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10  # seconds
        logger.info("DiscordToServerCog initialized")

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
        logger.info(f"DiscordToServerCog is ready.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.id != int(self.channel_id):
            return

        server_management_cog = self.bot.get_cog('ServerManagementCog')
        if not server_management_cog or not server_management_cog.is_server_running():
            await message.channel.send("The Factorio server is not running. Please start the server before sending messages.")
            return

        if not self.rcon_client:
            await self.reconnect_rcon()
            if not self.rcon_client:
                await message.channel.send("Failed to establish RCON connection. Please try again later.")
                return

        try:
            rcon_command = f"/cchat {message.author.display_name}: {message.content}"
            response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, rcon_command)
            logger.info(f"RCON command sent: {rcon_command}")
            logger.info(f"RCON response: {response}")
        except Exception as e:
            logger.error(f"Error sending RCON command: {str(e)}")
            await self.disconnect_rcon()
            await self.reconnect_rcon()

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")
        logger.info(f"Ping command executed by {ctx.author}")

    async def cog_unload(self):
        await self.disconnect_rcon()
        logger.info("DiscordToServerCog unloaded")

async def setup(bot):
    await bot.add_cog(DiscordToServerCog(bot))
    logger.info("DiscordToServerCog added to bot")
