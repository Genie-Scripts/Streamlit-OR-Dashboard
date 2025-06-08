import pandas as pd
import numpy as np
from utils import date_helpers
from analysis import weekly

def calculate_operating_room_utilization(df):
    """
    手術室の稼働率を計算する。（列名探索を強化）
    """
    if df.empty:
        return 0.0
    if 'is_weekday' not in df.columns:
        return 0.0

    weekday_df = df[df['is_weekday']].copy()
    if weekday_df.empty:
        return 0.0
        
    start_col, end_col, room_col = None, None, None
    
    # --- 列名探索ロジックを強化 ---
    possible_start_keys = ['入室時刻', '開始']
    possible_end_keys = ['退室時刻', '終了']
    possible_room_keys = ['実施手術室', '手術室']

    for col in df.columns:
        # 標準名または部分一致で検索
        if not start_col and any(key in col for key in possible_start_keys):
            start_col = col
        if not end_col and any(key in col for key in possible_end_keys):
            end_col = col
        if not room_col and any(key in col for key in possible_room_keys):
            room_col = col
            
        # 文字化けも考慮
        if not start_col and 'üº' in col: start_col = col
        if not end_col and 'Þº' in col: end_col = col
    # --- 探索ロジックここまで ---

    # --- 詳細計算ロジック (時刻と部屋データがある場合) ---
    if start_col and end_col and room_col:
        try:
            # 時刻データをdatetimeオブジェクトに変換 (エラーは無視)
            weekday_df[start_col] = pd.to_datetime(weekday_df[start_col], errors='coerce', format='%H:%M')
            weekday_df[end_col] = pd.to_datetime(weekday_df[end_col], errors='coerce', format='%H:%M')
            weekday_df.dropna(subset=[start_col, end_col], inplace=True)
            
            if weekday_df.empty: raise ValueError("Valid time data not found after conversion.")

            overnight_mask = weekday_df[end_col] < weekday_df[start_col]
            weekday_df.loc[overnight_mask, end_col] += pd.Timedelta(days=1)
            
            total_usage_minutes = 0
            op_start_time = pd.Timestamp('09:00:00').time()
            op_end_time = pd.Timestamp('17:15:00').time()

            for _, row in weekday_df.iterrows():
                day = row['手術実施日_dt'].date()
                operation_start = datetime.combine(day, op_start_time)
                operation_end = datetime.combine(day, op_end_time)
                
                actual_start = max(row[start_col], operation_start)
                actual_end = min(row[end_col], operation_end)
                
                if actual_end > actual_start:
                    total_usage_minutes += (actual_end - actual_start).total_seconds() / 60
            
            num_operating_days = weekday_df['手術実施日_dt'].dt.date.nunique()
            # 1日の稼働時間: 8時間15分 = 495分
            # 手術室の数を仮に11部屋とする (実績に合わせて調整が必要な場合あり)
            num_rooms = 11 
            total_available_minutes = num_operating_days * num_rooms * 495

            if total_available_minutes > 0:
                return min((total_usage_minutes / total_available_minutes) * 100, 100.0)
        except Exception as e:
            # 詳細計算でエラーが発生した場合は、簡易計算にフォールバックする
            print(f"Detailed utilization calculation failed: {e}. Falling back to estimation.")
            pass # Fallback to simplified calculation

    # --- 簡易計算ロジック (詳細データがない場合、またはエラー時) ---
    total_weekday_cases = len(weekday_df)
    total_operating_days = weekday_df['手術実施日_dt'].nunique()
    if total_operating_days > 0:
        avg_cases_per_day = total_weekday_cases / total_operating_days
        # 1日の手術室キャパシティを20件として推定
        return min((avg_cases_per_day / 20) * 100, 100.0)

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

    utilization_rate = calculate_operating_room_utilization(gas_df)

    return {
        "総手術件数 (直近30日)": total_cases,
        "1日あたり平均件数": f"{daily_average:.1f}",
        "平日1日あたり平均件数": f"{avg_cases_per_weekday:.1f}",
        "手術室稼働率": f"{utilization_rate:.1f}%" # ラベルを「(推定)」から変更
    }

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
    """
    主要診療科の直近4週間のパフォーマンスサマリーを計算する。
    """
    if df.empty or not target_dict:
        return pd.DataFrame()

    analysis_end_date = weekly.get_analysis_end_date(latest_date)
    if analysis_end_date is None:
        return pd.DataFrame()
        
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
        
        latest_week_start = dept_data['week_start'].max() if not dept_data.empty else pd.NaT
        latest_week_cases = len(dept_data[dept_data['week_start'] == latest_week_start])

        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        # ★ ここが列名を app.py の期待通りに修正した箇所です ★
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
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