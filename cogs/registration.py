import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import re
import string
import json
import datetime

ACCESS_PATTERN = r"\[ACCESS\] (\w+) (\w+) (\d+)"

class RegistrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('config.json') as config_file:
            self.config = json.load(config_file)
            self.log_file = self.config['factorio_server']['server_log_file']
            self.server_id = self.config['discord']['server_id']
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.registrations_file = os.path.join(self.parent_dir, "registrations.json")
        self.last_position = 0
        self.pending_registrations = {}
        self.registration_timestamps = {}
        self.create_registrations_file()

    def create_registrations_file(self):
        if not os.path.isfile(self.registrations_file):
            with open(self.registrations_file, "w") as file:
                json.dump({}, file)
            print(f"Created new registrations file: {self.registrations_file}")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"RegistrationCog is ready.")
        self.check_log.start()
        self.remove_expired_registrations()

    def cog_unload(self):
        self.check_log.cancel()

    @app_commands.command(name='register', description='Register for the Factorio server')
    async def register(self, interaction: discord.Interaction):
        # Generate a unique registration code
        code = self.generate_code()

        # Store the code and the user's ID in the pending_registrations dictionary
        self.pending_registrations[code] = interaction.user.id

        # Store the registration timestamp
        self.registration_timestamps[code] = datetime.datetime.now()

        # Create an embedded message
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
            value="Open the chat command box by pressing the backtick key, tilde key, grave, what ever the hell you wana call it. Its to the left of your number one, and above your tab key (`).",
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

        # Send the embedded message as an ephemeral response
        await interaction.response.send_message(embed=embed, ephemeral=True)

        print(f"[DEBUG] Registration code {code} sent to user {interaction.user.id}")

    def generate_code(self, length=6):
        # Generate a random code of specified length
        code = ''.join(random.choice(string.digits) for _ in range(length))
        print(f"[DEBUG] Generated registration code: {code}")
        return code

    @tasks.loop(seconds=5)
    async def check_log(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                for line in new_lines:
                    await self.process_registration(line)

        except FileNotFoundError:
            print(f"Log file not found: {self.log_file}")

    async def process_registration(self, line):
        # Check if the line matches the ACCESS pattern
        match = re.search(ACCESS_PATTERN, line)
        if match:
            rank = match.group(1)
            name = match.group(2)
            code = match.group(3)
            print(f"[DEBUG] Received ACCESS message: Rank={rank}, Name={name}, Code={code}")

            # Find the user with the matching registration code
            if code in self.pending_registrations:
                user_id = self.pending_registrations[code]
                guild = self.bot.get_guild(int(self.server_id))
                if guild:
                    member = discord.utils.get(guild.members, id=user_id)
                    if member:
                        # Assign the appropriate role based on the rank
                        role_id = self.get_role_id(rank)
                        if role_id:
                            role = guild.get_role(int(role_id))
                            if role:
                                await member.add_roles(role)
                                await member.send(f"Thank you for registering, {name}! You have been assigned the role: {role.name}")
                                print(f"[DEBUG] Assigned role '{role.name}' to member {member.id}")

                                # Store the registration in the registrations.json file
                                self.store_registration(user_id, name)
                            else:
                                await member.send(f"Role with ID '{role_id}' not found.")
                                print(f"[DEBUG] Role with ID '{role_id}' not found in the server")
                        else:
                            await member.send(f"Unknown rank: {rank}")
                            print(f"[DEBUG] Unknown rank: {rank}")

                        # Remove the pending registration and timestamp
                        del self.pending_registrations[code]
                        del self.registration_timestamps[code]
                        print(f"[DEBUG] Removed pending registration for member {member.id}")
                    else:
                        print(f"[DEBUG] Member {user_id} not found in the guild")
                else:
                    print(f"[DEBUG] Guild not found")
            else:
                print(f"[DEBUG] Invalid registration code: {code}")

    def get_role_id(self, rank):
        # Map the rank to the corresponding role ID
        role_mapping = {
            'moderator': self.config['discord']['moderator_role_id'],
            'regular': self.config['discord']['regular_role_id'],
            'trusted': self.config['discord']['trusted_role_id'],
            'normal': self.config['discord']['normal_role_id']
        }
        return role_mapping.get(rank.lower())

    def store_registration(self, user_id, player_name):
        # Load the existing registrations from the file
        with open(self.registrations_file, "r") as file:
            registrations = json.load(file)

        # Add the new registration to the dictionary
        registrations[str(user_id)] = player_name

        # Save the updated registrations back to the file
        with open(self.registrations_file, "w") as file:
            json.dump(registrations, file, indent=4)

        print(f"[DEBUG] Stored registration for user {user_id} with player name '{player_name}'")

    def remove_expired_registrations(self):
        """Remove registrations that are older than one hour."""
        one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
        expired_codes = [code for code, timestamp in self.registration_timestamps.items() if timestamp < one_hour_ago]

        for code in expired_codes:
            del self.pending_registrations[code]
            del self.registration_timestamps[code]

        print(f"[DEBUG] Removed {len(expired_codes)} expired registration(s)")

async def setup(bot):
    await bot.add_cog(RegistrationCog(bot))