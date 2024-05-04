import discord
from discord.ext import commands
from discord import app_commands
import json
import subprocess
import psutil
import os
import sys

with open('config.json') as config_file:
    config = json.load(config_file)

# Factorio server configuration
FACTORIO_EXE = config['factorio_server']['executable']
DEFAULT_PORT = config['factorio_server']['default_port']
DEFAULT_BIND_ADDRESS = config['factorio_server']['default_bind_address']
DEFAULT_RCON_PORT = config['factorio_server']['default_rcon_port']
DEFAULT_RCON_PASSWORD = config['factorio_server']['default_rcon_password']
DEFAULT_SERVER_SETTINGS = config['factorio_server']['server_settings_file']
DEFAULT_SERVER_ADMINLIST = config['factorio_server']['server_adminlist_file']
VERBOSE_LOG_FILE = config['factorio_server']['verbose_log_file']
SERVER_INFO_FILE = 'server_info.txt'

def setsid():
    if sys.platform == 'win32':
        from ctypes import windll
        kernel32 = windll.kernel32
        if kernel32.IsProcessInJob(kernel32.GetCurrentProcess(), None, None):
            kernel32.CreateJobObject(None, None)
            kernel32.AssignProcessToJobObject(None, kernel32.GetCurrentProcess())
    else:
        os.setsid()

class ServerManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_process = None
        self.server_command = None
        self.server_pid = None
        self.load_server_info()

    def load_server_info(self):
        if os.path.exists(SERVER_INFO_FILE):
            with open(SERVER_INFO_FILE, 'r') as file:
                self.server_command = file.readline().strip()
                self.server_pid = int(file.readline().strip())

    def save_server_info(self, command, pid):
        with open(SERVER_INFO_FILE, 'w') as file:
            file.write(command + '\n')
            file.write(str(pid) + '\n')

    def is_server_running(self):
        if self.server_pid is None:
            return False
        try:
            process = psutil.Process(self.server_pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_bot_status()

    async def update_bot_status(self):
        if self.is_server_running():
            await self.bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Game(name="Factorio."))
        else:
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game(name="Nothing."))

    @app_commands.command(name='startserver', description='Start the Factorio server with optional configuration')
    @app_commands.describe(port='Port number for the server (default: config value)')
    @app_commands.describe(save_file='Specific save file to load (default: latest save)')
    async def startserver(self, interaction: discord.Interaction, port: int = DEFAULT_PORT, save_file: str = None):
        """Command to start the Factorio server with optional configuration."""
        if self.is_server_running():
            await interaction.response.send_message("The server is already running.")
        else:
            await interaction.response.defer()  # Defer the response
            try:
                command = [
                    FACTORIO_EXE,
                    '--port', str(port),
                    '--bind', DEFAULT_BIND_ADDRESS,
                    '--rcon-port', str(DEFAULT_RCON_PORT),
                    '--rcon-password', DEFAULT_RCON_PASSWORD,
                    '--server-settings', DEFAULT_SERVER_SETTINGS,
                    '--server-adminlist', DEFAULT_SERVER_ADMINLIST
                ]
                if save_file:
                    command.extend(['--start-server', save_file])
                else:
                    command.append('--start-server-load-latest')

                verbose_log_file = open(VERBOSE_LOG_FILE, 'w')
                self.server_process = subprocess.Popen(command, stdout=verbose_log_file, stderr=subprocess.STDOUT, start_new_session=True)
                self.server_pid = self.server_process.pid
                self.server_command = ' '.join(command)
                self.save_server_info(self.server_command, self.server_pid)
                try:
                    setsid()
                except PermissionError:
                    pass  # Ignore the permission error and continue
                await interaction.followup.send("Server started successfully.")
                await self.update_bot_status()
            except Exception as e:
                await interaction.followup.send(f"Failed to start server: {str(e)}")

    @app_commands.command(name='stopserver', description='Stop the Factorio server')
    async def stopserver(self, interaction: discord.Interaction):
        """Command to stop the Factorio server."""
        if not self.is_server_running():
            await interaction.response.send_message("The server is already stopped.")
        else:
            await interaction.response.defer()  # Defer the response
            try:
                process = psutil.Process(self.server_pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
                self.server_pid = None
                self.server_command = None
                os.remove(SERVER_INFO_FILE)
                await interaction.followup.send("Server stopped successfully.")
                await self.update_bot_status()
            except Exception as e:
                await interaction.followup.send(f"Failed to stop server: {str(e)}")

    @app_commands.command(name='restart', description='Restart the Factorio server')
    async def restart(self, interaction: discord.Interaction):
        """Command to restart the Factorio server."""
        if not self.is_server_running():
            await interaction.response.send_message("The server is not running.")
        else:
            await interaction.response.defer()  # Defer the response
            try:
                await self.stopserver(interaction)  # Stop the server using the existing stopserver method
                await self.startserver(interaction)  # Start the server using the existing startserver method
                await interaction.followup.send("Server restarted successfully.")
                await self.update_bot_status()
            except Exception as e:
                await interaction.followup.send(f"Failed to restart server: {str(e)}")

async def setup(bot):
    cog = ServerManagementCog(bot)
    await bot.add_cog(cog)