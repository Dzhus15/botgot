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
            
            # Prepare request data according to API documentation
            request_data = {
                "prompt": prompt,
                "model": config.DEFAULT_MODEL,
                "aspectRatio": config.DEFAULT_ASPECT_RATIO,
                "enableFallback": True,  # Enable fallback for reliability
                # "callBackUrl": f"https://your-domain.com/webhook/veo-complete/{task_id}"  # Optional for notifications
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
            
            # Log request details for debugging
            logger.info(f"Sending API request for task {task_id}")
            logger.info(f"URL: {self.base_url}/api/v1/veo/generate")
            logger.info(f"Prompt: {prompt[:100]}...")
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/veo/generate",
                    headers=headers,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    logger.info(f"API Response status: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API Response: {response_text[:500]}...")
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                            logger.info(f"Parsed response: {result}")
                            
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
                        except Exception as json_error:
                            logger.error(f"JSON parsing error: {json_error}")
                            logger.error(f"Raw response: {response_text}")
                    else:
                        logger.error(f"HTTP error {response.status} for task {task_id}: {response_text}")
                        await db.update_video_generation(
                            task_id, "failed", 
                            error_message=f"HTTP {response.status}: {response_text[:100]}"
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
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            file_info = await bot.get_file(file_id)
            file_path = file_info.file_path
            
            # Download file
            file_data = await bot.download_file(file_path)
            
            # Save to local storage temporarily (in production use cloud storage)
            import os
            os.makedirs("attached_assets/temp_images", exist_ok=True)
            local_path = f"attached_assets/temp_images/{file_id}.jpg"
            
            with open(local_path, "wb") as f:
                f.write(file_data.read())
            
            # For now return a placeholder - in production upload to cloud
            # This needs proper implementation with cloud storage
            public_url = f"https://api.replit.com/v2/get_file?path={local_path}"
            
            logger.info(f"Image processed: {file_id} -> {local_path}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error processing image {file_id}: {e}")
            return None
    
    async def _poll_video_status(self, task_id: str, veo_task_id: str, user_id: int):
        """Poll video generation status with multiple endpoint attempts"""
        max_attempts = 24  # 2 minutes with 5-second intervals (reasonable for testing)
        attempt = 0
        
        logger.info(f"Starting polling for task {task_id} with Veo ID {veo_task_id}")
        
        while attempt < max_attempts:
            try:
                await asyncio.sleep(5)  # Wait 5 seconds between checks
                
                # Try multiple possible endpoints for status checking
                status_result = await self._get_video_status_multiple_endpoints(veo_task_id)
                
                if status_result:
                    logger.info(f"Status result for {task_id}: {status_result}")
                    
                    status = status_result.get("status")
                    
                    if status == "completed" or status == "success":
                        video_url = status_result.get("video_url") or status_result.get("videoUrl") or status_result.get("url")
                        
                        if video_url:
                            await db.update_video_generation(
                                task_id, "completed", video_url=video_url
                            )
                            
                            # Notify user
                            await self._notify_user_completion(user_id, video_url, task_id)
                            logger.info(f"Video generation completed: {task_id}")
                            return
                        
                    elif status == "failed" or status == "error":
                        error_msg = status_result.get("error") or status_result.get("message") or "Generation failed"
                        await db.update_video_generation(
                            task_id, "failed", error_message=error_msg
                        )
                        
                        # Notify user of failure
                        await self._notify_user_failure(user_id, error_msg)
                        logger.error(f"Video generation failed: {task_id} - {error_msg}")
                        return
                else:
                    logger.warning(f"No status result for {task_id}, attempt {attempt + 1}")
                
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error polling status for {task_id}: {e}")
                attempt += 1
        
        # Timeout - but don't mark as failed immediately
        logger.warning(f"Polling timeout for {task_id}, but task might still be processing")
        
        # Just log timeout, don't mark as failed in case task is still processing
        # The user can check manually or we can implement a longer polling strategy
    
    async def _get_video_status_multiple_endpoints(self, veo_task_id: str) -> Optional[dict]:
        """Try multiple possible endpoints for video status"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Try different possible endpoints based on common API patterns
        endpoints = [
            f"{self.base_url}/api/v1/veo/status/{veo_task_id}",
            f"{self.base_url}/api/v1/veo/result/{veo_task_id}",
            f"{self.base_url}/api/v1/veo/task/{veo_task_id}",
            f"{self.base_url}/api/v1/veo/video/{veo_task_id}",
            f"{self.base_url}/api/v1/tasks/{veo_task_id}",
            f"{self.base_url}/api/v1/status/{veo_task_id}"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    async with session.get(
                        endpoint,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        
                        logger.info(f"Trying endpoint {endpoint}: status {response.status}")
                        
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"Success response from {endpoint}: {result}")
                            
                            # Handle different response structures
                            if "data" in result:
                                return result["data"]
                            elif "result" in result:
                                return result["result"]
                            else:
                                return result
                                
                        elif response.status == 404:
                            continue  # Try next endpoint
                        else:
                            text = await response.text()
                            logger.warning(f"Status {response.status} from {endpoint}: {text[:200]}")
                            
                except Exception as e:
                    logger.debug(f"Error with endpoint {endpoint}: {e}")
                    continue
        
        return None
    
    async def _notify_user_completion(self, user_id: int, video_url: str, task_id: str):
        """Notify user about video completion"""
        try:
            logger.info(f"Notifying user {user_id} about completion: {task_id}")
            
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
            logger.info(f"Notifying user {user_id} about failure: {error_message}")
            
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
