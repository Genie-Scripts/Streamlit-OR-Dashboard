# analysis/ranking.py (手術室稼働率計算 修正版)
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
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
            # 全角文字を半角に変換
            half_width_name = unicodedata.normalize('NFKC', str(name))
            
            # 数字を抽出（「ハート1」→「1」、「心臓外1」→「1」など）
            match = re.search(r'(\d+)', half_width_name)
            if match:
                room_num = int(match.group(1))
                return f"OR{room_num}"
            return None
        except:
            return None
    
    return series.apply(normalize_single_name)

def _convert_to_datetime(time_series, date_series):
    """時刻文字列をdatetimeオブジェクトに変換する"""
    try:
        result = pd.Series(pd.NaT, index=time_series.index)
        
        for idx in time_series.index:
            if pd.isna(time_series[idx]) or pd.isna(date_series[idx]):
                continue
                
            time_str = str(time_series[idx]).strip()
            date_obj = date_series[idx]
            
            # 時刻文字列をパース（HH:MM形式を想定）
            try:
                if ':' in time_str:
                    hour, minute = map(int, time_str.split(':'))
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        # 日付と時刻を結合
                        if isinstance(date_obj, datetime):
                            result[idx] = datetime.combine(date_obj.date(), time(hour, minute))
                        else:
                            result[idx] = datetime.combine(date_obj, time(hour, minute))
            except (ValueError, AttributeError):
                continue
                
        return result
    except Exception:
        return pd.Series(pd.NaT, index=time_series.index)

