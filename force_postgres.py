#!/usr/bin/env python3
"""
Принудительное переключение на PostgreSQL в deployed среде
"""

import asyncio
import os
import logging
from database.database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def force_postgres_connection():
    """Принудительно проверить и настроить PostgreSQL подключение"""
    
    print("🔧 ПРИНУДИТЕЛЬНОЕ ПЕРЕКЛЮЧЕНИЕ НА POSTGRESQL")
    print("=" * 50)
    
    # Проверяем переменные окружения
    database_url = os.getenv('DATABASE_URL')
    replit_deployment = os.getenv('REPLIT_DEPLOYMENT')
    
    print(f"REPLIT_DEPLOYMENT: {replit_deployment}")
    print(f"DATABASE_URL присутствует: {'ДА' if database_url else 'НЕТ'}")
    
    if not database_url:
        print("❌ DATABASE_URL не найден!")
        return False
    
    # Принудительно устанавливаем asyncpg если нужно
    try:
        import asyncpg
        print("✅ asyncpg доступен")
    except ImportError:
        print("📦 Устанавливаем asyncpg...")
        import subprocess
        subprocess.run(["pip", "install", "asyncpg"], check=True)
        import asyncpg
        print("✅ asyncpg установлен")
    
    # Тестируем подключение
    try:
        conn = await asyncpg.connect(database_url)
        
        # Проверяем данные
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        print(f"✅ Пользователей в PostgreSQL: {user_count}")
        
        if user_count > 0:
            users = await conn.fetch("SELECT telegram_id, credits FROM users LIMIT 5")
            for user in users:
                print(f"   - User {user['telegram_id']}: {user['credits']} credits")
        
        await conn.close()
        print("✅ PostgreSQL подключение работает!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
        return False

async def test_database_selection():
    """Тестируем какую базу выбирает система"""
    
    print("\n🔍 ТЕСТИРОВАНИЕ ВЫБОРА БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    # Создаем Database объект
    db = Database()
    
    print(f"База данных выбрана: {'PostgreSQL' if db.use_postgres else 'SQLite'}")
    print(f"DATABASE_URL настроен: {'ДА' if db.database_url else 'НЕТ'}")
    
    # Проверяем реальное подключение
    if db.use_postgres:
        try:
            user = await db.get_user(1864913930)  # Admin user
            if user:
                print(f"✅ Найден admin: {user.credits} credits")
                return True
            else:
                print("❌ Admin пользователь не найден")
                return False
        except Exception as e:
            print(f"❌ Ошибка получения пользователя: {e}")
            return False
    else:
        print("❌ Система не использует PostgreSQL")
        return False

async def main():
    """Главная функция"""
    
    # Шаг 1: Проверяем PostgreSQL
    postgres_ok = await force_postgres_connection()
    
    # Шаг 2: Проверяем выбор базы
    db_selection_ok = await test_database_selection()
    
    print("\n📋 ИТОГ:")
    print("=" * 50)
    
    if postgres_ok and db_selection_ok:
        print("🎉 ВСЁ РАБОТАЕТ! Deployed бот использует PostgreSQL")
        print("📱 Ваши данные должны быть видны в боте")
    elif postgres_ok and not db_selection_ok:
        print("⚠️  PostgreSQL работает, но система выбирает SQLite")
        print("🔧 Нужно исправить логику выбора базы")
    else:
        print("❌ PostgreSQL подключение не работает")
        print("🔧 Нужно проверить настройки DATABASE_URL")

if __name__ == "__main__":
    asyncio.run(main())