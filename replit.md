# Overview

This is a Telegram bot that generates AI videos using Google's Veo 3 API through the kie.ai platform. The bot provides text-to-video and image-to-video generation capabilities with a credit-based payment system. Users can purchase credits using Telegram Stars or traditional payment methods (YooKassa), and each video generation costs 10 credits. The bot includes comprehensive admin functionality for user management and broadcasting.

# Recent Changes

**2025-08-26**: 
- ✅ Fixed tokenomics: 399₽ package now gives 50 credits (5 video generations)
- ✅ Fixed database connection issues in payment monitoring system
- ✅ Increased rate limiting from 15 to 100 messages per minute
- ✅ Added manual credit management tool (admin_tools/credit_manager.py)
- ✅ Hybrid database system: SQLite (current) + PostgreSQL ready for production
- ✅ User 848867375 compensated with 35 credits for incorrect 399₽ package
- ✅ **NEW**: Secure admin credit management system with production-only restrictions
- ✅ **NEW**: Automatic user notifications when admin grants credits with custom comments
- ✅ **NEW**: Complete audit trail for all admin credit operations
- ✅ **SECURITY**: Fixed all critical payment vulnerabilities - HMAC verification, rate limiting, race conditions
- ✅ **SECURITY**: Enhanced Telegram Stars payment validation against fraud attempts
- ✅ **SECURITY**: Strengthened webhook IP validation (removed localhost bypass)

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework and Communication
Built on aiogram (asynchronous Telegram bot framework) with handler-based routing for different bot commands and interactions. Uses inline keyboards for user navigation and FSM (Finite State Machine) for managing user conversation states during video generation and payment flows.

## Database Layer
Hybrid database system with SQLite-based persistence layer using aiosqlite (currently active) and PostgreSQL support ready for production deployment. Automatically switches to PostgreSQL when asyncpg is available and DATABASE_URL is configured. Core entities include:
- Users: Telegram ID, credits balance, admin status, user metadata
- Transactions: Credit purchases and spending with audit trail
- Video Generations: Task tracking for AI video creation
- Admin Logs: Activity tracking for administrative actions

Default admin user (ID: 1864913930) receives 100 credits and admin privileges on first registration. Database persists data during redeploys when using PostgreSQL.

## Credit System and Payments
Dual payment integration supporting:
- Telegram Stars for in-app purchases
- YooKassa for traditional payment methods (cards, SBP)
Fixed pricing at 10 credits per video generation with configurable credit packages.

## AI Video Generation
Integration with Veo 3 API through kie.ai platform supporting:
- Text-to-video generation from prompts
- Image-to-video generation (with image upload handling)
- Configurable models (default: veo3_fast for cost efficiency)
- Standard 16:9 aspect ratio output

## Security and Rate Limiting
- **Enhanced Payment Security**: HMAC signature verification for YooKassa webhooks with configurable secret
- **Fraud Prevention**: Multi-layer validation for Telegram Stars payments including amount verification and user ID matching
- **Rate Limiting**: Dual-layer protection - user rate limiting (100 msg/60s) + webhook rate limiting (10 req/60s per IP)
- **Race Condition Protection**: Atomic payment processing with database constraints to prevent duplicate credit grants
- **Webhook Security**: Strict IP validation for YooKassa webhooks without localhost bypass vulnerabilities
- Environment variable configuration for all API keys and secrets
- Input validation for prompts with content filtering
- Parameterized database queries for SQL injection prevention
- Comprehensive logging without sensitive data exposure

## Administrative Features
Admin-only functionality includes:
- User statistics and analytics dashboard
- Broadcast messaging system with media support
- **Advanced credit management system:**
  - Check user credits balance by Telegram ID
  - Grant credits with custom reason/comment (production only)
  - Automatic user notifications with admin comments
  - Complete audit logging and transaction records
  - Environment-aware security (local vs production)
- Activity monitoring and comprehensive audit trails
- Payment verification and manual credit recovery tools

## Error Handling and Resilience
Comprehensive error handling with user-friendly messages, structured logging with rotation, graceful degradation for API failures, and async architecture for handling concurrent requests.

# External Dependencies

## Primary APIs
- **Telegram Bot API**: Core bot functionality via aiogram library
- **Veo 3 AI API**: Video generation through kie.ai platform (api.kie.ai)
- **YooKassa Payment API**: Russian payment processing for cards and SBP
- **Telegram Payments API**: Telegram Stars integration

## Database
- **SQLite**: Local persistent storage with async operations via aiosqlite

## Python Libraries
- **aiogram**: Telegram bot framework with async support
- **aiosqlite**: Async SQLite database operations
- **aiohttp**: HTTP client for API integrations
- **logging**: Built-in Python logging with rotation

## Infrastructure
- **Replit Environment**: Hosting platform with secrets management
- **File Storage**: Local filesystem for database and logs

## Authentication Requirements
- TELEGRAM_BOT_TOKEN: Bot authentication with Telegram
- VEO_API_KEY: Access to Veo 3 video generation API
- YOOKASSA_API_KEY & YOOKASSA_SHOP_ID: Payment processing credentials
- TELEGRAM_PAYMENTS_TOKEN: Telegram Stars payment processing