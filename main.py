import asyncio
import os
import sqlite3
import time
import random
from datetime import datetime
from contextlib import contextmanager

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
from aiogram.exceptions import TelegramBadRequest

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений")

bot = Bot(TOKEN)
dp = Dispatcher()

# =========================
# DATABASE
# =========================
class Database:
    def __init__(self, db_path="clan.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                clan_name TEXT,
                role TEXT,
                role_level INTEGER,
                last_online INTEGER,
                registered_at INTEGER DEFAULT 0,
                chat_id INTEGER DEFAULT 0,
                is_registered INTEGER DEFAULT 0
            )
            """)
            
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
                remind15 INTEGER DEFAULT 0,
                started INTEGER DEFAULT 0,
                created INTEGER,
                creator_id INTEGER
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
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                clan_name TEXT,
                message_text TEXT,
                created INTEGER
            )
            """)
            
            conn.commit()

db = Database()

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
    "⚔️ Солдат": 7,
    "🤡 Придворний Шут": 8,
    "🫶🏿☠️ Чистильщик туалетів": 9
}

DEFAULT_ADMINS = {
    "Jordana_SWAT": ("👑 Лідер", 1),
    "Wtfmnnnn": ("🛡 Радник", 2)
}

# =========================
# ФРАЗИ
# =========================
ROLL_CALL_PHRASES = [
    "🌅 Доброго ранку! Перекличка!",
    "🔔 Перекличка! Всі на місці?",
    "⚡️ Ранкова побудова!",
    "🎯 Увага! Перекличка!",
    "🔥 Вогонь по готовності!",
    "💪 Збірка!",
    "🏃 Швидка перекличка!",
    "🤡 Алло! Всі живі?"
]

GATHER_PHRASES = [
    "🔔 **ЗБІР!** Всі сюди!",
    "⚡️ **ТЕРМІНОВО!** Збір всіх!",
    "🔥 **УВАГА!** Загальний збір!",
    "🎯 **ВСІМ!** Негайно на зв'язок!",
    "💪 **ЗБІР КЛАНУ!** Відповідайте!",
    "🚨 **ТРИВОГА!** Загальний збір!",
    "📢 **УВАГА КЛАН!** Збір!",
    "⚔️ **ВСІ ДО ЗБОРУ!**"
]

TAG_REPLIES = [
    "👋 Я тут!",
    "🫡 Що треба?",
    "😊 Слухаю!",
    "🙋‍♂️ Я на місці!",
    "✋ Тут я!",
    "🫡 Завжди готовий!",
    "👋 Привіт!",
    "🤔 Хто кликав?",
    "😏 Ну що?",
    "🫡 Так!",
    "🙂 Я тут, що трапилось?"
]

# =========================
# ACTIONS
# =========================
actions = {}
menu_owner = {}
roll_call_sent = False

# =========================
# DATABASE FUNCTIONS
# =========================

def register_user_start(message: Message):
    """Реєстрація через /start - створює запис але без ніка"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    with db.connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            role = "⚔️ Солдат"
            level = 7
            
            if username in DEFAULT_ADMINS:
                role, level = DEFAULT_ADMINS[username]
            
            cursor.execute("""
                INSERT INTO users(id, username, clan_name, role, role_level, last_online, registered_at, chat_id, is_registered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, username, None, role, level, int(time.time()), int(time.time()), 0, 0
            ))
            conn.commit()
            
            add_log(f"Новий користувач {username or user_id} почав реєстрацію")
            return False
        
        cursor.execute("""
            UPDATE users 
            SET last_online=?, username=?
            WHERE id=?
        """, (int(time.time()), username, user_id))
        conn.commit()
        return True

