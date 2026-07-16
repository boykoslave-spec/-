import asyncio
import sqlite3
import time
import random
from datetime import datetime, timedelta, timezone
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

# =========================
# ТОКЕН БОТА
# =========================
TOKEN = "8929512025:AAGWYvm3ZyB6v4VJAJq-IgGkNhTBHnnOp7U"

bot = Bot(TOKEN)
dp = Dispatcher()

# =========================
# ЧАСОВИЙ ПОЯС УКРАЇНИ (UTC+3)
# =========================
UKRAINE_TZ = timezone(timedelta(hours=3))

def get_ukraine_time():
    return datetime.now(timezone.utc).astimezone(UKRAINE_TZ)

def get_ukraine_timestamp():
    return int(get_ukraine_time().timestamp())

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
]

GATHER_PHRASES = [
    "🔔 **ЗБІР!** Всі сюди!",
    "⚡️ **ТЕРМІНОВО!** Збір всіх!",
    "🔥 **УВАГА!** Загальний збір!",
    "🎯 **ВСІМ!** Негайно на зв'язок!",
]

TAG_REPLIES = [
    "👋 Я тут!",
    "🫡 Що треба?",
    "😊 Слухаю!",
    "🙋‍♂️ Я на місці!",
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

def get_user(user_id):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return cursor.fetchone()

def get_user_by_clan_name(clan_name):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE clan_name=? AND is_registered=1", (clan_name,))
        return cursor.fetchone()

def is_registered(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return user['is_registered'] == 1

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

def status_icon(last):
    diff = get_ukraine_timestamp() - last
    if diff < 300:
        return "🟢"
    if diff < 86400:
        return "🟡"
    return "🔴"

def add_log(text):
    try:
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs(text, created) VALUES (?, ?)", (text, get_ukraine_timestamp()))
            conn.commit()
    except:
        pass

def get_all_registered_users():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, clan_name FROM users WHERE is_registered=1")
        return cursor.fetchall()

def get_all_users_for_nick_change():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, clan_name, role FROM users WHERE is_registered=1 ORDER BY clan_name ASC")
        return cursor.fetchall()

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
        """, (chat_id, user_id, username, clan_name, message_text, get_ukraine_timestamp()))
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

def get_registered_count():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_registered=1")
        return cursor.fetchone()[0]

def check_menu_owner(call: CallbackQuery):
    owner = menu_owner.get(call.message.message_id)
    if owner and owner != call.from_user.id:
        return False
    return True

def register_new_user(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            role = "⚔️ Солдат"
            level = 7
            if username and username in DEFAULT_ADMINS:
                role, level = DEFAULT_ADMINS[username]
            
            cursor.execute("""
                INSERT INTO users(id, username, clan_name, role, role_level, last_online, registered_at, chat_id, is_registered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, None, role, level, get_ukraine_timestamp(), get_ukraine_timestamp(), 0, 0))
            conn.commit()
            return False
        
        cursor.execute("UPDATE users SET last_online=?, username=? WHERE id=?", (get_ukraine_timestamp(), username, user_id))
        conn.commit()
        return True

def complete_registration(user_id, clan_name):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET clan_name=?, is_registered=1, registered_at=?
            WHERE id=?
        """, (clan_name, get_ukraine_timestamp(), user_id))
        conn.commit()

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
        [InlineKeyboardButton(text="📨 Історія чату", callback_data="chat_history")],
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
    user_id = message.from_user.id
    
    if is_registered(user_id):
        save_chat(message.chat.id)
        msg = await message.answer("🛡️ **Головне меню**", reply_markup=main_menu(user_id), parse_mode="Markdown")
        menu_owner[msg.message_id] = user_id
        return
    
    register_new_user(message)
    save_chat(message.chat.id)
    
    if user_id in actions:
        del actions[user_id]
    
    actions[user_id] = {"type": "register"}
    await message.answer(
        "🛡️ **Вас вітає ЗСУ 🇺🇦**\n\n"
        "Введіть свій клановий нік для реєстрації:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def menu_command(message: Message):
    user_id = message.from_user.id
    
    if not is_registered(user_id):
        await message.answer("❌ Спочатку зареєструйтесь через /start")
        return
    
    msg = await message.answer("🛡️ **Головне меню**", reply_markup=main_menu(user_id), parse_mode="Markdown")
    menu_owner[msg.message_id] = user_id

@dp.message(Command("check"))
async def check_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Ви не зареєстровані. Напишіть /start")
        return
    
    if user['is_registered']:
        reg_date = datetime.fromtimestamp(user['registered_at']).strftime('%d.%m.%Y %H:%M')
        await message.answer(
            f"✅ **Ви зареєстровані!**\n\n"
            f"🏷 Нік: {user['clan_name']}\n"
            f"👑 Роль: {user['role']}\n"
            f"📅 Зареєстровано: {reg_date}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "⚠️ Ви почали реєстрацію, але ще не вказали клановий нік!\nНапишіть /start",
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
    
    user_id = call.from_user.id
    if not is_registered(user_id):
        await call.answer("❌ Ви не зареєстровані!", show_alert=True)
        return
    
    chats = get_all_chats()
    
    if not chats:
        await call.message.edit_text(
            "📨 **Історія чату**\n\nНемає збережених чатів.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
        return
    
    buttons = []
    for chat in chats[:10]:
        buttons.append([
            InlineKeyboardButton(
                text=f"💬 Чат {chat[0]}",
                callback_data=f"history_chat_{chat[0]}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    await call.message.edit_text(
        "📨 **Історія чату**\n\nОберіть чат:",
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
            "📨 **Історія чату**\n\nНемає повідомлень.",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
        return
    
    text = "📨 **Історія чату**\n\n"
    for msg in reversed(messages):
        clan = msg['clan_name'] or msg['username'] or "Невідомий"
        time_str = datetime.fromtimestamp(msg['created']).strftime("%H:%M")
        text += f"`{time_str}` **{clan}:** {msg['message_text']}\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (обрізано)"
    
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="Markdown")

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
    except:
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
    await call.message.edit_text("🙈 Меню приховано.\n\n/menu щоб відкрити.")

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
        text += f"▫️ {user['clan_name']} {status_icon(user['last_online'])}\n"
    
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
    
    user_id = call.from_user.id
    
    if not is_registered(user_id):
        await call.answer("❌ Ви не зареєстровані! /start", show_alert=True)
        return
    
    user = get_user(user_id)
    reg_date = datetime.fromtimestamp(user['registered_at']).strftime('%d.%m.%Y %H:%M')
    
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
# EVENTS (скорочено)
# =========================

@dp.callback_query(lambda c: c.data == "events")
async def events_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_registered(call.from_user.id):
        await call.answer("❌ Ви не зареєстровані!", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, event_date, event_time
            FROM events WHERE started=0
            ORDER BY event_date || ' ' || event_time ASC LIMIT 10
        """)
        events = cursor.fetchall()
    
    buttons = []
    if is_admin(call.from_user.id):
        buttons.append([InlineKeyboardButton(text="➕ Створити", callback_data="create_event")])
    
    for event in events:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {event['title']}",
            callback_data=f"event_{event['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    text = "📅 **Події клану**\n\n"
    if not events:
        text += "Немає подій."
    else:
        for event in events:
            text += f"▫️ **{event['title']}** — {event['event_date']} {event['event_time']}\n"
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# =========================
# ГОЛОВНИЙ ОБРОБНИК ПОВІДОМЛЕНЬ (ШВИДКИЙ)
# =========================

