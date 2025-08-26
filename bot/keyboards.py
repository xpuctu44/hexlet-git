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


def nav_kb(back_callback: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[[
			InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback),
			InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root"),
		]]
	)