import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from dotenv import load_dotenv


load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not API_TOKEN:
    raise SystemExit(
        "Отсутствует переменная окружения TELEGRAM_BOT_TOKEN. Задайте её в .env или в окружении."
    )

bot = Bot(token=API_TOKEN, parse_mode="HTML")
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я эхо-бот на aiogram 3. Отправь мне сообщение, и я повторю его."
    )


@router.message(F.text)
async def echo_handler(message: Message) -> None:
    await message.answer(message.text)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())