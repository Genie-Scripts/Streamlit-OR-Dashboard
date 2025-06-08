# analysis/ranking.py
import pandas as pd
import numpy as np
from utils import date_helpers

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

    # 直近の完全な4週間分のデータを取得
    from analysis import weekly
    four_weeks_df = df.copy()
    # 4週間分のデータをフィルタリングするため、少し広めに期間を取る
    start_date_filter = latest_date - pd.Timedelta(days=35)
    four_weeks_df = four_weeks_df[four_weeks_df['手術実施日_dt'] >= start_date_filter]
    four_weeks_df = four_weeks_df[weekly._get_complete_week_filter(four_weeks_df)]
    
    gas_df = four_weeks_df[four_weeks_df['is_gas_20min']]
    
    if gas_df.empty:
        return pd.DataFrame()

    results = []
    for dept, target in target_dict.items():
        dept_data = gas_df[gas_df['実施診療科'] == dept]
        if dept_data.empty:
            continue
            
        total_cases = len(dept_data)
        num_weeks = dept_data['week_start'].nunique()
        avg_weekly = total_cases / num_weeks if num_weeks > 0 else 0
        achievement_rate = (avg_weekly / target) * 100 if target > 0 else 0
        
        # 直近週の実績
        latest_week_start = dept_data['week_start'].max()
        latest_week_cases = len(dept_data[dept_data['week_start'] == latest_week_start])

        results.append({
            "診療科": dept,
            "4週平均": avg_weekly,
            "直近週": latest_week_cases,
            "週次目標": target,
            "達成率(%)": achievement_rate,
        })

    if not results:
        return pd.DataFrame()
        
    return pd.DataFrame(results).sort_values("達成率(%)", ascending=False)

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