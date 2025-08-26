#!/usr/bin/env python3
"""
Синхронизация данных из Production (PostgreSQL) в Development (SQLite)
Для удобной работы с данными локально
"""

import asyncio
import aiosqlite
import asyncpg
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionSync:
    def __init__(self):
        self.sqlite_path = "bot_database.db"
        self.postgres_url = os.getenv('DATABASE_URL')
        
        if not self.postgres_url:
            raise ValueError("❌ DATABASE_URL не найден! Убедитесь что PostgreSQL настроен.")
    
    async def export_from_postgres(self) -> Dict[str, List[Dict[str, Any]]]:
        """Экспорт данных из PostgreSQL"""
        logger.info("📤 Экспортируем данные из Production PostgreSQL...")
        
        data = {
            'users': [],
            'transactions': [],
            'video_generations': [],
            'admin_logs': []
        }
        
        try:
            conn = await asyncpg.connect(self.postgres_url)
            
            # Экспорт пользователей
            rows = await conn.fetch("SELECT * FROM users ORDER BY created_at")
            for row in rows:
                data['users'].append({
                    'telegram_id': row['telegram_id'],
                    'username': row['username'],
                    'first_name': row['first_name'],
                    'last_name': row['last_name'],
                    'credits': row['credits'],
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
            
            # Экспорт транзакций
            rows = await conn.fetch("SELECT * FROM transactions ORDER BY created_at")
            for row in rows:
                data['transactions'].append({
                    'user_id': row['user_id'],
                    'type': row['type'],
                    'amount': row['amount'],
                    'description': row['description'],
                    'payment_method': row['payment_method'],
                    'payment_id': row['payment_id'],
                    'created_at': row['created_at']
                })
            
            # Экспорт видео генераций
            rows = await conn.fetch("SELECT * FROM video_generations ORDER BY created_at")
            for row in rows:
                data['video_generations'].append({
                    'user_id': row['user_id'],
                    'task_id': row['task_id'],
                    'veo_task_id': row['veo_task_id'],
                    'prompt': row['prompt'],
                    'generation_type': row['generation_type'],
                    'image_url': row['image_url'],
                    'model': row['model'],
                    'aspect_ratio': row['aspect_ratio'],
                    'status': row['status'],
                    'video_url': row['video_url'],
                    'error_message': row['error_message'],
                    'credits_spent': row['credits_spent'],
                    'created_at': row['created_at'],
                    'completed_at': row['completed_at']
                })
            
            # Экспорт админ логов
            try:
                rows = await conn.fetch("SELECT * FROM admin_logs ORDER BY created_at")
                for row in rows:
                    data['admin_logs'].append({
                        'admin_id': row['admin_id'],
                        'action': row['action'],
                        'target_user_id': row['target_user_id'],
                        'description': row['description'],
                        'created_at': row['created_at']
                    })
            except Exception as e:
                logger.warning(f"Не удалось экспортировать admin_logs: {e}")
            
            await conn.close()
            
            logger.info(f"✅ Экспортировано: {len(data['users'])} пользователей, "
                       f"{len(data['transactions'])} транзакций, "
                       f"{len(data['video_generations'])} видео генераций, "
                       f"{len(data['admin_logs'])} админ логов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта из PostgreSQL: {e}")
            raise
        
        return data
    
    async def import_to_sqlite(self, data: Dict[str, List[Dict[str, Any]]]):
        """Импорт данных в SQLite"""
        logger.info("📥 Импортируем данные в Development SQLite...")
        
        # Удаляем старый файл
        if os.path.exists(self.sqlite_path):
            os.remove(self.sqlite_path)
            logger.info("🗑️ Удален старый SQLite файл")
        
        async with aiosqlite.connect(self.sqlite_path) as db:
            # Создаем таблицы
            await self.create_sqlite_tables(db)
            
            # Импорт пользователей
            for user in data['users']:
                await db.execute('''
                    INSERT INTO users (telegram_id, username, first_name, last_name, credits, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['telegram_id'],
                    user['username'],
                    user['first_name'],
                    user['last_name'],
                    user['credits'],
                    user['status'],
                    user['created_at'].isoformat() if user['created_at'] else None,
                    user['updated_at'].isoformat() if user['updated_at'] else None
                ))
            
            # Импорт транзакций
            for transaction in data['transactions']:
                await db.execute('''
                    INSERT INTO transactions (user_id, type, amount, description, payment_method, payment_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction['user_id'],
                    transaction['type'],
                    transaction['amount'],
                    transaction['description'],
                    transaction['payment_method'],
                    transaction['payment_id'],
                    transaction['created_at'].isoformat() if transaction['created_at'] else None
                ))
            
            # Импорт видео генераций
            for video in data['video_generations']:
                await db.execute('''
                    INSERT INTO video_generations 
                    (user_id, task_id, veo_task_id, prompt, generation_type, image_url, model, aspect_ratio, status, video_url, error_message, credits_spent, created_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
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
                    video['created_at'].isoformat() if video['created_at'] else None,
                    video['completed_at'].isoformat() if video['completed_at'] else None
                ))
            
            # Импорт админ логов
            for log in data['admin_logs']:
                await db.execute('''
                    INSERT INTO admin_logs (admin_id, action, target_user_id, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    log['admin_id'],
                    log['action'],
                    log['target_user_id'],
                    log['description'],
                    log['created_at'].isoformat() if log['created_at'] else None
                ))
            
            await db.commit()
            logger.info("✅ Все данные успешно импортированы в SQLite!")
    
    async def create_sqlite_tables(self, db):
        """Создание таблиц в SQLite"""
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
    
    async def sync(self):
        """Полная синхронизация данных"""
        try:
            print("🔄 СИНХРОНИЗАЦИЯ ДАННЫХ ИЗ PRODUCTION")
            print("=" * 50)
            
            # Экспорт из PostgreSQL
            data = await self.export_from_postgres()
            
            if not any(data.values()):
                logger.warning("⚠️ Нет данных для синхронизации в PostgreSQL!")
                return
            
            # Импорт в SQLite
            await self.import_to_sqlite(data)
            
            print("=" * 50)
            print("🎉 СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            print("=" * 50)
            print("Теперь ваши production данные доступны в development среде.")
            print("Можете работать с ними локально через интерфейс базы данных.")
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации: {e}")
            print(f"\n❌ Ошибка: {e}")
            print("Обратитесь к разработчику за помощью.")

async def main():
    """Главная функция"""
    sync = ProductionSync()
    await sync.sync()

if __name__ == "__main__":
    asyncio.run(main())