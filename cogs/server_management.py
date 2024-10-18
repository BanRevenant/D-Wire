import discord
from discord.ext import commands
from discord import app_commands
import json
import subprocess
import psutil
import os
import sys
import datetime
import asyncio
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/server_management.log')

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
        self.config_manager = bot.config_manager
        self.server_process = None
        self.server_command = None
        self.server_pid = None
        self.load_server_info()
        logger.info("ServerManagementCog initialized")

    def load_server_info(self):
        if os.path.exists(SERVER_INFO_FILE):
            try:
                with open(SERVER_INFO_FILE, 'r') as file:
                    self.server_command = file.readline().strip()
                    self.server_pid = int(file.readline().strip())
                logger.info(f"Loaded server info: PID {self.server_pid}")
            except Exception as e:
                logger.error(f"Error loading server info: {str(e)}")

    def save_server_info(self, command, pid):
        try:
            with open(SERVER_INFO_FILE, 'w') as file:
                file.write(command + '\n')
                file.write(str(pid) + '\n')
            logger.info(f"Saved server info: PID {pid}")
        except Exception as e:
            logger.error(f"Error saving server info: {str(e)}")

    def is_server_running(self):
        if self.server_pid is None:
            return False
        try:
            process = psutil.Process(self.server_pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            logger.warning(f"No process found with PID {self.server_pid}")
            return False

    def rename_verbose_log_file(self):
        verbose_log_file = self.config_manager.get('factorio_server.verbose_log_file')
        if os.path.exists(verbose_log_file):
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                log_dir = os.path.dirname(verbose_log_file)
                log_filename = os.path.basename(verbose_log_file)
                renamed_log_file = os.path.join(log_dir, f"previous_{timestamp}_{log_filename}")
                os.rename(verbose_log_file, renamed_log_file)
                logger.info(f"Renamed {verbose_log_file} to {renamed_log_file}")
            except Exception as e:
                logger.error(f"Failed to rename verbose log file: {str(e)}")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_bot_status()
        logger.info("ServerManagementCog is ready")

    async def update_bot_status(self):
        if self.is_server_running():
            await self.bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Game(name="Factorio."))
            logger.info("Bot status updated: Server running")
        else:
            await self.bot.change_presence(status=discord.Status.idle, activity=discord.Game(name="Nothing."))
            logger.info("Bot status updated: Server not running")

    @app_commands.command(name='startserver', description='Start the Factorio server with optional configuration')
    @app_commands.describe(port='Port number for the server (default: config value)')
    @app_commands.describe(save_file='Specific save file to load (default: latest save)')
    async def startserver(self, interaction: discord.Interaction, port: int = None, save_file: str = None):
        if self.is_server_running():
            await interaction.response.send_message("The server is already running.")
            logger.warning("Attempted to start server when it's already running")
            return

        await interaction.response.defer(thinking=True)  # Send the initial defer with thinking animation
        try:
            self.rename_verbose_log_file()

            # Server setup details
            factorio_exe = self.config_manager.get('factorio_server.executable')
            default_port = self.config_manager.get('factorio_server.default_port')
            bind_address = self.config_manager.get('factorio_server.default_bind_address')
            rcon_port = self.config_manager.get('factorio_server.default_rcon_port')
            rcon_password = self.config_manager.get('factorio_server.default_rcon_password')
            server_settings = self.config_manager.get('factorio_server.server_settings_file')
            server_adminlist = self.config_manager.get('factorio_server.server_adminlist_file')
            verbose_log_file = self.config_manager.get('factorio_server.verbose_log_file')

            command = [
                factorio_exe,
                '--port', str(port or default_port),
                '--bind', bind_address,
                '--rcon-port', str(rcon_port),
                '--rcon-password', rcon_password,
                '--server-settings', server_settings,
                '--server-adminlist', server_adminlist
            ]
            if save_file:
                command.extend(['--start-server', save_file])
            else:
                command.append('--start-server-load-latest')

            verbose_log_file = open(verbose_log_file, 'w')
            self.server_process = subprocess.Popen(command, stdout=verbose_log_file, stderr=subprocess.STDOUT, start_new_session=True)
            self.server_pid = self.server_process.pid
            self.server_command = ' '.join(command)
            self.save_server_info(self.server_command, self.server_pid)

            try:
                setsid()
            except PermissionError:
                logger.warning("PermissionError when trying to set session ID")

            await interaction.followup.send("Server started successfully.")  # Use followup for the response after defer
            await self.update_bot_status()
            logger.info(f"Server started with PID {self.server_pid}")
        except Exception as e:
            await interaction.followup.send(f"Failed to start server: {str(e)}")
            logger.error(f"Failed to start server: {str(e)}")

    @app_commands.command(name='stopserver', description='Stop the Factorio server')
    async def stopserver(self, interaction: discord.Interaction):
        if not self.is_server_running():
            await interaction.response.send_message("The server is already stopped.")
            logger.warning("Attempted to stop server when it's not running")
            return

        await interaction.response.defer()
        try:
            process = psutil.Process(self.server_pid)
            for proc in process.children(recursive=True):
                proc.kill()
            process.kill()
            self.server_pid = None
            self.server_command = None
            os.remove(SERVER_INFO_FILE)
            await interaction.followup.send("Server stopped successfully.")
            logger.info("Server stopped successfully")

            await asyncio.sleep(5)

            if sys.platform == 'win32':
                subprocess.call(['taskkill', '/F', '/IM', 'factorio.exe'])
            else:
                subprocess.call(['killall', '-9', 'factorio'])

            await self.update_bot_status()
        except Exception as e:
            await interaction.followup.send(f"Failed to stop server: {str(e)}")
            logger.error(f"Failed to stop server: {str(e)}")

    @app_commands.command(name='restart', description='Restart the Factorio server')
    async def restart(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            self.load_server_info()

            if self.server_pid:
                process = psutil.Process(self.server_pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
                self.server_pid = None
                self.server_command = None
                os.remove(SERVER_INFO_FILE)

                while process.is_running():
                    await asyncio.sleep(1)

            self.rename_verbose_log_file()

            factorio_exe = self.config_manager.get('factorio_server.executable')
            default_port = self.config_manager.get('factorio_server.default_port')
            bind_address = self.config_manager.get('factorio_server.default_bind_address')
            rcon_port = self.config_manager.get('factorio_server.default_rcon_port')
            rcon_password = self.config_manager.get('factorio_server.default_rcon_password')
            server_settings = self.config_manager.get('factorio_server.server_settings_file')
            server_adminlist = self.config_manager.get('factorio_server.server_adminlist_file')
            verbose_log_file = self.config_manager.get('factorio_server.verbose_log_file')

            command = [
                factorio_exe,
                '--port', str(default_port),
                '--bind', bind_address,
                '--rcon-port', str(rcon_port),
                '--rcon-password', rcon_password,
                '--server-settings', server_settings,
                '--server-adminlist', server_adminlist,
                '--start-server-load-latest'
            ]

            verbose_log_file = open(verbose_log_file, 'w')
            self.server_process = subprocess.Popen(command, stdout=verbose_log_file, stderr=subprocess.STDOUT, start_new_session=True)
            self.server_pid = self.server_process.pid
            self.server_command = ' '.join(command)
            self.save_server_info(self.server_command, self.server_pid)

            try:
                setsid()
            except PermissionError:
                logger.warning("PermissionError when trying to set session ID")

            await interaction.followup.send("Server restarted successfully.")
            await self.update_bot_status()
            logger.info(f"Server restarted with PID {self.server_pid}")
        except Exception as e:
            await interaction.followup.send(f"Failed to restart server: {str(e)}")
            logger.error(f"Failed to restart server: {str(e)}")

async def setup(bot):
    await bot.add_cog(ServerManagementCog(bot))
    logger.info("ServerManagementCog added to bot")
