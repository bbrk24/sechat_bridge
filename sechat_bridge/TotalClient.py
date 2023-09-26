from asyncio import gather
from types import TracebackType
from typing import Callable, Coroutine, Optional

from aiohttp import ClientSession
import discord
import sechat

from .DiscordClient import DiscordClient
from .html_to_md import se_content_to_str

WAITING_EMOTE = '🟡'
SUCCESS_EMOTE = '✅'
ERROR_EMOTE = '❌'

class TotalClient:
    # MARK: Internals
    def __init__(
        self,
        room_id: int,
        channel_id: int,
        email: str,
        se_password: str,
        discord_token: str,
        se_host = 'https://codegolf.stackexchange.com'
    ):
        self.se_bot = sechat.Bot()
        self.room_id = room_id
        self.session: Optional[ClientSession] = None

        intents = discord.Intents.none()
        intents.guild_messages = True
        intents.message_content = True
        self.discord_client = DiscordClient(None, channel_id, intents)
        
        self.se_login_info = (email, se_password, se_host)
        self.discord_login_info = (discord_token,)

        attrs = filter(lambda el: el.startswith('_on_discord_'), dir(self))
        self.events = {
            attr.strip('_on_discord_'): getattr(self, attr) for attr in attrs
        }

    @property
    def _room(self):
        return self.discord_client.room
    
    @property
    def _discord_user_id(self):
        return self.discord_client.user.id


    async def _se_login(self):
        await self.se_bot.authenticate(*self.se_login_info)
        self.discord_client.room = await self.se_bot.joinRoom(self.room_id)

    async def _discord_login(self):
        await self.discord_client.login(*self.discord_login_info)

    def _register_discord_event(self, event_name: str, handler: Callable[..., Coroutine]):
        setattr(
            self.discord_client,
            'on_' + event_name,
            handler
        )

    async def __aenter__(self):
        for i in self.events.items():
            self._register_discord_event(*i)

        _0, _1, session = await gather(self._se_login(), self._discord_login(), ClientSession().__aenter__())
        self.session = session

        self._room.register(self._on_se_message, sechat.EventType.MESSAGE)

        return self.discord_client
    
    async def __aexit__(self, *args):
        await self.session.__aexit__(*args)
        self.se_bot.leaveAllRooms()

    # MARK: Discord event handlers
    async def _on_discord_message(self, message: discord.Message):
        if message.author.id != self._discord_user_id and message.channel.id == self.discord_client.CHANNEL_ID and self._room is not None:
            await message.add_reaction(WAITING_EMOTE)
            new_emote_coroutine = None
            try:
                await self._room.send(f'{message.author.display_name}: {message.content}')
                for attachment in message.attachments:
                    # How to get ratelimited 101
                    await self._room.send(attachment.url.split('?')[0])
            except:
                new_emote_coroutine = message.add_reaction(ERROR_EMOTE)
                raise
            else:
                new_emote_coroutine = message.add_reaction(SUCCESS_EMOTE)
            finally:
                await gather(
                    new_emote_coroutine,
                    message.remove_reaction(WAITING_EMOTE, self.discord_client.user)
                )

    async def _on_discord_message_edit(self, before: discord.Message, after: discord.Message):
        pass
    
    # MARK: SE event handlers
    async def _on_se_message(self, room: sechat.Room, message: sechat.MessageEvent):
        if message.user_id != self.se_bot.userID and self.discord_client.channel is not None:
            message_content, embed = await se_content_to_str(message.content, self.session)
            if embed is None:
                await self.discord_client.channel.send(f'{message.user_name}: {message_content}')
            elif isinstance(embed, discord.File):
                await self.discord_client.channel.send(
                    f'{message.user_name}: {message_content}',
                    file=embed
                )
            else:
                await self.discord_client.channel.send(
                    f'{message.user_name}: {message_content}',
                    embed=embed
                )
