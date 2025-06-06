# utils.py (新規作成)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import calendar

def is_weekday(date):
    """与えられた日付が平日かどうかを判定（祝日と年末年始を除外）"""
    try:
        import jpholiday
        
        if date.weekday() >= 5:  # 土日
            return False
        if jpholiday.is_holiday(date):  # 祝日
            return False
        if (date.month == 12 and date.day >= 29) or (date.month == 1 and date.day <= 3):  # 年末年始
            return False
        return True
    except ImportError:
        # jpholidayが利用できない場合は単純に平日判定
        return date.weekday() < 5

def calculate_weekdays_in_period(start_date, end_date):
    """指定された期間に含まれる平日の日数を計算"""
    try:
        all_days = pd.date_range(start=start_date, end=end_date)
        weekday_count = sum(is_weekday(day) for day in all_days)
        return weekday_count
    except Exception as e:
        print(f"平日計算中にエラーが発生: {e}")
        return 0

def get_fiscal_year(date):
    """指定された日付の年度を返す（4月始まり）"""
    if date.month >= 4:
        return date.year
    else:
        return date.year - 1

def get_fiscal_year_range(fiscal_year):
    """指定された年度の開始日と終了日を返す"""
    start_date = pd.Timestamp(fiscal_year, 4, 1)
    end_date = pd.Timestamp(fiscal_year + 1, 3, 31)
    return start_date, end_date

def format_date_range(start_date, end_date):
    """日付範囲を「YYYY/MM/DD〜YYYY/MM/DD」の形式でフォーマット"""
    start_str = start_date.strftime('%Y/%m/%d')
    end_str = end_date.strftime('%Y/%m/%d')
    return f"{start_str}〜{end_str}"

def calculate_achievement_rate(actual, target):
    """目標達成率を計算（%）"""
    if target is None or target == 0:
        return 0
    return (actual / target) * 100

def filter_anesthesia_data(df, department=None):
    """全身麻酔（20分以上）のデータをフィルタリング"""
    # 前処理済みデータならフラグを使用
    if 'is_gas_20min' in df.columns:
        filtered_df = df[df['is_gas_20min']]
    else:
        filtered_df = df[
            df['麻酔種別'].str.contains("全身麻酔", na=False) &
            df['麻酔種別'].str.contains("20分以上", na=False)
        ]
    
    # 診療科でさらにフィルタリング
    if department is not None and department != "全診療科":
        filtered_df = filtered_df[filtered_df['実施診療科'] == department]
    
    return filtered_df

def safe_division(numerator, denominator, default=0):
    """ゼロ除算を回避する除算関数"""
    if denominator is None or denominator == 0:
        return default
    return numerator / denominator