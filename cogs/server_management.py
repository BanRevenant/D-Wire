from discord.ext import commands
import aiohttp
import json

with open('config.json') as config_file:
    config = json.load(config_file)

# Login URL and credentials
LOGIN_URL = config['factorio_server_manager']['login_url']
API_URL = config['factorio_server_manager']['api_url']
USERNAME = config['factorio_server_manager']['username']
PASSWORD = config['factorio_server_manager']['password']

async def send_api_command(endpoint, method='GET', payload=None, cookie=None):
    """Send commands to the Factorio Server Manager API using aiohttp."""
    async with aiohttp.ClientSession() as session:
        headers = {'Content-Type': 'application/json'}
        url = f"{API_URL}{endpoint}"
        
        if method == 'POST':
            async with session.post(url, json=payload, cookies={'authentication': cookie}, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {'error': f"Failed with status {response.status}: {await response.text()}"}
        else:
            async with session.get(url, cookies={'authentication': cookie}, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {'error': f"Failed with status {response.status}: {await response.text()}"}

class ServerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def startserver(self, ctx):
        """Command to start the Factorio server with necessary configuration."""
        config_data = {
            'game_port': config['factorio_server_manager']['game_port'],
            'rcon_port': config['factorio_server_manager']['rcon_port'],
            'max_players': config['factorio_server_manager']['max_players']
        }
        await ctx.send("Attempting to start the Factorio server with provided settings...")
        result = await send_api_command('/server/start', 'POST', payload=config_data, cookie=self.bot.cookie)
        if 'error' in result:
            await ctx.send(f"Failed to start server: {result['error']}")
        else:
            await ctx.send("Server started successfully.")

    @commands.command()
    async def stopserver(self, ctx):
        """Command to stop the Factorio server."""
        await ctx.send("Attempting to stop the Factorio server...")
        result = await send_api_command('/server/stop', cookie=self.bot.cookie)
        if 'error' in result:
            await ctx.send(result['error'])
        else:
            await ctx.send("Server stopped successfully.")

async def setup(bot):
    await bot.add_cog(ServerManagement(bot))