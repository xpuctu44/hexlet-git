from datetime import date, datetime, timezone
from typing import Optional

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from .keyboards import main_menu_kb, back_to_menu_kb, meals_complexity_kb, nav_kb
from .storage import Storage
from .openai_client import make_meals_text, make_workout_text
from .pdf_generator import generate_order_pdf
import os


router = Router()


def _format_duration_since(created_at_iso: str) -> str:
	try:
		started = datetime.fromisoformat(created_at_iso)
	except Exception:
		return "?"
	# Normalize timezone handling
	if started.tzinfo is None:
		now = datetime.utcnow()
	else:
		now = datetime.now(started.tzinfo)
	delta = now - started
	days = delta.days
	hours = delta.seconds // 3600
	if days > 0:
		return f"{days} дн {hours} ч"
	return f"{hours} ч"


class ProfileForm(StatesGroup):
	height_cm = State()
	weight_kg = State()


class GoalForm(StatesGroup):
	desired_weight_kg = State()


class ConnectOpenAI(StatesGroup):
	api_key = State()


class IntakeCarForm(StatesGroup):
	full_name = State()
	phone = State()
	car_make_model = State()
	year = State()
	mileage = State()
	vin = State()
	plate = State()
	sts = State()
	pts = State()
	reason = State()
	confirm = State()


class AddWorkForm(StatesGroup):
	vehicle_id = State()
	part_name = State()
	part_price = State()
	job_name = State()
	job_price = State()


