from datetime import date
from typing import Optional

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest  # для отлова ошибок правки сообщения

from .keyboards import main_menu_kb, back_to_menu_kb, meals_complexity_kb  # добавили клавиатуру выбора сложности
from .storage import Storage
from .openai_client import make_meals_text, make_workout_text


router = Router()


class ProfileForm(StatesGroup):
	height_cm = State()
	weight_kg = State()


class GoalForm(StatesGroup):
	desired_weight_kg = State()


class ConnectOpenAI(StatesGroup):  # состояние для ввода персонального OpenAI ключа
	api_key = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, storage: Storage) -> None:
	user_id = await storage.upsert_user(
		tg_user_id=message.from_user.id,
		chat_id=message.chat.id,
		username=message.from_user.username,
	)
	await state.clear()
	await message.answer(
		"Привет! Я помогу с планом тренировок и питания. Выберите раздел меню:",
		reply_markup=main_menu_kb(),
	)


@router.callback_query(F.data == "menu_root")
async def cb_menu_root(callback: CallbackQuery) -> None:
	await callback.answer()  # отвечаем callback сразу, чтобы избежать таймаута
	try:
		await callback.message.edit_text(
			"Главное меню:", reply_markup=main_menu_kb()
		)
	except TelegramBadRequest as e:
		# Игнорируем ситуацию, когда сообщение не изменилось
		if "message is not modified" in str(e):
			return
		raise


