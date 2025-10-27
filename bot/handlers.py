from datetime import date, datetime, timezone
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from .keyboards import main_menu_kb, admin_menu_kb, client_menu_kb, user_type_selection_kb, back_to_menu_kb, meals_complexity_kb, nav_kb
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
	# Normalize timezone handling - make both datetimes naive
	if started.tzinfo is not None:
		started = started.replace(tzinfo=None)
	now = datetime.utcnow()
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
	body_type = State()
	color = State()
	engine_number = State()
	car_class = State()


class AddWorkForm(StatesGroup):
	vehicle_id = State()
	part_name = State()
	part_qty = State()
	part_price = State()
	job_name = State()
	job_price = State()


class AddPaymentForm(StatesGroup):
	client_id = State()
	amount = State()


class UserTypeSelection(StatesGroup):
	waiting_for_type = State()


class AdminPasswordForm(StatesGroup):
	password = State()


class ClientRegistrationForm(StatesGroup):
	full_name = State()
	phone = State()
	car_make_model = State()


class AdminReplyForm(StatesGroup):
	client_tg_id = State()
	client_id = State()




@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, storage: Storage) -> None:
	await storage.upsert_user(
		tg_user_id=message.from_user.id,
		chat_id=message.chat.id,
		username=message.from_user.username,
	)
	await state.clear()

	user = await storage.get_user_by_tg(message.from_user.id)
	if user and user.get("role") and user["role"] in ["admin", "client"]:
		# User already has a role, show appropriate menu
		if user["role"] == "admin":
			await message.answer(
				"Привет, Админ! Выберите раздел меню:",
				reply_markup=admin_menu_kb(),
			)
		else:  # client
			# Check if client has completed registration (has client_id)
			if user.get("client_id"):
				await message.answer(
					"Привет! Выберите действие:",
					reply_markup=client_menu_kb(),
				)
			else:
				# Client role but no client_id - needs to complete registration
				await message.answer(
					"Регистрация не завершена. Выберите тип пользователя:",
					reply_markup=user_type_selection_kb(),
				)
	else:
		# New user or user without role, show type selection
		await message.answer(
			"Привет! Выберите тип пользователя:",
			reply_markup=user_type_selection_kb(),
		)


