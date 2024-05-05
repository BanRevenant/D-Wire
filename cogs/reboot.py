import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import json

with open('config.json') as config_file:
    config = json.load(config_file)

class RebootCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="discordrestart", description="Restart the Discord bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def discordrestart(self, interaction: discord.Interaction):
        await interaction.response.send_message("Restarting the Discord bot...")
        os.execv(sys.executable, ['python'] + sys.argv)

async def setup(bot):
    await bot.add_cog(RebootCog(bot))