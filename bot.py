import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
import db
from routers import calc as calc_router
from routers import keys as keys_router
from storage import SqliteFsmStorage

logging.basicConfig(level=logging.INFO)


async def main():
    db.init_db()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=SqliteFsmStorage())
    dp.include_router(keys_router.router)
    dp.include_router(calc_router.router)
    await bot.set_my_description(
        description=(
            "Расчёт налога АУСН «доходы» 8% по вашим продажам на Wildberries.\n"
            "Добавьте API-ключ с правами на чтение финансовых отчётов — "
            "и бот сам посчитает налоговую базу за любой период."
        ),
        language_code="ru",
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
