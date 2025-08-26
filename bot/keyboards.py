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
			[
				InlineKeyboardButton(text="Создать заказ-наряд", callback_data="menu_create_order"),
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