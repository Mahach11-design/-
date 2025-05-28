import telebot
from telebot import types
import json
import os
from telethon import TelegramClient, events, errors
import asyncio
import re
import threading
from googletrans import Translator
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Инициализация бота
BOT_TOKEN = '8188485836:AAGeVVcISeIHlosZ-eLDOMSladaAevFEO8g'
bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация переводчика
translator = Translator()

# Словарь для хранения данных пользователей
user_data = {}

def save_user_data():
    """Сохраняет данные пользователей в красивом формате"""
    with open('user_data.json', 'w', encoding='utf-8') as f:
        json.dump(user_data, f, indent=4, ensure_ascii=False)

# Загрузка данных пользователей при запуске
if os.path.exists('user_data.json'):
    with open('user_data.json', 'r', encoding='utf-8') as f:
        user_data = json.load(f)
        save_user_data()

# Функции для клавиатур
def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton('🔑 Подключить аккаунт'))
    keyboard.row(types.KeyboardButton('❌ Отключить аккаунт'))
    keyboard.row(types.KeyboardButton('📝 Инструкция по получению API'))
    keyboard.row(types.KeyboardButton('ℹ️ О боте'))
    return keyboard

def create_cancel_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton('❌ Отмена'))
    return keyboard

def create_code_keyboard(current_code):
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(str(i), callback_data=f'code_digit_{i}') for i in range(1, 10)]
    buttons.append(InlineKeyboardButton('0', callback_data='code_digit_0'))
    buttons.append(InlineKeyboardButton('⌫', callback_data='code_backspace'))
    buttons.append(InlineKeyboardButton('✅', callback_data='code_confirm'))
    keyboard.add(*buttons[:3])
    keyboard.add(*buttons[3:6])
    keyboard.add(*buttons[6:9])
    keyboard.add(buttons[9], buttons[10], buttons[11])
    return keyboard

# Функции для userbot
async def code_callback(user_id):
    code_file = f"codes/{user_id}.txt"
    print(f"[main.py] Ожидание кода подтверждения для пользователя {user_id}...")
    while not os.path.exists(code_file):
        await asyncio.sleep(1)
    with open(code_file, 'r') as f:
        code = f.read().strip()
    os.remove(code_file)
    print(f"[main.py] Код подтверждения получен для user_id={user_id}: {code}")
    return code

async def run_userbot(api_id, api_hash, phone, session_name, user_id):
    client = TelegramClient(session_name, api_id, api_hash)

    @client.on(events.NewMessage(outgoing=True))
    async def handle_new_message(event):
        if event.text.startswith('en:'):
            text_to_translate = event.text[3:].strip()
            try:
                translation = translator.translate(text_to_translate, src='en', dest='ru')
                new_text = (
                    f"🇬🇧 en: {text_to_translate}\n\n"
                    f"🇷🇺 ru: {translation.text}"
                )
                await event.edit(new_text)
                print(f"[main.py] Сообщение переведено и отредактировано для user_id={user_id}")
            except Exception as e:
                print(f"[main.py] Error translating message for user_id={user_id}: {e}")

    while True:
        try:
            await client.start(phone=phone, code_callback=lambda: code_callback(user_id))
            print(f"[main.py] Userbot started for {phone} (user_id={user_id})")
            await client.run_until_disconnected()
            break
        except errors.SessionPasswordNeededError:
            print(f"[main.py] Для user_id={user_id} требуется двухфакторная аутентификация (пароль). Поддержка пароля не реализована.")
            break
        except errors.PhoneCodeInvalidError:
            print(f"[main.py] ❌ Введён неверный код для user_id={user_id}. Ожидание нового кода...")
            continue
        except Exception as e:
            print(f"[main.py] Ошибка авторизации для user_id={user_id}: {e}")
            break

