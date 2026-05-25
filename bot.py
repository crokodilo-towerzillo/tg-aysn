import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from routers import calc as calc_router
from routers import keys as keys_router

logging.basicConfig(level=logging.INFO)


async def main():
    db.init_db()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(keys_router.router)
    dp.include_router(calc_router.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
