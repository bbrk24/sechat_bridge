import asyncio
import itertools
import re
from typing import Any, Generator, Optional

import bs4
import discord
import sechat

# idk how to do this properly so I just put secrets.py in the gitignore
from .secrets import *

room: Optional[sechat.Room] = None

class DiscordClient(discord.Client):
    def __init__(self, intents: discord.Intents):
        self.channel_id = 771395175595245603
        self.channel: Optional[discord.abc.GuildChannel | discord.Thread] = None
        super().__init__(intents=intents)
    
    async def on_ready(self):
        self.channel = await self.fetch_channel(self.channel_id)

    async def on_message(self, message: discord.Message):
        if message.author.id != self.user.id and message.channel.id == self.channel_id and room is not None:
            await room.send(f'{message.author.display_name}: {message.content}')

html_regex = re.compile(r"<(\w+).*>.*</\1>", re.RegexFlag.DOTALL)
def se_content_to_str(content: str):
    if html_regex.match(content):
        try:
            soup = bs4.BeautifulSoup(content)
            print('translating HTML to MD:', content)
        except bs4.ParserRejectedMarkup:
            return content
    else:
        return content
    
    onebox = soup.find(lambda el: el.has_attr('class') and 'onebox' in el['class'])
    if onebox is not None:
        ob_type = list(filter(lambda c: c.startswith('ob-'), onebox['class']))[0]
        match ob_type:
            case 'ob-image':
                return soup.find('img').attrs['src']
            case 'ob-youtube' | 'ob-wikipedia' | 'ob-xkcd':
                return soup.find('a').attrs['href']
            case 'ob-message':
                return 'https://chat.stackexchange.com' + soup.find('a', {'class': 'roomname'}).attrs['href']
            case 'ob-post':
                return 'https:' + soup.find('a').attrs['href']
            case _:
                print('Unknown onebox type', ob_type)

    def translate_tag(tag: bs4.PageElement) -> Generator[str, Any, None]:
        if isinstance(tag, bs4.Tag):
            match tag.name:
                case 'i' | 'em':
                    yield '*'
                    yield from itertools.chain(*map(translate_tag, tag.children))
                    yield '*'
                case 'b' | 'strong':
                    yield '**'
                    yield from itertools.chain(*map(translate_tag, tag.children))
                    yield '**'
                case 'a':
                    yield '['
                    yield from itertools.chain(*map(translate_tag, tag.children))
                    yield '](<'
                    yield tag.attrs['href']
                    yield '>)'
                case 'pre':
                    yield '```\n'
                    yield tag.text
                    yield '\n```'
                case 'code':
                    marker = '`' if '``' in tag.text else '``'
                    yield marker
                    if tag.text.startswith('`'):
                        yield ' '
                    yield tag.text
                    if tag.text.endswith('`'):
                        yield ' '
                    yield marker
                case 'br':
                    yield '\n'
                case 'strike':
                    yield '~~'
                    yield from itertools.chain(*map(translate_tag, tag.children))
                    yield '~~'
                case _:
                    yield from itertools.chain(*map(translate_tag, tag.children))
        else:
            yield discord.utils.escape_markdown(tag.text)


    # holy cow Python, why is this so complicated. Why can I not just have flatmap
    return ''.join(itertools.chain(*map(translate_tag, soup.children)))

async def main():
    global room

    sechat_client = sechat.Bot()
    await sechat_client.authenticate(email, password, 'https://codegolf.stackexchange.com')
    room = await sechat_client.joinRoom(1)

    intents = discord.Intents.none()
    intents.guild_messages = True
    intents.message_content = True

    discord_client = DiscordClient(intents=intents)

    @room.on(sechat.EventType.MESSAGE)
    async def on_message(room: sechat.Room, message: sechat.MessageEvent):
        if message.user_id != sechat_client.userID and discord_client.channel is not None:
            message_content = se_content_to_str(message.content)
            await discord_client.channel.send(f'{message.user_name}: {message_content}')

    await discord_client.start(token)

if __name__ == '__main__':
    asyncio.run(main())
