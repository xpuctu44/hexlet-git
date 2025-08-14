import asyncio
from datetime import datetime, timedelta
from aiogram import Bot

from .storage import Storage


async def _seconds_until(hour: int) -> float:
	now = datetime.now()
	today_target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
	if now >= today_target:
		# tomorrow
		today_target = today_target + timedelta(days=1)
	return (today_target - now).total_seconds()


async def start_evening_calories_prompt_loop(bot: Bot, storage: Storage, notify_hour: int) -> None:
	async def loop() -> None:
		while True:
			seconds = await _seconds_until(notify_hour)
			await asyncio.sleep(seconds)
			# time to ask all users
			from datetime import date
			date_str = date.today().strftime("%Y-%m-%d")
			users = await storage.list_users()
			for u in users:
				try:
					await storage.set_daily_calories_pending(u["user_id"], date_str)
					await bot.send_message(
						chat_id=u["chat_id"],
						text=(
							"Сколько калорий вы сожгли сегодня по данным вашего трекера активности?\n"
							"Отправьте целое число, например 540."
						),
					)
				except Exception:
					# Ignore individual failures, continue with others
					continue
	# Run in background
	asyncio.create_task(loop())