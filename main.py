import os
import telebot
import requests
import urllib.parse
import random
import traceback
import textwrap
from flask import Flask, request
from telebot import types
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = "8125791280" 
CHANNEL_URL = "https://t.me/testchannel1234524234"

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}

# --- ГЕНЕРАТОР УМНЫХ ПОЗДРАВЛЕНИЙ ---
def generate_ai_wish(from_user, to_user):
    wishes = [
        f"Пусть эта искра между вами превратится в вечное пламя. {to_user}, ты — вдохновение!",
        f"В этом мире полном хаоса, ты — мой островок спокойствия. С любовью, {from_user}.",
        f"Для самой прекрасной души. Пусть каждый твой день будет наполнен светом.",
        f"Любовь не знает границ. {to_user}, ты — моё самое главное приключение!",
        f"Сквозь пространство и время, мое сердце выбирает тебя. С праздником!"
    ]
    return random.choice(wishes)

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Проверка подписки: {e}")
        return False

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎁 Сгенерировать валентинку", "✍️ Расписать свою")
    return markup

# --- ОБРАБОТКА КОМАНД ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    text = (
        "❤️ **Привет! Я — твой AI-генератор валентинок.**\n\n"
        "Я создаю уникальные открытки и помогаю оформить твои фото в стиле Digital Art.\n\n"
        "✨ Чтобы начать, подпишись на наш канал!"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "Доступ разрешен! ❤️")
        bot.send_message(call.message.chat.id, "Что создадим сегодня?", reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "Подпишись, чтобы пользоваться ИИ! 🛑", show_alert=True)

# --- ЛОГИКА ГЕНЕРАЦИИ (С ПЕРЕБОРОМ МОДЕЛЕЙ) ---
@bot.message_handler(func=lambda m: m.text == "🎁 Сгенерировать валентинку")
def gen_start(message):
    user_states[message.chat.id] = {'step': 'prompt'}
    bot.send_message(message.chat.id, "📝 Что изобразить? (Например: котята в космосе)", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'prompt')
def gen_prompt(message):
    user_states[message.chat.id].update({'prompt': message.text, 'step': 'from'})
    bot.send_message(message.chat.id, "💌 Твоё имя (От кого)?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'from')
def gen_from(message):
    user_states[message.chat.id].update({'from': message.text, 'step': 'to'})
    bot.send_message(message.chat.id, "📩 Имя получателя (Кому)?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'to')
def gen_final(message):
    chat_id = message.chat.id
    user_states[chat_id]['to'] = message.text
    data = user_states[chat_id]
    
    bot.send_message(chat_id, "🎨 **Нейросеть начала работу...**", parse_mode="Markdown")

    encoded_prompt = urllib.parse.quote(f"Valentine's day art, {data['prompt']}, masterpiece, cinematic lighting")
    
    # Список моделей для обхода ошибки 530
    models = ["flux", "turbo", "standard"]
    response = None

    try:
        for model in models:
            seed = random.randint(1, 999999)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model={model}&seed={seed}"
            print(f"LOG: Пробую модель {model}...")
            try:
                res = requests.get(url, timeout=30)
                if res.status_code == 200:
                    response = res
                    break
            except:
                continue

        if not response:
            raise Exception("Все сервера ИИ сейчас перегружены. Попробуй через минуту.")

        img = Image.open(BytesIO(response.content))
        img = add_text_to_image(img, data['from'], data['to'])
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)

        bot.send_photo(chat_id, bio, caption=f"💖 От {data['from']} для {data['to']}\n[Создать еще одну](https://t.me/{bot.get_me().username})", parse_mode="Markdown", reply_markup=get_main_menu())

    except Exception as e:
        print(f"❌ ERROR: {e}")
        bot.send_message(chat_id, f"⚠️ Ошибка: {e}")
    
    user_states[chat_id] = {}

# --- ЛОГИКА 2: РАСПИСАТЬ СВОЮ ---
@bot.message_handler(func=lambda m: m.text == "✍️ Расписать свою")
def sign_start(message):
    user_states[message.chat.id] = {'step': 'photo'}
    bot.send_message(message.chat.id, "🖼 Отправь мне фото или шаблон:", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'], func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'photo')
def sign_photo(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    user_states[message.chat.id].update({'photo': downloaded_file, 'step': 'sign_from'})
    bot.send_message(message.chat.id, "💌 Твоё имя?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'sign_from')
def sign_from(message):
    user_states[message.chat.id].update({'from': message.text, 'step': 'sign_to'})
    bot.send_message(message.chat.id, "📩 Имя получателя?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'sign_to')
def sign_final(message):
    chat_id = message.chat.id
    user_states[chat_id]['to'] = message.text
    data = user_states[chat_id]
    
    bot.send_message(chat_id, "✍️ **Дизайнер AI подписывает открытку...**")
    
    try:
        img = Image.open(BytesIO(data['photo']))
        img = add_text_to_image(img, data['from'], data['to'])
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)

        bot.send_photo(chat_id, bio, caption="Твоя идеальная валентинка готова! ❤️", reply_markup=get_main_menu())
    except Exception as e:
        bot.send_message(chat_id, "Ошибка обработки изображения.")
    
    user_states[chat_id] = {}

# --- ФУНКЦИЯ УМНОГО ДИЗАЙНА ТЕКСТА ---
def add_text_to_image(img, from_name, to_name):
    # Конвертируем в RGBA для прозрачности
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Шрифт
    try:
        font = ImageFont.truetype("font.ttf", int(height / 22))
        small_font = ImageFont.truetype("font.ttf", int(height / 30))
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Текст пожелания
    wish = generate_ai_wish(from_name, to_name)
    names_text = f"To: {to_name} | From: {from_name}"
    
    # Перенос строк
    wrapped_wish = textwrap.fill(wish, width=35)
    
    # Создаем "Стеклянную плашку" внизу (Blur-эффект имитации)
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    
    padding = 40
    rect_height = height // 4
    # Черная полупрозрачная плашка
    d.rectangle([0, height - rect_height, width, height], fill=(0, 0, 0, 160))
    
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    
    # Пишем текст
    y_text = height - rect_height + padding
    for line in wrapped_wish.split('\n'):
        draw.text((width // 2, y_text), line, font=font, fill="white", anchor="mm")
        y_text += int(height / 18)
    
    draw.text((width // 2, height - 40), names_text, font=small_font, fill="#ff4d4d", anchor="mm")
    
    return img.convert("RGB")

# --- СЕРВЕР ---
@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://valentink.onrender.com/' + TOKEN)
    return "Bot Online", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    server.run(host="0.0.0.0", port=port)
