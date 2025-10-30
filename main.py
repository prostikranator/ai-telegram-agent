import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# --- 1. Настройка Логирования ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. Константы и Переменные Среды ---
# Они будут взяты из настроек Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 
PORT = int(os.environ.get("PORT", 8080)) 

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# СИСТЕМНЫЙ ПРОМПТ: Ключ к адекватности и таблицам
SYSTEM_PROMPT = (
    "Ты — высококвалифицированный ИИ-агент по созданию документов и данных. "
    "Твоя задача — проанализировать запрос пользователя и создать готовый документ, текст или таблицу. "
    "Если пользователь описывает данные (списки, цифры, сравнения), сгенерируй таблицу, используя **строгий формат Markdown** (с вертикальными чертами | и дефисами -). "
    "Отвечай только сгенерированным контентом."
)
MODEL_NAME = "mistralai/mixtral-8x7b-instruct-v0.1" 
# NOTE: Для обеспечения бесплатности всегда выбирайте самую дешевую или "free tier" модель на OpenRouter.

# --- 3. Главный Обработчик Сообщений ---
async def generate_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет запрос пользователя в OpenRouter и отправляет ответ."""
    user_request = update.message.text

    # Проверка, что ключи настроены
    if not OPENROUTER_KEY:
        await update.message.reply_text("Ошибка: Не настроен ключ OpenRouter API.")
        return

    # Уведомление пользователя
    await update.message.reply_text("⏳ Запрос отправлен. Идет генерация документа...")

    try:
        data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_request}
            ]
        }
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        }

        # Выполнение запроса к OpenRouter
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        # Извлечение сгенерированного текста
        ai_response_text = response.json()["choices"][0]["message"]["content"]
        
        # Отправка ответа в Telegram с поддержкой MarkdownV2 для форматирования таблиц
        await update.message.reply_text(
            ai_response_text,
            parse_mode=ParseMode.MARKDOWN_V2 
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к OpenRouter: {e}")
        await update.message.reply_text(f"Произошла ошибка при обращении к AI: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await update.message.reply_text("Произошла неизвестная ошибка. Попробуйте снова.")

# --- 4. Запуск Бота (Режим Webhook для Render) ---
def main() -> None:
    """Запускает бота в режиме Webhook для Render."""
    
    if not TELEGRAM_TOKEN or not WEBHOOK_URL:
        logger.error("Ключи или WEBHOOK_URL не настроены. Бот не может быть запущен.")
        return

    # Создание экземпляра приложения
    # application является переменной, которую будет использовать Gunicorn
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавление обработчика для всех текстовых сообщений (кроме команд)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_document))

    # Настройка Webhook: listen на 0.0.0.0, порт берется из ENV
    # url_path используется для безопасности (делает URL сложнее угадать)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    )
    logger.info(f"Бот запущен на порту {PORT} с Webhook")

if __name__ == "__main__":
    main()