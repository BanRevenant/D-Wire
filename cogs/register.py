import discord
from discord.ext import commands
from factorio_rcon import RCONClient
import json


class RCONCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rcon_client = None

    async def ensure_connected(self):
        """Ensure the RCON client is connected before sending a command."""
        if self.rcon_client is None:
            with open('config.json', 'r') as config_file:
                config = json.load(config_file)
            host = config['rcon']['host']
            port = config['rcon']['port']
            password = config['rcon']['password']
            self.rcon_client = RCONClient(host, port, password)

    @commands.command()
    async def connect(self, ctx):
        """Connect to the RCON server."""
        await self.ensure_connected()
        await ctx.send("Connected to RCON server.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if self.rcon_client:
            response = self.rcon_client.send_command(message.content)
            if response is not None:
                log_channel_id = self.bot.config['log_channel_id']
                log_channel = self.bot.get_channel(log_channel_id)
                await log_channel.send(f"RCON output: {response}")
            else:
                await message.channel.send("No response received from RCON server.")


async def setup(bot):
    cog = RCONCog(bot)
    await bot.add_cog(cog)
