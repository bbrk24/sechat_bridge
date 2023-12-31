from asyncio import gather
from typing import Optional

import discord

class DiscordClient(discord.Client):
    def __init__(self, channel_id: int, intents: discord.Intents):
        self.CHANNEL_ID = channel_id
        self.channel: Optional[discord.abc.GuildChannel | discord.Thread] = None
        super().__init__(intents=intents)
    
    async def on_ready(self):
        self.channel = await self.fetch_channel(self.CHANNEL_ID)
        assert not isinstance(self.channel, discord.abc.PrivateChannel)
