from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений у Railway Variables")


bot = Bot(TOKEN)
dp = Dispatcher()


# Головне меню
menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🪖 Особовий склад"),
            KeyboardButton(text="📊 Статистика")
        ],
        [
            KeyboardButton(text="🎯 Цілі"),
            KeyboardButton(text="⚙️ Налаштування")
        ]
    ],
    resize_keyboard=True
)


# Команда старт
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🛡️ Вас вітає ЗСУ 🎯!",
        reply_markup=menu
    )


# Особовий склад
@dp.message(lambda message: message.text == "🪖 Особовий склад")
async def personnel(message: Message):
    await message.answer(
        "🪖 Особовий склад клану:\n\n"
        "👑 Лідер:\n"
        "— Вільне місце\n\n"
        
        "🛡 Радник:\n"
        "— Вільне місце\n\n"
        
        "⚔️ Солдати:\n"
        "— Поки немає\n\n"
        
        "🎣 Головний Рибалка:\n"
        "— Вільне місце\n\n"
        
        "🌾 Головний Фермер:\n"
        "— Вільне місце\n\n"
        
        "🪓 Головний Лісоруб:\n"
        "— Вільне місце\n\n"
        
        "🔨 Головний Коваль:\n"
        "— Вільне місце"
    )


# Статистика
@dp.message(lambda message: message.text == "📊 Статистика")
async def stats(message: Message):
    await message.answer(
        "📊 Статистика клану:\n\n"
        "👥 Учасників: 0\n"
        "🏆 Рейтинг: 0\n"
        "🔥 Активність: 0"
    )


# Цілі
@dp.message(lambda message: message.text == "🎯 Цілі")
async def goals(message: Message):
    await message.answer(
        "🎯 Цілі клану:\n\n"
        "▫️ Виконати завдання\n"
        "▫️ Розвивати клан\n"
        "▫️ Підвищувати рейтинг"
    )


# Налаштування
@dp.message(lambda message: message.text == "⚙️ Налаштування")
async def settings(message: Message):
    await message.answer(
        "⚙️ Налаштування:\n\n"
        "Доступ поки тільки для адміністратора"
    )


# Запуск
async def main():
    print("BOT STARTING...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("POLLING STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
