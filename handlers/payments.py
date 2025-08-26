from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, SuccessfulPayment
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import db
from database.models import Transaction, TransactionType, PaymentMethod
from keyboards.inline import get_payment_menu_keyboard, get_back_to_menu_keyboard, get_credit_packages_keyboard
from api_integrations.payment_api import PaymentAPI
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
router = Router()
config = Config()

class PaymentStates(StatesGroup):
    waiting_custom_amount = State()

# Credit packages - правильные цены
CREDIT_PACKAGES = {
    "package_1": {"credits": 10, "price_stars": 79, "price_rub": 79, "title": "1 генерация видео (10 кредитов)"},
    "package_5": {"credits": 50, "price_stars": 399, "price_rub": 399, "title": "5 генераций видео (50 кредитов)"},
    "package_10": {"credits": 100, "price_stars": 749, "price_rub": 749, "title": "10 генераций видео (100 кредитов)", "popular": True},
    "package_50": {"credits": 500, "price_stars": 3499, "price_rub": 3499, "title": "50 генераций видео (500 кредитов)", "bonus": 50},
}

@router.callback_query(F.data == "buy_credits")
async def buy_credits_menu(callback: CallbackQuery):
    """Show credits purchase menu"""
    user = await db.get_user(callback.from_user.id)
    credits = user.credits if user else 0
    
    text = f"""
💰 <b>Покупка кредитов</b>

💳 <b>Ваш текущий баланс:</b> {credits} кредитов

Выберите способ оплаты:

⭐️ <b>Telegram Stars</b> - быстро и удобно
💳 <b>Банковская карта/СБП</b> - через ЮКасса

💡 <b>1 кредит от 7₽</b> (в большом пакете)
🎬 <b>1 видео = 10 кредитов (от 70₽)</b>
    """
    
    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_payment_menu_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data == "pay_stars")
async def pay_with_stars(callback: CallbackQuery):
    """Show Telegram Stars payment options"""
    text = """
⭐️ <b>Оплата Telegram Stars</b>

🎬 <b>1 видео = 10 кредитов</b>
💰 <b>Выгодные цены:</b>
• 1 генерация - 79⭐️ (7.9⭐️ за кредит)
• 5 генераций - 399⭐️ (7.98⭐️ за кредит) 🔥
• 10 генераций - 749⭐️ (7.49⭐️ за кредит) 
• 50 генераций - 3499⭐️ (7⭐️ за кредит) + 🎁 бонус!

Выберите пакет кредитов:
    """
    
    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_credit_packages_keyboard("stars")
        )
    await callback.answer()

@router.callback_query(F.data == "pay_card")
async def pay_with_card(callback: CallbackQuery):
    """Show card payment options"""
    text = """
💳 <b>Оплата банковской картой</b>

🎬 <b>1 видео = 10 кредитов</b>
💰 <b>Выгодные цены:</b>
• 1 генерация - 79₽ (7.9₽ за кредит)
• 5 генераций - 399₽ (7.98₽ за кредит) 🔥 
• 10 генераций - 749₽ (7.49₽ за кредит)
• 50 генераций - 3499₽ (7₽ за кредит) + 🎁 бонус!

Выберите пакет кредитов:
    """
    
    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_credit_packages_keyboard("card")
        )
    await callback.answer()

@router.callback_query(F.data == "pay_sbp")
async def pay_with_sbp(callback: CallbackQuery):
    """Show SBP payment options"""
    text = """
🏦 <b>Оплата через СБП</b>

<b>Система быстрых платежей</b> - мгновенные переводы 24/7

🎬 <b>1 видео = 10 кредитов</b>
💰 <b>Выгодные цены:</b>
• 1 генерация - 79₽ (7.9₽ за кредит)
• 5 генераций - 399₽ (7.98₽ за кредит) 🔥
• 10 генераций - 749₽ (7.49₽ за кредит)
• 50 генераций - 3499₽ (7₽ за кредит) + 🎁 бонус!

Выберите пакет кредитов:
    """
    
    if callback.message:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_credit_packages_keyboard("sbp")
        )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_stars_"))
async def process_stars_payment(callback: CallbackQuery):
    """Process Telegram Stars payment"""
    package_id = callback.data.replace("buy_stars_", "")
    package = CREDIT_PACKAGES.get(package_id)
    
    if not package:
        await callback.answer("❌ Неверный пакет")
        return
    
    # Create invoice for Telegram Stars
    title = f"💰 {package['title']}"
    description = f"Покупка {package['credits']} кредитов для генерации AI видео"
    
    if package.get('bonus'):
        description += f" + {package['bonus']} бонусных кредитов!"
    
    prices = [{"label": "XTR", "amount": package['price_stars']}]
    
    try:
        if callback.message:
            await callback.message.answer_invoice(
                title=title,
                description=description,
                payload=f"credits_{package_id}_{callback.from_user.id}",
                provider_token="",  # Empty for Telegram Stars
                currency="XTR",
                prices=[{"label": "XTR", "amount": package['price_stars']}]
            )
        await callback.answer("✅ Счет создан!")
    except Exception as e:
        logger.error(f"Error creating Stars invoice: {e}")
        await callback.answer("❌ Ошибка создания счета")

