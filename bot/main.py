import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from bot.handlers import router
from bot.storage import Storage
from bot.middlewares import StorageMiddleware


async def main() -> None:
	load_dotenv()
	token = os.getenv("BOT_TOKEN")
	if not token:
		raise RuntimeError("BOT_TOKEN is not set in environment")

	logging.basicConfig(level=logging.INFO)

	bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
	dispatcher = Dispatcher()
	dispatcher.include_router(router)

	# Init storage and middleware
	storage = Storage(db_path=os.getenv("DATABASE_PATH", "/workspace/bot.db"))
	await storage.initialize()
	dispatcher.message.middleware.register(StorageMiddleware(storage))
	dispatcher.callback_query.middleware.register(StorageMiddleware(storage))

	await bot.delete_webhook(drop_pending_updates=True)
	await dispatcher.start_polling(bot)


if __name__ == "__main__":
	try:
		import uvloop  # type: ignore

		uvloop.install()
	except Exception:
		pass
	asyncio.run(main())