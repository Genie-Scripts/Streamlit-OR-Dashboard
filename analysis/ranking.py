# analysis/ranking.py (最終デバッグ版)
import pandas as pd
import numpy as np
from datetime import datetime, time
from utils import date_helpers
from analysis import weekly

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★ テストのため、この関数の内部を完全に書き換えます ★
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
def calculate_operating_room_utilization(df):
    """
    [デバッグ用] 常に固定値 12.3 を返すテスト関数
    """
    print("--- [ranking.py] <<デバッグ版>> calculate_operating_room_utilization が呼び出されました ---")
    return 12.3

def get_kpi_summary(df, latest_date):
    """
    ダッシュボード用の主要KPIサマリーを計算する。
    """
    if df.empty: return {}
    recent_df = date_helpers.filter_by_period(df, latest_date, "直近30日")
    
    # ★デバッグ版の稼働率計算関数を呼び出す
    utilization_rate = calculate_operating_room_utilization(recent_df)
    
    gas_df = recent_df[recent_df['is_gas_20min']]
    if gas_df.empty: 
        return {
            "総手術件数 (直近30日)": 0, "1日あたり平均件数": "0.0",
            "平日1日あたり平均件数": "0.0", "手術室稼働率": f"{utilization_rate:.1f}%"
        }

    total_cases = len(gas_df)
    days_in_period = (gas_df['手術実施日_dt'].max() - gas_df['手術実施日_dt'].min()).days + 1
    daily_average = total_cases / days_in_period if days_in_period > 0 else 0
    
    weekday_df = gas_df[gas_df['is_weekday']]
    total_operating_days = weekday_df['手術実施日_dt'].nunique()
    avg_cases_per_weekday = len(weekday_df) / total_operating_days if total_operating_days > 0 else 0
    
    return {
        "総手術件数 (直近30日)": total_cases,
        "1日あたり平均件数": f"{daily_average:.1f}",
        "平日1日あたり平均件数": f"{avg_cases_per_weekday:.1f}",
        "手術室稼働率": f"{utilization_rate:.1f}%"
    }

# ...(他の関数は変更なし)...
def calculate_achievement_rates(df, target_dict):
    # ...
    return pd.DataFrame()

def get_department_performance_summary(df, target_dict, latest_date):
    # ...
    return pd.DataFrame()

def calculate_cumulative_cases(df, target_weekly_cases):
    # ...
    return pd.DataFrame()