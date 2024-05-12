import discord
from discord.ext import commands
from factorio_rcon import RCONClient

class PlayerManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rcon_client = None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"PlayerManagementCog is ready.")

    async def connect_rcon(self):
        rcon_host = self.bot.config['factorio_server']['rcon_host']
        rcon_port = self.bot.config['factorio_server']['default_rcon_port']
        rcon_password = self.bot.config['factorio_server']['default_rcon_password']

        try:
            self.rcon_client = RCONClient(rcon_host, rcon_port, rcon_password)
            await self.bot.loop.run_in_executor(None, self.rcon_client.connect)
            print("RCON client connected successfully.")
            return True
        except Exception as e:
            print(f"Error connecting to RCON: {str(e)}")
            self.rcon_client = None
            return False

    async def send_rcon_command(self, command):
        if not self.rcon_client:
            success = await self.connect_rcon()
            if not success:
                return "Failed to establish RCON connection."

        try:
            response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, command)
            print(f"RCON command sent: {command}")
            print(f"RCON response: {response}")
            return response
        except Exception as e:
            print(f"Error sending RCON command: {str(e)}")
            self.rcon_client = None
            return "An error occurred while sending the command to the server."

    @commands.hybrid_command(name='enablecheats', description='Enable or disable cheats on the Factorio server')
    @commands.guild_only()
    async def enablecheats(self, ctx, value: str):
        value = value.lower()
        if value == "on":
            response = await self.send_rcon_command("/enablecheats on")
        elif value == "off":
            response = await self.send_rcon_command("/enablecheats off")
        else:
            response = "Invalid value. Use `/enablecheats on` or `/enablecheats off`"
        await ctx.send(response)

    @commands.hybrid_command(name='cspawn', description='Spawn the character at the specified coordinates')
    @commands.guild_only()
    async def cspawn(self, ctx, coordinates: str):
        response = await self.send_rcon_command(f"/cspawn {coordinates}")
        await ctx.send(response)

    @commands.hybrid_command(name='rechart', description='Recreate the map')
    @commands.guild_only()
    async def rechart(self, ctx):
        response = await self.send_rcon_command("/rechart")
        await ctx.send(response)

    @commands.hybrid_command(name='kick', description='Kick a player from the server')
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, name: str):
        response = await self.send_rcon_command(f"/kick {name}")
        await ctx.send(response)

    @commands.hybrid_command(name='banish', description='Ban a player from the server')
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def banish(self, ctx, name: str):
        response = await self.send_rcon_command(f"/ban {name}")
        await ctx.send(response)

    @commands.hybrid_command(name='unbanish', description='Unban a player from the server')
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def unbanish(self, ctx, name: str):
        response = await self.send_rcon_command(f"/unban {name}")
        await ctx.send(response)

async def setup(bot):
    await bot.add_cog(PlayerManagementCog(bot))