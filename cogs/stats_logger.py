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
            'stats_place': r"\[ACT\] ([^[\]]+) placed",
            'stats_mine': r"\[ACT\] ([^[\]]+) mined ([^[\]]+) \["  # Simplified mining pattern
        }
        # List of tree-related entities to ignore - expanded list
        self.tree_entities = [
            'tree-01', 'tree-02', 'tree-03', 'tree-04', 'tree-05',
            'tree-06', 'tree-07', 'tree-08', 'tree-09', 'dead-',
            'dry-hairy-tree', 'dry-tree', 'dead-dry-hairy-tree',
            'dead-grey-trunk', 'dead-tree-desert', 'demolisher-',
            '-tree-', 'volcanic'
        ]
        
        # Initialize the database
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
            
            c.execute("""CREATE TABLE IF NOT EXISTS player_mined
                        (player_name TEXT,
                         item_type TEXT,
                         count INTEGER DEFAULT 1,
                         UNIQUE(player_name, item_type))""")
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_file}")
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            logger.error(traceback.format_exc())
        
        logger.info("StatsLogger initialized")
        stats_logger_instance = self

    def is_tree_entity(self, unit):
        """Check if an entity is tree-related"""
        return any(tree_type in unit for tree_type in self.tree_entities)

    async def process_line(self, line):
        """Process a log line for statistics"""
        try:
            logger.debug(f"Processing line: {line}")
            
            # Process mining
            mine_match = re.search(self.stats_patterns['stats_mine'], line)
            if mine_match:
                player_name, item_type = mine_match.groups()
                logger.info(f"Mine match found - Player: {player_name}, Item: {item_type}")
                self.update_mined_database(player_name, item_type)
                return

            # Process kills - with tree filtering
            kill_match = re.search(self.stats_patterns['stats_kill'], line)
            if kill_match:
                player_name, unit, weapon = kill_match.groups()
                # Skip if the killed entity is a tree
                if not self.is_tree_entity(unit):
                    logger.debug(f"Kill match found - Player: {player_name}, Unit: {unit}, Weapon: {weapon}")
                    self.update_database(player_name, "kill", unit, weapon)
                else:
                    logger.debug(f"Skipping tree entity: {unit}")
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

    def update_mined_database(self, player_name, item_type):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            logger.info(f"Updating mined database for player {player_name} - Item: {item_type}")
            c.execute("""INSERT INTO player_mined (player_name, item_type)
                        VALUES (?, ?)
                        ON CONFLICT(player_name, item_type)
                        DO UPDATE SET count = count + 1""",
                     (player_name, item_type))
            conn.commit()
            conn.close()
            logger.info(f"Mined database updated successfully for player {player_name} - Item: {item_type}")
        except Exception as e:
            logger.error(f"Error updating mined database: {str(e)}")
            logger.error(traceback.format_exc())

    async def get_player_stats(self, player_name):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            logger.debug(f"Fetching stats for player {player_name}")
            
            # Get non-tree kills
            c.execute("""
                SELECT unit, weapon, count 
                FROM player_stats 
                WHERE player_name = ? 
                AND action = 'kill'
                AND unit NOT LIKE 'tree-%'
                AND unit NOT LIKE 'dead-%'
                AND unit NOT LIKE '%dry%'
            """, (player_name,))
            stats = c.fetchall()

            c.execute("SELECT killed_by, count FROM player_deaths WHERE player_name = ?", (player_name,))
            death_stats = c.fetchall()

            c.execute("SELECT count FROM player_placed WHERE player_name = ?", (player_name,))
            placed_stats = c.fetchone()

            c.execute("SELECT item_type, count FROM player_mined WHERE player_name = ?", (player_name,))
            mined_stats = c.fetchall()

            conn.close()
            logger.info(f"Retrieved stats for player {player_name}")
            return stats, death_stats, placed_stats, mined_stats

        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            logger.error(traceback.format_exc())
            return None, None, None, None

    def wipe_database(self):
        try:
            bak_file = os.path.join(self.parent_dir, "player_stats.db.bak")
            if os.path.isfile(self.db_file):
                if os.path.isfile(bak_file):
                    os.remove(bak_file)
                os.rename(self.db_file, bak_file)
            
            # Recreate the database
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
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
            
            c.execute("""CREATE TABLE IF NOT EXISTS player_mined
                        (player_name TEXT,
                         item_type TEXT,
                         count INTEGER DEFAULT 1,
                         UNIQUE(player_name, item_type))""")
            
            conn.commit()
            conn.close()
            
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