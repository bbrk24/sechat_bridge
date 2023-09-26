from typing import Any, Collection, Coroutine, Dict, Set, overload

# TODO: actually use a database
class MessageDB:
    def __init__(self):
        self.se_to_discord: Dict[int, Set[int]] = dict()
        self.discord_to_se: Dict[int, Set[int]] = dict()

    async def get_se_ids(self, discord_id: int) -> Collection[int]:
        return self.discord_to_se.get(discord_id, [])

    async def get_discord_ids(self, se_id: int) -> Collection[int]:
        return self.se_to_discord.get(se_id, [])
    
    async def correlate_msgs(self, discord_ids: Collection[int], se_ids: Collection[int]):
        if len(discord_ids) == 0 or len(se_ids) == 0:
            return
        for di in discord_ids:
            self.discord_to_se[di] = set(se_ids)
        for si in se_ids:
            self.se_to_discord[si] = set(discord_ids)

    @overload
    def remove_msg(self, *, discord_id: int) -> Coroutine[Any, Any, None]: ...
    @overload
    def remove_msg(self, *, se_id: int) -> Coroutine[Any, Any, None]: ...

    async def remove_msg(self, *, discord_id=None, se_id=None):
        if (discord_id is None) == (se_id is None):
            raise TypeError('Must specify discord_id xor se_id')

        if se_id is None:
            for si in self.discord_to_se[discord_id]:
                if len(self.se_to_discord[si]) > 1:
                    self.se_to_discord[si].remove(discord_id)
                else:
                    del self.se_to_discord[si]
            del self.discord_to_se[discord_id]
        else:
            for di in self.se_to_discord[se_id]:
                if len(self.discord_to_se[di]) > 1:
                    self.discord_to_se[di].remove(se_id)
                else:
                    del self.discord_to_se[di]
            del self.se_to_discord[se_id]
