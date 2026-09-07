from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta
from calendars import generate_workplace_calendar
from config import TELEGRAM_TOKEN
from database import Database
from keyboards import *
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot=bot, storage=MemoryStorage())

class BookingStates(StatesGroup):
    CHOOSE_WORKPLACE = State()
    CHOOSE_DATE = State()
    CHOOSE_DURATION = State()

class AdminStates(StatesGroup):
    ADD_WORKPLACE = State()
    DELETE_WORKPLACE = State()
    ADD_ADMIN = State()
    REMOVE_ADMIN = State()
    CANCEL_BOOKING = State()

async def return_to_menu(message: types.Message):
    """Возвращает пользователя в соответствующее меню"""
    if db.is_super_admin(message.from_user.id):
        await message.answer("Выберите действие:", reply_markup=get_super_admin_menu())
    elif db.is_admin(message.from_user.id):
        await message.answer("Выберите действие:", reply_markup=get_admin_menu())
    else:
        await message.answer("Выберите действие:", reply_markup=get_user_menu())

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    if not db.get_user(user_id):
        is_first = db.is_first_user()
        db.add_user(user_id, username, is_admin=is_first, is_super_admin=is_first)
    else:
        # Обновляем username при каждом старте на случай, если он изменился
        db.add_user(user_id, username)
    
    await return_to_menu(message)
    db.log_action(user_id, "Запуск бота")

@dp.message(lambda message: message.text == "🖥️ Забронировать место")
async def book_workplace(message: types.Message, state: FSMContext):
    workplaces = db.get_workplaces()
    if not workplaces:
        await message.answer("Нет доступных рабочих мест.")
        return
    
    await message.answer(
        "Выберите рабочее место:",
        reply_markup=generate_workplaces_kb(workplaces)
    )
    await state.set_state(BookingStates.CHOOSE_WORKPLACE)
    db.log_action(message.from_user.id, "Начало бронирования")

@dp.callback_query(BookingStates.CHOOSE_WORKPLACE)
async def process_workplace_selection(callback: types.CallbackQuery, state: FSMContext):
    if callback.data.startswith('select_wp_'):
        wp_id = int(callback.data.split('_')[2])
        await state.update_data(workplace_id=wp_id)
        
        await callback.message.answer(
            "Выберите дату начала бронирования:",
            reply_markup=generate_workplace_calendar(workplace_id=wp_id)
        )
        await state.set_state(BookingStates.CHOOSE_DATE)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('change_month_'))
async def change_month_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    workplace_id = data.get('workplace_id')
    month_str = callback.data.split('_')[2]  # Получаем строку вида "YYYY-MM"
    
    await callback.message.edit_reply_markup(
        reply_markup=generate_workplace_calendar(month_str, workplace_id)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('select_date_'), BookingStates.CHOOSE_DATE)
