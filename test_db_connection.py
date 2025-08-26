#!/usr/bin/env python3
"""
Тест подключения к базе данных
"""
import asyncio
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    print("🔍 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ")
    print("=" * 50)
    
    # Проверяем переменные окружения
    database_url = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {'Настроен ✅' if database_url else 'НЕ настроен ❌'}")
    
    # Проверяем импорт asyncpg
    try:
        import asyncpg
        print("asyncpg: Доступен ✅")
        postgres_available = True
    except ImportError:
        print("asyncpg: НЕ доступен ❌")
        postgres_available = False
    
    # Тестируем создание Database объекта
    from database.database import Database
    db = Database()
    
    print(f"База данных выбрана: {'PostgreSQL ✅' if db.use_postgres else 'SQLite ❌'}")
    
    # Проверяем подключение к PostgreSQL
    if db.use_postgres and postgres_available and database_url:
        try:
            import asyncpg
            conn = await asyncpg.connect(database_url)
            
            # Проверяем данные в PostgreSQL
            result = await conn.fetchval("SELECT COUNT(*) FROM users")
            print(f"Пользователей в PostgreSQL: {result}")
            
            users = await conn.fetch("SELECT telegram_id, credits FROM users")
            for user in users:
                print(f"  - User {user['telegram_id']}: {user['credits']} credits")
            
            await conn.close()
            print("Подключение к PostgreSQL: РАБОТАЕТ ✅")
            
        except Exception as e:
            print(f"Ошибка подключения к PostgreSQL: {e} ❌")
    
    # Проверяем SQLite
    import aiosqlite
    sqlite_path = "bot_database.db"
    
    if os.path.exists(sqlite_path):
        print(f"SQLite файл существует: {sqlite_path}")
        
        try:
            async with aiosqlite.connect(sqlite_path) as sqlite_db:
                cursor = await sqlite_db.execute("SELECT COUNT(*) FROM users")
                result = await cursor.fetchone()
                print(f"Пользователей в SQLite: {result[0] if result else 0}")
        except Exception as e:
            print(f"Ошибка чтения SQLite: {e}")
    else:
        print("SQLite файл не существует")
    
    print("=" * 50)
    print("🎯 РЕКОМЕНДАЦИЯ:")
    
    if db.use_postgres:
        print("✅ Система правильно настроена на PostgreSQL")
        print("📱 Перезапустите deployed бота для применения изменений")
    else:
        print("❌ Система использует SQLite вместо PostgreSQL") 
        print("🔧 Проверьте настройки DATABASE_URL в deployed среде")

if __name__ == "__main__":
    asyncio.run(test_connection())