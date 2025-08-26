import asyncio
import logging
import os
import sys

# Setup basic logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    logger.info("✅ aiohttp imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import aiohttp: {e}")
    sys.exit(1)

try:
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    logger.info("✅ aiogram imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import aiogram: {e}")
    sys.exit(1)

try:
    from config import Config
    logger.info("✅ config imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import config: {e}")
    sys.exit(1)

try:
    from database.database import init_database
    logger.info("✅ database imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import database: {e}")
    sys.exit(1)

try:
    from handlers import start, generate, payments, admin
    logger.info("✅ handlers imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import handlers: {e}")
    sys.exit(1)

try:
    from middlewares.rate_limit import RateLimitMiddleware
    logger.info("✅ middlewares imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import middlewares: {e}")
    sys.exit(1)

try:
    from webhook_server import init_webhook_server
    logger.info("✅ webhook_server imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import webhook_server: {e}")
    sys.exit(1)

logger.info("🚀 All imports completed successfully, starting bot...")

async def start_bot_polling():
    """Start Telegram bot polling in background"""
    try:
        # Initialize configuration
        config = Config()
        logger.info(f"Starting bot with Veo model: {config.DEFAULT_MODEL}")
        
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
        
        # Start polling
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def main():
    """Main function to start the web server on port 5000"""
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Initialize webhook web application
        app = await init_webhook_server()
        
        # Start bot polling in background
        bot_task = asyncio.create_task(start_bot_polling())
        logger.info("Bot polling started in background...")
        
        # Start payment monitoring in background
        from utils.payment_monitor import payment_monitor
        monitor_task = asyncio.create_task(payment_monitor.start_monitoring())
        logger.info("Payment monitoring started in background...")
        
        # Start web server on port 5000 (main process)
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', 5000)
        await site.start()
        
        logger.info("Web server started on port 5000")
        logger.info("Application endpoints:")
        logger.info("  POST /webhook/veo-complete/{task_id} - Veo completion callbacks")
        logger.info("  POST /webhook/yookassa - YooKassa payment notifications")
        logger.info("  GET /health - Health check")
        
        # Keep the server running indefinitely
        try:
            # Create a future that will never complete to keep the event loop running
            stop_event = asyncio.Event()
            await stop_event.wait()
        except asyncio.CancelledError:
            logger.info("Application shutdown requested")
        finally:
            # Cleanup tasks
            bot_task.cancel()
            monitor_task.cancel()
            await runner.cleanup()
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
