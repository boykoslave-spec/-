import asyncio
import os
import sqlite3
import time
import random
from datetime import datetime, timedelta
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
                points INTEGER DEFAULT 0,
                events_visited INTEGER DEFAULT 0,
                coins_received INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                last_streak_date INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                registered_at INTEGER DEFAULT 0
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
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER,
                player2_id INTEGER,
                game_type TEXT,
                bet INTEGER,
                winner_id INTEGER,
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

POINT_PRICE = 100
STREAK_BONUS = 10

DEFAULT_ADMINS = {
    "Jordana_SWAT": ("👑 Лідер", 1),
    "Wtfmnnnn": ("🛡 Радник", 2)
}

# =========================
# ЗЛІ ТА ДОБРІ РЕАКЦІЇ
# =========================

# Добрі реакції
GOOD_REACTIONS = {
    "зсу": "🇺🇦 **Слава Україні!** Героям Слава! 💙💛",
    "україна": "🇺🇦 **Слава Україні!** Разом переможемо! 💪",
    "дякую": "🙏 Будь ласка! Завжди радий допомогти! 😊",
    "спасибі": "😊 Не дякуйте! Звертайтесь ще!",
    "привіт": "👋 Привіт-привіт! Як справи? 😊",
    "добрий день": "☀️ Доброго дня! Чим можу допомогти?",
    "доброго ранку": "🌅 Доброго ранку! Гарного дня! ☕️",
    "добрий вечір": "🌙 Доброго вечора! Як минув день?",
}

# Злі/хамські реакції
BAD_REACTIONS = {
    "бот": "🖕 **Сам ти бот, пішов нахуй!** 😏",
    "син": "👶 **Я тобі не син, бидло!** 🖕",
    "сина": "👶 **Ти мені не батько, довбойоб!** 🤡",
    "тупий": "🧠 **Сам тупий, довбойоб єбаний!** 🤡",
    "дурак": "🤡 **Ти тут головний дурак, ясно?** 🖕",
    "лох": "💰 **Лох - це той, хто програв, а не я!** 😏",
    "козел": "🐐 **Сам козел, а я баран - у нас тут зоопарк, чи шо?** 🤡",
    "ідіот": "🧠 **Ти - професор ідіотії! Поважай себе!** 🖕",
    "довбойоб": "🪓 **Е, ти на себе подивись, довбойобище!** 🤡",
}

# Фрази для переклички
ROLL_CALL_PHRASES = [
    "🌅 **Підйом, мазафакери!** Всі на місці, або я починаю кидати тапками! 🩴",
    "🔔 **Перекличка, бидло!** Хто не відгукнеться - той миє туалети до кінця місяця! 🚽",
    "⚡️ **Ранкова побудова!** Хто спить - той проїбав день! Вставайте, ліниві дупи! 🍑",
    "🎯 **Увага, клан!** Перекличка! Хто не відповість - той черговий по кухні! 🍳",
    "🔥 **Вогонь по готовності!** Всі на місці, або я вас всіх ... вибачте, посміюся! 😂",
    "💪 **Збірка, гандони!** Покажіть, що ви тут! Хто не відповів - той втратив яйця! 🥚",
    "🏃 **Швидка перекличка!** Відповідайте, бо я подумаю, що ви померли! 💀",
    "🤡 **Алло, клан!** Всі живі? Відповідайте, поки я не почав хвилюватися! (а я не почну) 🖕",
]

# Хамські фрази для особового складу
MEMBER_REPLIES = [
    "🖕 {name} - {role} {status} (Краще б сидів вдома!)",
    "🤡 {name} - {role} {status} (Ну ти й клоун, друже!)",
    "💩 {name} - {role} {status} (Хто це тебе взяв в клан?)",
    "😏 {name} - {role} {status} (Ну ти й довбойоб, я люблю тебе!)",
    "🫵 {name} - {role} {status} (Це ти той самий, який ... ну ти зрозумів!)",
    "🤡 {name} - {role} {status} (Ти тут найголовніший циркач!)",
    "🖕 {name} - {role} {status} (Ти гарний, але я тобі цього не скажу!)",
    "💀 {name} - {role} {status} (Ти вже мертвий, ти знаєш?)",
]

