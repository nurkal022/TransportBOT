import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from database import Database

# Настройка страницы
st.set_page_config(
    page_title="Панель управления",
    page_icon="📊",
    layout="wide"
)

@st.cache_resource
def get_database_connection():
    return Database('transport_expenses.db')

# Загрузка данных
@st.cache_data
def load_data():
    with get_database_connection() as db:
        conn = db.get_connection()
        
        # Загрузка расходов с информацией о водителях
        expenses_df = pd.read_sql("""
            SELECT 
                e.id,
                e.driver_id,
                d.full_name as driver_name,
                e.expense_type,
                e.amount,
                e.comment,
                e.created_at
            FROM expenses e
            JOIN drivers d ON e.driver_id = d.telegram_id
        """, conn)
        
        # Преобразуем created_at в datetime
        expenses_df['created_at'] = pd.to_datetime(expenses_df['created_at'])
        
        # Загрузка маршрутов
        routes_df = pd.read_sql("""
            SELECT 
                r.id,
                r.route_name,
                r.start_point,
                r.end_point,
                r.distance,
                r.price,
                r.cargo_type,
                re.status,
                d.full_name as driver_name,
                re.start_time,
                re.end_time
            FROM routes r
            LEFT JOIN route_executions re ON r.id = re.route_id
            LEFT JOIN drivers d ON re.driver_id = d.telegram_id
        """, conn)
        
        # Преобразуем start_time и end_time в datetime
        routes_df['start_time'] = pd.to_datetime(routes_df['start_time'])
        routes_df['end_time'] = pd.to_datetime(routes_df['end_time'])
        
        return expenses_df, routes_df

# Загрузка данных
expenses_df, routes_df = load_data()

# Заголовок дашборда
st.title("🚛 Дашборд транспортной компании")

# Боковая панель с фильтрами
st.sidebar.header("Фильтры")

# Фильтр по датам
date_range = st.sidebar.date_input(
    "Выберите период",
    value=(
        datetime.now() - timedelta(days=30),
        datetime.now()
    )
)

if len(date_range) == 2:
    start_date, end_date = date_range
    # Преобразуем даты в datetime
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    # Фильтруем данные
    expenses_filtered = expenses_df[
        (expenses_df['created_at'] >= start_datetime) &
        (expenses_df['created_at'] <= end_datetime)
    ]
    routes_filtered = routes_df[
        (routes_df['start_time'] >= start_datetime) &
        (routes_df['start_time'] <= end_datetime)
    ]
else:
    expenses_filtered = expenses_df
    routes_filtered = routes_df

# Основные метрики
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Общие расходы",
        f"{expenses_filtered['amount'].sum():,.0f} ₸"
    )

with col2:
    st.metric(
        "Количество маршрутов",
        len(routes_filtered)
    )

with col3:
    st.metric(
        "Средняя длина маршрута",
        f"{routes_filtered['distance'].mean():,.0f} км"
    )

with col4:
    st.metric(
        "Общий доход",
        f"{routes_filtered['price'].sum():,.0f} ₸"
    )

# Графики в две колонки
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Расходы по категориям")
    expenses_by_type = expenses_filtered.groupby('expense_type')['amount'].sum().reset_index()
    fig = px.pie(
        expenses_by_type,
        values='amount',
        names='expense_type',
        title='Распределение расходов по категориям'
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📈 Динамика расходов")
    expenses_by_date = expenses_filtered.groupby(
        expenses_filtered['created_at'].dt.date
    )['amount'].sum().reset_index()
    fig = px.line(
        expenses_by_date,
        x='created_at',
        y='amount',
        title='Динамика расходов по дням'
    )
    st.plotly_chart(fig, use_container_width=True)

# Анализ маршрутов
st.subheader("🗺️ Анализ маршрутов")
col1, col2 = st.columns(2)

with col1:
    # Топ маршрутов по прибыльности
    routes_profit = routes_filtered.groupby('route_name')['price'].sum().sort_values(ascending=False).head(10)
    fig = px.bar(
        routes_profit,
        title='Топ-10 маршрутов по прибыльности'
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Распределение грузов
    cargo_distribution = routes_filtered['cargo_type'].value_counts()
    fig = px.pie(
        values=cargo_distribution.values,
        names=cargo_distribution.index,
        title='Распеделение типов грузов'
    )
    st.plotly_chart(fig, use_container_width=True)

# Анализ водителей
st.subheader("👥 Анализ водителей")

# Метрики по водителям
driver_metrics = routes_filtered.groupby('driver_name').agg({
    'id': 'count',
    'distance': 'sum',
    'price': 'sum'
}).reset_index()

driver_metrics.columns = ['Водитель', 'Количество маршрутов', 'Общее расстояние', 'Общий доход']
st.dataframe(driver_metrics, use_container_width=True)

# График эффективности водителей
col1, col2 = st.columns(2)

with col1:
    # Среднее время выполнения маршрута
    routes_filtered['duration'] = (routes_filtered['end_time'] - routes_filtered['start_time']).dt.total_seconds() / 3600
    avg_duration = routes_filtered.groupby('driver_name')['duration'].mean().sort_values(ascending=True)
    
    fig = px.bar(
        avg_duration,
        title='Среднее время выполнения маршрута (часы)',
        labels={'driver_name': 'Водитель', 'value': 'Часы'}
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # Средняя скорость выполнения маршрута
    routes_filtered['speed'] = routes_filtered['distance'] / routes_filtered['duration']
    avg_speed = routes_filtered.groupby('driver_name')['speed'].mean().sort_values(ascending=False)
    
    fig = px.bar(
        avg_speed,
        title='Средняя скорость (км/ч)',
        labels={'driver_name': 'Водитель', 'value': 'км/ч'}
    )
    st.plotly_chart(fig, use_container_width=True)

# Карта тепла активности по дням недели и часам
st.subheader("📅 Тепловая карта активности")

routes_filtered['hour'] = routes_filtered['start_time'].dt.hour
routes_filtered['day_of_week'] = routes_filtered['start_time'].dt.day_name()

heatmap_data = routes_filtered.groupby(['day_of_week', 'hour']).size().reset_index()
heatmap_data.columns = ['day_of_week', 'hour', 'count']

# Сортировка дней недели
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
heatmap_data['day_of_week'] = pd.Categorical(heatmap_data['day_of_week'], categories=day_order, ordered=True)
heatmap_data = heatmap_data.sort_values(['day_of_week', 'hour'])

fig = px.density_heatmap(
    heatmap_data,
    x='hour',
    y='day_of_week',
    z='count',
    title='Тепловая карта начала маршруо',
    labels={'hour': 'Час', 'day_of_week': 'День недели', 'count': 'Количество маршрутов'}
)
st.plotly_chart(fig, use_container_width=True)

# Прогноз расходов (простой линейный тренд)
st.subheader("📈 Прогноз расходов")

# Группировка по месяцам для тренда
monthly_expenses = expenses_df.groupby(
    pd.Grouper(key='created_at', freq='M')
)['amount'].sum().reset_index() 