import aiohttp
import asyncio
import logging
from typing import Optional
from config import Config
from database.database import db
from database.models import GenerationType
from utils.logger import get_logger

logger = get_logger(__name__)
config = Config()

class VeoAPI:
    """Veo API integration for video generation"""
    
    def __init__(self):
        self.base_url = config.VEO_API_BASE_URL
        self.api_key = config.VEO_API_KEY
        
    async def generate_video(
        self, 
        task_id: str,
        prompt: str, 
        generation_type: GenerationType,
        user_id: int,
        image_file_id: str = None
    ) -> bool:
        """Generate video using Veo API"""
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare request data
            request_data = {
                "prompt": prompt,
                "model": config.DEFAULT_MODEL,
                "aspectRatio": config.DEFAULT_ASPECT_RATIO,
                "enableFallback": True  # Enable fallback for reliability
            }
            
            # Handle image-to-video
            if generation_type == GenerationType.IMAGE_TO_VIDEO and image_file_id:
                # In a real implementation, you would need to:
                # 1. Download the image from Telegram
                # 2. Upload it to a public URL (e.g., cloud storage)
                # 3. Use that URL in the API request
                
                # For now, we'll simulate this process
                image_url = await self._upload_telegram_image(image_file_id)
                if image_url:
                    request_data["imageUrls"] = [image_url]
                else:
                    logger.error(f"Failed to upload image for task {task_id}")
                    await db.update_video_generation(
                        task_id, "failed", 
                        error_message="Failed to process image"
                    )
                    return False
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/veo/generate",
                    headers=headers,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("code") == 200:
                            veo_task_id = result.get("data", {}).get("taskId")
                            if veo_task_id:
                                # Update database with Veo task ID
                                await db.update_video_generation(task_id, "processing")
                                
                                # Start polling for completion
                                asyncio.create_task(
                                    self._poll_video_status(task_id, veo_task_id, user_id)
                                )
                                
                                logger.info(f"Video generation started: {task_id} -> {veo_task_id}")
                                return True
                            else:
                                logger.error(f"No task ID in response: {result}")
                        else:
                            error_msg = result.get("msg", "Unknown API error")
                            logger.error(f"API error for task {task_id}: {error_msg}")
                            await db.update_video_generation(
                                task_id, "failed", 
                                error_message=error_msg
                            )
                    else:
                        error_text = await response.text()
                        logger.error(f"HTTP error {response.status} for task {task_id}: {error_text}")
                        await db.update_video_generation(
                            task_id, "failed", 
                            error_message=f"HTTP {response.status}"
                        )
                        
        except asyncio.TimeoutError:
            logger.error(f"Timeout error for task {task_id}")
            await db.update_video_generation(
                task_id, "failed", 
                error_message="Request timeout"
            )
        except Exception as e:
            logger.error(f"Exception in video generation for task {task_id}: {e}")
            await db.update_video_generation(
                task_id, "failed", 
                error_message=str(e)
            )
        
        return False
    
    async def _upload_telegram_image(self, file_id: str) -> Optional[str]:
        """Upload Telegram image to public URL"""
        # This is a simplified implementation
        # In production, you would:
        # 1. Use Bot.get_file() to get file path
        # 2. Download the file
        # 3. Upload to cloud storage (AWS S3, Google Cloud, etc.)
        # 4. Return public URL
        
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            file_info = await bot.get_file(file_id)
            file_path = file_info.file_path
            
            # Download file
            file_data = await bot.download_file(file_path)
            
            # In a real implementation, upload to cloud storage
            # For now, return a placeholder URL
            placeholder_url = f"https://example.com/images/{file_id}.jpg"
            
            logger.info(f"Image uploaded: {file_id} -> {placeholder_url}")
            return placeholder_url
            
        except Exception as e:
            logger.error(f"Error uploading image {file_id}: {e}")
            return None
    
    async def _poll_video_status(self, task_id: str, veo_task_id: str, user_id: int):
        """Poll video generation status"""
        max_attempts = 60  # 5 minutes with 5-second intervals
        attempt = 0
        
        while attempt < max_attempts:
            try:
                await asyncio.sleep(5)  # Wait 5 seconds between checks
                
                status_result = await self._get_video_status(veo_task_id)
                
                if status_result:
                    status = status_result.get("status")
                    
                    if status == "completed":
                        video_url = status_result.get("video_url")
                        await db.update_video_generation(
                            task_id, "completed", video_url=video_url
                        )
                        
                        # Notify user
                        await self._notify_user_completion(user_id, video_url, task_id)
                        logger.info(f"Video generation completed: {task_id}")
                        return
                        
                    elif status == "failed":
                        error_msg = status_result.get("error", "Generation failed")
                        await db.update_video_generation(
                            task_id, "failed", error_message=error_msg
                        )
                        
                        # Notify user of failure
                        await self._notify_user_failure(user_id, error_msg)
                        logger.error(f"Video generation failed: {task_id} - {error_msg}")
                        return
                
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error polling status for {task_id}: {e}")
                attempt += 1
        
        # Timeout
        await db.update_video_generation(
            task_id, "failed", error_message="Generation timeout"
        )
        await self._notify_user_failure(user_id, "Generation timeout")
        logger.error(f"Video generation timeout: {task_id}")
    
    async def _get_video_status(self, veo_task_id: str) -> Optional[dict]:
        """Get video generation status from Veo API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                # This endpoint would be for checking status
                # The actual endpoint might be different
                async with session.get(
                    f"{self.base_url}/api/v1/veo/status/{veo_task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return result.get("data", {})
                        
        except Exception as e:
            logger.error(f"Error getting video status {veo_task_id}: {e}")
        
        return None
    
    async def _notify_user_completion(self, user_id: int, video_url: str, task_id: str):
        """Notify user about video completion"""
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            from keyboards.inline import get_main_menu_keyboard
            
            await bot.send_message(
                chat_id=user_id,
                text=f"✅ <b>Ваше видео готово!</b>\n\n"
                     f"🎬 Видео успешно сгенерировано и готово к просмотру.\n"
                     f"📥 Скачайте видео по ссылке ниже:",
                reply_markup=get_main_menu_keyboard()
            )
            
            # Send video file
            if video_url and video_url.startswith("http"):
                await bot.send_video(
                    chat_id=user_id,
                    video=video_url,
                    caption="🎬 Ваше AI-видео готово!"
                )
            
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")
    
    async def _notify_user_failure(self, user_id: int, error_message: str):
        """Notify user about generation failure"""
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            from keyboards.inline import get_main_menu_keyboard
            
            user_friendly_error = self._get_user_friendly_error(error_message)
            
            await bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>Ошибка генерации видео</b>\n\n"
                     f"К сожалению, не удалось сгенерировать ваше видео.\n\n"
                     f"💡 <b>Причина:</b> {user_friendly_error}\n\n"
                     f"💰 Кредиты возвращены на ваш счет.\n"
                     f"🔄 Попробуйте еще раз с другим запросом.",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error notifying user failure {user_id}: {e}")
    
    def _get_user_friendly_error(self, error_message: str) -> str:
        """Convert technical error to user-friendly message"""
        error_lower = error_message.lower()
        
        if "timeout" in error_lower:
            return "Превышено время ожидания. Сервис перегружен."
        elif "content policies" in error_lower or "flagged" in error_lower:
            return "Запрос нарушает правила контента. Измените описание."
        elif "insufficient credits" in error_lower:
            return "Недостаточно кредитов на счете."
        elif "rate limit" in error_lower:
            return "Слишком много запросов. Подождите немного."
        else:
            return "Техническая ошибка сервиса. Попробуйте позже."
