#!/usr/bin/env python3
"""
Инструмент для ручного управления кредитами пользователей
"""
import asyncio
import sys
import os

# Добавляем корневую папку в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import db, init_database
from database.models import Transaction, TransactionType

async def add_credits_to_user(telegram_id: int, credits: int, description: str = "Manual credit adjustment"):
    """Добавить кредиты пользователю"""
    await init_database()
    
    # Получаем пользователя
    user = await db.get_user(telegram_id)
    if not user:
        print(f"🤖 Пользователь с ID {telegram_id} не найден в базе данных")
        print(f"📝 Создаю профиль пользователя...")
        
        # Создаем пользователя
        from database.models import User, UserStatus
        new_user = User(
            telegram_id=telegram_id,
            credits=0,
            status=UserStatus.REGULAR,
            first_name="Неизвестно",
            username=None
        )
        
        created = await db.create_user(new_user)
        if not created:
            print(f"❌ Ошибка при создании пользователя")
            return False
        
        user = await db.get_user(telegram_id)
        print(f"✅ Пользователь создан")
    else:
        print(f"👤 Найден пользователь: {user.first_name} (@{user.username})")
    
    print(f"💰 Текущий баланс: {user.credits} кредитов")
    
    # Обновляем кредиты
    new_credits = user.credits + credits
    success = await db.update_user_credits(telegram_id, new_credits)
    
    if success:
        # Создаем запись транзакции
        transaction = Transaction(
            user_id=telegram_id,
            type=TransactionType.ADMIN_GRANT,
            amount=credits,
            description=description
        )
        await db.create_transaction(transaction)
        
        print(f"✅ Успешно добавлено {credits} кредитов")
        print(f"💳 Новый баланс: {new_credits} кредитов")
        return True
    else:
        print(f"❌ Ошибка при обновлении кредитов")
        return False

async def find_recent_payments(amount: int = 399):
    """Найти недавние платежи на определенную сумму"""
    await init_database()
    
    print(f"🔍 Поиск платежей на сумму {amount} рублей...")
    
    # Здесь можно добавить логику поиска по транзакциям
    # Пока что просто выводим инструкцию
    print("💡 Для поиска пользователя используйте:")
    print("   - Telegram ID пользователя")
    print("   - Username пользователя")

async def main():
    """Главная функция"""
    if len(sys.argv) < 3:
        print("📋 Использование:")
        print(f"   python {sys.argv[0]} <telegram_id> <credits> [описание]")
        print("\n🔍 Примеры:")
        print(f"   python {sys.argv[0]} 123456789 35 'Компенсация за пакет 399₽'")
        print(f"   python {sys.argv[0]} 123456789 -10 'Возврат ошибочного начисления'")
        return
    
    try:
        telegram_id = int(sys.argv[1])
        credits = int(sys.argv[2])
        description = sys.argv[3] if len(sys.argv) > 3 else "Manual credit adjustment"
        
        print(f"🎯 Начисление {credits} кредитов пользователю {telegram_id}")
        
        success = await add_credits_to_user(telegram_id, credits, description)
        
        if success:
            print("🎉 Операция выполнена успешно!")
        else:
            print("💥 Операция не выполнена!")
            
    except ValueError:
        print("❌ Неверный формат данных. Telegram ID и количество кредитов должны быть числами.")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())