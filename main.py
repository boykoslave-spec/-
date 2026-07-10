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
                last_streak_date INTEGER DEFAULT 0
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
                created INTEGER,
                status TEXT DEFAULT 'pending'
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

# =========================
# ACTIVE USER ACTIONS
# =========================
actions = {}
menu_owner = {}

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
                                 points, events_visited, coins_received, streak, last_streak_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, None, role, level, int(time.time()), 0, 0, 0, 0, 0))
        
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
    """Перевіряє, чи може адмін змінювати роль цільового користувача"""
    admin = get_user(admin_user_id)
    target = get_user(target_user_id)
    
    if not admin or not target:
        return False
    
    # Лідер може все
    if admin['role_level'] == 1:
        return True
    
    # Радник не може змінювати Лідера або іншого Радника
    if admin['role_level'] == 2:
        if target['role_level'] <= 2:
            return False
        return True
    
    return False

def can_exchange(user_id):
    """Перевіряє, чи може користувач обмінювати бали на монети"""
    user = get_user(user_id)
    if not user:
        return False
    # Тільки Лідер або Радник можуть обмінювати
    return user['role_level'] <= 2

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

# =========================
# KEYBOARDS
# =========================

def main_menu(user_id):
    keyboard = []
    
    if is_admin(user_id):
        keyboard.extend([
            [InlineKeyboardButton(text="🪖 Особовий склад", callback_data="staff")],
            [InlineKeyboardButton(text="🎖 Керування ролями", callback_data="roles")],
            [InlineKeyboardButton(text="✏️ Змінити нік бійця", callback_data="change_nick")],
            [InlineKeyboardButton(text="📅 Події", callback_data="events")],
            [InlineKeyboardButton(text="📜 Журнал", callback_data="logs")],
            [InlineKeyboardButton(text="📢 Оголошення", callback_data="announce")]
        ])
    
    # Кнопка обміну тільки для Лідера/Радників
    if is_leader_or_advisor(user_id):
        keyboard.append([InlineKeyboardButton(text="💱 Обмін балів на монети", callback_data="exchange")])
    
    # Кнопка списання монет тільки для Лідера/Радників
    if is_leader_or_advisor(user_id):
        keyboard.append([InlineKeyboardButton(text="💰 Списання монет", callback_data="remove_coins")])
    
    keyboard.extend([
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile")],
        [InlineKeyboardButton(text="⚙️ Налаштування", callback_data="settings")],
        [InlineKeyboardButton(text="🙈 Сховати меню", callback_data="hide_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def cancel_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel")]
    ])

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
# HIDE, BACK, CANCEL
# =========================

@dp.callback_query(lambda c: c.data == "hide_menu")
async def hide_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    await call.message.edit_text("🙈 Меню приховано.\n\nВикористайте /menu щоб відкрити його.")

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
        f"👤 Профіль\n\n"
        f"Нік: {user['clan_name']}\n"
        f"Роль: {user['role']}\n"
        f"🪙 Бали: {user['points']}\n"
        f"🏆 Подій відвідано: {user['events_visited']}\n"
        f"💰 Монет отримано: {user['coins_received']}\n"
        f"🔥 Стрік: {streak} днів\n"
        f"Статус: {status_icon(user['last_online'])}",
        reply_markup=back_button()
    )

# =========================
# EXCHANGE (тільки для Лідера/Радників)
# =========================

