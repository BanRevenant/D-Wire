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
                    return await response.json(), None
                else:
                    return None, {'error': f"Failed with status {response.status}: {await response.text()}"}

class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='serverstatus', description='Get the current status of the Factorio server')
    async def serverstatus(self, interaction: discord.Interaction):
        """Get the current status of the Factorio server."""
        await interaction.response.defer()
        status, error = await send_api_command('/server/status', cookie=self.bot.cookie)
        if error:
            await interaction.followup.send(f"Error retrieving server status: {error['error']}")
            return
        
        embed = discord.Embed(title="Factorio Server Status", color=discord.Color.blue())
        
        if 'running' in status:
            embed.add_field(name="Running", value=status['running'], inline=False)
        else:
            embed.add_field(name="Running", value="Unknown", inline=False)
        
        if 'savefile' in status:
            embed.add_field(name="Save File", value=status['savefile'], inline=False)
        else:
            embed.add_field(name="Save File", value="Unknown", inline=False)
        
        if 'latency' in status:
            embed.add_field(name="Latency", value=status['latency'], inline=False)
        else:
            embed.add_field(name="Latency", value="Unknown", inline=False)
        
        if 'port' in status:
            embed.add_field(name="Port", value=status['port'], inline=False)
        else:
            embed.add_field(name="Port", value="Unknown", inline=False)
        
        if 'bindip' in status:
            embed.add_field(name="Bind IP", value=status['bindip'], inline=False)
        else:
            embed.add_field(name="Bind IP", value="Unknown", inline=False)
        
        if 'fac_version' in status:
            embed.add_field(name="Factorio Version", value=status['fac_version'], inline=False)
        else:
            embed.add_field(name="Factorio Version", value="Unknown", inline=False)
        
        if 'base_mod_version' in status:
            embed.add_field(name="Base Mod Version", value=status['base_mod_version'], inline=False)
        else:
            embed.add_field(name="Base Mod Version", value="Unknown", inline=False)
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StatusCog(bot))