from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Добавить расход")],
            [KeyboardButton(text="📊 Мои расходы")],
            [KeyboardButton(text="🚛 Мои маршруты")],
            [KeyboardButton(text="📜 История маршрутов")],
            [KeyboardButton(text="➕ Добавить тестовый маршрут")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_expense_types_keyboard():
    builder = InlineKeyboardBuilder()
    expenses = [
        ("Бензин", "fuel"),
        ("Масло", "oil"),
        ("Шины", "tires")
    ]
    
    for expense_name, callback_data in expenses:
        builder.add(InlineKeyboardButton(
            text=expense_name,
            callback_data=f"expense_{callback_data}"
        ))
    
    builder.adjust(1)
    return builder.as_markup()

def get_expense_list_keyboard(expenses):
    """Создает инлайн клавиатуру со списком расходов"""
    keyboard = InlineKeyboardBuilder()
    
    for expense in expenses:
        # Используем словарь из get_driver_expenses
        formatted_date = expense['date'].strftime("%d.%m.%Y")
        formatted_amount = "{:,}".format(int(expense['amount'])).replace(",", " ")
            
        # Создаем текст кнопки
        button_text = f"{formatted_date} | {expense['type']} | {formatted_amount} ₸"
        # Создаем callback_data с датой
        callback_data = f"show_expense_{expense['date'].strftime('%Y-%m-%d %H:%M:%S.%f')}"
        
        keyboard.add(InlineKeyboardButton(
            text=button_text,
            callback_data=callback_data
        ))
    
    keyboard.adjust(1)  # Размещаем кнопки в один столбец
    return keyboard.as_markup()

def get_receipt_button(expense_date):
    """Создает кнопку для просмотра чека"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="📸 Показать чек",
        callback_data=f"show_receipt_{expense_date}"
    ))
    return keyboard.as_markup()

def get_routes_keyboard(routes, active_route=None):
    """Создает клавиатуру со списком маршрутов"""
    keyboard = InlineKeyboardBuilder()
    
    for route_id, name, start, end in routes:
        button_text = f"🚚 {name} ({start} → {end})"
        keyboard.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"route_{route_id}"
        ))
    
    if active_route:
        keyboard.add(InlineKeyboardButton(
            text="✅ Завершить текущий маршрут",
            callback_data="finish_route"
        ))
    
    keyboard.adjust(1)
    return keyboard.as_markup() 

def get_route_details_keyboard(route_id):
    """Создает клавиатуру для начала маршрута"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text="🚀 Начать маршрут",
        callback_data=f"start_route_{route_id}"
    ))
    keyboard.add(InlineKeyboardButton(
        text="↩️ Назад к списку",
        callback_data="back_to_routes"
    ))
    keyboard.adjust(1)
    return keyboard.as_markup() 

def get_route_history_keyboard(routes):
    """Создает клавиатуру с историей маршрутов"""
    keyboard = InlineKeyboardBuilder()
    
    for route_id, name, start, end, start_time, end_time, distance, price in routes:
        try:
            start_date = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f').strftime("%d.%m.%Y")
            end_date = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S.%f').strftime("%d.%m.%Y")
        except:
            start_date = "???"
            end_date = "???"
            
        button_text = f"🏁 {name} ({start_date} - {end_date})"
        keyboard.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"history_route_{route_id}"
        ))
    
    keyboard.adjust(1)
    return keyboard.as_markup()