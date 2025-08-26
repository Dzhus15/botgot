#!/usr/bin/env python3
"""
Инструменты для выдачи кредитов при deploy
Используется для быстрого восстановления кредитов пользователей
"""

import asyncio
import sys
from typing import List, Dict, Any
from credit_management import check_user_credits, grant_user_credits, emergency_credit_restore
from database.database import db, init_database
from config import Config

config = Config()

class DeployCreditTools:
    """Инструменты для работы с кредитами при deploy"""
    
    def __init__(self):
        self.admin_id = config.ADMIN_USER_ID
        
    async def batch_check_credits(self, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Проверяет кредиты нескольких пользователей"""
        results = {}
        
        print(f"🔍 Проверяем кредиты {len(user_ids)} пользователей...")
        
        for user_id in user_ids:
            try:
                result = await check_user_credits(self.admin_id, user_id)
                results[user_id] = result
                
                if "error" not in result:
                    print(f"👤 {user_id}: {result['credits']} кредитов")
                else:
                    print(f"❌ {user_id}: {result['error']}")
                    
            except Exception as e:
                print(f"❌ Ошибка при проверке {user_id}: {e}")
                results[user_id] = {"error": str(e)}
        
        return results
    
    async def batch_grant_credits(self, credit_assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Массовая выдача кредитов
        
        Args:
            credit_assignments: список словарей с ключами:
                - user_id: ID пользователя
                - credits: количество кредитов
                - reason: причина (опционально)
                - payment_id: ID платежа (опционально)
        """
        results = {
            "success": [],
            "failed": [],
            "total_credits_granted": 0
        }
        
        print(f"💰 Начинаем массовую выдачу кредитов для {len(credit_assignments)} пользователей...")
        
        for assignment in credit_assignments:
            user_id = assignment.get("user_id")
            credits = assignment.get("credits")
            reason = assignment.get("reason", "Массовая выдача при deploy")
            payment_id = assignment.get("payment_id", "")
            
            if not user_id or not credits:
                print(f"❌ Пропуск неверного задания: {assignment}")
                results["failed"].append({
                    "assignment": assignment,
                    "error": "Отсутствует user_id или credits"
                })
                continue
            
            try:
                if payment_id:
                    result = await emergency_credit_restore(self.admin_id, user_id, credits, payment_id)
                else:
                    result = await grant_user_credits(self.admin_id, user_id, credits, reason)
                
                if result.get("success"):
                    print(f"✅ {user_id}: +{credits} кредитов")
                    results["success"].append(result)
                    results["total_credits_granted"] += credits
                else:
                    print(f"❌ {user_id}: {result.get('error', 'Неизвестная ошибка')}")
                    results["failed"].append({
                        "user_id": user_id,
                        "credits": credits,
                        "error": result.get("error")
                    })
                    
            except Exception as e:
                print(f"❌ Ошибка при выдаче кредитов {user_id}: {e}")
                results["failed"].append({
                    "user_id": user_id,
                    "credits": credits,
                    "error": str(e)
                })
        
        print(f"\n📊 Итоги массовой выдачи:")
        print(f"✅ Успешно: {len(results['success'])}")
        print(f"❌ Ошибок: {len(results['failed'])}")
        print(f"💰 Всего выдано кредитов: {results['total_credits_granted']}")
        
        return results
    
    async def restore_lost_payment(self, user_id: int, credits: int, payment_id: str) -> Dict[str, Any]:
        """Восстанавливает кредиты для потерянного платежа"""
        print(f"🚨 Восстанавливаем потерянный платеж...")
        print(f"👤 Пользователь: {user_id}")
        print(f"💰 Кредиты: {credits}")
        print(f"💳 Платеж: {payment_id}")
        
        result = await emergency_credit_restore(self.admin_id, user_id, credits, payment_id)
        
        if result.get("success"):
            print(f"✅ УСПЕШНО! Восстановлено {credits} кредитов")
        else:
            print(f"❌ ОШИБКА: {result.get('error')}")
        
        return result

async def main():
    """Основная функция для интерактивного использования"""
    print("🚀 Deploy Credit Tools")
    print("=" * 40)
    
    # Инициализируем базу данных
    await init_database()
    
    tools = DeployCreditTools()
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python deploy_credit_tools.py check <user_id>")
        print("  python deploy_credit_tools.py grant <user_id> <credits> [reason]")
        print("  python deploy_credit_tools.py restore <user_id> <credits> <payment_id>")
        return
    
    command = sys.argv[1].lower()
    
    if command == "check" and len(sys.argv) >= 3:
        user_id = int(sys.argv[2])
        result = await check_user_credits(config.ADMIN_USER_ID, user_id)
        print(f"Результат: {result}")
        
    elif command == "grant" and len(sys.argv) >= 4:
        user_id = int(sys.argv[2])
        credits = int(sys.argv[3])
        reason = sys.argv[4] if len(sys.argv) > 4 else "Deploy credit grant"
        
        result = await grant_user_credits(config.ADMIN_USER_ID, user_id, credits, reason)
        print(f"Результат: {result}")
        
    elif command == "restore" and len(sys.argv) >= 5:
        user_id = int(sys.argv[2])
        credits = int(sys.argv[3])
        payment_id = sys.argv[4]
        
        result = await tools.restore_lost_payment(user_id, credits, payment_id)
        print(f"Результат: {result}")
        
    else:
        print("❌ Неверная команда или недостаточно аргументов")

if __name__ == "__main__":
    asyncio.run(main())