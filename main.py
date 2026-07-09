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
    ReplyKeyboardRemove,
    BotCommand
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
# NEW DATABASE TABLES
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    created INTEGER
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    event_date TEXT,
    event_time TEXT,
    remind1 INTEGER DEFAULT 0,
    remind15 INTEGER DEFAULT 0,
    started INTEGER DEFAULT 0,
    created INTEGER
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS event_members (
    event_id INTEGER,
    user_id INTEGER,
    status TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS exchange_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    points INTEGER,
    coins INTEGER,
    created INTEGER
)
""")


try:
    cursor.execute(
        "ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0"
    )
except:
    pass


try:
    cursor.execute(
        "ALTER TABLE users ADD COLUMN events_visited INTEGER DEFAULT 0"
    )
except:
        pass


try:
    cursor.execute(
        "ALTER TABLE users ADD COLUMN coins_received INTEGER DEFAULT 0"
    )
except:
        pass


try:
    cursor.execute(
        "ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0"
    )
except:
        pass


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
POINT_PRICE = 100


DEFAULT_ADMINS = {
    "Jordana_SWAT": (
        "👑 Лідер",
        1
    ),

    "Wtfmnnnn": (
        "🛡 Радник",
        2
    )
}



# =========================
# ACTIVE USER ACTIONS
# =========================


actions = {}


# хто відкрив конкретне меню
menu_owner = {}



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

    result = cursor.fetchone()


    if not result:

        role = "⚔️ Солдат"
        level = 7


        if username in DEFAULT_ADMINS:

            role, level = DEFAULT_ADMINS[username]


        cursor.execute(
    """
    INSERT INTO users(
        id,
        username,
        clan_name,
        role,
        role_level,
        last_online,
        points,
        events_visited,
        coins_received,
        streak
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        user_id,
        username,
        None,
        role,
        level,
        int(time.time()),
        0,
        0,
        0,
        0
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



def status_icon(last):

    diff = int(time.time()) - last


    if diff < 300:
        return "🟢"


    if diff < 86400:
        return "🟡"


    return "🔴"
    # =========================
# NEW FUNCTIONS
# =========================

def add_log(text):

    cursor.execute(
        """
        INSERT INTO logs(
            text,
            created
        )
        VALUES (?, ?)
        """,
        (
            text,
            int(time.time())
        )
    )

    db.commit()


def add_points(user_id, amount):

    cursor.execute(
        """
        UPDATE users
        SET points = points + ?
        WHERE id = ?
        """,
        (
            amount,
            user_id
        )
    )

    db.commit()


def remove_points(user_id, amount):

    cursor.execute(
        """
        UPDATE users
        SET points = points - ?
        WHERE id = ?
        """,
        (
            amount,
            user_id
        )
    )

    db.commit()


def add_event_visit(user_id):

    cursor.execute(
        """
        UPDATE users
        SET events_visited =
        events_visited + 1
        WHERE id = ?
        """,
        (user_id,)
    )

    db.commit()
  # =========================
# MENU CHECK
# =========================


def check_menu_owner(call: CallbackQuery):

    owner = menu_owner.get(
        call.message.message_id
    )


    if owner and owner != call.from_user.id:

        return False


    return True



# =========================
# KEYBOARDS
# =========================


def main_menu(user_id):

    keyboard = []

    if is_admin(user_id):

        keyboard.extend([
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
                    text="📅 Події",
                    callback_data="events"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Журнал",
                    callback_data="logs"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Оголошення",
                    callback_data="announce"
                )
            ]
        ])

    keyboard.extend([
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
        ],
        [
            InlineKeyboardButton(
                text="🙈 Сховати меню",
                callback_data="hide_menu"
            )
        ]
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
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


    await message.answer(
        "Оновлення меню...",
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



    msg = await message.answer(
        "🛡️ Головне меню",
        reply_markup=main_menu(
            message.from_user.id
        )
    )


    menu_owner[
        msg.message_id
    ] = message.from_user.id



# =========================
# MENU COMMAND
# =========================


@dp.message(Command("menu"))
async def menu_command(message: Message):

    register_user(message)


    msg = await message.answer(
        "🛡️ Головне меню",
        reply_markup=main_menu(
            message.from_user.id
        )
    )


    menu_owner[
        msg.message_id
    ] = message.from_user.id



# =========================
# HIDE MENU
# =========================


@dp.callback_query(
    lambda c: c.data == "hide_menu"
)
async def hide_menu(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return



    await call.message.edit_text(
        "🙈 Меню приховано.\n\n"
        "Використайте /menu щоб відкрити його."
    )



# =========================
# BACK
# =========================


@dp.callback_query(
    lambda c: c.data == "back"
)
async def back(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return
try:
    await call.message.edit_text(
        "🛡️ Головне меню",
        reply_markup=main_menu(
            call.from_user.id
        )
    )
except:
    pass
  # =========================
# PROFILE
# =========================


@dp.callback_query(
    lambda c: c.data == "profile"
)
async def profile(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return



    register_user(call.message)


    user = get_user(
        call.from_user.id
    )


    await call.message.edit_text(
    f"👤 Профіль\n\n"
    f"Нік: {user[2]}\n"
    f"Роль: {user[3]}\n"
    f"🪙 Бали: {user[6]}\n"
    f"🏆 Подій відвідано: {user[7]}\n"
    f"💰 Монет отримано: {user[8]}\n"
    f"Статус: {status_icon(user[5])}",
    reply_markup=back_button()
)



# =========================
# SETTINGS
# =========================


@dp.callback_query(
    lambda c: c.data == "settings"
)
async def settings(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return



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


@dp.callback_query(
    lambda c: c.data == "my_nick"
)
async def my_nick(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return



    actions[
        call.from_user.id
    ] = {
        "type": "my_nick",
        "message_id": call.message.message_id
    }



    await call.message.edit_text(
        "✏️ Введіть новий клановий нік:",
        reply_markup=cancel_button()
    )



# =========================
# CANCEL
# =========================


@dp.callback_query(
    lambda c: c.data == "cancel"
)
async def cancel(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return



    actions.pop(
        call.from_user.id,
        None
    )


    try:

        await call.message.delete()

    except:

        pass



    msg = await call.message.answer(
        "❌ Дію скасовано",
        reply_markup=main_menu(
            call.from_user.id
        )
    )


    menu_owner[
        msg.message_id
    ] = call.from_user.id
  # =========================
# STAFF LIST
# =========================


@dp.callback_query(
    lambda c: c.data == "staff"
)
async def staff(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return



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


@dp.callback_query(
    lambda c: c.data == "roles"
)
async def roles(call: CallbackQuery):

    if not check_menu_owner(call):
        return


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
                    callback_data=f"role_user_{user[0]}"
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
# SELECT ROLE USER
# =========================


@dp.callback_query(
    lambda c: c.data.startswith("role_user_")
)
async def select_role_user(call: CallbackQuery):

    if not check_menu_owner(call):
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


    for role, level in ROLES.items():

        buttons.append(
            [
                InlineKeyboardButton(
                    text=role,
                    callback_data=f"give_role_{level}"
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

    if not check_menu_owner(call):
        return


    level = int(
        call.data.split("_")[2]
    )


    role = None


    for name, lvl in ROLES.items():

        if lvl == level:
            role = name
            break



    action = actions.get(
        call.from_user.id
    )


    if not action:
        return
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
            action["target"]
        )
    )

    db.commit()

    target = get_user(action["target"])

    add_log(
        f"{get_user(call.from_user.id)[2]} "
        f"видав роль {role} бійцю {target[2]}"
    )

    actions.pop(
        call.from_user.id,
        None
    )





    await call.message.edit_text(
        f"✅ Роль змінено\n\n"
        f"Нова роль: {role}",
        reply_markup=back_button()
    )


# =========================
# LOGS
# =========================

@dp.callback_query(
    lambda c: c.data == "logs"
)
async def logs_menu(call: CallbackQuery):

    if not check_menu_owner(call):

        await call.answer(
            "❌ Це не ваше меню",
            show_alert=True
        )

        return


    if not is_admin(call.from_user.id):
        return


    cursor.execute(
        """
        SELECT text
        FROM logs
        ORDER BY id DESC
        LIMIT 20
        """
    )

    rows = cursor.fetchall()


    text = "📜 Журнал дій\n\n"


    if not rows:
        text += "Журнал порожній."
    else:
        for row in rows:
            text += f"• {row[0]}\n"


            await call.message.edit_text(
        text,
        reply_markup=back_button()
    )

@dp.callback_query(

    lambda c: c.data == "events"

)

async def events_menu(call: CallbackQuery):

    if not check_menu_owner(call):
        return

    buttons = []

    if is_admin(call.from_user.id):
        buttons.append(
            [
                InlineKeyboardButton(
                    text="➕ Створити подію",
                    callback_data="create_event"
                )
            ]
        )

    cursor.execute(
        """
        SELECT id, title, event_date, event_time
        FROM events
        ORDER BY id DESC
        LIMIT 10
        """
    )

    events = cursor.fetchall()

    for event in events:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📅 {event[1]} | {event[2]} {event[3]}",
                    callback_data=f"event_{event[0]}"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back"
            )
        ]
    )

    await call.message.edit_text(
        "📅 Події клану",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )
@dp.callback_query(
    lambda c: c.data.startswith("event_")
)
async def open_event(call: CallbackQuery):

    if not check_menu_owner(call):
        return

    event_id = int(call.data.split("_")[1])

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE id=?
        """,
        (event_id,)
    )

    event = cursor.fetchone()

    if not event:
        await call.answer("Подію не знайдено")
        return

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM event_members
        WHERE event_id=?
        AND status=?
        """,
        (
            event_id,
            "joined"
        )
    )

    members = cursor.fetchone()[0]

    text = (
        f"📅 {event[1]}\n\n"
        f"📝 {event[2]}\n\n"
        f"📆 {event[3]}\n"
        f"🕒 {event[4]}\n"
        f"👥 Учасники: {members}"
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Я буду",
                        callback_data=f"join_{event_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👥 Учасники",
                        callback_data=f"members_{event_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Не буду",
                        callback_data=f"leave_{event_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="events"
                    )
                ]
            ]
        )
    )    
@dp.callback_query(
    lambda c: c.data.startswith("join_")
)
async def join_event(call: CallbackQuery):

    if not check_menu_owner(call):
        return

    event_id = int(
        call.data.split("_")[1]
    )

    user_id = call.from_user.id

    cursor.execute(
        """
        SELECT event_id
        FROM event_members
        WHERE event_id=? AND user_id=?
        """,
        (
            event_id,
            user_id
        )
    )

    exists = cursor.fetchone()

    if exists:

        await call.answer(
            "Ви вже записані на подію",
            show_alert=True
        )
        return


    cursor.execute(
        """
        INSERT INTO event_members(
            event_id,
            user_id,
            status
        )
        VALUES (?, ?, ?)
        """,
        (
            event_id,
            user_id,
            "joined"
        )
    )

    db.commit()


    add_log(
        f"{get_user(user_id)[2]} "
        f"записався на подію"
    )


    await call.answer(
        "✅ Ви записані"
    )
@dp.callback_query(
    lambda c: c.data.startswith("leave_")
)
async def leave_event(call: CallbackQuery):

    if not check_menu_owner(call):
        return

    event_id = int(
        call.data.split("_")[1]
    )

    user_id = call.from_user.id


    cursor.execute(
        """
        DELETE FROM event_members
        WHERE event_id=? AND user_id=?
        """,
        (
            event_id,
            user_id
        )
    )

    db.commit()


    add_log(
        f"{get_user(user_id)[2]} "
        f"відмовився від події"
    )


    await call.answer(
        "❌ Ви більше не берете участь"
    )
@dp.callback_query(
    lambda c: c.data.startswith("members_")
)
async def event_members(call: CallbackQuery):

    if not check_menu_owner(call):
        return


    event_id = int(
        call.data.split("_")[1]
    )


    cursor.execute(
        """
        SELECT users.clan_name
        FROM event_members
        JOIN users
        ON users.id = event_members.user_id
        WHERE event_members.event_id=?
        AND event_members.status=?
        """,
        (
            event_id,
            "joined"
        )
    )


    members = cursor.fetchall()


    text = "👥 Учасники події:\n\n"


    if not members:

        text += "Поки ніхто не записався."

    else:

        for member in members:

            text += f"• {member[0]}\n"



    await call.message.edit_text(
        text,
        reply_markup=back_button()
    )
async def open_event(call: CallbackQuery):

    if not check_menu_owner(call):
        return

    event_id = int(
        call.data.split("_")[1]
    )

    cursor.execute(
        """
        SELECT *
        FROM events
        WHERE id=?
        """,
        (event_id,)
    )

    event = cursor.fetchone()

    if not event:
        await call.answer(
            "Подію не знайдено",
            show_alert=True
        )
        return


    await call.message.edit_text(
        f"📅 {event[1]}\n\n"
        f"📝 {event[2]}\n\n"
        f"📆 Дата: {event[3]}\n"
        f"🕒 Час: {event[4]}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Я буду",
                        callback_data=f"join_{event_id}"
                    )
                ],
                [
    InlineKeyboardButton(
        text="👥 Учасники",
        callback_data=f"members_{event_id}"
    )
],
                [
                    InlineKeyboardButton(
                        text="❌ Не буду",
                        callback_data=f"leave_{event_id}"
                    )
                ],
                [
    InlineKeyboardButton(
        text="👥 Учасники",
        callback_data=f"members_{event_id}"
    )
],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="events"
                    )
                ]
            ]
        )
    )