@router.callback_query(F.data == "menu_profile")
async def cb_menu_profile(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(ProfileForm.height_cm)
	await callback.message.edit_text(
		"Введите ваш рост в сантиметрах (например, 180):",
		reply_markup=back_to_menu_kb(),
	)
	await callback.answer()


@router.message(ProfileForm.height_cm)
async def process_height(message: Message, state: FSMContext) -> None:
	text = (message.text or "").strip()
	if not text.isdigit():
		await message.answer("Пожалуйста, введите число в сантиметрах, например 180.")
		return
	await state.update_data(height_cm=int(text))
	await state.set_state(ProfileForm.weight_kg)
	await message.answer("Теперь введите ваш текущий вес в кг (например, 82.5):")


@router.message(ProfileForm.weight_kg)
async def process_weight(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		weight = float(text)
	except ValueError:
		await message.answer("Введите число, например 82.5")
		return
	data = await state.get_data()
	height_cm = int(data["height_cm"]) if "height_cm" in data else None
	user = await storage.get_user_by_tg(message.from_user.id)
	if user is None:
		await message.answer("Пользователь не найден. Наберите /start")
		await state.clear()
		return
	await storage.update_profile(user_id=user["user_id"], height_cm=height_cm, weight_kg=weight)
	await state.clear()
	await message.answer(
		"Профиль сохранен. Возврат в меню.", reply_markup=main_menu_kb()
	)


class CaloriesForm(StatesGroup):
	calories = State()


@router.callback_query(F.data == "menu_goals")
async def cb_menu_goals(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(GoalForm.desired_weight_kg)
	await callback.message.edit_text(
		"Введите желаемый вес в кг:", reply_markup=back_to_menu_kb()
	)
	await callback.answer()


@router.message(GoalForm.desired_weight_kg)
async def process_goal(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		desired = float(text)
	except ValueError:
		await message.answer("Введите число, например 78")
		return
	user = await storage.get_user_by_tg(message.from_user.id)
	if user is None:
		await message.answer("Пользователь не найден. Наберите /start")
		await state.clear()
		return
	await storage.update_goal(user_id=user["user_id"], desired_weight_kg=desired)
	await state.clear()
	await message.answer("Цель сохранена. Возврат в меню.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_connect_openai")  # обработчик кнопки Подключить ChatGPT
async def cb_connect_openai(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	await state.set_state(ConnectOpenAI.api_key)  # переходим к состоянию ввода ключа
	# Отправляем инструкцию с кликабельной ссылкой на страницу выдачи OpenAI API ключей
	await callback.message.edit_text(
		(
			"Подключение к ChatGPT (OpenAI):\n"  # заголовок инструкции
			"1) Откройте страницу API Keys: "
			"<a href='https://platform.openai.com/settings/keys'>platform.openai.com/settings/keys</a>\n"  # ссылка
			"2) Нажмите Create new secret key и скопируйте ключ (начинается с sk-).\n"  # шаг создания ключа
			"3) Отправьте ваш ключ сюда одним сообщением.\n"  # как передать ключ
			"4) Чтобы удалить ключ и использовать общий из .env — отправьте слово УДАЛИТЬ.\n"  # как удалить ключ
			"Важно: храните ключ в секрете и не публикуйте его."  # предупреждение о безопасности
		),
		reply_markup=back_to_menu_kb(),  # кнопка «В меню»
		disable_web_page_preview=True,  # скрываем превью ссылки
	)
	await callback.answer()


@router.message(ConnectOpenAI.api_key)  # прием и сохранение ключа
async def process_openai_key(message: Message, state: FSMContext, storage: Storage) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user:
		await message.answer("Пользователь не найден. Наберите /start")
		await state.clear()
		return
	text = (message.text or "").strip()
	if text.lower() in {"удалить", "delete", "remove"}:  # очистка ключа по слову
		await storage.update_openai_key(user["user_id"], None)
		await state.clear()
		await message.answer("Ключ удалён. Будет использоваться ключ по умолчанию.", reply_markup=main_menu_kb())
		return
	await storage.update_openai_key(user["user_id"], text)  # сохраняем персональный ключ
	await state.clear()
	await message.answer("Ключ сохранён. Можно генерировать планы.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_workout")
async def cb_menu_workout(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user:
		await callback.message.edit_text("Пользователь не найден. Наберите /start")
		await callback.answer()
		return
	await callback.message.edit_text("Готовлю тренировку на сегодня…")
	text = make_workout_text(user, user.get("openai_api_key"))  # используем персональный ключ, если есть
	await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), disable_web_page_preview=True)
	await callback.answer()


@router.callback_query(F.data == "menu_meals")
async def cb_menu_meals(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user:
		await callback.message.edit_text("Пользователь не найден. Наберите /start")
		await callback.answer()
		return
	# Сначала предлагаем выбрать сложность блюд
	await callback.message.edit_text("Выберите сложность рациона на сегодня:", reply_markup=meals_complexity_kb())
	await callback.answer()


@router.callback_query(F.data.in_({"menu_meals_simple", "menu_meals_gourmet"}))  # выбор сложности
async def cb_menu_meals_complexity(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user:
		await callback.message.edit_text("Пользователь не найден. Наберите /start")
		await callback.answer()
		return
	date_str = date.today().strftime("%Y-%m-%d")
	cal = await storage.get_today_calories(user["user_id"], date_str)
	complexity = "simple" if callback.data == "menu_meals_simple" else "gourmet"  # маппинг сложности
	await callback.message.edit_text("Составляю питание на сегодня…")
	text = make_meals_text(user, cal, user.get("openai_api_key"), complexity)  # передаём сложность и ключ
	await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), disable_web_page_preview=True)
	await callback.answer()


@router.message(F.text.regexp(r"^\d{2,5}$"))
async def maybe_calories_input(message: Message, storage: Storage) -> None:
	# Если от пользователя ожидаются калории за сегодня — записываем
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user:
		return
	date_str = date.today().strftime("%Y-%m-%d")
	if not await storage.has_pending_calories(user["user_id"], date_str):
		return
	try:
		calories = int((message.text or "0").strip())
	except ValueError:
		await message.answer("Пожалуйста, пришлите целое число калорий.")
		return
	await storage.set_daily_calories(user["user_id"], date_str, calories)
	await message.answer("Принято! Данные об активности сохранены.")


@router.message(F.text.regexp(r"^\d{1,2}([.,]\d{1,2})?$"))  # парсим часы сна (целые или с десятичной частью)
async def maybe_sleep_input(message: Message, storage: Storage) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user:
		return
	date_str = date.today().strftime("%Y-%m-%d")
	if not await storage.has_pending_sleep(user["user_id"], date_str):  # проверяем ожидание
		return
	text = (message.text or "").strip().replace(",", ".")
	try:
		hours = float(text)
		if hours <= 0 or hours > 24:
			raise ValueError
	except ValueError:
		await message.answer("Пришлите количество часов сна (например, 7 или 7.5).")
		return
	await storage.set_daily_sleep_hours(user["user_id"], date_str, hours)
	await message.answer("Спасибо! Часы сна сохранены.")