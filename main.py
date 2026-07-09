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

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("🛡️ Вас вітає ЗСУ 🎯!")


async def main():
    print("BOT STARTING...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("POLLING STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