@router.callback_query(F.data == "select_admin")
async def cb_select_admin(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(AdminPasswordForm.password)
	await callback.message.edit_text(
		"Введите пароль администратора:",
		reply_markup=nav_kb("menu_root"),
	)
	await callback.answer()


@router.callback_query(F.data == "select_client")
async def cb_select_client(callback: CallbackQuery, state: FSMContext) -> None:
	await state.set_state(ClientRegistrationForm.full_name)
	await callback.message.edit_text(
		"Регистрация клиента.\n\n1) Введите ваше ФИО:",
		reply_markup=nav_kb("menu_root"),
	)
	await callback.answer()


@router.message(AdminPasswordForm.password)
async def process_admin_password(message: Message, state: FSMContext, storage: Storage) -> None:
	password = (message.text or "").strip()
	if password == "481004":
		await storage.set_user_role(message.from_user.id, "admin")
		await state.clear()
		await message.answer("Пароль верный! Добро пожаловать, Админ.", reply_markup=admin_menu_kb())
	else:
		await message.answer("Неверный пароль. Попробуйте ещё раз:", reply_markup=nav_kb("menu_root"))


@router.message(ClientRegistrationForm.full_name)
async def client_reg_full_name(message: Message, state: FSMContext) -> None:
	full_name = (message.text or "").strip()
	if not full_name:
		await message.answer("Пожалуйста, укажите ФИО.")
		return
	await state.update_data(full_name=full_name)
	await state.set_state(ClientRegistrationForm.phone)
	await message.answer("2) Введите ваш номер телефона:", reply_markup=nav_kb("menu_root"))


@router.message(ClientRegistrationForm.phone)
async def client_reg_phone(message: Message, state: FSMContext) -> None:
	phone = (message.text or "").strip()
	if not phone:
		await message.answer("Пожалуйста, укажите номер телефона.")
		return
	await state.update_data(phone=phone)
	await state.set_state(ClientRegistrationForm.car_make_model)
	await message.answer("3) Введите марку и модель вашего автомобиля:", reply_markup=nav_kb("menu_root"))


@router.message(ClientRegistrationForm.car_make_model)
async def client_reg_car(message: Message, state: FSMContext, storage: Storage) -> None:
	car = (message.text or "").strip()
	if not car:
		await message.answer("Пожалуйста, укажите марку и модель автомобиля.")
		return

	data = await state.get_data()
	full_name = data.get("full_name")
	phone = data.get("phone")

	# Create client account
	client_id = await storage.create_bot_client(
		tg_user_id=message.from_user.id,
		full_name=full_name,
		phone=phone,
		car_make_model=car
	)

	# Set user role to client
	await storage.set_user_role(message.from_user.id, "client")

	await state.clear()
	await message.answer(
		f"Регистрация завершена! Ваш ID: {client_id}\n\nТеперь вы можете просто писать сообщения боту - они автоматически отправятся мастеру.",
		reply_markup=client_menu_kb()
	)




# Admin ID for direct message forwarding
ADMIN_ID = 79417807


@router.message(F.text)
async def handle_client_text_messages(message: Message, storage: Storage, bot: Bot) -> None:
	# Check if user is a client
	user = await storage.get_user_by_tg(message.from_user.id)

	if not user or user.get("role") != "client" or not user.get("client_id"):
		return  # Not a client or not registered, let other handlers process

	text = (message.text or "").strip()
	if not text:
		return

	# Don't process commands
	if text.startswith("/"):
		return

	# Get client info
	client_info = await storage.get_client(user["client_id"])
	client_name = client_info["full_name"] if client_info else "Неизвестный клиент"

	# Forward message to admin with reply button
	try:
		from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
		kb = InlineKeyboardMarkup(
			inline_keyboard=[
				[InlineKeyboardButton(text="💬 Ответить клиенту", callback_data=f"reply_to_client:{user['tg_user_id']}:{user['client_id']}")],
			]
		)

		await bot.send_message(
			chat_id=ADMIN_ID,
			text=f"📨 <b>Сообщение от клиента</b>\n\n"
				 f"👤 <b>{client_name}</b>\n"
				 f"🚗 {client_info.get('car_make_model', 'Не указано') if client_info else 'Не указано'}\n\n"
				 f"💬 <i>{text}</i>",
			reply_markup=kb,
			parse_mode="HTML"
		)
	except Exception as e:
		print(f"Error forwarding message to admin: {e}")

	# Client gets a simple confirmation
	await message.answer("✅ Ваше сообщение отправлено мастеру!")


@router.callback_query(F.data.startswith("reply_to_client:"))
async def cb_reply_to_client(callback: CallbackQuery, state: FSMContext) -> None:
	# Format: reply_to_client:{client_tg_id}:{client_id}
	parts = callback.data.split(":", 2)
	if len(parts) != 3:
		await callback.answer("Ошибка в данных")
		return

	client_tg_id = int(parts[1])
	client_id = int(parts[2])

	await state.set_state(AdminReplyForm.client_tg_id)
	await state.update_data(client_tg_id=client_tg_id, client_id=client_id)

	await callback.message.edit_text(
		f"💬 Введите ответ для клиента (ID: {client_id}):",
		reply_markup=None
	)
	await callback.answer()


@router.message(AdminReplyForm.client_tg_id)
async def admin_send_reply_to_client(message: Message, state: FSMContext, storage: Storage, bot: Bot) -> None:
	data = await state.get_data()
	client_tg_id = data.get("client_tg_id")
	client_id = data.get("client_id")
	reply_text = (message.text or "").strip()

	if not reply_text:
		await message.answer("Ответ не может быть пустым.")
		return

	# Format as command and process internally
	command_text = f"/reply {client_tg_id} {reply_text}"

	# Simulate command processing
	await state.clear()

	# Process the reply command
	await process_reply_command(message, command_text, storage, bot)


async def process_reply_command(message: Message, command_text: str, storage: Storage, bot: Bot) -> None:
	"""Process /reply command internally"""
	try:
		parts = command_text.split(" ", 2)
		if len(parts) < 3:
			await message.answer("Неверный формат команды. Используйте: /reply <user_id> <message>")
			return

		command = parts[0]
		client_tg_id = int(parts[1])
		reply_text = parts[2]

		# Verify admin permissions
		user = await storage.get_user_by_tg(message.from_user.id)
		if not user or user.get("role") != "admin":
			await message.answer("У вас нет прав для выполнения этой команды.")
			return

		# Send message to client (appears as regular bot message)
		try:
			await bot.send_message(
				chat_id=client_tg_id,
				text=reply_text
			)
		except Exception as e:
			await message.answer(f"Ошибка отправки сообщения: {str(e)}")
			return

		# Save message in database
		client_user = await storage.get_user_by_tg(client_tg_id)
		if client_user and client_user.get("client_id"):
			await storage.send_message(
				from_user_id=user["user_id"],
				to_user_id=client_tg_id,
				client_id=client_user["client_id"],
				message_text=reply_text
			)

		await message.answer("✅ Ответ отправлен клиенту!")

	except ValueError:
		await message.answer("Неверный формат user_id.")
	except Exception as e:
		await message.answer(f"Ошибка обработки команды: {str(e)}")


# Also add explicit command handler for manual use
@router.message(F.text.startswith("/reply "))
async def cmd_reply(message: Message, storage: Storage, bot: Bot) -> None:
	command_text = message.text
	await process_reply_command(message, command_text, storage, bot)


@router.callback_query(F.data == "menu_client_chat")
async def cb_menu_client_chat(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user or user.get("role") != "admin":
		await callback.answer("Доступ запрещен")
		return

	messages = await storage.get_messages_for_admin()
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

	if not messages:
		await callback.message.edit_text("Нет новых сообщений от клиентов.", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return

	rows = []
	for msg in messages:
		status = "✅" if msg["is_read"] else "🆕"
		rows.append([
			InlineKeyboardButton(
				text=f"{status} #{msg['client_id']} {msg['client_name']} - {msg['client_car']}",
				callback_data=f"view_client_chat:{msg['client_id']}"
			)
		])

	rows.append([InlineKeyboardButton(text="⬅️ Назад к меню", callback_data="menu_root")])
	kb = InlineKeyboardMarkup(inline_keyboard=rows)
	await callback.message.edit_text("Чат с клиентами:", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("view_client_chat:"))
async def cb_view_client_chat(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user or user.get("role") != "admin":
		await callback.answer("Доступ запрещен")
		return

	client_id = int(callback.data.split(":", 1)[1])
	messages = await storage.get_messages_for_client(client_id)

	if not messages:
		await callback.message.edit_text("Нет сообщений от этого клиента.", reply_markup=nav_kb("menu_client_chat"))
		await callback.answer()
		return

	# Mark messages as read
	for msg in messages:
		if not msg.get("is_read", True):
			await storage.mark_message_read(msg["message_id"])

	# Format chat history
	chat_text = f"Чат с клиентом #{client_id}:\n\n"
	for msg in messages:
		timestamp = msg["created_at"][:19].replace("T", " ")
		if msg["from_role"] == "client":
			chat_text += f"Клиент: {msg['message_text']}\n({timestamp})\n\n"
		else:
			chat_text += f"Админ: {msg['message_text']}\n({timestamp})\n\n"

	# Set state for direct messaging
	await state.set_state(AdminReplyForm.reply_text)
	await state.update_data(client_id=client_id)

	chat_text += "\n💬 Напишите ваш ответ клиенту (или нажмите кнопку ниже):"

	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="menu_client_chat")],
			[InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)

	await callback.message.edit_text(chat_text, reply_markup=kb)
	await callback.answer()


class AdminReplyForm(StatesGroup):
	client_id = State()
	reply_text = State()


@router.message(AdminReplyForm.reply_text)
async def admin_send_reply(message: Message, state: FSMContext, storage: Storage, bot: Bot) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user or user.get("role") != "admin":
		await message.answer("Ошибка: доступ запрещен.")
		await state.clear()
		return

	data = await state.get_data()
	client_id = data.get("client_id")
	reply_text = (message.text or "").strip()

	if not reply_text:
		await message.answer("Ответ не может быть пустым.")
		return

	# Get client chat information
	client_info = await storage.get_client_chat_info(client_id)
	if not client_info:
		await message.answer("Ошибка: клиент не найден или не является бот-клиентом.")
		await state.clear()
		return

	# Send message to client via Telegram
	try:
		await bot.send_message(
			chat_id=client_info["chat_id"],
			text=f"📨 Сообщение от мастера:\n\n{reply_text}"
		)
	except Exception as e:
		await message.answer(f"Ошибка отправки сообщения: {str(e)}")
		await state.clear()
		return

	# Save message in database
	await storage.send_message(
		from_user_id=user["user_id"],
		to_user_id=client_info["tg_user_id"],
		client_id=client_id,
		message_text=reply_text
	)

	await state.clear()

	# Show confirmation and return to chat menu
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="💬 Ответить ещё", callback_data=f"view_client_chat:{client_id}")],
			[InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="menu_client_chat")],
			[InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)

	await message.answer("✅ Сообщение отправлено!", reply_markup=kb)




