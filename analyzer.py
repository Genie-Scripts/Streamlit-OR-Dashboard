# analyzer.py (月次集計修正版)
import pandas as pd
import numpy as np
import streamlit as st  # ← この行を追加
from holiday_handler import is_weekday
from dateutil.relativedelta import relativedelta # calculate_recent_averages で使用

@st.cache_data(ttl=3600)  # 1時間キャッシュ
def analyze_hospital_summary(df):
    """
    病院全体の全身麻酔手術件数を週単位で集計する関数
    
    Parameters:
    -----------
    df : pandas.DataFrame
        分析対象の手術データフレーム。必須列: ['手術実施日', '麻酔種別']
        
    Returns:
    --------
    pandas.DataFrame
        週単位集計結果。列: ['週', '全日件数', '平日件数', '平日日数', '平日1日平均件数']
    """
    # データのコピーは必要な時のみ
    if '手術実施日_dt' not in df.columns:
        df = df.copy()
        df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')

    # 集計前の重複チェック - 同一手術が複数回カウントされないようにする
    id_col_name = None # ID列名を保持する変数
    if all(col in df.columns for col in ["手術実施日", "実施診療科", "実施手術室", "入室時刻"]):
        print("重複ID作成のための十分なデータがあります。重複チェックを実行します。")
        df['unique_op_id'] = (
            df['手術実施日'].astype(str) + '_' +
            df['実施診療科'].astype(str) + '_' +
            df['実施手術室'].astype(str) + '_' +
            df['入室時刻'].astype(str)
        )
        id_col_name = 'unique_op_id' # ID列名を保存
        # 重複レコードを削除（最新のレコードを保持）
        records_before = len(df)
        df = df.drop_duplicates(subset=id_col_name, keep='last')
        records_after = len(df)

        if records_before > records_after:
            print(f"分析前に {records_before - records_after} 件の重複レコードを削除しました。")
    else:
        print("重複チェックに必要なカラムが不足しています。手術実施日と診療科のみでチェックします。")
        # 最低限の重複チェック
        if all(col in df.columns for col in ["手術実施日", "実施診療科"]):
            df['minimal_id'] = df['手術実施日'].astype(str) + '_' + df['実施診療科'].astype(str)
            id_col_name = 'minimal_id' # ID列名を保存
            records_before = len(df)
            df = df.drop_duplicates(subset=id_col_name, keep='last')
            records_after = len(df)

            if records_before > records_after:
                print(f"分析前に最低限のチェックで {records_before - records_after} 件の重複を削除しました。")

    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()

    if df_gas.empty:
        return pd.DataFrame()

    # 週単位でまとめる (月曜始まり) - 修正済み方法
    df_gas.loc[:, '週'] = df_gas['手術実施日_dt'] - pd.to_timedelta(df_gas['手術実施日_dt'].dt.dayofweek, unit='d')
    df_gas['週'] = df_gas['週'].dt.normalize()  # 時間部分を削除

    # 週ごとの集計 (重複を最小限に)
    # id_col_name は上で設定済み
    if id_col_name and id_col_name in df_gas.columns: # ID列が存在するか再確認
        unique_cases = df_gas[[id_col_name, '週', '手術実施日_dt']].drop_duplicates(subset=[id_col_name])
        weekly_counts = unique_cases.groupby('週').size().reset_index(name='全日件数')
    else:
        # IDがない場合は全レコードを使用（重複の可能性あり）
        print("警告: 集計に使用できる一意なID列が見つかりません。週次集計で重複が発生する可能性があります。")
        weekly_counts = df_gas.groupby('週').size().reset_index(name='全日件数')

    # 平日のみの件数を計算
    df_gas_weekday = df_gas[df_gas['手術実施日_dt'].apply(is_weekday)]

    if id_col_name and id_col_name in df_gas_weekday.columns: # ID列が存在するか再確認
        unique_weekday_cases = df_gas_weekday[[id_col_name, '週', '手術実施日_dt']].drop_duplicates(subset=[id_col_name])
        weekly_weekday_counts = unique_weekday_cases.groupby('週').size().reset_index(name='平日件数')
    else:
        weekly_weekday_counts = df_gas_weekday.groupby('週').size().reset_index(name='平日件数')

    # マージ
    weekly_counts = pd.merge(weekly_counts, weekly_weekday_counts, on='週', how='left')
    weekly_counts['平日件数'] = weekly_counts['平日件数'].fillna(0).astype(int)

    # ここが修正ポイント: 各週ごとに実際にデータがある平日の日数を計算
    weekly_actual_weekdays = df_gas_weekday.groupby([df_gas_weekday['手術実施日_dt'].dt.date]).size().reset_index()
    weekly_actual_weekdays['週'] = weekly_actual_weekdays['手術実施日_dt'] - pd.to_timedelta(pd.to_datetime(weekly_actual_weekdays['手術実施日_dt']).dt.dayofweek, unit='d')
    weekly_actual_weekdays['週'] = pd.to_datetime(weekly_actual_weekdays['週']).dt.normalize()
    actual_weekday_counts = weekly_actual_weekdays.groupby('週').size().reset_index(name='実データ平日数')
    
    # 実データの平日数をマージ
    weekly_counts = pd.merge(weekly_counts, actual_weekday_counts, on='週', how='left')
    weekly_counts['実データ平日数'] = weekly_counts['実データ平日数'].fillna(0).astype(int)
    
    # カレンダー上の平日日数も保持（従来の機能を維持）
    weekly_counts['平日日数'] = weekly_counts['週'].apply(lambda start_date: sum(
        is_weekday(d) for d in pd.date_range(start=start_date, periods=7)
    ))

    # 平日1日平均件数（小数点1桁）- 実データの平日数で割る
    weekly_counts['平日1日平均件数'] = np.where(weekly_counts['実データ平日数'] > 0,
                                    (weekly_counts['平日件数'] / weekly_counts['実データ平日数']).round(1),
                                    np.where(weekly_counts['平日日数'] > 0,  # 実データ平日数がない場合は従来の計算を使用
                                             (weekly_counts['平日件数'] / weekly_counts['平日日数']).round(1),
                                             0)) # 0除算回避

    # データの最小日と最大日を取得
    min_date = df_gas['手術実施日_dt'].min()
    max_date = df_gas['手術実施日_dt'].max()

    # 最初の完全な週の開始日（最初の月曜日）
    first_monday = min_date - pd.to_timedelta(min_date.dayofweek, unit='d')

    # 最後の完全な週の終了日（日曜日）
    last_sunday = max_date - pd.to_timedelta(max_date.dayofweek, unit='d') + pd.to_timedelta(6, unit='d')

    # 完全な週のみを抽出
    weekly_counts = weekly_counts[
        (weekly_counts['週'] >= first_monday) &
        (weekly_counts['週'] <= last_sunday - pd.to_timedelta(6, unit='d'))  # 週の開始日が最後の日曜日を超えない
    ]

    # 列順を整理
    weekly_counts = weekly_counts[['週', '全日件数', '平日件数', '平日日数', '平日1日平均件数']]

    return weekly_counts

