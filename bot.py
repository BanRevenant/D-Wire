import discord
from discord.ext import commands
from discord import app_commands
import os
import aiohttp
import json
import signal
import sys
import asyncio
import traceback

with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.all()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
bot.config = config

async def login_and_get_cookie():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(config['factorio_server_manager']['login_url'], json={'username': config['factorio_server_manager']['username'], 'password': config['factorio_server_manager']['password']}) as response:
                if response.status == 200:
                    cookie = response.cookies.get('authentication')
                    return cookie.value if cookie else None
                else:
                    return None
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return None

async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded {filename}')
            except Exception as e:
                print(f'Failed to load {filename}: {e}')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print("Bot is ready to send commands.")
    
    bot.cookie = await login_and_get_cookie()
    if bot.cookie:
        print("Successfully logged in to the Factorio server manager API.")
        channel_id = config['discord']['channel_id']
        channel = bot.get_channel(int(channel_id))
        await channel.send("Connected to the Factorio server manager API successfully.")
    else:
        print("Failed to log in to the Factorio server manager API.")
    
    # Sync the commands globally
    await bot.tree.sync()
    print("Synced commands globally")

asyncio.run(load_cogs())
bot.run(config['discord']['bot_token'])