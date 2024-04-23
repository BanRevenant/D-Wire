import discord
from discord.ext import commands
import os
import aiohttp
import json
import signal
import sys
import asyncio
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix=config['discord']['command_prefix'], intents=intents)
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
    
    asyncio.create_task(monitor_cogs())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.CommandInvokeError):
        original_error = error.original
        if isinstance(original_error, discord.Forbidden):
            await ctx.send("I don't have the necessary permissions to execute this command.")
        else:
            print(f"Error executing command: {ctx.command}")
            traceback.print_exception(type(original_error), original_error, original_error.__traceback__)
    else:
        print(f"Error in command: {ctx.command}")
        traceback.print_exception(type(error), error, error.__traceback__)

async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded {filename}')
            except Exception as e:
                print(f'Failed to load {filename}: {e}')


@bot.command(name='reload')
async def reload_cog(ctx, cog_name):
    try:
        await bot.reload_extension(f'cogs.{cog_name}')
        if ctx:
            await ctx.send(f'Reloaded {cog_name}.py')
        else:
            print(f'Reloaded {cog_name}.py')
    except Exception as e:
        if ctx:
            await ctx.send(f'Failed to reload {cog_name}.py: {str(e)}')
        else:
            print(f'Failed to reload {cog_name}.py: {str(e)}')

class CogFileHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            cog_name = os.path.basename(event.src_path)[:-3]
            try:
                asyncio.run_coroutine_threadsafe(reload_cog(None, cog_name), self.loop).result()
            except Exception as e:
                print(f"Error reloading cog {cog_name}: {str(e)}")

async def monitor_cogs():
    observer = Observer()
    observer.schedule(CogFileHandler(asyncio.get_event_loop()), path='./cogs', recursive=False)
    observer.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

asyncio.run(load_cogs())
bot.run(config['discord']['bot_token'])