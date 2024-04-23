import discord
from discord.ext import commands
import asyncio
import json
import aiohttp
import websockets
import re

class SendChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.websocket = None
        self.channel_id = self.bot.config['discord']['channel_id']
        self.debug_channel = None
        self.login_url = self.bot.config['factorio_server_manager']['login_url']
        self.username = self.bot.config['factorio_server_manager']['username']
        self.password = self.bot.config['factorio_server_manager']['password']

    async def login_and_get_cookie(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.login_url, json={'username': self.username, 'password': self.password}) as response:
                    if response.status == 200:
                        cookie = response.cookies.get('authentication')
                        return cookie.value if cookie else None
                    else:
                        return None
        except Exception as e:
            print(f"Error during login: {str(e)}")
            return None

    async def connect_websocket(self):
        try:
            cookie = await self.login_and_get_cookie()
            if cookie:
                headers = {'Cookie': f'authentication={cookie}'}
                self.websocket = await websockets.connect('ws://localhost/ws', extra_headers=headers)
                print("WebSocket connected successfully.")
            else:
                print("Failed to get authentication cookie.")
        except Exception as e:
            print(f"Error connecting to WebSocket: {str(e)}")

    async def send_debug_message(self, message):
        if self.debug_channel:
            await self.debug_channel.send(f"Debug: {message}")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"SendChatCog is ready.")
        self.debug_channel = self.bot.get_channel(int(self.channel_id))
        await self.connect_websocket()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith("!"):
            return

        try:
            # Escape special characters in the message
            escaped_message = re.sub(r'([^a-zA-Z0-9\s])', r'\\\1', message.content)

            wrapped_message = {
                "room_name": "",
                "controls": {"type": "command", "value": f"/cchat {message.author.display_name}: {escaped_message}"}
            }
            print(f"Sending message to WebSocket: {json.dumps(wrapped_message)}")
            await self.websocket.send(json.dumps(wrapped_message))
            print("Message sent to WebSocket successfully.")
        except Exception as e:
            print(f"Error sending message to WebSocket: {str(e)}")

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")

    async def cog_unload(self):
        if self.websocket:
            await self.websocket.close()
            print("WebSocket closed.")

async def setup(bot):
    await bot.add_cog(SendChatCog(bot))