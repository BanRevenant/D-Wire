import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import re
import string
import json
import datetime
import asyncio
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/registration.log')

ACCESS_PATTERN = r"\[CMD\] NAME: ([^,]+), COMMAND: register, ARGS: (\d+)"

class RegistrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.server_id = self.config_manager.get('discord.server_id')
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.pending_registrations = {}
        self.registration_timestamps = {}
        self.create_registrations_file()
        self.readlog_cog = None
        logger.info("RegistrationCog initialized")

    def cog_unload(self):
        if self.readlog_cog:
            self.readlog_cog.unsubscribe("CMD", self.process_registration)
        self.remove_expired_registrations.cancel()
        logger.info("RegistrationCog unloaded")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_readlog_cog()
        self.remove_expired_registrations.start()
        logger.info("RegistrationCog is ready.")

    async def ensure_readlog_cog(self):
        """Ensure connection to ReadLogCog"""
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            self.readlog_cog = self.bot.get_cog('ReadLogCog')
            if self.readlog_cog:
                self.readlog_cog.subscribe("CMD", self.process_registration)
                logger.info("Successfully connected to ReadLogCog.")
                return True
            attempt += 1
            logger.warning(f"ReadLogCog not found (Attempt {attempt}/{max_attempts}). Retrying in 2 seconds...")
            await asyncio.sleep(2)
        
        logger.error("Max attempts reached. Registration functionality may be limited.")
        return False

    def create_registrations_file(self):
        if not os.path.isfile(self.registrations_file):
            with open(self.registrations_file, "w") as file:
                json.dump({}, file)
            logger.info(f"Created new registrations file: {self.registrations_file}")

    @app_commands.command(name='register', description='Register for the Factorio server')
    async def register(self, interaction: discord.Interaction):
        code = self.generate_code()
        self.pending_registrations[code] = interaction.user.id
        self.registration_timestamps[code] = datetime.datetime.now()

        embed = discord.Embed(
            title="Registration Instructions",
            description="To complete your registration, please follow these steps:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Step 1",
            value="Return to the Factorio game server.",
            inline=False
        )
        embed.add_field(
            name="Step 2",
            value="Open the chat command box by pressing the backtick key (`), to the left of your number one key and above your tab key.",
            inline=False
        )
        embed.add_field(
            name="Step 3",
            value=f"Type the following command: `/register {code}`",
            inline=False
        )
        embed.add_field(
            name="Additional Perks",
            value="Once registered, you will gain access to the following features:\n"
                  "- Ability to pick up objects\n"
                  "- Deletion of objects\n"
                  "- Use of speakers",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Registration code {code} sent to user {interaction.user.id}")

    def generate_code(self, length=6):
        code = ''.join(random.choice(string.digits) for _ in range(length))
        logger.debug(f"Generated registration code: {code}")
        return code

    async def process_registration(self, line):
        match = re.search(ACCESS_PATTERN, line)
        if match:
            name, code = match.groups()
            logger.debug(f"Received registration attempt: Name={name}, Code={code}")

            if code in self.pending_registrations:
                user_id = self.pending_registrations[code]
                guild = self.bot.get_guild(int(self.server_id))
                if guild:
                    member = guild.get_member(user_id)
                    if member:
                        # Default to 'normal' rank for now since we don't get rank info
                        role_id = self.get_role_id('normal')
                        if role_id:
                            role = guild.get_role(int(role_id))
                            if role:
                                await member.add_roles(role)
                                await member.send(f"Thank you for registering, {name}! You have been assigned the role: {role.name}")
                                logger.info(f"Assigned role '{role.name}' to member {member.id}")

                                self.store_registration(user_id, name)
                            else:
                                await member.send(f"Role with ID '{role_id}' not found.")
                                logger.warning(f"Role with ID '{role_id}' not found in the server")
                        else:
                            await member.send(f"Unable to determine role.")
                            logger.warning(f"Unable to determine role for registration")

                        del self.pending_registrations[code]
                        del self.registration_timestamps[code]
                        logger.info(f"Removed pending registration for member {member.id}")
                    else:
                        logger.warning(f"Member {user_id} not found in the guild")
                else:
                    logger.warning(f"Guild not found")
            else:
                logger.warning(f"Invalid registration code: {code}")

    def get_role_id(self, rank):
        role_mapping = {
            'moderator': self.config_manager.get('discord.moderator_role_id'),
            'regular': self.config_manager.get('discord.regular_role_id'),
            'trusted': self.config_manager.get('discord.trusted_role_id'),
            'normal': self.config_manager.get('discord.normal_role_id')
        }
        return role_mapping.get(rank.lower())

    def store_registration(self, user_id, player_name):
        with open(self.registrations_file, "r") as file:
            registrations = json.load(file)

        registrations[str(user_id)] = player_name

        with open(self.registrations_file, "w") as file:
            json.dump(registrations, file, indent=4)

        logger.info(f"Stored registration for user {user_id} with player name '{player_name}'")

    @tasks.loop(minutes=5)
    async def remove_expired_registrations(self):
        one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
        expired_codes = [code for code, timestamp in self.registration_timestamps.items() if timestamp < one_hour_ago]

        for code in expired_codes:
            del self.pending_registrations[code]
            del self.registration_timestamps[code]

        logger.info(f"Removed {len(expired_codes)} expired registration(s)")

async def setup(bot):
    await bot.add_cog(RegistrationCog(bot))
    logger.info("RegistrationCog added to bot")