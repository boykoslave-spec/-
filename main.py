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
# БАЗА ДАНИХ
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



# ======================
# КНОПКИ
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
            KeyboardButton(text="📋 Керування складом")
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


# тимчасова пам'ять дій
actions = {}
# ======================
# РОБОТА З КОРИСТУВАЧАМИ
# ======================


def register_user(user_id, username, fullname):

    cursor.execute(
        "SELECT id FROM users WHERE id=?",
        (user_id,)
    )

    user = cursor.fetchone()


    if not user:

        cursor.execute(
            """
            INSERT INTO users
            (id, username, fullname)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                username,
                fullname
            )
        )

        db.commit()



def get_user_role(user_id):

    cursor.execute(
        "SELECT role FROM users WHERE id=?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return "⚔️ Солдати"



# ======================
# АВТОРЕЄСТРАЦІЯ
# ======================

@dp.message()
async def auto_register(message: Message):

    register_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )



# ======================
# КОМАНДИ
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
        "Ви додані до складу клану",
        reply_markup=main_menu
    )



# ======================
# ПРОФІЛЬ
# ======================

@dp.message(lambda m: m.text == "👤 Мій профіль")
async def profile(message: Message):

    role = get_user_role(
        message.from_user.id
    )


    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "немає"
    )


    await message.answer(
        f"👤 Ваш профіль:\n\n"
        f"Ім'я: {message.from_user.full_name}\n"
        f"Username: {username}\n"
        f"ID: {message.from_user.id}\n"
        f"Роль: {role}"
    )



# ======================
# ОСОБОВИЙ СКЛАД
# ======================

@dp.message(lambda m: m.text == "🪖 Особовий склад")
async def clan_list(message: Message):

    cursor.execute(
        "SELECT fullname, username, role FROM users"
    )

    users = cursor.fetchall()


    text = "🪖 Особовий склад:\n\n"


    for user in users:

        name = user[0]
        username = user[1]
        role = user[2]


        if username:
            text += (
                f"{role}\n"
                f"• {name} (@{username})\n\n"
            )

        else:

            text += (
                f"{role}\n"
                f"• {name}\n\n"
            )


    await message.answer(text)
  # ======================
# НАЛАШТУВАННЯ
# ======================


@dp.message(lambda m: m.text == "⚙️ Налаштування")
async def settings(message: Message):

    role = get_user_role(
        message.from_user.id
    )


    if role in ["👑 Лідер", "🛡 Радник"]:

        await message.answer(
            "⚙️ Панель керування:",
            reply_markup=admin_menu
        )

    else:

        await message.answer(
            "❌ У вас немає доступу до керування"
        )



# ======================
# РОЛІ
# ======================


@dp.message(lambda m: m.text == "🎖 Ролі")
async def roles_panel(message: Message):

    role = get_user_role(
        message.from_user.id
    )


    if role not in ["👑 Лідер", "🛡 Радник"]:
        return


    cursor.execute(
        "SELECT id, fullname, username FROM users"
    )

    users = cursor.fetchall()


    text = "👥 Вибери бійця по ID:\n\n"


    for user in users:

        text += (
            f"{user[0]} - {user[1]}"
        )

        if user[2]:
            text += f" (@{user[2]})"

        text += "\n"


    text += (
        "\nНапиши ID користувача"
    )


    actions[message.from_user.id] = {
        "step": "choose_user"
    }


    await message.answer(text)



# ======================
# ВИБІР БІЙЦЯ
# ======================


@dp.message()
async def role_process(message: Message):

    user_action = actions.get(
        message.from_user.id
    )


    if not user_action:
        return


    if user_action["step"] == "choose_user":


        try:

            target_id = int(
                message.text
            )


            cursor.execute(
                "SELECT fullname FROM users WHERE id=?",
                (target_id,)
            )

            user = cursor.fetchone()


            if not user:

                await message.answer(
                    "❌ Такого користувача немає"
                )
                return


            actions[message.from_user.id] = {
                "step": "choose_role",
                "target": target_id
            }


            await message.answer(
                f"Обраний боєць:\n"
                f"{user[0]}\n\n"
                "Вибери нову роль:",
                reply_markup=role_menu
            )


        except:

            await message.answer(
                "Введи ID цифрами"
            )



    elif user_action["step"] == "choose_role":


        new_role = message.text


        if new_role not in ROLES:

            return


        target = user_action["target"]


        cursor.execute(
            """
            UPDATE users
            SET role=?
            WHERE id=?
            """,
            (
                new_role,
                target
            )
        )


        db.commit()


        cursor.execute(
            "SELECT fullname FROM users WHERE id=?",
            (target,)
        )

        name = cursor.fetchone()[0]


        del actions[
            message.from_user.id
        ]


        await message.answer(
            f"✅ {name}\n\n"
            f"Нова роль:\n{new_role}",
            reply_markup=admin_menu
        )



# ======================
# КЕРУВАННЯ СКЛАДОМ
# ======================


@dp.message(lambda m: m.text == "📋 Керування складом")
async def manage(message: Message):

    role = get_user_role(
        message.from_user.id
    )


    if role not in ["👑 Лідер", "🛡 Радник"]:
        return


    await message.answer(
        "📋 Керування складом доступне"
    )



# ======================
# HELP
# ======================


@dp.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "Команда:\n"
        "/start - запуск бота"
    )



# ======================
# ЗАПУСК
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
