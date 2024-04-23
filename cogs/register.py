import discord
from discord.ext import commands

class RegisterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.registration_codes = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if "[Registration System]" in message.content:
            parts = message.content.split("]")
            player_name = parts[1].strip()[1:]
            code = parts[2].strip()[1:]
            self.registration_codes[player_name] = code
            print(f"Registration code for {player_name}: {code}")

    @commands.command()
    async def register(self, ctx, code: str):
        player_name = str(ctx.author)
        if player_name in self.registration_codes:
            if self.registration_codes[player_name] == code:
                role = ctx.guild.get_role(1219796319347150989)
                await ctx.author.add_roles(role)
                await ctx.send("Thank you for registering!")
                del self.registration_codes[player_name]
            else:
                await ctx.send("Invalid registration code. Please try again.")
        else:
            await ctx.send("You haven't initiated the registration process in-game. Please type `/register` in the Factorio game chat to get your registration code.")

        await ctx.message.delete(delay=5)
        await ctx.send(f"{ctx.author.mention}, this message will self-destruct in 5 seconds.", delete_after=5)

async def setup(bot):
    await bot.add_cog(RegisterCog(bot))