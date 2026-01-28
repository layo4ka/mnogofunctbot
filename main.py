import asyncio
import io
import os
import tempfile
from pathlib import Path
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты для конвертации документов
import aspose.words as aw
from PIL import Image

# Импорт для загрузки видео
import yt_dlp
import aiohttp


# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8570622676:AAHO6NjmuUyBqBXgKEIVkXFVyrZPOs0JTG8"  # Замените на ваш токен

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()


# ==================== КЛАВИАТУРА ====================
def get_main_keyboard():
    """Главное меню с кнопкой помощи"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


# ==================== КОМАНДЫ ====================
@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Добро пожаловать в Swiss Bot!\n\n"
        "Я — ваш швейцарский нож для работы с файлами и медиа.\n\n"
        "Нажмите '📖 Помощь', чтобы узнать, что я умею!",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "📖 Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды помощи"""
    help_text = """
📚 <b>Что я умею:</b>

<b>1️⃣ Конвертация документов:</b>
• Пришлите <code>.pdf</code> — я конвертирую в <code>.docx</code>
• Пришлите <code>.docx</code> — я конвертирую в <code>.pdf</code>

<b>2️⃣ Загрузка видео:</b>
• Пришлите ссылку на YouTube, TikTok или Instagram
• Я скачаю видео и отправлю вам файлом

<b>3️⃣ Обработка фото:</b>
• Пришлите фото
• Я конвертирую его в PDF

<b>🔧 Дополнительные команды:</b>
/update_ytdlp - обновить загрузчик видео (если видео не скачивается)

<i>Просто отправьте файл или ссылку — я всё сделаю сам! 🚀</i>
    """
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("update_ytdlp"))
async def cmd_update_ytdlp(message: Message):
    """Обновление yt-dlp"""
    status_msg = await message.answer("🔄 Обновляю yt-dlp...")
    
    try:
        import subprocess
        
        # Обновляем yt-dlp
        result = subprocess.run(
            ["pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            await status_msg.edit_text(
                "✅ yt-dlp успешно обновлён!\n\n"
                "Попробуйте загрузить видео снова."
            )
        else:
            await status_msg.edit_text(
                f"❌ Ошибка обновления:\n\n"
                f"<code>{result.stderr[:500]}</code>",
                parse_mode="HTML"
            )
    except subprocess.TimeoutExpired:
        await status_msg.edit_text("❌ Превышено время ожидания обновления.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


# ==================== КОНВЕРТАЦИЯ PDF → DOCX ====================
@router.message(F.document)
async def handle_document(message: Message):
    """Обработчик документов"""
    document = message.document
    file_name = document.file_name
    
    if not file_name:
        await message.answer("❌ Не удалось определить имя файла.")
        return
    
    # Проверяем расширение
    if file_name.lower().endswith('.pdf'):
        await convert_pdf_to_docx(message, document)
    elif file_name.lower().endswith('.docx'):
        await convert_docx_to_pdf(message, document)
    else:
        await message.answer(
            "⚠️ Я работаю только с файлами .pdf и .docx\n"
            "Пришлите документ в одном из этих форматов."
        )


async def convert_pdf_to_docx(message: Message, document):
    """Конвертация PDF в DOCX"""
# ==================== КОНВЕРТАЦИЯ ДОКУМЕНТОВ ====================
@router.message(F.document)
async def handle_document(message: Message):
    """Обработчик документов для конвертации PDF <=> DOCX"""
    document = message.document
    file_name = document.file_name

    if not file_name:
        await message.answer("❌ Не удалось определить имя файла.")
        return

    # Проверяем, подходит ли файл
    is_pdf = file_name.lower().endswith('.pdf')
    is_docx = file_name.lower().endswith('.docx')

    if not is_pdf and not is_docx:
        await message.answer(
            "⚠️ Я работаю только с файлами .pdf и .docx\n"
            "Пришлите документ в одном из этих форматов."
        )
        return

    # Определяем, во что конвертировать
    if is_pdf:
        status_text = "🔄 Конвертирую PDF в DOCX..."
        output_extension = '.docx'
    else: # is_docx
        status_text = "🔄 Конвертирую DOCX в PDF..."
        output_extension = '.pdf'

    status_msg = await message.answer(status_text)
    
    # Запускаем конвертацию
    try:
        # Скачиваем файл
        file = await bot.get_file(document.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        
        # Конвертируем с помощью Aspose.Words
        doc = aw.Document(file_bytes_io)
        
        # Сохраняем результат в байтовый поток
        output_buffer = io.BytesIO()
        doc.save(output_buffer, aw.SaveFormat.DOCX if is_pdf else aw.SaveFormat.PDF)
        output_buffer.seek(0)
        
        # Формируем новое имя файла
        new_filename = file_name.rsplit('.', 1)[0] + output_extension
        
        # Отправляем документ
        input_file = BufferedInputFile(output_buffer.read(), filename=new_filename)
        await message.answer_document(
            input_file,
            caption=f"✅ Готово! Ваш файл конвертирован в {output_extension.upper()}."
        )
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при конвертации: {str(e)}")



# ==================== ЗАГРУЗКА ВИДЕО ====================
def is_tiktok_url(url: str) -> bool:
    """Проверка, является ли URL ссылкой на TikTok"""
    tiktok_patterns = [
        r'tiktok\.com/@[\w\.-]+/video/\d+',
        r'vm\.tiktok\.com/[\w]+',
        r'vt\.tiktok\.com/[\w]+',
        r'm\.tiktok\.com',
        r'tiktok\.com/.*',
    ]
    return any(re.search(pattern, url.lower()) for pattern in tiktok_patterns)


async def download_tiktok_alternative(message: Message, url: str):
    """Альтернативный метод загрузки TikTok через API"""
    status_msg = await message.answer("📥 Загружаю TikTok видео (альтернативный метод)...")
    
    try:
        # API для загрузки TikTok
        async with aiohttp.ClientSession() as session:
            # Пробуем первый API
            try:
                api_url = 'https://tikwm.com/api/'
                async with session.post(
                    api_url,
                    json={'url': url, 'hd': 1},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('code') == 0:
                            video_url = data.get('data', {}).get('play')
                            
                            if video_url:
                                # Скачиваем видео
                                await status_msg.edit_text("📥 Скачиваю видео...")
                                async with session.get(video_url) as video_response:
                                    if video_response.status == 200:
                                        video_data = await video_response.read()
                                        
                                        # Проверяем размер
                                        size_mb = len(video_data) / (1024 * 1024)
                                        if size_mb > 50:
                                            await status_msg.edit_text(
                                                f"❌ Видео слишком большое ({size_mb:.1f} MB).\n"
                                                "Telegram ограничивает размер до 50 MB."
                                            )
                                            return True
                                        
                                        # Отправляем
                                        await status_msg.edit_text(f"📤 Отправляю ({size_mb:.1f} MB)...")
                                        input_file = BufferedInputFile(
                                            video_data,
                                            filename="tiktok_video.mp4"
                                        )
                                        
                                        title = data.get('data', {}).get('title', 'TikTok видео')
                                        caption = f"✅ {title[:100]}\n💾 Размер: {size_mb:.1f} MB"
                                        
                                        await message.answer_document(input_file, caption=caption)
                                        await status_msg.delete()
                                        return True
            except Exception as e:
                print(f"TikTok API failed: {e}")
        
        return False
    
    except Exception as e:
        print(f"Alternative TikTok download error: {e}")
        return False


@router.message(F.text)
async def handle_text(message: Message):
    """Обработчик текстовых сообщений (ссылки на видео)"""
    text = message.text
    
    # Пропускаем команды и кнопки меню
    if text.startswith('/') or text == "📖 Помощь":
        return
    
    # Проверяем, похоже ли на ссылку
    if not ('http://' in text or 'https://' in text):
        await message.answer(
            "🤔 Отправьте мне:\n"
            "• Ссылку на видео (YouTube, TikTok, Instagram)\n"
            "• Документ (.pdf или .docx)\n"
            "• Фото для конвертации в PDF"
        )
        return
    
    # Для TikTok сначала пробуем альтернативный метод
    if is_tiktok_url(text):
        success = await download_tiktok_alternative(message, text)
        if not success:
            # Если альтернативный метод не сработал, пробуем yt-dlp
            await download_video(message, text)
    else:
        # Для YouTube, Instagram и других используем yt-dlp
        await download_video(message, text)


async def download_video(message: Message, url: str):
    """Загрузка видео по ссылке"""
    status_msg = await message.answer("📥 Начинаю загрузку видео...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
            
            # Определяем, это TikTok или нет
            is_tiktok = 'tiktok.com' in url.lower() or 'vm.tiktok.com' in url.lower()
            
            ydl_opts = {
                # Формат видео - берем лучшее качество до 720p для экономии размера
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                # Ограничение размера (50MB для Telegram)
                'max_filesize': 50 * 1024 * 1024,
                # Важные заголовки для обхода блокировок
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Accept-Encoding': 'gzip,deflate',
                    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                    'Referer': 'https://www.tiktok.com/' if is_tiktok else 'https://www.google.com/',
                },
                # Дополнительные опции для обхода ограничений
                'nocheckcertificate': True,
                'geo_bypass': True,
                'age_limit': None,
                # Таймауты
                'socket_timeout': 30,
                # Для Instagram и TikTok
                'extractor_args': {
                    'instagram': {
                        'api': 'graphql'
                    },
                    'tiktok': {
                        'api_hostname': 'api22-normal-c-useast2a.tiktokv.com',
                        'app_version': '34.1.2',
                        'manifest_app_version': '2023401020',
                    }
                },
                # Повторные попытки
                'retries': 5,
                'fragment_retries': 5,
            }
            
            # Для TikTok используем специальные настройки
            if is_tiktok:
                ydl_opts['format'] = 'best[ext=mp4]/best'
                ydl_opts['http_headers']['User-Agent'] = 'com.zhiliaoapp.musically/2023401020 (Linux; U; Android 13; en_US; Pixel 7; Build/TP1A.220624.014; Cronet/58.0.2991.0)'
            
            # Скачиваем
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await status_msg.edit_text("⏳ Загружаю видео...")
                
                # Выполняем загрузку в отдельном потоке
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=True)
                )
                
                # Ищем скачанный файл
                video_file = None
                for file in os.listdir(temp_dir):
                    if file.endswith(('.mp4', '.mkv', '.webm', '.mov')):
                        video_file = os.path.join(temp_dir, file)
                        break
                
                if not video_file:
                    await status_msg.edit_text("❌ Не удалось найти скачанное видео.")
                    return
                
                # Проверяем размер
                file_size = os.path.getsize(video_file)
                size_mb = file_size / (1024 * 1024)
                
                if file_size > 50 * 1024 * 1024:
                    await status_msg.edit_text(
                        f"❌ Видео слишком большое ({size_mb:.1f} MB).\n"
                        "Telegram ограничивает размер файлов до 50 MB.\n\n"
                        "💡 Попробуйте найти видео в более низком качестве."
                    )
                    return
                
                # Отправляем
                await status_msg.edit_text(f"📤 Отправляю видео ({size_mb:.1f} MB)...")
                
                with open(video_file, 'rb') as video:
                    video_data = video.read()
                    input_file = BufferedInputFile(
                        video_data, 
                        filename=os.path.basename(video_file)
                    )
                    
                    title = info.get('title', 'Видео')
                    duration = info.get('duration', 0)
                    
                    caption = f"✅ Видео загружено!\n\n📹 {title}"
                    if duration:
                        mins = int(duration // 60)
                        secs = int(duration % 60)
                        caption += f"\n⏱ Длительность: {mins}:{secs:02d}"
                    caption += f"\n💾 Размер: {size_mb:.1f} MB"
                    
                    await message.answer_document(
                        input_file,
                        caption=caption[:1024]  # Telegram ограничивает длину подписи
                    )
                
                await status_msg.delete()
                
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        
        if 'timeout' in error_msg or 'timed out' in error_msg:
            await status_msg.edit_text(
                "⏱ Превышено время ожидания.\n\n"
                "Возможные причины:\n"
                "• TikTok блокирует загрузки в вашем регионе\n"
                "• Сервер перегружен\n"
                "• Проблемы с интернет-соединением\n\n"
                "💡 Попробуйте:\n"
                "1. Подождать 1-2 минуты и попробовать снова\n"
                "2. Использовать другую ссылку\n"
                "3. Проверить, что видео публичное\n"
                "4. Для TikTok: используйте полную ссылку с https://www.tiktok.com/"
            )
        elif '403' in error_msg or 'forbidden' in error_msg:
            await status_msg.edit_text(
                "❌ Доступ запрещён (403 Forbidden).\n\n"
                "Возможные решения:\n"
                "• Видео может быть ограничено по региону\n"
                "• Попробуйте другую ссылку\n"
                "• Некоторые платформы блокируют загрузку\n\n"
                "💡 Обновите yt-dlp: <code>pip install -U yt-dlp</code>\n"
                "Или используйте команду: /update_ytdlp",
                parse_mode="HTML"
            )
        elif 'private' in error_msg or 'unavailable' in error_msg:
            await status_msg.edit_text(
                "❌ Видео недоступно.\n\n"
                "Возможные причины:\n"
                "• Приватный аккаунт или видео\n"
                "• Видео удалено\n"
                "• Географические ограничения"
            )
        elif 'sign in' in error_msg or 'login' in error_msg:
            await status_msg.edit_text(
                "🔐 Требуется авторизация.\n\n"
                "Это видео доступно только авторизованным пользователям.\n"
                "К сожалению, бот не может скачать такие видео."
            )
        else:
            await status_msg.edit_text(
                f"❌ Не удалось загрузить видео.\n\n"
                f"Ошибка: {str(e)[:200]}\n\n"
                f"💡 Попробуйте другую ссылку или обновите yt-dlp"
            )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Произошла ошибка: {str(e)[:200]}\n\n"
            f"💡 Попробуйте ещё раз или используйте другую ссылку"
        )


# ==================== ОБРАБОТКА ФОТО ====================
@router.message(F.photo)
async def handle_photo(message: Message):
    """Обработчик фотографий"""
    status_msg = await message.answer("🖼️ Конвертирую фото в PDF...")
    
    try:
        # Получаем фото максимального качества
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        # Открываем изображение
        image = Image.open(file_bytes)
        
        # Конвертируем в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Сохраняем в PDF через BytesIO
        pdf_buffer = io.BytesIO()
        image.save(pdf_buffer, 'PDF', resolution=100.0)
        pdf_buffer.seek(0)
        
        # Формируем имя файла
        filename = f"photo_{message.message_id}.pdf"
        
        # Отправляем
        input_file = BufferedInputFile(pdf_buffer.read(), filename=filename)
        await message.answer_document(
            input_file,
            caption="✅ Фото конвертировано в PDF!"
        )
        
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при конвертации фото: {str(e)}")


# ==================== ЗАПУСК БОТА ====================
async def main():
    """Главная функция запуска бота"""
    # Подключаем роутер
    dp.include_router(router)
    
    # Удаляем вебхуки (если были)
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("🤖 Бот запущен!")
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен!")
