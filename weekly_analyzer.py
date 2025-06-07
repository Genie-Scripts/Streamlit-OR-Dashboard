# 週単位分析フレームワーク（月曜開始）

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st

def get_week_start_monday(date):
    """指定された日付が含まれる週の月曜日を取得"""
    if isinstance(date, str):
        date = pd.to_datetime(date)
    # 月曜日を0とする曜日計算
    days_since_monday = date.weekday()
    monday = date - timedelta(days=days_since_monday)
    return monday.normalize()  # 時刻を00:00:00にする

def get_week_end_sunday(date):
    """指定された日付が含まれる週の日曜日を取得"""
    monday = get_week_start_monday(date)
    sunday = monday + timedelta(days=6)
    return sunday.replace(hour=23, minute=59, second=59)

def filter_data_by_week_period(df, period_filter, latest_date=None):
    """週単位での期間フィルタリング（月曜開始）"""
    if df.empty:
        return df
    
    if latest_date is None:
        latest_date = df['手術実施日_dt'].max()
    
    # 最新データが含まれる週の日曜日を終了点とする
    period_end = get_week_end_sunday(latest_date)
    
    if period_filter == "直近1週":
        # 現在の週
        period_start = get_week_start_monday(latest_date)
    elif period_filter == "直近4週":
        # 直近4週間（現在の週を含む）
        period_start = get_week_start_monday(latest_date - timedelta(weeks=3))
    elif period_filter == "直近12週":
        # 直近12週間（約3ヶ月）
        period_start = get_week_start_monday(latest_date - timedelta(weeks=11))
    elif period_filter == "直近26週":
        # 直近26週間（約6ヶ月）
        period_start = get_week_start_monday(latest_date - timedelta(weeks=25))
    elif period_filter == "直近52週":
        # 直近52週間（約1年）
        period_start = get_week_start_monday(latest_date - timedelta(weeks=51))
    elif period_filter == "今年度":
        # 今年度4月1日から
        current_year = latest_date.year
        fiscal_year = current_year if latest_date.month >= 4 else current_year - 1
        fiscal_start = pd.Timestamp(f'{fiscal_year}-04-01')
        period_start = get_week_start_monday(fiscal_start)
    else:  # "全期間"
        period_start = get_week_start_monday(df['手術実施日_dt'].min())
    
    # フィルタリング
    filtered_df = df[
        (df['手術実施日_dt'] >= period_start) &
        (df['手術実施日_dt'] <= period_end)
    ].copy()
    
    return filtered_df

def add_week_columns(df):
    """データフレームに週関連の列を追加"""
    if df.empty:
        return df
    
    df = df.copy()
    
    # 週の開始日（月曜日）を追加
    df['週開始日'] = df['手術実施日_dt'].apply(get_week_start_monday)
    
    # 週番号（年-週番号形式）
    df['週番号'] = df['週開始日'].dt.strftime('%Y-W%U')
    
    # ISO週番号（月曜開始）
    df['ISO週番号'] = df['手術実施日_dt'].dt.isocalendar().week
    df['ISO年'] = df['手術実施日_dt'].dt.isocalendar().year
    df['ISO週ラベル'] = df['ISO年'].astype(str) + '-W' + df['ISO週番号'].astype(str).str.zfill(2)
    
    # 曜日（月曜=0, 日曜=6）
    df['曜日番号'] = df['手術実施日_dt'].dt.weekday
    df['曜日名'] = df['手術実施日_dt'].dt.day_name()
    
    # 平日フラグ
    df['平日フラグ'] = df['曜日番号'] < 5
    
    return df

