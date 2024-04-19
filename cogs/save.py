import discord
from discord.ext import commands
import os
import time


class Save(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def save(self, ctx):
        """Save the server and upload the most recent file edited within 3 seconds."""
        # Send the /server-save command
        # Implement your RCON command execution logic here

        # Wait for 3 seconds for the file modification
        time.sleep(3)

        # Get the save directory path from the JSON configuration
        save_directory = self.bot.get_cog("ConfigCog").config["paths"]["save_directory"]

        # Access the most recently edited file in the save directory
        files = os.listdir(save_directory)
        files = [os.path.join(save_directory, file) for file in files]

        # Sort the files based on modification time (most recent first)
        files.sort(key=os.path.getmtime, reverse=True)

        # Select the most recent file
        most_recent_file = files[0]

        # Upload the most recent file to the Discord channel
        file = discord.File(most_recent_file)

        embed = discord.Embed(title="Most Recently Saved File",
                              description=f"Game file: {os.path.basename(most_recent_file)}")
        embed.set_image(url="attachment://file.png")

        await ctx.send(embed=embed, file=file)


async def setup(bot):
    await bot.add_cog(Save(bot))
