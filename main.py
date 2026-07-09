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


# Дані клану
clan = {
    "👑 Лідер": [],
    "🛡 Радник": [],
    "⚔️ Солдати": [],
    "🎣 Головний Рибалка": [],
    "🌾 Головний Фермер": [],
    "🪓 Головний Лісоруб": [],
    "🔨 Головний Коваль": []
}


# Кнопки
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


# Старт
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🛡️ Вас вітає ЗСУ 🎯!",
        reply_markup=menu
    )


# Особовий склад
@dp.message(lambda message: message.text == "🪖 Особовий склад")
async def personnel(message: Message):

    text = "🪖 Особовий склад клану:\n\n"

    for role, people in clan.items():
        text += f"{role}:\n"

        if people:
            for person in people:
                text += f"• {person}\n"
        else:
            text += "— Вільне місце\n"

        text += "\n"

    await message.answer(text)


# Додавання людини
@dp.message(Command("add"))
async def add_role(message: Message):

    try:
        data = message.text.split()

        name = data[1]
        role = " ".join(data[2:])

        if role not in clan:
            await message.answer(
                "❌ Такої ролі немає\n\n"
                "Доступні ролі:\n"
                + "\n".join(clan.keys())
            )
            return

        clan[role].append(name)

        await message.answer(
            f"✅ {name} призначений:\n{role}"
        )

    except:
        await message.answer(
            "❌ Формат:\n\n"
            "/add Ім'я Роль\n\n"
            "Приклад:\n"
            "/add Саня ⚔️ Солдати"
        )


# Статистика
@dp.message(lambda message: message.text == "📊 Статистика")
async def stats(message: Message):

    total = sum(len(x) for x in clan.values())

    await message.answer(
        f"📊 Статистика клану:\n\n"
        f"👥 Учасників: {total}"
    )


# Цілі
@dp.message(lambda message: message.text == "🎯 Цілі")
async def goals(message: Message):

    await message.answer(
        "🎯 Цілі клану:\n\n"
        "▫️ Розвиток клану\n"
        "▫️ Виконання завдань\n"
        "▫️ Підвищення рейтингу"
    )


# Налаштування
@dp.message(lambda message: message.text == "⚙️ Налаштування")
async def settings(message: Message):

    await message.answer(
        "⚙️ Налаштування клану\n\n"
        "Доступ адміністратора"
    )


# Запуск
async def main():

    print("BOT STARTING...")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    print("POLLING STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
