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
    InlineKeyboardButton
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
    fullname TEXT,
    clan_name TEXT,
    role TEXT DEFAULT '⚔️ Солдати',
    role_level INTEGER DEFAULT 7,
    last_online INTEGER DEFAULT 0
)
""")


db.commit()



# =========================
# CONFIG
# =========================


ROLES = {
    "👑 Лідер": 1,
    "🛡 Радник": 2,
    "🎣 Головний Рибалка": 3,
    "🌾 Головний Фермер": 4,
    "🪓 Головний Лісоруб": 5,
    "🔨 Головний Коваль": 6,
    "⚔️ Солдати": 7
}


START_ROLES = {
    "Jordana_SWAT": "👑 Лідер",
    "Wtfmnnnn": "🛡 Радник"
}



# тут зберігаємо активні дії

actions = {}



# =========================
# ONLINE STATUS
# =========================


def get_status(last_online):

    now = int(time.time())

    diff = now - last_online


    if diff < 300:
        return "🟢"


    elif diff < 86400:
        return "🟡"


    else:
        return "🔴"



# =========================
# DATABASE FUNCTIONS
# =========================


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



def register_user(message: Message):

    user_id = message.from_user.id
    username = message.from_user.username


    cursor.execute(
        "SELECT id FROM users WHERE id=?",
        (user_id,)
    )


    exists = cursor.fetchone()


    if not exists:


        role = "⚔️ Солдати"
        level = 7


        if username in START_ROLES:

            role = START_ROLES[username]
            level = ROLES[role]


        cursor.execute(
            """
            INSERT INTO users
            (
                id,
                username,
                fullname,
                role,
                role_level,
                last_online
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                message.from_user.full_name,
                role,
                level,
                int(time.time())
            )
        )

        db.commit()


    update_online(user_id)



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


    return user[5] <= 2
  # =========================
# INLINE MENUS
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
                        callback_data="change_nick"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Профіль",
                        callback_data="profile"
                    ),
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


    user = get_user(
        message.from_user.id
    )


    if not user[3]:

        actions[
            message.from_user.id
        ] = {
            "type": "register_name"
        }


        await message.answer(
            "🛡️ Вас вітає ЗСУ 🇺🇦\n\n"
            "Введіть ваш клановий нік:",
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
# CALLBACK PROFILE
# =========================


@dp.callback_query(lambda c: c.data == "profile")
async def profile(call: CallbackQuery):

    register_user(call.message)


    user = get_user(
        call.from_user.id
    )


    await call.message.edit_text(
        f"👤 Профіль\n\n"
        f"Нік: {user[3]}\n"
        f"Роль: {user[4]}\n"
        f"Статус: {get_status(user[6])}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
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
                        callback_data="my_nick"
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


@dp.callback_query(lambda c: c.data == "my_nick")
async def my_nick(call: CallbackQuery):

    actions[
        call.from_user.id
    ] = {
        "type": "change_my_nick",
        "message_id": call.message.message_id
    }


    await call.message.edit_text(
        "✏️ Введіть новий клановий нік:",
        reply_markup=cancel_button()
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


    if not users:

        text = "🪖 Особовий склад порожній"

    else:

        text = "🪖 Особовий склад:\n\n"


        last_role = None


        for user in users:


            if user[1] != last_role:

                text += f"\n{user[1]}\n"
                last_role = user[1]


            text += (
                f"• {user[0]} "
                f"{get_status(user[2])}\n"
            )



    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
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
# ROLE MANAGEMENT START
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
                    text=f"{user[1]} ({user[2]})",
                    callback_data=f"setrole_user_{user[0]}"
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


    actions[
        call.from_user.id
    ] = {
        "type": "choose_role_user"
    }


    await call.message.edit_text(
        "🎖 Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )



# =========================
# CHOOSE ROLE
# =========================


@dp.callback_query(
    lambda c: c.data.startswith("setrole_user_")
)
async def choose_role_user(call: CallbackQuery):

    if not is_admin(call.from_user.id):

        return



    target_id = int(
        call.data.split("_")[2]
    )


    actions[
        call.from_user.id
    ] = {
        "type": "choose_role",
        "target": target_id
    }



    buttons = []


    for role in ROLES:

        buttons.append(
            [
                InlineKeyboardButton(
                    text=role,
                    callback_data=f"give_role_{ROLES[role]}_{role}"
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
    lambda c: c.data.startswith("give_role_")
)
async def give_role(call: CallbackQuery):

    if not is_admin(call.from_user.id):

        return



    data = call.data.split("_")


    level = int(data[2])


    role = "_".join(
        data[3:]
    )



    action = actions.get(
        call.from_user.id
    )


    if not action:

        await call.answer(
            "❌ Час дії вийшов",
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
        f"✅ Роль змінено на:\n{role}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
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
# CHANGE FIGHTER NICK
# =========================


@dp.callback_query(lambda c: c.data == "change_nick")
async def change_nick_start(call: CallbackQuery):

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
                    text=f"{user[1]} ({user[2]})",
                    callback_data=f"nick_user_{user[0]}"
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


    actions[
        call.from_user.id
    ] = {
        "type": "choose_nick_user"
    }


    await call.message.edit_text(
        "✏️ Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )



# =========================
# CHOOSE FIGHTER FOR NICK
# =========================


@dp.callback_query(
    lambda c: c.data.startswith("nick_user_")
)
async def choose_nick_user(call: CallbackQuery):

    if not is_admin(call.from_user.id):

        return



    target_id = int(
        call.data.split("_")[2]
    )


    actions[
        call.from_user.id
    ] = {
        "type": "new_nick",
        "target": target_id
    }



    await call.message.edit_text(
        "✏️ Введіть новий клановий нік:",
        reply_markup=cancel_button()
    )



# =========================
# TEXT ACTIONS
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



    # Реєстрація нового гравця

    if action["type"] == "register_name":


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



    # Зміна свого ніку

    if action["type"] == "change_my_nick":


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



    # Зміна ніку іншого бійця

    if action["type"] == "new_nick":


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
# BOT START
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
  
