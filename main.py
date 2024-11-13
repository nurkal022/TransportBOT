import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database import Database
from keyboards import get_main_keyboard, get_expense_types_keyboard, get_expense_list_keyboard, get_receipt_button, get_routes_keyboard, get_route_details_keyboard, get_route_history_keyboard
from datetime import datetime
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Инициализация логгера
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher()

# Инициализация базы данных
db = Database("transport_expenses.db")

# Определение состояний FSM
class ExpenseStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()
    waiting_for_comment = State()

# Добавьте новый класс состояний для регистрации
class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    with db as database:
        if not database.driver_exists(message.from_user.id):
            await message.answer(
                "Добро пожаловать! Для начала работы, пожалуйста, отправьте свое полное имя."
            )
            await state.set_state(RegistrationStates.waiting_for_name)
        else:
            await message.answer(
                "Выберите действие:",
                reply_markup=get_main_keyboard()
            )

# Добавьте новые обработчики для регистрации
@dp.message(StateFilter(RegistrationStates.waiting_for_name))
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer(
        "Пожалуйста, отправьте ваш номер телефона в формате +7XXXXXXXXXX"
    )
    await state.set_state(RegistrationStates.waiting_for_phone)

@dp.message(StateFilter(RegistrationStates.waiting_for_phone))
async def process_phone(message: Message, state: FSMContext):
    phone = message.text
    user_data = await state.get_data()
    
    with db as database:
        # Сохраняем водителя в базу данных
        database.add_driver(
            telegram_id=message.from_user.id,
            full_name=user_data['full_name'],
            phone=phone
        )
    
    await message.answer(
        "Регистрация успешно завершена! Теперь вы можете пользоваться ботом.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

# Обработчик кнопки "Добавить расход"
@dp.message(F.text == "📝 Добавить расход")
async def add_expense(message: Message):
    await message.answer(
        "Выберите тип расхода:",
        reply_markup=get_expense_types_keyboard()
    )

# Добавляем команду отмены в клавиатуру
@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer(
        "Действие отменено. Выберите действие:",
        reply_markup=get_main_keyboard()
    )

# Обновляем обработчик выбора типа расхода
@dp.callback_query(F.data.startswith("expense_"))
async def process_expense_type(callback: CallbackQuery, state: FSMContext):
    expense_type = callback.data.split("_")[1]
    await state.update_data(expense_type=expense_type)
    
    await callback.message.edit_text(
        "Введите сумму расхода (в тенге):\n"
        "Для отмены операции напишите 'Отмена'"
    )
    await state.set_state(ExpenseStates.waiting_for_amount)

# Обновляем обработчик ввода суммы
@dp.message(StateFilter(ExpenseStates.waiting_for_amount))
async def process_amount(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer(
            "Действие отменено. Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        return

    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля. Попробуйте еще раз.")
            return
        
        await state.update_data(amount=amount)
        await message.answer(
            "Пожалуйста, отправьте фото чека:\n"
            "Для отмены операции напишите 'Отмена'"
        )
        await state.set_state(ExpenseStates.waiting_for_receipt)
    except ValueError:
        await message.answer(
            "Пожалуйста, введите корректную сумму числом.\n"
            "Например: 5000"
        )

# Обновляем обработчик получения фото чека
@dp.message(StateFilter(ExpenseStates.waiting_for_receipt))
async def process_receipt(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer(
            "Действие отменено. Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        return

    if not message.photo:
        await message.answer(
            "Пожалуйста, отправьте фото чека.\n"
            "Для отмены операции напишите 'Отмена'"
        )
        return

    photo = message.photo[-1]
    await state.update_data(receipt_photo=photo.file_id)
    
    await message.answer(
        "Добавьте комментарий к расходу:\n"
        "Для отмены операции напишите 'Отмена'"
    )
    await state.set_state(ExpenseStates.waiting_for_comment)

# Обновляем обработчик получения комментария
@dp.message(StateFilter(ExpenseStates.waiting_for_comment))
async def process_comment(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer(
            "Действие отменено. Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        return

    user_data = await state.get_data()
    
    # Сохраняем расход в базу данных
    active_route = db.get_active_route(message.from_user.id)
    route_execution_id = active_route[0] if active_route else None
    
    db.add_expense(
        driver_id=message.from_user.id,
        expense_type=user_data['expense_type'],
        amount=user_data['amount'],
        receipt_photo=user_data['receipt_photo'],
        comment=message.text,
        route_execution_id=route_execution_id
    )
    
    await state.clear()
    await message.answer(
        "✅ Расход успешно добавлен!",
        reply_markup=get_main_keyboard()
    )

# Добавляем обработчик для просмотра расходов
@dp.message(F.text == "📊 Мои расходы")
async def show_expenses(message: Message):
    expenses = db.get_driver_expenses(message.from_user.id)
    
    if not expenses:
        await message.answer(
            "У вас пока нет зарегистрированных расходов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    total_amount = sum(expense['amount'] for expense in expenses)
    formatted_total = "{:,}".format(int(total_amount)).replace(",", " ")
    
    expense_list = []
    for expense in expenses:
        formatted_amount = "{:,}".format(int(expense['amount'])).replace(",", " ")
        formatted_date = expense['date'].strftime("%d.%m.%Y %H:%M")
        
        expense_text = (
            f"💰 {formatted_amount} тг - {expense['type']}\n"
            f"📅 {formatted_date}\n"
            f"🚛 {expense['route']}\n"
            f"💭 {expense['comment'] if expense['comment'] else 'Без комментария'}\n"
        )
        expense_list.append(expense_text)
    
    await message.answer(
        f"📊 Ваши расходы:\n\n"
        f"{'—' * 30}\n"
        f"{('—' * 30 + '\n').join(expense_list)}"
        f"{'—' * 30}\n"
        f"Общая сумма: {formatted_total} тг",
        reply_markup=get_expense_list_keyboard(expenses)
    )

# Добавляем обработчик нажатия на расход
@dp.callback_query(F.data.startswith("show_expense_"))
async def show_expense_details(callback: CallbackQuery):
    expense_date = callback.data.replace("show_expense_", "")
    expense = db.get_expense_by_date(callback.from_user.id, expense_date)
    
    if not expense:
        await callback.answer("Информация о расходе не найдена")
        return
    
    exp_type, amount, receipt_photo, comment, date_str = expense
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
        formatted_date = date.strftime("%d.%m.%Y %H:%M")
    except:
        formatted_date = date_str
        
    try:
        formatted_amount = "{:,}".format(int(float(amount))).replace(",", " ")
    except (ValueError, TypeError):
        formatted_amount = str(amount)
    
    response = (
        f"📅 Дата: {formatted_date}\n"
        f"📋 Тип: {exp_type}\n"
        f"💰 Сумма: {formatted_amount} тенге\n"
        f"💬 Комментарий: {comment if comment else 'Без комментария'}"
    )
    
    await callback.message.edit_text(
        response,
        reply_markup=get_receipt_button(expense_date)
    )

# Добавляем обработчик кнопки показа чека
@dp.callback_query(F.data.startswith("show_receipt_"))
async def show_receipt(callback: CallbackQuery):
    expense_date = callback.data.replace("show_receipt_", "")
    expense = db.get_expense_by_date(callback.from_user.id, expense_date)
    
    if not expense:
        await callback.answer("Чек не найден")
        return
    
    _, _, receipt_photo, _, _ = expense
    
    if receipt_photo:
        try:
            await callback.message.answer_photo(
                receipt_photo,
                caption="🧾 Фото чека"
            )
            await callback.answer()
        except Exception as e:
            logging.error(f"Error sending receipt photo: {e}")
            await callback.answer("Не удалось загрузить фото чека")
    else:
        await callback.answer("Чек отсутствует")

# Добавляем обработчик для маршрутов
@dp.message(F.text == "🚛 Мои маршруты")
async def show_routes(message: Message):
    active_route = db.get_active_route(message.from_user.id)
    
    if active_route:
        route_id, name, start, end, start_time = active_route
        try:
            # start_time уже является объектом datetime после преобразования в get_active_route
            formatted_time = start_time.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_time = str(start_time)  # Fallback если что-то пошло не так
        
        await message.answer(
            f"🚛 У вас есть активный маршрут:\n\n"
            f"Маршрут: {name}\n"
            f"Откуда: {start}\n"
            f"Куда: {end}\n"
            f"Начало: {formatted_time}\n\n"
            f"Нажмите кнопку ниже, чтобы завершить маршрут:",
            reply_markup=get_routes_keyboard([], active_route=True)
        )
        return
    
    routes = db.get_available_routes()
    if not routes:
        await message.answer(
            "На данный момент нет доступных маршрутов.\n"
            "Нажмите '➕ Добавить тестовый маршрут' для создания тестового маршрута.",
            reply_markup=get_main_keyboard()
        )
        return
    
    await message.answer(
        "📋 Доступные маршруты:",
        reply_markup=get_routes_keyboard(routes)
    )

# Обработчик выбора маршрута для показа деталей
@dp.callback_query(F.data.startswith("route_"))
async def show_route_details(callback: CallbackQuery):
    route_id = int(callback.data.replace("route_", ""))
    route = db.get_route_details(route_id)
    
    if not route:
        await callback.answer("Маршрут не найден")
        return
    
    try:
        price = float(route['price'])
        formatted_price = "{:,}".format(int(price)).replace(",", " ")
    except (ValueError, TypeError):
        formatted_price = str(route['price'])
    
    await callback.message.edit_text(
        f"🚛 Информация о маршруте:\n\n"
        f"📍 Маршрут: {route['name']}\n"
        f"🏁 Откуда: {route['start']}\n"
        f"🏁 Куда: {route['end']}\n"
        f"📏 Расстояние: {route['distance']} км\n"
        f"💰 Стоимость: {formatted_price} тенге\n"
        f"📦 Груз: {route['cargo']}\n\n"
        f"Нажмите кнопку ниже, чтобы начать маршрут:",
        reply_markup=get_route_details_keyboard(route_id)
    )

# Обработчик начала маршрута
@dp.callback_query(F.data.startswith("start_route_"))
async def start_route(callback: CallbackQuery):
    route_id = int(callback.data.replace("start_route_", ""))
    
    # Проверяем, нет ли уже активного маршрута
    active_route = db.get_active_route(callback.from_user.id)
    if active_route:
        await callback.answer("У вас уже есть активный маршрут!")
        return
    
    try:
        db.start_route(callback.from_user.id, route_id)
        route = db.get_route_details(route_id)
        
        await callback.message.edit_text(
            f"✅ Маршрут успешно начат!\n\n"
            f"📍 Маршрут: {route['name']}\n"
            f"🏁 Откуда: {route['start']}\n"
            f"🏁 Куда: {route['end']}\n",
            reply_markup=get_routes_keyboard([], active_route=True)
        )
        await callback.answer("Маршрут начат")
    except Exception as e:
        logging.error(f"Error starting route: {e}")
        await callback.answer("Произошла ошибка при начале маршрута")

# Добавляем обработчик для возврата к списку маршрутов
@dp.callback_query(F.data == "back_to_routes")
async def back_to_routes(callback: CallbackQuery):
    routes = db.get_available_routes()
    await callback.message.edit_text(
        "📋 Доступные маршруты:",
        reply_markup=get_routes_keyboard(routes)
    )

# Добавляем обработчик для создания тестового маршрута
@dp.message(F.text == "➕ Добавить тестовый маршрут")
async def add_test_route(message: Message):
    route_id = db.add_test_route()
    await message.answer(
        "✅ Тестовый маршрут упешно добавлен!",
        reply_markup=get_main_keyboard()
    )

# Добавляем обработчик для завершения маршрута
@dp.callback_query(F.data == "finish_route")
async def finish_active_route(callback: CallbackQuery):
    active_route = db.get_active_route(callback.from_user.id)
    if not active_route:
        await callback.answer("У вас нет активного маршрута")
        return
    
    route_id = active_route[0]  # Получаем ID маршрута
    try:
        db.finish_route(callback.from_user.id, route_id)
        # Сначала редактируем сообщение с инлайн клавиатурой
        await callback.message.edit_text(
            "✅ Маршрут успешно завершен!",
            reply_markup=None  # Убираем инлайн клавиатуру
        )
        # Затем отправляем новое сообщение с обычной клавиатурой
        await callback.message.answer(
            "Вы можете:\n"
            "- Начать новый маршрут, нажав '🚛 Мои маршруты'\n"
            "- Посмотреть завершенные маршруты, нажав '📜 История маршрутов'",
            reply_markup=get_main_keyboard()
        )
        await callback.answer("Маршрут завершен")
    except Exception as e:
        logging.error(f"Error finishing route: {e}")
        await callback.answer("Произошла ошибка при завершении маршрута")

# Обработчик для истории маршрутов
@dp.message(F.text == "📜 История маршрутов")
async def show_route_history(message: Message):
    completed_routes = db.get_completed_routes(message.from_user.id)
    
    if not completed_routes:
        await message.answer(
            "У вас пока нет завершенных маршрутов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    await message.answer(
        "📜 История завершенных маршрутов:",
        reply_markup=get_route_history_keyboard(completed_routes)
    )

# Добавляем обработчик для просмотра деталей завершенного маршрута
@dp.callback_query(F.data.startswith("history_route_"))
async def show_completed_route_details(callback: CallbackQuery):
    route_id = int(callback.data.replace("history_route_", ""))
    route = db.get_route_details(route_id)
    
    if not route:
        await callback.answer("Маршрут не найден")
        return
    
    try:
        # Преобразуем цену в число и форматируем
        price = float(route[4]) if isinstance(route, tuple) else float(route['price'])
        formatted_price = "{:,}".format(int(price)).replace(",", " ")
    except (ValueError, TypeError, IndexError, KeyError):
        # Если преобразование не удалось, используем исходное значение
        formatted_price = str(route[4] if isinstance(route, tuple) else route['price'])
    
    # Получаем остальные данные в зависимости от формата
    if isinstance(route, tuple):
        name, start, end, distance, _, cargo = route
    else:
        name = route['name']
        start = route['start']
        end = route['end']
        distance = route['distance']
        cargo = route['cargo']
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад к истории", callback_data="back_to_history")]
        ]
    )
    
    await callback.message.edit_text(
        f"📜 Информация о завершенном маршруте:\n\n"
        f"📍 Маршрут: {name}\n"
        f"🏁 Откуда: {start}\n"
        f"🏁 Куда: {end}\n"
        f"📏 Расстояние: {distance} км\n"
        f"💰 Стоимость: {formatted_price} тенге\n"
        f"📦 Груз: {cargo}\n",
        reply_markup=keyboard
    )

# Добавляем обработчик для возврата к истории маршрутов
@dp.callback_query(F.data == "back_to_history")
async def back_to_history(callback: CallbackQuery):
    completed_routes = db.get_completed_routes(callback.from_user.id)
    if not completed_routes:
        await callback.message.edit_text(
            "У вас пока нет завершенных маршрутов.",
            reply_markup=None
        )
        return
        
    await callback.message.edit_text(
        "📜 История завершенных маршрутов:",
        reply_markup=get_route_history_keyboard(completed_routes)
    )

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 