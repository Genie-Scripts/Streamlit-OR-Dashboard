# analysis/ranking.py
import pandas as pd
from utils import date_helpers

def calculate_achievement_rates(df, target_dict):
    """
    診療科ごとの目標達成率を計算する。

    :param df: フィルタリング済みのDataFrame
    :param target_dict: 診療科と目標値の辞書
    :return: 達成率を計算したDataFrame
    """
    if df.empty or not target_dict:
        return pd.DataFrame()

    gas_df = df[df['is_gas_20min']].copy()
    if gas_df.empty:
        return pd.DataFrame()

    # 期間の日数と週数を計算
    actual_start_date = gas_df['手術実施日_dt'].min()
    actual_end_date = gas_df['手術実施日_dt'].max()
    period_days = (actual_end_date - actual_start_date).days + 1
    weeks_in_period = period_days / 7.0

    if weeks_in_period <= 0:
        return pd.DataFrame()

    # 診療科ごとの件数
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

    :param df: 前処理済みのDataFrame
    :param latest_date: 最新データの日付
    :return: KPI値を含む辞書
    """
    if df.empty:
        return {}

    # 直近30日のデータ
    recent_df = date_helpers.filter_by_period(df, latest_date, "直近30日")
    gas_df = recent_df[recent_df['is_gas_20min']]

    if gas_df.empty:
        return {}

    total_cases = len(gas_df)
    days_in_period = (gas_df['手術実施日_dt'].max() - gas_df['手術実施日_dt'].min()).days + 1
    daily_average = total_cases / days_in_period if days_in_period > 0 else 0

    # 稼働率の簡易計算
    weekday_df = gas_df[gas_df['is_weekday']]
    total_operating_days = weekday_df['手術実施日_dt'].nunique()
    avg_cases_per_weekday = len(weekday_df) / total_operating_days if total_operating_days > 0 else 0
    # 1日の手術室キャパシティを仮に20件として稼働率を推定
    utilization_rate = min((avg_cases_per_weekday / 20) * 100, 100)

    return {
        "総手術件数 (直近30日)": total_cases,
        "1日あたり平均件数": f"{daily_average:.1f}",
        "平日1日あたり平均件数": f"{avg_cases_per_weekday:.1f}",
        "手術室稼働率 (推定)": f"{utilization_rate:.1f}%"
    }