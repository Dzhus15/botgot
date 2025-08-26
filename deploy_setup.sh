#!/bin/bash

echo "🚀 АВТОМАТИЧЕСКАЯ НАСТРОЙКА ДЕПЛОЯ"
echo "=================================="

# Установка зависимостей
echo "📦 Устанавливаем зависимости..."
pip install -q aiogram aiosqlite aiohttp

# Проверяем среду
if [ "$REPLIT_DEPLOYMENT" = "1" ]; then
    echo "🌍 Обнаружена deployment среда"
    
    # Устанавливаем PostgreSQL драйвер
    echo "🐘 Устанавливаем PostgreSQL драйвер..."
    pip install -q asyncpg
    
    # Запускаем автоматическую миграцию
    echo "🔄 Запускаем автоматическую миграцию данных..."
    python auto_migrate.py
    
    echo "✅ Деплой настроен успешно!"
else
    echo "🏠 Обнаружена development среда"
    echo "ℹ️  Миграция будет выполнена при деплое"
fi

echo "✅ Установка завершена!"