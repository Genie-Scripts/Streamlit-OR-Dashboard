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
    
# utils/date_helpers.py に追加する関数

def filter_by_complete_weeks(df, latest_date, num_weeks):
    """
    完全週単位でデータをフィルタリングする
    
    Args:
        df: データフレーム
        latest_date: 最新日付
        num_weeks: 週数（4, 12など）
    
    Returns:
        フィルタリングされたデータフレーム
    """
    from analysis import weekly
    
    # 分析終了日を前の日曜日に設定
    analysis_end_date = weekly.get_analysis_end_date(latest_date)
    
    if analysis_end_date is None:
        return df.iloc[0:0]  # 空のデータフレームを返す
    
    # 開始日を計算（月曜日起算）
    start_date = analysis_end_date - pd.Timedelta(days=(num_weeks * 7 - 1))
    
    return df[
        (df['手術実施日_dt'] >= start_date) & 
        (df['手術実施日_dt'] <= analysis_end_date)
    ]

def get_period_info(latest_date, num_weeks):
    """
    完全週単位の期間情報を取得する
    
    Args:
        latest_date: 最新日付
        num_weeks: 週数
    
    Returns:
        dict: 期間情報（開始日、終了日、実日数など）
    """
    from analysis import weekly
    
    analysis_end_date = weekly.get_analysis_end_date(latest_date)
    
    if analysis_end_date is None:
        return {}
    
    start_date = analysis_end_date - pd.Timedelta(days=(num_weeks * 7 - 1))
    
    # 平日数を計算
    weekdays = pd.bdate_range(start=start_date, end=analysis_end_date)
    
    return {
        'start_date': start_date,
        'end_date': analysis_end_date,
        'total_days': num_weeks * 7,
        'weekdays': len(weekdays),
        'weeks': num_weeks,
        'excluded_days': (latest_date - analysis_end_date).days
    }

def format_period_description(latest_date, num_weeks):
    """
    期間の説明文を生成する
    
    Args:
        latest_date: 最新日付
        num_weeks: 週数
    
    Returns:
        str: 期間説明文
    """
    info = get_period_info(latest_date, num_weeks)
    
    if not info:
        return "期間情報を取得できませんでした"
    
    description = (
        f"📊 分析期間: {info['start_date'].strftime('%Y/%m/%d')} ～ "
        f"{info['end_date'].strftime('%Y/%m/%d')} "
        f"({info['weeks']}週間 = {info['total_days']}日, 平日{info['weekdays']}日)"
    )
    
    if info['excluded_days'] > 0:
        description += f"\n💡 最新データ日の{latest_date.strftime('%Y/%m/%d')}から{info['excluded_days']}日分を除外して完全週単位で分析"
    
    return description