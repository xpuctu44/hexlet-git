import aiosqlite
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple


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
			try:
				await db.execute("ALTER TABLE users ADD COLUMN openai_api_key TEXT")
			except Exception:
				pass
			try:
				await db.execute("ALTER TABLE daily_activity ADD COLUMN sleep_hours REAL")
			except Exception:
				pass
			try:
				await db.execute("ALTER TABLE daily_activity ADD COLUMN sleep_pending INTEGER DEFAULT 0")
			except Exception:
				pass
			# Clients table
			await db.execute(
				"""
				CREATE TABLE IF NOT EXISTS clients (
					client_id INTEGER PRIMARY KEY AUTOINCREMENT,
					full_name TEXT NOT NULL,
					phone TEXT,
					car_make_model TEXT,
					year INTEGER,
					vin TEXT,
					plate TEXT,
					sts TEXT,
					reason TEXT,
					balance REAL DEFAULT 0,
					created_at TEXT NOT NULL,
					updated_at TEXT NOT NULL
				);
				"""
			)
			# Ensure balance column exists (for migrations)
			try:
				await db.execute("ALTER TABLE clients ADD COLUMN balance REAL DEFAULT 0")
			except Exception:
				pass
			# Vehicles table for garage
			await db.execute(
				"""
				CREATE TABLE IF NOT EXISTS vehicles (
					vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
					client_id INTEGER NOT NULL,
					status TEXT NOT NULL,
					created_at TEXT NOT NULL,
					updated_at TEXT NOT NULL,
					FOREIGN KEY(client_id) REFERENCES clients(client_id)
				);
				"""
			)
			# Parts and jobs
			await db.execute(
				"""
				CREATE TABLE IF NOT EXISTS parts (
					part_id INTEGER PRIMARY KEY AUTOINCREMENT,
					vehicle_id INTEGER NOT NULL,
					name TEXT NOT NULL,
					price REAL NOT NULL,
					created_at TEXT NOT NULL,
					FOREIGN KEY(vehicle_id) REFERENCES vehicles(vehicle_id)
				);
				"""
			)
			await db.execute(
				"""
				CREATE TABLE IF NOT EXISTS jobs (
					job_id INTEGER PRIMARY KEY AUTOINCREMENT,
					vehicle_id INTEGER NOT NULL,
					name TEXT NOT NULL,
					price REAL NOT NULL,
					created_at TEXT NOT NULL,
					FOREIGN KEY(vehicle_id) REFERENCES vehicles(vehicle_id)
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
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT sleep_pending FROM daily_activity WHERE user_id=? AND date=?",
				(user_id, date_str),
			)
			row = await cursor.fetchone()
			return bool(row and row[0] == 1)

	async def get_today_sleep_hours(self, user_id: int, date_str: str) -> Optional[float]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"SELECT sleep_hours FROM daily_activity WHERE user_id=? AND date=?",
				(user_id, date_str),
			)
			row = await cursor.fetchone()
			return None if not row else row[0]

	# ===== Clients and Garage =====
	async def create_client(self, full_name: str) -> int:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				INSERT INTO clients(full_name, created_at, updated_at)
				VALUES(?,?,?)
				""",
				(full_name, now, now),
			)
			await db.commit()
			return cursor.lastrowid

	async def update_client_contact(self, client_id: int, phone: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET phone=?, updated_at=? WHERE client_id=?",
				(phone, now, client_id),
			)
			await db.commit()

	async def update_client_car(self, client_id: int, car_make_model: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET car_make_model=?, updated_at=? WHERE client_id=?",
				(car_make_model, now, client_id),
			)
			await db.commit()

	async def update_client_year(self, client_id: int, year: int) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET year=?, updated_at=? WHERE client_id=?",
				(year, now, client_id),
			)
			await db.commit()

	async def update_client_vin(self, client_id: int, vin: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET vin=?, updated_at=? WHERE client_id=?",
				(vin, now, client_id),
			)
			await db.commit()

	async def update_client_plate(self, client_id: int, plate: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET plate=?, updated_at=? WHERE client_id=?",
				(plate, now, client_id),
			)
			await db.commit()

	async def update_client_sts(self, client_id: int, sts: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET sts=?, updated_at=? WHERE client_id=?",
				(sts, now, client_id),
			)
			await db.commit()

	async def update_client_reason(self, client_id: int, reason: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET reason=?, updated_at=? WHERE client_id=?",
				(reason, now, client_id),
			)
			await db.commit()

	async def adjust_client_balance(self, client_id: int, delta: float) -> None:
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE clients SET balance = COALESCE(balance,0) + ? WHERE client_id=?",
				(delta, client_id),
			)
			await db.commit()

	async def get_client(self, client_id: int) -> Optional[Dict[str, Any]]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				SELECT client_id, full_name, phone, car_make_model, year, vin, plate, sts, reason, balance
				FROM clients WHERE client_id=?
				""",
				(client_id,),
			)
			row = await cursor.fetchone()
			if not row:
				return None
			return {
				"client_id": row[0],
				"full_name": row[1],
				"phone": row[2],
				"car_make_model": row[3],
				"year": row[4],
				"vin": row[5],
				"plate": row[6],
				"sts": row[7],
				"reason": row[8],
				"balance": row[9],
			}

	async def list_clients(self, limit: int = 20) -> List[Dict[str, Any]]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				SELECT client_id, full_name, phone, car_make_model, plate, balance
				FROM clients ORDER BY client_id DESC LIMIT ?
				""",
				(limit,),
			)
			rows = await cursor.fetchall()
			return [
				{
					"client_id": r[0],
					"full_name": r[1],
					"phone": r[2],
					"car_make_model": r[3],
					"plate": r[4],
					"balance": r[5],
				}
				for r in rows
			]

	async def create_vehicle_from_client(self, client_id: int) -> int:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				INSERT INTO vehicles(client_id, status, created_at, updated_at)
				VALUES(?, 'in_garage', ?, ?)
				""",
				(client_id, now, now),
			)
			await db.commit()
			return cursor.lastrowid

	async def get_vehicle_with_client(self, vehicle_id: int) -> Optional[Dict[str, Any]]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				SELECT v.vehicle_id, v.client_id, v.status,
				       c.full_name, c.balance
				FROM vehicles v JOIN clients c ON c.client_id = v.client_id
				WHERE v.vehicle_id=?
				""",
				(vehicle_id,),
			)
			row = await cursor.fetchone()
			if not row:
				return None
			return {
				"vehicle_id": row[0],
				"client_id": row[1],
				"status": row[2],
				"full_name": row[3],
				"balance": row[4],
			}

	async def list_garage(self) -> List[Dict[str, Any]]:
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				SELECT v.vehicle_id, v.client_id, v.status,
				       c.full_name, c.car_make_model, c.plate, c.vin
				FROM vehicles v
				JOIN clients c ON c.client_id = v.client_id
				WHERE v.status='in_garage'
				ORDER BY v.vehicle_id DESC
				"""
			)
			rows = await cursor.fetchall()
			return [
				{
					"vehicle_id": r[0],
					"client_id": r[1],
					"status": r[2],
					"full_name": r[3],
					"car_make_model": r[4],
					"plate": r[5],
					"vin": r[6],
				}
				for r in rows
			]

	async def set_vehicle_status(self, vehicle_id: int, status: str) -> None:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			await db.execute(
				"UPDATE vehicles SET status=?, updated_at=? WHERE vehicle_id=?",
				(status, now, vehicle_id),
			)
			await db.commit()

	# ===== Parts and Jobs =====
	async def add_part(self, vehicle_id: int, name: str, price: float) -> int:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				INSERT INTO parts(vehicle_id, name, price, created_at)
				VALUES(?,?,?,?)
				""",
				(vehicle_id, name, price, now),
			)
			await db.commit()
			return cursor.lastrowid

	async def add_job(self, vehicle_id: int, name: str, price: float) -> int:
		now = datetime.utcnow().isoformat()
		async with aiosqlite.connect(self.db_path) as db:
			cursor = await db.execute(
				"""
				INSERT INTO jobs(vehicle_id, name, price, created_at)
				VALUES(?,?,?,?)
				""",
				(vehicle_id, name, price, now),
			)
			await db.commit()
			return cursor.lastrowid

	async def list_items_for_vehicle(self, vehicle_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
		async with aiosqlite.connect(self.db_path) as db:
			c1 = await db.execute("SELECT part_id, name, price FROM parts WHERE vehicle_id=? ORDER BY part_id DESC", (vehicle_id,))
			parts = [
				{"part_id": r[0], "name": r[1], "price": r[2]}
				for r in await c1.fetchall()
			]
			c2 = await db.execute("SELECT job_id, name, price FROM jobs WHERE vehicle_id=? ORDER BY job_id DESC", (vehicle_id,))
			jobs = [
				{"job_id": r[0], "name": r[1], "price": r[2]}
				for r in await c2.fetchall()
			]
			return parts, jobs

	async def delete_part(self, part_id: int) -> Optional[Tuple[int, float]]:
		async with aiosqlite.connect(self.db_path) as db:
			cur = await db.execute("SELECT vehicle_id, price FROM parts WHERE part_id=?", (part_id,))
			row = await cur.fetchone()
			if not row:
				return None
			vehicle_id, price = row[0], row[1]
			await db.execute("DELETE FROM parts WHERE part_id=?", (part_id,))
			await db.commit()
			return vehicle_id, float(price)

	async def delete_job(self, job_id: int) -> Optional[Tuple[int, float]]:
		async with aiosqlite.connect(self.db_path) as db:
			cur = await db.execute("SELECT vehicle_id, price FROM jobs WHERE job_id=?", (job_id,))
			row = await cur.fetchone()
			if not row:
				return None
			vehicle_id, price = row[0], row[1]
			await db.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
			await db.commit()
			return vehicle_id, float(price)