@router.callback_query(F.data.startswith("view_client_chat:"))
async def cb_view_client_chat(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	messages = await storage.get_messages_for_client(client_id)

	if not messages:
		await callback.message.edit_text("Нет сообщений от этого клиента.", reply_markup=nav_kb("menu_client_chat"))
		await callback.answer()
		return

	# Mark messages as read
	for msg in messages:
		if not msg.get("is_read", True):
			await storage.mark_message_read(msg["message_id"])

	# Format chat history
	chat_text = f"Чат с клиентом #{client_id}:\n\n"
	for msg in messages:
		timestamp = msg["created_at"][:19].replace("T", " ")
		if msg["from_role"] == "client":
			chat_text += f"Клиент: {msg['message_text']}\n({timestamp})\n\n"
		else:
			chat_text += f"Админ: {msg['message_text']}\n({timestamp})\n\n"

	# Set state for direct messaging
	await state.set_state(AdminReplyForm.reply_text)
	await state.update_data(client_id=client_id)

	chat_text += "\n💬 Напишите ваш ответ клиенту (или нажмите кнопку ниже):"

	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="menu_client_chat")],
			[InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)

	await callback.message.edit_text(chat_text, reply_markup=kb)
	await callback.answer()


class AdminReplyForm(StatesGroup):
	client_id = State()
	reply_text = State()




