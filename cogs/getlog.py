import os
import discord
from discord.ext import commands
from discord import app_commands
import io

class GetLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_file = bot.config['factorio_server']['verbose_log_file']

    @app_commands.command(name='verbose', description='Upload the Factorio verbose log file')
    async def verbose(self, interaction: discord.Interaction):
        if os.path.isfile(self.log_file):
            with open(self.log_file, 'rb') as f:
                log_data = f.read()
                await interaction.response.send_message(file=discord.File(io.BytesIO(log_data), filename='verbose.log'))
        else:
            await interaction.response.send_message(f"The log file {self.log_file} doesn't exist.")

async def setup(bot):
    await bot.add_cog(GetLogCog(bot))