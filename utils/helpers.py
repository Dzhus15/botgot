import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import hashlib
import uuid

def validate_prompt(prompt: str) -> tuple[bool, str]:
    """Validate video generation prompt"""
    if not prompt or not prompt.strip():
        return False, "Промпт не может быть пустым"
    
    prompt = prompt.strip()
    
    if len(prompt) < 10:
        return False, "Промпт слишком короткий. Минимум 10 символов."
    
    if len(prompt) > 1000:
        return False, "Промпт слишком длинный. Максимум 1000 символов."
    
    # Check for potentially harmful content
    forbidden_keywords = [
        "nsfw", "nude", "naked", "sexual", "porn", "xxx",
        "violence", "kill", "death", "suicide", "harm",
        "drugs", "illegal", "weapon", "bomb", "terror"
    ]
    
    prompt_lower = prompt.lower()
    for keyword in forbidden_keywords:
        if keyword in prompt_lower:
            return False, "Промпт содержит запрещенный контент"
    
    return True, "OK"

def format_duration(seconds: int) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if remaining_seconds == 0:
            return f"{minutes}м"
        return f"{minutes}м {remaining_seconds}с"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        if remaining_minutes == 0:
            return f"{hours}ч"
        return f"{hours}ч {remaining_minutes}м"

def format_credits(credits: int) -> str:
    """Format credits with proper plural form"""
    if credits % 10 == 1 and credits % 100 != 11:
        return f"{credits} кредит"
    elif credits % 10 in [2, 3, 4] and credits % 100 not in [12, 13, 14]:
        return f"{credits} кредита"
    else:
        return f"{credits} кредитов"

def escape_html(text: str) -> str:
    """Escape HTML special characters"""
    if not text:
        return ""
    
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;"))

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def generate_task_id(prefix: str = "veo") -> str:
    """Generate unique task ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_part = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{random_part}"

def is_valid_url(url: str) -> bool:
    """Check if URL is valid"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def hash_string(text: str) -> str:
    """Generate SHA-256 hash of string"""
    return hashlib.sha256(text.encode()).hexdigest()

def parse_callback_data(callback_data: str) -> Dict[str, str]:
    """Parse callback data into dictionary"""
    parts = callback_data.split('_')
    if len(parts) < 2:
        return {"action": callback_data}
    
    result = {"action": parts[0]}
    for i, part in enumerate(parts[1:], 1):
        result[f"param{i}"] = part
    
    return result

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def get_user_display_name(user) -> str:
    """Get user display name from Telegram user object"""
    if hasattr(user, 'first_name') and user.first_name:
        name = user.first_name
        if hasattr(user, 'last_name') and user.last_name:
            name += f" {user.last_name}"
        return name
    elif hasattr(user, 'username') and user.username:
        return f"@{user.username}"
    else:
        return f"User {user.id}"

def is_recent_timestamp(timestamp: datetime, hours: int = 24) -> bool:
    """Check if timestamp is within recent hours"""
    if not timestamp:
        return False
    
    now = datetime.now()
    time_diff = now - timestamp
    return time_diff < timedelta(hours=hours)

def batch_list(items: List[Any], batch_size: int) -> List[List[Any]]:
    """Split list into batches"""
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

async def retry_async(func, max_retries: int = 3, delay: float = 1.0):
    """Retry async function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            wait_time = delay * (2 ** attempt)  # Exponential backoff
            await asyncio.sleep(wait_time)
    
    return None

def clean_filename(filename: str) -> str:
    """Clean filename from invalid characters"""
    # Remove invalid characters for filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    filename = filename[:100]
    
    return filename

def format_timestamp(timestamp: datetime, format_type: str = "short") -> str:
    """Format timestamp for display"""
    if not timestamp:
        return "N/A"
    
    now = datetime.now()
    diff = now - timestamp
    
    if format_type == "relative":
        if diff.days > 0:
            return f"{diff.days} дней назад"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} часов назад"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} минут назад"
        else:
            return "Только что"
    elif format_type == "short":
        return timestamp.strftime("%d.%m.%Y %H:%M")
    elif format_type == "long":
        return timestamp.strftime("%d %B %Y, %H:%M:%S")
    else:
        return timestamp.isoformat()

def extract_numbers(text: str) -> List[int]:
    """Extract all numbers from text"""
    numbers = re.findall(r'\d+', text)
    return [int(num) for num in numbers]

def is_valid_telegram_id(user_id: str) -> bool:
    """Check if string is valid Telegram user ID"""
    try:
        user_id_int = int(user_id)
        return 1 <= user_id_int <= 999999999999
    except ValueError:
        return False
