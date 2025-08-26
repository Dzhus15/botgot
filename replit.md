# Overview

This is a Telegram bot that generates AI videos using Google's Veo 3 API through the kie.ai platform. The bot provides text-to-video and image-to-video generation capabilities with a credit-based payment system. Users can purchase credits using Telegram Stars or traditional payment methods (YooKassa), and each video generation costs 10 credits. The bot includes comprehensive admin functionality for user management and broadcasting.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework and Communication
Built on aiogram (asynchronous Telegram bot framework) with handler-based routing for different bot commands and interactions. Uses inline keyboards for user navigation and FSM (Finite State Machine) for managing user conversation states during video generation and payment flows.

## Database Layer
SQLite-based persistence layer with async operations using aiosqlite. Core entities include:
- Users: Telegram ID, credits balance, admin status, user metadata
- Transactions: Credit purchases and spending with audit trail
- Video Generations: Task tracking for AI video creation
- Admin Logs: Activity tracking for administrative actions

Default admin user (ID: 1864913930) receives 100 credits and admin privileges on first registration.

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
- Environment variable configuration for all API keys and secrets
- Rate limiting middleware (5 requests per minute per user)
- Input validation for prompts with content filtering
- Parameterized database queries for SQL injection prevention
- Comprehensive logging without sensitive data exposure

## Administrative Features
Admin-only functionality includes:
- User statistics and analytics dashboard
- Broadcast messaging system with media support
- Credit management and user account control
- Activity monitoring and audit trails

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