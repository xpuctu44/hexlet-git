from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="Подключить ChatGPT", callback_data="menu_connect_openai"),
			],
			[
				InlineKeyboardButton(text="Клиенты", callback_data="menu_clients"),
			],
			[
				InlineKeyboardButton(text="Принять машину в ремонт", callback_data="menu_accept_car"),
			],
			[
				InlineKeyboardButton(text="Гараж", callback_data="menu_garage"),
			],
		]
	)


def meals_complexity_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="Простой", callback_data="menu_meals_simple"),
				InlineKeyboardButton(text="Изысканный", callback_data="menu_meals_gourmet"),
			],
		]
	)


def back_to_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[]
	)