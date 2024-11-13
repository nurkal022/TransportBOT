import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Настройка страницы
st.set_page_config(
    page_title="Управление маршрутами",
    page_icon="🚛",
    layout="wide"
)

# Подключение к базе данных
@st.cache_resource
def get_database_connection():
    conn = sqlite3.connect('transport_expenses.db', check_same_thread=False)
    return conn

# Функции для работы с данными
def load_drivers(conn):
    return pd.read_sql("SELECT telegram_id, full_name FROM drivers", conn)

def load_cities(conn):
    cities_start = pd.read_sql("SELECT DISTINCT start_point FROM routes", conn)
    cities_end = pd.read_sql("SELECT DISTINCT end_point FROM routes", conn)
    return pd.concat([cities_start['start_point'], cities_end['end_point']]).unique()

def load_cargo_types(conn):
    return pd.read_sql("SELECT DISTINCT cargo_type FROM routes", conn)['cargo_type'].unique()

def load_active_routes(conn):
    return pd.read_sql("""
        SELECT 
            r.route_name,
            r.start_point,
            r.end_point,
            r.distance,
            r.price,
            r.cargo_type,
            d.full_name as driver_name,
            re.start_time,
            re.status
        FROM routes r
        JOIN route_executions re ON r.id = re.route_id
        JOIN drivers d ON re.driver_id = d.telegram_id
        WHERE re.status IN ('assigned', 'in_progress')
        ORDER BY re.start_time DESC
    """, conn)

def load_filtered_routes(conn, selected_driver, selected_status, selected_cargo):
    query = """
        SELECT 
            r.route_name,
            r.start_point,
            r.end_point,
            r.distance,
            r.price,
            r.cargo_type,
            d.full_name as driver_name,
            re.start_time,
            re.end_time,
            re.status
        FROM routes r
        JOIN route_executions re ON r.id = re.route_id
        JOIN drivers d ON re.driver_id = d.telegram_id
        WHERE 1=1
    """
    
    if selected_driver != 'Все':
        query += f" AND d.full_name = '{selected_driver}'"
    if selected_status != 'Все':
        query += f" AND re.status = '{selected_status}'"
    if selected_cargo != 'Все':
        query += f" AND r.cargo_type = '{selected_cargo}'"
    
    query += " ORDER BY re.start_time DESC"
    
    return pd.read_sql(query, conn)