def start_userbots():
    """Запускает userbot'ы для всех пользователей в отдельном потоке"""
    async def run_all_userbots():
        for user_id, data in user_data.items():
            if all(key in data for key in ['api_id', 'api_hash', 'phone']):
                session_name = f'sessions/user_{user_id}'
                print(f"[main.py] Запуск userbot для user_id={user_id}, phone={data['phone']}")
                await run_userbot(
                    data['api_id'],
                    data['api_hash'],
                    data['phone'],
                    session_name,
                    user_id
                )

    def run_async():
        asyncio.run(run_all_userbots())

    thread = threading.Thread(target=run_async)
    thread.daemon = True
    thread.start()

# Обработчики команд бота
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in user_data:
        user_data[user_id] = {'state': 'main'}
        save_user_data()
    
    welcome_text = (
        "👋 Привет! Я бот для автоматического перевода сообщений.\n\n"
        "🔹 Я могу переводить сообщения, начинающиеся с 'en:' с английского на русский.\n"
        "🔹 Для работы мне нужно подключить ваш аккаунт Telegram.\n\n"
        "Выберите действие из меню ниже:"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == '🔑 Подключить аккаунт')
def connect_account(message):
    user_id = str(message.from_user.id)
    user_data[user_id] = {'state': 'waiting_api_id'}
    save_user_data()
    
    text = (
        "📱 Для подключения аккаунта мне нужны ваши API данные.\n\n"
        "1️⃣ Введите ваш API ID (это число):"
    )
    bot.send_message(message.chat.id, text, reply_markup=create_cancel_keyboard())

