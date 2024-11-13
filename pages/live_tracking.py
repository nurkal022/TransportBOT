import streamlit as st
import folium
from folium import plugins
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from streamlit_folium import folium_static
import random

# Настройка страницы
st.set_page_config(
    page_title="Отслеживание транспорта",
    page_icon="🚛",
    layout="wide"
)

# Подключение к базе данных
@st.cache_resource
def get_database_connection():
    return sqlite3.connect('transport_expenses.db', check_same_thread=False)

# Загрузка данных о водителях
def load_drivers(conn):
    return pd.read_sql("SELECT telegram_id, full_name FROM drivers", conn)

# Демонстрационные данные о местоположении (основные города Казахстана)
DEMO_LOCATIONS = {
    "Алматы": {"lat": 43.2220, "lon": 76.8512},
    "Астана": {"lat": 51.1801, "lon": 71.446},
    "Шымкент": {"lat": 42.3174, "lon": 69.5956},
    "Караганда": {"lat": 49.8047, "lon": 73.1094},
    "Актобе": {"lat": 50.2785, "lon": 57.2072},
    "Тараз": {"lat": 42.9000, "lon": 71.3667},
    "Павлодар": {"lat": 52.2873, "lon": 76.9674},
    "Усть-Каменогорск": {"lat": 49.9481, "lon": 82.6276},
    "Семей": {"lat": 50.4265, "lon": 80.2671},
    "Атырау": {"lat": 47.1167, "lon": 51.8833},
}

# Генерация демонстрационных данных о движении транспорта
def generate_demo_vehicle_data(drivers_df):
    vehicles = []
    statuses = ['В пути', 'На погрузке', 'На разгрузке', 'Остановка']
    
    for _, driver in drivers_df.iterrows():
        # Выбираем случайный город
        city = random.choice(list(DEMO_LOCATIONS.keys()))
        location = DEMO_LOCATIONS[city]
        
        # Добавляем небольшое случайное отклонение к координатам
        lat = location['lat'] + random.uniform(-0.1, 0.1)
        lon = location['lon'] + random.uniform(-0.1, 0.1)
        
        # Генерируем случайную скорость и направление
        speed = random.randint(0, 90)
        status = random.choice(statuses)
        
        vehicles.append({
            'driver_id': driver['telegram_id'],
            'driver_name': driver['full_name'],
            'lat': lat,
            'lon': lon,
            'speed': speed,
            'status': status,
            'last_update': datetime.now() - timedelta(minutes=random.randint(0, 30)),
            'destination': random.choice(list(DEMO_LOCATIONS.keys())),
            'cargo': random.choice(['Продукты', 'Стройматериалы', 'Техника', 'Мебель'])
        })
    
    return pd.DataFrame(vehicles)

# Создание карты
def create_map(vehicles_df):
    # Создаем карту, центрированную по Казахстану
    m = folium.Map(
        location=[48.0196, 66.9237],
        zoom_start=5,
        tiles='CartoDB positron'
    )
    
    # Добавляем основные города
    for city, coords in DEMO_LOCATIONS.items():
        folium.CircleMarker(
            location=[coords['lat'], coords['lon']],
            radius=8,
            popup=city,
            color="#3186cc",
            fill=True,
            fill_color="#3186cc"
        ).add_to(m)
    
    # Добавляем маркеры транспорта
    for _, vehicle in vehicles_df.iterrows():
        # Определяем иконку в зависимости от статуса
        icon_color = {
            'В пути': 'green',
            'На погрузке': 'blue',
            'На разгрузке': 'orange',
            'Остановка': 'red'
        }.get(vehicle['status'], 'gray')
        
        # Создаем HTML для всплывающего окна
        popup_html = f"""
            <div style="width: 200px;">
                <h4>{vehicle['driver_name']}</h4>
                <p><b>Статус:</b> {vehicle['status']}</p>
                <p><b>Скорость:</b> {vehicle['speed']} км/ч</p>
                <p><b>Пункт назначения:</b> {vehicle['destination']}</p>
                <p><b>Груз:</b> {vehicle['cargo']}</p>
                <p><b>Последнее обновление:</b> {vehicle['last_update'].strftime('%H:%M')}</p>
            </div>
        """

        # Создаем иконку грузовика
        truck_icon = folium.features.CustomIcon(
            icon_image=f'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-{icon_color}.png',
            icon_size=(25, 41),
            icon_anchor=(12, 41),
            popup_anchor=(0, -41)
        )
        
        # Добавляем маркер на карту
        folium.Marker(
            location=[vehicle['lat'], vehicle['lon']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=truck_icon,
            tooltip=f"{vehicle['driver_name']} - {vehicle['status']}"
        ).add_to(m)

        # Добавляем круг для обозначения области движения
        folium.Circle(
            location=[vehicle['lat'], vehicle['lon']],
            radius=1000,  # радиус в метрах
            color=icon_color,
            fill=True,
            fill_opacity=0.2
        ).add_to(m)

    # Добавляем плагин для отслеживания местоположения
    plugins.LocateControl().add_to(m)
    
    # Добавляем плагин для полноэкранного режима
    plugins.Fullscreen().add_to(m)
    
    # Добавляем плагин для измерения расстояний
    plugins.MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='miles',
        primary_area_unit='sqmeters',
        secondary_area_unit='acres'
    ).add_to(m)

    return m

