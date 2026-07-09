from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
import asyncio
import os


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений")


bot = Bot(TOKEN)
dp = Dispatcher()


# Склад клану
clan = {
    "👑 Лідер": [],
    "🛡 Радник": [],
    "⚔️ Солдати": [],
    "🎣 Головний Рибалка": [],
    "🌾 Головний Фермер": [],
    "🪓 Головний Лісоруб": [],
    "🔨 Головний Коваль": []
}


# Тимчасова пам'ять додавання
adding_users = {}


# Головне меню
menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🪖 Особовий склад"),
            KeyboardButton(text="➕ Додати бійця")
        ],
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="🎯 Цілі")
        ],
        [
            KeyboardButton(text="⚙️ Налаштування")
        ]
    ],
    resize_keyboard=True
)


# Меню ролей
role_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👑 Лідер"),
            KeyboardButton(text="🛡 Радник")
        ],
        [
            KeyboardButton(text="⚔️ Солдати")
        ],
        [
            KeyboardButton(text="🎣 Головний Рибалка"),
            KeyboardButton(text="🌾 Головний Фермер")
        ],
        [
            KeyboardButton(text="🪓 Головний Лісоруб"),
            KeyboardButton(text="🔨 Головний Коваль")
        ]
    ],
    resize_keyboard=True
)


# Команди після /
async def set_commands():

    await bot.set_my_commands([
        BotCommand(
            command="start",
            description="Запуск бота"
        ),
        BotCommand(
            command="help",
            description="Допомога"
        )
    ])


# Старт
@dp.message(Command("start"))
async def start(message: Message):

    await message.answer(
        "🛡️ Вас вітає ЗСУ 🎯!",
        reply_markup=menu
    )


# Особовий склад
@dp.message(lambda m: m.text == "🪖 Особовий склад")
async def personnel(message: Message):

    text = "🪖 Особовий склад:\n\n"

    for role, people in clan.items():

        text += f"{role}:\n"

        if people:
            for p in people:
                text += f"• {p}\n"
        else:
            text += "— Вільне місце\n"

        text += "\n"

    await message.answer(text)


# Початок додавання
@dp.message(lambda m: m.text == "➕ Додати бійця")
async def add_start(message: Message):

    adding_users[message.from_user.id] = {
        "step": "name"
    }

    await message.answer(
        "Введи ім'я бійця:"
    )


# Отримання імені
@dp.message()
async def get_name(message: Message):

    user = adding_users.get(message.from_user.id)

    if not user:
        return


    if user["step"] == "name":

        user["name"] = message.text
        user["step"] = "role"

        await message.answer(
            "Обери роль:",
            reply_markup=role_menu
        )

        return


    if user["step"] == "role":

        role = message.text

        if role not in clan:
            await message.answer(
                "Такої ролі немає"
            )
            return


        name = user["name"]

        clan[role].append(name)

        del adding_users[message.from_user.id]


        await message.answer(
            f"✅ {name} доданий у:\n{role}",
            reply_markup=menu
        )


# Статистика
@dp.message(lambda m: m.text == "📊 Статистика")
async def stats(message: Message):

    total = sum(len(x) for x in clan.values())

    await message.answer(
        f"📊 Статистика:\n\n"
        f"👥 Учасників: {total}"
    )


# Цілі
@dp.message(lambda m: m.text == "🎯 Цілі")
async def goals(message: Message):

    await message.answer(
        "🎯 Цілі клану:\n\n"
        "▫️ Розвиток\n"
        "▫️ Виконання завдань\n"
        "▫️ Підняття рейтингу"
    )


# Налаштування
@dp.message(lambda m: m.text == "⚙️ Налаштування")
async def settings(message: Message):

    await message.answer(
        "⚙️ Налаштування клану"
    )


# Допомога
@dp.message(Command("help"))
async def help_cmd(message: Message):

    await message.answer(
        "/start - запуск"
    )


async def main():

    print("BOT STARTING")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await set_commands()

    print("POLLING STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
