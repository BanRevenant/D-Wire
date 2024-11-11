import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import traceback
import re
import asyncio
from logger import setup_logger
from .stats_logger import StatsLogger

logger = setup_logger(__name__, 'logs/stats_commands.log')

CHAT_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[CHAT\] (.+): (.+)"

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        if not hasattr(bot, 'stats_logger_instance'):
            bot.stats_logger_instance = StatsLogger(self.parent_dir)
        self.stats_logger = bot.stats_logger_instance
        self.readlog_cog = None
        logger.info("StatsCog initialized")

    async def ensure_readlog_cog(self):
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            self.readlog_cog = self.bot.get_cog('ReadLogCog')
            if self.readlog_cog:
                # Subscribe to receive log lines
                self.readlog_cog.subscribe("STATS-E1", self.process_stats_line)
                self.readlog_cog.subscribe("STATS-D2", self.process_stats_line)
                self.readlog_cog.subscribe("ACT", self.process_stats_line)
                self.readlog_cog.subscribe("CHAT", self.process_stats_line)
                self.readlog_cog.subscribe("CHAT_STATS", self.process_statsme_command)
                logger.info("Successfully connected to ReadLogCog and subscribed to messages")
                return True
            attempt += 1
            logger.warning(f"ReadLogCog not found (Attempt {attempt}/{max_attempts}). Retrying in 2 seconds...")
            await asyncio.sleep(2)
        
        logger.error("Max attempts reached. Stats tracking will not work.")
        return False

    async def process_statsme_command(self, line):
        """Process the !statsme command from chat."""
        chat_match = re.search(CHAT_PATTERN, line)
        if chat_match:
            _, player_name, _ = chat_match.groups()
            logger.info(f"Processing !statsme command for player {player_name}")
            await self.post_player_stats(player_name, from_chat=True)

    async def process_stats_line(self, line):
        """Process a log line from ReadLogCog"""
        await self.stats_logger.process_line(line)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_readlog_cog()
        logger.info("StatsCog is ready.")

    @app_commands.command(name='stats', description='Get player statistics')
    async def stats(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user
        logger.debug(f"Stats requested for user {member.name} (ID: {member.id})")
        player_name = await self.get_player_name(member.id)
        logger.debug(f"Found player name: {player_name}")
        await self.post_player_stats(player_name, interaction)
        logger.info(f"Stats command used for player: {player_name}")

    async def post_player_stats(self, player_name, interaction=None, from_chat=False):
        logger.debug(f"Posting stats for player: {player_name}")
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
            # Get stats from the logger
            stats, death_stats, placed_stats, mined_stats = await self.stats_logger.get_player_stats(player_name)
            logger.debug(f"Retrieved stats for {player_name}")

            embed = discord.Embed(color=discord.Color.green())
            
            # Set the thumbnail
            guild = self.bot.get_guild(int(self.config_manager.get('discord.server_id')))
            if guild:
                member_id = await self.get_user_id_from_player_name(player_name)
                if member_id:
                    member = guild.get_member(member_id)
                    if member and member.avatar:
                        embed.set_thumbnail(url=member.avatar.url)

            if stats or death_stats or placed_stats or mined_stats:
                total_kills = sum(count for _, _, count in stats) if stats else 0
                total_deaths = sum(count for _, count in death_stats) if death_stats else 0
                total_placed = placed_stats[0] if placed_stats else 0
                total_mined = sum(count for _, count in mined_stats) if mined_stats else 0

                # Overall Stats section
                overall_stats = f"Total Kills: {total_kills}\nTotal Deaths: {total_deaths}\n"
                overall_stats += f"Placed Objects: {total_placed}\nPicked Objects: {total_mined}"
                embed.add_field(name="Overall Stats:", value=overall_stats, inline=False)

                # Process unit stats with pagination if needed
                if stats:
                    unit_stats = {}
                    weapon_stats = {}
                    for unit, weapon, count in stats:
                        unit_stats[unit] = unit_stats.get(unit, 0) + count
                        weapon_stats[weapon] = weapon_stats.get(weapon, 0) + count

                    if unit_stats:
                        # Sort unit stats by count
                        sorted_unit_stats = sorted(unit_stats.items(), key=lambda x: x[1], reverse=True)
                        
                        # Split into chunks if needed
                        unit_chunks = []
                        current_chunk = []
                        current_length = 0
                        
                        for unit, count in sorted_unit_stats:
                            line = f"{unit}: {count}\n"
                            if current_length + len(line) > 1024:
                                if current_chunk:  # Only append if there's content
                                    unit_chunks.append("".join(current_chunk))
                                current_chunk = [line]
                                current_length = len(line)
                            else:
                                current_chunk.append(line)
                                current_length += len(line)
                        
                        if current_chunk:  # Add the last chunk
                            unit_chunks.append("".join(current_chunk))
                        
                        # Add fields for each chunk
                        for i, chunk in enumerate(unit_chunks):
                            field_name = "Kills Breakdown:" if i == 0 else f"Kills Breakdown (Cont. {i}):"
                            embed.add_field(name=field_name, value=chunk, inline=True)

                    if weapon_stats:
                        # Sort weapon stats by count
                        sorted_weapon_stats = sorted(weapon_stats.items(), key=lambda x: x[1], reverse=True)
                        
                        # Split into chunks if needed
                        weapon_chunks = []
                        current_chunk = []
                        current_length = 0
                        
                        for weapon, count in sorted_weapon_stats:
                            line = f"{weapon}: {count}\n"
                            if current_length + len(line) > 1024:
                                if current_chunk:  # Only append if there's content
                                    weapon_chunks.append("".join(current_chunk))
                                current_chunk = [line]
                                current_length = len(line)
                            else:
                                current_chunk.append(line)
                                current_length += len(line)
                        
                        if current_chunk:  # Add the last chunk
                            weapon_chunks.append("".join(current_chunk))
                        
                        # Add fields for each chunk
                        for i, chunk in enumerate(weapon_chunks):
                            field_name = "Weapon Kills:" if i == 0 else f"Weapon Kills (Cont. {i}):"
                            embed.add_field(name=field_name, value=chunk, inline=True)

                # Add death stats if available
                if death_stats:
                    death_text = "\n".join([f"{killed_by}: {count}" for killed_by, count in
                        sorted(death_stats, key=lambda x: x[1], reverse=True)])
                    if len(death_text) <= 1024:
                        embed.add_field(name="Death Breakdown:", value=death_text, inline=True)
                    else:
                        # Split death stats if too long
                        death_chunks = []
                        current_chunk = []
                        current_length = 0
                        
                        for killed_by, count in sorted(death_stats, key=lambda x: x[1], reverse=True):
                            line = f"{killed_by}: {count}\n"
                            if current_length + len(line) > 1024:
                                if current_chunk:
                                    death_chunks.append("".join(current_chunk))
                                current_chunk = [line]
                                current_length = len(line)
                            else:
                                current_chunk.append(line)
                                current_length += len(line)
                        
                        if current_chunk:
                            death_chunks.append("".join(current_chunk))
                        
                        for i, chunk in enumerate(death_chunks):
                            field_name = "Death Breakdown:" if i == 0 else f"Death Breakdown (Cont. {i}):"
                            embed.add_field(name=field_name, value=chunk, inline=True)

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
        success = self.stats_logger.wipe_database()
        if success:
            embed = discord.Embed(color=discord.Color.green())
            embed.add_field(
                name="Success",
                value="Player statistics data has been wiped and a new database has been created.",
                inline=False
            )
        else:
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

    async def get_user_id_from_player_name(self, player_name):
        try:
            with open(self.registrations_file, "r") as file:
                registrations = json.load(file)
            for user_id, registered_name in registrations.items():
                if registered_name == player_name:
                    logger.debug(f"Retrieved user ID {user_id} for player name {player_name}")
                    return int(user_id)
            logger.warning(f"No user ID found for player name {player_name}")
            return None
        except Exception as e:
            logger.error(f"Error getting user ID from player name: {str(e)}")
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
                channel_id = self.config_manager.get('discord.channel_id')
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await self.post_player_stats(player_name)
                    logger.info(f"Processed !statsme command for player {player_name}")
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