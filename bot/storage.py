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
				"SELECT user_id, tg_user_id, chat_id, username, height_cm, weight_kg, desired_weight_kg FROM users WHERE tg_user_id=?",
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