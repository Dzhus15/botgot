from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu inline keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="🎬 Генерировать видео", callback_data="generate_video")],
        [InlineKeyboardButton(text="💰 Купить кредиты", callback_data="buy_credits")],
        [InlineKeyboardButton(text="📖 Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_generation_menu_keyboard() -> InlineKeyboardMarkup:
    """Video generation menu keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="📝 Видео из текста", callback_data="text_to_video")],
        [InlineKeyboardButton(text="🖼 Видео из изображения", callback_data="image_to_video")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payment_menu_keyboard() -> InlineKeyboardMarkup:
    """Payment method selection keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data="pay_stars")],
        [InlineKeyboardButton(text="💳 Банковская карта / СБП", callback_data="pay_card")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_credit_packages_keyboard(payment_method: str) -> InlineKeyboardMarkup:
    """Credit packages keyboard"""
    # Import here to avoid circular import
    from handlers.payments import CREDIT_PACKAGES
    
    keyboard = []
    
    for package_id, package in CREDIT_PACKAGES.items():
        # Format package button text
        text = f"💎 {package['title']}"
        
        if payment_method == "stars":
            text += f" - {package['price_stars']} ⭐️"
        else:
            text += f" - {package['price_rub']} ₽"
        
        # Add bonus indicator
        if package.get('bonus'):
            text += f" (+{package['bonus']} бонус!)"
        
        # Add popular indicator
        if package.get('popular'):
            text = "🔥 " + text
        
        callback_data = f"buy_{payment_method}_{package_id}"
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    
    # Back button
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="buy_credits")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Simple back to main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin menu keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка сообщений", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔍 Проверка платежа", callback_data="admin_check_payment")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_to_admin_keyboard() -> InlineKeyboardMarkup:
    """Back to admin menu keyboard"""
    keyboard = [
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_video_result_keyboard(video_url: str = None) -> InlineKeyboardMarkup:
    """Keyboard for video generation result"""
    keyboard = []
    
    if video_url:
        keyboard.append([InlineKeyboardButton(text="📥 Скачать видео", url=video_url)])
    
    keyboard.extend([
        [InlineKeyboardButton(text="🎬 Создать еще видео", callback_data="generate_video")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirm_payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    """Keyboard with payment confirmation button"""
    keyboard = [
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_credits")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
