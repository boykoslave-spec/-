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


# ======================
# DATABASE
# ======================

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


ADMINS = {
    "Jordana_SWAT": "👑 Лідер",
    "Wtfmnnnn": "🛡 Радник"
}



# ======================
# MENUS
# ======================


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
        ],
        [
            KeyboardButton(text="❌ Відмінити")
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
        ],
        [
            KeyboardButton(text="❌ Відмінити")
        ]
    ],
    resize_keyboard=True
)


actions = {}
# ======================
# FUNCTIONS
# ======================


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



def is_admin(user_id):

    return get_role(user_id) in [
        "👑 Лідер",
        "🛡 Радник"
    ]



# ======================
# COMMANDS
# ======================


async def set_commands():

    await bot.set_my_commands(
        [
            BotCommand(
                command="start",
                description="Запуск бота"
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
        "Ви зареєстровані у клані",
        reply_markup=main_menu
    )



# ======================
# PROFILE
# ======================


@dp.message(lambda m: m.text == "👤 Мій профіль")
async def profile(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "немає"
    )


    await message.answer(
        f"👤 Профіль\n\n"
        f"Ім'я: {message.from_user.full_name}\n"
        f"Username: {username}\n"
        f"ID: {message.from_user.id}\n"
        f"Роль: {get_role(message.from_user.id)}"
    )



# ======================
# CLAN
# ======================


@dp.message(lambda m: m.text == "🪖 Особовий склад")
async def clan_list(message: Message):

    cursor.execute(
        "SELECT fullname, username, role FROM users ORDER BY role"
    )

    users = cursor.fetchall()


    if not users:

        await message.answer(
            "Склад порожній"
        )

        return


    text = "🪖 Особовий склад:\n\n"


    for user in users:

        nick = ""

        if user[1]:
            nick = f" (@{user[1]})"


        text += (
            f"{user[2]}\n"
            f"• {user[0]}{nick}\n\n"
        )


    await message.answer(text)



# ======================
# SETTINGS
# ======================


@dp.message(lambda m: m.text == "⚙️ Налаштування")
async def settings(message: Message):

    if is_admin(message.from_user.id):

        await message.answer(
            "⚙️ Адмін панель",
            reply_markup=admin_menu
        )

    else:

        await message.answer(
            "❌ У вас немає доступу"
        )



# ======================
# CANCEL
# ======================


@dp.message(lambda m: m.text == "❌ Відмінити")
async def cancel(message: Message):

    if message.from_user.id in actions:

        del actions[
            message.from_user.id
        ]


    await message.answer(
        "❌ Дію скасовано",
        reply_markup=main_menu
    )



# ======================
# ROLE PANEL START
# ======================


@dp.message(lambda m: m.text == "🎖 Ролі")
async def role_start(message: Message):

    if not is_admin(message.from_user.id):
        return


    cursor.execute(
        "SELECT id, fullname, username FROM users"
    )

    users = cursor.fetchall()


    keyboard = []


    for user in users:

        username = ""

        if user[2]:
            username = f" @{user[2]}"


        keyboard.append(
            [
                KeyboardButton(
                    text=f"{user[1]}{username}"
                )
            ]
        )


    keyboard.append(
        [
            KeyboardButton(
                text="❌ Відмінити"
            )
        ]
    )


    user_menu = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


    actions[message.from_user.id] = {
        "step": "choose_user"
    }


    await message.answer(
        "👤 Вибери учасника:",
        reply_markup=user_menu
    )
  # ======================
# ROLE SELECT
# ======================


@dp.message()
async def actions_handler(message: Message):

    # автоматична реєстрація
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



    # вибір бійця

    if action["step"] == "choose_user":


        cursor.execute(
            "SELECT id, fullname FROM users"
        )

        users = cursor.fetchall()


        target_id = None


        for user in users:

            if message.text.startswith(user[1]):

                target_id = user[0]
                break



        if not target_id:

            await message.answer(
                "❌ Учасника не знайдено"
            )

            return



        actions[message.from_user.id] = {
            "step": "choose_role",
            "target": target_id
        }


        await message.answer(
            "🎖 Обери нову роль:",
            reply_markup=role_menu
        )


        return



    # вибір ролі

    if action["step"] == "choose_role":


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


        cursor.execute(
            """
            SELECT fullname 
            FROM users
            WHERE id=?
            """,
            (
                action["target"],
            )
        )


        user = cursor.fetchone()


        del actions[
            message.from_user.id
        ]


        await message.answer(
            f"✅ Роль змінено\n\n"
            f"Боєць: {user[0]}\n"
            f"Нова роль: {message.text}",
            reply_markup=admin_menu
        )



# ======================
# ADMIN LIST
# ======================


@dp.message(lambda m: m.text == "📋 Склад")
async def admin_list(message: Message):

    if not is_admin(message.from_user.id):

        return


    cursor.execute(
        """
        SELECT fullname, username, role
        FROM users
        """
    )


    users = cursor.fetchall()


    text = "📋 Повний склад:\n\n"


    for user in users:

        nick = ""

        if user[1]:

            nick = f" @{user[1]}"


        text += (
            f"{user[2]}\n"
            f"{user[0]}{nick}\n\n"
        )


    await message.answer(text)



# ======================
# HELP
# ======================


@dp.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "/start - запуск бота"
    )



# ======================
# START BOT
# ======================


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
