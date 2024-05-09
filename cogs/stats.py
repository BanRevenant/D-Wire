import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import re
import shutil
import asyncio
import json

STATS_PATTERN = r"\[STATS-E1\] \[([^]]+)\] ([^[]+) \[([^]]+)\] with \[([^]]+)\]"

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(self.parent_dir, "player_stats.db")
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.log_file = bot.config['factorio_server']['verbose_log_file']
        self.last_position = 0
        self.create_database()
        self.create_registrations_file()

    def cog_unload(self):
        self.check_log.cancel()

    def create_database(self):
        db_exists = os.path.isfile(self.db_file)
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS player_stats
                     (player_name TEXT, action TEXT, unit TEXT, weapon TEXT, count INTEGER)""")
        conn.commit()
        conn.close()
        if not db_exists:
            print(f"Created new database file: {self.db_file}")
            channel_id = self.bot.config['discord']['channel_id']
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                message = f"A new player statistics database has been created at {self.db_file}."
                asyncio.create_task(channel.send(message))

    def create_registrations_file(self):
        if not os.path.isfile(self.registrations_file):
            with open(self.registrations_file, "w") as file:
                json.dump({}, file)
            print(f"Created new registrations file: {self.registrations_file}")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"StatsCog is ready.")
        self.check_log.start()

    @tasks.loop(seconds=5)
    async def check_log(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                for line in new_lines:
                    await self.process_stats(line)

        except FileNotFoundError:
            print(f"Log file not found: {self.log_file}")

    async def process_stats(self, line):
        match = re.search(STATS_PATTERN, line)
        if match:
            player_name, action, unit, weapon = match.groups()
            self.update_database(player_name, action, unit, weapon)

    def update_database(self, player_name, action, unit, weapon):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT count FROM player_stats WHERE player_name = ? AND action = ? AND unit = ? AND weapon = ?",
                  (player_name, action, unit, weapon))
        result = c.fetchone()
        if result:
            count = result[0] + 1
            c.execute("UPDATE player_stats SET count = ? WHERE player_name = ? AND action = ? AND unit = ? AND weapon = ?",
                      (count, player_name, action, unit, weapon))
        else:
            c.execute("INSERT INTO player_stats (player_name, action, unit, weapon, count) VALUES (?, ?, ?, ?, 1)",
                      (player_name, action, unit, weapon))
        conn.commit()
        conn.close()

    @app_commands.command(name='stats', description='Get player statistics')
    async def stats(self, interaction: discord.Interaction):
        # Find the player name based on their Discord ID
        member = interaction.user
        player_name = await self.get_player_name(member.id)

        if player_name:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("SELECT action, unit, weapon, count FROM player_stats WHERE player_name = ?", (player_name,))
            stats = c.fetchall()
            conn.close()

            if stats:
                total_kills = sum(count for _, _, _, count in stats)
                embed = discord.Embed(title=f"Statistics for {player_name}", color=discord.Color.green())
                embed.add_field(name="Total Kills", value=str(total_kills))

                for action, unit, weapon, count in stats:
                    embed.add_field(name=f"{action} {unit} with {weapon}", value=str(count), inline=False)

                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"No statistics found for {player_name}.")
        else:
            await interaction.response.send_message("You need to register before checking your stats.")

    @app_commands.command(name='wipedata', description='Wipe player statistics data')
    @app_commands.default_permissions(manage_guild=True)
    async def wipedata(self, interaction: discord.Interaction):
        bak_file = os.path.join(self.parent_dir, "player_stats.db.bak")
        if os.path.isfile(self.db_file):
            if os.path.isfile(bak_file):
                os.remove(bak_file)
            os.rename(self.db_file, bak_file)
            print(f"Renamed existing database file to {bak_file}")
        self.create_database()
        await interaction.response.send_message("Player statistics data has been wiped and a new database has been created.")

    async def get_player_name(self, user_id):
        # Load the registration data from the registrations file
        with open(self.registrations_file, "r") as file:
            registrations = json.load(file)

        # Find the player name associated with the Discord user ID
        player_name = registrations.get(str(user_id))

        return player_name

async def setup(bot):
    await bot.add_cog(StatsCog(bot))