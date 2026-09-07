from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

def get_user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖥️ Забронировать место")],
            [KeyboardButton(text="📋 Мои бронирования")],
            [KeyboardButton(text="❌ Отменить бронь")]
        ],
        resize_keyboard=True
    )

def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖥️ Забронировать место"), KeyboardButton(text="📋 Мои бронирования")],
            [KeyboardButton(text="❌ Отменить бронь"), KeyboardButton(text="📋 Все брони")],
            [KeyboardButton(text="➕ Добавить место"), KeyboardButton(text="➖ Удалить место")],
            [KeyboardButton(text="👥 Администраторы"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🔙 В главное меню")]
        ],
        resize_keyboard=True
    )

def get_super_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖥️ Забронировать место"), KeyboardButton(text="📋 Мои бронирования")],
            [KeyboardButton(text="❌ Отменить бронь"), KeyboardButton(text="📋 Все брони")],
            [KeyboardButton(text="➕ Добавить место"), KeyboardButton(text="➖ Удалить место")],
            [KeyboardButton(text="👥 Управление админами"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🔙 В главное меню")]
        ],
        resize_keyboard=True
    )

def get_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def generate_workplaces_kb(workplaces, action="select"):
    builder = InlineKeyboardBuilder()
    for wp_id, name in workplaces:
        builder.button(
            text=f"🖥️ {name}",
            callback_data=f"{action}_wp_{wp_id}"
        )
    builder.adjust(1)
    return builder.as_markup()

def generate_bookings_kb(bookings, is_admin=False):
    builder = InlineKeyboardBuilder()
    for booking in bookings:
        if is_admin:
            text = f"👤 {booking[1]} | 🖥️ {booking[2]} | 📅 {booking[3]} - {booking[4]}"
        else:
            text = f"🖥️ {booking[1]} | 📅 {booking[2]} - {booking[3]}"
        
        builder.button(
            text=text,
            callback_data=f"cancel_{booking[0]}"
        )
    builder.adjust(1)
    return builder.as_markup()

def generate_calendar_kb(selected_date=None):
    if not selected_date:
        selected_date = datetime.now()
    
    builder = InlineKeyboardBuilder()
    
    # Month header
    month_name = selected_date.strftime("%B %Y")
    builder.button(text=month_name, callback_data="ignore")
    
    # Week days
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in week_days:
        builder.button(text=day, callback_data="ignore")
    
    # Days
    first_day = selected_date.replace(day=1)
    last_day = (first_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Empty cells before first day
    for _ in range(first_day.weekday()):
        builder.button(text=" ", callback_data="ignore")
    
    # Days of month
    for day in range(1, last_day.day + 1):
        date = first_day.replace(day=day)
        builder.button(
            text=str(day),
            callback_data=f"select_date_{date.strftime('%Y-%m-%d')}"
        )
    
    # Navigation
    prev_month = (first_day - timedelta(days=1)).replace(day=1)
    next_month = (first_day + timedelta(days=32)).replace(day=1)
    
    builder.button(
        text="⬅️",
        callback_data=f"change_month_{prev_month.strftime('%Y-%m')}"
    )
    builder.button(
        text="➡️",
        callback_data=f"change_month_{next_month.strftime('%Y-%m')}"
    )
    
    builder.adjust(7, 7, *[7 for _ in range(5)], 2)
    return builder.as_markup()

def confirm_delete_kb(item_id, item_type="wp", has_bookings=False):
    builder = InlineKeyboardBuilder()
    if has_bookings:
        builder.button(
            text="✅ Да, удалить с бронированиями",
            callback_data=f"confirm_{item_type}_force_delete_{item_id}"
        )
    else:
        builder.button(
            text="✅ Да",
            callback_data=f"confirm_{item_type}_delete_{item_id}"
        )
    builder.button(
        text="❌ Нет",
        callback_data=f"cancel_{item_type}_delete"
    )
    builder.adjust(1)
    return builder.as_markup()

def admin_management_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить админа", callback_data="add_admin")
    builder.button(text="➖ Удалить админа", callback_data="remove_admin")
    builder.button(text="📋 Список админов", callback_data="list_admins")
    builder.adjust(1)
    return builder.as_markup()
