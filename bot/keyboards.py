from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text="Профиль пользователя", callback_data="menu_profile"),
			],
			[
				InlineKeyboardButton(text="Цели", callback_data="menu_goals"),
			],
			[
				InlineKeyboardButton(text="Подключить ChatGPT", callback_data="menu_connect_openai"),
			],
			[
				InlineKeyboardButton(text="Тренировка на сегодня", callback_data="menu_workout"),
			],
			[
				InlineKeyboardButton(text="Питание на сегодня", callback_data="menu_meals"),
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
			[
				InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_root"),
			],
		]
	)


def back_to_menu_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_root")]]
	)