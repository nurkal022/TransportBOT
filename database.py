import sqlite3
from datetime import datetime
import random
import threading

class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.connection = None
        self._lock = threading.Lock()
        self._connect()
    
    def _connect(self):
        """Установить соединение с базой данных"""
        if not self.connection:
            self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
            
            # Создаем таблицу drivers если её нет
            self._execute_query('''
                CREATE TABLE IF NOT EXISTS drivers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL
                )
            ''')
            
            # Создаем таблицу routes если её нет
            self._execute_query('''
                CREATE TABLE IF NOT EXISTS routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_name TEXT NOT NULL,
                    start_point TEXT NOT NULL,
                    end_point TEXT NOT NULL,
                    distance INTEGER NOT NULL,
                    price REAL NOT NULL,
                    cargo_type TEXT
                )
            ''')
            
            # Создаем таблицу route_executions если её нет
            self._execute_query('''
                CREATE TABLE IF NOT EXISTS route_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_id INTEGER NOT NULL,
                    driver_id INTEGER NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (route_id) REFERENCES routes (id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (id)
                )
            ''')
            
            # Создаем таблицу expenses если её нет
            self._execute_query('''
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    driver_id INTEGER NOT NULL,
                    expense_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    receipt_photo TEXT,
                    comment TEXT,
                    route_execution_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (driver_id) REFERENCES drivers (id),
                    FOREIGN KEY (route_execution_id) REFERENCES route_executions (id)
                )
            ''')
            
            self.connection.commit()
    
    def __enter__(self):
        self._connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.connection.rollback()
        else:
            self.connection.commit()
    
    def _execute_query(self, query, params=None):
        """Выполнить запрос с блокировкой"""
        with self._lock:
            self._connect()
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
    
    def driver_exists(self, telegram_id):
        """Проверить существование водителя"""
        cursor = self._execute_query(
            "SELECT COUNT(*) FROM drivers WHERE telegram_id = ?", 
            (telegram_id,)
        )
        return cursor.fetchone()[0] > 0
    
    def add_driver(self, telegram_id, full_name, phone):
        """Добавить нового водителя"""
        self._execute_query(
            "INSERT INTO drivers (telegram_id, full_name, phone) VALUES (?, ?, ?)",
            (telegram_id, full_name, phone)
        )
        self.connection.commit()
    
    def get_active_route(self, driver_id):
        """Получить активный маршрут водителя"""
        cursor = self._execute_query('''
            SELECT r.id, r.route_name, r.start_point, r.end_point, re.start_time
            FROM route_executions re
            JOIN routes r ON r.id = re.route_id
            WHERE re.driver_id = ? AND re.status = 'in_progress'
        ''', (driver_id,))
        result = cursor.fetchone()
        if result:
            route_id, name, start, end, start_time = result
            start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S.%f')
            return route_id, name, start, end, start_time
        return None
    
    def get_available_routes(self):
        """Получить список доступных маршрутов (исключая завершенные)"""
        cursor = self._execute_query('''
            SELECT r.id, r.route_name, r.start_point, r.end_point
            FROM routes r
            WHERE NOT EXISTS (
                SELECT 1 
                FROM route_executions re 
                WHERE re.route_id = r.id 
                AND re.status = 'completed'
            )
        ''')
        return cursor.fetchall()
    
    def start_route(self, driver_id, route_id):
        """Начать выполнение маршрута"""
        self._execute_query(
            'INSERT INTO route_executions (route_id, driver_id, start_time, status) VALUES (?, ?, ?, ?)',
            (route_id, driver_id, datetime.now(), 'in_progress')
        )
        self.connection.commit()
    
    def finish_route(self, driver_id, route_id):
        """Завершить маршрут"""
        self._execute_query('''
            UPDATE route_executions 
            SET status = 'completed', 
                end_time = ? 
            WHERE driver_id = ? 
            AND route_id = ? 
            AND status = 'in_progress'
        ''', (datetime.now(), driver_id, route_id))
        self.connection.commit()
    
    def get_completed_routes(self, driver_id):
        """Получить завершенные маршруты водителя"""
        cursor = self._execute_query('''
            SELECT 
                r.id,
                r.route_name,
                r.start_point,
                r.end_point,
                re.start_time,
                re.end_time,
                r.distance,
                r.price
            FROM routes r
            JOIN route_executions re ON re.route_id = r.id
            WHERE re.driver_id = ? 
            AND re.status = 'completed'
            ORDER BY re.end_time DESC
        ''', (driver_id,))
        return cursor.fetchall()
    
    def close(self):
        """Закрыть соединение с базой данных"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def get_route_details(self, route_id):
        """Получить детальную информацию о маршруте"""
        cursor = self._execute_query('''
            SELECT 
                route_name,
                start_point,
                end_point,
                distance,
                price,
                cargo_type
            FROM routes 
            WHERE id = ?
        ''', (route_id,))
        
        result = cursor.fetchone()
        if result:
            return {
                'name': result[0],
                'start': result[1],
                'end': result[2],
                'distance': result[3],
                'price': result[4],
                'cargo': result[5]
            }
        return None
    
    def add_test_route(self):
        """Добавить тестовый маршрут"""
        cursor = self._execute_query('''
            INSERT INTO routes (
                route_name, 
                start_point, 
                end_point, 
                distance, 
                price, 
                cargo_type
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            f"Маршрут {random.randint(1, 100)}",
            "Алматы",
            "Астана",
            random.randint(1000, 2000),
            random.randint(100000, 500000),
            "Общие грузы"
        ))
        self.connection.commit()
        return cursor.lastrowid
    
    def get_driver_expenses(self, driver_id):
        """Получить все расходы водителя"""
        cursor = self._execute_query('''
            SELECT 
                e.id,
                e.amount,
                e.expense_type,
                e.receipt_photo,
                e.comment,
                e.created_at,
                r.route_name
            FROM expenses e
            LEFT JOIN route_executions re ON e.route_execution_id = re.id
            LEFT JOIN routes r ON re.route_id = r.id
            WHERE e.driver_id = ?
            ORDER BY e.created_at DESC
        ''', (driver_id,))
        
        expenses = cursor.fetchall()
        result = []
        
        for expense in expenses:
            result.append({
                'id': expense[0],
                'amount': float(expense[1]),
                'type': expense[2],
                'receipt': expense[3],
                'comment': expense[4],
                'date': datetime.strptime(expense[5], '%Y-%m-%d %H:%M:%S.%f') if expense[5] else datetime.now(),
                'route': expense[6] if expense[6] else 'Без маршрута'
            })
        
        return result
    
    def add_expense(self, driver_id, expense_type, amount, receipt_photo, comment, route_execution_id=None):
        """Добавить новый расход"""
        self._execute_query('''
            INSERT INTO expenses (
                driver_id, 
                expense_type, 
                amount, 
                receipt_photo, 
                comment, 
                route_execution_id,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            driver_id,
            expense_type,
            amount,
            receipt_photo,
            comment,
            route_execution_id,
            datetime.now()
        ))
        self.connection.commit()
    
    def get_expense_by_date(self, driver_id, date_str):
        """Получить расход по дате"""
        cursor = self._execute_query('''
            SELECT 
                expense_type,
                amount,
                receipt_photo,
                comment,
                created_at
            FROM expenses 
            WHERE driver_id = ? AND created_at = ?
        ''', (driver_id, date_str))
        return cursor.fetchone()
