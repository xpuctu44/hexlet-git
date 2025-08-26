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


class IntakeCarForm(StatesGroup):
	full_name = State()
	phone = State()
	car_make_model = State()
	year = State()
	vin = State()
	plate = State()
	sts = State()
	reason = State()
	confirm = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, storage: Storage) -> None:
	user_id = await storage.upsert_user(
		tg_user_id=message.from_user.id,
		chat_id=message.chat.id,
		username=message.from_user.username,
	)
	await state.clear()
	await message.answer(
		"Привет! Выберите раздел меню:",
		reply_markup=main_menu_kb(),
	)


@router.callback_query(F.data == "menu_root")
async def cb_menu_root(callback: CallbackQuery) -> None:
	await callback.answer()
	try:
		await callback.message.edit_text(
			"Главное меню:", reply_markup=main_menu_kb()
		)
	except TelegramBadRequest as e:
		if "message is not modified" in str(e):
			return
		raise


@router.callback_query(F.data == "menu_accept_car")
async def cb_menu_accept_car(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(IntakeCarForm.full_name)
	await callback.message.edit_text(
		"Приём авто в ремонт.\n\n1) Введите ФИО клиента:",
	)
	await callback.answer()


@router.message(IntakeCarForm.full_name)
async def intake_full_name(message: Message, state: FSMContext, storage: Storage) -> None:
	full_name = (message.text or "").strip()
	if not full_name:
		await message.answer("Пожалуйста, укажите ФИО клиента.")
		return
	client_id = await storage.create_client(full_name)
	await state.update_data(client_id=client_id, full_name=full_name)
	await state.set_state(IntakeCarForm.phone)
	await message.answer("2) Контактный номер для связи:")


@router.message(IntakeCarForm.phone)
async def intake_phone(message: Message, state: FSMContext, storage: Storage) -> None:
	phone = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_contact(client_id, phone)
	await state.update_data(phone=phone)
	await state.set_state(IntakeCarForm.car_make_model)
	await message.answer("3) Марка и модель авто:")


@router.message(IntakeCarForm.car_make_model)
async def intake_car_make_model(message: Message, state: FSMContext, storage: Storage) -> None:
	car = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_car(client_id, car)
	await state.update_data(car_make_model=car)
	await state.set_state(IntakeCarForm.year)
	await message.answer("4) Год выпуска:")


@router.message(IntakeCarForm.year)
async def intake_year(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").strip()
	try:
		year = int(text)
		if year < 1950 or year > 2100:
			raise ValueError
	except ValueError:
		await message.answer("Введите год числом, например 2015.")
		return
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_year(client_id, year)
	await state.update_data(year=year)
	await state.set_state(IntakeCarForm.vin)
	await message.answer("5) VIN:")


@router.message(IntakeCarForm.vin)
async def intake_vin(message: Message, state: FSMContext, storage: Storage) -> None:
	vin = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_vin(client_id, vin)
	await state.update_data(vin=vin)
	await state.set_state(IntakeCarForm.plate)
	await message.answer("6) Гос номер авто:")


@router.message(IntakeCarForm.plate)
async def intake_plate(message: Message, state: FSMContext, storage: Storage) -> None:
	plate = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_plate(client_id, plate)
	await state.update_data(plate=plate)
	await state.set_state(IntakeCarForm.sts)
	await message.answer("7) СТС:")


@router.message(IntakeCarForm.sts)
async def intake_sts(message: Message, state: FSMContext, storage: Storage) -> None:
	sts = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_sts(client_id, sts)
	await state.update_data(sts=sts)
	await state.set_state(IntakeCarForm.reason)
	await message.answer("8) Причина обращения:")


@router.message(IntakeCarForm.reason)
async def intake_reason(message: Message, state: FSMContext, storage: Storage) -> None:
	reason = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_reason(client_id, reason)
	await state.update_data(reason=reason)
	# Summary
	data = await state.get_data()
	summary = (
		"Карточка клиента и авто:\n\n"
		f"ФИО: {data.get('full_name','')}\n"
		f"Телефон: {data.get('phone','')}\n"
		f"Авто: {data.get('car_make_model','')}\n"
		f"Год: {data.get('year','')}\n"
		f"VIN: {data.get('vin','')}\n"
		f"Гос номер: {data.get('plate','')}\n"
		f"СТС: {data.get('sts','')}\n"
		f"Причина: {data.get('reason','')}\n\n"
		"Нажмите кнопку ниже, чтобы поставить авто в ГАРАЖ."
	)
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Поставить авто в ГАРАЖ", callback_data="put_in_garage")],
		]
	)
	await state.set_state(IntakeCarForm.confirm)
	await message.answer(summary, reply_markup=kb)


@router.callback_query(F.data == "put_in_garage")
async def cb_put_in_garage(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		vehicle_id = await storage.create_vehicle_from_client(client_id)
		await state.clear()
		await callback.message.edit_text(
			"Авто добавлено в ГАРАЖ.",
		)
	await callback.answer()


@router.callback_query(F.data == "menu_garage")
async def cb_menu_garage(callback: CallbackQuery, storage: Storage) -> None:
	vehicles = await storage.list_garage()
	if not vehicles:
		text = "Гараж пуст."
	else:
		lines = [
			f"#{v['vehicle_id']}: {v['full_name']} — {v['car_make_model']} ({v['plate'] or 'без номера'})"
			for v in vehicles
		]
		text = "Гараж:\n\n" + "\n".join(lines)
	await callback.message.edit_text(text)
	await callback.answer()


@router.callback_query(F.data == "menu_root")
async def _noop_back(callback: CallbackQuery) -> None:
	# Ничего не показываем дополнительно — просто обновим меню
	try:
		await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
	except TelegramBadRequest:
		pass
	await callback.answer()


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


@router.callback_query(F.data == "menu_clients")
async def cb_menu_clients(callback: CallbackQuery, storage: Storage) -> None:
	# Покажем последних клиентов
	clients = await storage.list_clients()
	if not clients:
		text = "Клиентов пока нет. Принимите авто, чтобы создать клиента."
	else:
		lines = [
			f"#{c['client_id']}: {c['full_name']} — {c['phone'] or 'без телефона'} — {c['car_make_model'] or 'без авто'}"
			for c in clients
		]
		text = "Клиенты:\n\n" + "\n".join(lines)
	await callback.message.edit_text(text)
	await callback.answer()