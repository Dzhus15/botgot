import time
from typing import Dict, List
from dataclasses import dataclass, field
from config import Config

config = Config()

@dataclass
class UserLimitData:
    """User rate limit tracking data"""
    requests: List[float] = field(default_factory=list)
    blocked_until: float = 0.0

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.users: Dict[int, UserLimitData] = {}
        self.max_requests = config.RATE_LIMIT_MESSAGES
        self.time_window = config.RATE_LIMIT_WINDOW
        self.block_duration = 300  # 5 minutes block
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make a request"""
        current_time = time.time()
        
        # Get or create user data
        if user_id not in self.users:
            self.users[user_id] = UserLimitData()
        
        user_data = self.users[user_id]
        
        # Check if user is currently blocked
        if user_data.blocked_until > current_time:
            return False
        
        # Clean old requests
        cutoff_time = current_time - self.time_window
        user_data.requests = [req_time for req_time in user_data.requests if req_time > cutoff_time]
        
        # Check rate limit
        if len(user_data.requests) >= self.max_requests:
            # Block user
            user_data.blocked_until = current_time + self.block_duration
            return False
        
        # Record request
        user_data.requests.append(current_time)
        return True
    
    def get_reset_time(self, user_id: int) -> float:
        """Get time when user's rate limit resets"""
        if user_id not in self.users:
            return 0.0
        
        user_data = self.users[user_id]
        current_time = time.time()
        
        if user_data.blocked_until > current_time:
            return user_data.blocked_until
        
        if user_data.requests:
            return user_data.requests[0] + self.time_window
        
        return 0.0
    
    def cleanup_old_data(self):
        """Clean up old user data to prevent memory leaks"""
        current_time = time.time()
        cutoff_time = current_time - (self.time_window * 2)  # Keep data for 2x window
        
        users_to_remove = []
        for user_id, user_data in self.users.items():
            if (user_data.blocked_until < current_time and 
                not user_data.requests):
                users_to_remove.append(user_id)
            else:
                # Clean old requests
                user_data.requests = [req for req in user_data.requests if req > cutoff_time]
        
        for user_id in users_to_remove:
            del self.users[user_id]

# Global rate limiter instance
rate_limiter = RateLimiter()
