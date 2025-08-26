from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

class UserStatus(Enum):
    REGULAR = "regular"
    ADMIN = "admin"
    BANNED = "banned"

class TransactionType(Enum):
    CREDIT_PURCHASE = "credit_purchase"
    CREDIT_SPEND = "credit_spend"
    ADMIN_GRANT = "admin_grant"

class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    YOOKASSA = "yookassa"

class GenerationType(Enum):
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"

@dataclass
class User:
    """User model"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    credits: int = 0
    status: UserStatus = UserStatus.REGULAR
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class Transaction:
    """Transaction model for credit operations"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    type: Optional[TransactionType] = None
    amount: int = 0
    description: str = ""
    payment_method: Optional[PaymentMethod] = None
    payment_id: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class VideoGeneration:
    """Video generation task model"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    task_id: str = ""
    veo_task_id: Optional[str] = None  # API task ID from Veo
    prompt: str = ""
    generation_type: Optional[GenerationType] = None
    image_url: Optional[str] = None
    model: str = "veo3_fast"
    aspect_ratio: str = "16:9"
    status: str = "pending"  # pending, processing, completed, failed
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    credits_spent: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class AdminLog:
    """Admin action log model"""
    id: Optional[int] = None
    admin_id: Optional[int] = None
    action: str = ""
    target_user_id: Optional[int] = None
    description: str = ""
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
