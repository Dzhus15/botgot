from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

from database.database import db
from database.models import AdminLog, UserStatus
from keyboards.inline import get_admin_menu_keyboard, get_back_to_admin_keyboard
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()
config = Config()

class AdminStates(StatesGroup):
    waiting_broadcast_message = State()

async def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    user = await db.get_user(user_id)
    return user and user.status == UserStatus.ADMIN

@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    """Handle /admin command"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    await state.clear()
    
    admin_text = """
👑 <b>Панель администратора</b>

Добро пожаловать в админ-панель! Выберите действие:

📊 <b>Статистика пользователей</b> - просмотр статистики
📢 <b>Рассылка сообщений</b> - отправка сообщений всем пользователям

Выберите действие из меню ниже:
    """
    
    await message.answer(
        admin_text,
        reply_markup=get_admin_menu_keyboard()
    )

@router.callback_query(F.data == "admin_stats")
async def admin_statistics(callback: CallbackQuery):
    """Show admin statistics"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    try:
        stats = await db.get_user_statistics()
        
        stats_text = f"""
📊 <b>Статистика пользователей</b>

👥 <b>Общее количество пользователей:</b> {stats['total_users']}
🔥 <b>Активные пользователи (30 дней):</b> {stats['active_users']}
💰 <b>Всего кредитов в системе:</b> {stats['total_credits']:,}
🎬 <b>Всего создано видео:</b> {stats['total_videos']}

📈 <b>Активность:</b>
• Конверсия в активных: {(stats['active_users'] / max(stats['total_users'], 1) * 100):.1f}%
• Среднее кредитов на пользователя: {(stats['total_credits'] / max(stats['total_users'], 1)):.1f}
        """
        
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_back_to_admin_keyboard()
        )
        
        # Log admin action
        admin_log = AdminLog(
            admin_id=callback.from_user.id,
            action="view_statistics",
            description="Viewed user statistics"
        )
        await db.log_admin_action(admin_log)
        
    except Exception as e:
        logger.error(f"Error getting admin statistics: {e}")
        await callback.message.edit_text(
            "❌ Ошибка получения статистики",
            reply_markup=get_back_to_admin_keyboard()
        )
    
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Start broadcast message creation"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    broadcast_text = """
📢 <b>Рассылка сообщений</b>

Отправьте сообщение, которое хотите разослать всем пользователям.

💡 <b>Вы можете отправить:</b>
• Текстовое сообщение
• Сообщение с фото
• Переслать сообщение из другого чата

⚠️ <b>Внимание:</b> Рассылка будет отправлена ВСЕМ активным пользователям бота!

Отправьте сообщение для рассылки:
    """
    
    await callback.message.edit_text(
        broadcast_text,
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_broadcast_message)
    await callback.answer()

@router.message(AdminStates.waiting_broadcast_message)
async def admin_broadcast_process(message: Message, state: FSMContext):
    """Process broadcast message"""
    if not await is_admin(message.from_user.id):
        return
    
    await state.clear()
    
    # Get all user IDs
    user_ids = await db.get_all_user_ids()
    total_users = len(user_ids)
    
    if total_users == 0:
        await message.answer(
            "❌ Нет пользователей для рассылки.",
            reply_markup=get_back_to_admin_keyboard()
        )
        return
    
    # Confirm broadcast
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить рассылку", callback_data="confirm_broadcast"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin_menu")
        ]
    ])
    
    await message.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"👥 <b>Получателей:</b> {total_users} пользователей\n"
        f"📝 <b>Тип сообщения:</b> {'С фото' if message.photo else 'Текстовое'}\n\n"
        f"⚠️ Вы уверены, что хотите отправить рассылку?",
        reply_markup=confirm_keyboard
    )
    
    # Store message for broadcast
    await state.update_data(
        broadcast_message_id=message.message_id,
        total_users=total_users
    )

@router.callback_query(F.data == "confirm_broadcast")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm and execute broadcast"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    state_data = await state.get_data()
    broadcast_message_id = state_data.get('broadcast_message_id')
    total_users = state_data.get('total_users', 0)
    
    if not broadcast_message_id:
        await callback.answer("❌ Сообщение для рассылки не найдено")
        return
    
    await state.clear()
    
    # Start broadcast
    progress_msg = await callback.message.edit_text(
        f"📢 <b>Рассылка началась...</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Отправлено: 0\n"
        f"❌ Ошибок: 0\n\n"
        f"⏳ Ожидайте завершения..."
    )
    
    # Get user IDs and start broadcast
    user_ids = await db.get_all_user_ids()
    success_count = 0
    error_count = 0
    
    # Import bot instance
    from aiogram import Bot
    from config import Config
    bot_config = Config()
    bot = Bot(token=bot_config.TELEGRAM_BOT_TOKEN)
    
    for i, user_id in enumerate(user_ids):
        try:
            # Forward the broadcast message
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=callback.from_user.id,
                message_id=broadcast_message_id
            )
            success_count += 1
            
            # Update progress every 10 users
            if (i + 1) % 10 == 0 or i == len(user_ids) - 1:
                try:
                    await progress_msg.edit_text(
                        f"📢 <b>Рассылка в процессе...</b>\n\n"
                        f"👥 Всего пользователей: {total_users}\n"
                        f"✅ Отправлено: {success_count}\n"
                        f"❌ Ошибок: {error_count}\n"
                        f"📊 Прогресс: {((i + 1) / total_users * 100):.1f}%"
                    )
                except:
                    pass  # Ignore edit errors
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.05)
            
        except Exception as e:
            error_count += 1
            logger.warning(f"Broadcast error for user {user_id}: {e}")
            
            # Longer delay on errors
            await asyncio.sleep(0.1)
    
    # Final results
    await progress_msg.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Успешно отправлено: {success_count}\n"
        f"❌ Ошибок доставки: {error_count}\n"
        f"📊 Успешность: {(success_count / max(total_users, 1) * 100):.1f}%",
        reply_markup=get_back_to_admin_keyboard()
    )
    
    # Log admin action
    admin_log = AdminLog(
        admin_id=callback.from_user.id,
        action="broadcast_message",
        description=f"Broadcast sent to {success_count}/{total_users} users"
    )
    await db.log_admin_action(admin_log)
    
    logger.info(f"Broadcast completed: {success_count}/{total_users} users")
    await callback.answer("✅ Рассылка завершена!")

@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    """Back to admin menu"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    await state.clear()
    
    admin_text = """
👑 <b>Панель администратора</b>

Выберите действие из меню ниже:
    """
    
    await callback.message.edit_text(
        admin_text,
        reply_markup=get_admin_menu_keyboard()
    )
    await callback.answer()
