import streamlit as st
import pandas as pd
import plotly.express as px
import requests

def find_anomalies(city, season, df, city_seasons_stats):
    city_season_df = df[(df['city'] == city) & (df['season'] == season)]
    cur_stat = city_seasons_stats[
        (city_seasons_stats['city'] == city) &
        (city_seasons_stats['season'] == season)
    ]

    return city_season_df[abs(city_season_df['temperature'] - cur_stat['mean_temp'].iloc[0]) >
                        2 * cur_stat['std_dev'].iloc[0]]

def analyse(orig_df):
    df = orig_df.copy(deep=True)
    df['ma_30_temp'] = df.groupby('city')['temperature'].rolling(
        window=30, min_periods=1).mean().reset_index(level=0, drop=True)
    city_seasons_stats = df.groupby(['city', 'season']).agg(
        mean_temp=('temperature', 'mean'),
        std_dev=('temperature', 'std')).reset_index()
    
    anomalies = pd.DataFrame()
    for city in city_seasons_stats['city'].unique():
        for season in ['winter', 'spring', 'summer', 'autumn']:
            anomalies = pd.concat([anomalies, find_anomalies(city, season, df, city_seasons_stats)])
            
    return (df, city_seasons_stats, anomalies)


st.set_page_config(
    page_title="Weather Analyser",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.subheader("Анализ погоды в городах")

city_to_check = None
season_to_check = 'winter'

loaded_file = st.file_uploader("Загрузите CSV историческими данными", type=["csv"])
if loaded_file:
    df = pd.read_csv(loaded_file)
    unique_vals = df['city'].unique()
    city_to_check = st.selectbox('city', unique_vals, key=f"city")
    df, stats, anomalies = analyse(df)
    df = df[df['city'] == city_to_check]
    stats = stats[stats['city'] == city_to_check]
    anomalies = anomalies[anomalies['city'] == city_to_check]


if city_to_check:
    with st.expander("Аналитика"):
        df_city = df[df['city'] == city_to_check]
        st.subheader(f"Описательная статистика температуры в {city_to_check}")
        df_describe = df_city["temperature"].describe()
        st.dataframe(df_describe)
        fig_hist = px.histogram(
            df_city,
            x="temperature",
            nbins=30,
            title="Распределение температуры",
            labels={"temperature": "Температура"}
        )
        st.plotly_chart(fig_hist, width='stretch')


        st.subheader("Временной ряд температур и аномалии")
        mean_temp = stats['mean_temp']
        std_temp = stats['std_dev']

        fig_ts = px.line(
            df_city,
            x="timestamp",
            y="ma_30_temp",
            labels={"ma_30_temp": "Скользящее среднее за 30 дней", "timestamp": "Дата"},
            title="Временной ряд температуры со сглаживанием по скользящему среднему и аномалиями"
        )

        fig_anom = px.scatter(
            anomalies[anomalies["city"] == city_to_check],
            x="timestamp",
            y="ma_30_temp",
            color_discrete_sequence=["red"]
        )

        fig_ts.add_traces(fig_anom.data)

        st.plotly_chart(fig_ts, width='stretch')


        df['day_month'] = pd.to_datetime(df['timestamp']).dt.strftime('%d-%m')
        df['day_of_year'] = pd.to_datetime(df['timestamp']).dt.dayofyear

        seasonal = (
            df.groupby("day_of_year")['temperature']
            .agg(['mean', 'std']).reset_index()
        )

        fig_season = px.line(
            seasonal,
            x="day_of_year",
            y="mean",
            title="Сезонный профиль температуры",
            labels={"mean": "Средняя температура за годы", "day_of_year": "День года"}
        )

        seasonal["label"] = (
            pd.to_datetime(seasonal["day_of_year"], format="%j")
            .dt.strftime("%d.%m")
        )

        fig_season.add_scatter(
            x=seasonal["day_of_year"],
            y=seasonal["mean"] + seasonal["std"],
            mode="lines",
            line=dict(dash="dash"),
            name="+1 σ"
        )

        fig_season.add_scatter(
            x=seasonal["day_of_year"],
            y=seasonal["mean"] - seasonal["std"],
            mode="lines",
            line=dict(dash="dash"),
            name="-1 σ",
        )

        fig_season.update_traces(
            customdata=seasonal["label"],
            hovertemplate="Дата: %{customdata}<br>Температура: %{y:.1f} C"
        )

        season_ticks = [30, 105, 195, 285, 350]
        season_labels = ["Зима", "Весна", "Лето", "Осень", "Зима"]
        fig_season.update_xaxes(
            tickmode="array",
            tickvals=season_ticks,
            ticktext=season_labels,
            title="Сезон"
        )

        st.plotly_chart(fig_season, width='stretch')



with st.form("api_key_form"):
    api_key = st.text_input(
        "Введите API-ключ OpenWeatherMap",
        type="password",
        placeholder="Ваш API-ключ"
    )
    submitted = st.form_submit_button("Использовать этот API ключ")


if api_key :
    if not city_to_check:
        st.warning("⚠️ Пожалуйста, выберите город")
    else:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city_to_check,
            "appid": api_key,
            "units": "metric",
            "lang": "ru"
        }

        response = requests.get(url, params=params)

        if response.status_code == 401:
            error_data = response.json()
            st.error(
                f"❌ Ошибка {error_data['cod']}: {error_data['message']}"
            )

        elif response.status_code == 200:
            data = response.json()

            st.success(f"Погода в городе {data['name']}")

            st.metric(
                label="Температура",
                value=f"{data['main']['temp']} С"
            )

            st.write(f"Ветер: {data['wind']['speed']} м/с")
            st.write(f"Описание: {data['weather'][0]['description']}")

            temp_diff = data['main']['temp'] - stats[stats['season'] == season_to_check]['mean_temp'].iloc[0]
            temp_diff_std = temp_diff / stats[stats['season'] == season_to_check]['std_dev'].iloc[0]
            st.write(f"""Температура отличается от средней на {temp_diff:.4f} C""")
            st.write(f"Это {temp_diff_std:.2f} стандартных отклонений. ")
            if temp_diff_std < -2:
                st.warning("🌡️🔥 ВНИМАНИЕ! Данная температура является аномально высокой! Учтите это перед выходом на улицу! ")
            elif temp_diff_std > 2:
                st.warning("🌡️🥶 ВНИМАНИЕ! Данная температура является аномально низкой! Учтите это перед выходом на улицу! ")