def analyze_department_summary(df, department):
    """診療科別の全身麻酔手術件数を週単位で集計する関数"""
    df = df.copy()
    df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
    df = df.dropna(subset=['手術実施日_dt'])

    # 診療科でフィルタリング
    df = df[df['実施診療科'] == department]

    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()  # 明示的にコピーを作成して警告を回避

    if df_gas.empty:
        return pd.DataFrame()

    # --- 重複排除を追加 ---
    id_col_name = None
    if all(col in df_gas.columns for col in ["手術実施日", "実施診療科", "実施手術室", "入室時刻"]):
        df_gas['unique_op_id'] = (
            df_gas['手術実施日'].astype(str) + '_' +
            df_gas['実施診療科'].astype(str) + '_' +
            df_gas['実施手術室'].astype(str) + '_' +
            df_gas['入室時刻'].astype(str)
        )
        id_col_name = 'unique_op_id'
    elif '手術ID' in df_gas.columns:
         id_col_name = '手術ID'
    elif all(col in df_gas.columns for col in ["手術実施日", "実施診療科"]):
         df_gas['minimal_id'] = df_gas['手術実施日'].astype(str) + '_' + df_gas['実施診療科'].astype(str)
         id_col_name = 'minimal_id'

    if id_col_name:
        records_before = len(df_gas)
        df_gas = df_gas.drop_duplicates(subset=id_col_name, keep='last')
        records_after = len(df_gas)
        if records_before > records_after:
             print(f"診療科({department})週次集計前に {records_before - records_after} 件の重複を削除しました。")
    # --- 重複排除ここまで ---

    # 週単位でまとめる (月曜始まり) - 修正済み方法
    df_gas.loc[:, '週'] = df_gas['手術実施日_dt'] - pd.to_timedelta(df_gas['手術実施日_dt'].dt.dayofweek, unit='d')
    df_gas['週'] = df_gas['週'].dt.normalize()  # 時間部分を削除

    # 週合計件数を計算（重複排除後のデータで）
    # 各週ごとに実際にデータがある日を集計
    weekly_counts = df_gas.groupby('週').size().reset_index(name='週合計件数')
    
    # 各週ごとに実際にデータがある日数を計算
    daily_data = df_gas.groupby([df_gas['手術実施日_dt'].dt.date]).size().reset_index()
    daily_data['週'] = pd.to_datetime(daily_data['手術実施日_dt']) - pd.to_timedelta(pd.to_datetime(daily_data['手術実施日_dt']).dt.dayofweek, unit='d')
    daily_data['週'] = daily_data['週'].dt.normalize()
    actual_days_count = daily_data.groupby('週').size().reset_index(name='実データ日数')
    
    # 週ごとの実際のデータ日数を追加
    weekly_counts = pd.merge(weekly_counts, actual_days_count, on='週', how='left')
    weekly_counts['実データ日数'] = weekly_counts['実データ日数'].fillna(0).astype(int)
    
    # 平日のデータのみで同様の計算を行う
    df_gas_weekday = df_gas[df_gas['手術実施日_dt'].apply(is_weekday)]
    if not df_gas_weekday.empty:
        daily_weekday_data = df_gas_weekday.groupby([df_gas_weekday['手術実施日_dt'].dt.date]).size().reset_index()
        daily_weekday_data['週'] = pd.to_datetime(daily_weekday_data['手術実施日_dt']) - pd.to_timedelta(pd.to_datetime(daily_weekday_data['手術実施日_dt']).dt.dayofweek, unit='d')
        daily_weekday_data['週'] = daily_weekday_data['週'].dt.normalize()
        actual_weekday_count = daily_weekday_data.groupby('週').size().reset_index(name='実データ平日数')
        
        # 週ごとの実際の平日データ日数を追加
        weekly_counts = pd.merge(weekly_counts, actual_weekday_count, on='週', how='left')
        weekly_counts['実データ平日数'] = weekly_counts['実データ平日数'].fillna(0).astype(int)
    else:
        weekly_counts['実データ平日数'] = 0

    # データの最小日と最大日を取得
    min_date = df_gas['手術実施日_dt'].min()
    max_date = df_gas['手術実施日_dt'].max()

    # 最初の完全な週の開始日（最初の月曜日）
    first_monday = min_date - pd.to_timedelta(min_date.dayofweek, unit='d')

    # 最後の完全な週の終了日（日曜日）
    last_sunday = max_date - pd.to_timedelta(max_date.dayofweek, unit='d') + pd.to_timedelta(6, unit='d')

    # 完全な週のみを抽出
    weekly_counts = weekly_counts[
        (weekly_counts['週'] >= first_monday) &
        (weekly_counts['週'] <= last_sunday - pd.to_timedelta(6, unit='d'))  # 週の開始日が最後の日曜日を超えない
    ]

    # 新しい指標: 平日1日平均件数（実際のデータ日を使用）
    weekly_counts['平日1日平均件数'] = np.where(weekly_counts['実データ平日数'] > 0,
                                      (weekly_counts['週合計件数'] / weekly_counts['実データ平日数']).round(1),
                                      weekly_counts['週合計件数']) # 実データ平日数がない場合は合計を表示

    return weekly_counts

