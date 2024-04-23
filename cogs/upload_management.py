from discord.ext import commands
import aiohttp
import json
import discord
import os

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
                    return await response.read(), None
                else:
                    return None, {'error': f"Failed with status {response.status}: {await response.text()}"}

async def download_save_file(save_name, cookie):
    """Downloads a save file from the Factorio server."""
    save_url = f"{API_URL}/saves/dl/{save_name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(save_url, cookies={'authentication': cookie}) as response:
            if response.status == 200:
                data = await response.read()
                return data, None
            else:
                return None, f"Failed to download save file: HTTP {response.status}"

class UploadManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def downloadsave(self, ctx, save_name):
        """Downloads a save file and uploads it to the Discord channel."""
        message = await ctx.send(f"Downloading save file `{save_name}`...")
        file_data, error = await download_save_file(save_name, self.bot.cookie)
        if error:
            await message.edit(content=error)
            return
        
        file_path = f"{save_name}.zip"  # Assuming save files are in zip format
        with open(file_path, 'wb') as file:
            file.write(file_data)
        
        with open(file_path, 'rb') as file:
            await ctx.send(file=discord.File(file, file_path))
        await message.edit(content="Download and upload complete.")
        os.remove(file_path)  # Remove the temporary file

async def setup(bot):
    await bot.add_cog(UploadManagement(bot))