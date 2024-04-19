import discord
from discord.ext import commands
import os
import json
import asyncio


# Function to load configuration from JSON file
def load_config():
    with open('config.json', 'r') as config_file:
        return json.load(config_file)


config = load_config()

# Configure the bot
TOKEN = config['token']  # Read token from JSON config file
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=config['command_prefix'], intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} with ID {bot.user.id}')
    print('------')
    await load_cogs()


# Function to load all cogs at startup
async def load_cogs():
    cogs_directory = config['paths']['cogs_directory']
    for filename in os.listdir(cogs_directory):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"Loaded extension: {filename}")
            except Exception as e:
                print(f"Failed to load extension {filename}: {e}")


# Commands to manage cogs
@bot.command()
@commands.check(lambda ctx: any(role.name == config.get('required_role', "Floor Warden") for role in ctx.author.roles))
async def load(ctx, extension):
    await bot.load_extension(f'cogs.{extension}')
    await ctx.send(f'{extension} loaded.')


@bot.command()
@commands.check(lambda ctx: any(role.name == config.get('required_role', "Floor Warden") for role in ctx.author.roles))
async def unload(ctx, extension):
    await bot.unload_extension(f'cogs.{extension}')
    await ctx.send(f'{extension} unloaded.')


@bot.command()
@commands.check(lambda ctx: any(role.name == config.get('required_role', "Floor Warden") for role in ctx.author.roles))
async def reload(ctx, extension):
    await bot.reload_extension(f'cogs.{extension}')
    await ctx.send(f'{extension} reloaded.')


@bot.command()
@commands.check(lambda ctx: any(role.name == config.get('required_role', "Floor Warden") for role in ctx.author.roles))
async def loaded(ctx):
    all_cogs = [filename[:-3].lower() for filename in os.listdir(config['paths']['cogs_directory']) if
                filename.endswith('.py')]
    loaded_cogs = [cog.lower() for cog in bot.cogs.keys()]
    unloaded_cogs = [cog for cog in all_cogs if cog not in loaded_cogs]
    loaded_cogs_str = "\n".join(loaded_cogs) if loaded_cogs else "No cogs loaded."
    unloaded_cogs_str = "\n".join(unloaded_cogs) if unloaded_cogs else "All cogs are loaded."
    embed = discord.Embed(title="Loaded Cogs", color=discord.Color.blue())
    embed.add_field(name="Loaded Cogs", value=loaded_cogs_str, inline=False)
    embed.add_field(name="Unloaded Cogs", value=unloaded_cogs_str, inline=False)
    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(TOKEN)  # Start the bot