@bot.message_handler(func=lambda message: message.text == '❌ Отключить аккаунт')
def disconnect_account(message):
    user_id = str(message.from_user.id)
    if user_id in user_data and 'api_id' in user_data[user_id]:
        del user_data[user_id]
        save_user_data()
        bot.send_message(message.chat.id, "✅ Аккаунт успешно отключен!", reply_markup=create_main_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ У вас нет подключенного аккаунта.", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == '📝 Инструкция по получению API')
def show_api_instructions(message):
    instructions = (
        "📱 Как получить API ID и API Hash:\n\n"
        "1️⃣ Перейдите на сайт https://my.telegram.org\n"
        "2️⃣ Войдите в свой аккаунт Telegram\n"
        "3️⃣ Перейдите в 'API development tools'\n"
        "4️⃣ Создайте новое приложение:\n"
        "   • App title: любое название\n"
        "   • Short name: любое короткое название\n"
        "   • Platform: Desktop\n"
        "   • Description: можно оставить пустым\n"
        "5️⃣ После создания вы получите:\n"
        "   • api_id (это число)\n"
        "   • api_hash (это строка из букв и цифр)\n\n"
        "⚠️ ВАЖНО: Никому не передавайте эти данные!\n"
        "Они дают доступ к вашему аккаунту Telegram."
    )
    bot.send_message(message.chat.id, instructions, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == 'ℹ️ О боте')
def about_bot(message):
    about_text = (
        "🤖 О боте:\n\n"
        "Этот бот автоматически переводит сообщения с английского на русский.\n\n"
        "🔹 Как это работает:\n"
        "1. Подключите свой аккаунт Telegram\n"
        "2. В любом чате напишите сообщение, начиная с 'en:'\n"
        "3. Бот автоматически переведет его на русский\n\n"
        "🔹 Пример:\n"
        "Вы пишете: 'en: Hello, how are you?'\n"
        "Бот переведет: 'Привет, как дела?'\n\n"
        "🔹 Особенности:\n"
        "• Работает во всех чатах\n"
        "• Мгновенный перевод\n"
        "• Поддержка длинных сообщений\n"
        "• Безопасное хранение данных"
    )
    bot.send_message(message.chat.id, about_text, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def cancel_action(message):
    user_id = str(message.from_user.id)
    user_data[user_id] = {'state': 'main'}
    save_user_data()
    bot.send_message(message.chat.id, "❌ Действие отменено.", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.from_user.id)
    print(f"[main.py] handle_message: user_id={user_id}, state={user_data.get(user_id, {}).get('state')}")
    
    if user_id not in user_data:
        user_data[user_id] = {'state': 'main'}
        save_user_data()
    
    if user_data[user_id]['state'] == 'waiting_api_id':
        try:
            api_id = int(message.text)
            user_data[user_id]['api_id'] = api_id
            user_data[user_id]['state'] = 'waiting_api_hash'
            print(f"[main.py] API ID принят для user_id={user_id}: {api_id}")
            bot.send_message(message.chat.id, "✅ API ID принят!\n\nТеперь введите ваш API Hash:")
        except ValueError:
            print(f"[main.py] Некорректный API ID от user_id={user_id}: {message.text}")
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный API ID (это должно быть число):")
    
    elif user_data[user_id]['state'] == 'waiting_api_hash':
        api_hash = message.text.strip()
        if re.match(r'^[a-f0-9]{32}$', api_hash):
            user_data[user_id]['api_hash'] = api_hash
            user_data[user_id]['state'] = 'waiting_phone'
            save_user_data()
            print(f"[main.py] API Hash принят для user_id={user_id}: {api_hash}")
            bot.send_message(message.chat.id, "✅ API Hash принят!\n\nТеперь введите ваш номер телефона в международном формате (например, +79001234567):")
        else:
            print(f"[main.py] Некорректный API Hash от user_id={user_id}: {api_hash}")
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный API Hash (32 символа, только буквы a-f и цифры):")
    
    elif user_data[user_id]['state'] == 'waiting_phone':
        phone = message.text.strip()
        if re.match(r'^\+[0-9]{11,15}$', phone):
            user_data[user_id]['phone'] = phone
            user_data[user_id]['state'] = 'waiting_code_buttons'
            user_data[user_id]['code_input'] = ''
            save_user_data()
            print(f"[main.py] Телефон принят для user_id={user_id}: {phone}")
            bot.send_message(
                message.chat.id,
                f"Введите код, нажимая на кнопки.\nКод: ",
                reply_markup=create_code_keyboard('')
            )
            # Запускаем userbot в отдельном потоке
            start_userbots()
        else:
            print(f"[main.py] Некорректный телефон от user_id={user_id}: {phone}")
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный номер телефона в международном формате (например, +79001234567):")
    elif user_data[user_id]['state'] == 'waiting_code':
        bot.send_message(message.chat.id, "Пожалуйста, используйте кнопки для ввода кода.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('code_'))
def code_input_callback(call):
    user_id = str(call.from_user.id)
    code = user_data[user_id].get('code_input', '')
    action = call.data
    if action.startswith('code_digit_'):
        digit = action.split('_')[-1]
        if len(code) < 10:
            code += digit
    elif action == 'code_backspace':
        code = code[:-1]
    elif action == 'code_confirm':
        if len(code) >= 3:
            os.makedirs('codes', exist_ok=True)
            with open(f'codes/{user_id}.txt', 'w') as f:
                f.write(code)
            print(f"[main.py] Код подтверждения записан для user_id={user_id}: {code}")
            user_data[user_id]['state'] = 'main'
            user_data[user_id]['code_input'] = ''
            save_user_data()
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f'✅ Код {code} принят! Авторизация продолжается...'
            )
            return
        else:
            bot.answer_callback_query(call.id, 'Код слишком короткий!')
    user_data[user_id]['code_input'] = code
    save_user_data()
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f'Введите код, нажимая на кнопки.\nКод: {code}',
        reply_markup=create_code_keyboard(code)
    )

if __name__ == '__main__':
    # Создаем необходимые директории
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    if not os.path.exists('codes'):
        os.makedirs('codes')
    
    # Запускаем userbot'ы в отдельном потоке
    start_userbots()
    
    print("Бот запущен...")
    bot.polling(none_stop=True) 