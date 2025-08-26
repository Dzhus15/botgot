#!/usr/bin/env python3
"""
Utility to setup YooKassa webhooks for payment notifications
Run this script once to configure webhooks in your YooKassa account
"""

import asyncio
import aiohttp
import base64
import json
from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)
config = Config()

class YooKassaWebhookSetup:
    def __init__(self):
        self.yookassa_api_key = config.YOOKASSA_API_KEY
        self.yookassa_shop_id = config.YOOKASSA_SHOP_ID
        self.yookassa_base_url = "https://api.yookassa.ru/v3"
        
    def get_webhook_url(self):
        """Get the webhook URL for your Replit app"""
        # Replace with your actual Replit app URL
        replit_url = "https://your-repl-name.your-username.repl.co"  # Update this!
        return f"{replit_url}/webhook/yookassa"
    
    async def setup_webhooks(self):
        """Setup webhooks for payment notifications"""
        
        if not self.yookassa_api_key or not self.yookassa_shop_id:
            logger.error("❌ YooKassa credentials not configured!")
            logger.error("Please set YOOKASSA_API_KEY and YOOKASSA_SHOP_ID environment variables")
            return False
            
        webhook_url = self.get_webhook_url()
        logger.info(f"Setting up webhook URL: {webhook_url}")
        
        # Events we want to receive notifications for
        events = [
            "payment.succeeded",
            "payment.canceled", 
            "payment.waiting_for_capture",
            "refund.succeeded"
        ]
        
        success = True
        
        for event in events:
            if await self.create_webhook(event, webhook_url):
                logger.info(f"✅ Webhook created for event: {event}")
            else:
                logger.error(f"❌ Failed to create webhook for event: {event}")
                success = False
        
        if success:
            logger.info("🎉 All webhooks configured successfully!")
            logger.info("💡 Make sure your app is running on the webhook URL")
        else:
            logger.error("⚠️ Some webhooks failed to configure")
            
        return success
    
    async def create_webhook(self, event: str, webhook_url: str) -> bool:
        """Create a single webhook for specific event"""
        try:
            auth_string = f"{self.yookassa_shop_id}:{self.yookassa_api_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {auth_bytes}",
                "Content-Type": "application/json",
                "Idempotence-Key": f"webhook-{event}-setup"
            }
            
            webhook_data = {
                "event": event,
                "url": webhook_url
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.yookassa_base_url}/webhooks",
                    headers=headers,
                    json=webhook_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status in [200, 201]:
                        result = await response.json()
                        logger.debug(f"Webhook created: {result}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"YooKassa webhook creation error {response.status}: {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error creating webhook for {event}: {e}")
            return False
    
    async def list_webhooks(self):
        """List existing webhooks"""
        try:
            auth_string = f"{self.yookassa_shop_id}:{self.yookassa_api_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {auth_bytes}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.yookassa_base_url}/webhooks",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info("📋 Current webhooks:")
                        
                        webhooks = result.get("items", [])
                        if not webhooks:
                            logger.info("   No webhooks configured")
                        else:
                            for webhook in webhooks:
                                logger.info(f"   {webhook['event']} -> {webhook['url']}")
                        
                        return webhooks
                    else:
                        error_text = await response.text()
                        logger.error(f"Error listing webhooks {response.status}: {error_text}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error listing webhooks: {e}")
            return []

async def main():
    """Main function to run webhook setup"""
    print("🔧 YooKassa Webhook Setup Utility")
    print("=" * 40)
    
    setup = YooKassaWebhookSetup()
    
    # First, list existing webhooks
    print("\n📋 Checking existing webhooks...")
    await setup.list_webhooks()
    
    # Setup new webhooks
    print(f"\n🔗 Setting up webhooks for URL: {setup.get_webhook_url()}")
    print("⚠️  IMPORTANT: Update the webhook URL in this script with your actual Replit app URL!")
    
    success = await setup.setup_webhooks()
    
    if success:
        print("\n✅ Webhook setup completed successfully!")
        print("\n📝 Next steps:")
        print("1. Make sure your bot is running on the webhook URL")
        print("2. Test a payment to verify webhooks work")
        print("3. Check logs for incoming webhook notifications")
    else:
        print("\n❌ Webhook setup failed!")
        print("Please check your YooKassa API credentials and try again")

if __name__ == "__main__":
    asyncio.run(main())