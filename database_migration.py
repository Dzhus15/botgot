#!/usr/bin/env python3
"""
Database Migration Tool
Переносит данные из SQLite (development) в PostgreSQL (production)
"""

import asyncio
import aiosqlite
import asyncpg
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self):
        self.sqlite_path = "bot_database.db"
        self.postgres_url = os.getenv('DATABASE_URL')
        
        if not self.postgres_url:
            raise ValueError("DATABASE_URL environment variable is required")
    
    async def export_sqlite_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Экспорт данных из SQLite"""
        logger.info("Начинаем экспорт данных из SQLite...")
        
        data = {
            'users': [],
            'transactions': [],
            'video_generations': [],
            'admin_logs': []
        }
        
        if not os.path.exists(self.sqlite_path):
            logger.warning(f"SQLite файл {self.sqlite_path} не найден!")
            return data
        
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
                        'id': row[0],
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
                        'id': row[0],
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
            
            # Экспорт логов администратора
            try:
                async with db.execute("SELECT * FROM admin_logs") as cursor:
                    async for row in cursor:
                        data['admin_logs'].append({
                            'id': row[0],
                            'admin_id': row[1],
                            'action': row[2],
                            'target_user_id': row[3],
                            'description': row[4],
                            'created_at': row[5]
                        })
            except Exception as e:
                logger.warning(f"Не удалось экспортировать admin_logs: {e}")
        
        logger.info(f"Экспортировано: {len(data['users'])} пользователей, "
                   f"{len(data['transactions'])} транзакций, "
                   f"{len(data['video_generations'])} видео генераций, "
                   f"{len(data['admin_logs'])} админ логов")
        
        return data
    
    async def import_to_postgres(self, data: Dict[str, List[Dict[str, Any]]]):
        """Импорт данных в PostgreSQL"""
        logger.info("Начинаем импорт данных в PostgreSQL...")
        
        try:
            conn = await asyncpg.connect(self.postgres_url)
            
            # Создаем таблицы если их нет
            await self.create_postgres_tables(conn)
            
            # Очищаем существующие данные (опционально)
            response = input("Очистить существующие данные в PostgreSQL? (y/N): ")
            if response.lower() == 'y':
                await conn.execute("DELETE FROM admin_logs")
                await conn.execute("DELETE FROM video_generations") 
                await conn.execute("DELETE FROM transactions")
                await conn.execute("DELETE FROM users")
                logger.info("Существующие данные очищены")
            
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
                    logger.error(f"Ошибка импорта пользователя {user['telegram_id']}: {e}")
            
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
                    logger.error(f"Ошибка импорта транзакции: {e}")
            
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
                    logger.error(f"Ошибка импорта видео генерации: {e}")
            
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
                    logger.error(f"Ошибка импорта админ лога: {e}")
            
            await conn.close()
            logger.info("Импорт данных в PostgreSQL завершен успешно!")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise
    
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
    
    async def migrate(self):
        """Полная миграция данных"""
        try:
            # Экспорт из SQLite
            data = await self.export_sqlite_data()
            
            if not any(data.values()):
                logger.warning("Нет данных для миграции!")
                return
            
            # Импорт в PostgreSQL
            await self.import_to_postgres(data)
            
            # Создание резервной копии SQLite
            import shutil
            backup_name = f"bot_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(self.sqlite_path, backup_name)
            logger.info(f"Создана резервная копия SQLite: {backup_name}")
            
            logger.info("🎉 Миграция данных завершена успешно!")
            
        except Exception as e:
            logger.error(f"Ошибка миграции: {e}")
            raise

async def main():
    """Главная функция"""
    print("=" * 60)
    print("🔄 ИНСТРУМЕНТ МИГРАЦИИ БАЗЫ ДАННЫХ")
    print("=" * 60)
    print("Этот скрипт перенесет все данные из SQLite (development)")
    print("в PostgreSQL (production) базу данных.")
    print()
    
    # Проверяем наличие DATABASE_URL
    if not os.getenv('DATABASE_URL'):
        print("❌ Ошибка: DATABASE_URL не настроен!")
        print("Убедитесь, что вы находитесь в production среде.")
        return
    
    response = input("Продолжить миграцию? (y/N): ")
    if response.lower() != 'y':
        print("Миграция отменена.")
        return
    
    try:
        migrator = DatabaseMigrator()
        await migrator.migrate()
        
        print()
        print("=" * 60)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 60)
        print("Теперь ваши данные доступны в production базе данных.")
        print("Рекомендуется перезапустить бота для применения изменений.")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        print("Обратитесь к разработчику за помощью.")

if __name__ == "__main__":
    asyncio.run(main())