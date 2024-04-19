import discord
from discord.ext import commands
import subprocess
import os
import asyncio
import json

# Define the base path for the script, adjusting it to point to the parent directory
base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Function to convert a relative path to an absolute path based on the base path
def absolute_path(relative_path):
    return os.path.join(base_path, relative_path)


# Load configuration from JSON file
with open(absolute_path('config.json'), 'r') as f:
    config = json.load(f)


# Function to check if the user has the required role to execute commands
def is_authorized(ctx):
    required_role_name = config["required_role"]
    return any(role.name == required_role_name for role in ctx.author.roles)


class Factorio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.factorio_process = None

    @commands.command()
    @commands.check(is_authorized)
    async def start(self, ctx, option=None):
        """Starts the Factorio server."""
        save_directory = absolute_path(config["paths"]["save_directory"])
        save_files = [f for f in os.listdir(save_directory) if f.endswith('.zip')]
        save_files.sort(key=lambda x: os.path.getmtime(os.path.join(save_directory, x)), reverse=True)
        if not save_files:
            await ctx.send("No save files found.")
            return

        embed = discord.Embed(title="Available Save Files",
                              description="Select a save file to load by typing its number, or type 'last' to load the most recent save:",
                              color=discord.Color.blue())
        columns = {'': '', ' ': '', '  ': ''}  # Using different spaces to avoid naming columns
        per_column = (len(save_files) + 2) // 3  # Aim for three columns

        for i, file in enumerate(save_files):
            column_key = list(columns.keys())[i // per_column]
            columns[column_key] += f"**{i + 1}.** {file}\n"

        embed.add_field(name='\u200b', value='**last**. Load the most recently modified save.', inline=False)
        for key, val in columns.items():
            embed.add_field(name='\u200b', value=val, inline=True)

        message = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and (
                        m.content.isdigit() and 1 <= int(m.content) <= len(save_files) or m.content == 'last')

        try:
            response = await self.bot.wait_for('message', check=check, timeout=60.0)
            if response.content == 'last':
                selected_save = save_files[0]  # Load the most recently modified save file
            else:
                selected_index = int(response.content) - 1
                selected_save = save_files[selected_index]
        except asyncio.TimeoutError:
            await ctx.send("No selection made in time, cancelling start.")
            return

        factorio_exe = absolute_path(config["paths"]["factorio_exe"])
        rcon_port = config["rcon"]["port"]
        rcon_password = config["rcon"]["password"]
        self.factorio_process = await asyncio.create_subprocess_exec(
            factorio_exe,
            "--start-server", os.path.join(save_directory, selected_save),
            "--rcon-port", str(rcon_port),
            "--rcon-password", rcon_password,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE)

        process_embed = discord.Embed(title="Loading Factorio Server", description=f"Loading **{selected_save}**...",
                                      color=discord.Color.orange())
        process_message = await ctx.send(embed=process_embed)

        # Update the embed with new status
        process_embed.title = "Factorio Server Started"
        process_embed.description += f"\nFactorio server started with the selected save: **{selected_save}**."
        process_embed.color = discord.Color.green()
        await process_message.edit(embed=process_embed)

        asyncio.create_task(self.log_output())

    async def log_output(self):
        """Logs output from the Factorio process to the console."""
        if self.factorio_process:
            async for line in self.factorio_process.stdout:
                print(line.decode('utf-8').strip())
            async for line in self.factorio_process.stderr:
                print('Error:', line.decode('utf-8').strip())

    @commands.command()
    async def info(self, ctx):
        """Provides information about the Factorio server process status."""
        if self.factorio_process is not None and self.factorio_process.returncode is None:
            running = "Yes"
            try:
                stdin_open = "Yes" if self.factorio_process.stdin and not self.factorio_process.stdin.at_eof() else "No"
            except AttributeError:
                stdin_open = "No"  # Assuming closed if attribute does not exist
            try:
                if self.factorio_process.stdout is not None:
                    stdout_open = "Yes" if not self.factorio_process.stdout.at_eof() else "No"
                else:
                    stdout_open = "No"  # Assuming closed if attribute does not exist
            except AttributeError:
                stdout_open = "No"  # Assuming closed if attribute does not exist
        else:
            running = "No"
            stdin_open = "N/A"
            stdout_open = "N/A"

        embed = discord.Embed(title="Factorio Server Info", color=discord.Color.magenta())
        embed.add_field(name="Running", value=running, inline=True)
        embed.add_field(name="STDIN Open", value=stdin_open, inline=True)
        embed.add_field(name="STDOUT Open", value=stdout_open, inline=True)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_authorized)
    async def send(self, ctx, *, message: str):
        """Sends input to the Factorio server via standard input."""
        if self.factorio_process is not None and self.factorio_process.stdin:
            try:
                message_encoded = (message + '\n').encode('utf-8')
                self.factorio_process.stdin.write(message_encoded)
                await self.factorio_process.stdin.drain()
                print(f"Sent '{message}' to Factorio server.")
                await ctx.send(f"Sent '{message}' to Factorio server.")
            except Exception as e:
                print(f"Error sending message to Factorio server: {str(e)}")
                await ctx.send(f"Error sending message to Factorio server: {str(e)}")
        else:
            print("Factorio server is not currently running or stdin is closed.")
            await ctx.send("Factorio server is not currently running or stdin is closed.")


async def setup(bot):
    await bot.add_cog(Factorio(bot))
    print("Factorio cog setup complete.")
