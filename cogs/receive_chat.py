import discord
from discord.ext import commands
import asyncio
import json
import aiohttp
import websockets

class ReceiveChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.websocket = None
        self.console_channel_id = 1228552030293852211  # Replace with your console channel ID
        self.websocket_url = 'ws://localhost/ws'
        self.login_url = 'http://localhost/api/login'
        self.username = 'admin'
        self.password = 'x'
        self.receive_lock = asyncio.Lock()

    async def login_and_get_cookie(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.login_url, json={'username': self.username, 'password': self.password}) as response:
                    if response.status == 200:
                        cookie = response.cookies.get('authentication')
                        return cookie.value if cookie else None
                    else:
                        await self.log_to_console(f"Login failed with status code: {response.status}")
                        return None
        except Exception as e:
            await self.log_to_console(f"Error during login: {str(e)}")
            return None

    async def connect_websocket(self):
        try:
            cookie = await self.login_and_get_cookie()
            if cookie:
                headers = {'Cookie': f'authentication={cookie}'}
                await self.log_to_console(f"Connecting to WebSocket: {self.websocket_url}")
                self.websocket = await websockets.connect(self.websocket_url, extra_headers=headers)
                await self.log_to_console("WebSocket connected successfully.")
                asyncio.create_task(self.receive_messages())
            else:
                await self.log_to_console("Failed to obtain login cookie.")
        except Exception as e:
            await self.log_to_console(f"Error connecting to WebSocket: {str(e)}")

    async def receive_messages(self):
        while True:
            try:
                async with self.receive_lock:
                    message = await self.websocket.recv()
                    await self.log_to_console(f"Received message: {message}")  
                    await self.send_discord_message(message)  
            except websockets.exceptions.ConnectionClosed:
                await self.log_to_console("WebSocket connection closed. Reconnecting...")
                await self.connect_websocket()
            except Exception as e:
                await self.log_to_console(f"Error receiving message: {str(e)}")

    async def send_discord_message(self, message):
        console_channel = self.bot.get_channel(self.console_channel_id)
        if console_channel:
            await console_channel.send(f"Received Message: {message}")  
            await self.log_to_console(f"Message sent to Discord: {message}")
        else:
            await self.log_to_console("Console channel not found.")

    async def log_to_console(self, message):
        console_channel = self.bot.get_channel(self.console_channel_id)
        if console_channel:
            await console_channel.send(f"Console: {message}")
        else:
            print(f"Console: {message}")  

    @commands.Cog.listener()
    async def on_ready(self):
        await self.log_to_console("ReceiveChatCog is ready.")
        await self.connect_websocket()

    async def cog_unload(self):
        if self.websocket:
            await self.websocket.close()
            await self.log_to_console("WebSocket closed.")

async def setup(bot):
    await bot.add_cog(ReceiveChatCog(bot))