import asyncio
import logging
import ipaddress
from aiohttp import web, ClientSession
from config import Config
from database.database import db
from api_integrations.veo_api import VeoAPI
from api_integrations.payment_api import PaymentAPI
from utils.logger import get_logger
import json

logger = get_logger(__name__)
config = Config()

# YooKassa official IP ranges for webhook security (updated 2024)
YOOKASSA_IP_RANGES = [
    '185.71.76.0/27',
    '185.71.77.0/27', 
    '77.75.153.0/25',
    '77.75.154.0/25',  # Added - your webhook came from 77.75.154.206
    '77.75.156.11/32',
    '77.75.156.35/32',
    '2a02:5180:0:1509::/64',
    '2a02:5180:0:2655::/64'
]

def is_yookassa_ip(ip_address: str) -> bool:
    """Check if IP address is from YooKassa official ranges"""
    try:
        client_ip = ipaddress.ip_address(ip_address)
        for ip_range in YOOKASSA_IP_RANGES:
            if client_ip in ipaddress.ip_network(ip_range, strict=False):
                return True
        return False
    except ValueError:
        logger.error(f"Invalid IP address format: {ip_address}")
        return False

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

def get_real_ip(request):
    """Get real client IP address from request headers"""
    # Check for forwarded IP headers (common in proxy setups)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(',')[0].strip()
    
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # Fallback to direct connection IP
    return request.remote

async def handle_yookassa_webhook(request):
    """Handle YooKassa payment webhook notifications with security checks"""
    try:
        # Get client IP and validate it's from YooKassa
        client_ip = get_real_ip(request)
        logger.info(f"Received YooKassa webhook from IP: {client_ip}")
        
        # Логируем все входящие запросы для отладки
        logger.info(f"Webhook request from IP: {client_ip}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Проверяем IP только если это не локальный запрос
        if client_ip not in ['127.0.0.1', '::1'] and not is_yookassa_ip(client_ip):
            logger.warning(f"Unauthorized webhook attempt from IP: {client_ip}")
            return web.Response(text="Forbidden", status=403)
        
        # Parse webhook data
        try:
            webhook_data = await request.json()
        except Exception as e:
            logger.error(f"Invalid JSON in YooKassa webhook: {e}")
            return web.Response(text="Invalid JSON", status=400)
        
        logger.info(f"Processing YooKassa webhook: {webhook_data.get('event', 'unknown')}")
        
        # Process webhook using PaymentAPI
        payment_api = PaymentAPI()
        success = await payment_api.process_yookassa_webhook(webhook_data)
        
        if success:
            logger.info("YooKassa webhook processed successfully")
        else:
            logger.error("Failed to process YooKassa webhook")
        
        # Always return 200 OK to YooKassa regardless of processing result
        # This prevents them from retrying the webhook
        return web.Response(text="OK", status=200)
        
    except Exception as e:
        logger.error(f"Error handling YooKassa webhook: {e}")
        # Still return 200 to prevent retries
        return web.Response(text="OK", status=200)

async def init_webhook_server():
    """Initialize and start the webhook server"""
    app = web.Application()
    
    # Add webhook routes
    app.router.add_post('/webhook/veo-complete/{task_id}', handle_veo_callback)
    app.router.add_post('/webhook/yookassa', handle_yookassa_webhook)
    
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
        logger.info("  POST /webhook/yookassa - YooKassa payment notifications")
        logger.info("  GET /health - Health check")
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour
            
    except Exception as e:
        logger.error(f"Error starting webhook server: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(start_webhook_server())