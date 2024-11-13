import sqlite3
import random
from datetime import datetime, timedelta
import names  # pip install names

# Подключение к базе данных
conn = sqlite3.connect('transport_expenses.db')
cursor = conn.cursor()

# Очистка существующих данных
cursor.execute('DELETE FROM route_executions')
cursor.execute('DELETE FROM routes')
cursor.execute('DELETE FROM expenses')
cursor.execute('DELETE FROM drivers')

# Константы для генерации данных
DRIVERS_COUNT = 10
ROUTES_COUNT = 20
EXECUTIONS_PER_ROUTE = 15
EXPENSES_PER_DRIVER = 100

CITIES = [
    "Алматы", "Астана", "Шымкент", "Караганда", "Актобе", 
    "Тараз", "Павлодар", "Усть-Каменогорск", "Семей", "Атырау",
    "Костанай", "Кызылорда", "Актау", "Петропавловск", "Талдыкорган"
]

CARGO_TYPES = [
    "Продукты питания", "Стройматериалы", "Техника", 
    "Мебель", "Одежда", "Автозапчасти", "Топливо",
    "Медикаменты", "Химикаты", "Металлопрокат"
]

EXPENSE_TYPES = {
    "fuel": (20000, 50000, "Заправка"),
    "oil": (15000, 35000, "Замена масла"),
    "tires": (80000, 150000, "Новые шины"),
    "repair": (30000, 100000, "Ремонт"),
    "food": (5000, 15000, "Питание"),
    "parking": (2000, 5000, "Парковка")
}

# Генерация водителей
print("Генерация водителей...")
drivers = []
for i in range(DRIVERS_COUNT):
    telegram_id = random.randint(100000000, 999999999)
    full_name = names.get_full_name()
    phone = f"+7{random.randint(7000000000, 7999999999)}"
    created_at = datetime.now() - timedelta(days=random.randint(30, 365))
    
    cursor.execute(
        'INSERT INTO drivers (telegram_id, full_name, phone, created_at) VALUES (?, ?, ?, ?)',
        (telegram_id, full_name, phone, created_at)
    )
    drivers.append((telegram_id, full_name))

# Генерация маршрутов
print("Генерация маршрутов...")
routes = []
for i in range(ROUTES_COUNT):
    start_point = random.choice(CITIES)
    end_point = random.choice([city for city in CITIES if city != start_point])
    route_name = f"Маршрут {start_point}-{end_point}"
    distance = random.randint(300, 2000)
    price = distance * random.randint(500, 1000)  # Цена зависит от расстояния
    cargo_type = random.choice(CARGO_TYPES)
    created_at = datetime.now() - timedelta(days=random.randint(30, 365))
    
    cursor.execute('''
        INSERT INTO routes (route_name, start_point, end_point, distance, price, cargo_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (route_name, start_point, end_point, distance, price, cargo_type, created_at))
    routes.append(cursor.lastrowid)

# Генерация выполненных маршрутов
print("Генерация выполненных маршрутов...")
for route_id in routes:
    for _ in range(random.randint(5, EXECUTIONS_PER_ROUTE)):
        driver_id = random.choice(drivers)[0]
        start_time = datetime.now() - timedelta(days=random.randint(1, 365))
        # Время в пути зависит от расстояния
        cursor.execute('SELECT distance FROM routes WHERE id = ?', (route_id,))
        distance = cursor.fetchone()[0]
        travel_hours = distance / random.randint(50, 70)  # Средняя скорость 50-70 км/ч
        end_time = start_time + timedelta(hours=travel_hours)
        
        cursor.execute('''
            INSERT INTO route_executions (route_id, driver_id, start_time, end_time, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (route_id, driver_id, start_time, end_time, 'completed'))

# Генерация расходов
print("Генерация расходов...")
for driver_id, _ in drivers:
    for _ in range(EXPENSES_PER_DRIVER):
        expense_type = random.choice(list(EXPENSE_TYPES.keys()))
        min_amount, max_amount, comment_template = EXPENSE_TYPES[expense_type]
        amount = random.randint(min_amount, max_amount)
        
        # Генерация случайного комментария
        comment = f"{comment_template} - {random.choice(['Плановый', 'Внеплановый', 'Срочный'])}"
        created_at = datetime.now() - timedelta(days=random.randint(1, 365))
        
        cursor.execute('''
            INSERT INTO expenses (driver_id, expense_type, amount, receipt_photo, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (driver_id, expense_type, amount, 'test_receipt.jpg', comment, created_at))

# Сохранение изменений
conn.commit()
conn.close()

print("Генерация тестовых данных завершена!") 