@router.message(AdminReplyForm.reply_text)
async def admin_send_reply(message: Message, state: FSMContext, storage: Storage, bot: Bot) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user or user.get("role") != "admin":
		await message.answer("Ошибка: доступ запрещен.")
		await state.clear()
		return

	data = await state.get_data()
	client_id = data.get("client_id")
	reply_text = (message.text or "").strip()

	if not reply_text:
		await message.answer("Ответ не может быть пустым.")
		return

	# Get client chat information
	client_info = await storage.get_client_chat_info(client_id)
	if not client_info:
		await message.answer("Ошибка: клиент не найден или не является бот-клиентом.")
		await state.clear()
		return

	# Send message to client via Telegram
	try:
		await bot.send_message(
			chat_id=client_info["chat_id"],
			text=f"📨 Сообщение от мастера:\n\n{reply_text}"
		)
	except Exception as e:
		await message.answer(f"Ошибка отправки сообщения: {str(e)}")
		await state.clear()
		return

	# Save message in database
	await storage.send_message(
		from_user_id=user["user_id"],
		to_user_id=client_info["tg_user_id"],
		client_id=client_id,
		message_text=reply_text
	)

	# Refresh chat view with new message
	messages = await storage.get_messages_for_client(client_id)

	# Format updated chat history
	chat_text = f"Чат с клиентом #{client_id}:\n\n"
	for msg in messages:
		timestamp = msg["created_at"][:19].replace("T", " ")
		if msg["from_role"] == "client":
			chat_text += f"Клиент: {msg['message_text']}\n({timestamp})\n\n"
		else:
			chat_text += f"Админ: {msg['message_text']}\n({timestamp})\n\n"

	chat_text += "\n💬 Напишите ваш ответ клиенту (или нажмите кнопку ниже):"

	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="menu_client_chat")],
			[InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)

	await message.answer("✅ Сообщение отправлено!", reply_markup=nav_kb("menu_client_chat"))
	await message.answer(chat_text, reply_markup=kb)

	# Keep the state active for continued messaging
	await state.set_state(AdminReplyForm.reply_text)
	await state.update_data(client_id=client_id)


