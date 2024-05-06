import os
clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
clear()

import discord
from discord.ext import commands
from discord import app_commands
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
    disabled_cogs = bot.config.get('disabled_cogs', [])
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3]
            if cog_name not in disabled_cogs:
                try:
                    await bot.load_extension(f'cogs.{cog_name}')
                    print(f'Loaded {filename}')
                except Exception as e:
                    print(f'Failed to load {filename}: {e}')
            else:
                print(f'Skipped loading {filename} (disabled)')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print("Bot is ready to process requests.")
    
    channel_id = config['discord']['channel_id']
    channel = bot.get_channel(int(channel_id))
        
    # Sync the commands globally
    await bot.tree.sync()
    print("Synced commands globally")

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
                    await bot.tree.sync()  # Sync the commands after enabling a cog
                except Exception as e:
                    await interaction.followup.send(f'Error enabling {selected_cog}: {e}', ephemeral=True)
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
                    await bot.tree.sync()  # Sync the commands after disabling a cog
                except Exception as e:
                    await interaction.followup.send(f'Error disabling {selected_cog}: {e}', ephemeral=True)
                    traceback.print_exc()
        elif action == 'reload':
            try:
                await bot.reload_extension(f'cogs.{selected_cog}')
                print(f'Reloaded {selected_cog}')
                await bot.tree.sync()  # Sync the commands after reloading a cog
            except Exception as e:
                await interaction.followup.send(f'Error reloading {selected_cog}: {e}', ephemeral=True)
                traceback.print_exc()
                try:
                    await bot.unload_extension(f'cogs.{selected_cog}')
                    print(f'Unloaded {selected_cog} due to error')
                    await bot.tree.sync()  # Sync the commands after unloading a cog
                except Exception as e:
                    await interaction.followup.send(f'Error unloading {selected_cog}: {e}', ephemeral=True)
                    traceback.print_exc()
        elif action == 'remove':
            try:
                await bot.unload_extension(f'cogs.{selected_cog}')
                print(f'Unloaded {selected_cog} before removal')
                await bot.tree.sync()  # Sync the commands after unloading a cog
            except Exception as e:
                await interaction.followup.send(f'Error unloading {selected_cog} before removal: {e}', ephemeral=True)
                traceback.print_exc()
            os.remove(f'./cogs/{selected_cog}.py')
            print(f'Removed {selected_cog}')
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

        @discord.ui.button(label='Enable', style=discord.ButtonStyle.green, custom_id='enable', row=1)
        async def enable_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Disable', style=discord.ButtonStyle.red, custom_id='disable', row=1)
        async def disable_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Reload', style=discord.ButtonStyle.blurple, custom_id='reload', row=1)
        async def reload_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Remove', style=discord.ButtonStyle.gray, custom_id='remove', row=1)
        async def remove_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await cog_callback(interaction, self.selected_cog)

        @discord.ui.button(label='Install', style=discord.ButtonStyle.gray, custom_id='install', row=1)
        async def install_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message('Please upload a .py file to install as a cog.', ephemeral=True)

            def check(msg):
                return msg.author == interaction.user and msg.attachments

            try:
                msg = await bot.wait_for('message', check=check, timeout=60)
                attachment = msg.attachments[0]
                if not attachment.filename.endswith('.py'):
                    await interaction.followup.send('Invalid file type. Please upload a .py file.', ephemeral=True)
                    return

                await attachment.save(f'./cogs/{attachment.filename}')
                try:
                    await bot.load_extension(f'cogs.{attachment.filename[:-3]}')
                    print(f'Installed {attachment.filename}')
                    await interaction.followup.send(f'Installed {attachment.filename} as a cog.', ephemeral=True)
                    cogs.append(attachment.filename[:-3])
                    await interaction.edit_original_response(
                        content=f"Selected {attachment.filename[:-3]}: Enabled",
                        view=CogView(cogs, disabled_cogs, attachment.filename[:-3])
                    )
                    await bot.tree.sync()  # Sync the commands after installing a cog
                except Exception as e:
                    await interaction.followup.send(f'Error installing {attachment.filename}: {e}', ephemeral=True)
                    traceback.print_exc()
            except asyncio.TimeoutError:
                await interaction.followup.send('Timed out waiting for file upload.', ephemeral=True)

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
    view.message = response

asyncio.run(load_cogs())
bot.run(config['discord']['bot_token'])