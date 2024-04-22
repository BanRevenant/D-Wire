import os
import discord
from discord.ext import commands, tasks

class ReadLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_file = "/opt/factorio/factorio-server-console.log"
        self.last_position = self.get_last_position()
        # print("ReadLogCog initialized.")

    def cog_unload(self):
        # print("ReadLogCog unloading...")
        self.check_log.cancel()
        # print("check_log task canceled.")

    def get_last_position(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(0, os.SEEK_END)
                last_position = file.tell()
                return last_position
        except FileNotFoundError:
            return 0

    @tasks.loop(seconds=5)  # Adjust the interval as needed
    async def check_log(self):
        # print("Checking log file...")
        try:
            with open(self.log_file, "r") as file:
                # print(f"Opened log file: {self.log_file}")
                file.seek(self.last_position)
                new_lines = file.readlines()
                # print(f"Read new lines: {new_lines}")
                self.last_position = file.tell()
                # print(f"Updated last position: {self.last_position}")

                # print(f"New lines: {new_lines}")

                if new_lines:
                    # print("New lines found.")
                    channel_id = self.bot.config['discord']['channel_id']
                    # print(f"Channel ID: {channel_id}")
                    channel = self.bot.get_channel(int(channel_id))
                    # print(f"Channel: {channel}")
                    if channel:
                        # print("Channel found.")
                        for line in new_lines:
                            # print(f"Sending line: {line.strip()}")
                            await channel.send(line.strip())
                            # print("Line sent to channel.")
                    # else:
                        # print("Channel not found.")
                # else:
                    # print("No new lines found.")

        except FileNotFoundError:
            pass
            # print(f"Log file not found: {self.log_file}")

    @commands.Cog.listener()
    async def on_ready(self):
        # print("Bot is ready. Starting log checking...")
        self.check_log.start()
        # print("check_log task started.")

async def setup(bot):
    await bot.add_cog(ReadLogCog(bot))
    # print("ReadLogCog loaded.")