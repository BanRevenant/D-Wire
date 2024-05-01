import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import traceback

with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.all()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
bot.config = config

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
    print("Bot is ready to process requests.")
    
    channel_id = config['discord']['channel_id']
    channel = bot.get_channel(int(channel_id))
        
    # Sync the commands globally
    await bot.tree.sync()
    print("Synced commands globally")

asyncio.run(load_cogs())
bot.run(config['discord']['bot_token'])