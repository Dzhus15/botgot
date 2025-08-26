import aiohttp
import logging
import uuid
from typing import Optional
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
config = Config()

class PaymentAPI:
    """Payment API integrations"""
    
    def __init__(self):
        self.yookassa_api_key = config.YOOKASSA_API_KEY
        self.yookassa_shop_id = config.YOOKASSA_SHOP_ID
        self.yookassa_base_url = "https://api.yookassa.ru/v3"
    
    async def create_yookassa_payment(
        self, 
        amount: int, 
        description: str, 
        user_id: int,
        package_id: str
    ) -> Optional[str]:
        """Create YooKassa payment and return payment URL"""
        
        if not self.yookassa_api_key or not self.yookassa_shop_id:
            logger.error("YooKassa credentials not configured")
            return None
        
        try:
            import base64
            
            # Prepare authentication
            auth_string = f"{self.yookassa_shop_id}:{self.yookassa_api_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {auth_bytes}",
                "Content-Type": "application/json",
                "Idempotence-Key": str(uuid.uuid4())
            }
            
            # Payment data
            payment_data = {
                "amount": {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/your_bot"  # Replace with your bot link
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "package_id": package_id,
                    "source": "telegram_bot"
                },
                "payment_method_data": {
                    "type": "bank_card"
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.yookassa_base_url}/payments",
                    headers=headers,
                    json=payment_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        confirmation_url = result.get("confirmation", {}).get("confirmation_url")
                        payment_id = result.get("id")
                        
                        if confirmation_url and payment_id:
                            logger.info(f"YooKassa payment created: {payment_id} for user {user_id}")
                            
                            # Store payment info for webhook processing
                            # In a real implementation, you'd store this in database
                            # await self.store_pending_payment(payment_id, user_id, package_id, amount)
                            
                            return confirmation_url
                        else:
                            logger.error(f"Invalid YooKassa response: {result}")
                    else:
                        error_text = await response.text()
                        logger.error(f"YooKassa API error {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"Error creating YooKassa payment: {e}")
        
        return None
    
    async def verify_yookassa_payment(self, payment_id: str) -> dict:
        """Verify YooKassa payment status"""
        
        if not self.yookassa_api_key or not self.yookassa_shop_id:
            logger.error("YooKassa credentials not configured")
            return {"status": "error", "message": "Not configured"}
        
        try:
            import base64
            
            auth_string = f"{self.yookassa_shop_id}:{self.yookassa_api_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {auth_bytes}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.yookassa_base_url}/payments/{payment_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "status": result.get("status"),
                            "amount": result.get("amount", {}).get("value"),
                            "currency": result.get("amount", {}).get("currency"),
                            "metadata": result.get("metadata", {}),
                            "paid": result.get("status") == "succeeded"
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"YooKassa verify error {response.status}: {error_text}")
                        return {"status": "error", "message": error_text}
                        
        except Exception as e:
            logger.error(f"Error verifying YooKassa payment {payment_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def process_yookassa_webhook(self, webhook_data: dict) -> bool:
        """Process YooKassa webhook notification"""
        
        try:
            event_type = webhook_data.get("event")
            payment_object = webhook_data.get("object", {})
            
            if event_type == "payment.succeeded":
                payment_id = payment_object.get("id")
                metadata = payment_object.get("metadata", {})
                amount_value = payment_object.get("amount", {}).get("value")
                
                user_id = metadata.get("user_id")
                package_id = metadata.get("package_id")
                
                if user_id and package_id and amount_value:
                    # Process successful payment
                    success = await self._process_successful_card_payment(
                        user_id=int(user_id),
                        package_id=package_id,
                        payment_id=payment_id,
                        amount=float(amount_value)
                    )
                    
                    logger.info(f"Processed YooKassa payment {payment_id}: {success}")
                    return success
                else:
                    logger.error(f"Invalid webhook data: missing required fields")
            else:
                logger.info(f"Ignoring webhook event: {event_type}")
                
        except Exception as e:
            logger.error(f"Error processing YooKassa webhook: {e}")
        
        return False
    
    async def _process_successful_card_payment(
        self, 
        user_id: int, 
        package_id: str, 
        payment_id: str, 
        amount: float
    ) -> bool:
        """Process successful card payment"""
        
        try:
            from handlers.payments import CREDIT_PACKAGES
            from database.database import db
            from database.models import Transaction, TransactionType, PaymentMethod
            
            package = CREDIT_PACKAGES.get(package_id)
            if not package:
                logger.error(f"Package {package_id} not found")
                return False
            
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
                    description=f"Purchase via YooKassa: {package['title']}",
                    payment_method=PaymentMethod.YOOKASSA,
                    payment_id=payment_id
                )
                await db.create_transaction(transaction)
                
                # Notify user
                await self._notify_payment_success(user_id, total_credits, new_credits)
                
                logger.info(f"Card payment processed: user {user_id}, credits {total_credits}")
                return True
            else:
                logger.error(f"User {user_id} not found")
                
        except Exception as e:
            logger.error(f"Error processing card payment: {e}")
        
        return False
    
    async def _notify_payment_success(self, user_id: int, credits_added: int, total_credits: int):
        """Notify user about successful payment"""
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            from keyboards.inline import get_main_menu_keyboard
            
            success_text = f"""
✅ <b>Оплата успешно завершена!</b>

💰 <b>Добавлено кредитов:</b> {credits_added}
💳 <b>Ваш баланс:</b> {total_credits} кредитов

Теперь вы можете генерировать видео! 🎬
            """
            
            await bot.send_message(
                chat_id=user_id,
                text=success_text,
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error notifying payment success to user {user_id}: {e}")
