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

# Credit packages
CREDIT_PACKAGES = {
    "package_50": {"credits": 50, "price_stars": 50, "price_rub": 100, "title": "50 кредитов"},
    "package_100": {"credits": 100, "price_stars": 90, "price_rub": 180, "title": "100 кредитов", "popular": True},
    "package_250": {"credits": 250, "price_stars": 200, "price_rub": 400, "title": "250 кредитов"},
    "package_500": {"credits": 500, "price_stars": 350, "price_rub": 700, "title": "500 кредитов", "bonus": 50},
    "package_1000": {"credits": 1000, "price_stars": 650, "price_rub": 1300, "title": "1000 кредитов", "bonus": 150},
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

💡 <b>1 кредит = ~2₽</b>
🎬 <b>1 видео = 10 кредитов</b>
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "pay_stars")
async def pay_with_stars(callback: CallbackQuery):
    """Show Telegram Stars payment options"""
    text = """
⭐️ <b>Оплата Telegram Stars</b>

Выберите пакет кредитов:

💎 <b>Популярные пакеты:</b>
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_credit_packages_keyboard("stars")
    )
    await callback.answer()

@router.callback_query(F.data == "pay_card")
async def pay_with_card(callback: CallbackQuery):
    """Show card/SBP payment options"""
    text = """
💳 <b>Оплата картой или СБП</b>

Выберите пакет кредитов:

💎 <b>Популярные пакеты:</b>
    """
    
    await callback.message.edit_text(
        text,
        reply_markup=get_credit_packages_keyboard("card")
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
        await callback.message.answer_invoice(
            title=title,
            description=description,
            payload=f"credits_{package_id}_{callback.from_user.id}",
            provider_token="",  # Empty for Telegram Stars
            currency="XTR",
            prices=prices
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
        package_id=package_id
    )
    
    if payment_url:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_credits")]
        ])
        
        await callback.message.edit_text(
            f"💳 <b>Оплата банковской картой или СБП</b>\n\n"
            f"📦 <b>Пакет:</b> {package['title']}\n"
            f"💰 <b>Стоимость:</b> {package['price_rub']} ₽\n\n"
            f"Нажмите кнопку ниже для перехода к оплате:",
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
    """Process successful Telegram Stars payment"""
    payment = message.successful_payment
    payload_parts = payment.invoice_payload.split('_')
    
    if len(payload_parts) >= 3 and payload_parts[0] == "credits":
        package_id = payload_parts[1]
        user_id = int(payload_parts[2])
        
        package = CREDIT_PACKAGES.get(package_id)
        if package:
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
                    reply_markup=get_main_menu_keyboard()
                )
                
                logger.info(f"Stars payment completed: user {user_id}, credits {total_credits}")
            else:
                logger.error(f"User {user_id} not found for payment processing")
        else:
            logger.error(f"Package {package_id} not found")
    else:
        logger.error(f"Invalid payment payload: {payment.invoice_payload}")

# Webhook handler for YooKassa payments would be implemented here
# This requires a separate web server endpoint
