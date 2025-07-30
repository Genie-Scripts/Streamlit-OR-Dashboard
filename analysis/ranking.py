# analysis/ranking.py
"""
手術室稼働率計算、KPIサマリー、診療科パフォーマンス計算
- 期間定義の堅牢化
- 平均計算のバグ修正
- 達成率ソート機能の追加
"""
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import re
import unicodedata
from utils import date_helpers
from analysis import weekly

def _normalize_room_name(series):
    """手術室名の表記を正規化（「ＯＰ－１」→「OR1」など）"""
    if not pd.api.types.is_string_dtype(series):
        series = series.astype(str)
    
    def normalize_single_name(name):
        try:
            if pd.isna(name) or name == 'nan':
                return None
            name_str = str(name).strip()
            if not name_str:
                return None
            half_width_name = unicodedata.normalize('NFKC', name_str)
            op_pattern = re.match(r'[OＯ][PＰ][-－](\d+)([AＡBＢ]?)', half_width_name)
            if op_pattern:
                room_num = int(op_pattern.group(1))
                if 1 <= room_num <= 12 and room_num != 11:
                    return f"OR{room_num}"
            return None
        except Exception:
            return None
    return series.apply(normalize_single_name)

def _convert_to_datetime(time_series, date_series):
    """時刻文字列・数値をdatetimeオブジェクトに変換する"""
    result = pd.Series(pd.NaT, index=time_series.index)
    for idx in time_series.index:
        if pd.isna(time_series[idx]) or pd.isna(date_series[idx]):
            continue
        time_value = time_series[idx]
        date_obj = date_series[idx]
        try:
            if isinstance(time_value, (int, float)) and 0 <= time_value <= 1:
                total_seconds = time_value * 24 * 3600
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                result[idx] = datetime.combine(date_obj.date(), time(int(hours), int(minutes)))
                continue
            time_str = str(time_value).strip()
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) >= 2:
                    hour, minute = int(parts[0]), int(parts[1])
                    result[idx] = datetime.combine(date_obj.date(), time(hour, minute))
            elif time_str.isdigit() and len(time_str) == 4:
                hour, minute = int(time_str[:2]), int(time_str[2:])
                result[idx] = datetime.combine(date_obj.date(), time(hour, minute))
        except (ValueError, AttributeError, TypeError):
            continue
    return result

def calculate_operating_room_utilization(df, period_df):
    """手術室の稼働率を実計算する"""
    try:
        if period_df.empty or 'is_weekday' not in period_df.columns:
            return 0.0
        weekday_df = period_df[period_df['is_weekday']].copy()
        if weekday_df.empty:
            return 0.0
        room_col = next((c for c in weekday_df.columns if '手術室' in str(c)), None)
        start_col = next((c for c in weekday_df.columns if '入室' in str(c) and '時刻' in str(c)), None)
        end_col = next((c for c in weekday_df.columns if '退室' in str(c) and '時刻' in str(c)), None)
        if not all([room_col, start_col, end_col]):
            return 0.0
        target_rooms = [f'OR{i}' for i in range(1, 13) if i != 11]
        weekday_df['normalized_room'] = _normalize_room_name(weekday_df[room_col])
        filtered_df = weekday_df[weekday_df['normalized_room'].isin(target_rooms)].copy()
        if filtered_df.empty:
            return 0.0
        filtered_df['start_datetime'] = _convert_to_datetime(filtered_df[start_col], filtered_df['手術実施日_dt'])
        filtered_df['end_datetime'] = _convert_to_datetime(filtered_df[end_col], filtered_df['手術実施日_dt'])
        valid_time_df = filtered_df.dropna(subset=['start_datetime', 'end_datetime']).copy()
        if valid_time_df.empty:
            return 0.0
        overnight_mask = valid_time_df['end_datetime'] < valid_time_df['start_datetime']
        if overnight_mask.any():
            valid_time_df.loc[overnight_mask, 'end_datetime'] += timedelta(days=1)
        operation_start_time, operation_end_time = time(9, 0), time(17, 15)
        total_usage_minutes = 0
        for _, row in valid_time_df.iterrows():
            op_start = datetime.combine(row['手術実施日_dt'].date(), operation_start_time)
            op_end = datetime.combine(row['手術実施日_dt'].date(), operation_end_time)
            actual_start = max(row['start_datetime'], op_start)
            actual_end = min(row['end_datetime'], op_end)
            if actual_end > actual_start:
                total_usage_minutes += (actual_end - actual_start).total_seconds() / 60
        total_weekdays = len(pd.bdate_range(start=period_df['手術実施日_dt'].min(), end=period_df['手術実施日_dt'].max()))
        total_available_minutes = total_weekdays * 11 * 495
        if total_available_minutes > 0:
            utilization_rate = min((total_usage_minutes / total_available_minutes) * 100, 100.0)
            return utilization_rate
        return 0.0
    except Exception:
        return 0.0

