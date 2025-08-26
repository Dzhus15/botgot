from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Any, Awaitable, Union
import time

from utils.rate_limiter import rate_limiter
from utils.logger import get_logger

logger = get_logger(__name__)

class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware for aiogram"""
    
    def __init__(self):
        self.rate_limiter = rate_limiter
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        # Get user ID from different event types
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            # Skip rate limiting for users in generation states (uploading images/prompts)
            if hasattr(data.get('state'), 'get_state'):
                try:
                    current_state = await data['state'].get_state()
                    if current_state and ('waiting_image' in current_state or 'waiting_text_prompt' in current_state):
                        return await handler(event, data)
                except:
                    pass  # Continue with normal rate limiting if state check fails
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            # Skip rate limiting for navigation callback queries
            navigation_callbacks = [
                "main_menu", "buy_credits", "pay_stars", "pay_card", 
                "generate_video", "text_to_video", "image_to_video",
                "admin_panel", "user_stats", "broadcast_menu", "back_to_menu"
            ]
            if event.data in navigation_callbacks:
                return await handler(event, data)
        
        # Skip rate limiting if no user ID found
        if not user_id:
            return await handler(event, data)
        
        # Check rate limit
        if not self.rate_limiter.is_allowed(user_id):
            reset_time = self.rate_limiter.get_reset_time(user_id)
            current_time = time.time()
            
            if reset_time > current_time:
                wait_seconds = int(reset_time - current_time) + 1
                
                rate_limit_message = (
                    f"🚫 <b>Превышен лимит запросов!</b>\n\n"
                    f"⏱ Попробуйте снова через {wait_seconds} секунд.\n\n"
                    f"💡 Это ограничение помогает поддерживать качество сервиса для всех пользователей."
                )
                
                if isinstance(event, Message):
                    await event.answer(rate_limit_message)
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        f"Превышен лимит! Ждите {wait_seconds} сек.",
                        show_alert=True
                    )
                
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return  # Don't proceed to handler
        
        # Proceed to handler if rate limit not exceeded
        return await handler(event, data)
