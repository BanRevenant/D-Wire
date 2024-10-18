import discord
from discord.ext import commands
from factorio_rcon import RCONClient
import json
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
        logger.info("DiscordToServerCog initialized")

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
        if not server_management_cog.is_server_running():
            await message.channel.send("The Factorio server is not running. Please start the server before sending messages.")
            return

        if not self.rcon_client:
            success = await self.connect_rcon()
            if not success:
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
            await message.channel.send("An error occurred while sending the message to the server. Please try again later.")

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