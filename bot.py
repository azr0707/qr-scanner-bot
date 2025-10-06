import logging
import asyncio
import qrcode
import io
import uuid
import urllib.parse
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = "8468433983:AAEhRMkYZr_lXTLyzzFiAnJWtZnBVB_2gQI"
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AdminStates(StatesGroup):
    waiting_for_partner_id = State()
    waiting_for_company_name = State()

qr_codes_db = {}
user_qr_history = {}
partners_db = {}
partner_stats = {}
ADMINS = []

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def register_partner(user_id: int, company_name: str = "Магазин"):
    partners_db[user_id] = {
        'company_name': company_name,
        'registered_at': datetime.now(),
        'is_active': True,
        'added_by_admin': True
    }
    partner_stats[user_id] = {
        'today_checks': 0,
        'today_success': 0,
        'total_checks': 0,
        'total_success': 0
    }
    return partners_db[user_id]

def generate_qr_code(user_id: int, discount_type: str = "10%", valid_minutes: int = 5):
    qr_id = str(uuid.uuid4())[:8].upper()
    created_at = datetime.now()
    expires_at = created_at + timedelta(minutes=valid_minutes)
    
    qr_data = f"DISCOUNT:{qr_id}:USER:{user_id}:TYPE:{discount_type}:EXP:{expires_at.timestamp()}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    qr_codes_db[qr_id] = {
        'user_id': user_id,
        'created_at': created_at,
        'expires_at': expires_at,
        'is_used': False,
        'used_at': None,
        'discount_type': discount_type,
        'qr_data': qr_data
    }
    
    if user_id not in user_qr_history:
        user_qr_history[user_id] = []
    user_qr_history[user_id].append(qr_id)
    
    return qr_id, bio, expires_at

def validate_qr_data_from_deeplink(qr_data: str, partner_id: int):
    """Валидация QR-кода из deep link (работает с полными данными без проверки в базе)"""
    try:
        logger.info(f"Validating QR data from deep link: {qr_data}")
        
        parts = qr_data.split(':')
        if len(parts) < 6 or parts[0] != 'DISCOUNT':
            return {'valid': False, 'reason': 'Неверный формат QR-кода'}
        
        qr_id = parts[1]
        user_id = int(parts[3])  # USER ID
        discount_type = parts[5]  # TYPE
        exp_timestamp = float(parts[7])  # EXP timestamp
        
        expires_at = datetime.fromtimestamp(exp_timestamp)
        
        # Проверяем срок действия
        if datetime.now() > expires_at:
            return {'valid': False, 'reason': 'QR-код просрочен'}
        
        # Проверяем, не использован ли уже этот QR-код
        if qr_id in qr_codes_db and qr_codes_db[qr_id]['is_used']:
            return {'valid': False, 'reason': 'QR-код уже использован'}
        
        # Отмечаем как использованный
        if qr_id not in qr_codes_db:
            # Создаем запись в базе, если её нет
            qr_codes_db[qr_id] = {
                'user_id': user_id,
                'created_at': datetime.fromtimestamp(float(parts[9]) if len(parts) > 9 else exp_timestamp - 300),
                'expires_at': expires_at,
                'is_used': True,
                'used_at': datetime.now(),
                'discount_type': discount_type,
                'qr_data': qr_data,
                'used_by_partner': partner_id
            }
        else:
            qr_codes_db[qr_id]['is_used'] = True
            qr_codes_db[qr_id]['used_at'] = datetime.now()
            qr_codes_db[qr_id]['used_by_partner'] = partner_id
        
        # Обновляем статистику партнера
        if partner_id in partner_stats:
            partner_stats[partner_id]['today_checks'] += 1
            partner_stats[partner_id]['today_success'] += 1
            partner_stats[partner_id]['total_checks'] += 1
            partner_stats[partner_id]['total_success'] += 1
        
        return {
            'valid': True,
            'qr_id': qr_id,
            'user_id': user_id,
            'discount_type': discount_type,
            'created_at': qr_codes_db[qr_id]['created_at']
        }
        
    except Exception as e:
        logger.error(f"Validation error from deep link: {e}")
        return {'valid': False, 'reason': f'Ошибка проверки: {str(e)}'}

