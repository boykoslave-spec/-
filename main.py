import asyncio
import os
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений")


bot = Bot(TOKEN)
dp = Dispatcher()


# =====================
# DATABASE
# =====================

db = sqlite3.connect("clan.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    fullname TEXT,
    role TEXT DEFAULT '⚔️ Солдати'
)
""")

db.commit()



ROLES = [
    "👑 Лідер",
    "🛡 Радник",
    "⚔️ Солдати",
    "🎣 Головний Рибалка",
    "🌾 Головний Фермер",
    "🪓 Головний Лісоруб",
    "🔨 Головний Коваль"
]


# =====================
# FIXED ADMINS
# =====================

ADMINS = {
    "Jordana_SWAT": "👑 Лідер",
    "Wtfmnnnn": "🛡 Радник"
}



# =====================
# MENUS
# =====================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🪖 Особовий склад"),
            KeyboardButton(text="👤 Мій профіль")
        ],
        [
            KeyboardButton(text="⚙️ Налаштування")
        ]
    ],
    resize_keyboard=True
)



admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🎖 Ролі")
        ],
        [
            KeyboardButton(text="📋 Склад")
        ]
    ],
    resize_keyboard=True
)



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
            KeyboardButton(text="🎣 Головний Рибалка")
        ],
        [
            KeyboardButton(text="🌾 Головний Фермер")
        ],
        [
            KeyboardButton(text="🪓 Головний Лісоруб")
        ],
        [
            KeyboardButton(text="🔨 Головний Коваль")
        ]
    ],
    resize_keyboard=True
)



actions = {}
# =====================
# DATABASE FUNCTIONS
# =====================


def register_user(user_id, username, fullname):

    cursor.execute(
        "SELECT id FROM users WHERE id=?",
        (user_id,)
    )

    exists = cursor.fetchone()


    if not exists:

        role = "⚔️ Солдати"

        if username in ADMINS:
            role = ADMINS[username]


        cursor.execute(
            """
            INSERT INTO users
            (id, username, fullname, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                fullname,
                role
            )
        )

        db.commit()



def get_role(user_id):

    cursor.execute(
        "SELECT role FROM users WHERE id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return "⚔️ Солдати"



# =====================
# START
# =====================


async def set_commands():

    await bot.set_my_commands(
        [
            BotCommand(
                command="start",
                description="Запуск"
            ),
            BotCommand(
                command="help",
                description="Допомога"
            )
        ]
    )



@dp.message(Command("start"))
async def start(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


    await message.answer(
        "🛡️ Вас вітає ЗСУ 🇺🇦\n\n"
        "Ви зареєстровані у складі клану",
        reply_markup=main_menu
    )



# =====================
# PROFILE
# =====================


@dp.message(lambda m: m.text == "👤 Мій профіль")
async def profile(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


    await message.answer(
        f"👤 {message.from_user.full_name}\n\n"
        f"ID: {message.from_user.id}\n"
        f"Username: @{message.from_user.username}\n"
        f"Роль: {get_role(message.from_user.id)}"
    )



# =====================
# CLAN LIST
# =====================


@dp.message(lambda m: m.text == "🪖 Особовий склад")
async def clan(message: Message):

    cursor.execute(
        "SELECT fullname, username, role FROM users"
    )

    users = cursor.fetchall()


    text = "🪖 Особовий склад:\n\n"


    for user in users:

        username = ""

        if user[1]:
            username = f" @{user[1]}"


        text += (
            f"{user[2]}\n"
            f"• {user[0]}{username}\n\n"
        )


    await message.answer(text)



# =====================
# SETTINGS
# =====================


@dp.message(lambda m: m.text == "⚙️ Налаштування")
async def settings(message: Message):

    role = get_role(message.from_user.id)


    if role in ["👑 Лідер", "🛡 Радник"]:

        await message.answer(
            "⚙️ Панель керування",
            reply_markup=admin_menu
        )

    else:

        await message.answer(
            "❌ Немає доступу"
        )



# =====================
# ROLE MANAGEMENT
# =====================


@dp.message(lambda m: m.text == "🎖 Ролі")
async def roles(message: Message):

    role = get_role(message.from_user.id)


    if role not in ["👑 Лідер", "🛡 Радник"]:
        return


    cursor.execute(
        "SELECT id, fullname, username FROM users"
    )

    users = cursor.fetchall()


    text = (
        "👥 Введи ID бійця, якому "
        "призначити роль:\n\n"
    )


    for user in users:

        text += f"{user[0]} - {user[1]}\n"


    actions[message.from_user.id] = {
        "step": "user"
    }


    await message.answer(text)



@dp.message()
async def role_handler(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


    action = actions.get(
        message.from_user.id
    )


    if not action:
        return


    if action["step"] == "user":

        try:

            target = int(message.text)


            cursor.execute(
                "SELECT fullname FROM users WHERE id=?",
                (target,)
            )

            result = cursor.fetchone()


            if not result:

                await message.answer(
                    "❌ Боєць не знайдений"
                )

                return


            actions[message.from_user.id] = {
                "step": "role",
                "target": target
            }


            await message.answer(
                f"Обрано: {result[0]}\n"
                "Вибери роль:",
                reply_markup=role_menu
            )


        except:

            await message.answer(
                "Введи ID цифрами"
            )



    elif action["step"] == "role":

        if message.text not in ROLES:
            return


        cursor.execute(
            """
            UPDATE users
            SET role=?
            WHERE id=?
            """,
            (
                message.text,
                action["target"]
            )
        )


        db.commit()


        del actions[
            message.from_user.id
        ]


        await message.answer(
            "✅ Роль змінена",
            reply_markup=admin_menu
        )



# =====================
# HELP
# =====================


@dp.message(Command("help"))
async def help_cmd(message: Message):

    await message.answer(
        "/start - запуск бота"
    )



# =====================
# RUN
# =====================


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
