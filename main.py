import asyncio
import os
import sqlite3
import time
import random
import io
from datetime import datetime
from contextlib import contextmanager
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
    BotCommand,
    FSInputFile,
    InputFile
)
from aiogram.exceptions import TelegramBadRequest

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдений")

bot = Bot(TOKEN)
dp = Dispatcher()

# =========================
# THREAD-SAFE DATABASE
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
                points INTEGER DEFAULT 0,
                events_visited INTEGER DEFAULT 0,
                coins_received INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_streak_date INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0
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
                remind1 INTEGER DEFAULT 0,
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
            CREATE TABLE IF NOT EXISTS exchange_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                points INTEGER,
                coins INTEGER,
                created INTEGER,
                status TEXT DEFAULT 'pending'
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS clan_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT,
                file_id TEXT,
                uploaded_by INTEGER
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

POINT_PRICE = 100
STREAK_BONUS = 10

DEFAULT_ADMINS = {
    "Jordana_SWAT": ("👑 Лідер", 1),
    "Wtfmnnnn": ("🛡 Радник", 2)
}

# =========================
# КУМЕДНІ ФРАЗИ
# =========================
FUNNY_REPLIES = [
    "Сходи нахуй 🖕😏",
    "Тебе вєбать! 💀🔥",
    "Разом ми сила! 💪🇺🇦",
    "Пішов нафіг, клоуне! 🤡",
    "Ти хто такий? 🤔",
    "Ну ти й жартівник! 😂",
    "Ану вгатив! 🤛",
    "Моя хата з краю, нічого не знаю 🏠",
    "Я з тебе сміюся! 😆",
    "Якби ж ти ще щось вмів, окрім тегів... 🥲",
    "Не засмучуй мене, бо я заплачу... зі сміху! 🤣",
    "Ви всі тут просто цирк, а я ведучий! 🎪",
    "Де ти взяв цей нік? У магазині клоунів? 🛒",
    "Ого, зірка! А де тобі медальку повісити? 🏅",
    "Ти як котлета - всіх дратуєш, але без тебе скучно! 🥩"
]

CASINO_GAMES = [
    "🎰 Орлянка", "🎲 Кістки", "🃏 Карти"
]

# =========================
# ACTIVE USER ACTIONS
# =========================
actions = {}
menu_owner = {}
active_games = {}

# =========================
# DATABASE FUNCTIONS
# =========================

def register_user(message: Message):
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
                INSERT INTO users(id, username, clan_name, role, role_level, last_online, 
                                 points, events_visited, coins_received, streak, last_streak_date, wins, losses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, None, role, level, int(time.time()), 0, 0, 0, 0, 0, 0, 0))
        
        cursor.execute("UPDATE users SET last_online=? WHERE id=?", (int(time.time()), user_id))
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