def update_user_clan_name(user_id, clan_name):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET clan_name=?, is_registered=1
            WHERE id=?
        """, (clan_name, user_id))
        conn.commit()

def get_user(user_id):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return cursor.fetchone()

def is_admin(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return user['role_level'] <= 2

def is_leader_or_advisor(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return user['role_level'] <= 2

def can_manage_roles(admin_user_id, target_user_id):
    admin = get_user(admin_user_id)
    target = get_user(target_user_id)
    
    if not admin or not target:
        return False
    
    if admin['role_level'] == 1:
        return True
    
    if admin['role_level'] == 2:
        if target['role_level'] <= 2:
            return False
        return True
    
    return False

def status_icon(last):
    diff = int(time.time()) - last
    if diff < 300:
        return "🟢"
    if diff < 86400:
        return "🟡"
    return "🔴"

def add_log(text):
    try:
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs(text, created) VALUES (?, ?)", (text, int(time.time())))
            conn.commit()
    except:
        pass

def get_registered_count():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered=1")
        return cursor.fetchone()[0]

def get_all_registered_users():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, clan_name FROM users WHERE is_registered=1")
        return cursor.fetchall()

def get_all_users_for_nick_change():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, clan_name, role 
            FROM users 
            WHERE is_registered=1 
            ORDER BY clan_name ASC
        """)
        return cursor.fetchall()

def get_user_by_clan_name(clan_name):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE clan_name=? AND is_registered=1", (clan_name,))
        return cursor.fetchone()

def get_event_members(event_id):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT users.clan_name, users.role, users.id
            FROM event_members
            JOIN users ON users.id = event_members.user_id
            WHERE event_members.event_id=? AND event_members.status='joined'
        """, (event_id,))
        return cursor.fetchall()

def get_all_chats():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM chats")
        return cursor.fetchall()

def save_chat(chat_id):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO chats(chat_id) VALUES (?)", (chat_id,))
        conn.commit()

def save_message(chat_id, user_id, username, clan_name, message_text):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_messages(chat_id, user_id, username, clan_name, message_text, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (chat_id, user_id, username, clan_name, message_text, int(time.time())))
        conn.commit()

def get_chat_messages(chat_id, limit=50):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, clan_name, message_text, created
            FROM chat_messages
            WHERE chat_id=?
            ORDER BY created DESC
            LIMIT ?
        """, (chat_id, limit))
        return cursor.fetchall()

def check_menu_owner(call: CallbackQuery):
    owner = menu_owner.get(call.message.message_id)
    if owner and owner != call.from_user.id:
        return False
    return True

# =========================
# KEYBOARDS
# =========================