@router.callback_query(F.data.startswith("buy_card_"))
async def process_card_payment(callback: CallbackQuery):
    """Process card/SBP payment through YooKassa"""
    package_id = callback.data.replace("buy_card_", "")
    package = CREDIT_PACKAGES.get(package_id)
    
    if not package:
        await callback.answer("❌ Неверный пакет")
        return
    
    # Create payment through YooKassa
    payment_api = PaymentAPI()
    
    description = f"Покупка {package['credits']} кредитов"
    if package.get('bonus'):
        description += f" + {package['bonus']} бонусных кредитов"
    
    payment_url = await payment_api.create_yookassa_payment(
        amount=package['price_rub'],
        description=description,
        user_id=callback.from_user.id,
        package_id=package_id,
        payment_method="bank_card"
    )
    
    if payment_url:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_credits")]
        ])
        
        await callback.message.edit_text(
            f"💳 <b>Оплата банковской картой</b>\n\n"
            f"📦 <b>Пакет:</b> {package['title']}\n"
            f"💰 <b>Стоимость:</b> {package['price_rub']} ₽\n\n"
            f"Нажмите кнопку ниже для перехода к оплате:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка создания платежа. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("buy_sbp_"))
async def process_sbp_payment(callback: CallbackQuery):
    """Process SBP payment through YooKassa"""
    package_id = callback.data.replace("buy_sbp_", "")
    package = CREDIT_PACKAGES.get(package_id)
    
    if not package:
        await callback.answer("❌ Неверный пакет")
        return
    
    # Create payment through YooKassa with SBP method
    payment_api = PaymentAPI()
    
    description = f"Покупка {package['credits']} кредитов"
    if package.get('bonus'):
        description += f" + {package['bonus']} бонусных кредитов"
    
    payment_url = await payment_api.create_yookassa_payment(
        amount=package['price_rub'],
        description=description,
        user_id=callback.from_user.id,
        package_id=package_id,
        payment_method="sbp"
    )
    
    if payment_url:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏦 Оплатить через СБП", url=payment_url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_credits")]
        ])
        
        await callback.message.edit_text(
            f"🏦 <b>Оплата через СБП</b>\n\n"
            f"📦 <b>Пакет:</b> {package['title']}\n"
            f"💰 <b>Стоимость:</b> {package['price_rub']} ₽\n\n"
            f"<b>Система быстрых платежей</b> - мгновенные переводы 24/7\n"
            f"Нажмите кнопку ниже для перехода к оплате:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка создания платежа. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await callback.answer()

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Process pre-checkout query for Telegram Stars"""
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Process successful Telegram Stars payment with enhanced validation"""
    payment = message.successful_payment
    
    # SECURITY: Validate that payment is from the actual user who initiated it
    actual_user_id = message.from_user.id
    
    # Parse and validate payload format
    try:
        payload_parts = payment.invoice_payload.split('_')
        if len(payload_parts) < 3 or payload_parts[0] != "credits":
            logger.error(f"Invalid payment payload format: {payment.invoice_payload}")
            return
        
        package_id = payload_parts[1]
        claimed_user_id = int(payload_parts[2])
        
        # SECURITY: Ensure user_id in payload matches actual payment sender
        if claimed_user_id != actual_user_id:
            logger.error(f"Payment fraud attempt: payload claims user {claimed_user_id} but payment from {actual_user_id}")
            return
        
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing payment payload: {e}")
        return
    
    user_id = actual_user_id  # Use verified user ID
    
    # Validate package exists and payment amount matches
    package = CREDIT_PACKAGES.get(package_id)
    if not package:
        logger.error(f"Invalid package_id in payment: {package_id}")
        return
    
    # SECURITY: Verify payment amount matches expected package price
    expected_amount = package['price_stars']
    actual_amount = payment.total_amount
    
    if actual_amount != expected_amount:
        logger.error(f"Payment amount mismatch: expected {expected_amount} XTR, got {actual_amount} XTR")
        return
    
    # Check for duplicate payment processing
    payment_id = payment.telegram_payment_charge_id
    if await db.payment_exists(payment_id):
        logger.warning(f"Duplicate Telegram Stars payment detected: {payment_id}")
        return
    
    # Process the validated payment
    # Calculate total credits (including bonus)
    total_credits = package['credits']
    if package.get('bonus'):
        total_credits += package['bonus']
    
    # Update user credits
    user = await db.get_user(user_id)
    if user:
        new_credits = user.credits + total_credits
        await db.update_user_credits(user_id, new_credits)
        
        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            type=TransactionType.CREDIT_PURCHASE,
            amount=total_credits,
            description=f"Purchase via Telegram Stars: {package['title']}",
            payment_method=PaymentMethod.TELEGRAM_STARS,
            payment_id=payment.telegram_payment_charge_id
        )
        await db.create_transaction(transaction)
        
        success_text = f"""
✅ <b>Платеж успешно завершен!</b>

💰 <b>Добавлено кредитов:</b> {total_credits}
💳 <b>Ваш баланс:</b> {new_credits} кредитов

Теперь вы можете генерировать видео! 🎬
        """
        
        from keyboards.inline import get_main_menu_keyboard
        await message.answer(
            success_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
        
        logger.info(f"Stars payment completed: user {user_id}, credits {total_credits}")
    else:
        logger.error(f"User {user_id} not found for payment processing")

# Webhook handler for YooKassa payments would be implemented here
# This requires a separate web server endpoint