def get_kpi_summary(df, analysis_base_date):
    """ダッシュボード用の主要KPIサマリーを計算する"""
    if df.empty: return {}
    analysis_end_date = weekly.get_analysis_end_date(analysis_base_date)
    if not analysis_end_date: return {}
    four_weeks_ago = analysis_end_date - pd.Timedelta(days=27)
    recent_df = df[(df['手術実施日_dt'] >= four_weeks_ago) & (df['手術実施日_dt'] <= analysis_end_date)]
    gas_df = recent_df[recent_df['is_gas_20min']]
    if gas_df.empty: return {}
    gas_weekday_df = gas_df[gas_df['is_weekday']]
    return {
        "全身麻酔手術件数 (直近4週)": len(gas_df),
        "全手術件数 (直近4週)": len(recent_df),
        "平日1日あたり全身麻酔手術件数": f"{len(gas_weekday_df) / 20.0:.1f}",
        "手術室稼働率 (全手術、平日のみ)": f"{calculate_operating_room_utilization(df, recent_df):.1f}%"
    }


def calculate_yearly_surgery_comparison(df, analysis_base_date):
    """
    全身麻酔手術件数と稼働率の年度比較を計算
    
    Args:
        df: 手術データ
        analysis_base_date: 現在の日付
        
    Returns:
        dict: 年度比較結果
    """
    try:
        if df.empty:
            return {}
        
        # 現在の年度判定（4月開始）
        if analysis_base_date.month >= 4:
            current_fiscal_year = analysis_base_date.year
        else:
            current_fiscal_year = analysis_base_date.year - 1
        
        # 今年度データ（4/1 - analysis_base_date）
        current_fiscal_start = pd.Timestamp(year=current_fiscal_year, month=4, day=1)
        current_fiscal_data = df[
            (df['手術実施日_dt'] >= current_fiscal_start) & 
            (df['手術実施日_dt'] <= analysis_base_date) &
            (df['is_gas_20min'])
        ]
        
        # 昨年度同期データ（昨年4/1 - 昨年同月日）
        prev_fiscal_start = pd.Timestamp(year=current_fiscal_year-1, month=4, day=1)
        try:
            prev_fiscal_end = pd.Timestamp(year=analysis_base_date.year-1, month=analysis_base_date.month, day=analysis_base_date.day)
        except ValueError:
            # 2月29日などの特殊ケース対応
            prev_fiscal_end = pd.Timestamp(year=analysis_base_date.year-1, month=analysis_base_date.month, day=28)
        
        prev_fiscal_data = df[
            (df['手術実施日_dt'] >= prev_fiscal_start) & 
            (df['手術実施日_dt'] <= prev_fiscal_end) &
            (df['is_gas_20min'])
        ]
        
        # 統計計算
        current_total = len(current_fiscal_data)
        prev_total = len(prev_fiscal_data)
        
        # 増減計算
        difference = current_total - prev_total
        growth_rate = (difference / prev_total * 100) if prev_total > 0 else 0
        
        # 年度末予測（現在のペースで推定）
        # 年度末予測（今年度の平日1日平均実績 × 今年度の総平日日数）
        # 今年度の平日における全身麻酔手術データを抽出
        current_fiscal_weekday_data = current_fiscal_data[current_fiscal_data['is_weekday']]
        
        # 今年度の開始日から今日までの平日日数を計算
        elapsed_weekdays = len(pd.bdate_range(start=current_fiscal_start, end=analysis_base_date))
        
        # 平日1日あたりの平均手術件数を計算
        avg_surgeries_per_weekday = len(current_fiscal_weekday_data) / elapsed_weekdays if elapsed_weekdays > 0 else 0
        
        # 今年度全体の平日日数を計算
        fiscal_year_end = pd.Timestamp(year=current_fiscal_year + 1, month=3, day=31)
        total_fiscal_weekdays = len(pd.bdate_range(start=current_fiscal_start, end=fiscal_year_end))
        
        # 新しい予測値を計算
        projected_total = int(avg_surgeries_per_weekday * total_fiscal_weekdays)

        
        # === 追加部分 Start ===
        # 前年度同期の稼働率を計算 (直近4週間の比較)
        analysis_end_date = weekly.get_analysis_end_date(analysis_base_date)
        four_weeks_ago = analysis_end_date - pd.Timedelta(days=27)

        # 前年度の同期間を定義
        prev_year_end_date = analysis_end_date - pd.DateOffset(years=1)
        prev_year_start_date = four_weeks_ago - pd.DateOffset(years=1)

        # 前年度同期のデータフレームをフィルタリング
        recent_df_prev_year = df[
            (df['手術実施日_dt'] >= prev_year_start_date) &
            (df['手術実施日_dt'] <= prev_year_end_date)
        ]

        # 前年度同期の稼働率を計算
        prev_year_utilization = calculate_operating_room_utilization(df, recent_df_prev_year)
        prev_year_utilization_str = f"{prev_year_utilization:.1f}%" if prev_year_utilization > 0 else "N/A"
        # === 追加部分 End ===
        
        return {
            "current_fiscal_total": current_total,
            "prev_fiscal_total": prev_total,
            "difference": difference,
            "growth_rate": growth_rate,
            "projected_annual": projected_total,
            "period_desc": f"{current_fiscal_year}年度",
            "comparison_period": f"{current_fiscal_start.strftime('%Y/%m/%d')} - {analysis_base_date.strftime('%Y/%m/%d')}",
            "fiscal_year": current_fiscal_year,
            "prev_year_utilization_rate": prev_year_utilization_str, # <<< 追加したデータ
        }
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"年度比較計算エラー: {e}")
        return {
            "current_fiscal_total": 0,
            "prev_fiscal_total": 0,
            "difference": 0,
            "growth_rate": 0,
            "projected_annual": 0,
            "period_desc": "データ不足",
            "comparison_period": "計算不可",
            "fiscal_year": datetime.now().year,
            "prev_year_utilization_rate": "N/A", # <<< エラー時もキーを追加
        }


