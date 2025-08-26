import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name: str = "telegram_bot", level: str = "INFO") -> logging.Logger:
    """Setup logging configuration"""
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Prevent duplicate handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # Simplified file handler without rotation to avoid threading issues
    try:
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        file_handler = logging.FileHandler("logs/bot.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
    
    return logger

def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    if name:
        return logging.getLogger(f"telegram_bot.{name}")
    return logging.getLogger("telegram_bot")

def log_user_action(user_id: int, action: str, details: str = ""):
    """Log user actions for monitoring"""
    logger = get_logger("user_actions")
    logger.info(f"User {user_id}: {action} | {details}")

def log_api_call(api_name: str, success: bool, duration: float = None, error: str = None):
    """Log API calls for monitoring"""
    logger = get_logger("api_calls")
    status = "SUCCESS" if success else "FAILED"
    duration_str = f" | Duration: {duration:.2f}s" if duration else ""
    error_str = f" | Error: {error}" if error else ""
    logger.info(f"API {api_name}: {status}{duration_str}{error_str}")

def log_payment(user_id: int, amount: int, method: str, success: bool, payment_id: str = None):
    """Log payment transactions"""
    logger = get_logger("payments")
    status = "SUCCESS" if success else "FAILED"
    payment_str = f" | PaymentID: {payment_id}" if payment_id else ""
    logger.info(f"Payment {status}: User {user_id} | Amount {amount} | Method {method}{payment_str}")

def sanitize_log_data(data: str) -> str:
    """Sanitize sensitive data from logs"""
    # Remove API keys, tokens, and other sensitive information
    sensitive_patterns = [
        r'Bearer [A-Za-z0-9\-_]+',
        r'token["\s]*[:=]["\s]*[A-Za-z0-9\-_]+',
        r'key["\s]*[:=]["\s]*[A-Za-z0-9\-_]+',
        r'password["\s]*[:=]["\s]*\S+',
    ]
    
    sanitized = data
    for pattern in sensitive_patterns:
        import re
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    return sanitized