@router.callback_query(F.data == "menu_client_chat")
async def cb_back_to_client_chat_menu(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	# Clear messaging state when going back to chat menu
	await state.clear()
	print("DEBUG: cb_back_to_client_chat_menu called")  # Debug log

	messages = await storage.get_messages_for_admin()
	print(f"DEBUG: cb_back_to_client_chat_menu found {len(messages)} messages")  # Debug log
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

	if not messages:
		print("DEBUG: No messages found, showing empty message")  # Debug log
		await callback.message.edit_text("Нет новых сообщений от клиентов.", reply_markup=nav_kb("menu_root"))
		await callback.answer()
		return

	rows = []
	for msg in messages:
		status = "✅" if msg["is_read"] else "🆕"
		rows.append([
			InlineKeyboardButton(
				text=f"{status} #{msg['client_id']} {msg['client_name']} - {msg['client_car']}",
				callback_data=f"view_client_chat:{msg['client_id']}"
			)
		])
		print(f"DEBUG: Added button for client {msg['client_id']} - {msg['client_name']}")  # Debug log

	rows.append([InlineKeyboardButton(text="⬅️ Назад к меню", callback_data="menu_root")])
	kb = InlineKeyboardMarkup(inline_keyboard=rows)
	await callback.message.edit_text("Чат с клиентами:", reply_markup=kb)
	await callback.answer()




class AdminReplyForm(StatesGroup):
	client_tg_id = State()
	client_id = State()
	reply_text = State()


@router.callback_query(F.data.startswith("reply_client:"))
async def cb_reply_client(callback: CallbackQuery, state: FSMContext) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	await state.set_state(AdminReplyForm.reply_text)
	await state.update_data(client_id=client_id)
	await callback.message.edit_text(
		f"💬 Введите текст ответа для клиента #{client_id}:",
		reply_markup=None
	)
	await callback.answer()


@router.message(AdminReplyForm.reply_text)
async def admin_send_reply(message: Message, state: FSMContext, storage: Storage, bot: Bot) -> None:
	user = await storage.get_user_by_tg(message.from_user.id)
	if not user or user.get("role") != "admin":
		await message.answer("Ошибка: доступ запрещен.")
		await state.clear()
		return

	data = await state.get_data()
	client_id = data.get("client_id")
	reply_text = (message.text or "").strip()

	if not reply_text:
		await message.answer("Ответ не может быть пустым.")
		return

	# Get client chat information
	client_info = await storage.get_client_chat_info(client_id)
	if not client_info:
		await message.answer("Ошибка: клиент не найден или не является бот-клиентом.")
		await state.clear()
		return

	# Send message to client via Telegram
	try:
		await bot.send_message(
			chat_id=client_info["chat_id"],
			text=f"📨 Сообщение от мастера:\n\n{reply_text}"
		)
	except Exception as e:
		await message.answer(f"Ошибка отправки сообщения: {str(e)}")
		await state.clear()
		return

	# Save message in database
	await storage.send_message(
		from_user_id=user["user_id"],
		to_user_id=client_info["tg_user_id"],
		client_id=client_id,
		message_text=reply_text
	)

	await state.clear()

	# Show confirmation and updated chat
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="💬 Ответить ещё", callback_data=f"reply_client:{client_id}")],
			[InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="menu_client_chat")],
			[InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu_root")],
		]
	)

	await message.answer("✅ Сообщение отправлено!", reply_markup=kb)


