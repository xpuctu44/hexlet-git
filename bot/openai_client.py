import os
from datetime import date
from typing import Optional, Dict, Any

from openai import OpenAI


_client: Optional[OpenAI] = None
_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()


def get_client() -> OpenAI:
	global _client
	if _client is None:
		if not _api_key:
			raise RuntimeError("OPENAI_API_KEY не задан. Укажите его в .env")
		_client = OpenAI(api_key=_api_key)
	return _client


def _profile_text(user: Dict[str, Any]) -> str:
	height = user.get("height_cm")
	weight = user.get("weight_kg")
	desired = user.get("desired_weight_kg")
	parts = []
	if height:
		parts.append(f"Рост: {height} см")
	if weight:
		parts.append(f"Вес: {weight} кг")
	if desired:
		parts.append(f"Целевой вес: {desired} кг")
	return "; ".join(parts) if parts else "нет данных"


def generate_workout_prompt(user: Dict[str, Any]) -> str:
	profile = _profile_text(user)
	current_date = date.today().strftime("%Y-%m-%d")
	return (
		"Ты — сертифицированный тренер по бодибилдингу. Составь ПЛАН ТРЕНИРОВКИ на сегодня "
		"с учетом данных пользователя, без лишних объяснений, на человеческом русском.\n"
		f"Дата: {current_date}. Профиль: {profile}.\n"
		"Требования:"
		"\n- 60–90 минут;"
		"\n- Укажи разминочные подходы, рабочие подходы и повторы;"
		"\n- Укажи ориентировочные веса как % от 1ПМ, если нет данных о весах;"
		"\n- Раздели по блокам (разминка, основная часть, заминка);"
		"\n- Выведи в формате маркированного списка с подзаголовками."
	)


def generate_meals_prompt(user: Dict[str, Any], calories_burned: Optional[int]) -> str:
	profile = _profile_text(user)
	current_date = date.today().strftime("%Y-%m-%d")
	burned_text = (
		f"Сегодня сожжено по активности: ~{calories_burned} ккал."
		if calories_burned is not None else "Нет данных об израсходованных калориях."
	)
	return (
		"Ты — нутрициолог. Составь ПЛАН ПИТАНИЯ на сегодня для бодибилдинга на русском.\n"
		f"Дата: {current_date}. Профиль: {profile}. {burned_text}\n"
		"Требования:"
		"\n- Укажи целевую суточную калорийность, Б/Ж/У;"
		"\n- Разбей на 4–6 приемов пищи с временем;"
		"\n- Дай заменяемые варианты блюд и простой список покупок;"
		"\n- Форматируй компактно с заголовками и списками."
	)


def generate_text(messages):
	client = get_client()
	resp = client.chat.completions.create(
		model=_model,
		messages=messages,
		temperature=0.7,
		max_tokens=900,
	)
	return resp.choices[0].message.content or ""


def make_workout_text(user: Dict[str, Any]) -> str:
	prompt = generate_workout_prompt(user)
	return generate_text([
		{"role": "system", "content": "Ты помогаешь составлять конкретные планы без лишней воды."},
		{"role": "user", "content": prompt},
	])


def make_meals_text(user: Dict[str, Any], calories_burned: Optional[int]) -> str:
	prompt = generate_meals_prompt(user, calories_burned)
	return generate_text([
		{"role": "system", "content": "Ты помогаешь составлять конкретные планы без лишней воды."},
		{"role": "user", "content": prompt},
	])