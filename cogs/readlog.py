import os
import re
import discord
from discord.ext import commands, tasks

JOIN_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[JOIN\] (.+) joined the game"
RESEARCH_PATTERN = r"\[MSG\] Research (.+) completed\."
CHAT_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[CHAT\] (.+): (.+)"
LEAVE_PATTERN = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[LEAVE\] (.+) left the game"
DEATH_PATTERN = r"\[MSG\] (\w+) was killed by (.+) at \[gps"

def send_discord_notification(event_type, data):
    if event_type == "JOIN":
        message = f"**{data}** joined the game."
    elif event_type == "RESEARCH":
        message = f"**Research Completed:** {data}"
    elif event_type == "CHAT":
        message = f"**{data[0]}** says: {data[1]}"
    elif event_type == "LEAVE":
        message = f"**{data}** left the game."
    elif event_type == "DEATH":
        message = f"**{data[0]}** was killed by {data[1]}"
    elif event_type == "SCRIPT_RELOADED":
        message = "**Script has been modified and reloaded successfully.**"
    else:
        message = f"**Unknown Event:** {data}"
    return message

class ReadLogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_file = "/opt/factorio/factorio-server-console.log"
        self.last_position = self.get_last_position()

    def cog_unload(self):
        self.check_log.cancel()

    def get_last_position(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(0, os.SEEK_END)
                last_position = file.tell()
                return last_position
        except FileNotFoundError:
            return 0

    @tasks.loop(seconds=1)
    async def check_log(self):
        try:
            with open(self.log_file, "r") as file:
                file.seek(self.last_position)
                new_lines = file.readlines()
                self.last_position = file.tell()

                if new_lines:
                    channel_id = self.bot.config['discord']['channel_id']
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        for line in new_lines:
                            join_match = re.search(JOIN_PATTERN, line)
                            research_match = re.search(RESEARCH_PATTERN, line)
                            chat_match = re.search(CHAT_PATTERN, line)
                            leave_match = re.search(LEAVE_PATTERN, line)
                            death_match = re.search(DEATH_PATTERN, line)

                            if join_match:
                                message = send_discord_notification("JOIN", join_match.group(2))
                            elif research_match:
                                message = send_discord_notification("RESEARCH", research_match.group(1))
                            elif chat_match:
                                message = send_discord_notification("CHAT", (chat_match.group(2), chat_match.group(3)))
                            elif leave_match:
                                message = send_discord_notification("LEAVE", leave_match.group(2))
                            elif death_match:
                                message = send_discord_notification("DEATH", (death_match.group(1), death_match.group(2)))
                            else:
                                continue

                            await channel.send(message)

        except FileNotFoundError:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_log.start()

async def setup(bot):
    await bot.add_cog(ReadLogCog(bot))