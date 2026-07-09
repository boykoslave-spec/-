import asyncio
import os
import sqlite3
import time

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений")


bot = Bot(TOKEN)
dp = Dispatcher()


# =========================
# DATABASE
# =========================

db = sqlite3.connect("clan.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    clan_name TEXT,
    role TEXT,
    role_level INTEGER,
    last_online INTEGER
)
""")

db.commit()



# =========================
# ROLES
# =========================

ROLES = {
    "👑 Лідер": 1,
    "🛡 Радник": 2,
    "🎣 Головний Рибалка": 3,
    "🌾 Головний Фермер": 4,
    "🪓 Головний Лісоруб": 5,
    "🔨 Головний Коваль": 6,
    "⚔️ Солдат": 7
}


START_ADMIN = {
    "Jordana_SWAT": ("👑 Лідер", 1),
    "Wtfmnnnn": ("🛡 Радник", 2)
}



# =========================
# ACTIVE ACTIONS
# =========================

actions = {}



# =========================
# DATABASE FUNCTIONS
# =========================


def register_user(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username


    cursor.execute(
        "SELECT id FROM users WHERE id=?",
        (user_id,)
    )

    user = cursor.fetchone()


    if not user:

        role = "⚔️ Солдат"
        level = 7


        if username in START_ADMIN:

            role, level = START_ADMIN[username]


        cursor.execute(
            """
            INSERT INTO users
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                None,
                role,
                level,
                int(time.time())
            )
        )

        db.commit()


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



def get_user(user_id):

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    return cursor.fetchone()



def is_admin(user_id):

    user = get_user(user_id)

    if not user:
        return False

    return user[4] <= 2



def status_icon(last_online):

    diff = int(time.time()) - last_online

    if diff < 300:
        return "🟢"

    if diff < 86400:
        return "🟡"

    return "🔴"
# =========================
# KEYBOARDS
# =========================


def main_menu(user_id):

    if is_admin(user_id):

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🪖 Особовий склад",
                        callback_data="staff"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🎖 Керування ролями",
                        callback_data="roles"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✏️ Змінити нік бійця",
                        callback_data="change_fighter_nick"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Профіль",
                        callback_data="profile"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⚙️ Налаштування",
                        callback_data="settings"
                    )
                ]
            ]
        )


    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Профіль",
                    callback_data="profile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Налаштування",
                    callback_data="settings"
                )
            ]
        ]
    )



def back_button():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back"
                )
            ]
        ]
    )



def cancel_button():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Відмінити",
                    callback_data="cancel"
                )
            ]
        ]
    )



# =========================
# START
# =========================


@dp.message(Command("start"))
async def start(message: Message):

    register_user(message)


    # прибираємо старі Reply кнопки
    await message.answer(
        "🧹 Оновлення меню...",
        reply_markup=ReplyKeyboardRemove()
    )


    user = get_user(
        message.from_user.id
    )


    if not user[2]:

        actions[
            message.from_user.id
        ] = {
            "type": "register"
        }


        await message.answer(
            "🛡️ Вас вітає ЗСУ 🇺🇦\n\n"
            "Введіть свій клановий нік:",
            reply_markup=cancel_button()
        )

        return



    await message.answer(
        "🛡️ Головне меню",
        reply_markup=main_menu(
            message.from_user.id
        )
    )



# =========================
# PROFILE
# =========================


@dp.callback_query(lambda c: c.data == "profile")
async def profile(call: CallbackQuery):

    register_user(call.message)


    user = get_user(
        call.from_user.id
    )


    await call.message.edit_text(
        f"👤 Профіль\n\n"
        f"Нік: {user[2]}\n"
        f"Роль: {user[3]}\n"
        f"Статус: {status_icon(user[5])}",
        reply_markup=back_button()
    )



# =========================
# SETTINGS
# =========================


@dp.callback_query(lambda c: c.data == "settings")
async def settings(call: CallbackQuery):

    await call.message.edit_text(
        "⚙️ Налаштування",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✏️ Змінити свій нік",
                        callback_data="change_my_nick"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        )
    )



# =========================
# CHANGE OWN NICK
# =========================


@dp.callback_query(lambda c: c.data == "change_my_nick")
async def change_my_nick(call: CallbackQuery):

    actions[
        call.from_user.id
    ] = {
        "type": "my_nick"
    }


    await call.message.edit_text(
        "✏️ Введіть новий нік:",
        reply_markup=cancel_button()
    )



# =========================
# BACK
# =========================


@dp.callback_query(lambda c: c.data == "back")
async def back(call: CallbackQuery):

    await call.message.edit_text(
        "🛡️ Головне меню",
        reply_markup=main_menu(
            call.from_user.id
        )
    )



# =========================
# CANCEL
# =========================


@dp.callback_query(lambda c: c.data == "cancel")
async def cancel(call: CallbackQuery):

    actions.pop(
        call.from_user.id,
        None
    )


    try:
        await call.message.delete()

    except:
        pass


    await call.message.answer(
        "❌ Дію скасовано",
        reply_markup=main_menu(
            call.from_user.id
        )
    )
# =========================
# STAFF LIST
# =========================