def calculate_recent_averages(df, category=None):
    """直近の様々な期間での全身麻酔件数の平均値を計算 (月次集計修正版)"""
    # 元のデータフレームを変更しないようにコピー
    df = df.copy()

    # 日付変換
    df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
    df = df.dropna(subset=['手術実施日_dt'])

    # 集計前の重複チェック
    id_col_name = None
    if all(col in df.columns for col in ["手術実施日", "実施診療科", "実施手術室", "入室時刻"]):
        df['unique_op_id'] = (
            df['手術実施日'].astype(str) + '_' +
            df['実施診療科'].astype(str) + '_' +
            df['実施手術室'].astype(str) + '_' +
            df['入室時刻'].astype(str)
        )
        id_col_name = 'unique_op_id'
    elif '手術ID' in df.columns:
         id_col_name = '手術ID'
    elif all(col in df.columns for col in ["手術実施日", "実施診療科"]):
         df['minimal_id'] = df['手術実施日'].astype(str) + '_' + df['実施診療科'].astype(str)
         id_col_name = 'minimal_id'

    if id_col_name:
        records_before = len(df)
        df = df.drop_duplicates(subset=id_col_name, keep='last')
        records_after = len(df)
        if records_before > records_after:
            print(f"平均計算前に {records_before - records_after} 件の重複レコードを削除しました。")
    else:
         print("警告: 平均計算のための重複チェック用ID列を作成できませんでした。")

    # 全身麻酔(20分以上)フィルタ
    df_gas = df[
        df['麻酔種別'].str.contains("全身麻酔", na=False) &
        df['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()

    # 申込区分フィルタ
    if category and category != "区別無し":
        df_gas = df_gas[df_gas["申込区分"] == category]

    if df_gas.empty:
        return pd.DataFrame()

    # 最新の手術日を基準日とする
    latest_date = df_gas["手術実施日_dt"].max()

    # 最新データ日から一番近い日曜日を見つける
    if latest_date.weekday() == 6:  # すでに日曜日の場合
        base_sunday = latest_date
    else:  # それ以外の場合は前の日曜日
        base_sunday = latest_date - pd.to_timedelta(latest_date.weekday() + 1, unit='d')

    # 各期間の計算
    result = []

    # 直近期間の計算 (修正: 実際のデータ期間で平均を計算)
    periods = [7, 14, 30, 60, 90]
    for p in periods:
        start_date = base_sunday - pd.to_timedelta(p - 1, unit='d')
        period_df = df_gas[(df_gas["手術実施日_dt"] >= start_date) & (df_gas["手術実施日_dt"] <= base_sunday)]

        # 全日件数 - 重複を排除 (id_col_name を使用)
        total_cases = 0
        if id_col_name and id_col_name in period_df.columns:
            total_cases = period_df[id_col_name].nunique()
        else:
            total_cases = len(period_df) # IDがない場合は全レコード

        # 平日のみの件数
        weekday_df = period_df[period_df["手術実施日_dt"].apply(is_weekday)]

        weekday_cases = 0
        if id_col_name and id_col_name in weekday_df.columns:
            weekday_cases = weekday_df[id_col_name].nunique()
        else:
            weekday_cases = len(weekday_df)

        # 期間内の実際にデータが存在する日付のリスト
        actual_dates = period_df["手術実施日_dt"].dt.date.unique()
        
        # 期間内の平日数を計算 (修正: 実データの日付範囲を取得)
        if len(actual_dates) > 0:
            # 実データの日付範囲
            actual_start = min(actual_dates)
            actual_end = max(actual_dates)
            
            # その範囲内の平日数を計算
            weekdays = sum(is_weekday(d) for d in pd.date_range(start=actual_start, end=actual_end))
        else:
            # データがない場合は全期間の平日数
            weekdays = sum(is_weekday(d) for d in pd.date_range(start=start_date, end=base_sunday))

        # 平日1日平均（小数点1桁）
        avg_cases = round(weekday_cases / weekdays, 1) if weekdays > 0 else 0

        result.append({
            "期間": f"直近{p}日",
            "全日件数": total_cases,
            "平日件数": weekday_cases,
            "平日数": weekdays,
            "平日1日平均件数": avg_cases
        })

    # 年度計算
    if latest_date.month >= 4:
        current_fy = latest_date.year
    else:
        current_fy = latest_date.year - 1

    last_fy = current_fy - 1

    # 昨年度平均
    last_fy_start = pd.Timestamp(f'{last_fy}-04-01')
    last_fy_end = pd.Timestamp(f'{last_fy + 1}-03-31')
    last_fy_df = df_gas[(df_gas["手術実施日_dt"] >= last_fy_start) & (df_gas["手術実施日_dt"] <= last_fy_end)]

    # 昨年度全日件数（重複排除）
    last_fy_cases = 0
    if id_col_name and id_col_name in last_fy_df.columns:
        last_fy_cases = last_fy_df[id_col_name].nunique()
    else:
        last_fy_cases = len(last_fy_df)

    # 平日のみの件数
    last_fy_weekday_df = last_fy_df[last_fy_df["手術実施日_dt"].apply(is_weekday)]

    last_fy_weekday_cases = 0
    if id_col_name and id_col_name in last_fy_weekday_df.columns:
        last_fy_weekday_cases = last_fy_weekday_df[id_col_name].nunique()
    else:
        last_fy_weekday_cases = len(last_fy_weekday_df)

    # 昨年度の実際にデータが存在する日付範囲
    if not last_fy_df.empty:
        actual_last_fy_start = last_fy_df["手術実施日_dt"].min().date()
        actual_last_fy_end = last_fy_df["手術実施日_dt"].max().date()
        last_fy_weekdays = sum(is_weekday(d) for d in pd.date_range(start=actual_last_fy_start, end=actual_last_fy_end))
    else:
        last_fy_weekdays = sum(is_weekday(d) for d in pd.date_range(start=last_fy_start, end=last_fy_end))
        
    last_fy_avg = round(last_fy_weekday_cases / last_fy_weekdays, 1) if last_fy_weekdays > 0 else 0

    result.append({
        "期間": f"{last_fy}年度平均",
        "全日件数": last_fy_cases,
        "平日件数": last_fy_weekday_cases,
        "平日数": last_fy_weekdays,
        "平日1日平均件数": last_fy_avg
    })

    # 昨年度同時期平均
    if latest_date >= pd.Timestamp(f'{current_fy}-04-01'):
        days_in_fy = (latest_date - pd.Timestamp(f'{current_fy}-04-01')).days + 1
    else: # 年度開始前（例：2024/3/1など）の場合、前年度の開始日から計算
        days_in_fy = (latest_date - pd.Timestamp(f'{last_fy}-04-01')).days + 1

    last_fy_same_end = pd.Timestamp(f'{last_fy}-04-01') + pd.to_timedelta(days_in_fy - 1, unit='d')
    last_fy_same_df = df_gas[(df_gas["手術実施日_dt"] >= last_fy_start) & (df_gas["手術実施日_dt"] <= last_fy_same_end)]

    # 昨年度同時期全日件数（重複排除）
    last_fy_same_cases = 0
    if id_col_name and id_col_name in last_fy_same_df.columns:
        last_fy_same_cases = last_fy_same_df[id_col_name].nunique()
    else:
        last_fy_same_cases = len(last_fy_same_df)

    # 平日のみの件数
    last_fy_same_weekday_df = last_fy_same_df[last_fy_same_df["手術実施日_dt"].apply(is_weekday)]

    last_fy_same_weekday_cases = 0
    if id_col_name and id_col_name in last_fy_same_weekday_df.columns:
        last_fy_same_weekday_cases = last_fy_same_weekday_df[id_col_name].nunique()
    else:
        last_fy_same_weekday_cases = len(last_fy_same_weekday_df)

    # 昨年度同時期の実際にデータが存在する日付範囲
    if not last_fy_same_df.empty:
        actual_last_fy_same_start = last_fy_same_df["手術実施日_dt"].min().date()
        actual_last_fy_same_end = last_fy_same_df["手術実施日_dt"].max().date()
        last_fy_same_weekdays = sum(is_weekday(d) for d in pd.date_range(start=actual_last_fy_same_start, end=actual_last_fy_same_end))
    else:
        last_fy_same_weekdays = sum(is_weekday(d) for d in pd.date_range(start=last_fy_start, end=last_fy_same_end))
        
    last_fy_same_avg = round(last_fy_same_weekday_cases / last_fy_same_weekdays, 1) if last_fy_same_weekdays > 0 else 0

    result.append({
        "期間": f"{last_fy}年度（同時期）",
        "全日件数": last_fy_same_cases,
        "平日件数": last_fy_same_weekday_cases,
        "平日数": last_fy_same_weekdays,
        "平日1日平均件数": last_fy_same_avg
    })

    # 今年度平均
    current_fy_start = pd.Timestamp(f'{current_fy}-04-01')
    current_fy_df = df_gas[(df_gas["手術実施日_dt"] >= current_fy_start) & (df_gas["手術実施日_dt"] <= latest_date)]

    # 今年度全日件数（重複排除）
    current_fy_cases = 0
    if id_col_name and id_col_name in current_fy_df.columns:
        current_fy_cases = current_fy_df[id_col_name].nunique()
    else:
        current_fy_cases = len(current_fy_df)

    # 平日のみの件数
    current_fy_weekday_df = current_fy_df[current_fy_df["手術実施日_dt"].apply(is_weekday)]

    current_fy_weekday_cases = 0
    if id_col_name and id_col_name in current_fy_weekday_df.columns:
        current_fy_weekday_cases = current_fy_weekday_df[id_col_name].nunique()
    else:
        current_fy_weekday_cases = len(current_fy_weekday_df)

    # 今年度の実際にデータが存在する日付範囲
    if not current_fy_df.empty:
        actual_current_fy_start = current_fy_df["手術実施日_dt"].min().date()
        actual_current_fy_end = current_fy_df["手術実施日_dt"].max().date()
        current_fy_weekdays = sum(is_weekday(d) for d in pd.date_range(start=actual_current_fy_start, end=actual_current_fy_end))
    else:
        current_fy_weekdays = sum(is_weekday(d) for d in pd.date_range(start=current_fy_start, end=latest_date))
        
    current_fy_avg = round(current_fy_weekday_cases / current_fy_weekdays, 1) if current_fy_weekdays > 0 else 0

    result.append({
        "期間": f"{current_fy}年度平均",
        "全日件数": current_fy_cases,
        "平日件数": current_fy_weekday_cases,
        "平日数": current_fy_weekdays,
        "平日1日平均件数": current_fy_avg
    })

    return pd.DataFrame(result)

def filter_data_by_period(df, period):
    """指定された期間でデータをフィルタリング (重複排除強化版)"""
    # ... (既存の関数内容は変更なし) ...
    # 元のデータフレームを変更しないようにコピー
    df = df.copy()

    # 重複排除
    id_col_name = None
    if all(col in df.columns for col in ["手術実施日", "実施診療科", "実施手術室", "入室時刻"]):
        df['unique_op_id'] = (
            df['手術実施日'].astype(str) + '_' +
            df['実施診療科'].astype(str) + '_' +
            df['実施手術室'].astype(str) + '_' +
            df['入室時刻'].astype(str)
        )
        id_col_name = 'unique_op_id'
    elif '手術ID' in df.columns:
         id_col_name = '手術ID'
    elif all(col in df.columns for col in ["手術実施日", "実施診療科"]):
         df['minimal_id'] = df['手術実施日'].astype(str) + '_' + df['実施診療科'].astype(str)
         id_col_name = 'minimal_id'

    if id_col_name:
        records_before = len(df)
        df = df.drop_duplicates(subset=id_col_name, keep='last')
        records_after = len(df)
        if records_before > records_after:
            print(f"期間フィルタ前に {records_before - records_after} 件の重複レコードを削除しました。")
    else:
         print("警告: 期間フィルタのための重複チェック用ID列を作成できませんでした。")


    # '手術実施日_dt' カラムが存在するか確認し、なければ作成
    if '手術実施日_dt' not in df.columns:
        if '手術実施日' in df.columns:
            df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
            df = df.dropna(subset=['手術実施日_dt'])
        else:
            # 日付カラムがない場合はエラーまたは空のDFを返すなどの処理が必要
            print("エラー: '手術実施日' または '手術実施日_dt' カラムが見つかりません。")
            return pd.DataFrame() # または raise ValueError

    # latest_date の取得前にデータが空でないか確認
    if df.empty or df['手術実施日_dt'].isnull().all():
        print("警告: フィルタリング可能な日付データがありません。")
        return pd.DataFrame()

    latest_date = df["手術実施日_dt"].max()

    if period == "全期間":
        return df
    elif period == "昨年度以降":
        # 最新データの年度を計算
        if latest_date.month >= 4:
            current_fy = latest_date.year
        else:
            current_fy = latest_date.year - 1
        last_fy_start = pd.Timestamp(f'{current_fy - 1}-04-01')
        return df[df["手術実施日_dt"] >= last_fy_start]
    elif period == "直近180日":
        start_date = latest_date - pd.Timedelta(days=179)
        return df[df["手術実施日_dt"] >= start_date]
    elif period == "直近90日":
        start_date = latest_date - pd.Timedelta(days=89)
        return df[df["手術実施日_dt"] >= start_date]

    return df