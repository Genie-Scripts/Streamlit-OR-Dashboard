# analysis/weekly.py
import pandas as pd
import numpy as np

def _get_complete_week_filter(df):
    """完全週の最終日（日曜日）を特定し、それ以前のデータのみを返すフィルターを生成"""
    if df.empty:
        return pd.Series(True, index=df.index)
    
    latest_date = df['手術実施日_dt'].max()
    # 最新データが日曜日の場合、その週は「完全」とみなす
    if latest_date.dayofweek == 6:
        return pd.Series(True, index=df.index)
    
    # 最新データが月曜〜土曜の場合、その週は「不完全」とし、その前の日曜日までを分析対象とする
    else:
        latest_monday = latest_date - pd.to_timedelta(latest_date.dayofweek, unit='d')
        analysis_end_date = latest_monday - pd.to_timedelta(1, unit='d')
        return df['手術実施日_dt'] <= analysis_end_date

def get_summary(df, department=None, use_complete_weeks=True):
    """
    週単位でのサマリーを計算する。

    :param df: 前処理済みのDataFrame
    :param department: 診療科名（指定しない場合は全体）
    :param use_complete_weeks: 完全週データのみを使用するか
    :return: 週次サマリーDataFrame
    """
    if df.empty:
        return pd.DataFrame()

    # 全身麻酔データのみを対象
    target_df = df[df['is_gas_20min']].copy()

    if department:
        target_df = target_df[target_df['実施診療科'] == department]

    if use_complete_weeks:
        target_df = target_df[_get_complete_week_filter(target_df)]

    if target_df.empty:
        return pd.DataFrame()

    # 週ごとの件数
    weekly_counts = target_df.groupby('week_start').size().reset_index(name='週合計件数')

    # 週ごとの平日件数と実際に手術があった平日日数
    weekday_df = target_df[target_df['is_weekday']]
    if not weekday_df.empty:
        weekly_weekday_counts = weekday_df.groupby('week_start').size().reset_index(name='平日件数')
        actual_weekdays = weekday_df.groupby('week_start')['手術実施日_dt'].nunique().reset_index(name='実データ平日数')
        
        # マージ
        summary = pd.merge(weekly_counts, weekly_weekday_counts, on='week_start', how='left')
        summary = pd.merge(summary, actual_weekdays, on='week_start', how='left')
    else:
        summary = weekly_counts
        summary['平日件数'] = 0
        summary['実データ平日数'] = 0

    summary.fillna(0, inplace=True)
    summary[['平日件数', '実データ平日数']] = summary[['平日件数', '実データ平日数']].astype(int)

    # 平均件数
    summary['平日1日平均件数'] = np.where(
        summary['実データ平日数'] > 0,
        summary['平日件数'] / summary['実データ平日数'],
        0
    ).round(1)

    return summary.rename(columns={'week_start': '週'})[['週', '週合計件数', '平日件数', '実データ平日数', '平日1日平均件数']]