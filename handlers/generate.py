from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import uuid

from database.database import db
from database.models import VideoGeneration, Transaction, TransactionType, GenerationType
from api_integrations.veo_api import VeoAPI
from keyboards.inline import get_generation_menu_keyboard, get_back_to_menu_keyboard
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()
config = Config()

class GenerationStates(StatesGroup):
    waiting_text_prompt = State()
    waiting_image_prompt = State()
    waiting_image = State()

@router.callback_query(F.data == "generate_video")
async def generate_video_menu(callback: CallbackQuery):
    """Show video generation menu"""
    text = """
🎬 Генерация видео

Выберите тип генерации:

📝 Видео из текста - создайте видео по текстовому описанию
🖼 Видео из изображения - оживите изображение с помощью ИИ

💡 Стоимость: 10 кредитов за видео (79₽)
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_generation_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "text_to_video")
async def text_to_video_start(callback: CallbackQuery, state: FSMContext):
    """Start text-to-video generation"""
    user = await db.get_user(callback.from_user.id)
    if not user or user.credits < config.VIDEO_GENERATION_COST:
        await callback.message.edit_text(
            f"❌ <b>Недостаточно кредитов!</b>\n\n"
            f"Для генерации видео нужно {config.VIDEO_GENERATION_COST} кредитов.\n"
            f"Ваш баланс: {user.credits if user else 0} кредитов",
            reply_markup=get_back_to_menu_keyboard()
        )
        await callback.answer()
        return
    
    prompt_tips = """
🎬 <b>Генерация видео из текста</b>

📝 Напишите подробное описание видео, которое хотите создать.

💡 <b>Советы для лучшего результата:</b>
• Описывайте действия, движения, сцены
• Указывайте стиль, освещение, ракурс камеры
• Будьте конкретными и детальными
• Избегайте сложных сцен с множеством персонажей

<b>Пример хорошего промпта:</b>
"Крупный план золотистого ретривера, играющего с мячом в солнечном парке. Собака радостно подпрыгивает, ловя мяч. Мягкое естественное освещение, кинематографическая съемка"

Отправьте ваш промпт:
    """
    
    await callback.message.edit_text(
        prompt_tips,
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(GenerationStates.waiting_text_prompt)
    await callback.answer()

@router.callback_query(F.data == "image_to_video")
async def image_to_video_start(callback: CallbackQuery, state: FSMContext):
    """Start image-to-video generation"""
    user = await db.get_user(callback.from_user.id)
    if not user or user.credits < config.VIDEO_GENERATION_COST:
        await callback.message.edit_text(
            f"❌ <b>Недостаточно кредитов!</b>\n\n"
            f"Для генерации видео нужно {config.VIDEO_GENERATION_COST} кредитов.\n"
            f"Ваш баланс: {user.credits if user else 0} кредитов",
            reply_markup=get_back_to_menu_keyboard()
        )
        await callback.answer()
        return
    
    image_instructions = """
🖼 <b>Генерация видео из изображения</b>

📷 Отправьте изображение, которое хотите оживить.

📝 После отправки изображения опишите, как оно должно ожить:

💡 <b>Советы:</b>
• Описывайте движения и действия
• Указывайте, какие части изображения должны двигаться
• Избегайте кардинальных изменений изображения
• Фокусируйтесь на естественных движениях

