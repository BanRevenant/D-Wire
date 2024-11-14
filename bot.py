import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import traceback
import logging
from typing import Optional
from config_manager import ConfigManager
from logger import setup_logger

# Initialize ConfigManager
config_manager = ConfigManager('config.json')

# Set up logger
logger = setup_logger('bot', '/opt/bot/logs/bot.log')

class AutoReconnectBot(commands.Bot):
    async def setup_hook(self):
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # Initial delay in seconds

    async def close(self):
        self.reconnect_attempts = 0
        await super().close()

    async def connect(self, *, reconnect=True):
        while True:
            try:
                await super().connect(reconnect=True)
                self.reconnect_attempts = 0
                self.reconnect_delay = 5
                break
            except discord.GatewayNotFound:
                logger.error("Discord gateway not found. Retrying...")
            except discord.ConnectionClosed as e:
                if e.code == 1000:  # Normal closure
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= self.max_reconnect_attempts:
                        logger.error(f"Failed to reconnect after {self.max_reconnect_attempts} attempts")
                        raise
                    
                    logger.warning(f"Connection closed normally. Attempting reconnect #{self.reconnect_attempts}")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(300, self.reconnect_delay * 2)  # Exponential backoff, max 5 minutes
                else:
                    logger.error(f"Connection closed with code {e.code}")
                    raise

intents = discord.Intents.all()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
bot.config_manager = config_manager
bot.logger = logger

if config_manager.get('debug_mode', False):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

async def load_cogs():
    disabled_cogs = config_manager.get('disabled_cogs', [])
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3]
            if cog_name not in disabled_cogs:
                try:
                    await bot.load_extension(f'cogs.{cog_name}')
                    logger.info(f'Loaded {filename}')
                except Exception as e:
                    logger.error(f'Failed to load {filename}: {e}')
                    await report_error(e, f'Failed to load {filename}')
            else:
                logger.info(f'Skipped loading {filename} (disabled)')

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')
    logger.info('Bot is ready to process requests.')
    
    # Store error channel for future use
    error_channel_id = config_manager.get('discord.error_channel_id')
    if error_channel_id:
        bot.error_channel = bot.get_channel(int(error_channel_id))
        if bot.error_channel:
            logger.info(f'Found error channel: {bot.error_channel.name}')
        else:
            logger.error(f'Could not find error channel with ID: {error_channel_id}')
    else:
        logger.error('No error channel ID configured')

    # Sync the commands globally
    await bot.tree.sync()
    logger.info('Synced commands globally')

@bot.event
async def on_command_error(ctx, error):
    await report_error(error, "Command Error")

@bot.event
async def on_application_command_error(interaction, error):
    await report_error(error, "Application Command Error")