# Функция для добавления нового маршрута
def add_new_route(conn, route_data):
    cursor = conn.cursor()
    
    try:
        # Проверяем существование таблиц
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_name TEXT,
                start_point TEXT,
                end_point TEXT,
                distance INTEGER,
                price INTEGER,
                cargo_type TEXT,
                created_at DATETIME
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS route_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_id INTEGER,
                driver_id INTEGER,
                start_time DATETIME,
                end_time DATETIME,
                status TEXT,
                FOREIGN KEY (route_id) REFERENCES routes(id),
                FOREIGN KEY (driver_id) REFERENCES drivers(telegram_id)
            )
        """)

        # Добавление маршрута
        cursor.execute("""
            INSERT INTO routes 
            (route_name, start_point, end_point, distance, price, cargo_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"Маршрут {route_data['start_point']}-{route_data['end_point']}",
            route_data['start_point'],
            route_data['end_point'],
            route_data['distance'],
            route_data['price'],
            route_data['cargo_type'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        route_id = cursor.lastrowid
        
        # Добавление назначения маршрута водителю
        if route_data['driver_id']:
            cursor.execute("""
                INSERT INTO route_executions 
                (route_id, driver_id, start_time, status)
                VALUES (?, ?, ?, ?)
            """, (
                route_id, 
                route_data['driver_id'], 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                'assigned'
            ))
        
        conn.commit()
        return True, "Маршрут успешно добавлен!"
    except Exception as e:
        conn.rollback()
        return False, f"Ошибка при добавлении маршрута: {str(e)}"

# Получаем соединение с базой данных
conn = get_database_connection()

# Заголовок страницы
st.title("🚛 Управление маршрутами")

# Загрузка начальных данных
drivers = load_drivers(conn)
cities = load_cities(conn)
cargo_types = load_cargo_types(conn)

# Создание формы для добавления маршрута
with st.form("add_route_form"):
    st.subheader("Добавление нового маршрута")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Заменяем selectbox на text_input для городов
        start_point = st.text_input(
            "Откуда",
            placeholder="Введите город отправления"
        )
        
        end_point = st.text_input(
            "Куда",
            placeholder="Введите город назначения"
        )
        
        driver = st.selectbox(
            "Водитель",
            options=[None] + drivers['telegram_id'].tolist(),
            format_func=lambda x: 'Выберите водителя' if x is None else drivers[drivers['telegram_id'] == x]['full_name'].iloc[0],
            index=0
        )
    
    with col2:
        distance = st.number_input("Расстояние (км)", min_value=1, value=100)
        price = st.number_input("Стоимость (тенге)", min_value=1000, value=50000)
        cargo_type = st.selectbox(
            "Тип груза", 
            options=[''] + list(cargo_types) if len(cargo_types) > 0 else ['Продукты', 'Стройматериалы', 'Техника', 'Мебель', 'Одежда'],
            index=0
        )
    
    submitted = st.form_submit_button("Добавить маршрут")
    
    if submitted:
        # Проверяем, что все поля заполнены
        if not start_point.strip() or not end_point.strip() or not driver or not cargo_type:
            st.error("Пожалуйста, заполните все поля формы")
        elif start_point.strip() == end_point.strip():
            st.error("Город отправления и назначения не могут быть одинаковыми")
        else:
            route_data = {
                'start_point': start_point.strip(),
                'end_point': end_point.strip(),
                'driver_id': driver,
                'distance': distance,
                'price': price,
                'cargo_type': cargo_type
            }
            
            success, message = add_new_route(conn, route_data)
            if success:
                st.success(message)
                # Заменяем experimental_rerun на rerun
                st.rerun()
            else:
                st.error(message)

# Отображение текущих активных маршрутов
st.subheader("Активные маршруты")

active_routes = load_active_routes(conn)
 
if not active_routes.empty:
    # Форматирование данных для отображения
    active_routes['start_time'] = pd.to_datetime(active_routes['start_time']).dt.strftime('%Y-%m-%d %H:%M')
    active_routes['price'] = active_routes['price'].apply(lambda x: f"{x:,.0f} ₸")
    active_routes['distance'] = active_routes['distance'].apply(lambda x: f"{x:,.0f} км")
    
    # Переименование колонок для отображения
    active_routes.columns = [
        'Маршрут', 'Откуда', 'Куда', 'Расстояние', 'Стоимость', 
        'Тип груза', 'Водитель', 'Время начала', 'Статус'
    ]
    
    st.dataframe(active_routes, use_container_width=True)
else:
    st.info("Нет активных маршрутов")

# Добавление фильтров для просмотра истории маршрутов
st.subheader("История маршрутов")

col1, col2, col3 = st.columns(3)

with col1:
    selected_driver = st.selectbox(
        "Фильтр по водителю",
        options=['Все'] + drivers['full_name'].tolist()
    )

with col2:
    selected_status = st.selectbox(
        "Статус маршрута",
        options=['Все', 'completed', 'assigned', 'in_progress']
    )

with col3:
    selected_cargo = st.selectbox(
        "Тип груза",
        options=['Все'] + list(cargo_types)
    )

# Загрузка и отображение отфильтрованных данных
filtered_routes = load_filtered_routes(conn, selected_driver, selected_status, selected_cargo)

if not filtered_routes.empty:
    # Форматирование данных
    filtered_routes['start_time'] = pd.to_datetime(filtered_routes['start_time']).dt.strftime('%Y-%m-%d %H:%M')
    filtered_routes['end_time'] = pd.to_datetime(filtered_routes['end_time']).dt.strftime('%Y-%m-%d %H:%M')
    filtered_routes['price'] = filtered_routes['price'].apply(lambda x: f"{x:,.0f} ₸")
    filtered_routes['distance'] = filtered_routes['distance'].apply(lambda x: f"{x:,.0f} км")
    
    # Переименование колонок
    filtered_routes.columns = [
        'Маршрут', 'Откуда', 'Куда', 'Расстояние', 'Стоимость', 
        'Тип груза', 'Водитель', 'Время начала', 'Время завершения', 'Статус'
    ]
    
    st.dataframe(filtered_routes, use_container_width=True)
else:
    st.info("Нет маршрутов, соответствующих выбранным фильтрам") 