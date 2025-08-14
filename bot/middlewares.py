from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from .storage import Storage


class StorageMiddleware(BaseMiddleware):
	def __init__(self, storage: Storage) -> None:
		self.storage = storage

	async def __call__(
		self,
		handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
		event: TelegramObject,
		data: Dict[str, Any],
	) -> Any:
		data["storage"] = self.storage
		return await handler(event, data)