@router.message(F.text == "/getmeadminstatus")
async def cmd_getmeadminstatus(message: Message, state: FSMContext) -> None:
	await state.set_state(AdminPasswordForm.password)
	await message.answer("Введите пароль администратора:")


@router.message(F.text == "/resetstatus")
async def cmd_resetstatus(message: Message, storage: Storage) -> None:
	await storage.reset_user_registration(message.from_user.id)
	await message.answer(
		"Ваша роль сброшена. Выберите тип пользователя:",
		reply_markup=user_type_selection_kb(),
	)


@router.message(F.text == "/getmeadminstatus")
async def cmd_getmeadminstatus(message: Message, state: FSMContext) -> None:
	await state.set_state(AdminPasswordForm.password)
	await message.answer("Введите пароль администратора:")


@router.message(F.text == "/resetstatus")
async def cmd_resetstatus(message: Message, storage: Storage) -> None:
	await storage.reset_user_registration(message.from_user.id)
	await message.answer(
		"Ваша роль сброшена. Выберите тип пользователя:",
		reply_markup=user_type_selection_kb(),
	)


@router.callback_query(F.data == "menu_root")
async def cb_menu_root(callback: CallbackQuery, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if user and user.get("role") == "admin":
		menu_kb = admin_menu_kb()
		menu_text = "Главное меню (Админ):"
	elif user and user.get("role") == "client" and user.get("client_id"):
		menu_kb = client_menu_kb()
		menu_text = "Главное меню (Клиент):"
	else:
		# User without proper registration
		menu_kb = user_type_selection_kb()
		menu_text = "Выберите тип пользователя:"

	await callback.answer()
	try:
		await callback.message.edit_text(
			menu_text, reply_markup=menu_kb
		)
	except TelegramBadRequest as e:
		if "message is not modified" in str(e):
			return
		raise


@router.callback_query(F.data == "menu_accept_car")
async def cb_menu_accept_car(callback: CallbackQuery, state: FSMContext, storage: Storage) -> None:
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user or user.get("role") != "admin":
		await callback.answer("Доступ запрещен")
		return

	await state.set_state(IntakeCarForm.full_name)
	await callback.message.edit_text(
		"Приём авто в ремонт.\n\n1) Введите ФИО клиента:",
		reply_markup=nav_kb("menu_root"),
	)
	await callback.answer()


@router.callback_query(F.data == "clientdelmenu")
async def cb_client_delete_menu(callback: CallbackQuery, storage: Storage) -> None:
	clients = await storage.list_clients(limit=100)
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	rows = []
	for c in clients:
		rows.append([
			InlineKeyboardButton(
				text=f"#{c['client_id']} {c['full_name']}",
				callback_data=f"clientdel:{c['client_id']}"
			)
		])
	if not rows:
		await callback.message.edit_text("Клиентов для удаления нет.", reply_markup=nav_kb("menu_clients"))
		await callback.answer()
		return
	rows.append([InlineKeyboardButton(text="⬅️ Назад к клиентам", callback_data="menu_clients")])
	kb = InlineKeyboardMarkup(inline_keyboard=rows)
	await callback.message.edit_text("Выберите клиента для удаления:", reply_markup=kb)
	await callback.answer()


@router.callback_query(F.data.startswith("clientdel:"))
async def cb_client_delete(callback: CallbackQuery, storage: Storage) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
	kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"clientdelconfirm:{client_id}")],
			[InlineKeyboardButton(text="❌ Отмена", callback_data="menu_clients")],
		]
	)
	await callback.message.edit_text(
		f"Вы уверены, что хотите удалить клиента #{client_id}? Это действие удалит все связанные данные.",
		reply_markup=kb,
	)
	await callback.answer()


