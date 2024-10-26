import os
import discord
from discord.ext import commands
from discord import app_commands
import json
import traceback
from logger import setup_logger
from .stats_logger import StatsLogger

logger = setup_logger(__name__, 'logs/stats_commands.log')

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.stats_logger = StatsLogger(self.parent_dir)
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
                logger.info("Successfully connected to ReadLogCog and subscribed to messages")
                return True
            attempt += 1
            logger.warning(f"ReadLogCog not found (Attempt {attempt}/{max_attempts}). Retrying in 2 seconds...")
            await asyncio.sleep(2)
        
        logger.error("Max attempts reached. Stats tracking will not work.")
        return False

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

    async def post_player_stats(self, player_name, interaction=None):
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
            # Get stats from the logger (now correctly awaiting)
            stats, death_stats, placed_stats = await self.stats_logger.get_player_stats(player_name)
            logger.debug(f"Retrieved stats for {player_name}: kills={stats}, deaths={death_stats}, placed={placed_stats}")

            embed = discord.Embed(color=discord.Color.green())
            
            # Set the author with avatar if we have an interaction
            if interaction and interaction.user.avatar:
                embed.set_author(name=f"Statistics for {player_name}", icon_url=interaction.user.avatar.url)
            else:
                embed.set_author(name=f"Statistics for {player_name}")

            if stats or death_stats or placed_stats:
                total_kills = sum(count for _, _, count in stats) if stats else 0
                total_deaths = sum(count for _, count in death_stats) if death_stats else 0
                total_placed = placed_stats[0] if placed_stats else 0

                embed.add_field(
                    name="Overall Stats",
                    value=f"Total Kills: {total_kills}\nTotal Deaths: {total_deaths}\nPlaced Objects: {total_placed}",
                    inline=False
                )

                if stats:
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