async def process_date_selection(callback: types.CallbackQuery, state: FSMContext):
    date_str = callback.data.split('_')[2]
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    
    if selected_date < today:
        await callback.answer("❌ Нельзя выбрать прошедшую дату", show_alert=True)
        return
    
    await state.update_data(start_date=date_str)
    await callback.message.answer(
        "Введите количество дней бронирования (от 1 до 5):",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(BookingStates.CHOOSE_DURATION)
    await callback.answer()

@dp.message(BookingStates.CHOOSE_DURATION)
async def choose_duration(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await return_to_menu(message)
        return
    
    try:
        days = int(message.text)
        if not 1 <= days <= 5:
            await message.answer("Введите число от 1 до 5")
            return
        
        data = await state.get_data()
        start_date = datetime.strptime(data['start_date'], "%Y-%m-%d").date()
        end_date = start_date + timedelta(days=days)
        
        booking_id = db.create_booking(
            user_id=message.from_user.id,
            workplace_id=data['workplace_id'],
            start_date=start_date,
            end_date=end_date
        )
        
        if booking_id:
            workplace = next(wp for wp in db.get_workplaces() if wp[0] == data['workplace_id'])
            await message.answer(
                f"✅ Бронирование #{booking_id} успешно создано!\n"
                f"🖥️ Место: {workplace[1]}\n"
                f"📅 Даты: {start_date} → {end_date}"
            )
            db.log_action(message.from_user.id, f"Создано бронирование ID: {booking_id}")
        else:
            await message.answer("❌ Место уже забронировано на эти даты")
        
        await state.clear()
        await return_to_menu(message)
    except ValueError:
        await message.answer("Введите корректное число дней (от 1 до 5)")

@dp.message(lambda message: message.text == "📋 Мои бронирования")
async def my_bookings(message: types.Message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer("У вас нет активных бронирований.")
    else:
        response = "📋 Ваши бронирования:\n\n"
        for booking in bookings:
            response += f"🆔 {booking[0]} | 🖥️ {booking[1]}\n"
            response += f"📅 {booking[2]} → {booking[3]}\n\n"
        await message.answer(response)
    
    await return_to_menu(message)
    db.log_action(message.from_user.id, "Просмотр своих бронирований")

@dp.message(lambda message: message.text == "📋 Все брони")
async def all_bookings(message: types.Message):
    if not (db.is_admin(message.from_user.id) or db.is_super_admin(message.from_user.id)):
        await message.answer("❌ Доступ запрещен")
        return
    
    bookings = db.get_all_bookings()
    if not bookings:
        await message.answer("Нет активных бронирований.")
    else:
        response = "📋 Все бронирования:\n\n"
        for booking in bookings:
            user_info = f"{booking[1]}" if booking[1] else f"ID: {booking[0]}"
            response += f"🆔 {booking[0]} | 👤 {user_info} | 🖥️ @{booking[2]}\n"
            response += f"📅 {booking[3]} → {booking[4]}\n\n"
        await message.answer(response)
    
    await return_to_menu(message)
    db.log_action(message.from_user.id, "Просмотр всех бронирований")

@dp.message(lambda message: message.text == "❌ Отменить бронь")
async def cancel_booking_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin = db.is_admin(user_id) or db.is_super_admin(user_id)
    
    bookings = db.get_all_bookings() if is_admin else db.get_user_bookings(user_id)
    
    if not bookings:
        await message.answer("Нет бронирований для отмены.")
    else:
        await message.answer(
            "Выберите бронирование для отмены:",
            reply_markup=generate_bookings_kb(bookings, is_admin)
        )
        await state.set_state(AdminStates.CANCEL_BOOKING)
    
    db.log_action(user_id, "Начало отмены бронирования")

@dp.callback_query(lambda c: c.data.startswith('cancel_wp_delete'))
async def cancel_delete_workplace(callback: types.CallbackQuery):
    workplaces = db.get_workplaces()
    await callback.message.edit_text(
        "Выберите место для удаления:",
        reply_markup=generate_workplaces_kb(workplaces, "delete")
    )
    await callback.answer()

@dp.callback_query(AdminStates.CANCEL_BOOKING)
async def process_cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    if callback.data.startswith('cancel_'):
        booking_id = int(callback.data.split('_')[1])
        user_id = callback.from_user.id
        is_admin = db.is_admin(user_id) or db.is_super_admin(user_id)
        
        if db.cancel_booking(booking_id, user_id, is_admin):
            await callback.message.edit_text(f"✅ Бронирование #{booking_id} отменено")
            db.log_action(user_id, f"Отменено бронирование ID: {booking_id}")
        else:
            await callback.message.edit_text("❌ Не удалось отменить бронирование")
        
        await state.clear()
    await callback.answer()

@dp.message(lambda message: message.text == "➕ Добавить место")
async def add_workplace_start(message: types.Message, state: FSMContext):
    if not (db.is_admin(message.from_user.id) or db.is_super_admin(message.from_user.id)):
        await message.answer("❌ Доступ запрещен")
        return
    
    await message.answer(
        "Введите название нового рабочего места:",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(AdminStates.ADD_WORKPLACE)
    db.log_action(message.from_user.id, "Начало добавления рабочего места")

@dp.message(AdminStates.ADD_WORKPLACE)
async def process_add_workplace(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await return_to_menu(message)
        return
    
    workplace_id = db.add_workplace(message.text)
    if workplace_id:
        await message.answer(f"✅ Рабочее место '{message.text}' добавлено (ID: {workplace_id})")
    else:
        await message.answer("❌ Ошибка при добавлении рабочего места")
    
    await state.clear()
    await return_to_menu(message)

@dp.message(lambda message: message.text == "➖ Удалить место")
async def delete_workplace_start(message: types.Message):
    if not (db.is_admin(message.from_user.id) or db.is_super_admin(message.from_user.id)):
        await message.answer("❌ Доступ запрещен")
        return
    
    workplaces = db.get_workplaces()
    if not workplaces:
        await message.answer("Нет рабочих мест для удаления.")
    else:
        await message.answer(
            "Выберите место для удаления:",
            reply_markup=generate_workplaces_kb(workplaces, "delete")
        )
    
    db.log_action(message.from_user.id, "Начало удаления рабочего места")

@dp.callback_query(lambda c: c.data.startswith('delete_wp_'))
async def ask_confirm_delete(callback: types.CallbackQuery):
    wp_id = int(callback.data.split('_')[2])  # Оставляем индекс 2 для начального запроса
    workplace = next(wp for wp in db.get_workplaces() if wp[0] == wp_id)
    has_bookings = db.has_bookings_for_workplace(wp_id)
    
    if has_bookings:
        await callback.message.edit_text(
            f"⚠️ На рабочее место '{workplace[1]}' есть бронирования.\n"
            "Вы уверены, что хотите удалить его вместе со всеми бронированиями?",
            reply_markup=confirm_delete_kb(wp_id, "wp", has_bookings=True)
        )
    else:
        await callback.message.edit_text(
            f"Вы уверены, что хотите удалить рабочее место '{workplace[1]}'?",
            reply_markup=confirm_delete_kb(wp_id, "wp")
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('confirm_wp_delete_'))
async def process_delete_workplace(callback: types.CallbackQuery):
    try:
        # Аналогично изменяем индекс с 3 на 4
        wp_id = int(callback.data.split('_')[4])
        workplace_name = db.delete_workplace(wp_id, force=False)
        if workplace_name:
            await callback.message.edit_text(f"✅ Рабочее место '{workplace_name}' удалено")
            db.log_action(callback.from_user.id, f"Удалено рабочее место ID: {wp_id}")
        else:
            await callback.message.edit_text(
                "❌ Не удалось удалить рабочее место. Возможно, на него есть бронирования.\n"
                "Попробуйте удалить его вместе с бронированиями."
            )
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка обработки callback_data: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при обработке запроса")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('confirm_wp_force_delete_'))
async def process_force_delete_workplace(callback: types.CallbackQuery):
    try:
        # Изменяем индекс с 3 на 4, так как теперь в callback_data больше частей
        wp_id = int(callback.data.split('_')[4])
        workplace_name = db.delete_workplace(wp_id, force=True)
        if workplace_name:
            await callback.message.edit_text(
                f"✅ Рабочее место '{workplace_name}' и все связанные бронирования удалены"
            )
            db.log_action(callback.from_user.id, f"Удалено рабочее место ID: {wp_id} с бронированиями")
        else:
            await callback.message.edit_text("❌ Ошибка при удалении рабочего места")
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка обработки callback_data: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при обработке запроса")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('cancel_wp_delete'))
async def cancel_delete_workplace(callback: types.CallbackQuery):
    workplaces = db.get_workplaces()
    await callback.message.edit_text(
        "Выберите место для удаления:",
        reply_markup=generate_workplaces_kb(workplaces, "delete")
    )
    await callback.answer()

@dp.message(lambda message: message.text == "👥 Управление админами")
async def manage_admins(message: types.Message):
    if not db.is_super_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    
    await message.answer(
        "Управление администраторами:",
        reply_markup=admin_management_kb()
    )
    db.log_action(message.from_user.id, "Просмотр управления админами")

@dp.callback_query(lambda c: c.data == "add_admin")
async def add_admin_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите ID пользователя для назначения администратором:",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(AdminStates.ADD_ADMIN)
    await callback.answer()

@dp.message(AdminStates.ADD_ADMIN)
async def process_add_admin(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await return_to_menu(message)
        return
    
    try:
        new_admin_id = int(message.text)
        if db.add_admin(new_admin_id):
            await message.answer(f"✅ Пользователь {new_admin_id} назначен администратором")
        else:
            await message.answer("❌ Ошибка при назначении администратора")
    except ValueError:
        await message.answer("Введите корректный ID пользователя (только цифры)")
    
    await state.clear()
    await return_to_menu(message)

@dp.callback_query(lambda c: c.data == "list_admins")
async def list_admins(callback: types.CallbackQuery):
    admins = db.get_admins()
    logger.info(f"Admins data: {admins}")
    if not admins:
        await callback.message.edit_text("Список администраторов пуст")
        await callback.answer()
        return
    
    response = "👥 Список администраторов:\n\n"
    for admin in admins:
        admin_id = admin[0]
        username = admin[1] if admin[1] else "нет username"
        is_super = admin[2]
        
        status = "👑 Супер-админ" if is_super else "🔧 Админ"
        response += f"🆔 {admin_id} (@{username}) - {status}\n"
    
    await callback.message.edit_text(response)
    await callback.answer()

@dp.message(lambda message: message.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    if not (db.is_admin(message.from_user.id) or db.is_super_admin(message.from_user.id)):
        await message.answer("❌ Доступ запрещен")
        return
    
    stats = db.get_statistics()
    if not stats:
        await message.answer("Не удалось получить статистику")
    else:
        response = "📊 Статистика бронирований:\n\n"
        response += f"• Всего бронирований: {stats['total_bookings']}\n"
        response += f"• Уникальных пользователей: {stats['unique_users']}\n\n"
        response += "🏆 Популярные рабочие места:\n"
        
        for i, (name, count) in enumerate(stats['popular_workplaces'], 1):
            response += f"{i}. {name}: {count} бронирований\n"
        
        await message.answer(response)
    
    await return_to_menu(message)
    db.log_action(message.from_user.id, "Просмотр статистики")

@dp.callback_query(lambda c: c.data == "remove_admin")
async def remove_admin_start(callback: types.CallbackQuery):
    """Обработчик кнопки удаления администратора"""
    if not db.is_super_admin(callback.from_user.id):
        await callback.answer("❌ Только супер-админ может удалять администраторов", show_alert=True)
        return
    
    admins = db.get_admins()
    if not admins:
        await callback.message.edit_text("Нет администраторов для удаления")
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for admin in admins:
        admin_id = admin[0]
        username = admin[1] if admin[1] else "нет username"
        is_super = admin[2]
        
        if admin_id != callback.from_user.id:  # Нельзя удалить себя
            status = "👑 Супер-админ" if is_super else "🔧 Админ"
            builder.button(
                text=f"ID {admin_id} (@{username}) - {status}",
                callback_data=f"remove_admin_{admin_id}"
            )
    builder.adjust(1)
    
    await callback.message.edit_text(
        "Выберите администратора для удаления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('remove_admin_'))
async def process_remove_admin(callback: types.CallbackQuery):
    """Обработчик подтверждения удаления администратора"""
    if not db.is_super_admin(callback.from_user.id):
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    admin_id = int(callback.data.split('_')[2])
    
    if admin_id == callback.from_user.id:
        await callback.answer("❌ Нельзя удалить самого себя", show_alert=True)
        return
    
    if db.remove_admin(admin_id):
        await callback.message.edit_text(f"✅ Пользователь {admin_id} больше не администратор")
        db.log_action(callback.from_user.id, f"Удален администратор: {admin_id}")
    else:
        await callback.message.edit_text("❌ Не удалось удалить администратора")
    
    await callback.answer()  

@dp.message(lambda message: message.text == "🔙 В главное меню")
async def back_to_main_menu(message: types.Message):
    await return_to_menu(message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())