def main_menu(user_id):
    keyboard = []
    
    keyboard.extend([
        [InlineKeyboardButton(text="🪖 Особовий склад", callback_data="staff")],
        [InlineKeyboardButton(text="📅 Події", callback_data="events")],
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile")]
    ])
    
    if is_leader_or_advisor(user_id):
        keyboard.extend([
            [InlineKeyboardButton(text="⚙️ Управління кланом", callback_data="clan_management")]
        ])
    
    keyboard.extend([
        [InlineKeyboardButton(text="📨 Історія чату", callback_data="chat_history")],
        [InlineKeyboardButton(text="🙈 Сховати меню", callback_data="hide_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def clan_management_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎖 Керування ролями", callback_data="roles")],
        [InlineKeyboardButton(text="✏️ Змінити нік бійця", callback_data="change_nick")],
        [InlineKeyboardButton(text="📜 Журнал", callback_data="logs")],
        [InlineKeyboardButton(text="📢 Оголошення", callback_data="announce")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def cancel_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel")]
    ])

# =========================
# START & COMMANDS
# =========================

@dp.message(Command("start"))
async def start(message: Message):
    register_user_start(message)
    await message.answer("Оновлення меню...", reply_markup=ReplyKeyboardRemove())
    
    save_chat(message.chat.id)
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET chat_id=? WHERE id=?", (message.chat.id, message.from_user.id))
        conn.commit()
    
    user = get_user(message.from_user.id)
    
    if not user['is_registered']:
        actions[message.from_user.id] = {"type": "register"}
        await message.answer(
            "🛡️ **Вас вітає ЗСУ 🇺🇦**\n\n"
            "Введіть свій клановий нік для реєстрації:",
            reply_markup=cancel_button(),
            parse_mode="Markdown"
        )
        return
    
    msg = await message.answer("🛡️ **Головне меню**", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    menu_owner[msg.message_id] = message.from_user.id

@dp.message(Command("menu"))
async def menu_command(message: Message):
    user = get_user(message.from_user.id)
    if not user or not user['is_registered']:
        await message.answer("❌ Спочатку зареєструйтесь через /start")
        return
    
    msg = await message.answer("🛡️ **Головне меню**", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    menu_owner[msg.message_id] = message.from_user.id

@dp.message(Command("check"))
async def check_command(message: Message):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ви не зареєстровані. Напишіть /start")
        return
    
    if user['is_registered']:
        await message.answer(
            f"✅ **Ви зареєстровані!**\n\n"
            f"🏷 Нік: {user['clan_name']}\n"
            f"👑 Роль: {user['role']}\n"
            f"📅 Зареєстровано: {datetime.fromtimestamp(user['registered_at']).strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "⚠️ **Ви почали реєстрацію, але ще не вказали клановий нік!**\n\n"
            "Напишіть /start щоб завершити реєстрацію.",
            parse_mode="Markdown"
        )

# =========================
# CHAT HISTORY
# =========================

@dp.callback_query(lambda c: c.data == "chat_history")
async def chat_history(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    if not user or not user['is_registered']:
        await call.answer("❌ Ви не зареєстровані!", show_alert=True)
        return
    
    chats = get_all_chats()
    
    if not chats:
        await call.message.edit_text(
            "📨 **Історія чату**\n\n"
            "Немає збережених чатів.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
        return
    
    buttons = []
    for chat in chats[:10]:
        buttons.append([
            InlineKeyboardButton(
                text=f"Чат {chat[0]}",
                callback_data=f"history_chat_{chat[0]}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    await call.message.edit_text(
        "📨 **Історія чату**\n\n"
        "Оберіть чат для перегляду:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("history_chat_"))
async def view_chat_history(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    chat_id = int(call.data.split("_")[2])
    messages = get_chat_messages(chat_id, 50)
    
    if not messages:
        await call.message.edit_text(
            "📨 **Історія чату**\n\n"
            "У цьому чаті ще немає повідомлень.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
        return
    
    text = f"📨 **Історія чату {chat_id}**\n\n"
    
    for msg in reversed(messages):
        clan = msg['clan_name'] or msg['username'] or "Невідомий"
        time_str = datetime.fromtimestamp(msg['created']).strftime("%H:%M")
        text += f"`{time_str}` **{clan}:** {msg['message_text']}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (обрізано)"
    
    await call.message.edit_text(
        text,
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

# =========================
# BACK, CANCEL, HIDE
# =========================

@dp.callback_query(lambda c: c.data == "back")
async def back(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    try:
        await call.message.edit_text("🛡️ **Головне меню**", reply_markup=main_menu(call.from_user.id), parse_mode="Markdown")
    except TelegramBadRequest:
        pass

@dp.callback_query(lambda c: c.data == "cancel")
async def cancel(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    actions.pop(call.from_user.id, None)
    
    try:
        await call.message.delete()
    except:
        pass
    
    msg = await call.message.answer("❌ Дію скасовано", reply_markup=main_menu(call.from_user.id))
    menu_owner[msg.message_id] = call.from_user.id

@dp.callback_query(lambda c: c.data == "hide_menu")
async def hide_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    await call.message.edit_text("🙈 Меню приховано.\n\nВикористайте /menu щоб відкрити його.")

# =========================
# CLAN MANAGEMENT
# =========================

@dp.callback_query(lambda c: c.data == "clan_management")
async def clan_management(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    await call.message.edit_text(
        "⚙️ **Управління кланом**\n\nОберіть дію:",
        reply_markup=clan_management_menu(),
        parse_mode="Markdown"
    )

# =========================
# STAFF LIST
# =========================

@dp.callback_query(lambda c: c.data == "staff")
async def staff(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT clan_name, role, last_online
            FROM users
            WHERE is_registered=1
            ORDER BY role_level ASC, clan_name ASC
        """)
        users = cursor.fetchall()
    
    text = "🪖 **Особовий склад клану**\n\n"
    current_role = None
    
    for user in users:
        if current_role != user['role']:
            current_role = user['role']
            text += f"\n**{current_role}**\n"
        
        status = status_icon(user['last_online'])
        text += f"▫️ {user['clan_name']} {status}\n"
    
    text += f"\n👥 Всього: {len(users)} бійців"
    
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="Markdown")

# =========================
# PROFILE
# =========================

@dp.callback_query(lambda c: c.data == "profile")
async def profile(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    
    if not user or not user['is_registered']:
        await call.answer("❌ Ви не зареєстровані!", show_alert=True)
        return
    
    reg_date = datetime.fromtimestamp(user['registered_at']).strftime('%d.%m.%Y')
    
    await call.message.edit_text(
        f"👤 **Профіль**\n\n"
        f"🏷 Нік: {user['clan_name']}\n"
        f"👑 Роль: {user['role']}\n"
        f"📊 Статус: {status_icon(user['last_online'])}\n"
        f"📅 З нами: {reg_date}",
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

# =========================
# EVENTS
# =========================

@dp.callback_query(lambda c: c.data == "events")
async def events_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, event_date, event_time, description
            FROM events
            WHERE started = 0
            ORDER BY event_date || ' ' || event_time ASC
            LIMIT 10
        """)
        events = cursor.fetchall()
    
    buttons = []
    if is_admin(call.from_user.id):
        buttons.append([InlineKeyboardButton(text="➕ Створити подію", callback_data="create_event")])
    
    for event in events:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {event['title']}",
            callback_data=f"event_{event['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    text = "📅 **Події клану**\n\n"
    if not events:
        text += "Немає запланованих подій."
    else:
        for event in events:
            text += f"▫️ **{event['title']}**\n"
            text += f"   📆 {event['event_date']} 🕒 {event['event_time']}\n"
            text += f"   📝 {event['description'][:40]}{'...' if len(event['description']) > 40 else ''}\n\n"
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("event_"))
async def open_event(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    event_id = int(call.data.split("_")[1])
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id=?", (event_id,))
        event = cursor.fetchone()
        
        if not event:
            await call.answer("Подію не знайдено", show_alert=True)
            return
        
        members = get_event_members(event_id)
    
    members_text = "\n".join([f"▫️ {m['clan_name']} ({m['role']})" for m in members[:10]])
    if len(members) > 10:
        members_text += f"\n... та ще {len(members) - 10}"
    
    text = (
        f"📅 **{event['title']}**\n\n"
        f"📝 {event['description']}\n\n"
        f"📆 Дата: {event['event_date']}\n"
        f"🕒 Час: {event['event_time']}\n\n"
        f"👥 Учасників: {len(members)}\n"
        f"{members_text if members else 'Поки ніхто не записався'}"
    )
    
    buttons = [
        [InlineKeyboardButton(text="✅ Я буду", callback_data=f"join_{event_id}")],
        [InlineKeyboardButton(text="👥 Учасники", callback_data=f"members_{event_id}")],
        [InlineKeyboardButton(text="❌ Не буду", callback_data=f"leave_{event_id}")]
    ]
    
    if is_admin(call.from_user.id):
        buttons.append([InlineKeyboardButton(text="🗑 Видалити", callback_data=f"delete_event_{event_id}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="events")])
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("join_"))
async def join_event(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    event_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT event_id FROM event_members WHERE event_id=? AND user_id=?", (event_id, user_id))
        exists = cursor.fetchone()
        
        if exists:
            await call.answer("Ви вже записані на подію", show_alert=True)
            return
        
        cursor.execute("INSERT INTO event_members(event_id, user_id, status) VALUES (?, ?, ?)", 
                      (event_id, user_id, "joined"))
        conn.commit()
    
    user = get_user(user_id)
    add_log(f"{user['clan_name']} записався на подію")
    await call.answer("✅ Ви записані на подію!")

@dp.callback_query(lambda c: c.data.startswith("leave_"))
async def leave_event(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    event_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM event_members WHERE event_id=? AND user_id=?", (event_id, user_id))
        conn.commit()
    
    user = get_user(user_id)
    add_log(f"{user['clan_name']} відмовився від події")
    await call.answer("❌ Ви більше не берете участь")

@dp.callback_query(lambda c: c.data.startswith("members_"))
async def event_members(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    event_id = int(call.data.split("_")[1])
    members = get_event_members(event_id)
    
    if not members:
        text = "👥 **Учасники події**\n\nПоки ніхто не записався."
    else:
        text = "👥 **Учасники події**\n\n"
        for m in members:
            text += f"▫️ {m['clan_name']} ({m['role']})\n"
    
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data.startswith("delete_event_"))
async def delete_event(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    event_id = int(call.data.split("_")[2])
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM event_members WHERE event_id=?", (event_id,))
        cursor.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
    
    add_log(f"{get_user(call.from_user.id)['clan_name']} видалив подію")
    await call.answer("✅ Подію видалено")
    await events_menu(call)

@dp.callback_query(lambda c: c.data == "create_event")
async def create_event(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "create_event_title"}
    await call.message.edit_text(
        "📅 **Створення події**\n\nВведіть назву події:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# CHANGE NICK (ЧЕРЕЗ ВИБІР ГРАВЦЯ)
# =========================

@dp.callback_query(lambda c: c.data == "change_nick")
async def change_nick_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    users = get_all_users_for_nick_change()
    
    if not users:
        await call.message.edit_text(
            "❌ Немає зареєстрованих користувачів.",
            reply_markup=back_button()
        )
        return
    
    buttons = []
    for user in users:
        buttons.append([
            InlineKeyboardButton(
                text=f"{user['clan_name']} | {user['role']}",
                callback_data=f"nick_select_{user['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    await call.message.edit_text(
        "✏️ **Зміна ніку бійця**\n\nОберіть бійця:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("nick_select_"))
async def select_user_for_nick(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    target_id = int(call.data.split("_")[2])
    target = get_user(target_id)
    
    if not target:
        await call.answer("❌ Користувача не знайдено", show_alert=True)
        return
    
    actions[call.from_user.id] = {
        "type": "change_nick_target",
        "target_id": target_id
    }
    
    await call.message.edit_text(
        f"✏️ **Зміна ніку**\n\n"
        f"Поточний нік: **{target['clan_name']}**\n"
        f"Роль: {target['role']}\n\n"
        f"Введіть новий нік для цього гравця:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# LOGS
# =========================

@dp.callback_query(lambda c: c.data == "logs")
async def logs_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text, created FROM logs ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
    
    text = "📜 **Журнал дій**\n\n"
    if rows:
        for row in rows:
            date = datetime.fromtimestamp(row['created']).strftime("%d.%m %H:%M")
            text += f"▫️ [{date}] {row['text']}\n"
    else:
        text += "Журнал порожній."
    
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="Markdown")

# =========================
# ANNOUNCE
# =========================

@dp.callback_query(lambda c: c.data == "announce")
async def announce(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "announce"}
    await call.message.edit_text(
        "📢 **Оголошення**\n\n"
        "Введіть текст оголошення.\n\n"
        "Воно буде відправлено у ВСІ чати, де є бот!",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# ROLE MANAGEMENT
# =========================

@dp.callback_query(lambda c: c.data == "roles")
async def roles(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, clan_name, role, role_level
            FROM users
            WHERE is_registered=1
            ORDER BY role_level ASC
        """)
        users = cursor.fetchall()
    
    buttons = []
    for user in users:
        if can_manage_roles(call.from_user.id, user['id']):
            buttons.append([
                InlineKeyboardButton(
                    text=f"{user['clan_name']} | {user['role']}",
                    callback_data=f"role_user_{user['id']}"
                )
            ])
    
    if not buttons:
        await call.message.edit_text(
            "❌ Немає користувачів, чиї ролі ви можете змінювати.",
            reply_markup=back_button()
        )
        return
    
    buttons.append([InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel")])
    
    await call.message.edit_text(
        "🎖 **Керування ролями**\n\nОберіть бійця:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("role_user_"))
async def select_role_user(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    target_id = int(call.data.split("_")[2])
    
    if not can_manage_roles(call.from_user.id, target_id):
        await call.answer("❌ Ви не можете змінювати роль цього користувача!", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "change_role", "target": target_id}
    
    admin = get_user(call.from_user.id)
    available_roles = {}
    
    for role, level in ROLES.items():
        if admin['role_level'] == 1:
            available_roles[role] = level
        elif admin['role_level'] == 2 and level > 2:
            available_roles[role] = level
    
    buttons = []
    for role, level in available_roles.items():
        buttons.append([InlineKeyboardButton(text=role, callback_data=f"give_role_{level}")])
    
    buttons.append([InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel")])
    
    await call.message.edit_text(
        "🎖 Оберіть нову роль:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(lambda c: c.data.startswith("give_role_"))
async def give_role(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    level = int(call.data.split("_")[2])
    role = [name for name, lvl in ROLES.items() if lvl == level][0]
    action = actions.get(call.from_user.id)
    
    if not action:
        return
    
    target_id = action["target"]
    
    if not can_manage_roles(call.from_user.id, target_id):
        await call.answer("❌ Ви не можете змінювати роль цього користувача!", show_alert=True)
        return
    
    admin = get_user(call.from_user.id)
    if admin['role_level'] == 2 and level <= 2:
        await call.answer("❌ Радник не може призначати роль Лідера або Радника!", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role=?, role_level=? WHERE id=?", (role, level, target_id))
        conn.commit()
    
    target = get_user(target_id)
    add_log(f"{admin['clan_name']} видав роль {role} бійцю {target['clan_name']}")
    
    actions.pop(call.from_user.id, None)
    
    await call.message.edit_text(
        f"✅ Роль змінено\n\nНова роль: {role}",
        reply_markup=clan_management_menu()
    )

# =========================
# ГОЛОВНИЙ ОБРОБНИК ПОВІДОМЛЕНЬ
# =========================

@dp.message()
async def handle_all_messages(message: Message):
    try:
        # Перевіряємо чи користувач є в БД (але не реєструємо автоматично!)
        user = get_user(message.from_user.id)
        
        # Зберігаємо чат
        save_chat(message.chat.id)
        
        # Зберігаємо повідомлення в історію (тільки якщо користувач зареєстрований)
        if user and user['is_registered'] and message.text:
            save_message(
                message.chat.id,
                message.from_user.id,
                message.from_user.username or str(message.from_user.id),
                user['clan_name'],
                message.text
            )
        elif user and not user['is_registered'] and message.text:
            # Якщо не зареєстрований - зберігаємо з username
            save_message(
                message.chat.id,
                message.from_user.id,
                message.from_user.username or str(message.from_user.id),
                None,
                message.text
            )
        
        # Перевірка на ключове слово "Збір" (тільки для зареєстрованих адмінів)
        if message.text and message.text.lower().strip() == "збір":
            if not user or not user['is_registered']:
                await message.answer("❌ Спочатку зареєструйтесь через /start")
                return
            
            if is_leader_or_advisor(message.from_user.id):
                users = get_all_registered_users()
                phrase = random.choice(GATHER_PHRASES)
                
                text = f"{phrase}\n\n"
                for u in users:
                    text += f"@{u['clan_name']} "
                
                text += f"\n\n🇺🇦 **Всі на зв'язок!**"
                
                await message.answer(text, parse_mode="Markdown")
                add_log(f"{user['clan_name']} оголосив збір")
                return
            else:
                await message.answer("❌ Тільки Лідер або Радник можуть оголошувати збір!")
                return
        
        # Перевірка згадування бота
        bot_mentioned = False
        
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    text = message.text[entity.offset:entity.offset + entity.length]
                    if text.lower() == "@" + (await bot.get_me()).username.lower():
                        bot_mentioned = True
                        break
        
        if message.reply_to_message and message.reply_to_message.from_user.id == (await bot.get_me()).id:
            bot_mentioned = True
        
        if message.text and f"@{ (await bot.get_me()).username}" in message.text:
            bot_mentioned = True
        
        if bot_mentioned:
            await message.reply(random.choice(TAG_REPLIES))
            return
        
        # Обробка дій
        action = actions.get(message.from_user.id)
        if not action:
            return
        
        user_id = message.from_user.id
        text = message.text
        
        # РЕЄСТРАЦІЯ (тільки через /start)
        if action["type"] == "register":
            # Перевіряємо чи нік вже зайнятий
            existing = get_user_by_clan_name(text)
            if existing:
                await message.answer("❌ Цей нік вже зайнятий! Введіть інший:")
                return
            
            update_user_clan_name(user_id, text)
            
            add_log(f"{get_user(user_id)['clan_name']} зареєструвався")
            actions.pop(user_id, None)
            
            msg = await message.answer("✅ Реєстрація завершена!", reply_markup=main_menu(user_id))
            menu_owner[msg.message_id] = user_id
            return
        
        # ЗМІНА НІКУ (через вибір гравця)
        if action["type"] == "change_nick_target":
            if not is_admin(user_id):
                return
            
            target_id = action["target_id"]
            target = get_user(target_id)
            
            if not target:
                await message.answer("❌ Користувача не знайдено.")
                return
            
            # Перевіряємо чи новий нік вже зайнятий
            existing = get_user_by_clan_name(text)
            if existing and existing['id'] != target_id:
                await message.answer("❌ Цей нік вже зайнятий! Введіть інший:")
                return
            
            old_nick = target['clan_name']
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET clan_name=? WHERE id=?", (text, target_id))
                conn.commit()
            
            admin = get_user(user_id)
            add_log(f"{admin['clan_name']} змінив нік {old_nick} на {text}")
            
            actions.pop(user_id, None)
            await message.answer(
                f"✅ Нік змінено!\n\n"
                f"Старий нік: {old_nick}\n"
                f"Новий нік: {text}",
                reply_markup=clan_management_menu()
            )
            return
        
        # ОГОЛОШЕННЯ
        if action["type"] == "announce":
            if not is_admin(user_id):
                return
            
            chats = get_all_chats()
            success = 0
            
            for chat in chats:
                try:
                    await bot.send_message(
                        chat[0],
                        f"📢 **Оголошення від {get_user(user_id)['clan_name']}**\n\n{text}",
                        parse_mode="Markdown"
                    )
                    success += 1
                    await asyncio.sleep(0.1)
                except:
                    pass
            
            admin = get_user(user_id)
            add_log(f"{admin['clan_name']} відправив оголошення в {success} чатів")
            
            actions.pop(user_id, None)
            await message.answer(
                f"✅ Оголошення відправлено в {success} чатів.",
                reply_markup=clan_management_menu()
            )
            return
        
        # СТВОРЕННЯ ПОДІЇ
        if action["type"] == "create_event_title":
            actions[user_id] = {"type": "create_event_description", "title": text}
            await message.answer("📝 Введіть опис події:", reply_markup=cancel_button())
            return
        
        if action["type"] == "create_event_description":
            actions[user_id] = {
                "type": "create_event_date",
                "title": action["title"],
                "description": text
            }
            await message.answer(
                "📅 Введіть дату події\nФормат: `ДД.ММ.РРРР`\nПриклад: `10.07.2026`\n\n"
                "⚠️ Дата не може бути в минулому!",
                parse_mode="Markdown"
            )
            return
        
        if action["type"] == "create_event_date":
            try:
                event_date = datetime.strptime(text, "%d.%m.%Y")
                today = datetime.now()
                if event_date.date() < today.date():
                    await message.answer("❌ Не можна створювати подію в минулому! Введіть правильну дату:")
                    return
            except ValueError:
                await message.answer("❌ Неправильний формат дати! Використовуйте `ДД.ММ.РРРР`", parse_mode="Markdown")
                return
            
            actions[user_id] = {
                "type": "create_event_time",
                "title": action["title"],
                "description": action["description"],
                "event_date": text
            }
            await message.answer(
                "🕒 Введіть час події\nФормат: `ГГ:ХХ`\nПриклад: `19:30`",
                parse_mode="Markdown"
            )
            return
        
        if action["type"] == "create_event_time":
            try:
                event_time = datetime.strptime(text, "%H:%M")
            except ValueError:
                await message.answer("❌ Неправильний формат часу! Використовуйте `ГГ:ХХ`", parse_mode="Markdown")
                return
            
            try:
                event_datetime = datetime.strptime(f"{action['event_date']} {text}", "%d.%m.%Y %H:%M")
                if event_datetime < datetime.now():
                    await message.answer("❌ Не можна створювати подію в минулому! Введіть правильний час:")
                    return
            except:
                pass
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO events(title, description, event_date, event_time, created, creator_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (action["title"], action["description"], action["event_date"], text, int(time.time()), user_id))
                conn.commit()
            
            admin = get_user(user_id)
            add_log(f"{admin['clan_name']} створив подію {action.get('title', 'Без назви')}")
            
            actions.pop(user_id, None)
            await message.answer(
                f"✅ Подію **{action['title']}** створено!\n"
                f"📆 {action['event_date']} 🕒 {text}",
                reply_markup=main_menu(user_id),
                parse_mode="Markdown"
            )
            return
    
    except Exception as e:
        print(f"Помилка: {e}")
        add_log(f"Помилка: {e}")

# =========================
# COMMAND LIST
# =========================

async def setup_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустити бота / реєстрація"),
        BotCommand(command="menu", description="Відкрити меню"),
        BotCommand(command="check", description="Перевірити статус реєстрації")
    ])

# =========================
# EVENT NOTIFICATIONS + ПЕРЕКЛИЧКА
# =========================

async def event_notifications():
    global roll_call_sent
    
    while True:
        try:
            now = int(time.time())
            current_time = datetime.now()
            
            # ПЕРЕКЛИЧКА О 10:00
            if current_time.hour == 10 and current_time.minute == 0 and not roll_call_sent:
                roll_call_sent = True
                
                chats = get_all_chats()
                phrase = random.choice(ROLL_CALL_PHRASES)
                
                for chat in chats:
                    try:
                        await bot.send_message(
                            chat[0],
                            f"🔔 **Перекличка!**\n\n{phrase}\n\n🇺🇦 **Слава Україні!**",
                            parse_mode="Markdown"
                        )
                        await asyncio.sleep(0.1)
                    except:
                        pass
                
                add_log("Проведено ранкову перекличку")
            
            # Скидаємо флаг о 11:00
            if current_time.hour == 11 and current_time.minute == 0:
                roll_call_sent = False
            
            # ПОДІЇ
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, event_date, event_time, remind15, started 
                    FROM events
                    WHERE started = 0
                """)
                events = cursor.fetchall()
            
            for event in events:
                try:
                    event_ts = int(datetime.strptime(
                        f"{event['event_date']} {event['event_time']}",
                        "%d.%m.%Y %H:%M"
                    ).timestamp())
                except:
                    continue
                
                if event['remind15'] == 0 and 0 < event_ts - now <= 900:
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id FROM event_members WHERE event_id=? AND status='joined'", 
                                      (event['id'],))
                        users = cursor.fetchall()
                    
                    for user in users:
                        try:
                            await bot.send_message(
                                user['user_id'],
                                f"⏰ **Нагадування!**\n\n"
                                f"До події **{event['title']}** залишилось 15 хвилин!\n\n"
                                f"Не забудьте прийти! 🏃‍♂️",
                                parse_mode="Markdown"
                            )
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET remind15=1 WHERE id=?", (event['id'],))
                        conn.commit()
                    
                    add_log(f"Відправлено нагадування про подію {event['title']}")
                
                if event['started'] == 0 and now >= event_ts:
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id FROM event_members WHERE event_id=? AND status='joined'", 
                                      (event['id'],))
                        users = cursor.fetchall()
                    
                    for user in users:
                        try:
                            await bot.send_message(
                                user['user_id'],
                                f"🚀 **Подія розпочалась!**\n\n"
                                f"**{event['title']}** стартувала!",
                                parse_mode="Markdown"
                            )
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET started=1 WHERE id=?", (event['id'],))
                        conn.commit()
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM event_members WHERE event_id=?", (event['id'],))
                        cursor.execute("DELETE FROM events WHERE id=?", (event['id'],))
                        conn.commit()
                    
                    add_log(f"Подія {event['title']} завершена та видалена")
            
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Помилка в event_notifications: {e}")
            add_log(f"Помилка в event_notifications: {e}")
            await asyncio.sleep(60)

# =========================
# MAIN
# =========================

async def main():
    print("🤖 BOT STARTING...")
    await setup_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ POLLING STARTED")
    print(f"📊 Всього зареєстровано: {get_registered_count()} користувачів")
    asyncio.create_task(event_notifications())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