# Получаем соединение с базой данных
conn = get_database_connection()

# Заголовок страницы
st.title("🗺️ Отслеживание транспорта в реальном времени")

# Загружаем данные о водителях
drivers_df = load_drivers(conn)

# Генерируем демонстрационные данные
vehicles_df = generate_demo_vehicle_data(drivers_df)

# Создаем колонки для отображения статистики
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Всего транспорта",
        len(vehicles_df)
    )

with col2:
    in_motion = len(vehicles_df[vehicles_df['status'] == 'В пути'])
    st.metric(
        "В движении",
        in_motion
    )

with col3:
    loading = len(vehicles_df[vehicles_df['status'].isin(['На погрузке', 'На разгрузке'])])
    st.metric(
        "На погрузке/разгрузке",
        loading
    )

with col4:
    stopped = len(vehicles_df[vehicles_df['status'] == 'Остановка'])
    st.metric(
        "На остановке",
        stopped
    )

# Создаем и отображаем карту
st.subheader("Карта транспорта")
m = create_map(vehicles_df)
folium_static(m, width=1400, height=600)

# Отображаем таблицу с данными о транспорте
st.subheader("Детальная информация")
detailed_df = vehicles_df[['driver_name', 'status', 'speed', 'destination', 'cargo', 'last_update']].copy()
detailed_df['last_update'] = detailed_df['last_update'].dt.strftime('%H:%M')
detailed_df.columns = ['Водитель', 'Статус', 'Скорость (км/ч)', 'Пункт назначения', 'Груз', 'Последнее обновление']
st.dataframe(detailed_df, use_container_width=True)

# Добавляем фильтры
st.sidebar.header("Фильтры")
status_filter = st.sidebar.multiselect(
    "Статус транспорта",
    options=['В пути', 'На погрузке', 'На разгрузке', 'Остановка'],
    default=['В пути', 'На погрузке', 'На разгрузке', 'Остановка']
)

cargo_filter = st.sidebar.multiselect(
    "Тип груза",
    options=vehicles_df['cargo'].unique(),
    default=vehicles_df['cargo'].unique()
)

# Обновление каждые 5 минут
st.sidebar.info("🔄 Данные обновляются каждые 5 минут")

# Добавляем легенду
st.sidebar.subheader("Легенда")
legend_html = """
<div style="padding: 10px; background-color: white; border-radius: 5px;">
    <div style="margin-bottom: 5px;">
        <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png" 
             style="width: 20px; vertical-align: middle;"> В пути
    </div>
    <div style="margin-bottom: 5px;">
        <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png" 
             style="width: 20px; vertical-align: middle;"> На погрузке
    </div>
    <div style="margin-bottom: 5px;">
        <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png" 
             style="width: 20px; vertical-align: middle;"> На разгрузке
    </div>
    <div style="margin-bottom: 5px;">
        <img src="https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png" 
             style="width: 20px; vertical-align: middle;"> Остановка
    </div>
</div>
"""
st.sidebar.markdown(legend_html, unsafe_allow_html=True)