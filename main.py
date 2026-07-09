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
# CONFIG
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



player_settings = ReplyKeyboardMarkup(
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



admin_settings = ReplyKeyboardMarkup(
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



cancel_keyboard = ReplyKeyboardMarkup(
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



def register_user(message):

    user_id = message.from_user.id
    username = message.from_user.username
    fullname = message.from_user.full_name


    cursor.execute(
        "SELECT id FROM users WHERE id=?",
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
            (
                id,
                username,
                fullname,
                role,
                last_online
            )
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



def get_role(user_id):

    cursor.execute(
        """
        SELECT role
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    result = cursor.fetchone()


    if result:
        return result[0]


    return "⚔️ Солдати"



def get_clan_name(user_id):

    cursor.execute(
        """
        SELECT clan_name
        FROM users
        WHERE id=?
        """,
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



def online_status(timestamp):

    now = int(time.time())

    diff = now - timestamp


    if diff < 300:
        return "🟢 Онлайн"


    elif diff < 86400:
        return "🟡 Був недавно"


    else:
        return "🔴 Був давно"



# ======================
# START
# ======================


@dp.message(Command("start"))
async def start(message: Message):

    register_user(message)


    if not get_clan_name(
        message.from_user.id
    ):


        actions[
            message.from_user.id
        ] = {
            "step": "register_name"
        }


        await message.answer(
            "🛡️ Вас вітає ЗСУ 🇺🇦\n\n"
            "Введіть ваш нік у клані:",
            reply_markup=cancel_keyboard
        )

        return



    menu = (
        admin_menu
        if is_admin(message.from_user.id)
        else player_menu
    )


    await message.answer(
        "🛡️ Готово. Ви в клані.",
        reply_markup=menu
    )



# ======================
# PROFILE
# ======================


@dp.message(lambda m: m.text == "👤 Мій профіль")
async def profile(message: Message):

    register_user(message)


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
        f"Нік: {user[0]}\n"
        f"Роль: {user[1]}"
    )
  # ======================
# SETTINGS
# ======================


@dp.message(lambda m: m.text == "⚙️ Налаштування")
async def settings(message: Message):

    register_user(message)


    if is_admin(message.from_user.id):

        await message.answer(
            "⚙️ Панель керування",
            reply_markup=admin_settings
        )

    else:

        await message.answer(
            "⚙️ Налаштування",
            reply_markup=player_settings
        )



# ======================
# CANCEL
# ======================


@dp.message(lambda m: m.text == "❌ Відмінити")
async def cancel(message: Message):

    actions.pop(
        message.from_user.id,
        None
    )


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
# CHANGE OWN NICK
# ======================


@dp.message(lambda m: m.text == "✏️ Змінити свій нік")
async def change_my_nick(message: Message):

    actions[
        message.from_user.id
    ] = {
        "step": "change_my_nick"
    }


    await message.answer(
        "Введіть новий нік:",
        reply_markup=cancel_keyboard
    )



# ======================
# CLAN LIST
# ======================


@dp.message(lambda m: m.text == "🪖 Особовий склад")
async def clan_list(message: Message):

    register_user(message)


    if not is_admin(message.from_user.id):
        return


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
# REGISTER NAME HANDLER
# ======================


@dp.message()
async def universal_handler(message: Message):

    register_user(message)


    action = actions.get(
        message.from_user.id
    )


    if not action:
        return



    # перша реєстрація

    if action["step"] == "register_name":


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
            f"✅ Ваш клановий нік: {message.text}",
            reply_markup=menu
        )

        return



    # зміна власного ніку

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
            reply_markup=(
                admin_menu
                if is_admin(message.from_user.id)
                else player_menu
            )
        )

        return
      # ======================
# ROLE MANAGEMENT
# ======================


@dp.message(lambda m: m.text == "🎖 Керування ролями")
async def role_management(message: Message):

    register_user(message)


    if not is_admin(message.from_user.id):

        await message.answer(
            "❌ Немає доступу"
        )

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


    actions[
        message.from_user.id
    ] = {
        "step": "choose_role_user"
    }


    await message.answer(
        "👤 Оберіть бійця:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True
        )
    )



# ======================
# CHANGE FIGHTER NICK
# ======================


@dp.message(lambda m: m.text == "✏️ Змінити нік бійця")
async def change_fighter_nick(message: Message):

    if not is_admin(message.from_user.id):
        return


    actions[
        message.from_user.id
    ] = {
        "step": "change_fighter_nick"
    }


    await message.answer(
        "Оберіть бійця:",
        reply_markup=cancel_keyboard
    )



# ======================
# CONTINUE ACTIONS
# ======================


@dp.message()
async def actions_handler(message: Message):

    register_user(message)


    action = actions.get(
        message.from_user.id
    )


    if not action:
        return



    # вибір бійця

    if action["step"] == "choose_role_user":


        try:

            target_id = int(
                message.text.split("|")[1]
            )

        except:

            return



        actions[
            message.from_user.id
        ] = {
            "step": "choose_role",
            "target": target_id
        }



        keyboard = []


        for role in ROLES:

            keyboard.append(
                [
                    KeyboardButton(
                        text=role
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


        await message.answer(
            "🎖 Оберіть роль:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=keyboard,
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
            "✅ Роль змінена",
            reply_markup=admin_settings
        )


        return



    # зміна ніку іншому бійцю

    if action["step"] == "change_fighter_nick":

        try:

            target_id = int(message.text)

        except:

            await message.answer(
                "❌ Введіть правильний ID"
            )

            return



        actions[
            message.from_user.id
        ] = {
            "step": "new_fighter_nick",
            "target": target_id
        }


        await message.answer(
            "Введіть новий нік:",
            reply_markup=cancel_keyboard
        )


        return



    if action["step"] == "new_fighter_nick":


        cursor.execute(
            """
            UPDATE users
            SET clan_name=?
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
            "✅ Нік бійця змінено",
            reply_markup=admin_settings
        )



# ======================
# COMMANDS
# ======================


@dp.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "/start - запуск бота"
    )



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