class AddPaymentForm(StatesGroup):
	client_id = State()
	amount = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, storage: Storage) -> None:
	await storage.upsert_user(
		tg_user_id=message.from_user.id,
		chat_id=message.chat.id,
		username=message.from_user.username,
	)
	await state.clear()
	# Directly show main menu (avoid sending empty text)
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
		reply_markup=nav_kb("menu_root"),
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
	await message.answer("2) Контактный номер для связи:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.phone)
async def intake_phone(message: Message, state: FSMContext, storage: Storage) -> None:
	phone = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_contact(client_id, phone)
	await state.update_data(phone=phone)
	await state.set_state(IntakeCarForm.car_make_model)
	await message.answer("3) Марка и модель авто:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.car_make_model)
async def intake_car_make_model(message: Message, state: FSMContext, storage: Storage) -> None:
	car = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_car(client_id, car)
	await state.update_data(car_make_model=car)
	await state.set_state(IntakeCarForm.year)
	await message.answer("4) Год выпуска:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.year)
async def intake_year(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").strip()
	try:
		year = int(text)
		if year < 1950 or year > 2100:
			raise ValueError
	except ValueError:
		await message.answer("Введите год числом, например 2015.", reply_markup=nav_kb("menu_root"))
		return
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_year(client_id, year)
	await state.update_data(year=year)
	await state.set_state(IntakeCarForm.mileage)
	await message.answer("5) Пробег (км):", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.mileage)
async def intake_mileage(message: Message, state: FSMContext, storage: Storage) -> None:
    text = (message.text or "").replace(" ", "").strip()
    try:
        mileage = int(text)
        if mileage < 0 or mileage > 3000000:
            raise ValueError
    except ValueError:
        await message.answer("Введите пробег целым числом, например 152000.", reply_markup=nav_kb("menu_root"))
        return
    data = await state.get_data()
    client_id = data.get("client_id")
    if client_id:
        await storage.update_client_mileage(client_id, mileage)
    await state.update_data(mileage=mileage)
    await state.set_state(IntakeCarForm.vin)
    await message.answer("6) VIN:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.vin)
async def intake_vin(message: Message, state: FSMContext, storage: Storage) -> None:
	vin = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_vin(client_id, vin)
	await state.update_data(vin=vin)
	await state.set_state(IntakeCarForm.plate)
	await message.answer("7) Гос номер авто:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.plate)
async def intake_plate(message: Message, state: FSMContext, storage: Storage) -> None:
	plate = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_plate(client_id, plate)
	await state.update_data(plate=plate)
	await state.set_state(IntakeCarForm.sts)
	await message.answer("8) СТС:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.sts)
async def intake_sts(message: Message, state: FSMContext, storage: Storage) -> None:
	sts = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_sts(client_id, sts)
	await state.update_data(sts=sts)
	await state.set_state(IntakeCarForm.pts)
	await message.answer("9) Номер ПТС:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.pts)
async def intake_pts(message: Message, state: FSMContext, storage: Storage) -> None:
    pts = (message.text or "").strip()
    data = await state.get_data()
    client_id = data.get("client_id")
    if client_id:
        await storage.update_client_pts(client_id, pts)
    await state.update_data(pts=pts)
    await state.set_state(IntakeCarForm.reason)
    await message.answer("10) Причина обращения:", reply_markup=nav_kb("menu_root"))


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
		f"Пробег: {data.get('mileage','')}\n"
		f"VIN: {data.get('vin','')}\n"
		f"Гос номер: {data.get('plate','')}\n"
		f"СТС: {data.get('sts','')}\n"
		f"ПТС: {data.get('pts','')}\n"
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
		await storage.create_vehicle_from_client(client_id)
		await state.clear()
		await callback.message.edit_text("Авто добавлено в ГАРАЖ.", reply_markup=nav_kb("menu_garage"))
	await callback.answer()


@router.callback_query(F.data == "menu_garage")
async def cb_menu_garage(callback: CallbackQuery, storage: Storage) -> None:
	vehicles = await storage.list_garage()
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	if not vehicles:
		await callback.message.edit_text("Гараж пуст.", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return
	buttons = []
	for v in vehicles:
		duration = _format_duration_since(v.get("created_at", ""))
		buttons.append([
			InlineKeyboardButton(
				text=f"#{v['vehicle_id']} — {v['full_name']} — {v['car_make_model']} ({v['plate'] or 'без номера'}) · {duration}",
				callback_data=f"vehicle:{v['vehicle_id']}"
			)
		])
	buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")])
	kb = InlineKeyboardMarkup(inline_keyboard=buttons)
	await callback.message.edit_text("Гараж: выберите авто", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("vehicle:"))
async def cb_vehicle_menu(callback: CallbackQuery, storage: Storage) -> None:
	vehicle_id = int(callback.data.split(":", 1)[1])
	vc = await storage.get_vehicle_with_client(vehicle_id)
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	if not vc:
		await callback.answer()
		return
	duration = _format_duration_since(vc.get("created_at", ""))
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Добавить запчасть + работу", callback_data=f"addwork:{vehicle_id}")],
			[InlineKeyboardButton(text="Удалить запчасть/работу", callback_data=f"delmenu:{vehicle_id}")],
			[InlineKeyboardButton(text="⬅️ Назад к гаражу", callback_data="menu_garage"), InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)
	await callback.message.edit_text(
		f"Авто #{vc['vehicle_id']} — {vc['full_name']}\nСтоит в гараже: {duration}\nБаланс: {vc['balance']:.2f}",
		reply_markup=kb,
	)
	await callback.answer()


@router.callback_query(F.data.startswith("addwork:"))
async def cb_addwork_start(callback: CallbackQuery, state: FSMContext) -> None:
	vehicle_id = int(callback.data.split(":", 1)[1])
	await state.set_state(AddWorkForm.part_name)
	await state.update_data(vehicle_id=vehicle_id)
	await callback.message.edit_text("1) Название запчасти:", reply_markup=nav_kb(f"vehicle:{vehicle_id}"))
	await callback.answer()


@router.message(AddWorkForm.part_name)
async def addwork_part_name(message: Message, state: FSMContext) -> None:
	name = (message.text or "").strip()
	if not name:
		await message.answer("Укажите название запчасти.", reply_markup=nav_kb("menu_garage"))
		return
	await state.update_data(part_name=name)
	await state.set_state(AddWorkForm.part_price)
	await message.answer("2) Цена запчасти:", reply_markup=nav_kb("menu_garage"))


@router.message(AddWorkForm.part_price)
async def addwork_part_price(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		price = float(text)
		if price < 0:
			raise ValueError
	except ValueError:
		await message.answer("Введите цену числом, например 3500.", reply_markup=nav_kb("menu_garage"))
		return
	data = await state.get_data()
	vehicle_id = int(data["vehicle_id"])
	await storage.add_part(vehicle_id, data.get("part_name", ""), price)
	vc = await storage.get_vehicle_with_client(vehicle_id)
	if vc:
		await storage.adjust_client_balance(vc["client_id"], price)
	await state.set_state(AddWorkForm.job_name)
	await message.answer("3) Название работы:", reply_markup=nav_kb(f"vehicle:{vehicle_id}"))


@router.message(AddWorkForm.job_name)
async def addwork_job_name(message: Message, state: FSMContext) -> None:
	name = (message.text or "").strip()
	if not name:
		await message.answer("Укажите название работы.", reply_markup=nav_kb("menu_garage"))
		return
	await state.update_data(job_name=name)
	await state.set_state(AddWorkForm.job_price)
	await message.answer("4) Стоимость работы:", reply_markup=nav_kb("menu_garage"))


@router.message(AddWorkForm.job_price)
async def addwork_job_price(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		price = float(text)
		if price < 0:
			raise ValueError
	except ValueError:
		await message.answer("Введите стоимость числом, например 2500.", reply_markup=nav_kb("menu_garage"))
		return
	data = await state.get_data()
	vehicle_id = int(data["vehicle_id"])
	await storage.add_job(vehicle_id, data.get("job_name", ""), price)
	vc = await storage.get_vehicle_with_client(vehicle_id)
	if vc:
		await storage.adjust_client_balance(vc["client_id"], price)
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Вернуться в гараж", callback_data="menu_garage")],
			[InlineKeyboardButton(text="Добавить ещё одну работу", callback_data=f"addwork:{vehicle_id}")],
			[InlineKeyboardButton(text="Удалить запчасть/работу", callback_data=f"delmenu:{vehicle_id}")],
			[InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)
	await state.clear()
	await message.answer("Добавлено. Что дальше?", reply_markup=kb)


@router.callback_query(F.data.startswith("delmenu:"))
async def cb_delete_menu(callback: CallbackQuery, storage: Storage) -> None:
	vehicle_id = int(callback.data.split(":", 1)[1])
	parts, jobs = await storage.list_items_for_vehicle(vehicle_id)
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	rows = []
	for p in parts:
		rows.append([InlineKeyboardButton(text=f"[Запчасть] {p['name']} — {p['price']:.2f}", callback_data=f"delpart:{p['part_id']}")])
	for j in jobs:
		rows.append([InlineKeyboardButton(text=f"[Работа] {j['name']} — {j['price']:.2f}", callback_data=f"deljob:{j['job_id']}")])
	if not rows:
		await callback.message.edit_text("Нет запчастей или работ для удаления.", reply_markup=nav_kb(f"vehicle:{vehicle_id}"))
		await callback.answer()
		return
	rows.append([InlineKeyboardButton(text="⬅️ Назад к авто", callback_data=f"vehicle:{vehicle_id}")])
	rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")])
	kb = InlineKeyboardMarkup(inline_keyboard=rows)
	await callback.message.edit_text("Удалить элемент:", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("delpart:"))
async def cb_delete_part(callback: CallbackQuery, storage: Storage) -> None:
	part_id = int(callback.data.split(":", 1)[1])
	info = await storage.delete_part(part_id)
	if info is None:
		await callback.answer("Элемент не найден")
		return
	vehicle_id, price = info
	vc = await storage.get_vehicle_with_client(vehicle_id)
	if vc:
		await storage.adjust_client_balance(vc["client_id"], -price)
	await callback.answer("Запчасть удалена")
	await cb_delete_menu(callback, storage)


@router.callback_query(F.data.startswith("deljob:"))
async def cb_delete_job(callback: CallbackQuery, storage: Storage) -> None:
	job_id = int(callback.data.split(":", 1)[1])
	info = await storage.delete_job(job_id)
	if info is None:
		await callback.answer("Элемент не найден")
		return
	vehicle_id, price = info
	vc = await storage.get_vehicle_with_client(vehicle_id)
	if vc:
		await storage.adjust_client_balance(vc["client_id"], -price)
	await callback.answer("Работа удалена")
	await cb_delete_menu(callback, storage)


@router.callback_query(F.data == "menu_profile")
async def cb_menu_profile(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(ProfileForm.height_cm)
	await callback.message.edit_text("Введите ваш рост в сантиметрах (например, 180):", reply_markup=nav_kb("menu_root"))
	await callback.answer()


@router.message(ProfileForm.height_cm)
async def process_height(message: Message, state: FSMContext) -> None:
	text = (message.text or "").strip()
	if not text.isdigit():
		await message.answer("Пожалуйста, введите число в сантиметрах, например 180.", reply_markup=nav_kb("menu_root"))
		return
	await state.update_data(height_cm=int(text))
	await state.set_state(ProfileForm.weight_kg)
	await message.answer("Теперь введите ваш текущий вес в кг (например, 82.5):", reply_markup=nav_kb("menu_root"))


@router.message(ProfileForm.weight_kg)
async def process_weight(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		weight = float(text)
	except ValueError:
		await message.answer("Введите число, например 82.5", reply_markup=nav_kb("menu_root"))
		return
	data = await state.get_data()
	height_cm = int(data["height_cm"]) if "height_cm" in data else None
	user = await storage.get_user_by_tg(message.from_user.id)
	if user is None:
		await message.answer("Пользователь не найден. Наберите /start", reply_markup=nav_kb("menu_root"))
		await state.clear()
		return
	await storage.update_profile(user_id=user["user_id"], height_cm=height_cm, weight_kg=weight)
	await state.clear()
	await message.answer("Профиль сохранен. Возврат в меню.", reply_markup=main_menu_kb())


class CaloriesForm(StatesGroup):
	calories = State()


@router.callback_query(F.data == "menu_goals")
async def cb_menu_goals(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(GoalForm.desired_weight_kg)
	await callback.message.edit_text("Введите желаемый вес в кг:", reply_markup=nav_kb("menu_root"))
	await callback.answer()


@router.message(GoalForm.desired_weight_kg)
async def process_goal(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		desired = float(text)
	except ValueError:
		await message.answer("Введите число, например 78", reply_markup=nav_kb("menu_root"))
		return
	user = await storage.get_user_by_tg(message.from_user.id)
	if user is None:
		await message.answer("Пользователь не найден. Наберите /start", reply_markup=nav_kb("menu_root"))
		await state.clear()
		return
	await storage.update_goal(user_id=user["user_id"], desired_weight_kg=desired)
	await state.clear()
	await message.answer("Цель сохранена. Возврат в меню.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_connect_openai")
async def cb_connect_openai(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	await state.set_state(ConnectOpenAI.api_key)
	await callback.message.edit_text(
		(
			"Подключение к ChatGPT (OpenAI):\n"
			"1) Откройте страницу API Keys: "
			"<a href='https://platform.openai.com/settings/keys'>platform.openai.com/settings/keys</a>\n"
			"2) Нажмите Create new secret key и скопируйте ключ (начинается с sk-).\n"
			"3) Отправьте ваш ключ сюда одним сообщением.\n"
			"4) Чтобы удалить ключ и использовать общий из .env — отправьте слово УДАЛИТЬ.\n"
			"Важно: храните ключ в секрете и не публикуйте его."
		),
		disable_web_page_preview=True,
		reply_markup=nav_kb("menu_root"),
	)
	await callback.answer()


@router.message(ConnectOpenAI.api_key)
async def process_openai_key(message: Message, state: FSMContext, storage: Storage) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user:
		await message.answer("Пользователь не найден. Наберите /start", reply_markup=nav_kb("menu_root"))
		await state.clear()
		return
	text = (message.text or "").strip()
	if text.lower() in {"удалить", "delete", "remove"}:
		await storage.update_openai_key(user["user_id"], None)
		await state.clear()
		await message.answer("Ключ удалён. Будет использоваться ключ по умолчанию.", reply_markup=main_menu_kb())
		return
	await storage.update_openai_key(user["user_id"], text)
	await state.clear()
	await message.answer("Ключ сохранён. Можно генерировать планы.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_meals")
async def cb_menu_meals(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user:
		await callback.message.edit_text("Пользователь не найден. Наберите /start", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return
	await callback.message.edit_text("Выберите сложность рациона на сегодня:", reply_markup=meals_complexity_kb())
	await callback.answer()


@router.callback_query(F.data.in_({"menu_meals_simple", "menu_meals_gourmet"}))
async def cb_menu_meals_complexity(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user:
		await callback.message.edit_text("Пользователь не найден. Наберите /start", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return
	date_str = date.today().strftime("%Y-%m-%d")
	cal = await storage.get_today_calories(user["user_id"], date_str)
	complexity = "simple" if callback.data == "menu_meals_simple" else "gourmet"
	await callback.message.edit_text("Составляю питание на сегодня…")
	text = make_meals_text(user, cal, user.get("openai_api_key"), complexity)
	await callback.message.edit_text(text, reply_markup=main_menu_kb(), disable_web_page_preview=True)
	await callback.answer()


@router.message(F.text.regexp(r"^\d{2,5}$"))
async def maybe_calories_input(message: Message, storage: Storage) -> None:
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


@router.message(F.text.regexp(r"^\d{1,2}([.,]\d{1,2})?$"))
async def maybe_sleep_input(message: Message, storage: Storage) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user:
		return
	date_str = date.today().strftime("%Y-%m-%d")
	if not await storage.has_pending_sleep(user["user_id"], date_str):
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
	clients = await storage.list_clients()
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	if not clients:
		await callback.message.edit_text("Клиентов пока нет. Принимите авто, чтобы создать клиента.", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return
	rows = []
	for c in clients:
		rows.append([
			InlineKeyboardButton(
				text=f"#{c['client_id']} {c['full_name']} — долг: {c['balance'] or 0:.2f}",
				callback_data=f"client:{c['client_id']}"
			)
		])
	rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")])
	kb = InlineKeyboardMarkup(inline_keyboard=rows)
	await callback.message.edit_text("Клиенты:", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("client:"))
async def cb_client_detail(callback: CallbackQuery, storage: Storage) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	client = await storage.get_client(client_id)
	if not client:
		await callback.answer("Клиент не найден")
		return
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	text = (
		f"Клиент #{client['client_id']}: {client['full_name']}\n"
		f"Телефон: {client.get('phone') or ''}\n"
		f"Долг: {client.get('balance') or 0:.2f}"
	)
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="Добавить оплату", callback_data=f"payadd:{client_id}")],
			[InlineKeyboardButton(text="Удалить оплату", callback_data=f"paydel:{client_id}")],
			[InlineKeyboardButton(text="История платежей", callback_data=f"payhist:{client_id}")],
			[InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="menu_clients"), InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)
	await callback.message.edit_text(text, reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("payadd:"))
async def cb_pay_add(callback: CallbackQuery, state: FSMContext) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	await state.set_state(AddPaymentForm.amount)
	await state.update_data(client_id=client_id)
	await callback.message.edit_text("Введите сумму оплаты (например, 1500.00)", reply_markup=nav_kb(f"client:{client_id}"))
	await callback.answer()


@router.message(AddPaymentForm.amount)
async def msg_pay_amount(message: Message, state: FSMContext, storage: Storage) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		amount = float(text)
		if amount <= 0:
			raise ValueError
	except ValueError:
		await message.answer("Введите положительное число, например 1500.00", reply_markup=nav_kb("menu_clients"))
		return
	data = await state.get_data()
	client_id = int(data["client_id"]) if "client_id" in data else 0
	if client_id:
		await storage.add_payment(client_id, amount)
		await storage.adjust_client_balance(client_id, -amount)
		await state.clear()
		await message.answer("Оплата добавлена и баланс обновлён.", reply_markup=nav_kb(f"client:{client_id}"))
	else:
		await state.clear()
		await message.answer("Клиент не найден.", reply_markup=nav_kb("menu_clients"))


@router.callback_query(F.data.startswith("payhist:"))
async def cb_pay_history(callback: CallbackQuery, storage: Storage) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	payments = await storage.list_payments(client_id)
	if not payments:
		await callback.message.edit_text("Платежей пока нет.", reply_markup=nav_kb(f"client:{client_id}"))
		await callback.answer()
		return
	lines = [f"{p['created_at'][:19].replace('T',' ')} — {p['amount']:.2f} ₽" for p in payments]
	text = "История платежей:\n\n" + "\n".join(lines)
	await callback.message.edit_text(text, reply_markup=nav_kb(f"client:{client_id}"))
	await callback.answer()


@router.callback_query(F.data.startswith("paydel:"))
async def cb_pay_delete_menu(callback: CallbackQuery, storage: Storage) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	payments = await storage.list_payments(client_id)
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	rows = []
	for p in payments:
		rows.append([
			InlineKeyboardButton(
				text=f"{p['created_at'][:19].replace('T',' ')} — {p['amount']:.2f} ₽",
				callback_data=f"paydelid:{p['payment_id']}:{client_id}"
			)
		])
	if not rows:
		await callback.message.edit_text("Платежей для удаления нет.", reply_markup=nav_kb(f"client:{client_id}"))
		await callback.answer()
		return
	rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"client:{client_id}")])
	kb = InlineKeyboardMarkup(inline_keyboard=rows)
	await callback.message.edit_text("Выберите оплату для удаления:", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("paydelid:"))
async def cb_pay_delete(callback: CallbackQuery, storage: Storage) -> None:
	parts = callback.data.split(":", 2)
	payment_id = int(parts[1])
	client_id = int(parts[2])
	info = await storage.delete_payment(payment_id)
	if info is None:
		await callback.answer("Платёж не найден")
		return
	client_id_conf, amount = info
	await storage.adjust_client_balance(client_id_conf, amount)
	await callback.message.edit_text("Платёж удалён и баланс обновлён.", reply_markup=nav_kb(f"client:{client_id}"))
	await callback.answer()


@router.callback_query(F.data == "menu_create_order")
async def cb_menu_create_order(callback: CallbackQuery, storage: Storage) -> None:
	vehicles = await storage.list_garage()
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	if not vehicles:
		await callback.message.edit_text("В гараже нет авто для заказа-наряда.", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return
	buttons = []
	for v in vehicles:
		buttons.append([
			InlineKeyboardButton(
				text=f"#{v['vehicle_id']} — {v['full_name']} — {v['car_make_model']} ({v['plate'] or 'без номера'})",
				callback_data=f"makeorder:{v['vehicle_id']}"
			)
		])
	buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_root"), InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")])
	kb = InlineKeyboardMarkup(inline_keyboard=buttons)
	await callback.message.edit_text("Выберите авто для заказа-наряда:", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("makeorder:"))
async def cb_make_order(callback: CallbackQuery, storage: Storage) -> None:
	vehicle_id = int(callback.data.split(":", 1)[1])
	vc = await storage.get_vehicle_with_client(vehicle_id)
	if not vc:
		await callback.answer("Авто не найдено")
		return
	# Collect works and parts from DB
	parts, jobs = await storage.list_items_for_vehicle(vehicle_id)
	# Prepare data shapes for PDF
	customer = {
		"full_name": vc.get("full_name", ""),
		"phone": "",
	}
	# fetch more client details
	client = await storage.get_client(vc["client_id"])
	if client:
		customer["phone"] = client.get("phone", "")
	vehicle = {
		"car_make_model": client.get("car_make_model", "") if client else "",
		"year": client.get("year", "") if client else "",
		"vin": client.get("vin", "") if client else "",
		"plate": client.get("plate", "") if client else "",
	}
	works_list = [{"name": j["name"], "price": j["price"]} for j in jobs]
	parts_list = [{"article": "-", "name": p["name"], "qty": 1, "price": p["price"]} for p in parts]
	# Order number
	order_number = await storage.create_order(vehicle_id)
	# Generate PDF
	orders_dir = "/workspace/orders"
	os.makedirs(orders_dir, exist_ok=True)
	pdf_path = os.path.join(orders_dir, f"order_{order_number}.pdf")
	generate_order_pdf(
		output_path=pdf_path,
		order_number=order_number,
		customer=customer,
		vehicle=vehicle,
		works=works_list,
		parts=parts_list,
	)
	# Send file
	await callback.message.answer_document(FSInputFile(pdf_path), caption=f"Заказ-наряд № {order_number}")
	await callback.answer("Сформировано")