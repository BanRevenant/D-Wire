import discord
from discord.ext import commands
from discord import app_commands 
from factorio_rcon import RCONClient
from logger import setup_logger
from config_manager import ConfigManager

logger = setup_logger(__name__, 'logs/playermanagement.log')

class PlayerManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        self.rcon_client = None
        logger.info("PlayerManagementCog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("PlayerManagementCog is ready.")

    async def connect_rcon(self):
        rcon_host = self.config_manager.get('factorio_server.rcon_host')
        rcon_port = self.config_manager.get('factorio_server.default_rcon_port')
        rcon_password = self.config_manager.get('factorio_server.default_rcon_password')

        try:
            self.rcon_client = RCONClient(rcon_host, rcon_port, rcon_password)
            await self.bot.loop.run_in_executor(None, self.rcon_client.connect)
            logger.info("RCON client connected successfully.")
            return True
        except Exception as e:
            logger.error(f"Error connecting to RCON: {str(e)}")
            self.rcon_client = None
            return False

    async def send_rcon_command(self, command):
        if not self.rcon_client:
            success = await self.connect_rcon()
            if not success:
                logger.error("Failed to establish RCON connection.")
                return "Failed to establish RCON connection."

        try:
            response = await self.bot.loop.run_in_executor(None, self.rcon_client.send_command, command)
            logger.info(f"RCON command sent: {command}")
            if response:
                logger.info(f"RCON response: {response}")
                return response
            else:
                return "Command executed successfully."
        except Exception as e:
            logger.error(f"Error sending RCON command: {str(e)}")
            self.rcon_client = None
            return "An error occurred while sending the command to the server."

    @commands.hybrid_command(name='enablecheats', description='Enable or disable cheats on the Factorio server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
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
        logger.info(f"Cheats {'enabled' if value == 'on' else 'disabled'} by {ctx.author}")

    @commands.hybrid_command(name='cspawn', description='Spawn the character at the specified coordinates')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.guild_only()
    async def cspawn(self, ctx, coordinates: str):
        response = await self.send_rcon_command(f"/cspawn {coordinates}")
        await ctx.send(response)
        logger.info(f"Character spawned at {coordinates} by {ctx.author}")

    @commands.hybrid_command(name='rechart', description='Recreate the map')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.guild_only()
    async def rechart(self, ctx):
        response = await self.send_rcon_command("/rechart")
        await ctx.send(response)
        logger.info(f"Map recharted by {ctx.author}")

    @commands.hybrid_command(name='kick', description='Kick a player from the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, name: str):
        response = await self.send_rcon_command(f"/kick {name}")
        await ctx.send(response)
        logger.info(f"Player {name} kicked by {ctx.author}")

    @commands.hybrid_command(name='ban', description='Ban a player from the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx, name: str):
        response = await self.send_rcon_command(f"/ban {name}")
        await ctx.send(response)
        logger.info(f"Player {name} banned by {ctx.author}")

    @commands.hybrid_command(name='unban', description='Unban a player from the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self, ctx, name: str):
        response = await self.send_rcon_command(f"/unban {name}")
        await ctx.send(response)
        logger.info(f"Player {name} unbanned by {ctx.author}")

    @commands.hybrid_command(name='unbanish', description='Unbanish a player on the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.guild_only()
    async def unbanish(self, ctx, name: str):
        response = await self.send_rcon_command(f"/unbanish {name}")
        await ctx.send(response)
        logger.info(f"Player {name} unbanished by {ctx.author}")

    @commands.hybrid_command(name='banish', description='Banish a player on the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.guild_only()
    async def banish(self, ctx, name: str):
        response = await self.send_rcon_command(f"/banish {name}")
        await ctx.send(response)
        logger.info(f"Player {name} banished by {ctx.author}")

    @commands.hybrid_command(name='mute', description='Mute a player on the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.guild_only()
    async def mute(self, ctx, name: str):
        response = await self.send_rcon_command(f"/mute {name}")
        await ctx.send(response)
        logger.info(f"Player {name} muted by {ctx.author}")

    @commands.hybrid_command(name='unmute', description='Unmute a player on the server')
    @app_commands.checks.has_permissions(administrator=True, moderate_members=True)  # Only server administrators can use this
    @commands.guild_only()
    async def unmute(self, ctx, name: str):
        response = await self.send_rcon_command(f"/unmute {name}")
        await ctx.send(response)
        logger.info(f"Player {name} unmuted by {ctx.author}")

async def setup(bot):
    await bot.add_cog(PlayerManagementCog(bot))
    logger.info("PlayerManagementCog added to bot")