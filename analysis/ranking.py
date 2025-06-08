# analysis/ranking.py (v6.1 最終完成版)
import pandas as pd
import numpy as np
from datetime import datetime, time
import re
import unicodedata
from utils import date_helpers
from analysis import weekly

def _normalize_room_name(series):
    """手術室名の表記を正規化（全角→半角、数字抽出、'OR'付与）する"""
    if not pd.api.types.is_string_dtype(series):
        series = series.astype(str)
    
    def normalize_single_name(name):
        try:
            half_width_name = unicodedata.normalize('NFKC', str(name))
            match = re.search(r'(\d+)', half_width_name)
            if match:
                return f"OR{match.group(1)}"
            return None
        except:
            return None
    return series.apply(normalize_single_name)

def _convert_to_datetime(series, date_series):
    """Excelの数値時間とテキスト時間を両方考慮してdatetimeオブジェクトに変換する"""
    try:
        numeric_series = pd.to_numeric(series, errors='coerce')
        valid_series = series.dropna()
        if not valid_series.empty and numeric_series.notna().sum() / len(valid_series) > 0.8:
            time_deltas = pd.to_timedelta(numeric_series * 24, unit='h', errors='coerce')
            return pd.to_datetime(date_series.astype(str)) + time_deltas
        
        time_only_series = pd.to_datetime(series, errors='coerce', format=None).dt.time
        valid_times = time_only_series.notna()
        combined_dt = pd.Series(pd.NaT, index=series.index)
        if valid_times.any():
            date_series_valid = date_series[valid_times]; time_only_series_valid = time_only_series[valid_times]
            combined_dt.loc[valid_times] = [datetime.combine(d.date(), t) if isinstance(d, datetime) else datetime.combine(d, t) for d, t in zip(date_series_valid, time_only_series_valid)]
        return combined_dt
    except Exception:
        return pd.Series(pd.NaT, index=series.index)

def calculate_operating_room_utilization(df, period_df):
    """手術室の稼働率を計算する"""
    if df.empty or period_df.empty or 'is_weekday' not in df.columns: return 0.0
    weekday_df = period_df[period_df['is_weekday']].copy()
    if weekday_df.empty: return 0.0
    start_col, end_col, room_col = None, None, None
    possible_start_keys=['入室時刻','開始']; possible_end_keys=['退室時刻','終了']; possible_room_keys=['実施手術室','手術室']
    for col in df.columns:
        if not start_col and any(key in col for key in possible_start_keys): start_col = col
        if not end_col and any(key in col for key in possible_end_keys): end_col = col
        if not room_col and any(key in col for key in possible_room_keys): room_col = col

    if start_col and end_col and room_col:
        try:
            target_rooms = ['OR1', 'OR2', 'OR3', 'OR4', 'OR5', 'OR6', 'OR7', 'OR8', 'OR9', 'OR10', 'OR12']
            normalized_room_series = _normalize_room_name(weekday_df[room_col])
            valid_normalized_rooms = normalized_room_series.dropna()
            filtered_weekday_df = weekday_df.loc[valid_normalized_rooms[valid_normalized_rooms.isin(target_rooms)].index].copy()
            if filtered_weekday_df.empty: return 0.0
            filtered_weekday_df['start_datetime'] = _convert_to_datetime(filtered_weekday_df[start_col], filtered_weekday_df['手術実施日_dt'])
            filtered_weekday_df['end_datetime'] = _convert_to_datetime(filtered_weekday_df[end_col], filtered_weekday_df['手術実施日_dt'])
            filtered_weekday_df.dropna(subset=['start_datetime', 'end_datetime'], inplace=True)
            if filtered_weekday_df.empty: return 0.0
            overnight_mask = filtered_weekday_df['end_datetime'] < filtered_weekday_df['start_datetime']
            filtered_weekday_df.loc[overnight_mask, 'end_datetime'] += pd.Timedelta(days=1)
            total_usage_minutes = 0
            op_start_time = time(9, 0); op_end_time = time(17, 15)
            for _, row in filtered_weekday_df.iterrows():
                day = row['手術実施日_dt'].date()
                operation_start = datetime.combine(day, op_start_time); operation_end = datetime.combine(day, op_end_time)
                actual_start = max(row['start_datetime'], operation_start); actual_end = min(row['end_datetime'], operation_end)
                if actual_end > actual_start: total_usage_minutes += (actual_end - actual_start).total_seconds() / 60
            period_start_date = period_df['手術実施日_dt'].min(); period_end_date = period_df['手術実施日_dt'].max()
            total_weekdays_in_period = len(pd.bdate_range(period_start_date, period_end_date))
            num_rooms = 11; total_available_minutes = total_weekdays_in_period * num_rooms * 495
            if total_available_minutes > 0: return min((total_usage_minutes / total_available_minutes) * 100, 100.0)
        except Exception: pass
    return 0.0

