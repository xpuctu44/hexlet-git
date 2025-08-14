import aiosqlite
from datetime import datetime
from typing import Optional, Dict, Any, List


class Storage:
	def __init__(self, db_path: str) -> None:
		self.db_path = db_path

	async def initialize(self) -> None:
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"""
				CREATE TABLE IF NOT EXISTS users (
					user_id INTEGER PRIMARY KEY AUTOINCREMENT,
					tg_user_id INTEGER NOT NULL,
					chat_id INTEGER NOT NULL,
					username TEXT,
					height_cm INTEGER,
					weight_kg REAL,
					desired_weight_kg REAL,
					created_at TEXT NOT NULL,
					updated_at TEXT NOT NULL
				);
				"""
			)
			await db.execute(
				"""
				CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tg ON users(tg_user_id);
				"""
			)
			await db.execute(
				"""
				CREATE TABLE IF NOT EXISTS daily_activity (
					user_id INTEGER NOT NULL,
					date TEXT NOT NULL,
					calories_burned INTEGER,
					pending INTEGER DEFAULT 0,
					PRIMARY KEY(user_id, date),
					FOREIGN KEY(user_id) REFERENCES users(user_id)
				);
				"""
			)
			# Try to add OpenAI key column if not present
			try:
				await db.execute("ALTER TABLE users ADD COLUMN openai_api_key TEXT")
			except Exception:
				pass
			# Add sleep_hours column if missing (REAL to allow fractional hours)  # добавляем колонку часов сна, если её нет
			try:
				await db.execute("ALTER TABLE daily_activity ADD COLUMN sleep_hours REAL")  # может хранить дробные значения
			except Exception:
				pass  # колонка уже существует — игнорируем
			# Add sleep_pending flag similar to calories pending  # флаг ожидания ввода часов сна на сегодня
			try:
				await db.execute("ALTER TABLE daily_activity ADD COLUMN sleep_pending INTEGER DEFAULT 0")  # 0/1
			except Exception:
				pass  # колонка уже существует — игнорируем
			await db.commit()

	async def upsert_user(self, tg_user_id: int, chat_id: int, username: Optional[str]) -> int:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT user_id FROM users WHERE tg_user_id=?",
				(tg_user_id,),
			)
			row = await cursor.fetchone()
			if row:
				user_id = row[0]
				await db.execute(
					"UPDATE users SET chat_id=?, username=?, updated_at=? WHERE user_id=?",
					(chat_id, username, now, user_id),
				)
				await db.commit()
				return user_id
			else:
				cursor = await db.execute(
					"""
					INSERT INTO users(tg_user_id, chat_id, username, created_at, updated_at)
					VALUES(?,?,?,?,?)
					""",
					(tg_user_id, chat_id, username, now, now),
				)
				await db.commit()
				return cursor.lastrowid

	async def get_user_by_tg(self, tg_user_id: int) -> Optional[Dict[str, Any]]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT user_id, tg_user_id, chat_id, username, height_cm, weight_kg, desired_weight_kg, openai_api_key FROM users WHERE tg_user_id=?",
				(tg_user_id,),
			)
			row = await cursor.fetchone()
			if not row:
				return None
			return {
				"user_id": row[0],
				"tg_user_id": row[1],
				"chat_id": row[2],
				"username": row[3],
				"height_cm": row[4],
				"weight_kg": row[5],
				"desired_weight_kg": row[6],
				"openai_api_key": row[7],
			}

	async def update_profile(self, user_id: int, height_cm: int, weight_kg: float) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE users SET height_cm=?, weight_kg=?, updated_at=? WHERE user_id=?",
				(height_cm, weight_kg, now, user_id),
			)
			await db.commit()

	async def update_goal(self, user_id: int, desired_weight_kg: float) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE users SET desired_weight_kg=?, updated_at=? WHERE user_id=?",
				(desired_weight_kg, now, user_id),
			)
			await db.commit()

	async def update_openai_key(self, user_id: int, api_key: Optional[str]) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE users SET openai_api_key=?, updated_at=? WHERE user_id=?",
				(api_key, now, user_id),
			)
			await db.commit()

	async def get_openai_key(self, user_id: int) -> Optional[str]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT openai_api_key FROM users WHERE user_id=?",
				(user_id,),
			)
			row = await cursor.fetchone()
			return None if not row else row[0]

	async def list_users(self) -> List[Dict[str, Any]]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT user_id, tg_user_id, chat_id FROM users"
			)
			rows = await cursor.fetchall()
			return [
				{"user_id": r[0], "tg_user_id": r[1], "chat_id": r[2]} for r in rows
			]

	async def set_daily_calories_pending(self, user_id: int, date_str: str) -> None:
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"""
				INSERT INTO daily_activity(user_id, date, pending) VALUES(?,?,1)
				ON CONFLICT(user_id, date) DO UPDATE SET pending=1
				""",
				(user_id, date_str),
			)
			await db.commit()

	async def set_daily_calories(self, user_id: int, date_str: str, calories: int) -> None:
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"""
				INSERT INTO daily_activity(user_id, date, calories_burned, pending) VALUES(?,?,?,0)
				ON CONFLICT(user_id, date) DO UPDATE SET calories_burned=excluded.calories_burned, pending=0
				""",
				(user_id, date_str, calories),
			)
			await db.commit()

	async def has_pending_calories(self, user_id: int, date_str: str) -> bool:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT pending FROM daily_activity WHERE user_id=? AND date=?",
				(user_id, date_str),
			)
			row = await cursor.fetchone()
			return bool(row and row[0] == 1)

	async def get_today_calories(self, user_id: int, date_str: str) -> Optional[int]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT calories_burned FROM daily_activity WHERE user_id=? AND date=?",
				(user_id, date_str),
			)
			row = await cursor.fetchone()
			return None if not row else row[0]

	async def set_daily_sleep_pending(self, user_id: int, date_str: str) -> None:
		# Помечаем, что для пользователя ожидается ввод часов сна за текущую дату
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"""
				INSERT INTO daily_activity(user_id, date, sleep_pending) VALUES(?,?,1)
				ON CONFLICT(user_id, date) DO UPDATE SET sleep_pending=1
				""",
				(user_id, date_str),
			)
			await db.commit()

	async def set_daily_sleep_hours(self, user_id: int, date_str: str, hours: float) -> None:
		# Сохраняем часы сна и снимаем флаг ожидания
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"""
				INSERT INTO daily_activity(user_id, date, sleep_hours, sleep_pending) VALUES(?,?,?,0)
				ON CONFLICT(user_id, date) DO UPDATE SET sleep_hours=excluded.sleep_hours, sleep_pending=0
				""",
				(user_id, date_str, hours),
			)
			await db.commit()

	async def has_pending_sleep(self, user_id: int, date_str: str) -> bool:
		# Проверяем, ожидается ли ввод часов сна на эту дату
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT sleep_pending FROM daily_activity WHERE user_id=? AND date=?",
				(user_id, date_str),
			)
			row = await cursor.fetchone()
			return bool(row and row[0] == 1)

	async def get_today_sleep_hours(self, user_id: int, date_str: str) -> Optional[float]:
		# Получаем сохраненные часы сна за дату (если есть)
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT sleep_hours FROM daily_activity WHERE user_id=? AND date=?",
				(user_id, date_str),
			)
			row = await cursor.fetchone()
			return None if not row else row[0]