def is_leader(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return user['role_level'] == 1

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
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO logs(text, created) VALUES (?, ?)", (text, int(time.time())))
        conn.commit()

def add_points(user_id, amount):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE id = ?", (amount, user_id))
        conn.commit()

def remove_points(user_id, amount):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points - ? WHERE id = ?", (amount, user_id))
        conn.commit()

def add_coins(user_id, amount):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins_received = coins_received + ? WHERE id = ?", (amount, user_id))
        conn.commit()

def remove_coins(user_id, amount):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins_received = coins_received - ? WHERE id = ?", (amount, user_id))
        conn.commit()

def add_event_visit(user_id):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET events_visited = events_visited + 1 WHERE id = ?", (user_id,))
        conn.commit()

def check_streak(user_id):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_streak_date, streak FROM users WHERE id=?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return 0
        
        last_date, streak = result
        today = int(time.time()) // 86400
        
        if last_date == today - 1:
            streak += 1
        elif last_date < today - 1:
            streak = 0
        
        cursor.execute("UPDATE users SET streak=?, last_streak_date=? WHERE id=?", 
                      (streak, today, user_id))
        conn.commit()
        
        if streak > 0 and streak % 7 == 0:
            bonus = STREAK_BONUS * (streak // 7)
            add_points(user_id, bonus)
            return streak, bonus
        
        return streak, 0

def get_top_users(limit=10):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT clan_name, points, role
            FROM users
            WHERE clan_name IS NOT NULL
            ORDER BY points DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def check_menu_owner(call: CallbackQuery):
    owner = menu_owner.get(call.message.message_id)
    if owner and owner != call.from_user.id:
        return False
    return True

def get_user_by_clan_name(clan_name):
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE clan_name=?", (clan_name,))
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

# =========================
# KEYBOARDS
# =========================

def main_menu(user_id):
    keyboard = []
    
    # Кнопки для всіх
    keyboard.extend([
        [InlineKeyboardButton(text="🪖 Особовий склад", callback_data="staff")],
        [InlineKeyboardButton(text="📅 Події", callback_data="events")],
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile")],
        [InlineKeyboardButton(text="🎰 Казино", callback_data="casino")]
    ])
    
    # Кнопки для Лідера/Радника
    if is_leader_or_advisor(user_id):
        keyboard.extend([
            [InlineKeyboardButton(text="⚙️ Управління кланом", callback_data="clan_management")]
        ])
    
    keyboard.extend([
        [InlineKeyboardButton(text="🙈 Сховати меню", callback_data="hide_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def clan_management_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎖 Керування ролями", callback_data="roles")],
        [InlineKeyboardButton(text="💰 Видача балів", callback_data="give_points")],
        [InlineKeyboardButton(text="🪙 Видача монет", callback_data="give_coins")],
        [InlineKeyboardButton(text="💱 Обмін балів на монети", callback_data="exchange")],
        [InlineKeyboardButton(text="💰 Списання монет", callback_data="remove_coins")],
        [InlineKeyboardButton(text="✏️ Змінити нік бійця", callback_data="change_nick")],
        [InlineKeyboardButton(text="📜 Журнал", callback_data="logs")],
        [InlineKeyboardButton(text="📢 Оголошення", callback_data="announce")],
        [InlineKeyboardButton(text="📸 Фото клану", callback_data="clan_photos")],
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

def events_menu_keyboard(events, user_id):
    buttons = []
    
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton(text="➕ Створити подію", callback_data="create_event")])
    
    for event in events:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {event['title']}",
            callback_data=f"event_{event['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def event_detail_keyboard(event_id, user_id, is_admin_flag=False):
    buttons = []
    
    buttons.append([InlineKeyboardButton(text="✅ Я буду", callback_data=f"join_{event_id}")])
    buttons.append([InlineKeyboardButton(text="👥 Учасники", callback_data=f"members_{event_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Не буду", callback_data=f"leave_{event_id}")])
    
    if is_admin_flag:
        buttons.append([InlineKeyboardButton(text="🗑 Видалити подію", callback_data=f"delete_event_{event_id}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="events")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# =========================
# START & MENU
# =========================

@dp.message(Command("start"))
async def start(message: Message):
    register_user(message)
    await message.answer("Оновлення меню...", reply_markup=ReplyKeyboardRemove())
    
    user = get_user(message.from_user.id)
    
    if not user['clan_name']:
        actions[message.from_user.id] = {"type": "register"}
        await message.answer(
            "🛡️ Вас вітає ЗСУ 🇺🇦\n\nВведіть свій клановий нік:",
            reply_markup=cancel_button()
        )
        return
    
    msg = await message.answer("🛡️ Головне меню", reply_markup=main_menu(message.from_user.id))
    menu_owner[msg.message_id] = message.from_user.id

@dp.message(Command("menu"))
async def menu_command(message: Message):
    register_user(message)
    msg = await message.answer("🛡️ Головне меню", reply_markup=main_menu(message.from_user.id))
    menu_owner[msg.message_id] = message.from_user.id

@dp.message(Command("top"))
async def top_command(message: Message):
    register_user(message)
    users = get_top_users(10)
    
    if not users:
        await message.answer("📊 Топ поки що порожній.")
        return
    
    text = "🏆 Топ гравців за балами:\n\n"
    for i, user in enumerate(users, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {user['clan_name']} - {user['points']} балів ({user['role']})\n"
    
    await message.answer(text)

# =========================
# BACK, CANCEL, HIDE
# =========================

@dp.callback_query(lambda c: c.data == "back")
async def back(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    try:
        await call.message.edit_text("🛡️ Головне меню", reply_markup=main_menu(call.from_user.id))
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
        "⚙️ Управління кланом\n\n"
        "Оберіть дію:",
        reply_markup=clan_management_menu()
    )

# =========================
# STAFF LIST (красивий)
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
            WHERE clan_name IS NOT NULL
            ORDER BY role_level ASC, clan_name ASC
        """)
        users = cursor.fetchall()
    
    # Красиве форматування
    text = "🪖 **Особовий склад клану**\n\n"
    current_role = None
    
    for user in users:
        if current_role != user['role']:
            current_role = user['role']
            text += f"\n**{current_role}**\n"
            text += "─" * 20 + "\n"
        text += f"▫️ {user['clan_name']} {status_icon(user['last_online'])}\n"
    
    await call.message.edit_text(text, reply_markup=back_button(), parse_mode="Markdown")

# =========================
# PROFILE
# =========================

@dp.callback_query(lambda c: c.data == "profile")
async def profile(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    register_user(call.message)
    user = get_user(call.from_user.id)
    
    streak_result = check_streak(call.from_user.id)
    if isinstance(streak_result, tuple):
        streak, bonus = streak_result
        if bonus > 0:
            await call.message.answer(f"🔥 Стрік {streak} днів! Отримано бонус: {bonus} балів!")
    else:
        streak = streak_result
    
    await call.message.edit_text(
        f"👤 **Профіль**\n\n"
        f"┌─────────────────\n"
        f"│ 🏷 Нік: {user['clan_name']}\n"
        f"│ 👑 Роль: {user['role']}\n"
        f"│ 🪙 Бали: {user['points']}\n"
        f"│ 💰 Монети: {user['coins_received']}\n"
        f"│ 🏆 Подій: {user['events_visited']}\n"
        f"│ 🔥 Стрік: {streak} днів\n"
        f"│ 🎮 Перемог: {user['wins']}\n"
        f"│ 💀 Поразок: {user['losses']}\n"
        f"│ 📊 Статус: {status_icon(user['last_online'])}\n"
        f"└─────────────────",
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

# =========================
# EVENTS (доступні всім)
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
    
    if not events:
        text = "📅 **Події клану**\n\nНемає запланованих подій."
        if is_admin(call.from_user.id):
            text += "\n\nНатисніть ➕ Створити подію"
        
        buttons = []
        if is_admin(call.from_user.id):
            buttons.append([InlineKeyboardButton(text="➕ Створити подію", callback_data="create_event")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
        
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
        return
    
    text = "📅 **Події клану**\n\n"
    for event in events:
        text += f"▫️ {event['title']}\n"
        text += f"   📆 {event['event_date']} 🕒 {event['event_time']}\n"
        text += f"   📝 {event['description'][:30]}{'...' if len(event['description']) > 30 else ''}\n\n"
    
    await call.message.edit_text(
        text,
        reply_markup=events_menu_keyboard(events, call.from_user.id),
        parse_mode="Markdown"
    )

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
    
    is_admin_flag = is_admin(call.from_user.id)
    
    await call.message.edit_text(
        text,
        reply_markup=event_detail_keyboard(event_id, call.from_user.id, is_admin_flag),
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
    await call.message.edit_text("📅 Введіть назву події:", reply_markup=cancel_button())

# =========================
# GIVE POINTS (тільки Лідер/Радник)
# =========================

@dp.callback_query(lambda c: c.data == "give_points")
async def give_points_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "give_points"}
    await call.message.edit_text(
        "💰 **Видача балів**\n\n"
        "Введіть у форматі:\n"
        "`нік_гравця кількість_балів`\n\n"
        "Приклад: `Jordana_SWAT 100`",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# GIVE COINS (тільки Лідер/Радник)
# =========================

@dp.callback_query(lambda c: c.data == "give_coins")
async def give_coins_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "give_coins"}
    await call.message.edit_text(
        "🪙 **Видача монет**\n\n"
        "Введіть у форматі:\n"
        "`нік_гравця кількість_монет`\n\n"
        "Приклад: `Jordana_SWAT 5`",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# EXCHANGE
# =========================

@dp.callback_query(lambda c: c.data == "exchange")
async def exchange_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Тільки Лідер або Радник", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    
    await call.message.edit_text(
        f"💱 **Обмін балів на монети**\n\n"
        f"Ваші бали: {user['points']}\n"
        f"Курс: {POINT_PRICE} балів = 1 монета\n\n"
        f"Введіть кількість балів для обміну:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )
    
    actions[call.from_user.id] = {"type": "exchange_points"}

# =========================
# REMOVE COINS
# =========================

@dp.callback_query(lambda c: c.data == "remove_coins")
async def remove_coins_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "remove_coins"}
    await call.message.edit_text(
        "💰 **Списання монет**\n\n"
        "Введіть у форматі:\n"
        "`нік_гравця кількість_монет`\n\n"
        "Приклад: `Jordana_SWAT 3`",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# CHANGE NICK
# =========================

@dp.callback_query(lambda c: c.data == "change_nick")
async def change_nick(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "change_nick"}
    await call.message.edit_text(
        "✏️ **Зміна ніку бійця**\n\n"
        "Введіть у форматі:\n"
        "`старий_нік новий_нік`\n\n"
        "Приклад: `Jordana_SWAT NewNick`",
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
        "📢 **Оголошення**\n\nВведіть текст оголошення:",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )

# =========================
# CLAN PHOTOS
# =========================

@dp.callback_query(lambda c: c.data == "clan_photos")
async def clan_photos_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    await call.message.edit_text(
        "📸 **Фото клану**\n\n"
        "Надішліть мені фото, і воно збережеться в галерею клану.",
        reply_markup=back_button()
    )
    
    actions[call.from_user.id] = {"type": "upload_photo"}

# =========================
# CASINO (Міні-гра)
# =========================

@dp.callback_query(lambda c: c.data == "casino")
async def casino_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    user = get_user(call.from_user.id)
    
    await call.message.edit_text(
        "🎰 **Казино**\n\n"
        f"💰 Ваші монети: {user['coins_received']}\n\n"
        "Оберіть гру:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Кістки (2 монети)", callback_data="game_dice")],
            [InlineKeyboardButton(text="🪙 Орлянка (1 монета)", callback_data="game_coin")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("game_"))
async def play_game(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    game = call.data.split("_")[1]
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if game == "dice":
        cost = 2
        if user['coins_received'] < cost:
            await call.answer(f"❌ Недостатньо монет! Потрібно: {cost}", show_alert=True)
            return
        
        # Гра в кістки
        player = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        
        remove_coins(user_id, cost)
        
        if player > bot_roll:
            win = cost * 2
            add_coins(user_id, win)
            add_points(user_id, 5)
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"🎉 Ви виграли!\nВаш кидок: {player} 🤖 Бот: {bot_roll}\n+{win} монет! +5 балів!"
        elif player < bot_roll:
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"😢 Ви програли!\nВаш кидок: {player} 🤖 Бот: {bot_roll}\n-{cost} монет."
        else:
            add_coins(user_id, cost)
            result = f"🤝 Нічия!\nВаш кидок: {player} 🤖 Бот: {bot_roll}\nПовернуто {cost} монет."
    
    elif game == "coin":
        cost = 1
        if user['coins_received'] < cost:
            await call.answer(f"❌ Недостатньо монет! Потрібно: {cost}", show_alert=True)
            return
        
        remove_coins(user_id, cost)
        
        choices = ["Орел", "Решка"]
        player_choice = random.choice(choices)
        bot_choice = random.choice(choices)
        
        if player_choice == bot_choice:
            win = cost * 2
            add_coins(user_id, win)
            add_points(user_id, 3)
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"🎉 Ви виграли!\nВи: {player_choice} 🤖 Бот: {bot_choice}\n+{win} монет! +3 бали!"
        else:
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"😢 Ви програли!\nВи: {player_choice} 🤖 Бот: {bot_choice}\n-{cost} монет."
    
    else:
        return
    
    user = get_user(user_id)
    result += f"\n\n💰 Баланс: {user['coins_received']} монет"
    
    await call.message.edit_text(
        result,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Грати ще", callback_data=f"game_{game}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="casino")]
        ])
    )

# =========================
# ROLE MANAGEMENT (з захистом)
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
            WHERE clan_name IS NOT NULL
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
# TEXT HANDLER (всі команди)
# =========================

@dp.message()
async def handle_all_messages(message: Message):
    # Перевіряємо згадування бота
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
        reply = random.choice(FUNNY_REPLIES)
        if message.reply_to_message:
            await message.reply(reply)
        else:
            await message.answer(reply)
        return
    
    # Обробка фото
    if message.photo:
        action = actions.get(message.from_user.id)
        if action and action.get("type") == "upload_photo":
            if not is_leader_or_advisor(message.from_user.id):
                await message.answer("❌ Немає доступу")
                return
            
            file_id = message.photo[-1].file_id
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO clan_photos(section, file_id, uploaded_by) VALUES (?, ?, ?)",
                              ("clan_gallery", file_id, message.from_user.id))
                conn.commit()
            
            add_log(f"{get_user(message.from_user.id)['clan_name']} завантажив фото")
            await message.answer("✅ Фото збережено в галерею клану!", reply_markup=main_menu(message.from_user.id))
            actions.pop(message.from_user.id, None)
            return
    
    # Обробка текстових команд
    register_user(message)
    action = actions.get(message.from_user.id)
    
    if not action:
        return
    
    user_id = message.from_user.id
    text = message.text
    
    # Реєстрація
    if action["type"] == "register":
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET clan_name=? WHERE id=?", (text, user_id))
            conn.commit()
        
        add_log(f"{get_user(user_id)['clan_name']} зареєструвався")
        actions.pop(user_id, None)
        
        msg = await message.answer("✅ Реєстрація завершена!", reply_markup=main_menu(user_id))
        menu_owner[msg.message_id] = user_id
        return
    
    # Зміна ніку
    if action["type"] == "change_nick":
        if not is_admin(user_id):
            return
        
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: `старий_нік новий_нік`", parse_mode="Markdown")
            return
        
        old_nick, new_nick = parts
        target = get_user_by_clan_name(old_nick)
        
        if not target:
            await message.answer(f"❌ Користувача з ніком {old_nick} не знайдено.")
            return
        
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET clan_name=? WHERE id=?", (new_nick, target['id']))
            conn.commit()
        
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} змінив нік {old_nick} на {new_nick}")
        
        actions.pop(user_id, None)
        await message.answer(f"✅ Нік змінено: {old_nick} → {new_nick}", reply_markup=clan_management_menu())
        return
    
    # Видача балів
    if action["type"] == "give_points":
        if not is_leader_or_advisor(user_id):
            return
        
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: `нік_гравця кількість`", parse_mode="Markdown")
            return
        
        clan_name, amount_str = parts
        try:
            amount = int(amount_str)
            if amount <= 0:
                await message.answer("❌ Кількість має бути більшою за 0.")
                return
        except ValueError:
            await message.answer("❌ Введіть число.")
            return
        
        target = get_user_by_clan_name(clan_name)
        if not target:
            await message.answer(f"❌ Користувача {clan_name} не знайдено.")
            return
        
        add_points(target['id'], amount)
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} видав {amount} балів {target['clan_name']}")
        
        actions.pop(user_id, None)
        await message.answer(
            f"✅ Видано {amount} балів {target['clan_name']}\n"
            f"Новий баланс: {get_user(target['id'])['points']} балів",
            reply_markup=clan_management_menu()
        )
        return
    
    # Видача монет
    if action["type"] == "give_coins":
        if not is_leader_or_advisor(user_id):
            return
        
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: `нік_гравця кількість`", parse_mode="Markdown")
            return
        
        clan_name, amount_str = parts
        try:
            amount = int(amount_str)
            if amount <= 0:
                await message.answer("❌ Кількість має бути більшою за 0.")
                return
        except ValueError:
            await message.answer("❌ Введіть число.")
            return
        
        target = get_user_by_clan_name(clan_name)
        if not target:
            await message.answer(f"❌ Користувача {clan_name} не знайдено.")
            return
        
        add_coins(target['id'], amount)
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} видав {amount} монет {target['clan_name']}")
        
        actions.pop(user_id, None)
        await message.answer(
            f"✅ Видано {amount} монет {target['clan_name']}\n"
            f"Новий баланс: {get_user(target['id'])['coins_received']} монет",
            reply_markup=clan_management_menu()
        )
        return
    
    # Списання монет
    if action["type"] == "remove_coins":
        if not is_leader_or_advisor(user_id):
            return
        
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: `нік_гравця кількість`", parse_mode="Markdown")
            return
        
        clan_name, amount_str = parts
        try:
            amount = int(amount_str)
            if amount <= 0:
                await message.answer("❌ Кількість має бути більшою за 0.")
                return
        except ValueError:
            await message.answer("❌ Введіть число.")
            return
        
        target = get_user_by_clan_name(clan_name)
        if not target:
            await message.answer(f"❌ Користувача {clan_name} не знайдено.")
            return
        
        if target['coins_received'] < amount:
            await message.answer(f"❌ У {target['clan_name']} тільки {target['coins_received']} монет.")
            return
        
        remove_coins(target['id'], amount)
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} списав {amount} монет у {target['clan_name']}")
        
        actions.pop(user_id, None)
        await message.answer(
            f"✅ Списано {amount} монет у {target['clan_name']}\n"
            f"Новий баланс: {get_user(target['id'])['coins_received']} монет",
            reply_markup=clan_management_menu()
        )
        return
    
    # Обмін балів
    if action["type"] == "exchange_points":
        if not is_leader_or_advisor(user_id):
            return
        
        try:
            points = int(text)
            if points <= 0:
                await message.answer("❌ Кількість балів має бути більшою за 0.")
                return
            
            user = get_user(user_id)
            if user['points'] < points:
                await message.answer(f"❌ У вас недостатньо балів. Маєте: {user['points']}")
                return
            
            coins = points // POINT_PRICE
            if coins == 0:
                await message.answer(f"❌ Мінімальний обмін: {POINT_PRICE} балів за 1 монету.")
                return
            
            remove_points(user_id, points)
            add_coins(user_id, coins)
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO exchange_requests(user_id, points, coins, created, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, points, coins, int(time.time()), 'completed'))
                conn.commit()
            
            add_log(f"{user['clan_name']} обміняв {points} балів на {coins} монет")
            
            actions.pop(user_id, None)
            await message.answer(
                f"✅ Обмін виконано!\n\n"
                f"Витрачено балів: {points}\n"
                f"Отримано монет: {coins}\n"
                f"Залишилось балів: {get_user(user_id)['points']}",
                reply_markup=clan_management_menu()
            )
            
        except ValueError:
            await message.answer("❌ Введіть число.")
        return
    
    # Оголошення
    if action["type"] == "announce":
        if not is_admin(user_id):
            return
        
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE clan_name IS NOT NULL")
            users = cursor.fetchall()
        
        success = 0
        for user in users:
            try:
                await bot.send_message(user['id'], f"📢 **Оголошення**\n\n{text}", parse_mode="Markdown")
                success += 1
                await asyncio.sleep(0.05)
            except:
                pass
        
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} відправив оголошення ({success} отримали)")
        
        actions.pop(user_id, None)
        await message.answer(
            f"✅ Оголошення відправлено {success} користувачам.",
            reply_markup=clan_management_menu()
        )
        return
    
    # Створення події
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
        await message.answer("📅 Введіть дату події\nФормат: `ДД.ММ.РРРР`\nПриклад: `10.07.2026`", parse_mode="Markdown")
        return
    
    if action["type"] == "create_event_date":
        actions[user_id] = {
            "type": "create_event_time",
            "title": action["title"],
            "description": action["description"],
            "event_date": text
        }
        await message.answer("🕒 Введіть час події\nФормат: `ГГ:ХХ`\nПриклад: `19:30`", parse_mode="Markdown")
        return
    
    if action["type"] == "create_event_time":
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
        await message.answer("✅ Подію створено!", reply_markup=main_menu(user_id))
        return

# =========================
# COMMAND LIST
# =========================

async def setup_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустити бота"),
        BotCommand(command="menu", description="Відкрити меню"),
        BotCommand(command="top", description="Топ гравців за балами")
    ])

# =========================
# EVENT NOTIFICATIONS
# =========================

async def event_notifications():
    while True:
        try:
            now = int(time.time())
            
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
                
                # Нагадування за 15 хвилин
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
                                f"⏰ **Нагадування!**\n\nДо події «{event['title']}» залишилось 15 хвилин!\n\n"
                                f"Не забудьте прийти! 🏃‍♂️"
                            )
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET remind15=1 WHERE id=?", (event['id'],))
                        conn.commit()
                
                # Початок події
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
                                f"«{event['title']}» розпочалась прямо зараз!\n"
                                f"+10 балів за участь! 🎉"
                            )
                            add_points(user['user_id'], 10)
                            add_event_visit(user['user_id'])
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET started=1 WHERE id=?", (event['id'],))
                        conn.commit()
            
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Помилка в event_notifications: {e}")
            await asyncio.sleep(60)

# =========================
# MAIN
# =========================

async def main():
    print("🤖 BOT STARTING...")
    await setup_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ POLLING STARTED")
    asyncio.create_task(event_notifications())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