def validate_qr_data(qr_data: str, partner_id: int):
    """Валидация QR-кода из WebApp (работает с базой данных)"""
    try:
        logger.info(f"Validating QR data: {qr_data}")
        
        parts = qr_data.split(':')
        if len(parts) < 6 or parts[0] != 'DISCOUNT':
            return {'valid': False, 'reason': 'Неверный формат QR-кода'}
        
        qr_id = parts[1]
        logger.info(f"QR ID from data: {qr_id}")
        
        if qr_id not in qr_codes_db:
            return {'valid': False, 'reason': 'QR-код не найден'}
        
        qr_info = qr_codes_db[qr_id]
        
        if qr_info['is_used']:
            return {'valid': False, 'reason': 'QR-код уже использован'}
        
        if datetime.now() > qr_info['expires_at']:
            return {'valid': False, 'reason': 'QR-код просрочен'}
        
        qr_codes_db[qr_id]['is_used'] = True
        qr_codes_db[qr_id]['used_at'] = datetime.now()
        qr_codes_db[qr_id]['used_by_partner'] = partner_id
        
        if partner_id in partner_stats:
            partner_stats[partner_id]['today_checks'] += 1
            partner_stats[partner_id]['today_success'] += 1
            partner_stats[partner_id]['total_checks'] += 1
            partner_stats[partner_id]['total_success'] += 1
        
        return {
            'valid': True,
            'qr_id': qr_id,
            'user_id': qr_info['user_id'],
            'discount_type': qr_info['discount_type'],
            'created_at': qr_info['created_at']
        }
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {'valid': False, 'reason': f'Ошибка проверки: {str(e)}'}

# ==================== ОБРАБОТКА DEEP LINK ИЗ СКАНЕРА ====================

