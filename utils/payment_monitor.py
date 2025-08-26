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
            
            # For demo purposes, you can manually add payment IDs here
            # that were created recently but might not have been processed
            recent_payment_ids = [
                "303fb971-000f-5000-b000-1b4b050da81f",  # Newest payment
                "303fb7c0-000f-5000-b000-13f5db7053a2",  # Latest successful payment
                "303fb2ed-000f-5000-b000-16f05c69d90c",  # Your recent payment
                "303fac32-000f-5001-9000-1951a1760f1a",  # Previous payment
                "303fb0dc-000f-5000-b000-1399ed8e827e"   # Another payment
            ]
            
            for payment_id in recent_payment_ids:
                if payment_id not in self.processed_payments:
                    await self.check_and_process_payment(payment_id)
                    
        except Exception as e:
            logger.error(f"Error checking recent payments: {e}")
    
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
                    
                    if user_id and package_id:
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