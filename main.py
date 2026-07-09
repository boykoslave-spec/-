import asyncio
import os
import sqlite3
import time

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
    clan_name TEXT,
    role TEXT DEFAULT '⚔️ Солдати',
    last_online INTEGER DEFAULT 0
)
""")


db.commit()



# ======================
# ROLES
# ======================

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
# ACTION MEMORY
# ======================

actions = {}



# ======================
# MENUS
# ======================


player_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 Мій профіль"),
            KeyboardButton(text="⚙️ Налаштування")
        ]
    ],
    resize_keyboard=True
)



admin_menu = ReplyKeyboardMarkup(
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



settings_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="✏️ Змінити свій нік")
        ],
        [
            KeyboardButton(text="❌ Відмінити")
        ]
    ],
    resize_keyboard=True
)



admin_settings_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🎖 Керування ролями")
        ],
        [
            KeyboardButton(text="✏️ Змінити нік бійця")
        ],
        [
            KeyboardButton(text="❌ Відмінити")
        ]
    ],
    resize_keyboard=True
)



cancel_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="❌ Відмінити")
        ]
    ],
    resize_keyboard=True
)
# ======================
# DATABASE FUNCTIONS
# ======================


def register_user(user_id, username, fullname):

    cursor.execute(
        "SELECT id, clan_name FROM users WHERE id=?",
        (user_id,)
    )

    user = cursor.fetchone()


    if not user:

        role = "⚔️ Солдати"

        if username in ADMINS:
            role = ADMINS[username]


        cursor.execute(
            """
            INSERT INTO users
            (id, username, fullname, role, last_online)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                fullname,
                role,
                int(time.time())
            )
        )

        db.commit()


    update_online(user_id)



