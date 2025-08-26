#!/usr/bin/env python3
"""
Быстрое восстановление кредитов конкретному пользователю
"""
import asyncio
import sys
from database.database import db
from database.models import Transaction, TransactionType, PaymentMethod, AdminLog

async def restore_credits(telegram_id: int, credits: int, comment: str):
    """Восстановить кредиты пользователю"""
    print(f"🔧 Восстановление кредитов пользователю {telegram_id}")
    
    # Проверить существование пользователя
    user = await db.get_user(telegram_id)
    if not user:
        print(f"❌ Пользователь {telegram_id} не найден!")
        return False
    
    old_credits = user.credits
    new_credits = old_credits + credits
    
    # Обновить кредиты
    success = await db.update_user_credits(telegram_id, new_credits)
    if not success:
        print(f"❌ Ошибка обновления кредитов!")
        return False
    
    # Создать транзакцию
    transaction = Transaction(
        user_id=telegram_id,
        type=TransactionType.ADMIN_GRANT,
        amount=credits,
        description=f"Восстановление: {comment}",
        payment_method=PaymentMethod.ADMIN_GRANT
    )
    await db.create_transaction(transaction)
    
    # Создать админ лог
    admin_log = AdminLog(
        admin_id=1864913930,  # ID админа
        action="credit_recovery",
        target_user_id=telegram_id,
        description=f"Восстановлено {credits} кредитов: {comment}"
    )
    await db.create_admin_log(admin_log)
    
    print(f"✅ Успешно!")
    print(f"   Было кредитов: {old_credits}")
    print(f"   Добавлено: {credits}")
    print(f"   Стало кредитов: {new_credits}")
    return True

async def show_users():
    """Показать всех пользователей"""
    print("📋 Пользователи в базе данных:")
    print("-" * 60)
    
    if db.use_postgres:
        conn = await db.get_postgres_connection()
        try:
            rows = await conn.fetch("""
                SELECT telegram_id, username, first_name, credits, created_at 
                FROM users 
                ORDER BY created_at
            """)
            for row in rows:
                username = row[1] or "нет"
                first_name = row[2] or "нет"
                created = row[4].strftime("%d.%m.%Y %H:%M")
                print(f"ID: {row[0]:<12} | @{username:<15} | {first_name:<15} | {row[3]:>3} кредитов | {created}")
        finally:
            await conn.close()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Показать пользователей
        asyncio.run(show_users())
        print("\nИспользование:")
        print(f"  python {sys.argv[0]} telegram_id количество_кредитов 'комментарий'")
        print(f"  python {sys.argv[0]} 123456789 50 'Восстановление после redeploy'")
    elif len(sys.argv) == 4:
        # Восстановить кредиты
        telegram_id = int(sys.argv[1])
        credits = int(sys.argv[2])
        comment = sys.argv[3]
        asyncio.run(restore_credits(telegram_id, credits, comment))
    else:
        print("❌ Неверное количество аргументов!")
        print("Использование:")
        print(f"  python {sys.argv[0]} telegram_id количество_кредитов 'комментарий'")