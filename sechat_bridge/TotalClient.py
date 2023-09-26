from asyncio import gather
from typing import Any, Callable, Coroutine, List, Optional

from aiohttp import ClientSession
import discord
import sechat

from .db import MessageDB
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
        self.db = MessageDB()

        intents = discord.Intents.none()
        intents.guild_messages = True
        intents.message_content = True
        intents.reactions = True
        self.discord_client = DiscordClient(channel_id, intents)
        
        self.se_login_info = (email, se_password, se_host)
        self.discord_login_info = (discord_token,)

        attrs = filter(lambda el: el.startswith('_on_discord_'), dir(self))
        self.events = {
            attr.strip('_on_discord_'): getattr(self, attr) for attr in attrs
        }
    
    @property
    def _discord_user_id(self):
        return self.discord_client.user.id

    @property
    def _channel_id(self):
        return self.discord_client.CHANNEL_ID

    def _can_process(self, message: discord.Message):
        return message.author.id != self._discord_user_id and message.channel.id == self._channel_id and self._room is not None

    async def _se_login(self):
        await self.se_bot.authenticate(*self.se_login_info)
        self._room = await self.se_bot.joinRoom(self.room_id)

    async def _discord_login(self):
        await self.discord_client.login(*self.discord_login_info)

    def _register_discord_event(self, event_name: str, handler: Callable[..., Coroutine]):
        setattr(
            self.discord_client,
            'on_' + event_name,
            handler
        )
    
    async def _remove_own_reactions(self, message: discord.Message):
        coroutines: List[Coroutine[Any, Any, None]] = []
        for reaction in message.reactions:
            if reaction.emoji in {SUCCESS_EMOTE, WAITING_EMOTE, ERROR_EMOTE} and reaction.me:
                coroutines.append(reaction.remove(self.discord_client.user))
        await gather(*coroutines)

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
        if not self._can_process(message):
            return
        await message.add_reaction(WAITING_EMOTE)
        msg_ids: List[int] = []
        try:
            id = await self._room.send(f'{message.author.display_name}: {message.content}')
            msg_ids.append(id)

            for attachment in message.attachments:
                # How to get ratelimited 101
                id = await self._room.send(attachment.url.split('?')[0])
                msg_ids.append(id)
        except:
            new_emote_coroutine = message.add_reaction(ERROR_EMOTE)
            raise
        else:
            new_emote_coroutine = message.add_reaction(SUCCESS_EMOTE)
        finally:
            await gather(
                new_emote_coroutine,
                message.remove_reaction(WAITING_EMOTE, self.discord_client.user),
                self.db.correlate_msgs(discord_ids=[message.id], se_ids=msg_ids)
            )

    async def _on_discord_message_edit(self, before: discord.Message, after: discord.Message):
        if not self._can_process(before):
            return
        se_ids = await self.db.get_se_ids(before.id)
        if len(se_ids) == 0:
            return
        se_id = min(se_ids)
        await self._remove_own_reactions(before)
        await after.add_reaction(WAITING_EMOTE)
        try:
            await self._room.edit(se_id, f'{after.author.display_name}: {after.content}')
        except:
            new_emote_coroutine = after.add_reaction(ERROR_EMOTE)
            raise
        else:
            new_emote_coroutine = after.add_reaction(SUCCESS_EMOTE)
        finally:
            await gather(
                new_emote_coroutine,
                after.remove_reaction(WAITING_EMOTE, self.discord_client.user)
            )

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