@dp.message()
async def handle_all_messages(message: Message):
    try:
        user_id = message.from_user.id
        user = get_user(user_id)
        
        save_chat(message.chat.id)
        
        # Якщо зареєстрований - зберігаємо повідомлення
        if user and user['is_registered'] and message.text:
            save_message(
                message.chat.id,
                user_id,
                message.from_user.username or str(user_id),
                user['clan_name'],
                message.text
            )
        
        # "Збір"
        if message.text and message.text.lower().strip() == "збір":
            if not user or not user['is_registered']:
                await message.answer("❌ Спочатку /start")
                return
            
            if is_leader_or_advisor(user_id):
                users = get_all_registered_users()
                if not users:
                    await message.answer("❌ Немає користувачів")
                    return
                
                text = random.choice(GATHER_PHRASES) + "\n\n"
                for u in users:
                    text += f"@{u['clan_name']} "
                text += "\n\n🇺🇦 **Всі на зв'язок!**"
                
                await message.answer(text, parse_mode="Markdown")
                add_log(f"{user['clan_name']} оголосив збір")
                return
            else:
                await message.answer("❌ Тільки Лідер або Радник!")
                return
        
        # Згадування бота
        bot_mentioned = False
        
        if message.entities and message.text:
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
        
        # Якщо не зареєстрований - пропонуємо реєстрацію
        if user and not user['is_registered'] and message.text:
            if user_id not in actions:
                actions[user_id] = {"type": "register"}
                await message.answer(
                    "🛡️ **Вас вітає ЗСУ 🇺🇦**\n\n"
                    "Ви ще не зареєстровані!\n"
                    "Введіть свій клановий нік:",
                    reply_markup=cancel_button(),
                    parse_mode="Markdown"
                )
            return
        
        # Обробка дій
        action = actions.get(user_id)
        if not action:
            return
        
        text = message.text
        
        # РЕЄСТРАЦІЯ
        if action["type"] == "register":
            existing = get_user_by_clan_name(text)
            if existing:
                await message.answer("❌ Цей нік вже зайнятий! Введіть інший:")
                return
            
            complete_registration(user_id, text)
            add_log(f"{get_user(user_id)['clan_name']} зареєструвався")
            actions.pop(user_id, None)
            
            msg = await message.answer("✅ Реєстрація завершена!", reply_markup=main_menu(user_id))
            menu_owner[msg.message_id] = user_id
            return
        
        # ЗМІНА НІКУ
        if action["type"] == "change_nick_target":
            if not is_admin(user_id):
                actions.pop(user_id, None)
                return
            
            target_id = action["target_id"]
            target = get_user(target_id)
            
            if not target:
                await message.answer("❌ Користувача не знайдено.")
                actions.pop(user_id, None)
                return
            
            existing = get_user_by_clan_name(text)
            if existing and existing['id'] != target_id:
                await message.answer("❌ Цей нік вже зайнятий! Введіть інший:")
                return
            
            old_nick = target['clan_name']
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET clan_name=? WHERE id=?", (text, target_id))
                conn.commit()
            
            add_log(f"{get_user(user_id)['clan_name']} змінив нік {old_nick} на {text}")
            actions.pop(user_id, None)
            await message.answer(f"✅ Нік змінено!\n{old_nick} → {text}", reply_markup=clan_management_menu())
            return
        
        # ОГОЛОШЕННЯ
        if action["type"] == "announce":
            if not is_admin(user_id):
                actions.pop(user_id, None)
                return
            
            chats = get_all_chats()
            success = 0
            
            for chat in chats:
                try:
                    await bot.send_message(chat[0], f"📢 **Оголошення**\n\n{text}", parse_mode="Markdown")
                    success += 1
                    await asyncio.sleep(0.1)
                except:
                    pass
            
            add_log(f"{get_user(user_id)['clan_name']} відправив оголошення в {success} чатів")
            actions.pop(user_id, None)
            await message.answer(f"✅ Оголошення відправлено в {success} чатів.", reply_markup=clan_management_menu())
            return
        
        # СТВОРЕННЯ ПОДІЇ
        if action["type"] == "create_event_title":
            actions[user_id] = {"type": "create_event_description", "title": text}
            await message.answer("📝 Опис події:", reply_markup=cancel_button())
            return
        
        if action["type"] == "create_event_description":
            actions[user_id] = {
                "type": "create_event_date",
                "title": action["title"],
                "description": text
            }
            await message.answer("📅 Дата (ДД.ММ.РРРР):", reply_markup=cancel_button())
            return
        
        if action["type"] == "create_event_date":
            try:
                datetime.strptime(text, "%d.%m.%Y")
            except:
                await message.answer("❌ Неправильний формат! ДД.ММ.РРРР")
                return
            
            actions[user_id] = {
                "type": "create_event_time",
                "title": action["title"],
                "description": action["description"],
                "event_date": text
            }
            await message.answer("🕒 Час (ГГ:ХХ):", reply_markup=cancel_button())
            return
        
        if action["type"] == "create_event_time":
            try:
                datetime.strptime(text, "%H:%M")
            except:
                await message.answer("❌ Неправильний формат! ГГ:ХХ")
                return
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO events(title, description, event_date, event_time, created, creator_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (action["title"], action["description"], action["event_date"], text, get_ukraine_timestamp(), user_id))
                conn.commit()
            
            add_log(f"{get_user(user_id)['clan_name']} створив подію {action['title']}")
            actions.pop(user_id, None)
            await message.answer(
                f"✅ Подію **{action['title']}** створено!\n📆 {action['event_date']} 🕒 {text}",
                reply_markup=main_menu(user_id),
                parse_mode="Markdown"
            )
            return
    
    except Exception as e:
        print(f"Помилка: {e}")
        add_log(f"Помилка: {e}")

