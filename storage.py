import json
from typing import Any, Optional

from aiogram.fsm.storage.base import BaseStorage, StorageKey

import db


class SqliteFsmStorage(BaseStorage):
    async def set_state(self, key: StorageKey, state=None) -> None:
        if state is None:
            state_str = None
        elif isinstance(state, str):
            state_str = state
        else:
            state_str = state.state  # State object → "GroupName:state_name"
        db.fsm_set_state(_skey(key), state_str)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return db.fsm_get_state(_skey(key))

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        db.fsm_set_data(_skey(key), json.dumps(data, ensure_ascii=False))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        raw = db.fsm_get_data(_skey(key))
        return json.loads(raw) if raw else {}

    async def close(self) -> None:
        pass


def _skey(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.destiny}"
