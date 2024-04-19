import json
from discord.ext import commands


class ConfigCog(commands.Cog):
    """Cog for handling configuration data."""

    def __init__(self, bot):
        self.bot = bot
        self.config = self.load_config()

    @staticmethod
    def load_config():
        """Load configuration from a JSON file."""
        try:
            with open('config.json', 'r') as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            print("Configuration file not found.")
            return {}
        except json.JSONDecodeError:
            print("Error decoding JSON from the configuration file.")
            return {}


async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
    print("ConfigCog loaded and configuration available.")
