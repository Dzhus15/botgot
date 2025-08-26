import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List
from config import Config
from database.models import User, Transaction, VideoGeneration, AdminLog, UserStatus, TransactionType, PaymentMethod, GenerationType

logger = logging.getLogger(__name__)
config = Config()

class Database:
    """Database manager for SQLite operations"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "bot_database.db"
    
    def get_connection(self):
        """Get database connection"""
        return aiosqlite.connect(self.db_path)
    
    async def create_tables(self):
        """Create all necessary tables"""
        async with self.get_connection() as db:
            # Users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    credits INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'regular',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Transactions table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    description TEXT,
                    payment_method TEXT,
                    payment_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Video generations table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS video_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task_id TEXT UNIQUE,
                    prompt TEXT NOT NULL,
                    generation_type TEXT NOT NULL,
                    image_url TEXT,
                    model TEXT DEFAULT 'veo3_fast',
                    aspect_ratio TEXT DEFAULT '16:9',
                    status TEXT DEFAULT 'pending',
                    video_url TEXT,
                    error_message TEXT,
                    credits_spent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Admin logs table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT NOT NULL,
                    target_user_id INTEGER,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES users (telegram_id)
                )
            ''')
            
            await db.commit()
            logger.info("Database tables created successfully")
    
    # User operations
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        async with self.get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                return User(
                    telegram_id=row[0],
                    username=row[1],
                    first_name=row[2],
                    last_name=row[3],
                    credits=row[4],
                    status=UserStatus(row[5]),
                    created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    updated_at=datetime.fromisoformat(row[7]) if row[7] else None
                )
            return None
    
    async def create_user(self, user: User) -> bool:
        """Create a new user"""
        try:
            async with self.get_connection() as db:
                await db.execute('''
                    INSERT INTO users (telegram_id, username, first_name, last_name, credits, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.telegram_id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.credits,
                    user.status.value,
                    user.created_at.isoformat(),
                    user.updated_at.isoformat()
                ))
                await db.commit()
                logger.info(f"Created user {user.telegram_id}")
                return True
        except Exception as e:
            logger.error(f"Error creating user {user.telegram_id}: {e}")
            return False
    
    async def update_user_credits(self, telegram_id: int, credits: int) -> bool:
        """Update user credits"""
        try:
            async with self.get_connection() as db:
                await db.execute(
                    "UPDATE users SET credits = ?, updated_at = ? WHERE telegram_id = ?",
                    (credits, datetime.now().isoformat(), telegram_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating credits for user {telegram_id}: {e}")
            return False
    
    # Transaction operations
    async def create_transaction(self, transaction: Transaction) -> bool:
        """Create a new transaction"""
        try:
            async with self.get_connection() as db:
                await db.execute('''
                    INSERT INTO transactions (user_id, type, amount, description, payment_method, payment_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction.user_id,
                    transaction.type.value,
                    transaction.amount,
                    transaction.description,
                    transaction.payment_method.value if transaction.payment_method else None,
                    transaction.payment_id,
                    transaction.created_at.isoformat()
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            return False
    
    # Video generation operations
    async def create_video_generation(self, generation: VideoGeneration) -> bool:
        """Create a new video generation record"""
        try:
            async with self.get_connection() as db:
                await db.execute('''
                    INSERT INTO video_generations 
                    (user_id, task_id, prompt, generation_type, image_url, model, aspect_ratio, status, credits_spent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    generation.user_id,
                    generation.task_id,
                    generation.prompt,
                    generation.generation_type.value,
                    generation.image_url,
                    generation.model,
                    generation.aspect_ratio,
                    generation.status,
                    generation.credits_spent,
                    generation.created_at.isoformat()
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating video generation record: {e}")
            return False
    
    async def update_video_generation(self, task_id: str, status: str, video_url: str = None, error_message: str = None) -> bool:
        """Update video generation status"""
        try:
            async with self.get_connection() as db:
                completed_at = datetime.now().isoformat() if status in ['completed', 'failed'] else None
                await db.execute('''
                    UPDATE video_generations 
                    SET status = ?, video_url = ?, error_message = ?, completed_at = ?
                    WHERE task_id = ?
                ''', (status, video_url, error_message, completed_at, task_id))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating video generation {task_id}: {e}")
            return False
    
    # Admin operations
    async def get_user_statistics(self) -> dict:
        """Get user statistics for admin"""
        async with self.get_connection() as db:
            # Total users
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            # Active users (generated video in last 30 days)
            cursor = await db.execute('''
                SELECT COUNT(DISTINCT user_id) FROM video_generations 
                WHERE created_at >= datetime('now', '-30 days')
            ''')
            active_users = (await cursor.fetchone())[0]
            
            # Total credits in system
            cursor = await db.execute("SELECT SUM(credits) FROM users")
            total_credits = (await cursor.fetchone())[0] or 0
            
            # Total videos generated
            cursor = await db.execute("SELECT COUNT(*) FROM video_generations WHERE status = 'completed'")
            total_videos = (await cursor.fetchone())[0]
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_credits': total_credits,
                'total_videos': total_videos
            }
    
    async def get_all_user_ids(self) -> List[int]:
        """Get all user IDs for broadcasting"""
        async with self.get_connection() as db:
            cursor = await db.execute("SELECT telegram_id FROM users WHERE status != 'banned'")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def log_admin_action(self, log: AdminLog) -> bool:
        """Log admin action"""
        try:
            async with self.get_connection() as db:
                await db.execute('''
                    INSERT INTO admin_logs (admin_id, action, target_user_id, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    log.admin_id,
                    log.action,
                    log.target_user_id,
                    log.description,
                    log.created_at.isoformat()
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error logging admin action: {e}")
            return False

# Global database instance will be initialized later
db = None

async def init_database():
    """Initialize database with tables and admin user"""
    global db
    db = Database()
    await db.create_tables()
    
    # Create admin user if not exists
    admin_user = await db.get_user(config.ADMIN_USER_ID)
    if not admin_user:
        admin_user = User(
            telegram_id=config.ADMIN_USER_ID,
            credits=config.INITIAL_ADMIN_CREDITS,
            status=UserStatus.ADMIN
        )
        await db.create_user(admin_user)
        
        # Log admin creation
        transaction = Transaction(
            user_id=config.ADMIN_USER_ID,
            type=TransactionType.ADMIN_GRANT,
            amount=config.INITIAL_ADMIN_CREDITS,
            description="Initial admin credits"
        )
        await db.create_transaction(transaction)
        
        logger.info(f"Admin user created with {config.INITIAL_ADMIN_CREDITS} credits")
