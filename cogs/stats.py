import os
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import re
import asyncio
import json
import traceback
from logger import setup_logger

logger = setup_logger(__name__, 'logs/stats.log')

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(self.parent_dir, "player_stats.db")
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.create_database()
        self.create_registrations_file()
        self.readlog_cog = None
        self.stats_patterns = {
            'stats_kill': r"\[STATS-E1\] \[([^]]+)\] ([^[]+) \[([^]]+)\] with \[([^]]+)\]",
            'stats_death': r"\[STATS-D2\] \[([^]]+)\] killed by \[([^]]+)\] force \[enemy\]",
            'stats_place': r"\[ACT\] ([^[\]]+) placed",
            'statsme': r"\[CHAT\] (.+): !statsme"  # Simplified pattern to catch statsme commands
        }
        logger.info("StatsCog initialized")

    async def ensure_readlog_cog(self):
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            self.readlog_cog = self.bot.get_cog('ReadLogCog')
            if self.readlog_cog:
                logger.info("Successfully connected to ReadLogCog.")
                return
            attempt += 1
            logger.warning(f"ReadLogCog not found (Attempt {attempt}/{max_attempts}). Retrying in 2 seconds...")
            await asyncio.sleep(2)
        
        logger.error("Max attempts reached. Stats tracking will not work.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_readlog_cog()
        logger.info("StatsCog is ready.")

    def create_database(self):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            # Drop existing tables if they exist
            c.execute("DROP TABLE IF EXISTS player_stats")
            c.execute("DROP TABLE IF EXISTS player_deaths")
            c.execute("DROP TABLE IF EXISTS player_placed")
            
            # Create tables with correct constraints
            c.execute("""CREATE TABLE player_stats
                        (player_name TEXT,
                         action TEXT,
                         unit TEXT,
                         weapon TEXT,
                         count INTEGER DEFAULT 1,
                         UNIQUE(player_name, action, unit, weapon))""")
            
            c.execute("""CREATE TABLE player_deaths
                        (player_name TEXT,
                         killed_by TEXT,
                         count INTEGER DEFAULT 1,
                         UNIQUE(player_name, killed_by))""")
            
            c.execute("""CREATE TABLE player_placed
                        (player_name TEXT UNIQUE,
                         count INTEGER DEFAULT 1)""")
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_file}")
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            logger.error(traceback.format_exc())

    def create_registrations_file(self):
        if not os.path.isfile(self.registrations_file):
            with open(self.registrations_file, "w") as file:
                json.dump({}, file)
            logger.info(f"Created new registrations file: {self.registrations_file}")

    async def process_stats_from_line(self, line):
        """Process a log line for statistics"""
        try:
            # Check for statsme command first
            statsme_match = re.search(self.stats_patterns['statsme'], line)
            if statsme_match:
                player_name = statsme_match.group(1)
                logger.info(f"Detected statsme command from player: {player_name}")
                await self.post_player_stats(player_name)
                return

            # Check for kills
            kill_match = re.search(self.stats_patterns['stats_kill'], line)
            if kill_match:
                player_name, action, unit, weapon = kill_match.groups()
                self.update_database(player_name, action, unit, weapon)
                logger.debug(f"Processed kill stat: {player_name}, {action}, {unit}, {weapon}")
                return

            # Check for deaths
            death_match = re.search(self.stats_patterns['stats_death'], line)
            if death_match:
                player_name, killed_by = death_match.groups()
                self.update_deaths_database(player_name, killed_by)
                logger.debug(f"Processed death stat: {player_name} killed by {killed_by}")
                return

            # Check for placed objects
            place_match = re.search(self.stats_patterns['stats_place'], line)
            if place_match:
                player_name = place_match.group(1)
                self.update_placed_database(player_name)
                logger.debug(f"Processed place stat: {player_name}")
                return

        except Exception as e:
            logger.error(f"Error processing stats line: {str(e)}")
            logger.error(traceback.format_exc())

    def update_database(self, player_name, action, unit, weapon):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("""INSERT INTO player_stats (player_name, action, unit, weapon)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(player_name, action, unit, weapon)
                        DO UPDATE SET count = count + 1""",
                     (player_name, action, unit, weapon))
            conn.commit()
            conn.close()
            logger.debug(f"Updated database: {player_name}, {action}, {unit}, {weapon}")
        except Exception as e:
            logger.error(f"Error updating database: {str(e)}")
            logger.error(traceback.format_exc())

    def update_deaths_database(self, player_name, killed_by):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("""INSERT INTO player_deaths (player_name, killed_by)
                        VALUES (?, ?)
                        ON CONFLICT(player_name, killed_by)
                        DO UPDATE SET count = count + 1""",
                     (player_name, killed_by))
            conn.commit()
            conn.close()
            logger.debug(f"Updated deaths database: {player_name} killed by {killed_by}")
        except Exception as e:
            logger.error(f"Error updating deaths database: {str(e)}")
            logger.error(traceback.format_exc())

    def update_placed_database(self, player_name):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("""INSERT INTO player_placed (player_name)
                        VALUES (?)
                        ON CONFLICT(player_name)
                        DO UPDATE SET count = count + 1""",
                     (player_name,))
            conn.commit()
            conn.close()
            logger.debug(f"Updated placed database: {player_name}")
        except Exception as e:
            logger.error(f"Error updating placed database: {str(e)}")
            logger.error(traceback.format_exc())

    @app_commands.command(name='stats', description='Get player statistics')
    async def stats(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user
        player_name = await self.get_player_name(member.id)
        await self.post_player_stats(player_name, interaction)
        logger.info(f"Stats command used for player: {player_name}")

    async def post_player_stats(self, player_name, interaction=None):
        if not player_name:
            embed = discord.Embed(color=discord.Color.red())
            embed.add_field(
                name="Error",
                value="Player not found. Please make sure you have registered using the `/register` command.",
                inline=False
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                channel_id = self.config_manager.get('discord.channel_id')
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)
            logger.warning(f"Stats requested for unknown player")
            return

        try:
            # Get the Discord user ID for the player
            user_id = None
            with open(self.registrations_file, 'r') as f:
                registrations = json.load(f)
                user_id = next((int(uid) for uid, name in registrations.items() if name == player_name), None)

            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()

            c.execute("SELECT unit, weapon, count FROM player_stats WHERE player_name = ?", (player_name,))
            stats = c.fetchall()

            c.execute("SELECT killed_by, count FROM player_deaths WHERE player_name = ?", (player_name,))
            death_stats = c.fetchall()

            c.execute("SELECT count FROM player_placed WHERE player_name = ?", (player_name,))
            placed_stats = c.fetchone()

            conn.close()

            embed = discord.Embed(color=discord.Color.green())
            
            # Set the author with the user's avatar if available
            if user_id:
                user = self.bot.get_user(user_id)
                if user and user.avatar:
                    embed.set_author(name=f"Statistics for {player_name}", icon_url=user.avatar.url)
                else:
                    embed.set_author(name=f"Statistics for {player_name}")
            else:
                embed.set_author(name=f"Statistics for {player_name}")

            if stats or death_stats or placed_stats:
                total_kills = sum(count for _, _, count in stats)
                total_deaths = sum(count for _, count in death_stats)
                total_placed = placed_stats[0] if placed_stats else 0

                embed.add_field(
                    name="Overall Stats",
                    value=f"Total Kills: {total_kills}\nTotal Deaths: {total_deaths}\nPlaced Objects: {total_placed}",
                    inline=False
                )

                unit_stats = {}
                weapon_stats = {}
                for unit, weapon, count in stats:
                    unit_stats[unit] = unit_stats.get(unit, 0) + count
                    weapon_stats[weapon] = weapon_stats.get(weapon, 0) + count

                if unit_stats:
                    unit_text = "\n".join([f"{unit}: {count}" for unit, count in
                        sorted(unit_stats.items(), key=lambda x: x[1], reverse=True)])
                    embed.add_field(name="Bug Kills:", value=unit_text, inline=True)

                if weapon_stats:
                    weapon_text = "\n".join([f"{weapon}: {count}" for weapon, count in
                        sorted(weapon_stats.items(), key=lambda x: x[1], reverse=True)])
                    embed.add_field(name="Weapon Kills:", value=weapon_text, inline=True)
            else:
                embed.add_field(
                    name="No Stats",
                    value="No recorded stats yet.",
                    inline=False
                )

            embed.set_footer(text="Statistics provided by D-Wire")

            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                channel_id = self.config_manager.get('discord.channel_id')
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)
            logger.info(f"Posted stats for player: {player_name}")

        except Exception as e:
            logger.error(f"Error posting player stats: {str(e)}")
            logger.error(traceback.format_exc())
            embed = discord.Embed(color=discord.Color.red())
            embed.add_field(
                name="Error",
                value="An error occurred while retrieving player statistics.",
                inline=False
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                channel_id = self.config_manager.get('discord.channel_id')
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)

    @app_commands.command(name='wipedata', description='Wipe player statistics data')
    @app_commands.default_permissions(manage_guild=True)
    async def wipedata(self, interaction: discord.Interaction):
        try:
            bak_file = os.path.join(self.parent_dir, "player_stats.db.bak")
            if os.path.isfile(self.db_file):
                if os.path.isfile(bak_file):
                    os.remove(bak_file)
                os.rename(self.db_file, bak_file)
                logger.info(f"Renamed existing database file to {bak_file}")
            self.create_database()
            
            embed = discord.Embed(color=discord.Color.green())
            embed.add_field(
                name="Success",
                value="Player statistics data has been wiped and a new database has been created.",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
            logger.warning("Player statistics data wiped")
        except Exception as e:
            logger.error(f"Error wiping data: {str(e)}")
            logger.error(traceback.format_exc())
            embed = discord.Embed(color=discord.Color.red())
            embed.add_field(
                name="Error",
                value="An error occurred while wiping the data.",
                inline=False
            )
            await interaction.response.send_message(embed=embed)

    async def get_player_name(self, user_id):
        try:
            with open(self.registrations_file, "r") as file:
                registrations = json.load(file)
            user_id_str = str(user_id)
            player_name = registrations.get(user_id_str)
            logger.debug(f"Retrieved player name for user ID {user_id}: {player_name}")
            return player_name
        except Exception as e:
            logger.error(f"Error getting player name: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor messages for stats processing"""
        if message.author.bot:
            return

        if message.content.startswith('!statsme'):
            player_name = await self.get_player_name(message.author.id)
            if player_name:
                await self.post_player_stats(player_name)
            else:
                embed = discord.Embed(color=discord.Color.red())
                embed.add_field(
                    name="Error",
                    value="You need to register first using the `/register` command.",
                    inline=False
                )
            await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))
    logger.info("StatsCog added to bot")