import asyncio
import logging
from aiohttp import web, ClientSession
from config import Config
from database.database import db
from api_integrations.veo_api import VeoAPI
from utils.logger import get_logger
import json

logger = get_logger(__name__)
config = Config()

async def handle_veo_callback(request):
    """Handle Veo API completion callbacks"""
    try:
        # Get task ID from URL path
        task_id = request.match_info.get('task_id')
        if not task_id:
            logger.error("No task_id in callback URL")
            return web.Response(text="Missing task_id", status=400)
        
        # Parse callback data
        callback_data = await request.json()
        logger.info(f"Received Veo callback for task {task_id}: {callback_data}")
        
        # Extract video information from callback
        status = callback_data.get("status", "unknown")
        video_url = callback_data.get("video_url") or callback_data.get("videoUrl") or callback_data.get("url")
        error_message = callback_data.get("error") or callback_data.get("message")
        
        # Get user ID from database using task_id
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT user_id FROM video_generations WHERE task_id = ?",
                (task_id,)
            )
            row = await cursor.fetchone()
            if not row:
                logger.error(f"Video task not found: {task_id}")
                return web.Response(text="Task not found", status=404)
            
            user_id = row[0]
        
        # Initialize VeoAPI for user notification
        veo_api = VeoAPI()
        
        if status == "completed" or status == "success":
            if video_url:
                # Update database
                await db.update_video_generation(task_id, "completed", video_url=video_url)
                
                # Notify user
                await veo_api._notify_user_completion(user_id, video_url, task_id)
                logger.info(f"Video completed via callback: {task_id}")
            else:
                logger.error(f"Completed status but no video URL for task {task_id}")
                
        elif status == "failed" or status == "error":
            # Update database
            error_msg = error_message or "Generation failed"
            await db.update_video_generation(task_id, "failed", error_message=error_msg)
            
            # Notify user
            await veo_api._notify_user_failure(user_id, error_msg)
            logger.error(f"Video failed via callback: {task_id} - {error_msg}")
        
        return web.Response(text="OK", status=200)
        
    except Exception as e:
        logger.error(f"Error handling Veo callback: {e}")
        return web.Response(text="Internal error", status=500)

async def init_webhook_server():
    """Initialize and start the webhook server"""
    app = web.Application()
    
    # Add webhook routes
    app.router.add_post('/webhook/veo-complete/{task_id}', handle_veo_callback)
    
    # Health check endpoint
    async def health(request):
        return web.Response(text="OK")
    
    app.router.add_get('/health', health)
    
    return app

async def start_webhook_server():
    """Start the webhook server on port 5000"""
    try:
        app = await init_webhook_server()
        
        # Start server on port 5000 (Replit's standard port)
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', 5000)
        await site.start()
        
        logger.info("Webhook server started on port 5000")
        logger.info("Webhook endpoints:")
        logger.info("  POST /webhook/veo-complete/{task_id} - Veo completion callbacks")
        logger.info("  GET /health - Health check")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour
            
    except Exception as e:
        logger.error(f"Error starting webhook server: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(start_webhook_server())