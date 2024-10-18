import asyncio
import os
from discord.ext import commands, tasks
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/reader.log')

class ReaderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.log_file = self.config_manager.get('factorio_server.verbose_log_file')
        self.last_position = 0
        self.subscribers = {}
        logger.info("ReaderCog initialized")

    def cog_unload(self):
        self.read_log.cancel()
        logger.info("ReaderCog unloaded")

    @commands.Cog.listener()
    async def on_ready(self):
        self.read_log.start()
        logger.info("ReaderCog started reading logs")

    @tasks.loop(seconds=1)
    async def read_log(self):
        try:
            if os.path.getsize(self.log_file) < self.last_position:
                logger.info("Log file has been reset. Starting from the beginning.")
                self.last_position = 0

            with open(self.log_file, 'r') as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

            for line in new_lines:
                await self.process_line(line)

        except FileNotFoundError:
            logger.error(f"Log file not found: {self.log_file}")
        except Exception as e:
            logger.error(f"Error reading log file: {str(e)}")

    async def process_line(self, line):
        for pattern, callbacks in self.subscribers.items():
            if pattern in line:
                for callback in callbacks:
                    await callback(line)

    def subscribe(self, pattern, callback):
        if pattern not in self.subscribers:
            self.subscribers[pattern] = []
        self.subscribers[pattern].append(callback)
        logger.info(f"New subscriber for pattern: {pattern}")

    def unsubscribe(self, pattern, callback):
        if pattern in self.subscribers and callback in self.subscribers[pattern]:
            self.subscribers[pattern].remove(callback)
            logger.info(f"Unsubscribed from pattern: {pattern}")

async def setup(bot):
    await bot.add_cog(ReaderCog(bot))
    logger.info("ReaderCog added to bot")