@dp.callback_query(lambda c: c.data == "exchange")
async def exchange_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    # Перевіряємо, чи має користувач право обмінювати
    if not can_exchange(call.from_user.id):
        await call.answer("❌ Тільки Лідер або Радник можуть обмінювати бали!", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    
    await call.message.edit_text(
        f"💱 Обмін балів на монети\n\n"
        f"Ваші бали: {user['points']}\n"
        f"Курс: {POINT_PRICE} балів = 1 монета\n\n"
        f"Введіть кількість балів для обміну:",
        reply_markup=cancel_button()
    )
    
    actions[call.from_user.id] = {"type": "exchange_points"}

# =========================
# REMOVE COINS (тільки для Лідера/Радників)
# =========================

@dp.callback_query(lambda c: c.data == "remove_coins")
async def remove_coins_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Тільки Лідер або Радник можуть списувати монети!", show_alert=True)
        return
    
    # Показуємо список гравців
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, clan_name, coins_received
            FROM users
            WHERE clan_name IS NOT NULL
            ORDER BY clan_name ASC
        """)
        users = cursor.fetchall()
    
    buttons = []
    for user in users:
        if user['coins_received'] > 0:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{user['clan_name']} (💰{user['coins_received']})",
                    callback_data=f"remove_coins_user_{user['id']}"
                )
            ])
    
    if not buttons:
        await call.message.edit_text(
            "💰 Немає гравців з монетами для списання.",
            reply_markup=back_button()
        )
        return
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    await call.message.edit_text(
        "💰 Оберіть гравця для списання монет:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(lambda c: c.data.startswith("remove_coins_user_"))
async def select_remove_coins_user(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_leader_or_advisor(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
        return
    
    target_id = int(call.data.split("_")[3])
    target = get_user(target_id)
    
    actions[call.from_user.id] = {
        "type": "remove_coins",
        "target": target_id
    }
    
    await call.message.edit_text(
        f"💰 Списання монет\n\n"
        f"Гравець: {target['clan_name']}\n"
        f"Поточний баланс монет: {target['coins_received']}\n\n"
        f"Введіть кількість монет для списання:",
        reply_markup=cancel_button()
    )

# =========================
# SETTINGS
# =========================

@dp.callback_query(lambda c: c.data == "settings")
async def settings(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    await call.message.edit_text(
        "⚙️ Налаштування",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Змінити свій нік", callback_data="my_nick")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ])
    )

@dp.callback_query(lambda c: c.data == "my_nick")
async def my_nick(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "my_nick", "message_id": call.message.message_id}
    await call.message.edit_text("✏️ Введіть новий клановий нік:", reply_markup=cancel_button())

# =========================
# STAFF LIST
# =========================

@dp.callback_query(lambda c: c.data == "staff")
async def staff(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    if not is_admin(call.from_user.id):
        await call.answer("❌ Немає доступу", show_alert=True)
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
    
    text = "🪖 Особовий склад:\n"
    current_role = None
    
    for user in users:
        if current_role != user['role']:
            current_role = user['role']
            text += f"\n{current_role}\n"
        text += f"• {user['clan_name']} {status_icon(user['last_online'])}\n"
    
    await call.message.edit_text(text, reply_markup=back_button())

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
        # Перевіряємо, чи може поточний адмін змінювати роль цього користувача
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
        "🎖 Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(lambda c: c.data.startswith("role_user_"))
async def select_role_user(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    target_id = int(call.data.split("_")[2])
    
    # Перевіряємо, чи може адмін змінювати роль цього користувача
    if not can_manage_roles(call.from_user.id, target_id):
        await call.answer("❌ Ви не можете змінювати роль цього користувача!", show_alert=True)
        return
    
    actions[call.from_user.id] = {"type": "change_role", "target": target_id}
    
    # Показуємо тільки ті ролі, які може призначати цей адмін
    admin = get_user(call.from_user.id)
    available_roles = {}
    
    for role, level in ROLES.items():
        # Лідер може призначати всі ролі
        if admin['role_level'] == 1:
            available_roles[role] = level
        # Радник не може призначати ролі вищі за себе (Лідер, Радник)
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
    
    # Перевіряємо, чи може адмін змінювати роль цього користувача
    if not can_manage_roles(call.from_user.id, target_id):
        await call.answer("❌ Ви не можете змінювати роль цього користувача!", show_alert=True)
        return
    
    # Перевіряємо, чи може адмін призначати цю роль
    admin = get_user(call.from_user.id)
    if admin['role_level'] == 2 and level <= 2:
        await call.answer("❌ Радник не може призначати роль Лідера або Радника!", show_alert=True)
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role=?, role_level=? WHERE id=?", (role, level, target_id))
        conn.commit()
    
    target = get_user(target_id)
    admin = get_user(call.from_user.id)
    add_log(f"{admin['clan_name']} видав роль {role} бійцю {target['clan_name']}")
    
    actions.pop(call.from_user.id, None)
    
    await call.message.edit_text(
        f"✅ Роль змінено\n\nНова роль: {role}",
        reply_markup=back_button()
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
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, clan_name, role FROM users WHERE clan_name IS NOT NULL ORDER BY role_level ASC")
        users = cursor.fetchall()
    
    buttons = [[InlineKeyboardButton(text=f"{user['clan_name']} | {user['role']}", 
                                     callback_data=f"nick_user_{user['id']}")] for user in users]
    
    await call.message.edit_text(
        "✏️ Оберіть бійця:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(lambda c: c.data.startswith("nick_user_"))
async def select_fighter_nick(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    target = int(call.data.split("_")[2])
    actions[call.from_user.id] = {"type": "fighter_nick", "target": target}
    
    await call.message.edit_text("✏️ Введіть новий нік бійця:", reply_markup=cancel_button())

# =========================
# LOGS
# =========================

@dp.callback_query(lambda c: c.data == "logs")
async def logs_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        await call.answer("❌ Це не ваше меню", show_alert=True)
        return
    
    if not is_admin(call.from_user.id):
        return
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM logs ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
    
    text = "📜 Журнал дій\n\n"
    text += "\n".join([f"• {row['text']}" for row in rows]) if rows else "Журнал порожній."
    
    await call.message.edit_text(text, reply_markup=back_button())

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
        "📢 Введіть текст оголошення для всіх користувачів:",
        reply_markup=cancel_button()
    )

# =========================
# EVENTS
# =========================

@dp.callback_query(lambda c: c.data == "events")
async def events_menu(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    buttons = []
    
    if is_admin(call.from_user.id):
        buttons.append([InlineKeyboardButton(text="➕ Створити подію", callback_data="create_event")])
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, event_date, event_time FROM events ORDER BY id DESC LIMIT 10")
        events = cursor.fetchall()
    
    for event in events:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {event['title']} | {event['event_date']} {event['event_time']}",
            callback_data=f"event_{event['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    
    await call.message.edit_text(
        "📅 Події клану",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
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
        
        cursor.execute("SELECT COUNT(*) FROM event_members WHERE event_id=? AND status='joined'", (event_id,))
        members_count = cursor.fetchone()[0]
    
    text = (
        f"📅 {event['title']}\n\n"
        f"📝 {event['description']}\n\n"
        f"📆 {event['event_date']}\n"
        f"🕒 {event['event_time']}\n"
        f"👥 Учасників: {members_count}"
    )
    
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я буду", callback_data=f"join_{event_id}")],
            [InlineKeyboardButton(text="👥 Учасники", callback_data=f"members_{event_id}")],
            [InlineKeyboardButton(text="❌ Не буду", callback_data=f"leave_{event_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="events")]
        ])
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
    await call.answer("✅ Ви записані")

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
    
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT users.clan_name
            FROM event_members
            JOIN users ON users.id = event_members.user_id
            WHERE event_members.event_id=? AND event_members.status='joined'
        """, (event_id,))
        members = cursor.fetchall()
    
    text = "👥 Учасники події:\n\n"
    text += "\n".join([f"• {member['clan_name']}" for member in members]) if members else "Поки ніхто не записався."
    
    await call.message.edit_text(text, reply_markup=back_button())

