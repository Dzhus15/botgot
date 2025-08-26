#!/usr/bin/env python3
"""
Автоматическая миграция данных при деплое
Запускается автоматически в build процессе
"""

import asyncio
import aiosqlite
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - AUTO-MIGRATE - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импорт asyncpg только если доступен
try:
    import asyncpg
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class AutoMigrator:
    def __init__(self):
        self.sqlite_path = "bot_database.db"
        self.postgres_url = os.getenv('DATABASE_URL')
        
        # Проверяем среду выполнения
        self.is_deployment = os.getenv('REPLIT_DEPLOYMENT') == '1'
        
        logger.info(f"AutoMigrator initialized:")
        logger.info(f"  - Is deployment: {self.is_deployment}")
        logger.info(f"  - PostgreSQL available: {POSTGRES_AVAILABLE}")
        logger.info(f"  - DATABASE_URL present: {bool(self.postgres_url)}")
        logger.info(f"  - SQLite file exists: {os.path.exists(self.sqlite_path)}")
    
    async def should_migrate(self) -> bool:
        """Определить нужно ли делать миграцию"""
        # Миграция нужна если:
        # 1. Это deployment среда
        # 2. Есть PostgreSQL
        # 3. Есть SQLite файл с данными
        # 4. PostgreSQL база пустая или содержит меньше данных
        
        if not self.is_deployment:
            logger.info("Not in deployment - skipping migration")
            return False
            
        if not POSTGRES_AVAILABLE or not self.postgres_url:
            logger.info("PostgreSQL not available - skipping migration")
            return False
            
        if not os.path.exists(self.sqlite_path):
            logger.info("No SQLite file found - skipping migration")
            return False
        
        # Проверяем количество пользователей в SQLite
        sqlite_users = await self.count_sqlite_users()
        if sqlite_users == 0:
            logger.info("No users in SQLite - skipping migration")
            return False
        
        # Проверяем количество пользователей в PostgreSQL
        postgres_users = await self.count_postgres_users()
        
        logger.info(f"Users count: SQLite={sqlite_users}, PostgreSQL={postgres_users}")
        
        # Мигрируем если в SQLite больше пользователей
        should_migrate = sqlite_users > postgres_users
        
        if should_migrate:
            logger.info("Migration needed - SQLite has more data")
        else:
            logger.info("Migration not needed - PostgreSQL is up to date")
            
        return should_migrate
    
    async def count_sqlite_users(self) -> int:
        """Подсчитать пользователей в SQLite"""
        try:
            async with aiosqlite.connect(self.sqlite_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.warning(f"Could not count SQLite users: {e}")
            return 0
    
    async def count_postgres_users(self) -> int:
        """Подсчитать пользователей в PostgreSQL"""
        try:
            conn = await asyncpg.connect(self.postgres_url)
            try:
                # Создаем таблицу если её нет
                await self.create_postgres_tables(conn)
                result = await conn.fetchval("SELECT COUNT(*) FROM users")
                return result if result else 0
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"Could not count PostgreSQL users: {e}")
            return 0
    
    async def create_postgres_tables(self, conn):
        """Создание таблиц в PostgreSQL"""
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
                payment_id TEXT UNIQUE,
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
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_transactions_payment_id ON transactions(payment_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_video_generations_task_id ON video_generations(task_id)')
    
    async def migrate_data(self):
        """Автоматическая миграция данных"""
        logger.info("Starting automatic data migration...")
        
        try:
            # Экспорт из SQLite
            data = await self.export_sqlite_data()
            
            if not any(data.values()):
                logger.warning("No data to migrate!")
                return
            
            # Импорт в PostgreSQL
            await self.import_to_postgres(data)
            
            logger.info("✅ Automatic migration completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            # Не прерываем деплой из-за ошибки миграции
            pass
    
    async def export_sqlite_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Экспорт данных из SQLite"""
        logger.info("Exporting data from SQLite...")
        
        data = {
            'users': [],
            'transactions': [],
            'video_generations': [],
            'admin_logs': []
        }
        
        async with aiosqlite.connect(self.sqlite_path) as db:
            # Экспорт пользователей
            async with db.execute("SELECT * FROM users") as cursor:
                async for row in cursor:
                    data['users'].append({
                        'telegram_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'credits': row[4],
                        'status': row[5],
                        'created_at': row[6],
                        'updated_at': row[7]
                    })
            
            # Экспорт транзакций
            async with db.execute("SELECT * FROM transactions") as cursor:
                async for row in cursor:
                    data['transactions'].append({
                        'user_id': row[1],
                        'type': row[2],
                        'amount': row[3],
                        'description': row[4],
                        'payment_method': row[5],
                        'payment_id': row[6],
                        'created_at': row[7]
                    })
            
            # Экспорт видео генераций
            async with db.execute("SELECT * FROM video_generations") as cursor:
                async for row in cursor:
                    data['video_generations'].append({
                        'user_id': row[1],
                        'task_id': row[2],
                        'veo_task_id': row[3] if len(row) > 3 else None,
                        'prompt': row[4] if len(row) > 4 else row[3],
                        'generation_type': row[5] if len(row) > 5 else row[4],
                        'image_url': row[6] if len(row) > 6 else row[5],
                        'model': row[7] if len(row) > 7 else row[6],
                        'aspect_ratio': row[8] if len(row) > 8 else row[7],
                        'status': row[9] if len(row) > 9 else row[8],
                        'video_url': row[10] if len(row) > 10 else row[9],
                        'error_message': row[11] if len(row) > 11 else row[10],
                        'credits_spent': row[12] if len(row) > 12 else row[11],
                        'created_at': row[13] if len(row) > 13 else row[12],
                        'completed_at': row[14] if len(row) > 14 else row[13]
                    })
            
            # Экспорт админ логов
            try:
                async with db.execute("SELECT * FROM admin_logs") as cursor:
                    async for row in cursor:
                        data['admin_logs'].append({
                            'admin_id': row[1],
                            'action': row[2],
                            'target_user_id': row[3],
                            'description': row[4],
                            'created_at': row[5]
                        })
            except Exception as e:
                logger.warning(f"Could not export admin_logs: {e}")
        
        logger.info(f"Exported: {len(data['users'])} users, "
                   f"{len(data['transactions'])} transactions, "
                   f"{len(data['video_generations'])} videos, "
                   f"{len(data['admin_logs'])} admin logs")
        
        return data
    
    async def import_to_postgres(self, data: Dict[str, List[Dict[str, Any]]]):
        """Импорт данных в PostgreSQL"""
        logger.info("Importing data to PostgreSQL...")
        
        conn = await asyncpg.connect(self.postgres_url)
        try:
            # Создаем таблицы
            await self.create_postgres_tables(conn)
            
            # Импорт пользователей
            for user in data['users']:
                try:
                    await conn.execute('''
                        INSERT INTO users (telegram_id, username, first_name, last_name, credits, status, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (telegram_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        credits = EXCLUDED.credits,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                    ''', 
                        user['telegram_id'],
                        user['username'],
                        user['first_name'],
                        user['last_name'],
                        user['credits'],
                        user['status'],
                        datetime.fromisoformat(user['created_at']) if isinstance(user['created_at'], str) else user['created_at'],
                        datetime.fromisoformat(user['updated_at']) if isinstance(user['updated_at'], str) else user['updated_at']
                    )
                except Exception as e:
                    logger.warning(f"Failed to import user {user['telegram_id']}: {e}")
            
            # Импорт транзакций
            for transaction in data['transactions']:
                try:
                    await conn.execute('''
                        INSERT INTO transactions (user_id, type, amount, description, payment_method, payment_id, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (payment_id) DO NOTHING
                    ''', 
                        transaction['user_id'],
                        transaction['type'],
                        transaction['amount'],
                        transaction['description'],
                        transaction['payment_method'],
                        transaction['payment_id'],
                        datetime.fromisoformat(transaction['created_at']) if isinstance(transaction['created_at'], str) else transaction['created_at']
                    )
                except Exception as e:
                    logger.warning(f"Failed to import transaction: {e}")
            
            # Импорт видео генераций
            for video in data['video_generations']:
                try:
                    await conn.execute('''
                        INSERT INTO video_generations 
                        (user_id, task_id, veo_task_id, prompt, generation_type, image_url, model, aspect_ratio, status, video_url, error_message, credits_spent, created_at, completed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        ON CONFLICT (task_id) DO NOTHING
                    ''', 
                        video['user_id'],
                        video['task_id'],
                        video['veo_task_id'],
                        video['prompt'],
                        video['generation_type'],
                        video['image_url'],
                        video['model'],
                        video['aspect_ratio'],
                        video['status'],
                        video['video_url'],
                        video['error_message'],
                        video['credits_spent'],
                        datetime.fromisoformat(video['created_at']) if isinstance(video['created_at'], str) else video['created_at'],
                        datetime.fromisoformat(video['completed_at']) if isinstance(video['completed_at'], str) and video['completed_at'] else None
                    )
                except Exception as e:
                    logger.warning(f"Failed to import video generation: {e}")
            
            # Импорт админ логов
            for log in data['admin_logs']:
                try:
                    await conn.execute('''
                        INSERT INTO admin_logs (admin_id, action, target_user_id, description, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                    ''', 
                        log['admin_id'],
                        log['action'],
                        log['target_user_id'],
                        log['description'],
                        datetime.fromisoformat(log['created_at']) if isinstance(log['created_at'], str) else log['created_at']
                    )
                except Exception as e:
                    logger.warning(f"Failed to import admin log: {e}")
                    
        finally:
            await conn.close()
        
        logger.info("PostgreSQL import completed")

async def main():
    """Главная функция автоматической миграции"""
    migrator = AutoMigrator()
    
    if await migrator.should_migrate():
        await migrator.migrate_data()
    else:
        logger.info("Migration not needed")

if __name__ == "__main__":
    asyncio.run(main())