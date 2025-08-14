import os
from dataclasses import dataclass


@dataclass
class Config:
	telegram_token: str
	openai_api_key: str
	openai_model: str = "gpt-4o-mini"
	database_path: str = "/workspace/bot.db"
	notify_hour: int = 21


def load_config() -> Config:
	telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
	openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
	openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
	database_path = os.getenv("DATABASE_PATH", "/workspace/bot.db").strip()
	notify_hour_str = os.getenv("NOTIFY_HOUR", "21").strip()
	try:
		notify_hour = int(notify_hour_str)
		if not (0 <= notify_hour <= 23):
			raise ValueError
	except ValueError:
		notify_hour = 21

	return Config(
		telegram_token=telegram_token,
		openai_api_key=openai_api_key,
		openai_model=openai_model,
		database_path=database_path,
		notify_hour=notify_hour,
	)