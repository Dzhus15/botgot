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
        package_id: str,
        payment_method: str = "bank_card"
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
            
            # Payment data with receipt (required by 54-FZ)
            payment_data = {
                "amount": {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/VideoAnalizAiBot?start=payment_success"
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "package_id": package_id,
                    "source": "telegram_bot"
                },
                "payment_method_data": {
                    "type": payment_method
                },
                "receipt": {
                    "customer": {
                        "email": "customer@example.com"
                    },
                    "items": [
                        {
                            "description": description,
                            "quantity": "1.00",
                            "amount": {
                                "value": f"{amount}.00",
                                "currency": "RUB"
                            },
                            "vat_code": 1  # НДС не облагается
                        }
                    ]
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
        """Process YooKassa webhook notification with enhanced security"""
        
        try:
            # Validate webhook data structure
            if not isinstance(webhook_data, dict):
                logger.error("Invalid webhook data type")
                return False
            
            event_type = webhook_data.get("event")
            payment_object = webhook_data.get("object", {})
            
            logger.info(f"Processing YooKassa webhook: event={event_type}")
            
            if event_type == "payment.succeeded":
                # Validate required fields
                payment_id = payment_object.get("id")
                if not payment_id:
                    logger.error("Missing payment ID in webhook")
                    return False
                
                metadata = payment_object.get("metadata", {})
                amount_data = payment_object.get("amount", {})
                amount_value = amount_data.get("value")
                currency = amount_data.get("currency")
                
                # Validate currency
                if currency != "RUB":
                    logger.error(f"Invalid currency in payment {payment_id}: {currency}")
                    return False
                
                user_id = metadata.get("user_id")
                package_id = metadata.get("package_id")
                source = metadata.get("source")
                
                # Validate metadata
                if not all([user_id, package_id, amount_value]):
                    logger.error(f"Missing required fields in payment {payment_id}")
                    return False
                
                # Validate source
                if source != "telegram_bot":
                    logger.warning(f"Unexpected payment source: {source}")
                
                # Process successful payment
                success = await self._process_successful_card_payment(
                    user_id=int(user_id),
                    package_id=package_id,
                    payment_id=payment_id,
                    amount=float(amount_value)
                )
                
                logger.info(f"YooKassa payment {payment_id} processed: {success}")
                return success
                
            elif event_type == "payment.canceled":
                payment_id = payment_object.get("id")
                logger.info(f"Payment canceled: {payment_id}")
                return True
                
            else:
                logger.info(f"Ignoring webhook event: {event_type}")
                return True
                
        except ValueError as e:
            logger.error(f"Data validation error in YooKassa webhook: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing YooKassa webhook: {e}")
        
        return False
    
    async def _process_successful_card_payment(
        self, 
        user_id: int, 
        package_id: str, 
        payment_id: str, 
        amount: float
    ) -> bool:
        """Process successful card payment with duplicate protection"""
        
        try:
            from handlers.payments import CREDIT_PACKAGES
            from database.database import db
            from database.models import Transaction, TransactionType, PaymentMethod
            
            # Check for duplicate payment
            if await db.payment_exists(payment_id):
                logger.warning(f"Duplicate payment attempt detected: {payment_id}")
                return False
            
            package = CREDIT_PACKAGES.get(package_id)
            if not package:
                logger.error(f"Package {package_id} not found")
                return False
            
            # Validate payment amount matches package price
            expected_amount = float(package['price_rub'])
            if abs(float(amount) - expected_amount) > 0.01:  # Allow small floating point differences
                logger.error(f"Payment amount mismatch: expected {expected_amount}, got {amount}")
                return False
            
            # Calculate total credits (including bonus)
            total_credits = package['credits']
            if package.get('bonus'):
                total_credits += package['bonus']
            
            # Verify user exists and get current credits
            user = await db.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found for payment {payment_id}")
                return False
            
            # Create transaction record FIRST (for atomicity)
            transaction = Transaction(
                user_id=user_id,
                type=TransactionType.CREDIT_PURCHASE,
                amount=total_credits,
                description=f"YooKassa: {package['title']} ({payment_id})",
                payment_method=PaymentMethod.YOOKASSA,
                payment_id=payment_id
            )
            
            transaction_created = await db.create_transaction(transaction)
            if not transaction_created:
                logger.error(f"Failed to create transaction record for payment {payment_id}")
                return False
            
            # Update user credits
            new_credits = user.credits + total_credits
            credits_updated = await db.update_user_credits(user_id, new_credits)
            
            if not credits_updated:
                logger.error(f"Failed to update credits for user {user_id}, payment {payment_id}")
                # Note: Transaction is already recorded, manual intervention may be needed
                return False
            
            # Notify user about successful payment
            try:
                await self._notify_payment_success(user_id, total_credits, new_credits)
            except Exception as e:
                logger.error(f"Failed to notify user {user_id} about payment success: {e}")
                # Don't return False here - payment was processed successfully
            
            logger.info(f"Payment processed successfully: user={user_id}, payment_id={payment_id}, credits={total_credits}")
            return True
                
        except ValueError as e:
            logger.error(f"Validation error processing payment {payment_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing payment {payment_id}: {e}")
        
        return False
    
    async def _notify_payment_success(self, user_id: int, credits_added: int, total_credits: int):
        """Notify user about successful payment"""
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            from keyboards.inline import get_main_menu_keyboard
            
            success_text = f"""
✅ **Оплата успешно завершена!**

💰 **Добавлено кредитов:** {credits_added}
💳 **Ваш баланс:** {total_credits} кредитов

Теперь вы можете генерировать видео! 🎬
            """
            
            await bot.send_message(
                chat_id=user_id,
                text=success_text,
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error notifying payment success to user {user_id}: {e}")
