import discord
from discord.ext import commands
import os
import json
import zipfile
import aiohttp
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict

logger = logging.getLogger('mod_discovery')

@dataclass
class InstalledMod:
    name: str
    version: str
    title: str
    file_name: str

class ModDiscoveryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.mod_path = self.config_manager.get('factorio_mod_portal.mod_path')
        self.api_url = 'https://mods.factorio.com/api'
        logger.info("ModDiscoveryCog initialized")

    async def scan_mods(self) -> List[InstalledMod]:
        """Scan the mods directory for installed mods."""
        installed_mods = []
        
        try:
            for filename in os.listdir(self.mod_path):
                if filename.endswith('.zip'):
                    mod_file = os.path.join(self.mod_path, filename)
                    mod_info = self._get_mod_info(mod_file)
                    if mod_info:
                        installed_mods.append(InstalledMod(
                            name=mod_info['name'],
                            version=mod_info['version'],
                            title=mod_info.get('title', mod_info['name']),
                            file_name=filename
                        ))
                        logger.info(f"Found installed mod: {mod_info['name']} (v{mod_info['version']})")
            
            return installed_mods
        except Exception as e:
            logger.error(f"Error scanning mods directory: {str(e)}")
            return []

    def _get_mod_info(self, mod_file: str) -> Optional[Dict]:
        """Extract mod information from a mod zip file."""
        try:
            with zipfile.ZipFile(mod_file, 'r') as zip_ref:
                # Find info.json file
                info_file = next((f for f in zip_ref.namelist() if f.endswith('info.json')), None)
                if not info_file:
                    logger.warning(f"No info.json found in {mod_file}")
                    return None

                with zip_ref.open(info_file) as f:
                    info_data = json.load(f)
                    return info_data

        except Exception as e:
            logger.error(f"Error reading mod file {mod_file}: {str(e)}")
            return None

    async def match_with_portal(self, mod: InstalledMod) -> Optional[Dict]:
        """Try to find a mod on the Factorio mod portal."""
        try:
            # Try direct name match first
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/mods/{mod.name}") as response:
                    if response.status == 200:
                        data = await response.json()
                        latest_version = data['releases'][-1]['version']
                        logger.info(f"Found exact match for mod: {mod.name}")
                        return {
                            'portal_url': f"https://mods.factorio.com/mod/{mod.name}",
                            'latest_version': latest_version,
                            'needs_update': latest_version != mod.version
                        }

            # If direct match fails, try searching
            search_url = f"{self.api_url}/mods?q={mod.name}"
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get('results', [])
                        
                        # Try various matching methods
                        for result in results:
                            if (result['name'].lower() == mod.name.lower() or 
                                result.get('title', '').lower() == mod.title.lower()):
                                latest_version = result['latest_release']['version']
                                logger.info(f"Found match for mod: {mod.name}")
                                return {
                                    'portal_url': f"https://mods.factorio.com/mod/{result['name']}",
                                    'latest_version': latest_version,
                                    'needs_update': latest_version != mod.version
                                }

            logger.warning(f"No match found for mod: {mod.name}")
            return None

        except Exception as e:
            logger.error(f"Error searching for mod {mod.name}: {str(e)}")
            return None

    async def verify_mod_exists(self, portal_name: str) -> bool:
        """Verify that a mod exists on the portal."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/mods/{portal_name}") as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Error verifying mod {portal_name}: {str(e)}")
            return False

    def get_local_mods(self) -> List[str]:
        """Get a list of locally installed mod names."""
        try:
            mods = []
            for filename in os.listdir(self.mod_path):
                if filename.endswith('.zip'):
                    mod_file = os.path.join(self.mod_path, filename)
                    mod_info = self._get_mod_info(mod_file)
                    if mod_info and 'name' in mod_info:
                        mods.append(mod_info['name'])
            return mods
        except Exception as e:
            logger.error(f"Error getting local mods: {str(e)}")
            return []

async def setup(bot):
    await bot.add_cog(ModDiscoveryCog(bot))
    logger.info("ModDiscoveryCog added to bot")