def calculate_operating_room_utilization(df, period_df):
    """
    手術室の稼働率を実計算する
    
    稼働率の定義：
    - 対象手術室：OR1〜OR12（OR11を除く）の11室
    - 稼働時間：平日9:00〜17:15（495分）
    - 計算式：(実際の手術時間の合計) / (495分 × 11室 × 平日日数) × 100
    """
    try:
        if df.empty or period_df.empty:
            return 0.0
            
        # 平日のみを対象とする
        if 'is_weekday' not in period_df.columns:
            return 0.0
            
        weekday_df = period_df[period_df['is_weekday']].copy()
        if weekday_df.empty:
            return 0.0
        
        # 列名の特定（文字化けに対応）
        possible_start_cols = ['入室時刻', '開始時刻', '入室時間']
        possible_end_cols = ['退室時刻', '終了時刻', '退室時間']
        possible_room_cols = ['実施手術室', '手術室', '手術室名']
        
        start_col = None
        end_col = None
        room_col = None
        
        # 実際の列名から対応する列を特定
        for col in weekday_df.columns:
            col_clean = str(col).strip()
            
            # 入室時刻の列を特定
            if not start_col:
                for possible in possible_start_cols:
                    if possible in col_clean or any(char in col_clean for char in ['入', '開始']):
                        # 時刻データがあるかチェック
                        sample = weekday_df[col].dropna().head(5)
                        if not sample.empty and any(':' in str(val) for val in sample):
                            start_col = col
                            break
            
            # 退室時刻の列を特定
            if not end_col:
                for possible in possible_end_cols:
                    if possible in col_clean or any(char in col_clean for char in ['退', '終了']):
                        # 時刻データがあるかチェック
                        sample = weekday_df[col].dropna().head(5)
                        if not sample.empty and any(':' in str(val) for val in sample):
                            end_col = col
                            break
            
            # 手術室の列を特定
            if not room_col:
                for possible in possible_room_cols:
                    if possible in col_clean or any(char in col_clean for char in ['室', '手術']):
                        # 手術室データがあるかチェック
                        sample = weekday_df[col].dropna().head(5)
                        if not sample.empty:
                            room_col = col
                            break
        
        print(f"特定された列: 入室={start_col}, 退室={end_col}, 手術室={room_col}")
        
        if not all([start_col, end_col, room_col]):
            print("必要な列が特定できませんでした")
            return 0.0
        
        # 対象手術室（OR1〜OR12、OR11除く）
        target_rooms = [f'OR{i}' for i in range(1, 13) if i != 11]
        print(f"対象手術室: {target_rooms}")
        
        # 手術室名を正規化
        weekday_df['normalized_room'] = _normalize_room_name(weekday_df[room_col])
        
        # 対象手術室でフィルタリング
        filtered_df = weekday_df[weekday_df['normalized_room'].isin(target_rooms)].copy()
        
        if filtered_df.empty:
            print("対象手術室でのデータが見つかりませんでした")
            return 0.0
        
        print(f"対象データ件数: {len(filtered_df)}")
        
        # 時刻をdatetimeに変換
        filtered_df['start_datetime'] = _convert_to_datetime(
            filtered_df[start_col], 
            filtered_df['手術実施日_dt']
        )
        filtered_df['end_datetime'] = _convert_to_datetime(
            filtered_df[end_col], 
            filtered_df['手術実施日_dt']
        )
        
        # 有効な時刻データのみを残す
        valid_time_df = filtered_df.dropna(subset=['start_datetime', 'end_datetime']).copy()
        
        if valid_time_df.empty:
            print("有効な時刻データがありませんでした")
            return 0.0
        
        print(f"有効な時刻データ件数: {len(valid_time_df)}")
        
        # 終了時刻が開始時刻より早い場合（日をまたぐ）は翌日とする
        overnight_mask = valid_time_df['end_datetime'] < valid_time_df['start_datetime']
        valid_time_df.loc[overnight_mask, 'end_datetime'] += timedelta(days=1)
        
        # 稼働時間の計算
        operation_start_time = time(9, 0)   # 9:00
        operation_end_time = time(17, 15)   # 17:15
        
        total_usage_minutes = 0
        
        for _, row in valid_time_df.iterrows():
            surgery_date = row['手術実施日_dt'].date()
            operation_start = datetime.combine(surgery_date, operation_start_time)
            operation_end = datetime.combine(surgery_date, operation_end_time)
            
            # 手術の実際の開始・終了時刻
            actual_start = max(row['start_datetime'], operation_start)
            actual_end = min(row['end_datetime'], operation_end)
            
            # 稼働時間内の手術時間を計算
            if actual_end > actual_start:
                usage_minutes = (actual_end - actual_start).total_seconds() / 60
                total_usage_minutes += usage_minutes
        
        print(f"総手術時間: {total_usage_minutes:.1f}分")
        
        # 期間内の平日数を計算
        period_start = period_df['手術実施日_dt'].min()
        period_end = period_df['手術実施日_dt'].max()
        
        # 平日数を計算（pandas.bdate_rangeを使用）
        weekdays = pd.bdate_range(start=period_start, end=period_end)
        total_weekdays = len(weekdays)
        
        print(f"期間内平日数: {total_weekdays}日")
        
        # 稼働率を計算
        # 総稼働可能時間 = 495分 × 11室 × 平日数
        num_rooms = 11
        operation_minutes_per_day = 495  # 9:00-17:15 = 495分
        total_available_minutes = total_weekdays * num_rooms * operation_minutes_per_day
        
        print(f"総稼働可能時間: {total_available_minutes:.1f}分")
        
        if total_available_minutes > 0:
            utilization_rate = (total_usage_minutes / total_available_minutes) * 100
            utilization_rate = min(utilization_rate, 100.0)  # 100%を上限とする
            print(f"稼働率: {utilization_rate:.1f}%")
            return utilization_rate
        else:
            return 0.0
            
    except Exception as e:
        print(f"稼働率計算でエラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0.0

def get_kpi_summary(df, latest_date):
    """
    ダッシュボード用の主要KPIサマリーを計算する。
    """
    if df.empty:
        return {}
    
    # 直近30日のデータを取得
    recent_df = date_helpers.filter_by_period(df, latest_date, "直近30日")
    gas_df = recent_df[recent_df['is_gas_20min']]
    
    if gas_df.empty:
        return {}
    
    # 基本統計
    total_cases = len(gas_df)
    days_in_period = (gas_df['手術実施日_dt'].max() - gas_df['手術実施日_dt'].min()).days + 1
    daily_average = total_cases / days_in_period if days_in_period > 0 else 0
    
    # 平日のみの統計
    weekday_df = gas_df[gas_df['is_weekday']]
    total_operating_days = weekday_df['手術実施日_dt'].nunique()
    avg_cases_per_weekday = len(weekday_df) / total_operating_days if total_operating_days > 0 else 0
    
    # 実際の手術室稼働率を計算
    utilization_rate = calculate_operating_room_utilization(df, recent_df)
    
    return {
        "総手術件数 (直近30日)": total_cases,
        "1日あたり平均件数": f"{daily_average:.1f}",
        "平日1日あたり平均件数": f"{avg_cases_per_weekday:.1f}",
        "手術室稼働率": f"{utilization_rate:.1f}%"
    }

def get_department_performance_summary(df, target_dict, latest_date):
    """診療科別パフォーマンスサマリーを取得"""
    if df.empty or not target_dict:
        return pd.DataFrame()
    
    analysis_end_date = weekly.get_analysis_end_date(latest_date)
    if analysis_end_date is None:
        return pd.DataFrame()
    
    # 直近4週間のデータ
    start_date_filter = analysis_end_date - pd.Timedelta(days=27)
    four_weeks_df = df[
        (df['手術実施日_dt'] >= start_date_filter) & 
        (df['手術実施日_dt'] <= analysis_end_date)
    ]
    
    gas_df = four_weeks_df[four_weeks_df['is_gas_20min']]
    if gas_df.empty:
        return pd.DataFrame()
    
    results = []
    for dept in target_dict.keys():
        dept_data = gas_df[gas_df['実施診療科'] == dept]
        if dept_data.empty:
            continue
        
        total_cases = len(dept_data)
        num_weeks = dept_data['week_start'].nunique()
        avg_weekly = total_cases / 4 if num_weeks == 0 else total_cases / num_weeks
        
        target = target_dict.get(dept, 0)
        achievement_rate = (avg_weekly / target) * 100 if target > 0 else 0
        
        # 最新週の実績
        latest_week_start = dept_data['week_start'].max() if not dept_data.empty else pd.NaT
        latest_week_cases = len(dept_data[dept_data['week_start'] == latest_week_start])
        
        results.append({
            "診療科": dept,
            "4週平均": avg_weekly,
            "直近週実績": latest_week_cases,
            "週次目標": target,
            "達成率(%)": achievement_rate,
        })
    
    if not results:
        return pd.DataFrame()
    
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