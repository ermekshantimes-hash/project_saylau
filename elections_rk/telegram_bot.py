"""
Telegram бот для мониторинга выборов в РК
Позволяет получать результаты выборов в реальном времени
"""
import asyncio
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_BASE = "http://127.0.0.1:8001/api"

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def fetch_api(endpoint: str):
    """Запрос к API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}{endpoint}") as response:
                if response.status == 200:
                    return await response.json()
                return None
    except Exception as e:
        print(f"Ошибка запроса к API: {e}")
        return None

def format_number(num):
    """Форматирование числа с разделителями"""
    return f"{num:,}".replace(",", " ")

# === КОМАНДЫ БОТА ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_text = """
🗳️ **Добро пожаловать в бот мониторинга выборов РК!**

Я помогу вам получать актуальную информацию о результатах выборов в режиме реального времени.

**Доступные команды:**
/elections - Список выборов
/results - Общие результаты
/regions - Результаты по регионам
/analytics - Аналитика и статистика
/help - Помощь

Выберите выборы для начала работы:
    """
    
    # Загрузить список выборов
    elections = await fetch_api("/elections")
    
    if elections:
        keyboard = []
        for election in elections:
            keyboard.append([
                InlineKeyboardButton(
                    f"{election['name']} ({election['election_date']})", 
                    callback_data=f"election_{election['id']}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Не удалось загрузить список выборов. Проверьте соединение с сервером.")

async def elections_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /elections - список выборов"""
    elections = await fetch_api("/elections")
    
    if not elections:
        await update.message.reply_text("❌ Не удалось загрузить список выборов.")
        return
    
    keyboard = []
    for election in elections:
        keyboard.append([
            InlineKeyboardButton(
                f"{election['name']} ({election['election_date']})", 
                callback_data=f"election_{election['id']}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите выборы:", reply_markup=reply_markup)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /results - общие результаты"""
    if 'election_id' not in context.user_data:
        await update.message.reply_text("⚠️ Сначала выберите выборы командой /elections")
        return
    
    election_id = context.user_data['election_id']
    
    # Загрузить статистику
    summary = await fetch_api(f"/analytics/elections/{election_id}/summary")
    
    if not summary:
        await update.message.reply_text("❌ Не удалось загрузить результаты.")
        return
    
    # Формирование сообщения
    text = f"📊 **Общие результаты выборов**\n\n"
    text += f"📍 Всего голосов: **{format_number(summary['total_votes'])}**\n"
    text += f"📦 Обработано участков: **{summary['processed_precincts']} / {summary['total_precincts']}**\n"
    text += f"📈 Прогресс: **{round(summary['processed_precincts']/summary['total_precincts']*100, 1) if summary['total_precincts'] > 0 else 0}%**\n\n"
    
    text += "🏆 **ТОП-5 кандидатов:**\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, result in enumerate(summary['results'][:5]):
        text += f"{medals[i]} **{result['name']}**\n"
        text += f"   └ {format_number(result['votes'])} голосов ({result['percentage']}%)\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def show_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /regions - результаты по регионам"""
    if 'election_id' not in context.user_data:
        await update.message.reply_text("⚠️ Сначала выберите выборы командой /elections")
        return
    
    election_id = context.user_data['election_id']
    
    # Загрузить результаты по регионам
    region_data = await fetch_api(f"/analytics/elections/{election_id}/by_region")
    
    if not region_data or not region_data.get('regions'):
        await update.message.reply_text("❌ Не удалось загрузить результаты по регионам.")
        return
    
    # Формирование сообщения
    text = "🗺️ **Результаты по регионам:**\n\n"
    
    for region in region_data['regions'][:10]:  # Топ-10 регионов
        text += f"📍 **{region['region_name']}**\n"
        text += f"   Всего голосов: {format_number(region['total_votes'])}\n"
        if region['winner']:
            percentage = round(region['winner_votes'] / region['total_votes'] * 100, 2) if region['total_votes'] > 0 else 0
            text += f"   🏆 Победитель: {region['winner']}\n"
            text += f"   └ {format_number(region['winner_votes'])} ({percentage}%)\n"
        text += "\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /analytics - аналитика"""
    if 'election_id' not in context.user_data:
        await update.message.reply_text("⚠️ Сначала выберите выборы командой /elections")
        return
    
    election_id = context.user_data['election_id']
    
    # Загрузить сравнительную таблицу
    comparison = await fetch_api(f"/analytics/elections/{election_id}/comparison")
    
    if not comparison:
        await update.message.reply_text("❌ Не удалось загрузить аналитику.")
        return
    
    # Формирование сообщения
    text = "📊 **Сравнительная аналитика кандидатов:**\n\n"
    
    for i, candidate in enumerate(comparison['candidates'], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} **{candidate['name']}**\n"
        text += f"   └ Голосов: {format_number(candidate['total_votes'])}\n"
        text += f"   └ Побед на участках: {candidate['precincts_won']}\n"
        text += f"   └ Средний %: {candidate['avg_percentage']}%\n"
        if candidate.get('subject_type'):
            text += f"   └ Тип: {candidate['subject_type']}\n"
        text += "\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - помощь"""
    help_text = """
ℹ️ **Справка по использованию бота**

**Основные команды:**
/start - Начать работу с ботом
/elections - Выбрать выборы
/results - Общие результаты голосования
/regions - Результаты по регионам
/analytics - Детальная аналитика
/help - Эта справка

**Как пользоваться:**
1. Выберите выборы командой /elections
2. Используйте команды для просмотра результатов
3. Результаты обновляются в реальном времени

**О системе:**
Бот подключен к API открытой системы мониторинга выборов РК
Данные предоставляются с избирательных участков в реальном времени

По вопросам: @support
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# === ОБРАБОТЧИКИ CALLBACK ===

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("election_"):
        # Выбраны выборы
        election_id = int(data.split("_")[1])
        context.user_data['election_id'] = election_id
        
        # Загрузить информацию о выборах
        election = await fetch_api(f"/elections/{election_id}")
        
        if election:
            text = f"✅ Выбраны выборы:\n**{election['name']}**\n"
            text += f"📅 Дата: {election['election_date']}\n"
            text += f"📋 Тип: {election['election_type']}\n\n"
            text += "Используйте команды для просмотра результатов:\n"
            text += "/results - Общие результаты\n"
            text += "/regions - По регионам\n"
            text += "/analytics - Аналитика"
            
            await query.edit_message_text(text, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ошибка загрузки информации о выборах")

# === MAIN ===

def main():
    """Запуск бота"""
    
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ ВНИМАНИЕ: Необходимо установить TELEGRAM_BOT_TOKEN в .env файле!")
        print("Получите токен у @BotFather в Telegram")
        return
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("elections", elections_list))
    application.add_handler(CommandHandler("results", show_results))
    application.add_handler(CommandHandler("regions", show_regions))
    application.add_handler(CommandHandler("analytics", show_analytics))
    application.add_handler(CommandHandler("help", help_command))
    
    # Регистрация обработчика кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запуск бота
    print("[OK] Telegram бот запущен!")
    print(f"[API] {API_BASE}")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"[ERROR] Ошибка при запуске бота: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
