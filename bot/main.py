import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from .config import load_config
from .handlers import router as handlers_router
from .middlewares import StorageMiddleware
from .scheduler import start_evening_calories_prompt_loop, start_morning_sleep_prompt_loop
from .storage import Storage


async def main() -> None:
	load_dotenv()
	config = load_config()
	if not config.telegram_token:
		raise SystemExit(
			"Отсутствует TELEGRAM_BOT_TOKEN. Укажите его в .env или переменных окружения."
		)

	logging.basicConfig(level=logging.INFO)

	bot = Bot(token=config.telegram_token, parse_mode="HTML")

	fsm_storage = MemoryStorage()
	dispatcher = Dispatcher(storage=fsm_storage)

	storage = Storage(config.database_path)
	await storage.initialize()

	dispatcher.update.outer_middleware(StorageMiddleware(storage))

	dispatcher.include_router(handlers_router)

	await start_evening_calories_prompt_loop(bot, storage, config.notify_hour)
	await start_morning_sleep_prompt_loop(bot, storage, config.sleep_notify_hour)

	await dispatcher.start_polling(bot)


if __name__ == "__main__":
	asyncio.run(main())