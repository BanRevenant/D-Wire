import discord
from discord.ext import commands
from discord import app_commands
import psutil
import datetime

class UptimeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='uptime', description='Show the uptime of the Factorio server')
    async def uptime(self, interaction: discord.Interaction):
        server_cog = self.bot.get_cog('ServerManagementCog')
        if server_cog is None or not server_cog.is_server_running():
            await interaction.response.send_message("The server is not running.")
        else:
            pid = server_cog.server_pid
            process = psutil.Process(pid)
            uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())

            embed = discord.Embed(title="Server Uptime", color=discord.Color.blue())
            embed.add_field(name="PID", value=str(pid), inline=False)
            embed.add_field(name="Uptime", value=str(uptime), inline=False)

            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(UptimeCog(bot))