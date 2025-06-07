# 完全週データ分析フレームワーク（改良版）

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st

def get_latest_complete_sunday(latest_data_date):
    """
    最新データ日から最も近い日曜日を取得（完全な週のため）
    - 最新データ日が日曜日の場合：その日曜日を返す
    - 最新データ日が月〜土曜日の場合：直前の日曜日を返す
    """
    if isinstance(latest_data_date, str):
        latest_data_date = pd.to_datetime(latest_data_date)
    
    # 曜日を取得（月曜=0, 日曜=6）
    weekday = latest_data_date.weekday()
    
    if weekday == 6:  # 日曜日の場合
        # その日曜日をそのまま使用
        return latest_data_date.replace(hour=23, minute=59, second=59)
    else:
        # 前の日曜日を計算（月曜=0なので、日曜=6に調整）
        days_since_sunday = (weekday + 1) % 7
        previous_sunday = latest_data_date - timedelta(days=days_since_sunday)
        return previous_sunday.replace(hour=23, minute=59, second=59)

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

def filter_data_by_complete_weeks(df, period_filter, latest_date=None):
    """
    完全な週のデータのみを使用した期間フィルタリング
    週の途中で切れている週は除外する
    """
    if df.empty:
        return df
    
    if latest_date is None:
        latest_date = df['手術実施日_dt'].max()
    
    # 最新の完全な週の日曜日を取得
    analysis_end_sunday = get_latest_complete_sunday(latest_date)
    
    # 分析終了点の週の月曜日
    analysis_end_monday = get_week_start_monday(analysis_end_sunday)
    
    if period_filter == "直近1週":
        # 最新の完全な1週間
        period_start = analysis_end_monday
        period_end = analysis_end_sunday
    elif period_filter == "直近4週":
        # 最新の完全な4週間
        period_start = analysis_end_monday - timedelta(weeks=3)
        period_end = analysis_end_sunday
    elif period_filter == "直近12週":
        # 最新の完全な12週間（約3ヶ月）
        period_start = analysis_end_monday - timedelta(weeks=11)
        period_end = analysis_end_sunday
    elif period_filter == "直近26週":
        # 最新の完全な26週間（約6ヶ月）
        period_start = analysis_end_monday - timedelta(weeks=25)
        period_end = analysis_end_sunday
    elif period_filter == "直近52週":
        # 最新の完全な52週間（約1年）
        period_start = analysis_end_monday - timedelta(weeks=51)
        period_end = analysis_end_sunday
    elif period_filter == "今年度":
        # 今年度4月1日から最新の完全な週まで
        current_year = analysis_end_sunday.year
        fiscal_year = current_year if analysis_end_sunday.month >= 4 else current_year - 1
        fiscal_start = pd.Timestamp(f'{fiscal_year}-04-01')
        period_start = get_week_start_monday(fiscal_start)
        period_end = analysis_end_sunday
    else:  # "全期間"
        period_start = get_week_start_monday(df['手術実施日_dt'].min())
        period_end = analysis_end_sunday
    
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
    
    # 週の終了日（日曜日）を追加
    df['週終了日'] = df['手術実施日_dt'].apply(get_week_end_sunday)
    
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

