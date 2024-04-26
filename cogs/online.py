import discord
from discord.ext import commands
from discord import app_commands

def get_last_online_message(log_file_path):
    try:
        with open(log_file_path, "r") as file:
            lines = file.readlines()
            for line in reversed(lines):
                if "[ONLINE2]" in line:
                    return line.strip()
    except FileNotFoundError:
        return ""
    return ""

def parse_player_data(log_entry):
    try:
        player_data = log_entry.split("[ONLINE2]")[-1].strip()
        player_entries = player_data.split(";")
        response_lines = []
        for entry in player_entries:
            if entry.strip():
                parts = entry.split(",")
                if len(parts) < 4:
                    continue  # Skip if there aren't enough data parts to parse
                username = parts[0]
                score = parts[1]
                time_minutes = parts[2]
                rank = parts[3].strip()
                hours_played = int(time_minutes) // 60  # Convert minutes to hours
                afk_time = ""
                if len(parts) > 4 and parts[4].strip():  # Check if the AFK time is present and not empty
                    afk_time = f", AFK for {parts[4].strip()}"
                player_info = f"{username} - **Score**: {score}, **Time Played**: {hours_played} hours, **Rank**: {rank}{afk_time}"
                response_lines.append(player_info)
        return "\n".join(response_lines) if response_lines else "No players online."
    except Exception as e:
        print(f"Error parsing player data: {e}")
        return "Error processing player data."

class OnlineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="online", description="Show currently online players and their stats")
    async def online(self, interaction: discord.Interaction):
        log_file_path = "/opt/factorio/factorio-server-console.log"
        online_message = get_last_online_message(log_file_path)
        if "[ONLINE2]" in online_message:
            player_info = parse_player_data(online_message)
            embed = discord.Embed(title="Online Players", description="Here are the currently online players and their stats:", color=0x00ff00)
            for line in player_info.split('\n'):
                if line:
                    parts = line.split(" - ")
                    username = parts[0].strip()
                    details = " - ".join(parts[1:])
                    embed.add_field(name=f"**{username}**", value=details, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No recent online data available.")

async def setup(bot):
    await bot.add_cog(OnlineCog(bot))