from itertools import chain
from typing import Any, Generator, List, Tuple, Union

from aiohttp import ClientSession
import bs4
import discord

BADGE_INFOS = [
    ('badge1', '🥇'),
    ('badge2', '🥈'),
    ('badge3', '🥉')
]

async def se_content_to_str(content: str, session: ClientSession) -> Tuple[str, Union[discord.Embed, discord.File, None]]:
    if '<' in content:
        try:
            soup = bs4.BeautifulSoup(content)
            print('translating HTML to MD:', content)
        except bs4.ParserRejectedMarkup:
            print('Error, not HTML:', content)
            return content, None
    else:
        return content, None
    
    onebox = soup.find(lambda el: el.has_attr('class') and 'onebox' in el['class'])
    if onebox is not None:
        ob_type = list(filter(lambda c: c.startswith('ob-'), onebox['class']))[0]
        match ob_type:
            case 'ob-image':
                img = soup.find('img')
                url = img.attrs['src']
                if url.startswith('//'):
                    url = 'https:' + url
                
                return url, None # FIXME: The below crashes with a null byte?
                alt = img.attrs['alt'] if img.has_attr('alt') else None
                
                async with session.get(url) as response:
                    data = await response.content.read()
                    return '', discord.File(
                        data,
                        description=alt
                    )
            case 'ob-youtube' | 'ob-wikipedia' | 'ob-xkcd':
                return soup.find('a').attrs['href'], None
            case 'ob-message':
                return 'https://chat.stackexchange.com' + soup.find('a', class_='roomname').attrs['href'], None
            case 'ob-post':
                return 'https:' + soup.find('a').attrs['href'], None
            case 'ob-user':
                username_a = soup.find('a', class_='ob-user-username')
                user_name = discord.utils.escape_markdown(username_a.text)
                pfp_url = soup.find(class_='user-gravatar64').find('img').attrs['src']

                embed = discord.Embed(title=user_name).set_thumbnail(url=pfp_url)

                user_url = 'https:' + username_a.attrs['href']
                site_icon = username_a.previous_sibling
                if isinstance(site_icon, bs4.Tag) and site_icon.has_attr('title'):
                    embed.description = f'[User on {site_icon["title"]} Stack Exchange]({user_url})'
                else:
                    embed.description = f'Stack Exchange User: <{user_url}>'
                
                reputation = soup.find(class_='reputation-score')
                if reputation is not None:
                    embed.add_field(
                        name='Reputation',
                        value=reputation.text
                    )
                
                badges: List[str] = []
                for class_name, icon in BADGE_INFOS:
                    badge_icon_tag = soup.find(class_=class_name)
                    if badge_icon_tag is None:
                        continue
                    badge_count_tag = badge_icon_tag.next_sibling
                    if badge_count_tag is None:
                        continue
                    assert 'badgecount' in badge_count_tag.attrs['class']
                    badges.append(f'{icon} {badge_count_tag.text}')
                if len(badges) > 0:
                    embed.add_field(
                        name='Badges',
                        value=', '.join(badges)
                    )

                tags = soup.find_all(class_='ob-user-tag')
                if len(tags) > 0:
                    embed.add_field(
                        name='Top Tags',
                        value='\n'.join(
                            map(lambda tag: f'\\[{tag.text.strip()}\\] \\({tag.attrs["title"]}\\)', tags)
                        ),
                        inline=False
                    )
                
                return ' ', embed
            case _:
                print('Unknown onebox type', ob_type)

    def translate_tag(tag: bs4.PageElement) -> Generator[str, Any, None]:
        if isinstance(tag, bs4.Tag):
            match tag.name:
                case 'i' | 'em':
                    yield '*'
                    yield from chain(*map(translate_tag, tag.children))
                    yield '*'
                case 'b' | 'strong':
                    yield '**'
                    yield from chain(*map(translate_tag, tag.children))
                    yield '**'
                case 'a':
                    yield '['
                    yield from chain(*map(translate_tag, tag.children))
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
                    yield from chain(*map(translate_tag, tag.children))
                    yield '~~'
                case _:
                    if tag.has_attr('class') and 'quote' in tag['class']:
                        yield '\n>>> '
                    yield from chain(*map(translate_tag, tag.children))
            if tag.has_attr('class') and 'partial' in tag['class']:
                yield '...'
        else:
            yield discord.utils.escape_markdown(tag.text)

    # holy cow Python, why is this so complicated. Why can I not just have flatmap
    return ''.join(chain(*map(translate_tag, soup.children)))