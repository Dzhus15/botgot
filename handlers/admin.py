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
from admin_tools.credit_management import check_user_credits, grant_user_credits, emergency_credit_restore

logger = get_logger(__name__)
router = Router()
config = Config()

class AdminStates(StatesGroup):
    waiting_broadcast_message = State()
    waiting_payment_id = State()
    waiting_user_id_for_notification = State()
    waiting_user_id_for_credits = State()
    waiting_credits_amount = State()
    waiting_credits_reason = State()

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
💰 <b>Проверить кредиты</b> - проверить баланс пользователя по ID
💎 <b>Выдать кредиты</b> - начислить кредиты пользователю (только на production)
📢 <b>Рассылка сообщений</b> - отправка сообщений всем пользователям
🔍 <b>Проверка платежа</b> - проверить статус и начислить кредиты

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

@router.callback_query(F.data == "admin_check_payment")
async def admin_check_payment(callback: CallbackQuery, state: FSMContext):
    """Check payment status manually"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.message.edit_text(
        "🔍 <b>Проверка платежа</b>\n\n"
        "Введите ID платежа ЮКассы для проверки и начисления кредитов:\n\n"
        "💡 ID платежа можно найти в логах бота или личном кабинете ЮКассы",
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_payment_id)
    await callback.answer()

@router.message(AdminStates.waiting_payment_id)
async def process_payment_check(message: Message, state: FSMContext):
    """Process payment ID and check status"""
    if not await is_admin(message.from_user.id):
        return
    
    payment_id = message.text.strip()
    
    if not payment_id:
        await message.reply("❌ Введите корректный ID платежа")
        return
    
    # Show progress message
    progress_msg = await message.reply("🔍 Проверяю статус платежа...")
    
    try:
        from api_integrations.payment_api import PaymentAPI
        
        payment_api = PaymentAPI()
        result = await payment_api.verify_yookassa_payment(payment_id)
        
        if result.get("status") == "error":
            await progress_msg.edit_text(f"❌ Ошибка проверки: {result.get('message')}")
            await state.clear()
            return
        
        status = result.get("status")
        amount = result.get("amount")
        currency = result.get("currency")
        metadata = result.get("metadata", {})
        is_paid = result.get("paid", False)
        
        user_id = metadata.get("user_id")
        package_id = metadata.get("package_id")
        
        status_text = f"""
🔍 <b>Результат проверки платежа</b>

💳 <b>ID платежа:</b> {payment_id}
💰 <b>Сумма:</b> {amount} {currency}
📊 <b>Статус:</b> {status}
✅ <b>Оплачен:</b> {'Да ✅' if is_paid else 'Нет ❌'}

👤 <b>Пользователь:</b> {user_id or 'Не указан'}
📦 <b>Пакет:</b> {package_id or 'Не указан'}
        """
        
        if is_paid and user_id and package_id:
            # Check if credits were already processed
            payment_exists = await db.payment_exists(payment_id)
            
            if payment_exists:
                status_text += "\n\n⚠️ Кредиты уже начислены ранее"
            else:
                # Process payment manually
                await progress_msg.edit_text("💰 Начисляю кредиты...")
                
                success = await payment_api._process_successful_card_payment(
                    user_id=int(user_id),
                    package_id=package_id,
                    payment_id=payment_id,
                    amount=float(amount)
                )
                
                if success:
                    status_text += "\n\n✅ Кредиты успешно начислены!"
                    
                    # Log admin action
                    admin_log = AdminLog(
                        admin_id=message.from_user.id,
                        action="manual_payment_processing",
                        target_user_id=int(user_id),
                        description=f"Manually processed payment {payment_id}"
                    )
                    await db.log_admin_action(admin_log)
                else:
                    status_text += "\n\n❌ Ошибка начисления кредитов"
        elif is_paid:
            status_text += "\n\n⚠️ Платеж успешен, но метаданные неполные"
        
        await progress_msg.edit_text(status_text)
        
    except Exception as e:
        logger.error(f"Error checking payment {payment_id}: {e}")
        await progress_msg.edit_text(f"❌ Ошибка проверки платежа: {e}")
    
    await state.clear()

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

# ======= НОВЫЕ ФУНКЦИИ УПРАВЛЕНИЯ КРЕДИТАМИ =======

@router.callback_query(F.data == "admin_check_credits")
async def admin_check_credits_start(callback: CallbackQuery, state: FSMContext):
    """Start checking user credits"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    text = """
🔍 <b>Проверка кредитов пользователя</b>

Введите ID пользователя (Telegram ID), чтобы проверить его баланс кредитов:

<i>Пример: 123456789</i>
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_for_credits)
    await state.update_data(action="check")
    await callback.answer()

@router.callback_query(F.data == "admin_grant_credits")
async def admin_grant_credits_start(callback: CallbackQuery, state: FSMContext):
    """Start granting credits to user"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    # Проверяем environment
    from admin_tools.credit_management import credit_manager
    
    if not credit_manager.is_production:
        await callback.message.edit_text(
            "⚠️ <b>Выдача кредитов заблокирована</b>\n\n"
            "Эта функция работает только на production (после deploy).\n"
            "Локальный запуск не позволяет выдавать кредиты для безопасности.",
            reply_markup=get_back_to_admin_keyboard()
        )
        await callback.answer()
        return
    
    text = """
