from asyncio import run

from .TotalClient import TotalClient
# idk how to do this properly so I just put secrets.py in the gitignore
from .secrets import *

async def main():
    async with TotalClient(
        room_id=1, channel_id=771395175595245603,
        email=EMAIL, se_password=PASSWORD, discord_token=TOKEN
    ) as bot:
        await bot.connect()

if __name__ == '__main__':
    run(main())
