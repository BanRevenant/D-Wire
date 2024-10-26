import os
import sqlite3
import re
import json
import traceback
from discord.ext import commands
from logger import setup_logger

# Ensure the logger is only set up once to prevent duplicate messages
if 'stats_logger_instance' not in globals():
    logger = setup_logger(__name__, 'logs/stats_logger.log')
    # Remove all existing handlers to prevent duplicate log entries
    if logger.hasHandlers():
        logger.handlers.clear()
    logger = setup_logger(__name__, 'logs/stats_logger.log')
    stats_logger_instance = None  # Global instance to prevent reinitialization

class StatsLogger(commands.Cog):
    def __init__(self, bot):
        global stats_logger_instance
        if stats_logger_instance is not None:
            logger.warning("StatsLogger instance already exists. Reusing existing instance.")
            return  # Prevent multiple initializations

        self.bot = bot
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_file = os.path.join(self.parent_dir, "player_stats.db")
        self.stats_patterns = {
            'stats_kill': r"\[STATS-E1\] \[([^]]+)] killed \[([^]]+)] with \[([^]]+)]",
            'stats_death': r"\[STATS-D2\] \[([^]]+)] killed by \[([^]]+)] force \[enemy]",
            'stats_place': r"\[ACT\] ([^[\]]+) placed"
        }
        self.create_database()
        logger.info("StatsLogger initialized")
        stats_logger_instance = self  # Store the instance globally to prevent reinitialization

    def create_database(self):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            logger.debug("Creating database tables if they do not exist")
            c.execute("""CREATE TABLE IF NOT EXISTS player_stats
                        (player_name TEXT,
                         action TEXT,
                         unit TEXT,
                         weapon TEXT,
                         count INTEGER DEFAULT 1,
                         UNIQUE(player_name, action, unit, weapon))""")
            
            c.execute("""CREATE TABLE IF NOT EXISTS player_deaths
                        (player_name TEXT,
                         killed_by TEXT,
                         count INTEGER DEFAULT 1,
                         UNIQUE(player_name, killed_by))""")
            
            c.execute("""CREATE TABLE IF NOT EXISTS player_placed
                        (player_name TEXT UNIQUE,
                         count INTEGER DEFAULT 1)""")
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_file}")
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            logger.error(traceback.format_exc())

    async def process_line(self, line):
        """Process a log line for statistics"""
        try:
            logger.debug(f"Processing line: {line}")
            
            kill_match = re.search(self.stats_patterns['stats_kill'], line)
            if kill_match:
                player_name, unit, weapon = kill_match.groups()
                logger.debug(f"Kill match found - Player: {player_name}, Unit: {unit}, Weapon: {weapon}")
                self.update_database(player_name, "kill", unit, weapon)
                return

            death_match = re.search(self.stats_patterns['stats_death'], line)
            if death_match:
                player_name, killed_by = death_match.groups()
                logger.debug(f"Death match found - Player: {player_name}, Killed By: {killed_by}")
                self.update_deaths_database(player_name, killed_by)
                return

            place_match = re.search(self.stats_patterns['stats_place'], line)
            if place_match:
                player_name = place_match.group(1)
                logger.debug(f"Place match found - Player: {player_name}")
                self.update_placed_database(player_name)
                return

            logger.debug("No match found for line.")

        except Exception as e:
            logger.error(f"Error processing stats line: {str(e)}")
            logger.error(traceback.format_exc())

    def update_database(self, player_name, action, unit, weapon):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            logger.debug(f"Updating database for player {player_name} - Action: {action}, Unit: {unit}, Weapon: {weapon}")
            c.execute("""INSERT INTO player_stats (player_name, action, unit, weapon)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(player_name, action, unit, weapon)
                        DO UPDATE SET count = count + 1""",
                     (player_name, action, unit, weapon))
            conn.commit()
            conn.close()
            logger.info(f"Database updated for player {player_name} - Action: {action}, Unit: {unit}, Weapon: {weapon}")
        except Exception as e:
            logger.error(f"Error updating database: {str(e)}")
            logger.error(traceback.format_exc())

    def update_deaths_database(self, player_name, killed_by):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            logger.debug(f"Updating deaths database for player {player_name} - Killed By: {killed_by}")
            c.execute("""INSERT INTO player_deaths (player_name, killed_by)
                        VALUES (?, ?)
                        ON CONFLICT(player_name, killed_by)
                        DO UPDATE SET count = count + 1""",
                     (player_name, killed_by))
            conn.commit()
            conn.close()
            logger.info(f"Deaths database updated for player {player_name} - Killed By: {killed_by}")
        except Exception as e:
            logger.error(f"Error updating deaths database: {str(e)}")
            logger.error(traceback.format_exc())

    def update_placed_database(self, player_name):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            logger.debug(f"Updating placed database for player {player_name}")
            c.execute("""INSERT INTO player_placed (player_name)
                        VALUES (?)
                        ON CONFLICT(player_name)
                        DO UPDATE SET count = count + 1""",
                     (player_name,))
            conn.commit()
            conn.close()
            logger.info(f"Placed database updated for player {player_name}")
        except Exception as e:
            logger.error(f"Error updating placed database: {str(e)}")
            logger.error(traceback.format_exc())

    async def get_player_stats(self, player_name):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            logger.debug(f"Fetching stats for player {player_name}")
            c.execute("SELECT unit, weapon, count FROM player_stats WHERE player_name = ?", (player_name,))
            stats = c.fetchall()

            c.execute("SELECT killed_by, count FROM player_deaths WHERE player_name = ?", (player_name,))
            death_stats = c.fetchall()

            c.execute("SELECT count FROM player_placed WHERE player_name = ?", (player_name,))
            placed_stats = c.fetchone()

            conn.close()
            logger.info(f"Retrieved stats for player {player_name}: kills={stats}, deaths={death_stats}, placed={placed_stats}")
            return stats, death_stats, placed_stats

        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            logger.error(traceback.format_exc())
            return None, None, None

    def wipe_database(self):
        try:
            bak_file = os.path.join(self.parent_dir, "player_stats.db.bak")
            if os.path.isfile(self.db_file):
                if os.path.isfile(bak_file):
                    os.remove(bak_file)
                os.rename(self.db_file, bak_file)
            self.create_database()
            logger.warning("Player statistics data wiped")
            return True
        except Exception as e:
            logger.error(f"Error wiping data: {str(e)}")
            logger.error(traceback.format_exc())
            return False

async def setup(bot):
    global stats_logger_instance
    if stats_logger_instance is None:
        stats_logger_instance = StatsLogger(bot)
    await bot.add_cog(stats_logger_instance)
    logger.info("StatsLogger added to bot")
