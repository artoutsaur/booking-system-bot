from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from database import Database

db = Database()

def generate_workplace_calendar(selected_date=None, workplace_id=None):
    """Генерирует календарь с учетом workplace_id"""
    # Обработка входной даты
    if isinstance(selected_date, str):
        try:
            # Для строк формата "YYYY-MM" добавляем первый день месяца
            if len(selected_date) == 7:  # Формат "YYYY-MM"
                selected_date = datetime.strptime(selected_date + "-01", "%Y-%m-%d").date()
            else:
                selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            selected_date = datetime.now().date()
    elif not selected_date:
        selected_date = datetime.now().date()
    
    today = datetime.now().date()
    builder = InlineKeyboardBuilder()
    
    # Получаем забронированные даты
    booked_dates = []
    if workplace_id is not None:
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT start_date, end_date 
                FROM bookings 
                WHERE workplace_id = %s
            """, (workplace_id,))
            booked_dates = cur.fetchall()
    
    # Заголовок с навигацией
    month_name = selected_date.strftime("%B %Y")
    prev_month = (selected_date.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (selected_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"change_month_{prev_month.strftime('%Y-%m')}"),
        InlineKeyboardButton(text=month_name, callback_data="ignore"),
        InlineKeyboardButton(text="➡️", callback_data=f"change_month_{next_month.strftime('%Y-%m')}"),
        width=3
    )
    
    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in week_days:
        builder.add(InlineKeyboardButton(text=day, callback_data="ignore"))
    
    # Пустые клетки перед первым днём месяца
    first_day = selected_date.replace(day=1)
    for _ in range(first_day.weekday()):
        builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))
    
    # Дни месяца
    # Дни месяца
    last_day = (first_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    for day in range(1, last_day.day + 1):
        current_date = first_day.replace(day=day)  # Убрали .date()
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Проверяем доступность даты
        is_booked = any(start <= current_date <= end for start, end in booked_dates)
        is_past = current_date < today
        
        if is_booked or is_past:
            builder.add(InlineKeyboardButton(text="❌", callback_data="ignore"))
        else:
            builder.add(InlineKeyboardButton(
                text=str(day),
                callback_data=f"select_date_{date_str}"
            ))
    
    builder.adjust(7, *[7 for _ in range(6)])
    return builder.as_markup()