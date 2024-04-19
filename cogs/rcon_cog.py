import discord
import asyncio
import subprocess
import os
import psutil
from discord.ext import commands
from factorio_rcon import RCONClient


class FactorioRCON(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rcon_client = None

    def ensure_connected(self):
        """Ensure the RCON client is connected before sending a command."""
        if self.rcon_client is None:
            config_cog = self.bot.get_cog('ConfigCog')
            if config_cog is None:
                raise Exception("ConfigCog not loaded. Please load ConfigCog before using RCON commands.")
            config = config_cog.config
            host = 'localhost'  # Assuming your Factorio server is hosted locally
            port = config['rcon']['port']
            password = config['rcon']['password']
            self.rcon_client = RCONClient(host, port, password)

    @commands.command()
    async def rcon(self, ctx, *, command):
        """Pass a command to the Factorio server."""
        self.ensure_connected()
        try:
            response = self.rcon_client.send_command(command)
            if response is not None:
                await ctx.send(f"Response from server: {response}")
        except Exception as e:
            await ctx.send(f"Error sending command: {e}")

    @commands.command()
    async def stop(self, ctx):
        """Shut down the Factorio server safely."""
        self.ensure_connected()
        try:
            response = self.rcon_client.send_command("/quit")
            if response is not None:
                await ctx.send("Server is shutting down...")
        except Exception as e:
            await ctx.send(f"Error sending shutdown command: {e}")
        finally:
            if self.rcon_client is not None:
                self.rcon_client.close()
                self.rcon_client = None
                await ctx.send("RCON connection closed.")

                # Find and kill the specific Factorio server process started by the Discord bot
                bot_process = psutil.Process(os.getpid())
                for proc in bot_process.parent().children(recursive=True):
                    if "factorio.exe" in proc.name():
                        proc.terminate()
                        await ctx.send("Factorio server process terminated.")
                        break

                await asyncio.sleep(5)  # Delay for 5 seconds

                # Clean up the .lock file in the Factorio Server folder
                factorio_folder = os.path.join(os.getcwd(), "Factorio Server")
                lock_file = os.path.join(factorio_folder, ".lock")
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    await ctx.send(".lock file removed.")
                else:
                    await ctx.send(".lock file not found.")


async def setup(bot):
    await bot.add_cog(FactorioRCON(bot))
