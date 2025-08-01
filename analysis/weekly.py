# analysis/weekly.py (修正版)
import pandas as pd
import numpy as np

def get_analysis_end_date(base_date: pd.Timestamp) -> pd.Timestamp:
    """
    分析の最終日（基準日以前の、完了した最新の週の最終日曜日）を計算する
    
    Args:
        base_date (pd.Timestamp): 分析の基準となる日
    
    Returns:
        pd.Timestamp: 分析対象となる期間の最終日（日曜日）
    """
    if pd.isna(base_date):
        return None
    
    # dayofweek: 月曜日=0, ..., 日曜日=6
    # 基準日が日曜日 (6) なら、その日が分析終了日
    if base_date.dayofweek == 6:
        return base_date
    # 月曜〜土曜の場合、その前の日曜日を分析終了日とする
    else:
        return base_date - pd.to_timedelta(base_date.dayofweek + 1, unit='d')
        
def get_summary(df, analysis_base_date, department=None, use_complete_weeks=True):
    """
    週単位でのサマリーを計算する。
    """
    if df.empty:
        return pd.DataFrame()

    target_df = df[df['is_gas_20min']].copy()

    if department:
        target_df = target_df[target_df['実施診療科'] == department]

    if use_complete_weeks:
        # 修正箇所: latest_date を使うのをやめ、引数の analysis_base_date を使う
        # latest_date = df['手術実施日_dt'].max()  <- この行を削除
        analysis_end_date = get_analysis_end_date(analysis_base_date) # 引数で受け取った日付を使用
        if analysis_end_date:
            target_df = target_df[target_df['手術実施日_dt'] <= analysis_end_date]
    
    if target_df.empty:
        return pd.DataFrame()

    weekly_counts = target_df.groupby('week_start').size().reset_index(name='週合計件数')
    
    weekday_df = target_df[target_df['is_weekday']]
    if not weekday_df.empty:
        weekly_weekday_counts = weekday_df.groupby('week_start').size().reset_index(name='平日件数')
        actual_weekdays = weekday_df.groupby('week_start')['手術実施日_dt'].nunique().reset_index(name='実データ平日数')
        summary = pd.merge(weekly_counts, weekly_weekday_counts, on='week_start', how='left')
        summary = pd.merge(summary, actual_weekdays, on='week_start', how='left')
    else:
        summary = weekly_counts
        summary['平日件数'] = 0
        summary['実データ平日数'] = 0

    summary.fillna(0, inplace=True)
    summary[['平日件数', '実データ平日数']] = summary[['平日件数', '実データ平日数']].astype(int)

    summary['平日1日平均件数'] = np.where(
        summary['実データ平日数'] > 0,
        summary['平日件数'] / summary['実データ平日数'],
        0
    ).round(1)

    return summary.rename(columns={'week_start': '週'})[['週', '週合計件数', '平日件数', '実データ平日数', '平日1日平均件数']]

def get_weekly_trend_data(df: pd.DataFrame, analysis_base_date: pd.Timestamp, weeks: int = 8) -> list:
    """
    過去N週間の週別推移データを取得（全身麻酔手術件数）
    
    Args:
        df: 手術データ
        analysis_base_date: 最新日付
        weeks: 取得する週数（デフォルト8週）
    
    Returns:
        list: 週別推移データ
    """
    try:
        if df.empty:
            return []

        # 日付列をdatetime型に変換
        df['手術実施日_dt'] = pd.to_datetime(df['手術実施日_dt'], errors='coerce')
        df.dropna(subset=['手術実施日_dt'], inplace=True)
        
        # 分析終了日を取得
        analysis_end_date = get_analysis_end_date(analysis_base_date)
        if not analysis_end_date:
            return []
        
        # 過去N週間の期間を計算
        start_date = analysis_end_date - pd.Timedelta(weeks=weeks-1, days=6)  # N週間前の月曜日
        
        # 期間内のデータをフィルタリング
        period_df = df[
            (df['手術実施日_dt'] >= start_date) &
            (df['手術実施日_dt'] <= analysis_end_date)
        ].copy()
        
        if period_df.empty:
            return []
        
        # 全身麻酔手術のみをフィルタリング
        gas_df = period_df[period_df['is_gas_20min'] == True]
        
        result = []
        
        # 各週のデータを計算
        for i in range(weeks):
            week_start = analysis_end_date - pd.Timedelta(weeks=weeks-1-i, days=6)
            week_end = week_start + pd.Timedelta(days=6)
            
            # 当該週のデータ
            week_gas_df = gas_df[
                (gas_df['手術実施日_dt'] >= week_start) &
                (gas_df['手術実施日_dt'] <= week_end)
            ]
            
            week_name = f"{week_start.month}/{week_start.day}-{week_end.month}/{week_end.day}"
            is_current_week = (week_end == analysis_end_date)
            
            result.append({
                'week': f"{week_start.year}-W{week_start.isocalendar()[1]:02d}",
                'week_name': week_name,
                'week_start': week_start,
                'week_end': week_end,
                'count': int(len(week_gas_df)),
                'is_current_week': is_current_week
            })
        
        return result
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"週別トレンドデータ取得エラー: {e}")
        return []

def get_weekly_target_value() -> int:
    """週次目標値を取得"""
    return 95  # 週次目標ライン