# Хамські фрази для реакції на згадування
FUNNY_REPLIES = [
    "🖕 **Сходи нахуй, довбойоб!** 😏",
    "🤡 **Тебе вєбать, пішов звідси!** 💀",
    "🖕 **Ти хто такий взагалі? Пішов нахуй!** 🤡",
    "💩 **Я тебе бачу, але ти мені не подобаєшся!** 🖕",
    "😏 **Ти гарний клоун, друже!** Продовжуй! 🤡",
    "🫵 **Ти бидло, але ти наше бидло!** 🖕",
    "💀 **Ти мертвий для мене, але я тебе люблю!** 😂",
    "🤡 **Ти - головний циркач нашого клану!** Поважай себе! 🖕",
    "🖕 **Ну ти й гандон, я аж плакати хочу!** 😂",
    "💪 **Ти сильний тільки в словах, як я бачу!** Пішов нахуй! 🖕",
]

# =========================
# ACTIONS
# =========================
actions = {}
menu_owner = {}
active_games = {}
roll_call_sent = False
event_monitoring = True

# =========================
# DATABASE FUNCTIONS
# =========================

def register_user(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    with db.connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, clan_name FROM users WHERE id=?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            role = "⚔️ Солдат"
            level = 7
            
            if username in DEFAULT_ADMINS:
                role, level = DEFAULT_ADMINS[username]
            
            cursor.execute("""
                INSERT INTO users(
                    id, username, clan_name, role, role_level, last_online, 
                    points, events_visited, coins_received, streak, 
                    last_streak_date, wins, losses, registered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, username, None, role, level, int(time.time()), 
                0, 0, 0, 0, 0, 0, 0, int(time.time())
            ))
            conn.commit()
            
            add_log(f"Новий користувач {username or user_id} зареєструвався")
            return False
        
        cursor.execute("""
            UPDATE users 
            SET last_online=?, username=?
            WHERE id=?
        """, (int(time.time()), username, user_id))
        conn.commit()
        return True

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

def get_registered_count():
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE clan_name IS NOT NULL")
        return cursor.fetchone()[0]

def get_all_chats():
    """Отримує всі чати де є бот (для оголошень)"""
    # Тут потрібно зберігати ID чатів при старті
    # Але для простоти - повертаємо всіх зареєстрованих
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT chat_id FROM users WHERE chat_id IS NOT NULL")
        chats = cursor.fetchall()
    return [chat[0] for chat in chats] if chats else []

# =========================
# KEYBOARDS
# =========================

def main_menu(user_id):
    keyboard = []
    
    keyboard.extend([
        [InlineKeyboardButton(text="🪖 Особовий склад", callback_data="staff")],
        [InlineKeyboardButton(text="📅 Події", callback_data="events")],
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile")],
        [InlineKeyboardButton(text="🎮 Міні ігри", callback_data="games")]
    ])
    
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
    is_registered = register_user(message)
    await message.answer("Оновлення меню...", reply_markup=ReplyKeyboardRemove())
    
    # Зберігаємо chat_id для оголошень
    with db.connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN chat_id INTEGER DEFAULT 0")
        except:
            pass
        cursor.execute("UPDATE users SET chat_id=? WHERE id=?", (message.chat.id, message.from_user.id))
        conn.commit()
    
    user = get_user(message.from_user.id)
    
    if not user['clan_name']:
        actions[message.from_user.id] = {"type": "register"}
        await message.answer(
            "🛡️ **Вас вітає ЗСУ 🇺🇦**\n\n"
            "Введіть свій клановий нік:",
            reply_markup=cancel_button(),
            parse_mode="Markdown"
        )
        return
    
    msg = await message.answer("🛡️ **Головне меню**", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    menu_owner[msg.message_id] = message.from_user.id

@dp.message(Command("menu"))
async def menu_command(message: Message):
    register_user(message)
    msg = await message.answer("🛡️ **Головне меню**", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    menu_owner[msg.message_id] = message.from_user.id

@dp.message(Command("top"))
async def top_command(message: Message):
    register_user(message)
    users = get_top_users(10)
    
    if not users:
        await message.answer("📊 Топ поки що порожній.")
        return
    
    text = "🏆 **Топ гравців за балами**\n\n"
    for i, user in enumerate(users, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {user['clan_name']} - {user['points']} балів ({user['role']})\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("check"))
async def check_command(message: Message):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Ви не зареєстровані. Напишіть /start")
        return
    
    if user['clan_name']:
        await message.answer(
            f"✅ **Ви зареєстровані!**\n\n"
            f"🏷 Нік: {user['clan_name']}\n"
            f"👑 Роль: {user['role']}\n"
            f"🪙 Бали: {user['points']}\n"
            f"💰 Монети: {user['coins_received']}\n"
            f"📅 Зареєстровано: {datetime.fromtimestamp(user['registered_at']).strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "⚠️ **Ви зареєстровані, але ще не вказали клановий нік!**\n\n"
            "Напишіть /start щоб завершити реєстрацію.",
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
# STAFF LIST (КРАСИВИЙ БЕЗ ЛІНІЙ)
# =========================

@dp.callback_query(lambda c: c.data == "staff")
async def staff(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT clan_name, role, last_online, id
            FROM users
            WHERE clan_name IS NOT NULL
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
        
        # Випадкова жартівлива/хамська фраза
        reply = random.choice(MEMBER_REPLIES).format(
            name=user['clan_name'],
            role=user['role'],
            status=status
        )
        text += f"{reply}\n"
    
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
    
    register_user(call.message)
    user = get_user(call.from_user.id)
    
    streak_result = check_streak(call.from_user.id)
    if isinstance(streak_result, tuple):
        streak, bonus = streak_result
        if bonus > 0:
            await call.message.answer(f"🔥 Стрік {streak} днів! Отримано бонус: {bonus} балів!")
    else:
        streak = streak_result
    
    reg_date = datetime.fromtimestamp(user['registered_at']).strftime('%d.%m.%Y')
    
    await call.message.edit_text(
        f"👤 **Профіль**\n\n"
        f"🏷 Нік: {user['clan_name']}\n"
        f"👑 Роль: {user['role']}\n"
        f"🪙 Бали: {user['points']}\n"
        f"💰 Монети: {user['coins_received']}\n"
        f"🏆 Подій: {user['events_visited']}\n"
        f"🔥 Стрік: {streak} днів\n"
        f"🎮 Перемог: {user['wins']}\n"
        f"💀 Поразок: {user['losses']}\n"
        f"📊 Статус: {status_icon(user['last_online'])}\n"
        f"📅 З нами: {reg_date}",
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

# =========================
# EVENTS (З ВАЛІДАЦІЄЮ ЧАСУ)
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
# GIVE POINTS / COINS / EXCHANGE / REMOVE
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
# ANNOUNCE (В ЧАТИ)
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
# GAMES (Міні ігри)
# =========================

@dp.callback_query(lambda c: c.data == "games")
async def games_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    user = get_user(call.from_user.id)
    
    await call.message.edit_text(
        "🎮 **Міні ігри**\n\n"
        f"💰 Ваші монети: {user['coins_received']}\n\n"
        "Оберіть гру:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Гра з ботом (Кістки)", callback_data="game_bot_dice")],
            [InlineKeyboardButton(text="🏀 Гра з ботом (Кидок у кошик)", callback_data="game_bot_hoop")],
            [InlineKeyboardButton(text="👥 Гра з гравцем (Кістки)", callback_data="game_player")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ])
    )

@dp.callback_query(lambda c: c.data == "game_player")
async def game_player_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    user = get_user(call.from_user.id)
    
    await call.message.edit_text(
        "👥 **Гра з гравцем (Кістки)**\n\n"
        "Введіть нік гравця та ставку у форматі:\n"
        "`нік_гравця ставка`\n\n"
        "Приклад: `Jordana_SWAT 5`\n\n"
        f"💰 Ваш баланс: {user['coins_received']} монет",
        reply_markup=cancel_button(),
        parse_mode="Markdown"
    )
    
    actions[call.from_user.id] = {"type": "game_player_challenge"}

@dp.callback_query(lambda c: c.data.startswith("game_bot_"))
async def game_with_bot(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    game_type = call.data.split("_")[2]
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if game_type == "dice":
        cost = 2
        if user['coins_received'] < cost:
            await call.answer(f"❌ Недостатньо монет! Потрібно: {cost}", show_alert=True)
            return
        
        # Відправляємо кубик
        msg = await call.message.answer_dice(emoji="🎲")
        await asyncio.sleep(2)
        
        player_roll = msg.dice.value
        bot_roll = random.randint(1, 6)
        
        # Видаляємо емодзі кубика
        await msg.delete()
        
        remove_coins(user_id, cost)
        
        if player_roll > bot_roll:
            win = cost * 2
            add_coins(user_id, win)
            add_points(user_id, 5)
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"🎉 **Ви виграли!**\nВаш кидок: {player_roll} 🤖 Бот: {bot_roll}\n+{win} монет! +5 балів!"
        elif player_roll < bot_roll:
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"😢 **Ви програли!**\nВаш кидок: {player_roll} 🤖 Бот: {bot_roll}\n-{cost} монет."
        else:
            add_coins(user_id, cost)
            result = f"🤝 **Нічия!**\nВаш кидок: {player_roll} 🤖 Бот: {bot_roll}\nПовернуто {cost} монет."
    
    elif game_type == "hoop":
        cost = 1
        if user['coins_received'] < cost:
            await call.answer(f"❌ Недостатньо монет! Потрібно: {cost}", show_alert=True)
            return
        
        # Відправляємо баскетбольний кидок
        msg = await call.message.answer_dice(emoji="🏀")
        await asyncio.sleep(2)
        
        player_result = "попав 🏀" if msg.dice.value >= 4 else "не попав ❌"
        bot_result = "попав 🏀" if random.randint(1, 6) >= 4 else "не попав ❌"
        
        # Видаляємо емодзі
        await msg.delete()
        
        remove_coins(user_id, cost)
        
        if msg.dice.value >= 4 and random.randint(1, 6) >= 4:
            win = cost * 2
            add_coins(user_id, win)
            add_points(user_id, 3)
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (user_id,))
                conn.commit()
            result = f"🎉 **Ви виграли!**\nВи: {player_result} 🤖 Бот: {bot_result}\n+{win} монет! +3 бали!"
        elif msg.dice.value >= 4 and random.randint(1, 6) < 4:
            result = f"😢 **Ви програли!**\nВи: {player_result} 🤖 Бот: {bot_result}\n-{cost} монет."
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (user_id,))
                conn.commit()
        else:
            add_coins(user_id, cost)
            result = f"🤝 **Нічия!**\nВи: {player_result} 🤖 Бот: {bot_result}\nПовернуто {cost} монет."
    
    else:
        return
    
    user = get_user(user_id)
    result += f"\n\n💰 Баланс: {user['coins_received']} монет"
    
    await call.message.answer(
        result,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Грати ще", callback_data=f"game_bot_{game_type}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="games")]
        ]),
        parse_mode="Markdown"
    )
    
    try:
        await call.message.delete()
    except:
        pass

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
# ПРИЙНЯТТЯ/ВІДМОВА ВІД ГРИ
# =========================

@dp.callback_query(lambda c: c.data.startswith("accept_game_"))
async def accept_game(call: CallbackQuery):
    challenger_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    
    game = active_games.get(challenger_id)
    if not game:
        await call.answer("❌ Гра вже не актуальна", show_alert=True)
        return
    
    if game["opponent"] != user_id:
        await call.answer("❌ Це не для вас", show_alert=True)
        return
    
    if game["status"] != "waiting":
        await call.answer("❌ Гра вже розпочата", show_alert=True)
        return
    
    challenger = get_user(challenger_id)
    opponent = get_user(user_id)
    bet = game["bet"]
    
    if challenger['coins_received'] < bet:
        await call.answer(f"❌ У {challenger['clan_name']} недостатньо монет!", show_alert=True)
        active_games.pop(challenger_id, None)
        return
    
    if opponent['coins_received'] < bet:
        await call.answer(f"❌ У вас недостатньо монет!", show_alert=True)
        active_games.pop(challenger_id, None)
        return
    
    game["status"] = "playing"
    active_games[challenger_id] = game
    
    await call.message.edit_text(
        f"🎲 **Гра почалась!**\n\n"
        f"{challenger['clan_name']} vs {opponent['clan_name']}\n"
        f"Ставка: {bet} монет\n\n"
        f"Кидайте кубики! 🎲",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Кинути кубик!", callback_data=f"roll_dice_{challenger_id}")]
        ])
    )
    
    await call.answer("✅ Гра розпочата!")

@dp.callback_query(lambda c: c.data.startswith("decline_game_"))
async def decline_game(call: CallbackQuery):
    challenger_id = int(call.data.split("_")[2])
    
    game = active_games.get(challenger_id)
    if game:
        active_games.pop(challenger_id, None)
    
    await call.message.edit_text("❌ Виклик відхилено.")
    await call.answer("❌ Ви відхилили виклик")

@dp.callback_query(lambda c: c.data.startswith("roll_dice_"))
async def roll_dice_game(call: CallbackQuery):
    challenger_id = int(call.data.split("_")[2])
    user_id = call.from_user.id
    
    game = active_games.get(challenger_id)
    if not game:
        await call.answer("❌ Гра не знайдена", show_alert=True)
        return
    
    if game["status"] != "playing":
        await call.answer("❌ Гра вже завершена", show_alert=True)
        return
    
    if user_id != challenger_id and user_id != game["opponent"]:
        await call.answer("❌ Ви не граєте в цій грі", show_alert=True)
        return
    
    # Кидаємо кубик
    msg = await call.message.answer_dice(emoji="🎲")
    await asyncio.sleep(2)
    roll = msg.dice.value
    
    # Видаляємо кубик
    await msg.delete()
    
    if "rolls" not in game:
        game["rolls"] = {}
    
    game["rolls"][user_id] = roll
    
    if len(game["rolls"]) < 2:
        await call.answer(f"🎲 Ви кинули {roll}! Очікуємо суперника...")
        
        opponent_id = game["opponent"] if user_id == challenger_id else challenger_id
        try:
            await bot.send_message(
                opponent_id,
                f"🎲 {get_user(user_id)['clan_name']} кинув кубик! Ваш хід!"
            )
        except:
            pass
        return
    
    # Обидва кинули
    player1_id = challenger_id
    player2_id = game["opponent"]
    roll1 = game["rolls"][player1_id]
    roll2 = game["rolls"][player2_id]
    bet = game["bet"]
    
    player1 = get_user(player1_id)
    player2 = get_user(player2_id)
    
    if roll1 > roll2:
        winner_id = player1_id
        loser_id = player2_id
        winner = player1
        loser = player2
    elif roll2 > roll1:
        winner_id = player2_id
        loser_id = player1_id
        winner = player2
        loser = player1
    else:
        result_text = (
            f"🤝 **Нічия!**\n\n"
            f"{player1['clan_name']}: {roll1} 🎲\n"
            f"{player2['clan_name']}: {roll2} 🎲\n\n"
            f"Ставки повернуто."
        )
        
        await call.message.edit_text(result_text, parse_mode="Markdown")
        active_games.pop(challenger_id, None)
        return
    
    add_coins(winner_id, bet * 2)
    remove_coins(loser_id, bet)
    add_points(winner_id, 5)
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (winner_id,))
        cursor.execute("UPDATE users SET losses = losses + 1 WHERE id=?", (loser_id,))
        conn.commit()
    
    add_log(f"{winner['clan_name']} виграв у {loser['clan_name']} в кістки (+{bet*2} монет)")
    
    result_text = (
        f"🏆 **Переможець: {winner['clan_name']}!**\n\n"
        f"{player1['clan_name']}: {roll1} 🎲\n"
        f"{player2['clan_name']}: {roll2} 🎲\n\n"
        f"💰 Виграш: +{bet*2} монет!\n"
        f"🪙 +5 балів!\n\n"
        f"Новий баланс {winner['clan_name']}: {get_user(winner_id)['coins_received']} монет"
    )
    
    await call.message.edit_text(result_text, parse_mode="Markdown")
    
    try:
        await bot.send_message(
            winner_id,
            f"🎉 **Ви перемогли!**\n+{bet*2} монет, +5 балів!"
        )
    except:
        pass
    
    active_games.pop(challenger_id, None)

@dp.callback_query(lambda c: c.data.startswith("cancel_game_"))
async def cancel_game(call: CallbackQuery):
    challenger_id = int(call.data.split("_")[2])
    active_games.pop(challenger_id, None)
    await call.message.edit_text("❌ Гру скасовано.")
    await call.answer("❌ Гру скасовано")

# =========================
# ГОЛОВНИЙ ОБРОБНИК ПОВІДОМЛЕНЬ
# =========================

@dp.message()
async def handle_all_messages(message: Message):
    try:
        is_registered = register_user(message)
        
        # Зберігаємо chat_id
        with db.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN chat_id INTEGER DEFAULT 0")
            except:
                pass
            cursor.execute("UPDATE users SET chat_id=? WHERE id=?", (message.chat.id, message.from_user.id))
            conn.commit()
        
        # Перевірка на добрі слова
        if message.text:
            text_lower = message.text.lower()
            for keyword, response in GOOD_REACTIONS.items():
                if keyword in text_lower:
                    await message.reply(response, parse_mode="Markdown")
                    return
            
            # Перевірка на злі слова
            for keyword, response in BAD_REACTIONS.items():
                if keyword in text_lower:
                    await message.reply(response, parse_mode="Markdown")
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
            await message.reply(random.choice(FUNNY_REPLIES), parse_mode="Markdown")
            return
        
        # Перевірка чи користувач зареєструвався
        user = get_user(message.from_user.id)
        if user and not user['clan_name'] and not actions.get(message.from_user.id):
            actions[message.from_user.id] = {"type": "register"}
            await message.answer(
                "🛡️ **Вас вітає ЗСУ 🇺🇦**\n\n"
                "Ви ще не зареєстровані!\n"
                "Введіть свій клановий нік:",
                reply_markup=cancel_button(),
                parse_mode="Markdown"
            )
            return
        
        # Обробка дій
        action = actions.get(message.from_user.id)
        if not action:
            return
        
        user_id = message.from_user.id
        text = message.text
        
        # РЕЄСТРАЦІЯ
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
        
        # ЗМІНА НІКУ
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
        
        # ВИДАЧА БАЛІВ
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
        
        # ВИДАЧА МОНЕТ
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
        
        # СПИСАННЯ МОНЕТ
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
        
        # ОБМІН БАЛІВ
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
        
        # ОГОЛОШЕННЯ (В ЧАТИ)
        if action["type"] == "announce":
            if not is_admin(user_id):
                return
            
            # Відправляємо в чати де є бот
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT chat_id FROM users WHERE chat_id IS NOT NULL AND chat_id != 0")
                chats = cursor.fetchall()
            
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
            # Перевіряємо дату
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
            # Перевіряємо час
            try:
                event_time = datetime.strptime(text, "%H:%M")
            except ValueError:
                await message.answer("❌ Неправильний формат часу! Використовуйте `ГГ:ХХ`", parse_mode="Markdown")
                return
            
            # Перевіряємо чи дата+час не в минулому
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
        
        # ГРА З ГРАВЦЕМ
        if action["type"] == "game_player_challenge":
            parts = text.split()
            if len(parts) != 2:
                await message.answer("❌ Формат: `нік_гравця ставка`", parse_mode="Markdown")
                return
            
            target_name, bet_str = parts
            try:
                bet = int(bet_str)
                if bet <= 0:
                    await message.answer("❌ Ставка має бути більшою за 0.")
                    return
            except ValueError:
                await message.answer("❌ Введіть число для ставки.")
                return
            
            player = get_user(user_id)
            target = get_user_by_clan_name(target_name)
            
            if not target:
                await message.answer(f"❌ Користувача {target_name} не знайдено.")
                return
            
            if target['id'] == user_id:
                await message.answer("❌ Не можна грати з самим собою!")
                return
            
            if player['coins_received'] < bet:
                await message.answer(f"❌ У вас недостатньо монет. Маєте: {player['coins_received']}")
                return
            
            if target['coins_received'] < bet:
                await message.answer(f"❌ У {target['clan_name']} недостатньо монет. Має: {target['coins_received']}")
                return
            
            active_games[user_id] = {
                "opponent": target['id'],
                "bet": bet,
                "status": "waiting"
            }
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Прийняти виклик", callback_data=f"accept_game_{user_id}")],
                [InlineKeyboardButton(text="❌ Відмовити", callback_data=f"decline_game_{user_id}")]
            ])
            
            await message.answer(
                f"🎮 **Виклик на гру!**\n\n"
                f"{player['clan_name']} викликає {target['clan_name']}\n"
                f"Ставка: {bet} монет\n\n"
                f"Гра: Кістки 🎲",
                reply_markup=keyboard
            )
            
            actions.pop(user_id, None)
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
        BotCommand(command="top", description="Топ гравців за балами"),
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
                
                with db.connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, clan_name FROM users WHERE clan_name IS NOT NULL")
                    users = cursor.fetchall()
                
                if users:
                    phrase = random.choice(ROLL_CALL_PHRASES)
                    
                    for user in users:
                        try:
                            await bot.send_message(
                                user['id'],
                                f"{phrase}\n\n"
                                f"🇺🇦 **Слава Україні!**\n"
                                f"Відгукнись, {user['clan_name']}! 🫡",
                                parse_mode="Markdown"
                            )
                            await asyncio.sleep(0.1)
                        except:
                            pass
                    
                    add_log("Проведено ранкову перекличку")
            
            # Скидаємо флаг о 11:00
            if current_time.hour == 11 and current_time.minute == 0:
                roll_call_sent = False
            
            # ПОДІЇ - МОНІТОРИНГ
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
                                f"**{event['title']}** стартувала!\n"
                                f"+10 балів за участь! 🎉",
                                parse_mode="Markdown"
                            )
                            add_points(user['user_id'], 10)
                            add_event_visit(user['user_id'])
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    
                    # Позначаємо як завершену
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET started=1 WHERE id=?", (event['id'],))
                        conn.commit()
                    
                    # ВИДАЛЯЄМО ПІСЛЯ ЗАВЕРШЕННЯ
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
