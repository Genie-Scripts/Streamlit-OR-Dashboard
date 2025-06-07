# utils/date_helpers.py
import pandas as pd
from datetime import datetime
import jpholiday  # requirements.txt に記載

def is_weekday(date):
    """
    祝日と年末年始（12/29～1/3）を除外した平日かどうかを判定する
    """
    if not isinstance(date, (datetime, pd.Timestamp)):
        return False
    if date.weekday() >= 5:  # 土日
        return False
    if jpholiday.is_holiday(date):  # 祝日
        return False
    if (date.month == 12 and date.day >= 29) or (date.month == 1 and date.day <= 3):  # 年末年始
        return False
    return True

def get_fiscal_year(date):
    """
    日付から年度を返す (4月始まり)
    """
    if date.month >= 4:
        return date.year
    else:
        return date.year - 1

def filter_by_period(df, latest_date, period_str):
    """
    期間文字列に基づいてDataFrameをフィルタリングする
    """
    if period_str == "直近30日":
        start_date = latest_date - pd.Timedelta(days=29)
    elif period_str == "直近90日":
        start_date = latest_date - pd.Timedelta(days=89)
    elif period_str == "直近180日":
        start_date = latest_date - pd.Timedelta(days=179)
    elif period_str == "今年度":
        start_date = pd.Timestamp(get_fiscal_year(latest_date), 4, 1)
    else: # 全期間
        return df

    return df[df['手術実施日_dt'] >= start_date]