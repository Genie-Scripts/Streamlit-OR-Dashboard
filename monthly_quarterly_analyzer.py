# monthly_quarterly_analyzer.py
import pandas as pd
from holiday_handler import is_weekday
import calendar
from datetime import datetime

def analyze_monthly_summary(df):
    """月単位での全身麻酔手術件数を分析"""
    df = df.copy()
    df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
    df = df.dropna(subset=['手術実施日_dt'])

    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()

    if df_gas.empty:
        return pd.DataFrame()

    # 月初日を取得
    df_gas.loc[:, '月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    
    # 月ごとの集計
    monthly_counts = df_gas.groupby('月').size().reset_index(name='全日件数')
    
    # 平日のみの件数を計算
    df_gas_weekday = df_gas[df_gas['手術実施日_dt'].apply(is_weekday)]
    monthly_weekday_counts = df_gas_weekday.groupby('月').size().reset_index(name='平日件数')
    
    # マージ
    monthly_counts = pd.merge(monthly_counts, monthly_weekday_counts, on='月', how='left')
    monthly_counts['平日件数'] = monthly_counts['平日件数'].fillna(0).astype(int)

    # 月ごとの平日日数
    monthly_counts['平日日数'] = monthly_counts['月'].apply(calculate_weekdays_in_month)

    # 平日1日平均件数（小数点1桁）
    monthly_counts['平日1日平均件数'] = (monthly_counts['平日件数'] / monthly_counts['平日日数']).round(1)
    
    # 完全なデータのある月のみを対象とする
    min_date = df_gas['手術実施日_dt'].min()
    max_date = df_gas['手術実施日_dt'].max()
    
    first_month_start = pd.Timestamp(min_date.year, min_date.month, 1)
    
    # 最終月の末日を計算
    last_month = max_date.month
    last_year = max_date.year
    _, last_day = calendar.monthrange(last_year, last_month)
    last_month_end = pd.Timestamp(last_year, last_month, last_day)
    
    # 月の最終日まで完全にデータがある月のみを抽出
    if max_date.day != last_day:
        monthly_counts = monthly_counts[monthly_counts['月'] < pd.Timestamp(max_date.year, max_date.month, 1)]
    
    # 列順を整理
    monthly_counts = monthly_counts[['月', '全日件数', '平日件数', '平日日数', '平日1日平均件数']]
    
    return monthly_counts

def calculate_weekdays_in_month(month_start):
    """
    指定された月に含まれる平日の日数を計算
    
    Parameters:
    -----------
    month_start : pandas.Timestamp
        月の開始日
    
    Returns:
    --------
    int
        平日の日数
    """
    year = month_start.year
    month = month_start.month
    
    # 月の最終日を取得
    _, last_day = calendar.monthrange(year, month)
    
    # 月の全日を取得
    all_days = pd.date_range(start=month_start, end=pd.Timestamp(year, month, last_day))
    
    # 平日をカウント
    weekday_count = sum(is_weekday(day) for day in all_days)
    
    return weekday_count

def analyze_quarterly_summary(df):
    """四半期単位での全身麻酔手術件数を分析"""
    df = df.copy()
    df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
    df = df.dropna(subset=['手術実施日_dt'])

    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()

    if df_gas.empty:
        return pd.DataFrame()

    # 四半期の開始日を取得
    df_gas.loc[:, '四半期'] = df_gas['手術実施日_dt'].dt.to_period('Q').apply(lambda r: r.start_time)
    
    # 四半期ごとの集計
    quarterly_counts = df_gas.groupby('四半期').size().reset_index(name='全日件数')
    
    # 平日のみの件数を計算
    df_gas_weekday = df_gas[df_gas['手術実施日_dt'].apply(is_weekday)]
    quarterly_weekday_counts = df_gas_weekday.groupby('四半期').size().reset_index(name='平日件数')
    
    # マージ
    quarterly_counts = pd.merge(quarterly_counts, quarterly_weekday_counts, on='四半期', how='left')
    quarterly_counts['平日件数'] = quarterly_counts['平日件数'].fillna(0).astype(int)

    # 四半期ごとの平日日数
    quarterly_counts['平日日数'] = quarterly_counts['四半期'].apply(calculate_weekdays_in_quarter)

    # 平日1日平均件数（小数点1桁）
    quarterly_counts['平日1日平均件数'] = (quarterly_counts['平日件数'] / quarterly_counts['平日日数']).round(1)
    
    # 完全なデータのある四半期のみを対象とする
    min_date = df_gas['手術実施日_dt'].min()
    max_date = df_gas['手術実施日_dt'].max()
    
    # 最新四半期の終了日
    max_quarter = (max_date.month - 1) // 3 + 1
    max_quarter_end_month = max_quarter * 3
    max_quarter_year = max_date.year
    _, max_quarter_last_day = calendar.monthrange(max_quarter_year, max_quarter_end_month)
    last_quarter_end = pd.Timestamp(max_quarter_year, max_quarter_end_month, max_quarter_last_day)
    
    # 最新の四半期が完全でない場合は除外
    if max_date < last_quarter_end:
        max_quarter_start = pd.Timestamp(max_quarter_year, (max_quarter-1)*3+1, 1)
        quarterly_counts = quarterly_counts[quarterly_counts['四半期'] < max_quarter_start]
    
    # 四半期ラベルを追加
    quarterly_counts['四半期ラベル'] = quarterly_counts['四半期'].apply(format_quarter)
    
    # 列順を整理
    quarterly_counts = quarterly_counts[['四半期', '四半期ラベル', '全日件数', '平日件数', '平日日数', '平日1日平均件数']]
    
    return quarterly_counts

def calculate_weekdays_in_quarter(quarter_start):
    """
    指定された四半期に含まれる平日の日数を計算
    
    Parameters:
    -----------
    quarter_start : pandas.Timestamp
        四半期の開始日
    
    Returns:
    --------
    int
        平日の日数

    """
    year = quarter_start.year
    quarter = (quarter_start.month - 1) // 3 + 1
    
    # 四半期の開始月と終了月
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3
    
    # 四半期の開始日と終了日
    start_date = pd.Timestamp(year, start_month, 1)
    
    # 終了月の最終日を取得
    _, last_day = calendar.monthrange(year, end_month)
    end_date = pd.Timestamp(year, end_month, last_day)
    
    # 四半期の全日を取得
    all_days = pd.date_range(start=start_date, end=end_date)
    
    # 平日をカウント
    weekday_count = sum(is_weekday(day) for day in all_days)
    
    return weekday_count

def format_quarter(date):
    """
    日付から四半期ラベルを生成 (例: '2023年Q1')
    
    Parameters:
    -----------
    date : pandas.Timestamp
        日付
    
    Returns:
    --------
    str
        四半期ラベル
    """
    year = date.year
    quarter = (date.month - 1) // 3 + 1
    return f"{year}年Q{quarter}"

def analyze_monthly_department_summary(df, department):
    """診療科別の月単位分析"""
    df = df.copy()
    df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
    df = df.dropna(subset=['手術実施日_dt'])
    
    # 診療科でフィルタリング
    df = df[df['実施診療科'] == department]
    
    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()
    
    if df_gas.empty:
        return pd.DataFrame()
    
    # 月単位でまとめる
    df_gas.loc[:, '月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    monthly_counts = df_gas.groupby('月').size().reset_index(name='月合計件数')
    
    # 完全なデータのある月のみを対象とする（直近の月は含めない）
    if len(monthly_counts) > 0:
        max_date = df_gas['手術実施日_dt'].max()
        last_month = max_date.month
        last_year = max_date.year
        _, last_day = calendar.monthrange(last_year, last_month)
        
        # 最新月が完了していない場合は除外
        if max_date.day < last_day:
            monthly_counts = monthly_counts[monthly_counts['月'] < pd.Timestamp(max_date.year, max_date.month, 1)]
    
    return monthly_counts

def analyze_quarterly_department_summary(df, department):
    """診療科別の四半期単位分析"""
    df = df.copy()
    df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
    df = df.dropna(subset=['手術実施日_dt'])
    
    # 診療科でフィルタリング
    df = df[df['実施診療科'] == department]
    
    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()
    
    if df_gas.empty:
        return pd.DataFrame()
    
    # 四半期単位でまとめる
    df_gas.loc[:, '四半期'] = df_gas['手術実施日_dt'].dt.to_period('Q').apply(lambda r: r.start_time)
    quarterly_counts = df_gas.groupby('四半期').size().reset_index(name='四半期合計件数')
    
    # 四半期ラベルを追加
    quarterly_counts['四半期ラベル'] = quarterly_counts['四半期'].apply(format_quarter)
    
    # 完全なデータのある四半期のみを対象とする
    if len(quarterly_counts) > 0:
        max_date = df_gas['手術実施日_dt'].max()
        
        # 最新四半期の終了日を取得
        current_quarter = (max_date.month - 1) // 3 + 1
        quarter_end_month = current_quarter * 3
        quarter_year = max_date.year
        _, quarter_last_day = calendar.monthrange(quarter_year, quarter_end_month)
        quarter_end_date = pd.Timestamp(quarter_year, quarter_end_month, quarter_last_day)
        
        # 最終四半期が完了していない場合は除外
        if max_date < quarter_end_date:
            quarterly_counts = quarterly_counts[quarterly_counts['四半期'] < pd.Timestamp(max_date.year, (current_quarter-1)*3+1, 1)]
    
    return quarterly_counts