def analyze_weekly_summary(df, target_dict=None):
    """週単位での病院全体サマリー分析"""
    if df.empty:
        return pd.DataFrame()
    
    # 週関連列を追加
    df_with_weeks = add_week_columns(df)
    
    # 全身麻酔手術のフィルタリング
    gas_df = df_with_weeks[
        df_with_weeks['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_with_weeks['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 平日のみのデータ
    weekday_gas_df = gas_df[gas_df['平日フラグ']]
    
    # 週ごとの集計
    weekly_summary = []
    
    for week_start, week_data in gas_df.groupby('週開始日'):
        week_end = week_start + timedelta(days=6)
        
        # 週全体の件数
        week_total = len(week_data)
        
        # 平日のみの件数
        weekday_data = week_data[week_data['平日フラグ']]
        week_weekday = len(weekday_data)
        
        # 平日日数（月〜金）
        weekday_count = len([d for d in pd.date_range(week_start, week_end) 
                           if d.weekday() < 5])
        
        # 平日1日平均
        daily_avg = week_weekday / weekday_count if weekday_count > 0 else 0
        
        weekly_summary.append({
            '週開始日': week_start,
            '週終了日': week_end,
            '週ラベル': f"{week_start.strftime('%m/%d')}～{week_end.strftime('%m/%d')}",
            'ISO週ラベル': week_data['ISO週ラベル'].iloc[0],
            '週総件数': week_total,
            '平日件数': week_weekday,
            '平日日数': weekday_count,
            '平日1日平均': round(daily_avg, 1),
            '土日件数': week_total - week_weekday
        })
    
    summary_df = pd.DataFrame(weekly_summary)
    summary_df = summary_df.sort_values('週開始日')
    
    # 目標との比較
    if target_dict:
        total_target = sum(target_dict.values())
        summary_df['目標件数'] = total_target
        summary_df['達成率'] = (summary_df['平日件数'] / total_target * 100).round(1)
        summary_df['目標差'] = summary_df['平日件数'] - total_target
    
    return summary_df

def analyze_department_weekly_summary(df, department, target_dict=None):
    """特定診療科の週単位サマリー分析"""
    if df.empty:
        return pd.DataFrame()
    
    # 診療科でフィルタリング
    dept_df = df[df['実施診療科'] == department].copy()
    
    if dept_df.empty:
        return pd.DataFrame()
    
    # 週関連列を追加
    df_with_weeks = add_week_columns(dept_df)
    
    # 全身麻酔手術のフィルタリング
    gas_df = df_with_weeks[
        df_with_weeks['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_with_weeks['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 週ごとの集計
    weekly_summary = []
    
    for week_start, week_data in gas_df.groupby('週開始日'):
        week_end = week_start + timedelta(days=6)
        
        # 平日のみの件数
        weekday_data = week_data[week_data['平日フラグ']]
        week_weekday = len(weekday_data)
        
        # 平日日数
        weekday_count = len([d for d in pd.date_range(week_start, week_end) 
                           if d.weekday() < 5])
        
        # 平日1日平均
        daily_avg = week_weekday / weekday_count if weekday_count > 0 else 0
        
        weekly_summary.append({
            '週開始日': week_start,
            '週終了日': week_end,
            '週ラベル': f"{week_start.strftime('%m/%d')}～{week_end.strftime('%m/%d')}",
            'ISO週ラベル': week_data['ISO週ラベル'].iloc[0],
            '診療科': department,
            '週件数': week_weekday,
            '平日日数': weekday_count,
            '平日1日平均': round(daily_avg, 1)
        })
    
    summary_df = pd.DataFrame(weekly_summary)
    summary_df = summary_df.sort_values('週開始日')
    
    # 目標との比較
    if target_dict and department in target_dict:
        dept_target = target_dict[department]
        summary_df['目標件数'] = dept_target
        summary_df['達成率'] = (summary_df['週件数'] / dept_target * 100).round(1)
        summary_df['目標差'] = summary_df['週件数'] - dept_target
    
    return summary_df

def calculate_kpi_weekly(df, latest_date=None):
    """週単位でのKPI計算"""
    if df.empty:
        return {}
    
    if latest_date is None:
        latest_date = df['手術実施日_dt'].max()
    
    # 週関連列を追加
    df_with_weeks = add_week_columns(df)
    
    # 全身麻酔手術
    gas_df = df_with_weeks[
        df_with_weeks['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_with_weeks['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 現在の週
    current_week_start = get_week_start_monday(latest_date)
    current_week_end = get_week_end_sunday(latest_date)
    
    # 前週
    prev_week_start = current_week_start - timedelta(weeks=1)
    prev_week_end = current_week_start - timedelta(days=1)
    
    # 現在の週のデータ
    current_week_data = gas_df[
        (gas_df['手術実施日_dt'] >= current_week_start) &
        (gas_df['手術実施日_dt'] <= current_week_end)
    ]
    
    # 前週のデータ
    prev_week_data = gas_df[
        (gas_df['手術実施日_dt'] >= prev_week_start) &
        (gas_df['手術実施日_dt'] <= prev_week_end)
    ]
    
    # KPI計算
    current_week_total = len(current_week_data)
    current_week_weekday = len(current_week_data[current_week_data['平日フラグ']])
    
    prev_week_total = len(prev_week_data)
    prev_week_weekday = len(prev_week_data[prev_week_data['平日フラグ']])
    
    # 変化率計算
    total_change = ((current_week_total - prev_week_total) / prev_week_total * 100) if prev_week_total > 0 else 0
    weekday_change = ((current_week_weekday - prev_week_weekday) / prev_week_weekday * 100) if prev_week_weekday > 0 else 0
    
    # 直近4週平均
    four_weeks_ago = current_week_start - timedelta(weeks=4)
    recent_4week_data = gas_df[
        (gas_df['手術実施日_dt'] >= four_weeks_ago) &
        (gas_df['手術実施日_dt'] < current_week_start)
    ]
    
    recent_4week_weekday = len(recent_4week_data[recent_4week_data['平日フラグ']])
    avg_4week_weekday = recent_4week_weekday / 4 if recent_4week_weekday > 0 else 0
    
    return {
        'current_week_total': current_week_total,
        'current_week_weekday': current_week_weekday,
        'prev_week_total': prev_week_total,
        'prev_week_weekday': prev_week_weekday,
        'total_change': total_change,
        'weekday_change': weekday_change,
        'avg_4week_weekday': avg_4week_weekday,
        'current_week_start': current_week_start,
        'current_week_end': current_week_end
    }

def get_week_period_options():
    """週単位の期間選択オプションを取得"""
    return [
        "直近1週",
        "直近4週", 
        "直近12週",
        "直近26週",
        "直近52週",
        "今年度",
        "全期間"
    ]

def format_week_period_info(period_filter, start_date, end_date, total_weeks):
    """期間情報を週単位でフォーマット"""
    period_text = {
        "直近1週": f"現在の週",
        "直近4週": f"直近4週間",
        "直近12週": f"直近12週間（約3ヶ月）",
        "直近26週": f"直近26週間（約6ヶ月）", 
        "直近52週": f"直近52週間（約1年）",
        "今年度": f"今年度",
        "全期間": f"全期間"
    }
    
    return f"📊 {period_text.get(period_filter, period_filter)}: " \
           f"{start_date.strftime('%Y/%m/%d')}～{end_date.strftime('%Y/%m/%d')} " \
           f"({total_weeks}週間)"

# 使用例とテスト
def test_weekly_framework():
    """週単位フレームワークのテスト"""
    # テスト用データ
    test_date = pd.Timestamp('2024-12-19')  # 木曜日
    
    print(f"テスト日付: {test_date} ({test_date.strftime('%A')})")
    print(f"週開始日（月曜）: {get_week_start_monday(test_date)}")
    print(f"週終了日（日曜）: {get_week_end_sunday(test_date)}")
    
    # 期間オプション
    print("\n利用可能な期間オプション:")
    for option in get_week_period_options():
        print(f"- {option}")

if __name__ == "__main__":
    test_weekly_framework()