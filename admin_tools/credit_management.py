#!/usr/bin/env python3
"""
Безопасная система управления кредитами для администратора
Работает только на production (deploy), не на локальном запуске
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from database.database import db
from database.models import User, Transaction, TransactionType, UserStatus, AdminLog
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
config = Config()

class CreditManager:
    """Безопасный менеджер кредитов для администраторов"""
    
    def __init__(self):
        self.is_production = self._is_production_environment()
        
    def _is_production_environment(self) -> bool:
        """Определяет, запущено ли приложение в production (на деплое)"""
        # Проверяем наличие DATABASE_URL (означает Replit production)
        database_url = os.getenv('DATABASE_URL')
        replit_deployment = os.getenv('REPLIT_DEPLOYMENT') == '1'
        
        # Production если есть DATABASE_URL или явно указан деплой
        return bool(database_url) or replit_deployment
    
    async def check_admin_permissions(self, admin_id: int) -> bool:
        """Проверяет права администратора"""
        try:
            admin = await db.get_user(admin_id)
            if not admin or admin.status != UserStatus.ADMIN:
                logger.warning(f"Unauthorized credit management attempt by user {admin_id}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking admin permissions for {admin_id}: {e}")
            return False
    
    async def get_user_credits(self, admin_id: int, target_user_id: int) -> Optional[Dict[str, Any]]:
        """
        Проверяет баланс кредитов пользователя
        
        Args:
            admin_id: ID администратора
            target_user_id: ID пользователя для проверки
            
        Returns:
            Dict с информацией о кредитах или None при ошибке
        """
        try:
            # Проверяем права администратора
            if not await self.check_admin_permissions(admin_id):
                return {"error": "Недостаточно прав для выполнения операции"}
            
            # Получаем информацию о пользователе
            user = await db.get_user(target_user_id)
            if not user:
                return {"error": f"Пользователь {target_user_id} не найден"}
            
            # Логируем проверку
            await db.log_admin_action(AdminLog(
                admin_id=admin_id,
                action="check_credits",
                target_user_id=target_user_id,
                description=f"Проверка баланса пользователя {target_user_id}"
            ))
            
            return {
                "user_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "credits": user.credits,
                "status": user.status.value,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
            
        except Exception as e:
            logger.error(f"Error checking credits for user {target_user_id}: {e}")
            return {"error": f"Ошибка при проверке кредитов: {str(e)}"}
    
    async def grant_credits(self, admin_id: int, target_user_id: int, credits_amount: int, reason: str = "") -> Dict[str, Any]:
        """
        Выдает кредиты пользователю (только на production)
        
        Args:
            admin_id: ID администратора
            target_user_id: ID пользователя
            credits_amount: Количество кредитов для выдачи
            reason: Причина выдачи кредитов
            
        Returns:
            Dict с результатом операции
        """
        try:
            # КРИТИЧЕСКАЯ ПРОВЕРКА: только на production!
            if not self.is_production:
                logger.warning(f"Credit grant attempt in non-production environment by admin {admin_id}")
                return {
                    "error": "Выдача кредитов доступна только на production (после deploy)",
                    "environment": "local/development"
                }
            
            # Проверяем права администратора
            if not await self.check_admin_permissions(admin_id):
                return {"error": "Недостаточно прав для выполнения операции"}
            
            # Валидация количества кредитов
            if not isinstance(credits_amount, int) or credits_amount <= 0:
                return {"error": "Количество кредитов должно быть положительным целым числом"}
            
            if credits_amount > 1000:  # Лимит безопасности
                return {"error": "Максимальное количество кредитов за раз: 1000"}
            
            # Получаем пользователя
            user = await db.get_user(target_user_id)
            if not user:
                return {"error": f"Пользователь {target_user_id} не найден"}
            
            old_credits = user.credits
            new_credits = old_credits + credits_amount
            
            # Обновляем кредиты
            success = await db.update_user_credits(target_user_id, new_credits)
            if not success:
                return {"error": "Ошибка при обновлении кредитов в базе данных"}
            
            # Создаем транзакцию
            transaction = Transaction(
                user_id=target_user_id,
                type=TransactionType.ADMIN_GRANT,
                amount=credits_amount,
                description=f"Выдача кредитов администратором {admin_id}. Причина: {reason or 'Не указана'}",
                created_at=datetime.now()
            )
            
            await db.create_transaction(transaction)
            
            # Логируем действие администратора
            await db.log_admin_action(AdminLog(
                admin_id=admin_id,
                action="grant_credits",
                target_user_id=target_user_id,
                description=f"Выдано {credits_amount} кредитов. Баланс: {old_credits} → {new_credits}. Причина: {reason}"
            ))
            
            logger.info(f"Admin {admin_id} granted {credits_amount} credits to user {target_user_id}. Balance: {old_credits} → {new_credits}")
            
            return {
                "success": True,
                "user_id": target_user_id,
                "credits_granted": credits_amount,
                "old_balance": old_credits,
                "new_balance": new_credits,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error granting credits to user {target_user_id}: {e}")
            return {"error": f"Ошибка при выдаче кредитов: {str(e)}"}

# Глобальный экземпляр менеджера
credit_manager = CreditManager()

async def check_user_credits(admin_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Публичная функция для проверки кредитов пользователя
    
    Args:
        admin_id: ID администратора
        user_id: ID пользователя для проверки
        
    Returns:
        Информация о кредитах пользователя
    """
    return await credit_manager.get_user_credits(admin_id, user_id)

async def grant_user_credits(admin_id: int, user_id: int, credits: int, reason: str = "") -> Dict[str, Any]:
    """
    Публичная функция для выдачи кредитов пользователю
    РАБОТАЕТ ТОЛЬКО НА PRODUCTION!
    
    Args:
        admin_id: ID администратора
        user_id: ID пользователя
        credits: Количество кредитов
        reason: Причина выдачи
        
    Returns:
        Результат операции
    """
    return await credit_manager.grant_credits(admin_id, user_id, credits, reason)

# Функция для быстрого восстановления кредитов при deploy
async def emergency_credit_restore(admin_id: int, user_id: int, credits: int, payment_id: str = "") -> Dict[str, Any]:
    """
    Экстренное восстановление кредитов (например, после технических проблем)
    
    Args:
        admin_id: ID администратора
        user_id: ID пользователя
        credits: Количество кредитов
        payment_id: ID платежа (если есть)
        
    Returns:
        Результат операции
    """
    reason = f"Экстренное восстановление кредитов"
    if payment_id:
        reason += f" для платежа {payment_id}"
    
    return await grant_user_credits(admin_id, user_id, credits, reason)

if __name__ == "__main__":
    # Пример использования (только для тестирования)
    async def main():
        print("🔒 Credit Management System")
        print(f"Production mode: {credit_manager.is_production}")
        
        if credit_manager.is_production:
            print("✅ Система готова к выдаче кредитов")
        else:
            print("⚠️  Локальная среда - выдача кредитов заблокирована")
    
    asyncio.run(main())