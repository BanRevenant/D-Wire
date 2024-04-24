import os
import discord
from discord.ext import commands, tasks

class RegisterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_file = "/opt/factorio/factorio-server-console.log"
        self.last_position = 0
        self.registration_codes = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"RegisterCog is ready.")
        self.check_log.start()

    def cog_unload(self):
        self.check_log.cancel()

    async def process_registration(self, line):
        if "[Registration System]" in line:
            parts = line.split("]")
            if len(parts) >= 3:
                player_name = parts[1].strip()[1:]
                code = parts[2].strip()[1:]
                self.registration_codes[code] = player_name
                # print(f"Registration code for {player_name}: {code}")
            else:
                print("Invalid registration line format.")

    @tasks.loop(seconds=5)
    async def check_log(self):
        # print("Checking log file...")
        try:
            with open(self.log_file, "r") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                for line in new_lines:
                    await self.process_registration(line)

        except FileNotFoundError:
            print(f"Log file not found: {self.log_file}")
        # print("Log file check completed.")

    @commands.command()
    async def register(self, ctx, code: str):
        # print(f"Received registration code: {code}")
        # print(f"Current registration codes: {self.registration_codes}")
        if code in self.registration_codes:
            player_name = self.registration_codes[code]
            role = ctx.guild.get_role(1219796319347150989)
            await ctx.author.add_roles(role)
            await ctx.send(f"Thank you for registering, {player_name}!")
            del self.registration_codes[code]
        else:
            await ctx.send("Invalid registration code. Please make sure you have initiated the registration process in-game by typing `/register` in the Factorio game chat.")

        await ctx.message.delete(delay=5)
        await ctx.send(f"{ctx.author.mention}, this message will self-destruct in 5 seconds.", delete_after=5)

async def setup(bot):
    await bot.add_cog(RegisterCog(bot))