def update_online(user_id):

    cursor.execute(
        """
        UPDATE users
        SET last_online=?
        WHERE id=?
        """,
        (
            int(time.time()),
            user_id
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



def get_clan_name(user_id):

    cursor.execute(
        "SELECT clan_name FROM users WHERE id=?",
        (user_id,)
    )

    result = cursor.fetchone()


    if result:
        return result[0]


    return None



def is_admin(user_id):

    return get_role(user_id) in [
        "👑 Лідер",
        "🛡 Радник"
    ]



def online_status(last_online):

    now = int(time.time())

    difference = now - last_online


    if difference < 300:

        return "🟢 Онлайн"


    elif difference < 86400:

        return "🟡 Був недавно"


    else:

        return "🔴 Був давно"



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



# ======================
# START
# ======================


@dp.message(Command("start"))
async def start(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


    if not get_clan_name(message.from_user.id):

        actions[message.from_user.id] = {
            "step": "set_name"
        }


        await message.answer(
            "🛡️ Вас вітає ЗСУ 🇺🇦\n\n"
            "Введіть ваш нік у клані:",
            reply_markup=cancel_menu
        )

        return



    if is_admin(message.from_user.id):

        menu = admin_menu

    else:

        menu = player_menu



    await message.answer(
        "🛡️ Вас вітає ЗСУ 🇺🇦",
        reply_markup=menu
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


    cursor.execute(
        """
        SELECT clan_name, role
        FROM users
        WHERE id=?
        """,
        (
            message.from_user.id,
        )
    )


    user = cursor.fetchone()


    await message.answer(
        f"👤 Профіль\n\n"
        f"Нік у клані: {user[0]}\n"
        f"Роль: {user[1]}"
    )



# ======================
# SET CLAN NAME
# ======================


@dp.message()
async def set_name_handler(message: Message):

    action = actions.get(
        message.from_user.id
    )


    if not action:
        return


    if action["step"] == "set_name":

        cursor.execute(
            """
            UPDATE users
            SET clan_name=?
            WHERE id=?
            """,
            (
                message.text,
                message.from_user.id
            )
        )


        db.commit()


        del actions[
            message.from_user.id
        ]


        menu = (
            admin_menu
            if is_admin(message.from_user.id)
            else player_menu
        )


        await message.answer(
            f"✅ Ваш нік у клані:\n"
            f"{message.text}",
            reply_markup=menu
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


    menu = (
        admin_menu
        if is_admin(message.from_user.id)
        else player_menu
    )


    await message.answer(
        "❌ Дію скасовано",
        reply_markup=menu
    )



# ======================
# SETTINGS
# ======================


@dp.message(lambda m: m.text == "⚙️ Налаштування")
async def settings(message: Message):

    if is_admin(message.from_user.id):

        await message.answer(
            "⚙️ Налаштування керування:",
            reply_markup=admin_settings_menu
        )

    else:

        await message.answer(
            "⚙️ Налаштування:",
            reply_markup=settings_menu
        )



# ======================
# CHANGE OWN NICK
# ======================


@dp.message(lambda m: m.text == "✏️ Змінити свій нік")
async def change_my_nick(message: Message):

    actions[message.from_user.id] = {
        "step": "change_my_nick"
    }


    await message.answer(
        "Введіть новий нік у клані:",
        reply_markup=cancel_menu
    )



# ======================
# CLAN LIST
# ======================


@dp.message(lambda m: m.text == "🪖 Особовий склад")
async def clan_list(message: Message):

    cursor.execute(
        """
        SELECT clan_name, role, last_online
        FROM users
        ORDER BY role
        """
    )


    users = cursor.fetchall()


    text = "🪖 Особовий склад:\n\n"


    for user in users:

        name = user[0] or "Без ніку"

        status = online_status(
            user[2]
        )


        text += (
            f"{user[1]}\n"
            f"• {name}\n"
            f"{status}\n\n"
        )


    await message.answer(text)



# ======================
# ADMIN ROLE CONTROL
# ======================


@dp.message(lambda m: m.text == "🎖 Керування ролями")
async def role_control(message: Message):

    if not is_admin(message.from_user.id):
        return


    cursor.execute(
        """
        SELECT id, clan_name
        FROM users
        WHERE clan_name IS NOT NULL
        """
    )


    users = cursor.fetchall()


    keyboard = []


    for user in users:

        keyboard.append(
            [
                KeyboardButton(
                    text=f"{user[1]} | {user[0]}"
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


    actions[message.from_user.id] = {
        "step": "choose_role_user"
    }


    await message.answer(
        "Оберіть бійця:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True
        )
    )



# ======================
# CHANGE FIGHTER NICK
# ======================


@dp.message(lambda m: m.text == "✏️ Змінити нік бійця")
async def change_other_nick(message: Message):

    if not is_admin(message.from_user.id):
        return


    actions[message.from_user.id] = {
        "step": "change_other_nick"
    }


    await message.answer(
        "Введіть ID бійця:",
        reply_markup=cancel_menu
    )



# ======================
# GENERAL ACTION HANDLER
# ======================


@dp.message()
async def actions_handler(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )


    update_online(
        message.from_user.id
    )


    action = actions.get(
        message.from_user.id
    )


    if not action:
        return



    # зміна свого ніку

    if action["step"] == "change_my_nick":


        cursor.execute(
            """
            UPDATE users
            SET clan_name=?
            WHERE id=?
            """,
            (
                message.text,
                message.from_user.id
            )
        )

        db.commit()


        del actions[
            message.from_user.id
        ]


        await message.answer(
            "✅ Нік змінено",
            reply_markup=player_menu
        )

        return



    # вибір бійця для ролі

    if action["step"] == "choose_role_user":


        target_id = int(
            message.text.split("|")[1]
        )


        actions[message.from_user.id] = {
            "step": "choose_role",
            "target": target_id
        }


        await message.answer(
            "Оберіть роль:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(text=r)
                    ]
                    for r in ROLES
                ],
                resize_keyboard=True
            )
        )

        return



    # видача ролі

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


        del actions[
            message.from_user.id
        ]


        await message.answer(
            "✅ Роль змінено",
            reply_markup=admin_menu
        )



# ======================
# HELP
# ======================


@dp.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "/start - запуск бота"
    )



# ======================
# RUN
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