def get_kpi_summary(df, latest_date):
    """
    ダッシュボード用の主要KPIサマリーを計算する。
    """
    if df.empty: return {}
    recent_df = date_helpers.filter_by_period(df, latest_date, "直近30日")
    gas_df = recent_df[recent_df['is_gas_20min']]
    if gas_df.empty: return {}
    total_cases = len(gas_df)
    days_in_period = (gas_df['手術実施日_dt'].max() - gas_df['手術実施日_dt'].min()).days + 1
    daily_average = total_cases / days_in_period if days_in_period > 0 else 0
    weekday_df = gas_df[gas_df['is_weekday']]
    total_operating_days = weekday_df['手術実施日_dt'].nunique()
    avg_cases_per_weekday = len(weekday_df) / total_operating_days if total_operating_days > 0 else 0
    utilization_rate = min((avg_cases_per_weekday / 20) * 100, 100)
    return {
        "総手術件数 (直近30日)": total_cases,
        "1日あたり平均件数": f"{daily_average:.1f}",
        "平日1日あたり平均件数": f"{avg_cases_per_weekday:.1f}",
        "手術室稼働率 (推定)": f"{utilization_rate:.1f}%"
    }

def get_department_performance_summary(df, target_dict, latest_date):
    if df.empty or not target_dict: return pd.DataFrame()
    analysis_end_date = weekly.get_analysis_end_date(latest_date)
    if analysis_end_date is None: return pd.DataFrame()
    start_date_filter = analysis_end_date - pd.Timedelta(days=27)
    four_weeks_df = df[(df['手術実施日_dt'] >= start_date_filter) & (df['手術実施日_dt'] <= analysis_end_date)]
    gas_df = four_weeks_df[four_weeks_df['is_gas_20min']]
    if gas_df.empty: return pd.DataFrame()
    results = []
    for dept in target_dict.keys():
        dept_data = gas_df[gas_df['実施診療科'] == dept]
        if dept_data.empty: continue
        total_cases = len(dept_data)
        num_weeks = dept_data['week_start'].nunique()
        avg_weekly = total_cases / 4 if num_weeks == 0 else total_cases / num_weeks
        target = target_dict.get(dept, 0)
        achievement_rate = (avg_weekly / target) * 100 if target > 0 else 0
        latest_week_start = dept_data['week_start'].max() if not dept_data.empty else pd.NaT
        latest_week_cases = len(dept_data[dept_data['week_start'] == latest_week_start])
        results.append({
            "診療科": dept,
            "4週平均": avg_weekly,
            "直近週実績": latest_week_cases,
            "週次目標": target,
            "達成率(%)": achievement_rate,
        })
    if not results: return pd.DataFrame()
    return pd.DataFrame(results)

def calculate_achievement_rates(df, target_dict):
    """
    診療科ごとの目標達成率を計算する。
    """
    if df.empty or not target_dict:
        return pd.DataFrame()

    gas_df = df[df['is_gas_20min']].copy()
    if gas_df.empty:
        return pd.DataFrame()

    actual_start_date = gas_df['手術実施日_dt'].min()
    actual_end_date = gas_df['手術実施日_dt'].max()
    period_days = (actual_end_date - actual_start_date).days + 1
    weeks_in_period = period_days / 7.0

    if weeks_in_period <= 0:
        return pd.DataFrame()

    dept_counts = gas_df.groupby('実施診療科').size().reset_index(name='実績件数')

    result = []
    for _, row in dept_counts.iterrows():
        dept = row['実施診療科']
        if dept in target_dict:
            actual_count = row['実績件数']
            weekly_target = target_dict[dept]
            target_count_period = weekly_target * weeks_in_period
            achievement_rate = (actual_count / target_count_period) * 100 if target_count_period > 0 else 0

            result.append({
                '診療科': dept,
                '実績件数': actual_count,
                '期間内目標件数': round(target_count_period, 1),
                '達成率(%)': round(achievement_rate, 1)
            })

    if not result:
        return pd.DataFrame()

    result_df = pd.DataFrame(result)
    return result_df.sort_values('達成率(%)', ascending=False).reset_index(drop=True)

def calculate_cumulative_cases(df, target_weekly_cases):
    """
    今年度の累積実績と目標を週次で計算する
    """
    if df.empty:
        return pd.DataFrame()

    fiscal_year = date_helpers.get_fiscal_year(df['手術実施日_dt'].max())
    start_fiscal_year = pd.Timestamp(fiscal_year, 4, 1)
    
    df_fiscal = df[(df['手術実施日_dt'] >= start_fiscal_year) & (df['is_gas_20min'])].copy()

    if df_fiscal.empty:
        return pd.DataFrame()

    weekly_actual = df_fiscal.groupby('week_start').size().reset_index(name='週次実績')
    
    min_week = df_fiscal['week_start'].min()
    max_week = df_fiscal['week_start'].max()

    all_weeks = pd.date_range(start=min_week, end=max_week, freq='W-MON')
    
    weekly_df = pd.DataFrame({'週': all_weeks})
    weekly_df = pd.merge(weekly_df, weekly_actual, left_on='週', right_on='week_start', how='left').fillna(0)
    weekly_df = weekly_df.sort_values('週')
    weekly_df['週次実績'] = weekly_df['週次実績'].astype(int)
    weekly_df['累積実績'] = weekly_df['週次実績'].cumsum()
    weekly_df['経過週'] = np.arange(len(weekly_df)) + 1
    weekly_df['累積目標'] = weekly_df['経過週'] * target_weekly_cases
    
    return weekly_df[['週', '週次実績', '累積実績', '累積目標']]