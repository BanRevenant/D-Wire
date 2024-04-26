import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json

with open('config.json') as config_file:
    config = json.load(config_file)

API_URL = config['factorio_server_manager']['api_url']

async def send_api_command(endpoint, method='GET', cookie=None):
    """Send commands to the Factorio Server Manager API using aiohttp."""
    async with aiohttp.ClientSession() as session:
        headers = {'Content-Type': 'application/json'}
        url = f"{API_URL}{endpoint}"
        
        if method == 'GET':
            async with session.get(url, cookies={'authentication': cookie}, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {'error': f"Failed with status {response.status}: {await response.text()}"}

class SavesManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='listsaves', description='Lists all save files on the Factorio server')
    async def listsaves(self, interaction: discord.Interaction):
        """Lists all save files on the Factorio server."""
        await interaction.response.defer()
        saves = await send_api_command('/saves/list', cookie=self.bot.cookie)
        if 'error' in saves:
            await interaction.followup.send(saves['error'])
            return
        
        embed = discord.Embed(title="Factorio Server Saves", description="List of all save files:", color=discord.Color.blue())
        for save in saves:
            embed.add_field(name="Save File", value=save, inline=False)

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SavesManagementCog(bot))