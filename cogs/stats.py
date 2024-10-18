import os
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import re
import shutil
import asyncio
import json
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/stats.log')

STATS_PATTERN = r"\[STATS-E1\] \[([^]]+)\] ([^[]+) \[([^]]+)\] with \[([^]]+)\]"
DEATH_PATTERN = r"\[STATS-D2\] \[([^]]+)\] killed by \[([^]]+)\] force \[enemy\]"
PLACE_PATTERN = r"\[ACT\] ([^[\]]+) placed"
STATSME_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[CHAT\] (.+): statsme"

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(self.parent_dir, "player_stats.db")
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.create_database()
        self.create_registrations_file()
        self.reader_cog = self.bot.get_cog('ReaderCog')
        if self.reader_cog:
            self.reader_cog.subscribe("STATS-E1", self.process_stats)
            self.reader_cog.subscribe("STATS-D2", self.process_deaths)
            self.reader_cog.subscribe("ACT", self.process_placed)
            self.reader_cog.subscribe("CHAT", self.process_statsme)
        else:
            logger.error("ReaderCog not found. Stats tracking will not work.")
        logger.info("StatsCog initialized")

    def cog_unload(self):
        if self.reader_cog:
            self.reader_cog.unsubscribe("STATS-E1", self.process_stats)
            self.reader_cog.unsubscribe("STATS-D2", self.process_deaths)
            self.reader_cog.unsubscribe("ACT", self.process_placed)
            self.reader_cog.unsubscribe("CHAT", self.process_statsme)
        logger.info("StatsCog unloaded")

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
            logger.info(f"Created new database file: {self.db_file}")
            channel_id = self.config_manager.get('discord.channel_id')
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                message = f"A new player statistics database has been created at {self.db_file}."
                asyncio.create_task(channel.send(message))

    def create_registrations_file(self):
        if not os.path.isfile(self.registrations_file):
            with open(self.registrations_file, "w") as file:
                json.dump({}, file)
            logger.info(f"Created new registrations file: {self.registrations_file}")

    async def process_stats(self, line):
        match = re.search(STATS_PATTERN, line)
        if match:
            player_name, action, unit, weapon = match.groups()
            self.update_database(player_name, action, unit, weapon)
            logger.debug(f"Processed stats: {player_name}, {action}, {unit}, {weapon}")

    async def process_deaths(self, line):
        match = re.search(DEATH_PATTERN, line)
        if match:
            player_name, killed_by = match.groups()
            self.update_deaths_database(player_name, killed_by)
            logger.debug(f"Processed death: {player_name} killed by {killed_by}")

    async def process_placed(self, line):
        match = re.search(PLACE_PATTERN, line)
        if match:
            player_name = match.group(1)
            self.update_placed_database(player_name)
            logger.debug(f"Processed placed: {player_name}")

    async def process_statsme(self, line):
        match = re.search(STATSME_PATTERN, line)
        if match:
            player_name = match.group(2)
            await self.post_player_stats(player_name)
            logger.debug(f"Processed statsme: {player_name}")

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
        logger.debug(f"Updated database: {player_name}, {action}, {unit}, {weapon}")

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
        logger.debug(f"Updated deaths database: {player_name} killed by {killed_by}")

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
        logger.debug(f"Updated placed database: {player_name}")

    @app_commands.command(name='stats', description='Get player statistics')
    async def stats(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user
        player_name = await self.get_player_name(member.id)

        await self.post_player_stats(player_name, interaction)
        logger.info(f"Stats command used for player: {player_name}")

    async def post_player_stats(self, player_name, interaction=None):
        if player_name:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()

            c.execute("SELECT unit, weapon, count FROM player_stats WHERE player_name = ?", (player_name,))
            stats = c.fetchall()

            c.execute("SELECT killed_by, count FROM player_deaths WHERE player_name = ?", (player_name,))
            death_stats = c.fetchall()

            c.execute("SELECT count FROM player_placed WHERE player_name = ?", (player_name,))
            placed_stats = c.fetchone()

            conn.close()

            if stats or death_stats or placed_stats:
                total_kills = sum(count for _, _, count in stats)
                total_deaths = sum(count for _, count in death_stats)
                total_placed = placed_stats[0] if placed_stats else 0

                embed = discord.Embed(color=discord.Color.green())
                embed.add_field(name=f"Statistics for {player_name}", value=f"Total Kills: {total_kills}\nTotal Deaths: {total_deaths}\nPlaced Objects: {total_placed}", inline=False)

                bug_kills_value = "\n".join([f"{unit.capitalize()}: {count}" for unit, count in sorted(self.unit_stats(stats), key=lambda x: x[1], reverse=True)])
                embed.add_field(name="Bug Kills:", value=bug_kills_value, inline=True)

                weapon_kills_value = "\n".join([f"{weapon.capitalize()}: {count}" for weapon, count in sorted(self.weapon_stats(stats), key=lambda x: x[1], reverse=True)])
                embed.add_field(name="Weapon Kills:", value=weapon_kills_value, inline=True)

                embed.set_footer(text="Statistics provided by D-Wire")

                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    channel_id = self.config_manager.get('discord.channel_id')
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        await channel.send(embed=embed)
                logger.info(f"Posted stats for player: {player_name}")
            else:
                no_stats_embed = discord.Embed(color=discord.Color.red(), description=f"{player_name} has no recorded stats yet.")

                if interaction:
                    await interaction.response.send_message(embed=no_stats_embed)
                else:
                    channel_id = self.config_manager.get('discord.channel_id')
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        await channel.send(embed=no_stats_embed)
                logger.info(f"No stats found for player: {player_name}")
        else:
            if interaction:
                await interaction.response.send_message("Player not found. Please make sure you have registered using the `/register` command.")
            logger.warning(f"Stats requested for unknown player")

    @app_commands.command(name='wipedata', description='Wipe player statistics data')
    @app_commands.default_permissions(manage_guild=True)
    async def wipedata(self, interaction: discord.Interaction):
        bak_file = os.path.join(self.parent_dir, "player_stats.db.bak")
        if os.path.isfile(self.db_file):
            if os.path.isfile(bak_file):
                os.remove(bak_file)
            os.rename(self.db_file, bak_file)
            logger.info(f"Renamed existing database file to {bak_file}")
        self.create_database()
        await interaction.response.send_message("Player statistics data has been wiped and a new database has been created.")
        logger.warning("Player statistics data wiped")

    async def get_player_name(self, user_id):
        with open(self.registrations_file, "r") as file:
            registrations = json.load(file)

        try:
            user_id_str = str(user_id)
        except ValueError:
            return None

        player_name = registrations.get(user_id_str)
        logger.debug(f"Retrieved player name for user ID {user_id}: {player_name}")
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
    logger.info("StatsCog added to bot")