import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuration class for the Telegram bot"""
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Veo API Configuration
    VEO_API_KEY: str = os.getenv("VEO_API_KEY", "")
    VEO_API_BASE_URL: str = "https://api.kie.ai"
    
    # Payment Configuration
    YOOKASSA_API_KEY: str = os.getenv("YOOKASSA_API_KEY", "")
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_WEBHOOK_SECRET: str = os.getenv("YOOKASSA_WEBHOOK_SECRET", "")
    TELEGRAM_PAYMENTS_TOKEN: str = os.getenv("TELEGRAM_PAYMENTS_TOKEN", "")
    
    # Admin Configuration
    ADMIN_USER_ID: int = 1864913930
    INITIAL_ADMIN_CREDITS: int = 100
    
    # Database Configuration  
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Rate Limiting Configuration
    RATE_LIMIT_MESSAGES: int = 100  # messages per period (increased)
    RATE_LIMIT_WINDOW: int = 60   # seconds
    
    # Video Generation Configuration
    DEFAULT_MODEL: str = "veo3_fast"  # Cost-efficient model
    DEFAULT_ASPECT_RATIO: str = "16:9"
    
    # Credits Configuration
    VIDEO_GENERATION_COST: int = 10  # credits per video
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        if not self.VEO_API_KEY:
            print("⚠️ Warning: VEO_API_KEY not set - video generation will not work")
