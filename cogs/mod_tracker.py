import discord
from discord.ext import commands
import json
import os
import logging
import aiohttp
from typing import Dict, List, Optional

logger = logging.getLogger('mod_tracker')

class ModTrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.mod_path = self.config_manager.get('factorio_mod_portal.mod_path')
        self.urls_file = os.path.join(self.mod_path, 'mod_urls.json')
        self.mod_urls: Dict[str, str] = {}
        self.api_url = 'https://mods.factorio.com/api'
        self._load_urls()
        logger.info("ModTrackerCog initialized")

    def _load_urls(self) -> None:
        """Load the mod URLs from disk."""
        if os.path.exists(self.urls_file):
            try:
                with open(self.urls_file, 'r') as f:
                    self.mod_urls = json.load(f)
                logger.info(f"Loaded {len(self.mod_urls)} mod URLs from storage")
            except Exception as e:
                logger.error(f"Error loading mod URLs: {str(e)}")
                self.mod_urls = {}

    def _save_urls(self) -> None:
        """Save the mod URLs to disk."""
        try:
            with open(self.urls_file, 'w') as f:
                json.dump(self.mod_urls, f, indent=4)
            logger.info("Saved mod URLs to storage")
        except Exception as e:
            logger.error(f"Error saving mod URLs: {str(e)}")

    def add_url(self, mod_name: str, url: str) -> None:
        """Add or update a mod's URL."""
        self.mod_urls[mod_name] = url
        self._save_urls()
        logger.info(f"Added URL for mod: {mod_name}")

    def remove_url(self, mod_name: str) -> None:
        """Remove a mod's URL."""
        if mod_name in self.mod_urls:
            del self.mod_urls[mod_name]
            self._save_urls()
            logger.info(f"Removed URL for mod: {mod_name}")

    async def get_mod_details(self, mod_name: str) -> Optional[dict]:
        """Get mod details from the Factorio mod portal."""
        try:
            portal_name = mod_name.split('/')[-1] if '/' in mod_name else mod_name
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/mods/{portal_name}/full") as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Retrieved details for mod: {mod_name}")
                        return data
                    else:
                        logger.warning(f"Failed to get details for {mod_name}. Status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting mod details for {mod_name}: {str(e)}")
            return None

    async def check_for_updates(self) -> List[dict]:
        """Check all tracked mods for available updates."""
        updates_available = []
        
        try:
            for mod_name, url in self.mod_urls.items():
                mod_details = await self.get_mod_details(mod_name)
                if not mod_details:
                    continue

                latest_version = mod_details['releases'][-1]['version']
                installed_version = self._get_installed_version(mod_name)

                if installed_version and installed_version != latest_version:
                    updates_available.append({
                        'name': mod_name,
                        'current_version': installed_version,
                        'latest_version': latest_version,
                        'url': url
                    })
                    logger.info(f"Update available for {mod_name}: {installed_version} -> {latest_version}")

            return updates_available
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")
            return []

    def _get_installed_version(self, mod_name: str) -> Optional[str]:
        """Get the installed version of a mod from its info.json in the zip file."""
        try:
            # Find the mod zip file
            for filename in os.listdir(self.mod_path):
                if filename.startswith(f"{mod_name}_"):
                    import zipfile
                    mod_file = os.path.join(self.mod_path, filename)
                    with zipfile.ZipFile(mod_file, 'r') as zip_ref:
                        # Find info.json
                        info_file = next((f for f in zip_ref.namelist() if f.endswith('info.json')), None)
                        if info_file:
                            with zip_ref.open(info_file) as f:
                                info_data = json.load(f)
                                version = info_data.get('version')
                                logger.info(f"Found installed version for {mod_name}: {version}")
                                return version
        except Exception as e:
            logger.error(f"Error getting installed version for {mod_name}: {str(e)}")
        return None

    def get_all_tracked_mods(self) -> Dict[str, str]:
        """Get all tracked mods and their URLs."""
        return self.mod_urls.copy()

    async def add_mod(self, mod_name: str, portal_url: str, version: str) -> bool:
        """Add a new mod to tracking."""
        try:
            self.add_url(mod_name, portal_url)
            logger.info(f"Added new mod to tracking: {mod_name}")
            return True
        except Exception as e:
            logger.error(f"Error adding mod to tracking {mod_name}: {str(e)}")
            return False

    def remove_mod(self, mod_name: str) -> bool:
        """Remove a mod from tracking."""
        try:
            self.remove_url(mod_name)
            logger.info(f"Removed mod from tracking: {mod_name}")
            return True
        except Exception as e:
            logger.error(f"Error removing mod from tracking {mod_name}: {str(e)}")
            return False

async def setup(bot):
    await bot.add_cog(ModTrackerCog(bot))
    logger.info("ModTrackerCog added to bot")
