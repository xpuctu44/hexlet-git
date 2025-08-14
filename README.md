# Простой Telegram-бот на aiogram 3

Минимальный каркас бота на `aiogram` v3.

## Установка

1. Убедитесь, что установлен Python 3.9+.
2. Создайте виртуальное окружение и установите зависимости:

```bash
cd /workspace
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Настройка

1. Получите токен у `@BotFather` в Telegram
2. Создайте файл `.env` на основе примера и впишите токен:

```bash
cp .env.example .env
# отредактируйте .env и подставьте ваш токен
```

## Запуск

```bash
source .venv/bin/activate
python -m bot.main
```

Бот запустится в режиме polling. Остановить – `Ctrl+C`.

## Дальше
- Добавить команды и обработчики
- Кнопки/инлайн-кнопки
- Хранение состояния и БД
- Вебхуки и деплой