@dp.callback_query(lambda c: c.data == "create_event")
async def create_event(call: CallbackQuery):
    if not check_menu_owner(call):
        return
    
    if not is_admin(call.from_user.id):
        return
    
    actions[call.from_user.id] = {"type": "create_event_title"}
    await call.message.edit_text("📅 Введіть назву події:", reply_markup=cancel_button())

# =========================
# 🎯 РЕАКЦІЯ НА ТЕГИ
# =========================

@dp.message()
async def handle_mentions(message: Message):
    # Перевіряємо згадування бота
    bot_mentioned = False
    
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                text = message.text[entity.offset:entity.offset + entity.length]
                if text.lower() in ["@" + (await bot.get_me()).username.lower()]:
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
        
        user = get_user(message.from_user.id)
        if user:
            add_log(f"{user['clan_name']} тегнув бота, отримав відповідь: {reply}")
        else:
            add_log(f"Користувач {message.from_user.id} тегнув бота, отримав відповідь: {reply}")
        
        return
    
    await handle_text_commands(message)

async def handle_text_commands(message: Message):
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
        
        msg = await message.answer("✅ Реєстрація завершена", reply_markup=main_menu(user_id))
        menu_owner[msg.message_id] = user_id
        return
    
    # Зміна свого ніку
    if action["type"] == "my_nick":
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET clan_name=? WHERE id=?", (text, user_id))
            conn.commit()
        
        add_log(f"{get_user(user_id)['clan_name']} змінив свій нік")
        actions.pop(user_id, None)
        
        msg = await message.answer("✅ Ваш нік змінено", reply_markup=main_menu(user_id))
        menu_owner[msg.message_id] = user_id
        return
    
    # Зміна ніку іншого бійця
    if action["type"] == "fighter_nick":
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET clan_name=? WHERE id=?", (text, action["target"]))
            conn.commit()
        
        target = get_user(action["target"])
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} змінив нік бійцю {target['clan_name']}")
        actions.pop(user_id, None)
        
        msg = await message.answer("✅ Нік бійця змінено", reply_markup=main_menu(user_id))
        menu_owner[msg.message_id] = user_id
        return
    
    # Обмін балів (тільки для Лідера/Радників)
    if action["type"] == "exchange_points":
        if not can_exchange(user_id):
            await message.answer("❌ Тільки Лідер або Радник можуть обмінювати бали!")
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
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET coins_received = coins_received + ? WHERE id=?", (coins, user_id))
                conn.commit()
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO exchange_requests(user_id, points, coins, created, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, points, coins, int(time.time()), 'completed'))
                conn.commit()
            
            add_log(f"{user['clan_name']} обміняв {points} балів на {coins} монет")
            
            await message.answer(
                f"✅ Обмін виконано!\n\n"
                f"Витрачено балів: {points}\n"
                f"Отримано монет: {coins}\n"
                f"Залишилось балів: {get_user(user_id)['points']}",
                reply_markup=main_menu(user_id)
            )
            actions.pop(user_id, None)
            
        except ValueError:
            await message.answer("❌ Введіть число.")
        return
    
    # Списання монет (тільки для Лідера/Радників)
    if action["type"] == "remove_coins":
        if not is_leader_or_advisor(user_id):
            await message.answer("❌ Тільки Лідер або Радник можуть списувати монети!")
            return
        
        try:
            coins = int(text)
            if coins <= 0:
                await message.answer("❌ Кількість монет має бути більшою за 0.")
                return
            
            target = get_user(action["target"])
            if not target:
                await message.answer("❌ Користувача не знайдено.")
                return
            
            if target['coins_received'] < coins:
                await message.answer(f"❌ У гравця {target['clan_name']} є тільки {target['coins_received']} монет.")
                return
            
            with db.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET coins_received = coins_received - ? WHERE id=?", (coins, target['id']))
                conn.commit()
            
            admin = get_user(user_id)
            add_log(f"{admin['clan_name']} списав {coins} монет у {target['clan_name']}")
            
            await message.answer(
                f"✅ Списання виконано!\n\n"
                f"Гравець: {target['clan_name']}\n"
                f"Списано монет: {coins}\n"
                f"Залишилось монет: {get_user(target['id'])['coins_received']}",
                reply_markup=main_menu(user_id)
            )
            actions.pop(user_id, None)
            
        except ValueError:
            await message.answer("❌ Введіть число.")
        return
    
    # Оголошення
    if action["type"] == "announce":
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE clan_name IS NOT NULL")
            users = cursor.fetchall()
        
        success = 0
        for user in users:
            try:
                await bot.send_message(user['id'], f"📢 Оголошення:\n\n{text}")
                success += 1
                await asyncio.sleep(0.1)
            except:
                pass
        
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} відправив оголошення ({success} отримали)")
        
        actions.pop(user_id, None)
        await message.answer(
            f"✅ Оголошення відправлено {success} користувачам.",
            reply_markup=main_menu(user_id)
        )
        return
    
    # Створення події
    if action["type"] == "create_event_title":
        actions[user_id] = {"type": "create_event_description", "title": text}
        await message.answer("📝 Введіть опис події:")
        return
    
    if action["type"] == "create_event_description":
        actions[user_id] = {
            "type": "create_event_date",
            "title": action["title"],
            "description": text
        }
        await message.answer("📅 Введіть дату події\nПриклад: 10.07.2026")
        return
    
    if action["type"] == "create_event_date":
        actions[user_id] = {
            "type": "create_event_time",
            "title": action["title"],
            "description": action["description"],
            "event_date": text
        }
        await message.answer("🕒 Введіть час події.\n\nПриклад: 19:30")
        return
    
    if action["type"] == "create_event_time":
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events(title, description, event_date, event_time, created)
                VALUES (?, ?, ?, ?, ?)
            """, (action["title"], action["description"], action["event_date"], text, int(time.time())))
            conn.commit()
        
        admin = get_user(user_id)
        add_log(f"{admin['clan_name']} створив подію {action.get('title', 'Без назви')}")
        
        actions.pop(user_id, None)
        await message.answer("✅ Подію створено", reply_markup=main_menu(user_id))
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
                cursor.execute("SELECT * FROM events")
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
                                f"⏰ До події «{event['title']}» залишилось 15 хвилин."
                            )
                            await asyncio.sleep(0.1)
                        except:
                            pass
                    
                    with db.connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE events SET remind15=1 WHERE id=?", (event['id'],))
                        conn.commit()
                
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
                                f"📢 Подія «{event['title']}» розпочалась! +10 балів за участь!"
                            )
                            add_points(user['user_id'], 10)
                            add_event_visit(user['user_id'])
                            await asyncio.sleep(0.1)
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
    print("BOT STARTING...")
    await setup_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    print("POLLING STARTED")
    asyncio.create_task(event_notifications())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
