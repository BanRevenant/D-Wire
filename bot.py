import os
clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
clear()

import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import traceback
import logging

with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.all()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
bot.config = config
bot.debug_mode = config.get('debug_mode', False)

if bot.debug_mode:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

async def load_cogs():
    disabled_cogs = bot.config.get('disabled_cogs', [])
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3]
            if cog_name not in disabled_cogs:
                try:
                    await bot.load_extension(f'cogs.{cog_name}')
                    print(f'Loaded {filename}')
                    if bot.debug_mode:
                        logging.info(f'Loaded cog: {cog_name}')
                except Exception as e:
                    print(f'Failed to load {filename}: {e}')
                    if bot.debug_mode:
                        logging.error(f'Failed to load cog: {cog_name}', exc_info=True)
                    await report_error(e)
            else:
                print(f'Skipped loading {filename} (disabled)')
                if bot.debug_mode:
                    logging.info(f'Skipped loading cog: {cog_name} (disabled)')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if bot.debug_mode:
        logging.info(f'Logged in as {bot.user.name}')
    print("Bot is ready to process requests.")
    if bot.debug_mode:
        logging.info('Bot is ready to process requests.')

    # Sync the commands globally
    await bot.tree.sync()
    print("Synced commands globally")
    if bot.debug_mode:
        logging.info('Synced commands globally')

@bot.event
async def on_command_error(ctx, error):
    await report_error(error)

@bot.event
async def on_application_command_error(interaction, error):
    await report_error(error)

async def report_error(error):
    error_message = f"Oh shit, something fuckin bad happened:\n```{str(error)}```"
    traceback_message = f"```{traceback.format_exc()}```"
    if bot.debug_mode:
        logging.error(f'Error occurred: {error}')
        logging.error(traceback_message)

    show_button = discord.ui.Button(label="Show Me", style=discord.ButtonStyle.primary)
    ignore_button = discord.ui.Button(label="Fuck It", style=discord.ButtonStyle.secondary)

    async def show_callback(interaction):
        await interaction.response.edit_message(content=error_message + "\n\n" + traceback_message)

    async def ignore_callback(interaction):
        await interaction.response.edit_message(content="Error ignored.", embed=None, view=None)

    show_button.callback = show_callback
    ignore_button.callback = ignore_callback

    view = discord.ui.View()
    view.add_item(show_button)
    view.add_item(ignore_button)

    embed = discord.Embed(title="Error Occurred", description=error_message, color=discord.Color.red())

    error_channel_id = config['discord']['error_channel_id']
    error_channel = bot.get_channel(int(error_channel_id))

    if error_channel:
        if bot.debug_mode:
            logging.info(f'Sending error message to channel: {error_channel.name}')
        try:
            await error_channel.send(embed=embed, view=view)
        except discord.HTTPException as e:
            if bot.debug_mode:
                logging.error(f'Failed to send error message to channel: {error_channel.name}', exc_info=True)
    else:
        if bot.debug_mode:
            logging.error(f"Error channel not found. Please set a valid error_channel_id in the config.")