async def report_error(error, context="Error"):
    error_message = f"{context}:\n```{str(error)}```"
    traceback_message = f"```{traceback.format_exc()}```"
    logger.error(f'{context}: {error}')
    logger.error(traceback_message)

    show_button = discord.ui.Button(label="Show Details", style=discord.ButtonStyle.primary)
    ignore_button = discord.ui.Button(label="Ignore", style=discord.ButtonStyle.secondary)

    async def show_callback(interaction):
        await interaction.response.edit_message(content=error_message + "\n\n" + traceback_message)

    async def ignore_callback(interaction):
        await interaction.response.edit_message(content="Error ignored.", embed=None, view=None)

    show_button.callback = show_callback
    ignore_button.callback = ignore_callback

    view = discord.ui.View()
    view.add_item(show_button)
    view.add_item(ignore_button)

    embed = discord.Embed(title=context, description=error_message, color=discord.Color.red())

    # Use the stored error channel from on_ready
    if hasattr(bot, 'error_channel') and bot.error_channel:
        try:
            await bot.error_channel.send(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error(f'Failed to send error message to channel: {bot.error_channel.name}', exc_info=True)
    else:
        logger.error(f"Error channel not found or not properly initialized. Please check your configuration.")

@bot.tree.command(name="debug", description="Enable, disable, or test debug mode")
@app_commands.describe(mode='Select the debug mode option')
@app_commands.choices(mode=[
    app_commands.Choice(name='Enable', value='enable'),
    app_commands.Choice(name='Disable', value='disable'),
    app_commands.Choice(name='Test', value='test')
])
@app_commands.default_permissions(administrator=True)
async def debug(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    if mode.value == 'test':
        try:
            raise ValueError("This is a test exception")
        except Exception as e:
            await report_error(e)
            await interaction.response.send_message(f"Test exception raised: {e}", ephemeral=True)
    elif mode.value == 'enable':
        bot.config_manager.config['debug_mode'] = True
        logger.setLevel(logging.DEBUG)
        logger.debug('Debug mode enabled')
        await interaction.response.send_message("Debug mode enabled", ephemeral=True)
    elif mode.value == 'disable':
        bot.config_manager.config['debug_mode'] = False
        logger.setLevel(logging.WARNING)
        logger.debug('Debug mode disabled')
        await interaction.response.send_message("Debug mode disabled", ephemeral=True)

    with open('config.json', 'w') as f:
        json.dump(bot.config_manager.config, f, indent=2)

@bot.tree.command(name="manage_cogs", description="Manage cogs")
@app_commands.default_permissions(administrator=True)
async def manage_cogs(interaction: discord.Interaction):
    cogs = [f[:-3] for f in os.listdir('./cogs') if f.endswith('.py')]
    disabled_cogs = config_manager.get('disabled_cogs', [])

    async def cog_callback(interaction: discord.Interaction, selected_cog: str):
        await interaction.response.defer()

        action = interaction.data['custom_id']

        if action == 'enable':
            if selected_cog in disabled_cogs:
                disabled_cogs.remove(selected_cog)
                config_manager.config['disabled_cogs'] = disabled_cogs
                with open('config.json', 'w') as f:
                    json.dump(config_manager.config, f, indent=2)
                try:
                    await bot.load_extension(f'cogs.{selected_cog}')
                    logger.info(f'Enabled and loaded cog: {selected_cog}')
                    await bot.tree.sync()
                except Exception as e:
                    await interaction.followup.send(f'Error enabling {selected_cog}: {e}', ephemeral=True)
                    logger.error(f'Error enabling cog: {selected_cog}', exc_info=True)
        elif action == 'disable':
            if selected_cog not in disabled_cogs:
                disabled_cogs.append(selected_cog)
                config_manager.config['disabled_cogs'] = disabled_cogs
                with open('config.json', 'w') as f:
                    json.dump(config_manager.config, f, indent=2)
                try:
                    await bot.unload_extension(f'cogs.{selected_cog}')
                    logger.info(f'Disabled and unloaded cog: {selected_cog}')
                    await bot.tree.sync()
                except Exception as e:
                    await interaction.followup.send(f'Error disabling {selected_cog}: {e}', ephemeral=True)
                    logger.error(f'Error disabling cog: {selected_cog}', exc_info=True)
        elif action == 'reload':
            try:
                await bot.reload_extension(f'cogs.{selected_cog}')
                logger.info(f'Reloaded cog: {selected_cog}')
                await bot.tree.sync()
            except Exception as e:
                await interaction.followup.send(f'Error reloading {selected_cog}: {e}', ephemeral=True)
                logger.error(f'Error reloading cog: {selected_cog}', exc_info=True)
        elif action == 'remove':
            try:
                await bot.unload_extension(f'cogs.{selected_cog}')
                logger.info(f'Unloaded cog: {selected_cog} before removal')
                await bot.tree.sync()
            except Exception as e:
                await interaction.followup.send(f'Error unloading {selected_cog} before removal: {e}', ephemeral=True)
                logger.error(f'Error unloading cog: {selected_cog} before removal', exc_info=True)
            os.remove(f'./cogs/{selected_cog}.py')
            logger.info(f'Removed cog: {selected_cog}')
            await interaction.edit_original_response(content=f'Removed {selected_cog}', view=None)
            return

        await interaction.edit_original_response(
            content=f"Selected {selected_cog}: {'Enabled' if selected_cog not in disabled_cogs else 'Disabled'}",
            view=CogView(cogs, disabled_cogs, selected_cog)
        )

    class CogView(discord.ui.View):
        def __init__(self, cogs, disabled_cogs, selected_cog=None):
            super().__init__(timeout=60)
            self.cogs = cogs
            self.disabled_cogs = disabled_cogs
            self.selected_cog = selected_cog
            self.add_item(CogDropdown(cogs, disabled_cogs, selected_cog))
            self.message = None

        async def on_timeout(self):
            if self.message:
                await self.message.delete()
                logger.info('CogView timed out and deleted message')

        @discord.ui.button(label='Enable', style=discord.ButtonStyle.green, custom_id='enable', row=1)
        async def enable_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            logger.info(f'Enable button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Disable', style=discord.ButtonStyle.red, custom_id='disable', row=1)
        async def disable_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            logger.info(f'Disable button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Reload', style=discord.ButtonStyle.blurple, custom_id='reload', row=1)
        async def reload_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            logger.info(f'Reload button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Remove', style=discord.ButtonStyle.gray, custom_id='remove', row=1)
        async def remove_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            logger.info(f'Remove button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Install', style=discord.ButtonStyle.gray, custom_id='install', row=1)
        async def install_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            logger.info('Install button clicked')
            await interaction.response.send_message('Please upload a .py file to install as a cog.', ephemeral=True)

            def check(msg):
                return msg.author == interaction.user and msg.attachments

            try:
                msg = await bot.wait_for('message', check=check, timeout=60)
                attachment = msg.attachments[0]
                if not attachment.filename.endswith('.py'):
                    await interaction.followup.send('Invalid file type. Please upload a .py file.', ephemeral=True)
                    logger.info('Invalid file type for installation')
                    return

                await attachment.save(f'./cogs/{attachment.filename}')
                try:
                    await bot.load_extension(f'cogs.{attachment.filename[:-3]}')
                    logger.info(f'Installed cog: {attachment.filename}')
                    await interaction.followup.send(f'Installed {attachment.filename} as a cog.', ephemeral=True)
                    self.cogs.append(attachment.filename[:-3])
                    await interaction.edit_original_response(
                        content=f"Selected {attachment.filename[:-3]}: Enabled",
                        view=CogView(self.cogs, self.disabled_cogs, attachment.filename[:-3])
                    )
                    await bot.tree.sync()
                except Exception as e:
                    await interaction.followup.send(f'Error installing {attachment.filename}: {e}', ephemeral=True)
                    logger.error(f'Error installing cog: {attachment.filename}', exc_info=True)
            except asyncio.TimeoutError:
                await interaction.followup.send('Timed out waiting for file upload.', ephemeral=True)
                logger.info('Timed out waiting for file upload')

    class CogDropdown(discord.ui.Select):
        def __init__(self, cogs, disabled_cogs, selected_cog=None):
            options = [
                discord.SelectOption(
                    label=cog,
                    default=cog == selected_cog
                )
                for cog in cogs
            ]
            super().__init__(placeholder='Select a cog', min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()

            selected_cog = self.values[0]
            self.view.selected_cog = selected_cog
            logger.info(f'Selected cog: {selected_cog}')
            await interaction.edit_original_response(
                content=f"Selected {selected_cog}: {'Enabled' if selected_cog not in self.view.disabled_cogs else 'Disabled'}",
                view=self.view
            )

    view = CogView(cogs, disabled_cogs)
    response = await interaction.response.send_message(
        content="Please select a cog from the dropdown menu.",
        view=view,
        ephemeral=True
    )
    logger.info('Sent CogView message')
    view.message = response

asyncio.run(load_cogs())
bot.run(config_manager.get('discord.bot_token'))