def get_monthly_surgery_trend(df, fiscal_year):
    """
    月別手術件数トレンド取得
    
    Args:
        df: 手術データ
        fiscal_year: 対象年度
        
    Returns:
        list: 月別トレンドデータ
    """
    try:
        if df.empty:
            return []
        
        start_date = pd.Timestamp(year=fiscal_year, month=4, day=1)
        end_date = pd.Timestamp(year=fiscal_year+1, month=3, day=31)
        
        fiscal_data = df[
            (df['手術実施日_dt'] >= start_date) & 
            (df['手術実施日_dt'] <= end_date) &
            (df['is_gas_20min'])
        ].copy()
        
        if fiscal_data.empty:
            return []
        
        # 月別集計
        fiscal_data['年月'] = fiscal_data['手術実施日_dt'].dt.to_period('M')
        monthly_counts = fiscal_data.groupby('年月').size().reset_index(name='件数')
        
        # 4月から3月の順序で整理
        result = []
        for month in range(4, 16):  # 4-15月（翌年3月まで）
            actual_month = month if month <= 12 else month - 12
            actual_year = fiscal_year if month <= 12 else fiscal_year + 1
            
            period = pd.Period(year=actual_year, month=actual_month, freq='M')
            count = monthly_counts[monthly_counts['年月'] == period]['件数'].sum()
            
            month_name = f"{actual_month}月"
            if actual_month == analysis_base_date.month and actual_year == analysis_base_date.year:
                month_name += "（途中）"
            
            result.append({
                'month': month_name,
                'count': int(count),
                'is_current_fiscal': True,
                'period': period
            })
        
        return result
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"月別トレンド取得エラー: {e}")
        return []


