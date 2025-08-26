#!/bin/bash

echo "🔄 БЫСТРАЯ МИГРАЦИЯ ДАННЫХ"
echo "================================"
echo "Этот скрипт перенесет все данные из SQLite в PostgreSQL"
echo ""

# Проверяем, что мы в правильной среде
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ОШИБКА: DATABASE_URL не найден!"
    echo "Убедитесь, что вы запускаете это в production (deployed) среде."
    echo ""
    echo "Чтобы запустить миграцию:"
    echo "1. Нажмите 'Deploy' в Replit"
    echo "2. Откройте консоль в deployed версии"
    echo "3. Запустите: bash migrate_data.sh"
    exit 1
fi

# Устанавливаем зависимости если нужно
echo "📦 Проверяем зависимости..."
pip install asyncpg aiosqlite > /dev/null 2>&1

# Запускаем миграцию
echo "🚀 Запускаем миграцию данных..."
python database_migration.py

echo ""
echo "✅ Готово! Теперь перезапустите бота для применения изменений."