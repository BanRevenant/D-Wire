import discord
from discord.ext import commands
from factorio_rcon import RCONClient
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

class DiscordToServerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rcon_client = None
        self.rcon_host = self.bot.config['factorio_server']['rcon_host']
        self.rcon_port = self.bot.config['factorio_server']['default_rcon_port']
        self.rcon_password = self.bot.config['factorio_server']['default_rcon_password']
        self.channel_id = self.bot.config['discord']['channel_id']

    async def connect_rcon(self):
        loop = asyncio.get_event_loop()
        try:
            self.rcon_client = await loop.run_in_executor(None, RCONClient, self.rcon_host, self.rcon_port, self.rcon_password)
            await loop.run_in_executor(None, self.rcon_client.connect)
            print("RCON client connected successfully.")
            return True
        except Exception as e:
            print(f"Error connecting to RCON: {str(e)}")
            self.rcon_client = None
            return False

    async def disconnect_rcon(self):
        if self.rcon_client:
            try:
                self.rcon_client.close()
                print("RCON client disconnected.")
            except Exception as e:
                print(f"Error disconnecting RCON: {str(e)}")
            finally:
                self.rcon_client = None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"DiscordToServerCog is ready.")

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
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.rcon_client.send_command, rcon_command)
            print(f"RCON command sent: {rcon_command}")
            print(f"RCON response: {response}")
        except Exception as e:
            print(f"Error sending RCON command: {str(e)}")
            await self.disconnect_rcon()
            await message.channel.send("An error occurred while sending the message to the server. Please try again later.")

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")

    async def cog_unload(self):
        await self.disconnect_rcon()

async def setup(bot):
    await bot.add_cog(DiscordToServerCog(bot))