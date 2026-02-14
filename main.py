import os
import telebot
import requests
import urllib.parse
from flask import Flask, request
from telebot import types
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_URL = "https://t.me/testchannel1234524234"
CHANNEL_ID = "8125791280"  # Обязательно добавь бота в админы канала!

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎁 Сгенерировать валентинку", "✍️ Расписать свою")
    return markup

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    text = (
        "❤️ **Привет! Я — твой генератор валентинок.**\n\n"
        "Создаю уникальные открытки с помощью ИИ и помогаю красиво подписать твои шаблоны.\n\n"
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
        bot.send_message(call.message.chat.id, "Выбирай действие:", reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "Нужна подписка на канал! 🛑", show_alert=True)

# --- ЛОГИКА 1: ГЕНЕРАЦИЯ ---
@bot.message_handler(func=lambda m: m.text == "🎁 Сгенерировать валентинку")
def gen_start(message):
    user_states[message.chat.id] = {'step': 'prompt'}
    bot.send_message(message.chat.id, "📝 Опиши, что должно быть на картинке?\n(Например: розовый фламинго в сердечках)", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'prompt')
def gen_prompt(message):
    user_states[message.chat.id].update({'prompt': message.text, 'step': 'from'})
    bot.send_message(message.chat.id, "💌 От кого?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'from')
def gen_from(message):
    user_states[message.chat.id].update({'from': message.text, 'step': 'to'})
    bot.send_message(message.chat.id, "📩 Кому?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'to')
def gen_final(message):
    chat_id = message.chat.id
    user_states[chat_id]['to'] = message.text
    data = user_states[chat_id]
    
    bot.send_message(chat_id, "⏳ **Нейросеть рисует вашу любовь...**", parse_mode="Markdown")

    # Используем Pollinations AI (Бесплатно)
    # Формируем промпт: описание + подпись
    full_prompt = f"Valentine's day card, {data['prompt']}, romantic aesthetic, high quality, digital art, soft lighting"
    encoded_prompt = urllib.parse.quote(full_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

    # Создаем подпись через Pillow поверх сгенерированной картинки
    try:
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        
        # Накладываем текст (От кого / Кому)
        img = add_text_to_image(img, data['from'], data['to'])
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)

        caption = f"💖 [Сгенерировать валентинку](https://t.me/{bot.get_me().username})"
        bot.send_photo(chat_id, bio, caption=caption, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.send_message(chat_id, "Ошибка генерации. Попробуй позже.")
    
    user_states[chat_id] = {}

# --- ЛОГИКА 2: РАСПИСАТЬ (СВОЁ ФОТО) ---
@bot.message_handler(func=lambda m: m.text == "✍️ Расписать свою")
def sign_start(message):
    user_states[message.chat.id] = {'step': 'photo'}
    bot.send_message(message.chat.id, "🖼 Пришли мне картинку-шаблон:", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'], func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'photo')
def sign_photo(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    user_states[message.chat.id].update({'photo': downloaded_file, 'step': 'sign_from'})
    bot.send_message(message.chat.id, "💌 От кого?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'sign_from')
def sign_from(message):
    user_states[message.chat.id].update({'from': message.text, 'step': 'sign_to'})
    bot.send_message(message.chat.id, "📩 Кому?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('step') == 'sign_to')
def sign_final(message):
    chat_id = message.chat.id
    user_states[chat_id]['to'] = message.text
    data = user_states[chat_id]
    
    bot.send_message(chat_id, "✍️ **Подписываю открытку...**", parse_mode="Markdown")
    
    img = Image.open(BytesIO(data['photo']))
    img = add_text_to_image(img, data['from'], data['to'])
    
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)

    caption = f"💖 [Сгенерировать валентинку](https://t.me/{bot.get_me().username})"
    bot.send_photo(chat_id, bio, caption=caption, parse_mode="Markdown", reply_markup=get_main_menu())
    user_states[chat_id] = {}

# --- ФУНКЦИЯ РИСОВАНИЯ ТЕКСТА ---
def add_text_to_image(img, from_name, to_name):
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Шрифт должен быть в корне проекта!
    try:
        font_path = "font.ttf"
        font = ImageFont.truetype(font_path, int(height / 18))
    except:
        font = ImageFont.load_default()

    text = f"От: {from_name} ❤️ Кому: {to_name}"
    
    # Центрируем текст внизу
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # Рисуем подложку (тень) для читаемости
    x, y = (width - tw) / 2, height - th - (height * 0.08)
    for off in range(-2, 3):
        draw.text((x+off, y+off), text, font=font, fill="black")
    
    draw.text((x, y), text, font=font, fill="white")
    return img

# --- FLASK SERVER ---
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
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
