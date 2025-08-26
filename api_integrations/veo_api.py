import aiohttp
import asyncio
import logging
import os
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
        image_file_id: Optional[str] = None
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
                "enableFallback": True,  # Enable fallback for higher success rates
            }
            
            # Callback URL temporarily disabled due to port conflict
            # repl_slug = os.getenv('REPL_SLUG')
            # repl_owner = os.getenv('REPL_OWNER')
            # if repl_slug and repl_owner:
            #     callback_url = f"https://{repl_slug}.{repl_owner}.repl.co/webhook/veo-complete/{task_id}"
            #     request_data["callBackUrl"] = callback_url
            #     logger.info(f"Using callback URL: {callback_url}")
            
            # Handle image-to-video
            if generation_type == GenerationType.IMAGE_TO_VIDEO and image_file_id:
                # Upload image using kie.ai File Upload API
                image_url = await self._upload_telegram_image(image_file_id)
                if image_url:
                    request_data["imageUrls"] = [image_url]
                    logger.info(f"Using uploaded image URL: {image_url}")
                else:
                    logger.error(f"Failed to upload image for task {task_id}")
                    await db.update_video_generation(
                        task_id, "failed", 
                        error_message="Failed to upload image to kie.ai"
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
                                    # Update database with Veo task ID and set processing status
                                    await db.update_veo_task_id(task_id, veo_task_id)
                                    
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
        """Upload Telegram image using kie.ai File Upload API"""
        try:
            from aiogram import Bot
            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            
            # Download file from Telegram
            file_info = await bot.get_file(file_id)
            if not file_info.file_path:
                logger.error(f"No file path for image {file_id}")
                return None
            
            file_data = await bot.download_file(file_info.file_path)
            if not file_data:
                logger.error(f"Failed to download file data for {file_id}")
                return None
            
            # Convert file data to bytes
            file_bytes = file_data.read()
            
            # Upload to kie.ai File Upload API
            upload_url = f"https://kieai.redpandaai.co/api/file-stream-upload"
            
            # Prepare multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field('file', 
                              file_bytes, 
                              filename=f"{file_id}.jpg",
                              content_type='image/jpeg')
            form_data.add_field('uploadPath', 'telegram-images')
            form_data.add_field('fileName', f"{file_id}.jpg")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    upload_url,
                    headers=headers,
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    logger.info(f"File upload response status: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"File upload response: {result}")
                        
                        if result.get("success") and result.get("data"):
                            # File Upload API returns downloadUrl field
                            file_url = result["data"].get("downloadUrl") or result["data"].get("fileUrl")
                            if file_url:
                                logger.info(f"Image uploaded successfully: {file_id} -> {file_url}")
                                return file_url
                            else:
                                logger.error(f"No download URL in response: {result}")
                                return None
                    
                    # Log error response
                    error_text = await response.text()
                    logger.error(f"File upload failed: {response.status} - {error_text}")
                    return None
            
        except Exception as e:
            logger.error(f"Error uploading image {file_id}: {e}")
            return None
    
    async def _poll_video_status(self, task_id: str, veo_task_id: str, user_id: int):
        """Poll video generation status with multiple endpoint attempts"""
        max_attempts = 60  # 5 minutes with 5-second intervals (video generation takes time)
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
        
        # Use the correct Veo API endpoint according to official docs
        # The primary endpoint uses GET with taskId as query parameter
        record_info_url = f"{self.base_url}/api/v1/veo/record-info?taskId={veo_task_id}"
        
        async with aiohttp.ClientSession() as session:
            try:
                # Primary endpoint: GET with taskId as query parameter (official docs)
                async with session.get(
                    record_info_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    logger.info(f"Trying GET {record_info_url}, status: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Success response from record-info: {result}")
                        
                        # Handle official Veo API response format
                        if result.get("code") == 200 and result.get("data"):
                            data = result["data"]
                            success_flag = data.get("successFlag")
                            
                            # Convert successFlag to standard status format
                            if success_flag == 0:
                                # Still processing
                                return {"status": "processing"}
                            elif success_flag == 1:
                                # Success - extract video URLs from correct location
                                response_data = data.get("response", {})
                                result_urls = response_data.get("resultUrls", [])
                                
                                if result_urls:
                                    # resultUrls is already an array
                                    video_url = result_urls[0] if result_urls and len(result_urls) > 0 else None
                                    
                                    if video_url:
                                        return {"status": "completed", "video_url": video_url}
                                
                                logger.error(f"Success status but no video URLs found. Response: {data}")
                            elif success_flag in [2, 3]:
                                # Failed
                                error_msg = data.get("errorMessage", "Video generation failed")
                                return {"status": "failed", "error": error_msg}
                    else:
                        text = await response.text()
                        logger.warning(f"Status {response.status} from record-info: {text[:200]}")
                        
            except Exception as e:
                logger.error(f"Error checking status with official endpoint: {e}")
                
            # Fallback: try alternative endpoints if main one fails
            fallback_endpoints = [
                f"{self.base_url}/api/v1/veo/record-detail?taskId={veo_task_id}",  # Alternative with query param
                f"{self.base_url}/api/v1/veo/status/{veo_task_id}",  # GET with task ID in path
            ]
            
            for endpoint in fallback_endpoints:
                try:
                    # For other endpoints, use GET
                    async with session.get(
                        endpoint,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        
                        logger.info(f"Trying GET {endpoint}: status {response.status}")
                        
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
        bot = None
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
                parse_mode="HTML",
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
        finally:
            # Properly close bot session
            if bot:
                await bot.session.close()
    
    async def _notify_user_failure(self, user_id: int, error_message: str):
        """Notify user about generation failure"""
        bot = None
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
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error notifying user failure {user_id}: {e}")
        finally:
            # Properly close bot session
            if bot:
                await bot.session.close()
    
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