@dp.callback_query(lambda c: c.data == "staff")
async def staff(call: CallbackQuery):

    register_user(call.message)


    if not is_admin(call.from_user.id):

        await call.answer(
            "❌ Немає доступу",
            show_alert=True
        )
        return



    cursor.execute(
        """
        SELECT clan_name, role, last_online
        FROM users
        WHERE clan_name IS NOT NULL
        ORDER BY role_level ASC, clan_name ASC
        """
    )


    users = cursor.fetchall()


    text = "🪖 Особовий склад:\n"


    if not users:

        text += "\nПоки що порожньо"

    else:

        current_role = None


        for user in users:

            if current_role != user[1]:

                current_role = user[1]
                text += f"\n{current_role}\n"


            text += (
                f"• {user[0]} "
                f"{status_icon(user[2])}\n"
            )



    await call.message.edit_text(
        text,
        reply_markup=back_button()
    )



# =========================
# ROLE MANAGEMENT
# =========================


@dp.callback_query(lambda c: c.data == "roles")
async def roles(call: CallbackQuery):

    if not is_admin(call.from_user.id):

        await call.answer(
            "❌ Немає доступу",
            show_alert=True
        )
        return



    cursor.execute(
        """
        SELECT id, clan_name, role
        FROM users
        WHERE clan_name IS NOT NULL
        ORDER BY role_level ASC
        """
    )


    users = cursor.fetchall()


    buttons = []


    for user in users:

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{user[1]} | {user[2]}",
                    callback_data=f"select_role_{user[0]}"
                )
            ]
        )


    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Відмінити",
                callback_data="cancel"
            )
        ]
    )


    await call.message.edit_text(
        "🎖 Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )



# =========================
# SELECT USER FOR ROLE
# =========================


@dp.callback_query(
    lambda c: c.data.startswith("select_role_")
)
async def select_role_user(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return



    user_id = int(
        call.data.split("_")[2]
    )


    actions[
        call.from_user.id
    ] = {
        "type": "change_role",
        "target": user_id
    }


    buttons = []


    for role in ROLES:

        buttons.append(
            [
                InlineKeyboardButton(
                    text=role,
                    callback_data=f"give_{ROLES[role]}_{role}"
                )
            ]
        )


    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Відмінити",
                callback_data="cancel"
            )
        ]
    )


    await call.message.edit_text(
        "🎖 Оберіть нову роль:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )



# =========================
# GIVE ROLE
# =========================


@dp.callback_query(
    lambda c: c.data.startswith("give_")
)
async def give_role(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return



    data = call.data.split("_")


    level = int(data[1])

    role = "_".join(
        data[2:]
    )


    action = actions.get(
        call.from_user.id
    )


    if not action:

        await call.answer(
            "❌ Дія завершена",
            show_alert=True
        )
        return



    target = action["target"]


    cursor.execute(
        """
        UPDATE users
        SET role=?,
            role_level=?
        WHERE id=?
        """,
        (
            role,
            level,
            target
        )
    )


    db.commit()


    actions.pop(
        call.from_user.id,
        None
    )


    await call.message.edit_text(
        f"✅ Роль змінено:\n{role}",
        reply_markup=back_button()
    )
# =========================
# CHANGE FIGHTER NICK
# =========================


@dp.callback_query(lambda c: c.data == "change_fighter_nick")
async def change_fighter_nick(call: CallbackQuery):

    if not is_admin(call.from_user.id):

        await call.answer(
            "❌ Немає доступу",
            show_alert=True
        )
        return



    cursor.execute(
        """
        SELECT id, clan_name, role
        FROM users
        WHERE clan_name IS NOT NULL
        ORDER BY role_level ASC
        """
    )


    users = cursor.fetchall()


    buttons = []


    for user in users:

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{user[1]} | {user[2]}",
                    callback_data=f"nick_{user[0]}"
                )
            ]
        )


    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Відмінити",
                callback_data="cancel"
            )
        ]
    )


    await call.message.edit_text(
        "✏️ Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )



@dp.callback_query(
    lambda c: c.data.startswith("nick_")
)
async def select_nick_user(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return


    target = int(
        call.data.split("_")[1]
    )


    actions[
        call.from_user.id
    ] = {
        "type": "fighter_nick",
        "target": target
    }


    await call.message.edit_text(
        "✏️ Введіть новий нік бійця:",
        reply_markup=cancel_button()
    )



# =========================
# TEXT HANDLER
# =========================


@dp.message()
async def text_handler(message: Message):

    register_user(message)


    action = actions.get(
        message.from_user.id
    )


    if not action:
        return



    user_id = message.from_user.id



    # перша реєстрація

    if action["type"] == "register":

        cursor.execute(
            """
            UPDATE users
            SET clan_name=?
            WHERE id=?
            """,
            (
                message.text,
                user_id
            )
        )

        db.commit()


        actions.pop(
            user_id,
            None
        )


        await message.answer(
            "✅ Реєстрація завершена",
            reply_markup=main_menu(
                user_id
            )
        )

        return



    # свій нік

    if action["type"] == "my_nick":

        cursor.execute(
            """
            UPDATE users
            SET clan_name=?
            WHERE id=?
            """,
            (
                message.text,
                user_id
            )
        )

        db.commit()


        actions.pop(
            user_id,
            None
        )


        await message.answer(
            "✅ Ваш нік змінено",
            reply_markup=main_menu(
                user_id
            )
        )

        return



    # чужий нік

    if action["type"] == "fighter_nick":

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


        actions.pop(
            user_id,
            None
        )


        await message.answer(
            "✅ Нік бійця змінено",
            reply_markup=main_menu(
                user_id
            )
        )

        return



# =========================
# START BOT
# =========================


async def main():

    print("BOT STARTING...")


    await bot.delete_webhook(
        drop_pending_updates=True
    )


    print("POLLING STARTED")


    await dp.start_polling(bot)



if __name__ == "__main__":

    asyncio.run(main())