Отправьте изображение:
    """
    
    await callback.message.edit_text(
        image_instructions,
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(GenerationStates.waiting_image)
    await callback.answer()

@router.message(GenerationStates.waiting_text_prompt)
async def process_text_prompt(message: Message, state: FSMContext):
    """Process text-to-video prompt"""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текстовое описание видео.")
        return
    
    await state.clear()
    
    # Check user credits again
    user = await db.get_user(message.from_user.id)
    if not user or user.credits < config.VIDEO_GENERATION_COST:
        await message.answer(
            f"❌ Недостаточно кредитов! Нужно {config.VIDEO_GENERATION_COST} кредитов.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    # Generate unique task ID
    task_id = f"veo_{uuid.uuid4().hex[:12]}"
    
    # Deduct credits
    new_credits = user.credits - config.VIDEO_GENERATION_COST
    await db.update_user_credits(message.from_user.id, new_credits)
    
    # Create transaction record
    transaction = Transaction(
        user_id=message.from_user.id,
        type=TransactionType.CREDIT_SPEND,
        amount=-config.VIDEO_GENERATION_COST,
        description=f"Video generation: {message.text[:50]}..."
    )
    await db.create_transaction(transaction)
    
    # Create video generation record
    generation = VideoGeneration(
        user_id=message.from_user.id,
        task_id=task_id,
        prompt=message.text,
        generation_type=GenerationType.TEXT_TO_VIDEO,
        model=config.DEFAULT_MODEL,
        aspect_ratio=config.DEFAULT_ASPECT_RATIO,
        credits_spent=config.VIDEO_GENERATION_COST
    )
    await db.create_video_generation(generation)
    
    # Start video generation
    processing_msg = await message.answer(
        f"🎬 <b>Генерируем ваше видео...</b>\n\n"
        f"📝 Промпт: {message.text[:100]}{'...' if len(message.text) > 100 else ''}\n"
        f"💰 Списано кредитов: {config.VIDEO_GENERATION_COST}\n"
        f"💳 Остаток: {new_credits} кредитов\n\n"
        f"⏳ Процесс займет 1-5 минут. Мы уведомим вас о готовности!",
        reply_markup=get_back_to_menu_keyboard()
    )
    
    # Call Veo API
    veo_api = VeoAPI()
    success = await veo_api.generate_video(
        task_id=task_id,
        prompt=message.text,
        generation_type=GenerationType.TEXT_TO_VIDEO,
        user_id=message.from_user.id
    )
    
    if not success:
        # Refund credits on failure
        await db.update_user_credits(message.from_user.id, user.credits)
        refund_transaction = Transaction(
            user_id=message.from_user.id,
            type=TransactionType.ADMIN_GRANT,
            amount=config.VIDEO_GENERATION_COST,
            description="Refund for failed generation"
        )
        await db.create_transaction(refund_transaction)
        
        await message.answer(
            "❌ <b>Ошибка генерации видео</b>\n\n"
            "Кредиты возвращены на ваш счет. Попробуйте еще раз.",
            reply_markup=get_back_to_menu_keyboard()
        )

@router.message(GenerationStates.waiting_image)
async def process_image_upload(message: Message, state: FSMContext):
    """Process image for image-to-video generation"""
    logger.info(f"Processing image upload from user {message.from_user.id}")
    
    if not message.photo:
        logger.warning(f"No photo in message from user {message.from_user.id}")
        await message.answer("❌ Пожалуйста, отправьте изображение.")
        return
    
    # Get the largest photo size
    photo = message.photo[-1]
    
    # Store image file_id in state
    await state.update_data(image_file_id=photo.file_id)
    
    await message.answer(
        "📝 <b>Отлично! Изображение получено.</b>\n\n"
        "Теперь опишите, как изображение должно ожить:\n"
        "• Какие движения должны происходить?\n"
        "• Какие части изображения должны двигаться?\n"
        "• Какая атмосфера должна быть?\n\n"
        "Напишите описание:",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(GenerationStates.waiting_image_prompt)

@router.message(GenerationStates.waiting_image_prompt)
async def process_image_prompt(message: Message, state: FSMContext):
    """Process prompt for image-to-video generation"""
    logger.info(f"Processing image prompt from user {message.from_user.id}: {message.text[:50] if message.text else 'No text'}")
    
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текстовое описание.")
        return
    
    state_data = await state.get_data()
    image_file_id = state_data.get('image_file_id')
    
    if not image_file_id:
        await message.answer("❌ Изображение потеряно. Начните сначала.")
        await state.clear()
        return
    
    await state.clear()
    
    # Check user credits
    user = await db.get_user(message.from_user.id)
    if not user or user.credits < config.VIDEO_GENERATION_COST:
        await message.answer(
            f"❌ Недостаточно кредитов! Нужно {config.VIDEO_GENERATION_COST} кредитов.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    # Generate unique task ID
    task_id = f"veo_{uuid.uuid4().hex[:12]}"
    
    # Deduct credits
    new_credits = user.credits - config.VIDEO_GENERATION_COST
    await db.update_user_credits(message.from_user.id, new_credits)
    
    # Create transaction record
    transaction = Transaction(
        user_id=message.from_user.id,
        type=TransactionType.CREDIT_SPEND,
        amount=-config.VIDEO_GENERATION_COST,
        description=f"Image-to-video generation: {message.text[:50]}..."
    )
    await db.create_transaction(transaction)
    
    # For image-to-video, we need to get the actual image URL
    # In a real implementation, you would upload the image to a public URL
    # For now, we'll use the file_id (this needs to be converted to a public URL)
    image_url = f"telegram_file:{image_file_id}"  # Placeholder
    
    # Create video generation record
    generation = VideoGeneration(
        user_id=message.from_user.id,
        task_id=task_id,
        prompt=message.text,
        generation_type=GenerationType.IMAGE_TO_VIDEO,
        image_url=image_url,
        model=config.DEFAULT_MODEL,
        aspect_ratio=config.DEFAULT_ASPECT_RATIO,
        credits_spent=config.VIDEO_GENERATION_COST
    )
    await db.create_video_generation(generation)
    
    await message.answer(
        f"🖼 <b>Генерируем видео из изображения...</b>\n\n"
        f"📝 Описание: {message.text[:100]}{'...' if len(message.text) > 100 else ''}\n"
        f"💰 Списано кредитов: {config.VIDEO_GENERATION_COST}\n"
        f"💳 Остаток: {new_credits} кредитов\n\n"
        f"⏳ Процесс займет 1-5 минут. Мы уведомим вас о готовности!",
        reply_markup=get_back_to_menu_keyboard()
    )
    
    # Call Veo API for image-to-video
    veo_api = VeoAPI()
    success = await veo_api.generate_video(
        task_id=task_id,
        prompt=message.text,
        generation_type=GenerationType.IMAGE_TO_VIDEO,
        image_file_id=image_file_id,
        user_id=message.from_user.id
    )
    
    if not success:
        # Refund credits on failure
        await db.update_user_credits(message.from_user.id, user.credits)
        refund_transaction = Transaction(
            user_id=message.from_user.id,
            type=TransactionType.ADMIN_GRANT,
            amount=config.VIDEO_GENERATION_COST,
            description="Refund for failed generation"
        )
        await db.create_transaction(refund_transaction)
        
        await message.answer(
            "❌ <b>Ошибка генерации видео</b>\n\n"
            "Кредиты возвращены на ваш счет. Попробуйте еще раз.",
            reply_markup=get_back_to_menu_keyboard()
        )
