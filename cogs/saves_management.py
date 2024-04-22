from discord.ext import commands
import aiohttp
import json
import discord

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

class SavesManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def listsaves(self, ctx):
        """Lists all save files on the Factorio server."""
        saves = await send_api_command('/saves/list', cookie=self.bot.cookie)
        if 'error' in saves:
            await ctx.send(saves['error'])
            return
        
        embed = discord.Embed(title="Factorio Server Saves", description="List of all save files:", color=discord.Color.blue())
        for save in saves:
            embed.add_field(name="Save File", value=save, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SavesManagement(bot))