# =========================
# ОБРОБНИКИ ЗМІНИ НІКУ ТА РОЛЕЙ (СКОРОЧЕНО)
# =========================

@dp.callback_query(lambda c: c.data == "change_nick")
async def change_nick_menu(call: CallbackQuery):
    if not check_menu_owner(call) or not is_admin(call.from_user.id):
        return
    
    users = get_all_users_for_nick_change()
    if not users:
        await call.message.edit_text("❌ Немає користувачів.", reply_markup=back_button())
        return
    
    buttons = []
    for user in users:
        buttons.append([InlineKeyboardButton(
            text=f"{user['clan_name']} | {user['role']}",
            callback_data=f"nick_select_{user['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    await call.message.edit_text(
        "✏️ **Зміна ніку**\n\nОберіть бійця:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("nick_select_"))
async def select_user_for_nick(call: CallbackQuery):
    if not check_menu_owner(call) or not is_admin(call.from_user.id):
        return
    
    target_id = int(call.data.split("_")[2])
    target = get_user(target_id)
    
    if not target:
        await call.answer("❌ Користувача не знайдено", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "change_nick_target", "target_id": target_id}
    await call.message.edit_text(
        f"✏️ **Зміна ніку**\n\nПоточний нік: **{target['clan_name']}**\n\nВведіть новий нік:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# LOGS
# =========================

@dp.callback_query(lambda c: c.data == "logs")
async def logs_menu(call: CallbackQuery):
    if not check_menu_owner(call) or not is_admin(call.from_user.id):
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text, created FROM logs ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
    
    text = "📜 **Журнал**\n\n"
    if rows:
        for row in rows:
            date = datetime.fromtimestamp(row['created']).strftime("%d.%m %H:%M")
            text += f"▫️ [{date}] {row['text']}\n"
    else:
        text += "Порожній."
    
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="Markdown")

# =========================
# ANNOUNCE
# =========================

@dp.callback_query(lambda c: c.data == "announce")
async def announce(call: CallbackQuery):
    if not check_menu_owner(call) or not is_admin(call.from_user.id):
        return
    
    actions[call.from_user.id] = {"type": "announce"}
    await call.message.edit_text(
        "📢 **Оголошення**\n\nВведіть текст:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# ROLES
# =========================

@dp.callback_query(lambda c: c.data == "roles")
async def roles(call: CallbackQuery):
    if not check_menu_owner(call) or not is_admin(call.from_user.id):
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, clan_name, role FROM users WHERE is_registered=1 ORDER BY role_level ASC")
        users = cursor.fetchall()
    
    buttons = []
    for user in users:
        buttons.append([InlineKeyboardButton(
            text=f"{user['clan_name']} | {user['role']}",
            callback_data=f"role_user_{user['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel")])
    
    await call.message.edit_text(
        "🎖 **Керування ролями**\n\nОберіть бійця:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data.startswith("role_user_"))
async def select_role_user(call: CallbackQuery):
    if not check_menu_owner(call) or not is_admin(call.from_user.id):
        return
    
    target_id = int(call.data.split("_")[2])
    actions[call.from_user.id] = {"type": "change_role", "target": target_id}
    
    buttons = []
    for role, level in ROLES.items():
        buttons.append([InlineKeyboardButton(text=role, callback_data=f"give_role_{level}")])
    buttons.append([InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel")])
    
    await call.message.edit_text(
        "🎖 Оберіть роль:",
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
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role=?, role_level=? WHERE id=?", (role, level, target_id))
        conn.commit()
    
    add_log(f"{get_user(call.from_user.id)['clan_name']} видав роль {role}")
    actions.pop(call.from_user.id, None)
    await call.message.edit_text(f"✅ Роль змінено\n\nНова роль: {role}", reply_markup=clan_management_menu())

# =========================
# EVENT NOTIFICATIONS + ПЕРЕКЛИЧКА
# =========================

async def event_notifications():
    global roll_call_sent
    
    while True:
        try:
            now = get_ukraine_timestamp()
            current_time = get_ukraine_time()
            
            if current_time.hour == 10 and current_time.minute == 0 and not roll_call_sent:
                roll_call_sent = True
                chats = get_all_chats()
                phrase = random.choice(ROLL_CALL_PHRASES)
                
                for chat in chats:
                    try:
                        await bot.send_message(chat[0], f"🔔 **Перекличка!**\n\n{phrase}\n\n🇺🇦 **Слава Україні!**", parse_mode="Markdown")
                        await asyncio.sleep(0.1)
                    except:
                        pass
                
                add_log("Проведено перекличку")
            
            if current_time.hour == 11 and current_time.minute == 0:
                roll_call_sent = False
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, event_date, event_time, remind15, started FROM events WHERE started=0")
                events = cursor.fetchall()
            
            for event in events:
                try:
                    event_ts = int(datetime.strptime(f"{event['event_date']} {event['event_time']}", "%d.%m.%Y %H:%M").timestamp())
                except:
                    continue
                
                if event['remind15'] == 0 and 0 < event_ts - now <= 900:
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id FROM event_members WHERE event_id=? AND status='joined'", (event['id'],))
                        users = cursor.fetchall()
                    
                    for user in users:
                        try:
                            await bot.send_message(user['user_id'], f"⏰ **Нагадування!**\n\nДо події **{event['title']}** залишилось 15 хвилин!", parse_mode="Markdown")
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET remind15=1 WHERE id=?", (event['id'],))
                        conn.commit()
                
                if event['started'] == 0 and now >= event_ts:
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_id FROM event_members WHERE event_id=? AND status='joined'", (event['id'],))
                        users = cursor.fetchall()
                    
                    for user in users:
                        try:
                            await bot.send_message(user['user_id'], f"🚀 **Подія розпочалась!**\n\n**{event['title']}** стартувала!", parse_mode="Markdown")
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET started=1 WHERE id=?", (event['id'],))
                        cursor.execute("DELETE FROM event_members WHERE event_id=?", (event['id'],))
                        cursor.execute("DELETE FROM events WHERE id=?", (event['id'],))
                        conn.commit()
                    
                    add_log(f"Подія {event['title']} завершена")
            
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Помилка: {e}")
            await asyncio.sleep(60)

# =========================
# COMMAND LIST
# =========================

async def setup_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустити бота / реєстрація"),
        BotCommand(command="menu", description="Відкрити меню"),
        BotCommand(command="check", description="Перевірити статус")
    ])

# =========================
# MAIN
# =========================

async def main():
    print("🤖 BOT STARTING...")
    
    # ПРИМУСОВЕ СКИДАННЯ ВСІХ З'ЄДНАНЬ
    for i in range(3):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print(f"✅ Webhook видалено (спроба {i+1})")
            break
        except Exception as e:
            print(f"⚠️ Спроба {i+1}: {e}")
            await asyncio.sleep(1)
    
    # ЧЕКАЄМО ПОКИ ВСІ З'ЄДНАННЯ ЗАКРИЮТЬСЯ
    await asyncio.sleep(2)
    
    await setup_commands()
    print("✅ POLLING STARTED")
    print(f"📊 Зареєстровано: {get_registered_count()} користувачів")
    
    asyncio.create_task(event_notifications())
    
    # ЗАПУСК З ПЕРЕЗАПУСКОМ ПРИ ПОМИЛЦІ
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print(f"❌ Помилка: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
