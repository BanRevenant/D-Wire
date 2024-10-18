import discord
from discord.ext import commands
from discord import app_commands
import zipfile
import io
import os
import json

class AugmentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='augment', description='Augment a Factorio game file with D-Wire controls.')
    async def augment(self, interaction: discord.Interaction, game_file: str):
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        saves_directory = config['factorio_server']['saves_directory']
        game_file_path = os.path.join(saves_directory, game_file)

        if game_file.lower().endswith('.zip') and os.path.isfile(game_file_path):
            # Open the game file
            with zipfile.ZipFile(game_file_path, 'r') as zip_file:
                # Find the control.lua file
                control_lua_path = None
                for file_path in zip_file.namelist():
                    if file_path.endswith('control.lua'):
                        control_lua_path = file_path
                        break

                if control_lua_path:
                    # Read the contents of control.lua
                    with zip_file.open(control_lua_path, 'r') as control_lua_file:
                        control_lua_content = control_lua_file.read().decode('utf-8')

                    # Check if the line is already present in control.lua
                    if 'require "d-wire" -- D-Wire Server commands' not in control_lua_content:
                        # Add the line to the end of control.lua
                        control_lua_content += '\nrequire "d-wire" -- D-Wire Server commands'

                        # Create a new ZIP file in memory
                        new_zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(new_zip_buffer, 'w') as new_zip_file:
                            # Copy all the files from the original ZIP to the new ZIP
                            for file_path in zip_file.namelist():
                                if file_path != control_lua_path:
                                    new_zip_file.writestr(file_path, zip_file.read(file_path))

                            # Write the modified control.lua to the new ZIP
                            new_zip_file.writestr(control_lua_path, control_lua_content)

                            # Write the d-wire.lua file to the new ZIP
                            new_zip_file.writestr('d-wire.lua', D_WIRE_LUA_CODE)

                        # Replace the original game file with the augmented one
                        new_zip_buffer.seek(0)
                        with open(game_file_path, 'wb') as f:
                            f.write(new_zip_buffer.getvalue())

                        await interaction.response.send_message('Game file augmented successfully.')
                    else:
                        await interaction.response.send_message('The game file is already augmented.')
                else:
                    await interaction.response.send_message('control.lua not found in the game file.')
        else:
            await interaction.response.send_message('Please provide a valid .zip game file.')

# Paste your d-wire.lua code here
D_WIRE_LUA_CODE = '''
-- Your d-wire.lua code goes here
'''

async def setup(bot):
    await bot.add_cog(AugmentCog(bot))