async def check_qr_from_deeplink(message: types.Message, qr_data: str):
    """Обработка QR-кода из deep link с полными данными"""
    user_id = message.from_user.id
    logger.info(f"Deep link QR check with data: {qr_data} by user {user_id}")
    
    if user_id not in partners_db:
        await message.answer("❌ Сначала зарегистрируйтесь как партнер!")
        return
    
    # Проверяем QR-код с полными данными (специальная функция для deep link)
    result = validate_qr_data_from_deeplink(qr_data, user_id)
    
    if result['valid']:
        success_message = (
            f"✅ **QR-код ДЕЙСТВИТЕЛЕН!**\n\n"
            f"🎫 ID: `{result['qr_id']}`\n"
            f"🎁 Скидка: {result['discount_type']}\n"
            f"👤 ID клиента: `{result['user_id']}`\n"
            f"📅 Создан: {result['created_at'].strftime('%H:%M %d.%m.%Y')}\n\n"
            f"**✅ Скидка успешно применена!**"
        )
        await message.answer(success_message, parse_mode="Markdown")
        
        # Уведомляем клиента
        try:
            client_user_id = result['user_id']
            await bot.send_message(
                client_user_id,
                f"🎉 **Ваш QR-код использован!**\n\n"
                f"🎫 ID: `{result['qr_id']}`\n"
                f"🏪 Партнер: `{user_id}`\n"
                f"🕒 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                f"Скидка успешно применена! ✅",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.info(f"Не удалось уведомить клиента {result['user_id']}: {e}")
            
    else:
        error_message = (
            f"❌ **QR-код НЕДЕЙСТВИТЕЛЕН!**\n\n"
            f"📋 Причина: **{result['reason']}**\n\n"
            f"⚠️ **Не предоставляйте скидку!**"
        )
        await message.answer(error_message, parse_mode="Markdown")

# ==================== КОМАНДЫ ДЛЯ ОТЛАДКИ ====================

@dp.message_handler(commands=['myid', 'id'])
async def get_my_id(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    response = (
        f"🔍 **ВАШИ ДАННЫЕ:**\n\n"
        f"👤 User ID: `{user_id}`\n"
        f"📛 Username: `{username}`\n"
        f"🔑 Админ: `{'✅ ДА' if is_admin(user_id) else '❌ НЕТ'}`\n"
        f"🏪 Партнер: `{'✅ ДА' if user_id in partners_db else '❌ НЕТ'}`\n\n"
        f"💡 **Для получения админ-прав напишите:** /makeadmin"
    )
    await message.answer(response, parse_mode="Markdown")

@dp.message_handler(commands=['makeadmin'])
async def make_me_admin(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if username == "az64335":
        if user_id not in ADMINS:
            ADMINS.append(user_id)
            register_partner(user_id, "АДМИН")
        
        await message.answer(
            f"✅ **ВЫ СТАЛИ АДМИНОМ!**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📛 Username: `{username}`\n\n"
            f"**Теперь перезапустите бота:** /start\n\n"
            f"⚙️ **Админ-панель активирована!**",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Только пользователь az64335 может стать админом!")

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    try:
        # ПРОВЕРЯЕМ DEEP LINK ПАРАМЕТР С ПОЛНЫМИ ДАННЫМИ
        command_parts = message.text.split()
        if len(command_parts) > 1 and command_parts[1].startswith('full_'):
            # Декодируем полные данные QR-кода
            qr_data = urllib.parse.unquote(command_parts[1][5:])  # Убираем 'full_'
            logger.info(f"Received deep link QR data: {qr_data}")
            await check_qr_from_deeplink(message, qr_data)
            return
        
        user_id = message.from_user.id
        username = message.from_user.username
        
        if username == "az64335" and user_id not in ADMINS:
            ADMINS.append(user_id)
            register_partner(user_id, "АДМИН")
            logger.info(f"Автоматически добавлен админ: {user_id}")
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        if is_admin(user_id):
            keyboard.row("👤 Я клиент", "🏪 Я партнер")
            keyboard.row("⚙️ Админ-панель")
            
            await message.answer(
                "👋 **Добро пожаловать, АДМИН!** 🎯\n\n"
                "У вас есть полный доступ ко всем функциям системы.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            keyboard.row("👤 Я клиент", "🏪 Я партнер")
            
            await message.answer(
                "👋 Добро пожаловать в сервис эксклюзивных скидок!\n\n"
                "Выберите вашу роль:",
                reply_markup=keyboard
            )
        
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await message.answer("❌ Ошибка при запуске бота")

# ... остальной код остается без изменений ...

@dp.message_handler(content_types=['web_app_data'])
async def handle_web_app_data(message: types.Message):
    try:
        user_id = message.from_user.id
        logger.info(f"WebApp data received from user {user_id}")
        
        if user_id not in partners_db:
            await message.answer("❌ Сначала зарегистрируйтесь как партнер!")
            return
        
        qr_data = message.web_app_data.data
        logger.info(f"Received QR data from Web-App: {qr_data}")
        
        # Используем обычную валидацию для WebApp
        result = validate_qr_data(qr_data, user_id)
        
        if result['valid']:
            success_message = (
                f"✅ **QR-код ДЕЙСТВИТЕЛЕН!**\n\n"
                f"🎫 ID: `{result['qr_id']}`\n"
                f"🎁 Скидка: {result['discount_type']}\n"
                f"👤 ID клиента: `{result['user_id']}`\n"
                f"📅 Создан: {result['created_at'].strftime('%H:%M %d.%m.%Y')}\n\n"
                f"**✅ Скидка успешно применена!**\n"
                f"Можете предоставлять скидку клиенту! 🎉"
            )
            
            await message.answer(success_message, parse_mode="Markdown")
            
            try:
                client_user_id = result['user_id']
                await bot.send_message(
                    client_user_id,
                    f"🎉 **Ваш QR-код использован!**\n\n"
                    f"🎫 ID: `{result['qr_id']}`\n"
                    f"🏪 Партнер: `{user_id}`\n"
                    f"🕒 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                    f"Скидка успешно применена! ✅",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.info(f"Не удалось уведомить клиента {result['user_id']}: {e}")
                
        else:
            error_message = (
                f"❌ **QR-код НЕДЕЙСТВИТЕЛЕН!**\n\n"
                f"📋 Причина: **{result['reason']}**\n\n"
                f"⚠️ **Не предоставляйте скидку!**\n"
                f"Попросите клиента получить новый QR-код"
            )
            
            await message.answer(error_message, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Web app data error: {e}")
        error_text = (
            "❌ Ошибка при обработке QR-кода\n\n"
            "Возможные причины:\n"
            "• Неверный формат QR-кода\n"
            "• Проблемы с подключением\n"
            "• Ошибка в данных\n\n"
            "Попробуйте:\n"
            "• Сканировать еще раз\n"
            "• Использовать проверку по ID\n"
            "• Перезапустить сканер"
        )
        await message.answer(error_text)

# ... остальной код без изменений ...

async def on_startup(dp):
    logger.info("✅ Бот успешно запущен!")
    
    asyncio.create_task(cleanup_expired_qr_codes())
    asyncio.create_task(reset_daily_stats())
    
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                "🤖 **Бот запущен и готов к работе!**\n\n"
                "📊 Статистика системы:\n"
                f"• Партнеров: {len(partners_db)}\n"
                f"• Пользователей: {len(user_qr_history)}\n"
                f"• QR-кодов в базе: {len(qr_codes_db)}\n\n"
                "🔄 Фоновые задачи активированы!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

async def on_shutdown(dp):
    logger.info("🛑 Бот останавливается...")
    
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "🛑 Бот остановлен!")
        except:
            pass
    
    await bot.close()

if __name__ == '__main__':
    try:
        logger.info("🤖 Запуск QR-CODE BOT...")
        print("=" * 60)
        print("🚀 QR-CODE BOT WITH DEEP LINK SCANNER")
        print("📱 Version: 7.0 - FIXED DEEP LINK VALIDATION")
        print("👑 Admin: az64335")
        print("🔗 Scanner: https://azr0707.github.io/qr-scanner-bot/")
        print("📊 System ready for operation")
        print("=" * 60)
        
        executor.start_polling(
            dp,
            skip_updates=True,
            on_startup=on_startup,
            on_shutdown=on_shutdown
        )
        
    except KeyboardInterrupt:
        logger.info("⏹ Остановка по команде пользователя")
        print("\n⏹ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {e}")
    finally:
        logger.info("🛑 Бот полностью остановлен")
        print("🛑 Бот полностью остановлен") остановлен")