💎 <b>Выдача кредитов пользователю</b>

⚠️ <b>ВНИМАНИЕ:</b> Выдача кредитов работает только на production!

Введите ID пользователя (Telegram ID):

<i>Пример: 123456789</i>
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_admin_keyboard()
    )
    await state.set_state(AdminStates.waiting_user_id_for_credits)
    await state.update_data(action="grant")
    await callback.answer()

@router.message(AdminStates.waiting_user_id_for_credits)
async def admin_process_user_id_for_action(message: Message, state: FSMContext):
    """Process user ID for credit actions"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        data = await state.get_data()
        action = data.get('action', 'check')
        user_id = int(message.text.strip())
        
        if action == "check":
            # Проверяем кредиты через безопасную систему
            result = await check_user_credits(message.from_user.id, user_id)
            
            if "error" in result:
                await message.answer(f"❌ {result['error']}")
            else:
                credits_text = f"""
💰 <b>Баланс кредитов пользователя</b>

👤 <b>User ID:</b> {result['user_id']}
👤 <b>Username:</b> @{result['username'] or 'не указан'}
👤 <b>Имя:</b> {result['first_name'] or 'не указано'}
💎 <b>Кредиты:</b> {result['credits']}
📊 <b>Статус:</b> {result['status']}
📅 <b>Регистрация:</b> {result['created_at'][:10] if result['created_at'] else 'неизвестно'}
🕐 <b>Обновлен:</b> {result['updated_at'][:10] if result['updated_at'] else 'неизвестно'}
                """
                
                await message.answer(
                    credits_text,
                    reply_markup=get_back_to_admin_keyboard()
                )
            await state.clear()
            
        elif action == "grant":
            # Переходим к вводу количества кредитов
            await state.update_data(user_id=user_id)
            
            await message.answer(
                f"💎 <b>Выдача кредитов пользователю {user_id}</b>\n\n"
                f"Введите количество кредитов для выдачи (1-1000):\n\n"
                f"<i>Например: 50</i>",
                reply_markup=get_back_to_admin_keyboard()
            )
            await state.set_state(AdminStates.waiting_credits_amount)
            
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите числовой Telegram ID.")
    except Exception as e:
        logger.error(f"Error processing user ID for action: {e}")
        await message.answer("❌ Ошибка при обработке ID пользователя.")

@router.message(AdminStates.waiting_credits_amount)
async def admin_process_credits_amount(message: Message, state: FSMContext):
    """Process credits amount input"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        credits = int(message.text.strip())
        
        if credits <= 0:
            await message.answer("❌ Количество кредитов должно быть положительным числом.")
            return
            
        if credits > 1000:
            await message.answer("❌ Максимальное количество кредитов за раз: 1000")
            return
        
        await state.update_data(credits=credits)
        
        await message.answer(
            f"💎 <b>Выдача {credits} кредитов</b>\n\n"
            f"Введите причину выдачи кредитов (необязательно):\n\n"
            f"<i>Например: Компенсация за техническую ошибку</i>\n\n"
            f"Или отправьте '-' чтобы пропустить:",
            reply_markup=get_back_to_admin_keyboard()
        )
        await state.set_state(AdminStates.waiting_credits_reason)
        
    except ValueError:
        await message.answer("❌ Введите числовое количество кредитов.")
    except Exception as e:
        logger.error(f"Error processing credits amount: {e}")
        await message.answer("❌ Ошибка при обработке количества кредитов.")

@router.message(AdminStates.waiting_credits_reason)
async def admin_process_credits_reason(message: Message, state: FSMContext):
    """Process credits reason and complete grant"""
    if not await is_admin(message.from_user.id):
        return
    
    try:
        data = await state.get_data()
        user_id = data.get('user_id')
        credits = data.get('credits')
        reason = message.text.strip() if message.text.strip() != '-' else ""
        
        # Выдаем кредиты через безопасную систему с уведомлением пользователю
        result = await grant_user_credits(message.from_user.id, user_id, credits, reason, message.bot)
        
        if result.get("success"):
            notification_status = "✅ Отправлено" if result.get("notification_sent") else "⚠️ Не отправлено"
            
            success_text = f"""
✅ <b>КРЕДИТЫ УСПЕШНО ВЫДАНЫ!</b>

👤 <b>Пользователь:</b> {result['user_id']}
💎 <b>Выдано кредитов:</b> {result['credits_granted']}
💰 <b>Старый баланс:</b> {result['old_balance']}
💰 <b>Новый баланс:</b> {result['new_balance']}
📝 <b>Причина:</b> {result['reason'] or 'Не указана'}
🕐 <b>Время:</b> {result['timestamp'][:19]}
📨 <b>Уведомление пользователю:</b> {notification_status}

Операция записана в логи администратора.
            """
            await message.answer(
                success_text,
                reply_markup=get_back_to_admin_keyboard()
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка при выдаче кредитов:</b>\n\n{result.get('error')}",
                reply_markup=get_back_to_admin_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error in credit grant completion: {e}")
        await message.answer(
            "❌ Ошибка при завершении выдачи кредитов.",
            reply_markup=get_back_to_admin_keyboard()
        )
    
    await state.clear()
