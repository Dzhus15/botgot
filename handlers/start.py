from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.database import db
from database.models import User, UserStatus
from keyboards.inline import get_main_menu_keyboard
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle /start command"""
    try:
        user_id = message.from_user.id
        
        # Get or create user
        user = await db.get_user(user_id)
        if not user:
            user = User(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            await db.create_user(user)
            logger.info(f"New user created: {user_id}")
        
        # Clear any existing state
        await state.clear()
        
        # Check if this is a return from payment
        start_param = message.text.split(' ', 1)[1] if ' ' in message.text else None
        if start_param == "payment_success":
            welcome_text = f"""
✅ **Добро пожаловать обратно!**

Привет, {message.from_user.first_name}! 👋

💰 **Ваш текущий баланс:** {user.credits} кредитов

Если вы только что совершили оплату, кредиты будут зачислены в течение нескольких минут.

Выберите действие из меню ниже:
            """
        else:
            # Regular welcome message
            welcome_text = f"""
🎬 **Добро пожаловать в AI Video Generator!**

Привет, {message.from_user.first_name}! 👋

Этот бот поможет вам создавать потрясающие видео с помощью искусственного интеллекта Veo 3.

💰 **Ваш баланс:** {user.credits} кредитов

Выберите действие из меню ниже:
            """
        
        await message.answer(
            welcome_text,
            reply_markup=get_main_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже.",
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Handle back to main menu"""
    await state.clear()
    
    user = await db.get_user(callback.from_user.id)
    credits = user.credits if user else 0
    
    welcome_text = f"""
🎬 **AI Video Generator**

💰 **Ваш баланс:** {credits} кредитов

Выберите действие из меню ниже:
    """
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "help")
async def help_command(callback: CallbackQuery):
    """Handle help callback"""
    help_text = """
📖 **Помощь по использованию бота**

**Важные советы по составлению запросов:**
https://t.me/CatiAiPromt/51

**Примеры хороших запросов можно найти здесь:**
https://t.me/CatiAiPromt

**Как пользоваться ботом:**

🎥 **Генерация видео:**
• Выберите тип генерации (из текста или изображения)
• Опишите детально, что вы хотите видеть в видео
• Дождитесь завершения генерации (1-5 минут)

💰 **Кредиты:**
• 1 видео = 10 кредитов (749₽)
• Покупайте кредиты через Telegram Stars или банковскую карту

🎯 **Советы для лучшего результата:**
• Будьте конкретны в описании
• Указывайте детали: освещение, камеру, стиль
• Избегайте сложных сцен с множеством объектов
    """
    
    from keyboards.inline import get_back_to_menu_keyboard
    await callback.message.edit_text(
        help_text,
        reply_markup=get_back_to_menu_keyboard(),
        disable_web_page_preview=True
    )
    await callback.answer()