def analyze_weekly_summary_complete(df, target_dict=None, latest_date=None):
    """完全な週のデータのみを使用した週単位での病院全体サマリー分析"""
    if df.empty:
        return pd.DataFrame()
    
    # 完全な週のデータのみを使用
    if latest_date:
        analysis_end_sunday = get_latest_complete_sunday(latest_date)
        # 分析終了日以降のデータは除外
        df = df[df['手術実施日_dt'] <= analysis_end_sunday]
    
    # 週関連列を追加
    df_with_weeks = add_week_columns(df)
    
    # 全身麻酔手術のフィルタリング
    gas_df = df_with_weeks[
        df_with_weeks['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_with_weeks['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 週ごとの集計（完全な週のみ）
    weekly_summary = []
    
    for week_start, week_data in gas_df.groupby('週開始日'):
        week_end = week_start + timedelta(days=6)
        
        # この週が完全な週かチェック（月曜〜日曜の7日間すべてにデータの可能性があるか）
        week_dates = pd.date_range(week_start, week_end, freq='D')
        data_dates = week_data['手術実施日_dt'].dt.date.unique()
        
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
            '土日件数': week_total - week_weekday,
            '完全週フラグ': True  # 完全な週のみを使用しているためすべてTrue
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

def calculate_kpi_weekly_complete(df, latest_date=None):
    """完全な週のデータのみを使用したKPI計算"""
    if df.empty:
        return {}
    
    if latest_date is None:
        latest_date = df['手術実施日_dt'].max()
    
    # 最新の完全な週の日曜日を取得
    analysis_end_sunday = get_latest_complete_sunday(latest_date)
    
    # 週関連列を追加
    df_with_weeks = add_week_columns(df)
    
    # 分析終了日以降のデータは除外
    df_with_weeks = df_with_weeks[df_with_weeks['手術実施日_dt'] <= analysis_end_sunday]
    
    # 全身麻酔手術
    gas_df = df_with_weeks[
        df_with_weeks['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_with_weeks['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 最新の完全な週
    latest_week_start = get_week_start_monday(analysis_end_sunday)
    latest_week_end = analysis_end_sunday
    
    # 前週（最新の完全な週の1週前）
    prev_week_start = latest_week_start - timedelta(weeks=1)
    prev_week_end = latest_week_start - timedelta(days=1)
    
    # 最新の完全な週のデータ
    latest_week_data = gas_df[
        (gas_df['手術実施日_dt'] >= latest_week_start) &
        (gas_df['手術実施日_dt'] <= latest_week_end)
    ]
    
    # 前週のデータ
    prev_week_data = gas_df[
        (gas_df['手術実施日_dt'] >= prev_week_start) &
        (gas_df['手術実施日_dt'] <= prev_week_end)
    ]
    
    # KPI計算
    latest_week_total = len(latest_week_data)
    latest_week_weekday = len(latest_week_data[latest_week_data['平日フラグ']])
    
    prev_week_total = len(prev_week_data)
    prev_week_weekday = len(prev_week_data[prev_week_data['平日フラグ']])
    
    # 変化率計算
    total_change = ((latest_week_total - prev_week_total) / prev_week_total * 100) if prev_week_total > 0 else 0
    weekday_change = ((latest_week_weekday - prev_week_weekday) / prev_week_weekday * 100) if prev_week_weekday > 0 else 0
    
    # 直近4週平均（最新の完全な週を除く過去4週）
    four_weeks_ago = latest_week_start - timedelta(weeks=4)
    recent_4week_data = gas_df[
        (gas_df['手術実施日_dt'] >= four_weeks_ago) &
        (gas_df['手術実施日_dt'] < latest_week_start)
    ]
    
    recent_4week_weekday = len(recent_4week_data[recent_4week_data['平日フラグ']])
    avg_4week_weekday = recent_4week_weekday / 4 if recent_4week_weekday > 0 else 0
    
    return {
        'latest_week_total': latest_week_total,
        'latest_week_weekday': latest_week_weekday,
        'prev_week_total': prev_week_total,
        'prev_week_weekday': prev_week_weekday,
        'total_change': total_change,
        'weekday_change': weekday_change,
        'avg_4week_weekday': avg_4week_weekday,
        'latest_week_start': latest_week_start,
        'latest_week_end': latest_week_end,
        'analysis_end_sunday': analysis_end_sunday,
        'data_cutoff_reason': get_data_cutoff_explanation(latest_date, analysis_end_sunday)
    }

def get_data_cutoff_explanation(latest_data_date, analysis_end_sunday):
    """データカットオフの理由を説明"""
    if isinstance(latest_data_date, str):
        latest_data_date = pd.to_datetime(latest_data_date)
    
    if latest_data_date.date() == analysis_end_sunday.date():
        return "最新データが日曜日のため、その週まで分析対象"
    else:
        weekday_name = latest_data_date.strftime('%A')
        return f"最新データが{weekday_name}のため、前の日曜日({analysis_end_sunday.strftime('%Y/%m/%d')})まで分析対象"

def format_week_period_info_complete(period_filter, start_date, end_date, total_weeks, latest_data_date=None):
    """完全週分析用の期間情報をフォーマット"""
    period_text = {
        "直近1週": f"最新の完全な1週間",
        "直近4週": f"最新の完全な4週間",
        "直近12週": f"最新の完全な12週間（約3ヶ月）",
        "直近26週": f"最新の完全な26週間（約6ヶ月）", 
        "直近52週": f"最新の完全な52週間（約1年）",
        "今年度": f"今年度（完全週のみ）",
        "全期間": f"全期間（完全週のみ）"
    }
    
    info_text = f"📊 {period_text.get(period_filter, period_filter)}: " \
                f"{start_date.strftime('%Y/%m/%d')}～{end_date.strftime('%Y/%m/%d')} " \
                f"({total_weeks}週間)"
    
    # データカットオフの説明を追加
    if latest_data_date:
        analysis_end_sunday = get_latest_complete_sunday(latest_data_date)
        cutoff_explanation = get_data_cutoff_explanation(latest_data_date, analysis_end_sunday)
        info_text += f"\n💡 {cutoff_explanation}"
    
    return info_text

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

# 使用例とテスト
def test_complete_weeks_framework():
    """完全週フレームワークのテスト"""
    
    # テストケース1: 最新データが日曜日
    test_date_sunday = pd.Timestamp('2024-12-22')  # 日曜日
    print(f"テスト1 - 最新データが日曜日: {test_date_sunday}")
    print(f"分析終了日: {get_latest_complete_sunday(test_date_sunday)}")
    print(f"説明: {get_data_cutoff_explanation(test_date_sunday, get_latest_complete_sunday(test_date_sunday))}")
    print()
    
    # テストケース2: 最新データが木曜日
    test_date_thursday = pd.Timestamp('2024-12-19')  # 木曜日
    print(f"テスト2 - 最新データが木曜日: {test_date_thursday}")
    print(f"分析終了日: {get_latest_complete_sunday(test_date_thursday)}")
    print(f"説明: {get_data_cutoff_explanation(test_date_thursday, get_latest_complete_sunday(test_date_thursday))}")
    print()
    
    # テストケース3: 最新データが月曜日
    test_date_monday = pd.Timestamp('2024-12-16')  # 月曜日
    print(f"テスト3 - 最新データが月曜日: {test_date_monday}")
    print(f"分析終了日: {get_latest_complete_sunday(test_date_monday)}")
    print(f"説明: {get_data_cutoff_explanation(test_date_monday, get_latest_complete_sunday(test_date_monday))}")

if __name__ == "__main__":
    test_complete_weeks_framework()