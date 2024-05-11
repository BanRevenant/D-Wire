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
DEATH_PATTERN = r"\[STATS-D2\] \[([^]]+)\] killed by \[([^]]+)\] force \[enemy\]"
PLACE_PATTERN = r"\[ACT\] ([^[\]]+) placed"

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(self.parent_dir, "player_stats.db")
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.log_file = bot.config['factorio_server']['verbose_log_file']
        self.load_last_position()
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
        c.execute("""CREATE TABLE IF NOT EXISTS player_deaths
                     (player_name TEXT, killed_by TEXT, count INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS player_placed
                     (player_name TEXT, count INTEGER)""")
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

    def load_last_position(self):
        last_position_file = os.path.join(self.parent_dir, "last_position.txt")
        if os.path.isfile(last_position_file):
            with open(last_position_file, "r") as file:
                self.last_position = int(file.read().strip())
        else:
            self.last_position = 0

    def store_last_position(self):
        with open(os.path.join(self.parent_dir, "last_position.txt"), "w") as file:
            file.write(str(self.last_position))

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"StatsCog is ready.")
        self.check_log.start()

    @tasks.loop(seconds=5)
    async def check_log(self):
        try:
            with open(self.log_file, "r") as file:
                # Check if the log file has changed
                if os.path.getsize(self.log_file) < self.last_position:
                    print(f"Log file has changed. Resetting last_position to 0.")
                    self.last_position = 0

                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                for line in new_lines:
                    await self.process_stats(line)
                    await self.process_deaths(line)
                    await self.process_placed(line)

            self.store_last_position()
        except FileNotFoundError:
            print(f"Log file not found: {self.log_file}")

    async def process_stats(self, line):
        match = re.search(STATS_PATTERN, line)
        if match:
            player_name, action, unit, weapon = match.groups()
            self.update_database(player_name, action, unit, weapon)

    async def process_deaths(self, line):
        match = re.search(DEATH_PATTERN, line)
        if match:
            player_name, killed_by = match.groups()
            self.update_deaths_database(player_name, killed_by)

    async def process_placed(self, line):
        match = re.search(PLACE_PATTERN, line)
        if match:
            player_name = match.group(1)
            self.update_placed_database(player_name)

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

    def update_deaths_database(self, player_name, killed_by):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT count FROM player_deaths WHERE player_name = ? AND killed_by = ?", (player_name, killed_by))
        result = c.fetchone()
        if result:
            count = result[0] + 1
            c.execute("UPDATE player_deaths SET count = ? WHERE player_name = ? AND killed_by = ?", (count, player_name, killed_by))
        else:
            c.execute("INSERT INTO player_deaths (player_name, killed_by, count) VALUES (?, ?, 1)", (player_name, killed_by))
        conn.commit()
        conn.close()

    def update_placed_database(self, player_name):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT count FROM player_placed WHERE player_name = ?", (player_name,))
        result = c.fetchone()
        if result:
            count = result[0] + 1
            c.execute("UPDATE player_placed SET count = ? WHERE player_name = ?", (count, player_name))
        else:
            c.execute("INSERT INTO player_placed (player_name, count) VALUES (?, 1)", (player_name,))
        conn.commit()
        conn.close()

    @app_commands.command(name='stats', description='Get player statistics')
    async def stats(self, interaction: discord.Interaction, member: discord.Member = None):
        # Find the player name based on the Discord ID
        if member is None:
            member = interaction.user
        player_name = await self.get_player_name(member.id)

        if player_name:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()

            # Fetch kill stats
            c.execute("SELECT unit, weapon, count FROM player_stats WHERE player_name = ?", (player_name,))
            stats = c.fetchall()

            # Fetch death stats
            c.execute("SELECT killed_by, count FROM player_deaths WHERE player_name = ?", (player_name,))
            death_stats = c.fetchall()

            # Fetch placed stats
            c.execute("SELECT count FROM player_placed WHERE player_name = ?", (player_name,))
            placed_stats = c.fetchone()

            conn.close()

            if stats or death_stats or placed_stats:
                total_kills = sum(count for _, _, count in stats)
                total_deaths = sum(count for _, count in death_stats)
                total_placed = placed_stats[0] if placed_stats else 0

                # Create the embed
                embed = discord.Embed(color=discord.Color.green())
                embed.add_field(name=f"Statistics for {player_name}", value=f"Total Kills: {total_kills}\nTotal Deaths: {total_deaths}\nPlaced Objects: {total_placed}", inline=False)
                embed.set_thumbnail(url=member.display_avatar.url)  # Set the user's avatar as the thumbnail

                bug_kills_value = "\n".join([f"{unit.capitalize()}: {count}" for unit, count in sorted(self.unit_stats(stats), key=lambda x: x[1], reverse=True)])
                embed.add_field(name="Bug Kills:", value=bug_kills_value, inline=True)

                weapon_kills_value = "\n".join([f"{weapon.capitalize()}: {count}" for weapon, count in sorted(self.weapon_stats(stats), key=lambda x: x[1], reverse=True)])
                embed.add_field(name="Weapon Kills:", value=weapon_kills_value, inline=True)

                embed.set_footer(text="Statistics provided by D-Wire")

                # Send the embed
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"No statistics found for {player_name}.")
        else:
            await interaction.response.send_message(f"{member.mention} hasn't registered yet. Please encourage them to register using the `/register` command.")

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

    def unit_stats(self, stats):
        unit_stats = {}
        for unit, _, count in stats:
            unit_stats.setdefault(unit, 0)
            unit_stats[unit] += count
        return unit_stats.items()

    def weapon_stats(self, stats):
        weapon_stats = {}
        for _, weapon, count in stats:
            weapon_stats.setdefault(weapon, 0)
            weapon_stats[weapon] += count
        return weapon_stats.items()

async def setup(bot):
    await bot.add_cog(StatsCog(bot))