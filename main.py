import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database.database import init_database
from handlers import start, generate, payments, admin
from middlewares.rate_limit import RateLimitMiddleware
# from webhook_server import start_webhook_server  # Temporarily disabled

# Simple logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Main function to start the bot"""
    try:
        # Initialize configuration
        config = Config()
        logger.info(f"Starting bot with Veo model: {config.DEFAULT_MODEL}")
        
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Initialize bot and dispatcher
        bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        dp = Dispatcher(storage=MemoryStorage())
        
        # Register middleware
        dp.message.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())
        
        # Register handlers
        dp.include_router(start.router)
        dp.include_router(generate.router)
        dp.include_router(payments.router)
        dp.include_router(admin.router)
        
        logger.info("Bot starting polling...")
        
        # Start polling (webhook server temporarily disabled due to port conflict)
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