def safe_yearly_comparison(df, analysis_base_date):
    """
    エラー耐性のある年度比較（ラッパー関数）
    """
    try:
        return calculate_yearly_surgery_comparison(df, analysis_base_date)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"安全な年度比較計算エラー: {e}")
        return {
            "current_fiscal_total": 0,
            "prev_fiscal_total": 0,
            "difference": 0,
            "growth_rate": 0,
            "projected_annual": 0,
            "period_desc": "データ不足",
            "comparison_period": "計算不可",
            "fiscal_year": datetime.now().year
        }


def get_enhanced_kpi_summary(df, latest_date):
    """
    年度比較を含む拡張KPIサマリー
    
    Args:
        df: 手術データ
        latest_date: 最新日付
        
    Returns:
        dict: 拡張KPIデータ
    """
    try:
        # 基本KPI取得
        basic_kpi = get_kpi_summary(df, latest_date)
        
        # 年度比較データ追加
        yearly_comparison = safe_yearly_comparison(df, latest_date)
        
        # 月別トレンド追加
        fiscal_year = yearly_comparison.get('fiscal_year', datetime.now().year)
        monthly_trend = get_monthly_surgery_trend(df, fiscal_year)
        
        # 統合データ返却
        return {
            **basic_kpi,
            'yearly_comparison': yearly_comparison,
            'monthly_trend': monthly_trend,
            'enhanced': True
        }
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"拡張KPIサマリー計算エラー: {e}")
        # フォールバックとして基本KPIのみ返却
        return get_kpi_summary(df, latest_date)

def get_department_performance_summary(df, target_dict, analysis_base_date):
    """診療科別パフォーマンスサマリーを取得（期間定義・平均計算・ソート修正版）"""
    if df.empty or not target_dict:
        return pd.DataFrame()

    # 1. 分析期間の正確な定義
    # <<< 修正箇所 >>>
    # weekly.pyの共通関数を使って、分析終了日を正しく取得します
    analysis_end_date = weekly.get_analysis_end_date(analysis_base_date)
    if not analysis_end_date:
        return pd.DataFrame() # 終了日が決まらない場合は空のDataFrameを返す

    start_date_filter = analysis_end_date - pd.Timedelta(days=27)  # 4週間前

    # 4週間のデータをフィルタリング
    four_weeks_df = df[
        (df['手術実施日_dt'] >= start_date_filter) &
        (df['手術実施日_dt'] <= analysis_end_date) &
        (df['is_gas_20min'])  # 全身麻酔のみ
    ]
    if four_weeks_df.empty:
        return pd.DataFrame()

    results = []
    for dept in target_dict.keys():
        dept_data = four_weeks_df[four_weeks_df['実施診療科'] == dept]

        # 2. 4週平均の計算
        # 常に4で割ることで、手術がない週も考慮した正確な平均を計算
        avg_weekly = len(dept_data) / 4.0

        # 3. 直近週実績の計算
        if not dept_data.empty:
            # 4週間データの中から最新の週を特定
            latest_week_start = dept_data['week_start'].max()
            latest_week_cases = len(dept_data[dept_data['week_start'] == latest_week_start])
        else:
            latest_week_cases = 0

        target = target_dict.get(dept, 0)
        achievement_rate = (latest_week_cases / target) * 100 if target > 0 else 0

        results.append({
            "診療科": dept,
            "4週平均": round(avg_weekly, 1),
            "直近週実績": latest_week_cases,
            "週次目標": target,
            "達成率(%)": round(achievement_rate, 1),
        })

    if not results:
        return pd.DataFrame()

    # 4. DataFrameに変換し、達成率でソート
    result_df = pd.DataFrame(results)
    return result_df.sort_values(by="達成率(%)", ascending=False)