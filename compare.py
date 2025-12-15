import time
from multiprocessing import Pool, cpu_count
import pandas as pd
import numpy as np

# загрузим датасет

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
            city_season_df = df[(df['city'] == city) & (df['season'] == season)]
            cur_stat = city_seasons_stats[(city_seasons_stats['city'] == city) &
                                                (city_seasons_stats['season'] == season)]
            anomalies = pd.concat([anomalies, find_anomalies(city, season, df, city_seasons_stats)])
            
    return (df, city_seasons_stats, anomalies)

func_df, func_stats, func_anomalies = analyse(pd.read_csv('temperature_data.csv'))

def parallel_analyse(orig_df, n_jobs=4):
    df = orig_df.copy(deep=True)
    df['ma_30_temp'] = df.groupby('city')['temperature'].rolling(
    window=30, min_periods=1).mean().reset_index(level=0, drop=True)
    city_seasons_stats = df.groupby(['city', 'season']).agg(
    mean_temp=('temperature', 'mean'),
    std_dev=('temperature', 'std')).reset_index()

    # параллельность может быть полезной только в этих вычислениях, тк мы проходимся по циклам
    tasks = [
        (city, season, df, city_seasons_stats)
        for city in city_seasons_stats['city'].unique()
        for season in ['winter', 'spring', 'summer', 'autumn']
    ]
    with Pool(processes=n_jobs or cpu_count()) as pool:
        anomalies = pool.starmap(find_anomalies, tasks)
    anomalies = pd.concat(anomalies, ignore_index=True)

            
    return (df, city_seasons_stats, anomalies)

# func_df, func_stats, func_anomalies = parallel_analyse(pd.read_csv('temperature_data.csv'))


if __name__ == '__main__':
    df = pd.read_csv('temperature_data.csv')

    start = time.time()
    analyse(df)
    seq_time = time.time() - start

    start = time.time()
    parallel_analyse(df)
    par_time = time.time() - start

    print(f"Обычный:        {seq_time:.2f} sec")
    print(f"Параллельный:   {par_time:.2f} sec")
    print(f"Ускорение:      {seq_time / par_time:.2f}x")