@dp.callback_query(
    lambda c: c.data == "create_event"
)
async def create_event(call: CallbackQuery):

    if not check_menu_owner(call):
        return

    if not is_admin(call.from_user.id):
        return

    actions[call.from_user.id] = {
        "type": "create_event_title"
    }

    await call.message.edit_text(
        "📅 Введіть назву події:",
        reply_markup=cancel_button()
    )
# =========================
# CHANGE FIGHTER NICK
# =========================


@dp.callback_query(
    lambda c: c.data == "change_nick"
)
async def change_nick(call: CallbackQuery):

    if not check_menu_owner(call):
        return


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
                    callback_data=f"nick_user_{user[0]}"
                )
            ]
        )


    await call.message.edit_text(
        "✏️ Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    
    )
  # =========================
# SELECT FIGHTER FOR NICK
# =========================


@dp.callback_query(
    lambda c: c.data.startswith("nick_user_")
)
async def select_fighter_nick(call: CallbackQuery):

    if not check_menu_owner(call):
        return


    target = int(
        call.data.split("_")[2]
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


    # створення події - назва

    if action["type"] == "create_event_title":

        actions[user_id] = {
            "type": "create_event_description",
            "title": message.text
        }

        await message.answer(
            "📝 Введіть опис події:"
        )

        return
            # створення події - опис

    if action["type"] == "create_event_description":

        actions[user_id] = {
            "type": "create_event_date",
            "title": action["title"],
            "description": message.text
        }

        await message.answer(
            "📅 Введіть дату події\n"
            "Приклад: 10.07.2026"
        )

        return
            # створення події - дата

    if action["type"] == "create_event_date":

        actions[user_id] = {
            "type": "create_event_time",
            "title": action["title"],
            "description": action["description"],
            "event_date": message.text
        }

        await message.answer(
            "🕒 Введіть час події\n"
            "Приклад: 20:00"
        )

        return
            # створення події - час

    if action["type"] == "create_event_time":

        cursor.execute(
            """
            INSERT INTO events(
                title,
                description,
                event_date,
                event_time,
                created
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                action["title"],
                action["description"],
                action["event_date"],
                message.text,
                int(time.time())
            )
        )

        db.commit()

        add_log(
            f"{get_user(user_id)[2]} "
            f"створив подію {action['title']}"
        )

        actions.pop(
            user_id,
            None
        )

        await message.answer(
            "✅ Подію створено",
            reply_markup=main_menu(user_id)
        )

        return
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
        add_log(
    f"{get_user(user_id)[2]} змінив свій нік"
)


        actions.pop(
            user_id,
            None
        )


        msg = await message.answer(
            "✅ Реєстрація завершена",
            reply_markup=main_menu(user_id)
        )


        menu_owner[
            msg.message_id
        ] = user_id


        return



    # зміна свого ніку

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
        add_log(
    f"{get_user(user_id)[2]} змінив свій нік"
)


        actions.pop(
            user_id,
            None
        )


        msg = await message.answer(
            "✅ Ваш нік змінено",
            reply_markup=main_menu(user_id)
        )


        menu_owner[
            msg.message_id
        ] = user_id


        return



    # зміна ніку іншого бійця

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

        target = get_user(
            action["target"]
        )

        add_log(
            f"{get_user(user_id)[2]} "
            f"змінив нік бійцю {target[2]}"
        )

        actions.pop(
            user_id,
            None
        )

        msg = await message.answer(
            "✅ Нік бійця змінено",
            reply_markup=main_menu(user_id)
        )

        menu_owner[
            msg.message_id
        ] = user_id


        return



# =========================
# COMMAND LIST
# =========================


async def setup_commands():

    await bot.set_my_commands(
        [
            BotCommand(
                command="start",
                description="Запустити бота"
            ),
            BotCommand(
                command="menu",
                description="Відкрити меню"
            )
        ]
    )



# =========================
# BOT START
# =========================


async def main():

    print("BOT STARTING...")


    await setup_commands()


    await bot.delete_webhook(
        drop_pending_updates=True
    )


    print("POLLING STARTED")


    await dp.start_polling(bot)



if __name__ == "__main__":

    asyncio.run(main())
  
