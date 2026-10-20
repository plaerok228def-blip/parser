# language: Python, file: parser_bot.py, target: Python 3.10+
import telebot
from telebot import types
import sqlite3
import random
import time

# --- НАСТРОЙКИ ---
BOT_TOKEN = "СЮДА_ВСТАВЬ_ТОКЕН_НОВОГО_БОТА_ПАРСЕРА"
ADMIN_ID = 6484025560 # Твой ID

bot = telebot.TeleBot(BOT_TOKEN)

# --- БАЗА ДАННЫХ (Чтобы не выдавать одних и тех же людей) ---
conn = sqlite3.connect('issued_users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS issued (
        username TEXT PRIMARY KEY,
        issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# --- БАЗА ЮЗЕРНЕЙМОВ (Имитация парсинга) ---
# Генерируем 4000 ников при запуске
def generate_pool():
    first_names_male = ["mason", "cole", "ethan", "liam", "noah", "lucas", "logan", "jack", "harry", "george", "nazar", "dima", "sasha", "max", "ivan"]
    first_names_female = ["masha", "dasha", "katya", "yulya", "anya", "alina", "lera", "nastya", "olya", "kristina", "alisa", "sonya", "liza"]
    
    pool = {"male": [], "female": []}
    for _ in range(2000):
        pool["male"].append(f"@{random.choice(first_names_male)}_{random.randint(10, 99999)}")
    for _ in range(2000):
        pool["female"].append(f"@{random.choice(first_names_female)}_{random.randint(10, 99999)}")
    return pool

USER_POOL = generate_pool()

# --- СПИСОК ПОДАРКОВ ---
GIFTS = [
    "Bunny Muffin", "Mirage Lamp", "Heart Locket", "Durov's Cap", 
    "Artisan Brick", "Sharp Tongue", "Blue Muffin", "Crystal Ball",
    "Pink Socks", "Teddy Bear", "Rose", "Cupid's Heart",
    "Santa Hat", "Skull", "Plush Pepe", "Bonded Ring",
    "Asteroid", "Whip Cupcake", "Perfume", "Signet Ring"
]

user_state = {}

# --- БАЗА ДАННЫХ ---
def is_issued(username):
    cursor.execute("SELECT 1 FROM issued WHERE username = ?", (username,))
    return cursor.fetchone() is not None

def mark_as_issued(username):
    cursor.execute("INSERT OR IGNORE INTO issued (username) VALUES (?)", (username,))
    conn.commit()

def get_unique_users(gender, count):
    pool = USER_POOL.get(gender, [])
    random.shuffle(pool)
    
    result = []
    for user in pool:
        if len(result) >= count:
            break
        if not is_issued(user):
            result.append(user)
            mark_as_issued(user)
            
    return result

# --- ХЕНДЛЕРЫ ---
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔍 Начать парсинг")
    bot.send_message(message.chat.id, "Бот-парсер готов. Нажми кнопку ниже:", reply_markup=kb)

@bot.message_handler(func=lambda message: message.text == "🔍 Начать парсинг")
def start_parsing(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    user_state[message.from_user.id] = {"step": "gender"}
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("Мужчины", "Девушки")
    bot.send_message(message.chat.id, "Кого ищем?", reply_markup=kb)

@bot.message_handler(func=lambda message: message.from_user.id in user_state and user_state[message.from_user.id].get("step") == "gender")
def choose_gender(message):
    if message.text == "Мужчины":
        user_state[message.from_user.id]["gender"] = "male"
    elif message.text == "Девушки":
        user_state[message.from_user.id]["gender"] = "female"
    else:
        return
        
    user_state[message.from_user.id]["step"] = "gift"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for gift in GIFTS:
        buttons.append(types.InlineKeyboardButton(gift, callback_data=f"gift|{gift}"))
    kb.add(*buttons)
    
    bot.send_message(message.chat.id, "Выбери подарок для парсинга:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gift|"))
def choose_gift(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    gift_name = call.data.split("|")[1]
    user_state[call.from_user.id]["gift"] = gift_name
    user_state[call.from_user.id]["step"] = "count"
    
    bot.answer_callback_query(call.id, f"Выбран: {gift_name}")
    bot.send_message(
        call.message.chat.id,
        f"Подарок: <b>{gift_name}</b>\n\nСколько человек нужно выдать? (введи число от 1 до 50):",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_state and user_state[message.from_user.id].get("step") == "count")
def get_count(message):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 50:
            bot.send_message(message.chat.id, "Введи число от 1 до 50:")
            return
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введи число:")
        return
        
    state = user_state.pop(message.from_user.id)
    gender = state["gender"]
    gift_name = state["gift"]
    
    users = get_unique_users(gender, count)
    
    if not users:
        bot.send_message(message.chat.id, "❌ Свободных юзеров в базе не осталось. База закончилась.")
        return

    result_lines = []
    for user in users:
        clean_name = gift_name.replace(" ", "").replace("'", "")
        random_id = random.randint(10000, 99999)
        link = f"https://t.me/nft/{clean_name}-{random_id}"
        result_lines.append(f"{user} | {link}")
        
    result_text = "\n".join(result_lines)
    
    bot.send_message(
        message.chat.id,
        f"✅ <b>Успешно спарсено!</b>\nПодарок: {gift_name}\nВсего найдено: {len(users)} чел.\n\n{result_text}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔍 Начать парсинг")
    bot.send_message(message.chat.id, "Готово. Жми кнопку для нового парсинга.", reply_markup=kb)

if __name__ == "__main__":
    print("Бот-парсер запущен!")
    bot.infinity_polling()