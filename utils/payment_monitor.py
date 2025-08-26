"""
Payment monitoring utility to check successful payments and notify users
"""

import asyncio
from typing import List
from datetime import datetime, timedelta
import re

from api_integrations.payment_api import PaymentAPI
from utils.logger import get_logger

logger = get_logger(__name__)

class PaymentMonitor:
    def __init__(self):
        self.payment_api = PaymentAPI()
        self.processed_payments = set()  # Keep track of processed payment IDs
        self.check_interval = 15  # Check every 15 seconds for faster processing
        
    async def check_recent_payments(self, lookback_minutes: int = 60):
        """Check recent log entries for payment IDs and verify their status"""
        try:
            import os
            
            # Look for payment creation logs in recent output
            # This is a simple approach - in production you'd store payment IDs in DB
            
            # Read recent logs to find payment IDs
            payment_ids = []
            
            # Try to find payment IDs from recent bot activity
            # In a real system, you'd have a proper payment tracking table
            
            logger.info(f"Checking recent payments from last {lookback_minutes} minutes")
            
            # Get recent payment IDs from database instead of hardcoded list
            from database.database import db
            
            # Get recent payment IDs that might need checking
            recent_payment_ids = await self.get_recent_payment_ids_from_db(lookback_minutes)
            
            for payment_id in recent_payment_ids:
                if payment_id not in self.processed_payments:
                    await self.check_and_process_payment(payment_id)
                    
        except Exception as e:
            logger.error(f"Error checking recent payments: {e}")
    
    async def get_recent_payment_ids_from_db(self, lookback_minutes: int = 60) -> List[str]:
        """Get recent payment IDs from database that might need verification"""
        try:
            from database.database import db
            from datetime import datetime, timedelta
            
            # Get payment IDs from recent transactions that might not be completed
            cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
            
            if db.use_postgres:
                pool = await db.get_postgres_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT DISTINCT payment_id FROM transactions 
                        WHERE payment_id IS NOT NULL 
                        AND created_at > $1 
                        AND type = 'credit_purchase'
                        AND payment_method = 'yookassa'
                    """, cutoff_time)
                    
                    return [row[0] for row in rows if row[0]]
            else:
                async with db.get_sqlite_connection() as conn:
                    cursor = await conn.execute("""
                        SELECT DISTINCT payment_id FROM transactions 
                        WHERE payment_id IS NOT NULL 
                        AND created_at > ? 
                        AND type = 'credit_purchase'
                        AND payment_method = 'yookassa'
                    """, (cutoff_time.isoformat(),))
                    
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows if row[0]]
                
        except Exception as e:
            logger.error(f"Error getting recent payment IDs from DB: {e}")
            return []
    
    async def check_and_process_payment(self, payment_id: str):
        """Check specific payment and process if successful"""
        try:
            result = await self.payment_api.verify_yookassa_payment(payment_id)
            
            if result.get('paid', False):
                # Payment is successful, check if it was already processed
                from database.database import db
                payment_exists = await db.payment_exists(payment_id)
                
                if not payment_exists:
                    # Process the payment
                    metadata = result.get('metadata', {})
                    user_id = metadata.get('user_id')
                    package_id = metadata.get('package_id')
                    amount = result.get('amount')
                    
                    if user_id and package_id and amount:
                        logger.info(f"Processing untracked successful payment: {payment_id}")
                        
                        success = await self.payment_api._process_successful_card_payment(
                            user_id=int(user_id),
                            package_id=package_id,
                            payment_id=payment_id,
                            amount=float(amount)
                        )
                        
                        if success:
                            logger.info(f"Successfully processed payment {payment_id}")
                            self.processed_payments.add(payment_id)
                        else:
                            logger.error(f"Failed to process payment {payment_id}")
                else:
                    # Payment already processed, just mark as seen to avoid re-notifications
                    self.processed_payments.add(payment_id)
            else:
                logger.info(f"Payment {payment_id} status: {result.get('status')}")
                
        except Exception as e:
            logger.error(f"Error checking payment {payment_id}: {e}")
    
    async def start_monitoring(self):
        """Start the payment monitoring loop"""
        logger.info("Starting payment monitoring...")
        
        while True:
            try:
                await self.check_recent_payments()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in payment monitoring: {e}")
                await asyncio.sleep(self.check_interval)

# Global instance
payment_monitor = PaymentMonitor()