@router.callback_query(F.data.startswith("clientdelconfirm:"))
async def cb_client_delete_confirm(callback: CallbackQuery, storage: Storage) -> None:
	client_id = int(callback.data.split(":", 1)[1])
	await storage.delete_client(client_id)
	await callback.message.edit_text("Клиент удалён.", reply_markup=nav_kb("menu_clients"))
	await callback.answer("Удалено")

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
	await state.set_state(IntakeCarForm.body_type)
	await message.answer("6) Тип кузова:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.body_type)
async def intake_body_type(message: Message, state: FSMContext, storage: Storage) -> None:
	body_type = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_body_type(client_id, body_type)
	await state.update_data(body_type=body_type)
	await state.set_state(IntakeCarForm.color)
	await message.answer("7) Цвет:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.color)
async def intake_color(message: Message, state: FSMContext, storage: Storage) -> None:
	color = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_color(client_id, color)
	await state.update_data(color=color)
	await state.set_state(IntakeCarForm.engine_number)
	await message.answer("8) Номер двигателя:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.engine_number)
async def intake_engine_number(message: Message, state: FSMContext, storage: Storage) -> None:
	eng = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_engine_number(client_id, eng)
	await state.update_data(engine_number=eng)
	await state.set_state(IntakeCarForm.car_class)
	await message.answer("9) Класс:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.car_class)
async def intake_car_class(message: Message, state: FSMContext, storage: Storage) -> None:
	cls = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_car_class(client_id, cls)
	await state.update_data(car_class=cls)
	await state.set_state(IntakeCarForm.vin)
	await message.answer("10) VIN:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.vin)
async def intake_vin(message: Message, state: FSMContext, storage: Storage) -> None:
	vin = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_vin(client_id, vin)
	await state.update_data(vin=vin)
	await state.set_state(IntakeCarForm.plate)
	await message.answer("11) Гос номер авто:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.plate)
async def intake_plate(message: Message, state: FSMContext, storage: Storage) -> None:
	plate = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_plate(client_id, plate)
	await state.update_data(plate=plate)
	await state.set_state(IntakeCarForm.sts)
	await message.answer("12) СТС:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.sts)
async def intake_sts(message: Message, state: FSMContext, storage: Storage) -> None:
	sts = (message.text or "").strip()
	data = await state.get_data()
	client_id = data.get("client_id")
	if client_id:
		await storage.update_client_sts(client_id, sts)
	await state.update_data(sts=sts)
	await state.set_state(IntakeCarForm.pts)
	await message.answer("13) Номер ПТС:", reply_markup=nav_kb("menu_root"))


@router.message(IntakeCarForm.pts)
async def intake_pts(message: Message, state: FSMContext, storage: Storage) -> None:
    pts = (message.text or "").strip()
    data = await state.get_data()
    client_id = data.get("client_id")
    if client_id:
        await storage.update_client_pts(client_id, pts)
    await state.update_data(pts=pts)
    await state.set_state(IntakeCarForm.reason)
    await message.answer("14) Причина обращения:", reply_markup=nav_kb("menu_root"))


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
		f"Тип кузова: {data.get('body_type','')}\n"
		f"Цвет: {data.get('color','')}\n"
		f"Номер двигателя: {data.get('engine_number','')}\n"
		f"Класс: {data.get('car_class','')}\n"
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
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user or user.get("role") != "admin":
		await callback.answer("Доступ запрещен")
		return

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
	await state.set_state(AddWorkForm.part_qty)
	await message.answer("2) Количество (например, 1 или 2.5):", reply_markup=nav_kb("menu_garage"))


@router.message(AddWorkForm.part_qty)
async def addwork_part_qty(message: Message, state: FSMContext) -> None:
	text = (message.text or "").replace(",", ".").strip()
	try:
		qty = float(text)
		if qty <= 0:
			raise ValueError
	except ValueError:
		await message.answer("Введите количество числом, например 1 или 2.5.", reply_markup=nav_kb("menu_garage"))
		return
	await state.update_data(part_qty=qty)
	await state.set_state(AddWorkForm.part_price)
	await message.answer("3) Цена запчасти за единицу:", reply_markup=nav_kb("menu_garage"))


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
	qty = float(data.get("part_qty", 1))
	await storage.add_part(vehicle_id, data.get("part_name", ""), price, qty)
	vc = await storage.get_vehicle_with_client(vehicle_id)
	if vc:
		await storage.adjust_client_balance(vc["client_id"], price * qty)
	await state.set_state(AddWorkForm.job_name)
	await message.answer("4) Название работы:", reply_markup=nav_kb(f"vehicle:{vehicle_id}"))


@router.message(AddWorkForm.job_name)
async def addwork_job_name(message: Message, state: FSMContext) -> None:
	name = (message.text or "").strip()
	if not name:
		await message.answer("Укажите название работы.", reply_markup=nav_kb("menu_garage"))
		return
	await state.update_data(job_name=name)
	await state.set_state(AddWorkForm.job_price)
	await message.answer("5) Стоимость работы:", reply_markup=nav_kb("menu_garage"))


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
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user or user.get("role") != "admin":
		await callback.answer("Доступ запрещен")
		return

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
	rows.append([InlineKeyboardButton(text="🗑️ Удалить клиента", callback_data="clientdelmenu")])
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
			[InlineKeyboardButton(text="Удалить клиента", callback_data=f"clientdelmenu")],
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
	user = await storage.get_user_by_tg(callback.from_user.id)
	if not user or user.get("role") != "admin":
		await callback.answer("Доступ запрещен")
		return

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
		"mileage": client.get("mileage", "") if client else "",
		"body_type": client.get("body_type", "") if client else "",
		"color": client.get("color", "") if client else "",
		"engine_number": client.get("engine_number", "") if client else "",
		"car_class": client.get("car_class", "") if client else "",
		"vin": client.get("vin", "") if client else "",
		"plate": client.get("plate", "") if client else "",
		"sts": client.get("sts", "") if client else "",
		"pts": client.get("pts", "") if client else "",
		"reason": client.get("reason", "") if client else "",
	}
	works_list = [{"name": j["name"], "price": j["price"]} for j in jobs]
	parts_list = [{"article": "-", "name": p["name"], "qty": p.get("qty", 1), "price": p["price"]} for p in parts]
	# Order number
	order_number = await storage.create_order(vehicle_id)
	# Generate PDF
	try:
		orders_dir = os.path.join(os.getcwd(), "orders")
		os.makedirs(orders_dir, exist_ok=True)
		pdf_path = os.path.join(orders_dir, f"order_{order_number}.pdf")

		generate_order_pdf(
			output_path=pdf_path,
			order_number=order_number,
			customer=customer,
			vehicle=vehicle,
			works=works_list,
			parts=parts_list,
			accepted_at_iso=vc.get("created_at", None),
		)

		# Send file
		await callback.message.answer_document(FSInputFile(pdf_path), caption=f"Заказ-наряд № {order_number}")
		await callback.answer("Сформировано")
	except Exception as e:
		print(f"DEBUG: PDF generation error: {e}")
		await callback.message.answer(f"Ошибка при создании PDF: {str(e)}")
		await callback.answer("Ошибка")