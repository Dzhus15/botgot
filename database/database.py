import aiosqlite
import logging
import os
from datetime import datetime
from typing import Optional, List
from config import Config
from database.models import User, Transaction, VideoGeneration, AdminLog, UserStatus, TransactionType, PaymentMethod, GenerationType

# Try to import asyncpg for PostgreSQL, fallback to SQLite
try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

logger = logging.getLogger(__name__)
config = Config()

class Database:
    """Database manager for PostgreSQL and SQLite operations"""
    
    def __init__(self, database_url: Optional[str] = None, sqlite_path: Optional[str] = None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.sqlite_path = sqlite_path or "bot_database.db" 
        self.use_postgres = POSTGRES_AVAILABLE and self.database_url is not None
        
        if self.use_postgres:
            logger.info("Using PostgreSQL database")
        else:
            logger.info("Using SQLite database as fallback")
    
    async def get_postgres_connection(self):
        """Get PostgreSQL connection"""
        return await asyncpg.connect(self.database_url)
    
    def get_sqlite_connection(self):
        """Get SQLite connection"""
        return aiosqlite.connect(self.sqlite_path)
    
    async def create_tables(self):
        """Create all necessary tables"""
        if self.use_postgres:
            conn = await self.get_postgres_connection()
            try:
                # Users table  
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        telegram_id BIGINT PRIMARY KEY,
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
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
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
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS video_generations (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        task_id TEXT UNIQUE,
                        veo_task_id TEXT,
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
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS admin_logs (
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT,
                        action TEXT NOT NULL,
                        target_user_id BIGINT,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (admin_id) REFERENCES users (telegram_id)
                    )
                ''')
                
                logger.info("Database tables created successfully (PostgreSQL)")
            finally:
                await conn.close()
        else:
            # SQLite version
            async with self.get_sqlite_connection() as db:
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
                        veo_task_id TEXT,
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
                
                # Add veo_task_id column if it doesn't exist (migration)
                try:
                    await db.execute('ALTER TABLE video_generations ADD COLUMN veo_task_id TEXT')
                    await db.commit()
                    logger.info("Added veo_task_id column to video_generations table")
                except Exception:
                    # Column already exists
                    pass
                
                await db.commit()
                logger.info("Database tables created successfully (SQLite)")
    
    # User operations
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        if self.use_postgres:
            conn = await self.get_postgres_connection()
            try:
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE telegram_id = $1",
                    telegram_id
                )
                if row:
                    return User(
                        telegram_id=row[0],
                        username=row[1],
                        first_name=row[2],
                        last_name=row[3],
                        credits=row[4],
                        status=UserStatus(row[5]),
                        created_at=row[6],
                        updated_at=row[7]
                    )
                return None
            finally:
                await conn.close()
        else:
            async with self.get_sqlite_connection() as db:
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
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    await conn.execute('''
                        INSERT INTO users (telegram_id, username, first_name, last_name, credits, status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ''', 
                        user.telegram_id,
                        user.username,
                        user.first_name,
                        user.last_name,
                        user.credits,
                        user.status.value,
                        user.created_at or datetime.now(),
                        user.updated_at or datetime.now()
                    )
                    logger.info(f"Created user {user.telegram_id}")
                    return True
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
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
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    await conn.execute(
                        "UPDATE users SET credits = $1, updated_at = $2 WHERE telegram_id = $3",
                        credits, datetime.now(), telegram_id
                    )
                    return True
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
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
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    await conn.execute('''
                        INSERT INTO transactions (user_id, type, amount, description, payment_method, payment_id, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ''', 
                        transaction.user_id,
                        transaction.type.value,
                        transaction.amount,
                        transaction.description,
                        transaction.payment_method.value if transaction.payment_method else None,
                        transaction.payment_id,
                        transaction.created_at or datetime.now()
                    )
                    return True
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
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
    
    async def payment_exists(self, payment_id: str) -> bool:
        """Check if payment_id already exists in transactions"""
        try:
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM transactions WHERE payment_id = $1",
                        payment_id
                    )
                    return result > 0 if result else False
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
                    cursor = await db.execute(
                        "SELECT COUNT(*) FROM transactions WHERE payment_id = ?",
                        (payment_id,)
                    )
                    result = await cursor.fetchone()
                    return result[0] > 0 if result else False
        except Exception as e:
            logger.error(f"Error checking payment existence: {e}")
            return False
    
    # Video generation operations
    async def create_video_generation(self, generation: VideoGeneration) -> bool:
        """Create a new video generation record"""
        try:
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    await conn.execute('''
                        INSERT INTO video_generations 
                        (user_id, task_id, veo_task_id, prompt, generation_type, image_url, model, aspect_ratio, status, credits_spent, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ''', 
                        generation.user_id,
                        generation.task_id,
                        generation.veo_task_id,
                        generation.prompt,
                        generation.generation_type.value,
                        generation.image_url,
                        generation.model,
                        generation.aspect_ratio,
                        generation.status,
                        generation.credits_spent,
                        generation.created_at or datetime.now()
                    )
                    return True
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
                    await db.execute('''
                        INSERT INTO video_generations 
                        (user_id, task_id, veo_task_id, prompt, generation_type, image_url, model, aspect_ratio, status, credits_spent, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        generation.user_id,
                        generation.task_id,
                        generation.veo_task_id,
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
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    completed_at = datetime.now() if status in ['completed', 'failed'] else None
                    await conn.execute('''
                        UPDATE video_generations 
                        SET status = $1, video_url = $2, error_message = $3, completed_at = $4
                        WHERE task_id = $5
                    ''', status, video_url, error_message, completed_at, task_id)
                    return True
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
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
    
    async def update_veo_task_id(self, task_id: str, veo_task_id: str) -> bool:
        """Update the Veo API task ID for a generation"""
        try:
            if self.use_postgres:
                conn = await self.get_postgres_connection()
                try:
                    await conn.execute('''
                        UPDATE video_generations 
                        SET veo_task_id = $1, status = 'processing'
                        WHERE task_id = $2
                    ''', veo_task_id, task_id)
                    return True
                finally:
                    await conn.close()
            else:
                async with self.get_sqlite_connection() as db:
                    await db.execute('''
                        UPDATE video_generations 
                        SET veo_task_id = ?, status = 'processing'
                        WHERE task_id = ?
                    ''', (veo_task_id, task_id))
                    await db.commit()
                    return True
        except Exception as e:
            logger.error(f"Error updating veo_task_id for {task_id}: {e}")
            return False
            
    async def get_video_generation_by_veo_id(self, veo_task_id: str) -> Optional[VideoGeneration]:
        """Get video generation by Veo task ID"""
        if self.use_postgres:
            conn = await self.get_postgres_connection()
            try:
                row = await conn.fetchrow(
                    "SELECT * FROM video_generations WHERE veo_task_id = $1",
                    veo_task_id
                )
                if row:
                    return VideoGeneration(
                        id=row[0],
                        user_id=row[1],
                        task_id=row[2],
                        veo_task_id=row[3],
                        prompt=row[4],
                        generation_type=GenerationType(row[5]),
                        image_url=row[6],
                        model=row[7],
                        aspect_ratio=row[8],
                        status=row[9],
                        video_url=row[10],
                        error_message=row[11],
                        credits_spent=row[12],
                        created_at=row[13],
                        completed_at=row[14]
                    )
                return None
            finally:
                await conn.close()
        else:
            async with self.get_sqlite_connection() as db:
                cursor = await db.execute(
                    "SELECT * FROM video_generations WHERE veo_task_id = ?",
                    (veo_task_id,)
                )
                row = await cursor.fetchone()
                if row:
                    return VideoGeneration(
                        id=row[0],
                        user_id=row[1],
                        task_id=row[2],
                        veo_task_id=row[3],
                        prompt=row[4],
                        generation_type=GenerationType(row[5]),
                        image_url=row[6],
                        model=row[7],
                        aspect_ratio=row[8],
                        status=row[9],
                        video_url=row[10],
                        error_message=row[11],
                        credits_spent=row[12],
                        created_at=datetime.fromisoformat(row[13]) if row[13] else None,
                        completed_at=datetime.fromisoformat(row[14]) if row[14] else None
                    )
                return None
            
    async def get_processing_generations(self) -> List[VideoGeneration]:
        """Get all processing video generations that have veo_task_id"""
        async with self.get_sqlite_connection() as db:
            cursor = await db.execute('''
                SELECT * FROM video_generations 
                WHERE status = 'processing' AND veo_task_id IS NOT NULL
            ''')
            rows = await cursor.fetchall()
            generations = []
            for row in rows:
                generation = VideoGeneration(
                    id=row[0],
                    user_id=row[1],
                    task_id=row[2],
                    veo_task_id=row[3],
                    prompt=row[4],
                    generation_type=GenerationType(row[5]),
                    image_url=row[6],
                    model=row[7],
                    aspect_ratio=row[8],
                    status=row[9],
                    video_url=row[10],
                    error_message=row[11],
                    credits_spent=row[12],
                    created_at=datetime.fromisoformat(row[13]) if row[13] else None,
                    completed_at=datetime.fromisoformat(row[14]) if row[14] else None
                )
                generations.append(generation)
            return generations
    
    # Admin operations
    async def get_user_statistics(self) -> dict:
        """Get user statistics for admin"""
        async with self.get_sqlite_connection() as db:
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
        async with self.get_sqlite_connection() as db:
            cursor = await db.execute("SELECT telegram_id FROM users WHERE status != 'banned'")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def log_admin_action(self, log: AdminLog) -> bool:
        """Log admin action"""
        try:
            async with self.get_sqlite_connection() as db:
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

# Create database instance directly
db = Database()

async def init_database():
    """Initialize database with tables and admin user"""
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
