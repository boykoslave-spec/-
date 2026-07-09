from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
import os

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений у Railway Variables")

bot = Bot(TOKEN)
dp = Dispatcher()


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