@bot.tree.command(name="debug", description="Enable, disable, or test debug mode")
@app_commands.describe(mode='Select the debug mode option')
@app_commands.choices(mode=[
    app_commands.Choice(name='Enable', value='enable'),
    app_commands.Choice(name='Disable', value='disable'),
    app_commands.Choice(name='Test', value='test')
])
@app_commands.default_permissions(manage_guild=True)
async def debug(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    if mode.value == 'test':
        try:
            raise ValueError("This is a test exception")
        except Exception as e:
            await report_error(e)
            await interaction.response.send_message(f"Test exception raised: {e}", ephemeral=True)
    elif mode.value == 'enable':
        bot.debug_mode = True
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug('Debug mode enabled')
        await interaction.response.send_message("Debug mode enabled", ephemeral=True)
    elif mode.value == 'disable':
        bot.debug_mode = False
        logging.getLogger().setLevel(logging.WARNING)
        logging.debug('Debug mode disabled')
        await interaction.response.send_message("Debug mode disabled", ephemeral=True)

    with open('config.json', 'w') as f:
        bot.config['debug_mode'] = bot.debug_mode
        json.dump(bot.config, f, indent=2)

@bot.tree.command(name="manage_cogs", description="Manage cogs")
@app_commands.default_permissions(manage_guild=True)
async def manage_cogs(interaction: discord.Interaction):
    cogs = [f[:-3] for f in os.listdir('./cogs') if f.endswith('.py')]
    disabled_cogs = bot.config.get('disabled_cogs', [])

    async def cog_callback(interaction: discord.Interaction, selected_cog: str):
        await interaction.response.defer()  # Defer the interaction response

        action = interaction.data['custom_id']

        if action == 'enable':
            if selected_cog in disabled_cogs:
                disabled_cogs.remove(selected_cog)
                bot.config['disabled_cogs'] = disabled_cogs
                with open('config.json', 'w') as f:
                    json.dump(bot.config, f, indent=2)
                try:
                    await bot.load_extension(f'cogs.{selected_cog}')
                    print(f'Enabled and loaded {selected_cog}')
                    if bot.debug_mode:
                        logging.info(f'Enabled and loaded cog: {selected_cog}')
                    await bot.tree.sync()  # Sync the commands after enabling a cog
                except Exception as e:
                    await interaction.followup.send(f'Error enabling {selected_cog}: {e}', ephemeral=True)
                    if bot.debug_mode:
                        logging.error(f'Error enabling cog: {selected_cog}', exc_info=True)
                    traceback.print_exc()
        elif action == 'disable':
            if selected_cog not in disabled_cogs:
                disabled_cogs.append(selected_cog)
                bot.config['disabled_cogs'] = disabled_cogs
                with open('config.json', 'w') as f:
                    json.dump(bot.config, f, indent=2)
                try:
                    await bot.unload_extension(f'cogs.{selected_cog}')
                    print(f'Disabled and unloaded {selected_cog}')
                    if bot.debug_mode:
                        logging.info(f'Disabled and unloaded cog: {selected_cog}')
                    await bot.tree.sync()  # Sync the commands after disabling a cog
                except Exception as e:
                    await interaction.followup.send(f'Error disabling {selected_cog}: {e}', ephemeral=True)
                    if bot.debug_mode:
                        logging.error(f'Error disabling cog: {selected_cog}', exc_info=True)
                    traceback.print_exc()
        elif action == 'reload':
            try:
                await bot.reload_extension(f'cogs.{selected_cog}')
                print(f'Reloaded {selected_cog}')
                if bot.debug_mode:
                    logging.info(f'Reloaded cog: {selected_cog}')
                await bot.tree.sync()  # Sync the commands after reloading a cog
            except Exception as e:
                await interaction.followup.send(f'Error reloading {selected_cog}: {e}', ephemeral=True)
                if bot.debug_mode:
                    logging.error(f'Error reloading cog: {selected_cog}', exc_info=True)
                traceback.print_exc()
                try:
                    await bot.unload_extension(f'cogs.{selected_cog}')
                    print(f'Unloaded {selected_cog} due to error')
                    if bot.debug_mode:
                        logging.info(f'Unloaded cog: {selected_cog} due to error')
                    await bot.tree.sync()  # Sync the commands after unloading a cog
                except Exception as e:
                    await interaction.followup.send(f'Error unloading {selected_cog}: {e}', ephemeral=True)
                    if bot.debug_mode:
                        logging.error(f'Error unloading cog: {selected_cog}', exc_info=True)
                    traceback.print_exc()
        elif action == 'remove':
            try:
                await bot.unload_extension(f'cogs.{selected_cog}')
                print(f'Unloaded {selected_cog} before removal')
                if bot.debug_mode:
                    logging.info(f'Unloaded cog: {selected_cog} before removal')
                await bot.tree.sync()  # Sync the commands after unloading a cog
            except Exception as e:
                await interaction.followup.send(f'Error unloading {selected_cog} before removal: {e}', ephemeral=True)
                if bot.debug_mode:
                    logging.error(f'Error unloading cog: {selected_cog} before removal', exc_info=True)
                traceback.print_exc()
            os.remove(f'./cogs/{selected_cog}.py')
            print(f'Removed {selected_cog}')
            if bot.debug_mode:
                logging.info(f'Removed cog: {selected_cog}')
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
                if bot.debug_mode:
                    logging.info('CogView timed out and deleted message')

        @discord.ui.button(label='Enable', style=discord.ButtonStyle.green, custom_id='enable', row=1)
        async def enable_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if bot.debug_mode:
                logging.info(f'Enable button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Disable', style=discord.ButtonStyle.red, custom_id='disable', row=1)
        async def disable_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if bot.debug_mode:
                logging.info(f'Disable button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Reload', style=discord.ButtonStyle.blurple, custom_id='reload', row=1)
        async def reload_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if bot.debug_mode:
                logging.info(f'Reload button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Remove', style=discord.ButtonStyle.gray, custom_id='remove', row=1)
        async def remove_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if bot.debug_mode:
                logging.info(f'Remove button clicked for cog: {self.selected_cog}')
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Install', style=discord.ButtonStyle.gray, custom_id='install', row=1)
        async def install_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if bot.debug_mode:
                logging.info('Install button clicked')
            await interaction.response.send_message('Please upload a .py file to install as a cog.', ephemeral=True)

            def check(msg):
                return msg.author == interaction.user and msg.attachments

            try:
                msg = await bot.wait_for('message', check=check, timeout=60)
                attachment = msg.attachments[0]
                if not attachment.filename.endswith('.py'):
                    await interaction.followup.send('Invalid file type. Please upload a .py file.', ephemeral=True)
                    if bot.debug_mode:
                        logging.info('Invalid file type for installation')
                    return

                await attachment.save(f'./cogs/{attachment.filename}')
                try:
                    await bot.load_extension(f'cogs.{attachment.filename[:-3]}')
                    print(f'Installed {attachment.filename}')
                    if bot.debug_mode:
                        logging.info(f'Installed cog: {attachment.filename}')
                    await interaction.followup.send(f'Installed {attachment.filename} as a cog.', ephemeral=True)
                    cogs.append(attachment.filename[:-3])
                    await interaction.edit_original_response(
                        content=f"Selected {attachment.filename[:-3]}: Enabled",
                        view=CogView(cogs, disabled_cogs, attachment.filename[:-3])
                    )
                    await bot.tree.sync()  # Sync the commands after installing a cog
                except Exception as e:
                    await interaction.followup.send(f'Error installing {attachment.filename}: {e}', ephemeral=True)
                    if bot.debug_mode:
                        logging.error(f'Error installing cog: {attachment.filename}', exc_info=True)
                    traceback.print_exc()
            except asyncio.TimeoutError:
                await interaction.followup.send('Timed out waiting for file upload.', ephemeral=True)
                if bot.debug_mode:
                    logging.info('Timed out waiting for file upload')
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
            await interaction.response.defer()  # Defer the interaction response

            selected_cog = self.values[0]
            self.view.selected_cog = selected_cog
            if bot.debug_mode:
                logging.info(f'Selected cog: {selected_cog}')
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
    if bot.debug_mode:
        logging.info('Sent CogView message')
    view.message = response

asyncio.run(load_cogs())
bot.run(config['discord']['bot_token'])