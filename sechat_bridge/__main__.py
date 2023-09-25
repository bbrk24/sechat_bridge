import asyncio
from typing import Optional

import discord
import sechat

# idk how to do this properly so I just put secrets.py in the gitignore
from .secrets import *

room: Optional[sechat.Room] = None

class DiscordClient(discord.Client):
    async def on_message(self, message: discord.Message):
        print(f'Discord message from {message.author}: {message.content}')

async def main():
    global room

    sechat_client = sechat.Bot()
    await sechat_client.authenticate(email, password, 'https://codegolf.stackexchange.com')
    room = await sechat_client.joinRoom(1)

    @room.on(sechat.EventType.MESSAGE)
    async def on_message(room: sechat.Room, message: sechat.MessageEvent):
        print(f'SE message from {message.user_name}: {message.content}')

    intents = discord.Intents.none()
    intents.guild_messages = True
    intents.message_content = True

    discord_client = DiscordClient(intents=intents)
    await discord_client.start(token)

if __name__ == '__main__':
    asyncio.run(main())
