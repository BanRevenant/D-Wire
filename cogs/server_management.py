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

    @app_commands.command(name='startserver', description='Start the Factorio server with optional configuration')
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @app_commands.describe(port='Port number for the server (default: config value)')
    @app_commands.describe(save_file='Specific save file to load (default: latest save)')
    async def startserver(self, interaction: discord.Interaction, port: int = None, save_file: str = None):
        await interaction.response.defer()  # Deferring to allow time for processing
        response = await self.start_server(port, save_file)
        await interaction.followup.send(response)  # Using followup to send response after deferring

    @app_commands.command(name='stopserver', description='Stop the Factorio server')
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    async def stopserver(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Deferring to allow time for processing
        response = await self.stop_server()
        await interaction.followup.send(response)  # Using followup to send response after deferring

    @app_commands.command(name='restartserver', description='Restart the Factorio server')
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    async def restartserver(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Deferring to allow time for processing
        response = await self.restart_server()
        await interaction.followup.send(response)  # Using followup to send response after deferring

    async def start_server(self, port: int = None, save_file: str = None):
        if self.is_server_running():
            logger.warning("Attempted to start server when it's already running")
            return "The server is already running."

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

            await self.update_bot_status()
            logger.info(f"Server started with PID {self.server_pid}")
            return "Server started successfully."
        except Exception as e:
            logger.error(f"Failed to start server: {str(e)}")
            return f"Failed to start server: {str(e)}"

    async def stop_server(self):
        if not self.is_server_running():
            logger.warning("Attempted to stop server when it's not running")
            return "The server is already stopped."

        try:
            process = psutil.Process(self.server_pid)
            
            # First attempt graceful shutdown
            logger.info("Initiating graceful server shutdown")
            for proc in process.children(recursive=True):
                proc.terminate()
            process.terminate()
            
            # Wait up to 30 seconds for the process to terminate
            try:
                process.wait(timeout=30)
            except psutil.TimeoutExpired:
                logger.warning("Server didn't shutdown gracefully, forcing termination")
                # If graceful shutdown fails, then force kill
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
            
            self.server_pid = None
            self.server_command = None
            if os.path.exists(SERVER_INFO_FILE):
                os.remove(SERVER_INFO_FILE)
            logger.info("Server stopped successfully")

            await asyncio.sleep(5)

            # Cleanup any remaining processes if necessary
            if sys.platform == 'win32':
                subprocess.call(['taskkill', '/F', '/IM', 'factorio.exe'])
            else:
                subprocess.call(['killall', '-9', 'factorio'])

            await self.update_bot_status()
            return "Server stopped successfully."
        except Exception as e:
            logger.error(f"Failed to stop server: {str(e)}")
            return f"Failed to stop server: {str(e)}"

    async def restart_server(self):
        stop_result = await self.stop_server()
        if "successfully" not in stop_result:
            return stop_result

        start_result = await self.start_server()
        return start_result

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

async def setup(bot):
    await bot.add_cog(ServerManagementCog(bot))
    logger.info("ServerManagementCog added to bot")

# Standalone function bindings for external script access
async def start_server(port=None, save_file=None):
    cog = ServerManagementCog(None)
    return await cog.start_server(port, save_file)

async def stop_server():
    cog = ServerManagementCog(None)
    return await cog.stop_server()

async def restart_server():
    cog = ServerManagementCog(None)
    return await cog.restart_server()