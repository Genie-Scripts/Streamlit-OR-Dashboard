# hospital_prediction.py (月次集計修正版)
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
import calendar
from datetime import datetime, timedelta
import style_config as sc

try:
    from holiday_handler import is_weekday
except ImportError:
    print("Warning: holiday_handler.py not found. Assuming standard weekdays.")
    def is_weekday(date):
        return date.weekday() < 5

def calculate_weekdays_in_month(month_start):
    """指定された月に含まれる平日の日数を計算"""
    year = month_start.year; month = month_start.month
    try:
        _, last_day = calendar.monthrange(year, month)
        all_days = pd.date_range(start=month_start, end=pd.Timestamp(year, month, last_day))
        weekday_count = sum(is_weekday(day) for day in all_days)
    except ValueError:
        weekday_count = 20 # Fallback
    return weekday_count

def calculate_weekdays_in_period(start_date, end_date):
    """指定された期間に含まれる平日の日数を計算"""
    try:
        all_days = pd.date_range(start=start_date, end=end_date)
        weekday_count = sum(is_weekday(day) for day in all_days)
        return weekday_count
    except ValueError:
        print(f"Warning: Invalid date range for weekday calculation: {start_date} to {end_date}")
        return 0

def predict_hospital_future(df, period_end_date=None, prediction_period='fiscal_year', model_type='hwes', custom_params=None):
    """病院全体の将来予測を行う関数 (月次集計修正版)"""
    df = df.copy(); df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce'); df = df.dropna(subset=['手術実施日_dt'])
    df_gas = df[df['麻酔種別'].str.contains("全身麻酔", na=False) & df['麻酔種別'].str.contains("20分以上", na=False)].copy()
    if df_gas.empty: return pd.DataFrame(), None, {"message": "全身麻酔(20分以上)のデータが見つかりません"}

    # 月次集計 (平日1日平均) - 修正版
    df_gas.loc[:, '月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    df_gas.loc[:, '日'] = df_gas['手術実施日_dt'].dt.day  # 日にちも追加
    
    # 集計対象の期間を得る
    min_date = df_gas['手術実施日_dt'].min()
    max_date = df_gas['手術実施日_dt'].max()
    unique_months = df_gas['月'].unique()
    
    # 月ごとの集計結果を格納するリスト
    monthly_results = []
    
    for month_start in unique_months:
        # 月の最終日
        year = month_start.year
        month = month_start.month
        _, last_day = calendar.monthrange(year, month)
        month_end = pd.Timestamp(year, month, last_day)
        
        # この月のデータ
        month_data = df_gas[df_gas['月'] == month_start]
        
        if month_start.year == max_date.year and month_start.month == max_date.month:
            # 最新月の場合は、データが存在する最終日までの期間で計算
            actual_month_end = max_date
        else:
            # それ以外の月は月末まで
            actual_month_end = month_end
            
        # この月の実績値（全日と平日）
        all_days_count = len(month_data)
        weekday_data = month_data[month_data['手術実施日_dt'].apply(is_weekday)]
        weekday_count = len(weekday_data)
        
        # この月の期間に含まれる平日数 (修正: 実際にデータがある期間のみ)
        month_first_day = month_start
        if month_start.year == min_date.year and month_start.month == min_date.month:
            # 最初の月は、データが存在する最初の日から計算
            month_first_day = min_date
        
        # 該当期間の平日数を計算
        weekdays_in_period = calculate_weekdays_in_period(month_first_day, actual_month_end)
        
        # 平日1日平均件数
        avg_per_weekday = 0
        if weekdays_in_period > 0:
            avg_per_weekday = (weekday_count / weekdays_in_period)
        
        # 結果を格納
        monthly_results.append({
            '月': month_start,
            '全日件数': all_days_count,
            '平日件数': weekday_count,
            '平日日数': weekdays_in_period,
            '平日1日平均件数': round(avg_per_weekday, 1)
        })
    
    # 結果をデータフレームに変換
    monthly_counts = pd.DataFrame(monthly_results)
    
    # 日付順にソート
    if not monthly_counts.empty:
        monthly_counts = monthly_counts.sort_values('月')
        
        # インデックスをリセット
        monthly_counts = monthly_counts.reset_index(drop=True)
    
    # --- 修正箇所 1 ---
    # monthly_counts を実績データとし、'月' を index に設定
    monthly_counts = monthly_counts.set_index('月')
    # -----------------

    ts_data = monthly_counts['平日1日平均件数'] # index設定後の Series を使う
    if ts_data.empty: return pd.DataFrame(), None, {"message": "月次集計データが空です"}

    # 予測期間設定 ... (変更なし)
    latest_month_dt = ts_data.index.max()
    if period_end_date is None:
        today = latest_month_dt
        if prediction_period == 'fiscal_year':
            if today.month >= 4: period_end_date = pd.Timestamp(today.year + 1, 3, 31)
            else: period_end_date = pd.Timestamp(today.year, 3, 31)
        elif prediction_period == 'calendar_year': period_end_date = pd.Timestamp(today.year, 12, 31)
        elif prediction_period == 'six_months':
            six_months_later = today + pd.DateOffset(months=6)
            last_day_of_month = calendar.monthrange(six_months_later.year, six_months_later.month)[1]
            period_end_date = pd.Timestamp(six_months_later.year, six_months_later.month, last_day_of_month)
        else:
             if today.month >= 4: period_end_date = pd.Timestamp(today.year + 1, 3, 31)
             else: period_end_date = pd.Timestamp(today.year, 3, 31)
    if period_end_date <= latest_month_dt: return monthly_counts.reset_index(), None, {"message": "予測期間の終了日が過去または最新データ月以前です"} # monthly_counts を返す
    forecast_months = pd.date_range(start=latest_month_dt + pd.DateOffset(months=1), end=period_end_date, freq='MS')
    if forecast_months.empty: return monthly_counts.reset_index(), None, {"message": "予測対象となる未来の月がありません"}

    forecast_df = pd.DataFrame(index=forecast_months)
    # --- 修正箇所 2 ---
    forecast_df.index.name = '月' # forecast_df の index 名も '月' に設定
    # -----------------

    # 予測モデル適用 ... (変更なし)
    model_used = 'moving_avg'; forecast = pd.Series([ts_data.mean()] * len(forecast_months), index=forecast_months)
    if model_type == 'hwes' and len(ts_data) >= 12:
        try:
            params = {'seasonal_periods': 12, 'trend': 'add', 'seasonal': 'add', 'use_boxcox': True}
            if custom_params: params.update(custom_params)
            model = ExponentialSmoothing(ts_data, **params, initialization_method="estimated").fit()
            forecast = model.forecast(len(forecast_months)); model_used = 'hwes'
        except Exception as e: print(f"HWES failed: {e}"); model_type = 'moving_avg'
    elif model_type == 'arima' and len(ts_data) >= 12:
        try:
            model = ARIMA(ts_data, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12)).fit()
            forecast = model.forecast(len(forecast_months)); model_used = 'arima'
        except Exception as e: print(f"ARIMA failed: {e}"); model_type = 'moving_avg'
    if model_used == 'moving_avg' or model_type == 'moving_avg':
        window_size = min(6, len(ts_data)); rolling_avg = ts_data.rolling(window=window_size).mean()
        last_avg = rolling_avg.iloc[-1]; last_avg = ts_data.mean() if pd.isna(last_avg) else last_avg
        forecast = pd.Series([last_avg] * len(forecast_months), index=forecast_months); model_used = 'moving_avg'

    # 予測結果をDataFrameに格納 ... (変更なし)
    forecast_weekdays = pd.Series([calculate_weekdays_in_month(m) for m in forecast_months], index=forecast_months)
    forecast_df['平日1日平均件数'] = forecast.round(1); forecast_df['平日日数'] = forecast_weekdays
    forecast_df['平日件数'] = np.where(forecast_df['平日日数'] > 0, (forecast_df['平日1日平均件数'] * forecast_df['平日日数']).round(), 0).astype(int)
    forecast_df['全日件数'] = forecast_df['平日件数']

    # --- 修正箇所 3 ---
    # 実績と予測を結合 (両方とも index が '月')
    combined_df = pd.concat([monthly_counts, forecast_df], sort=True)
    result_df = combined_df.reset_index() # index ('月') を列に戻す
    # .rename(...) は不要
    # -----------------

    # グラフ作成
    fig = create_prediction_graph(result_df, len(monthly_counts)) # monthly_countsの長さ(実績期間)を渡す

    # メトリクス計算 ... (monthly_counts を使うように修正)
    actual_data = monthly_counts['平日1日平均件数'] # index設定後の実績データを使用
    forecast_data_series = forecast_df['平日1日平均件数']
    current_date = latest_month_dt # latest_month_dt を使う
    fiscal_year = current_date.year if current_date.month >= 4 else current_date.year - 1
    fiscal_year_start = pd.Timestamp(fiscal_year, 4, 1); fiscal_year_end = pd.Timestamp(fiscal_year + 1, 3, 31)

    # result_df から実績と予測を再抽出
    fiscal_year_actual = result_df[(result_df['月'] >= fiscal_year_start) & (result_df['月'] <= current_date)]
    fiscal_year_forecast = result_df[(result_df['月'] > current_date) & (result_df['月'] <= fiscal_year_end)]

    fiscal_year_actual_weekdays = fiscal_year_actual['平日日数'].sum(); fiscal_year_forecast_weekdays = fiscal_year_forecast['平日日数'].sum(skipna=True) # skipna追加
    fiscal_year_total_weekdays = fiscal_year_actual_weekdays + fiscal_year_forecast_weekdays
    fiscal_year_actual_cases = fiscal_year_actual['平日件数'].sum(); fiscal_year_forecast_cases = fiscal_year_forecast['平日件数'].sum(skipna=True) # skipna追加
    fiscal_year_total_cases = fiscal_year_actual_cases + fiscal_year_forecast_cases

    annual_target_per_day = 21
    annual_target = annual_target_per_day * fiscal_year_total_weekdays
    achievement_rate = (fiscal_year_total_cases / annual_target) * 100 if annual_target > 0 else 0

    metrics = {
        "予測使用モデル": model_used,
        "実績平均": actual_data.mean(),
        "予測平均": forecast_data_series.mean() if not forecast_data_series.empty else 0, # 空チェック
        "変化率(%)": ((forecast_data_series.mean() / actual_data.mean()) - 1) * 100 if actual_data.mean() > 0 and not forecast_data_series.empty else 0,
        "年度内平日数": fiscal_year_total_weekdays,
        "年度実績件数": fiscal_year_actual_cases,
        "年度予測件数": fiscal_year_forecast_cases,
        "年度合計予測": fiscal_year_total_cases,
        "目標達成率予測": achievement_rate
    }
    # --- メトリクス計算終了 ---

    return result_df, fig, metrics


def predict_department_future(df, department, period_end_date=None, prediction_period='fiscal_year', model_type='hwes', custom_params=None):
    """診療科別の将来予測を行う関数 (既存の関数 - 変更なし)"""
    # ... (内容は変更なし) ...
    df = df.copy(); df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce'); df = df.dropna(subset=['手術実施日_dt'])
    df = df[df['実施診療科'] == department]
    df_gas = df[df['麻酔種別'].str.contains("全身麻酔", na=False) & df['麻酔種別'].str.contains("20分以上", na=False)].copy()
    if df_gas.empty: return pd.DataFrame(), None, {"message": f"{department}の全身麻酔(20分以上)データが見つかりません"}

    # 月次集計 (月合計件数)
    df_gas['月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    monthly_agg = df_gas.groupby('月').size().reset_index(name='月合計件数').sort_values('月') # monthly_agg とする

    # --- 修正箇所 1 (診療科別) ---
    monthly_counts = monthly_agg.set_index('月')
    # --------------------------

    ts_data = monthly_counts['月合計件数'] # index設定後の Series を使う
    if ts_data.empty: return pd.DataFrame(), None, {"message": f"{department}の月次集計データが空です"}

    # 予測期間設定 ... (変更なし)
    latest_month_dt = ts_data.index.max()
    if period_end_date is None:
        today = latest_month_dt
        if prediction_period == 'fiscal_year':
             if today.month >= 4: period_end_date = pd.Timestamp(today.year + 1, 3, 31)
             else: period_end_date = pd.Timestamp(today.year, 3, 31)
        elif prediction_period == 'calendar_year': period_end_date = pd.Timestamp(today.year, 12, 31)
        elif prediction_period == 'six_months':
             six_months_later = today + pd.DateOffset(months=6)
             last_day_of_month = calendar.monthrange(six_months_later.year, six_months_later.month)[1]
             period_end_date = pd.Timestamp(six_months_later.year, six_months_later.month, last_day_of_month)
        else:
             if today.month >= 4: period_end_date = pd.Timestamp(today.year + 1, 3, 31)
             else: period_end_date = pd.Timestamp(today.year, 3, 31)
    if period_end_date <= latest_month_dt: return monthly_agg, None, {"message": "予測期間の終了日が過去または最新データ月以前です"} # monthly_agg を返す
    forecast_months = pd.date_range(start=latest_month_dt + pd.DateOffset(months=1), end=period_end_date, freq='MS')
    if forecast_months.empty: return monthly_agg, None, {"message": "予測対象となる未来の月がありません"}

    forecast_df = pd.DataFrame(index=forecast_months)
    # --- 修正箇所 2 (診療科別) ---
    forecast_df.index.name = '月'
    # --------------------------

    # 予測モデル適用 ... (変更なし)
    model_used = 'moving_avg'; forecast = pd.Series([ts_data.mean()] * len(forecast_months), index=forecast_months)
    if model_type == 'hwes' and len(ts_data) >= 12:
        try:
            params = {'seasonal_periods': 12, 'trend': 'add', 'seasonal': 'add', 'use_boxcox': True}
            if custom_params: params.update(custom_params)
            model = ExponentialSmoothing(ts_data, **params, initialization_method="estimated").fit()
            forecast = model.forecast(len(forecast_months)); model_used = 'hwes'
        except Exception as e: print(f"HWES failed for {department}: {e}"); model_type = 'moving_avg'
    elif model_type == 'arima' and len(ts_data) >= 12:
        try:
            model = ARIMA(ts_data, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12)).fit()
            forecast = model.forecast(len(forecast_months)); model_used = 'arima'
        except Exception as e: print(f"ARIMA failed for {department}: {e}"); model_type = 'moving_avg'
    if model_used == 'moving_avg' or model_type == 'moving_avg':
        window_size = min(6, len(ts_data)); rolling_avg = ts_data.rolling(window=window_size).mean()
        last_avg = rolling_avg.iloc[-1]; last_avg = ts_data.mean() if pd.isna(last_avg) else last_avg
        forecast = pd.Series([last_avg] * len(forecast_months), index=forecast_months); model_used = 'moving_avg'

    # 予測結果をDataFrameに格納 ... (変更なし)
    forecast_df['月合計件数'] = forecast.replace([np.inf, -np.inf], np.nan).fillna(0).round().astype(int)

    # --- 修正箇所 3 (診療科別) ---
    combined_df = pd.concat([monthly_counts, forecast_df], sort=True)
    result_df = combined_df.reset_index()
    # --------------------------

    # グラフ作成
    fig = create_department_prediction_graph(result_df, department, len(monthly_counts))

    # メトリクス計算
    metrics = calculate_department_prediction_metrics(result_df, department, len(monthly_counts), model_used)

    return result_df, fig, metrics


# --- グラフ作成関数 (create_prediction_graph, create_department_prediction_graph は変更なし) ---
def create_prediction_graph(df, actual_data_length):
    """病院全体用の予測グラフを作成 (スタイル適用済み)"""
    # ... (内容は変更なし) ...
    fig = go.Figure()
    if df.empty or '平日1日平均件数' not in df.columns:
        fig.update_layout(title="予測グラフデータがありません")
        return fig
    actual_df = df.iloc[:actual_data_length]
    if actual_data_length < len(df): forecast_df = df.iloc[actual_data_length-1:]
    else: forecast_df = pd.DataFrame()
    fig.add_trace(go.Scatter(x=actual_df['月'], y=actual_df['平日1日平均件数'], mode='lines+markers', name='実績', line=sc.PREDICTION_ACTUAL_LINE_STYLE, marker=sc.PREDICTION_ACTUAL_MARKER))
    if not forecast_df.empty: fig.add_trace(go.Scatter(x=forecast_df['月'], y=forecast_df['平日1日平均件数'], mode='lines+markers', name='予測', line=sc.PREDICTION_LINE_STYLE, marker=sc.PREDICTION_MARKER))
    all_y = pd.concat([actual_df['平日1日平均件数'], forecast_df['平日1日平均件数']]).dropna() if not forecast_df.empty else actual_df['平日1日平均件数'].dropna()
    y_min = all_y.min() if not all_y.empty else 0; y_max = all_y.max() if not all_y.empty else 10
    y_range_margin = (y_max - y_min) * 0.05; y_axis_range = [y_min - y_range_margin, y_max + y_range_margin]
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(title="全身麻酔 平日1日平均件数（実績＋予測） - 病院全体", xaxis_title="月", yaxis_title="件数/日", xaxis=dict(tickformat="%Y-%m"), yaxis=dict(range=y_axis_range))
    return fig

def create_department_prediction_graph(df, department, actual_data_length):
    """診療科別の予測グラフを作成 (スタイル適用済み)"""
    # ... (内容は変更なし) ...
    fig = go.Figure()
    if df.empty or '月合計件数' not in df.columns:
        fig.update_layout(title=f"{department} - 予測グラフデータがありません")
        return fig
    actual_df = df.iloc[:actual_data_length]
    if actual_data_length < len(df): forecast_df = df.iloc[actual_data_length-1:]
    else: forecast_df = pd.DataFrame()
    fig.add_trace(go.Scatter(x=actual_df['月'], y=actual_df['月合計件数'], mode='lines+markers', name='実績', line=sc.PREDICTION_ACTUAL_LINE_STYLE, marker=sc.PREDICTION_ACTUAL_MARKER))
    if not forecast_df.empty: fig.add_trace(go.Scatter(x=forecast_df['月'], y=forecast_df['月合計件数'], mode='lines+markers', name='予測', line=sc.PREDICTION_LINE_STYLE, marker=sc.PREDICTION_MARKER))
    all_y = pd.concat([actual_df['月合計件数'], forecast_df['月合計件数']]).dropna() if not forecast_df.empty else actual_df['月合計件数'].dropna()
    y_min = all_y.min() if not all_y.empty else 0; y_max = all_y.max() if not all_y.empty else 10
    y_range_margin = (y_max - y_min) * 0.05; y_axis_range = [y_min - y_range_margin, y_max + y_range_margin]
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(title=f"{department} - 月合計件数（実績＋予測）", xaxis_title="月", yaxis_title="件数/月", xaxis=dict(tickformat="%Y-%m"), yaxis=dict(range=y_axis_range))
    return fig


# --- メトリクス計算関数 (calculate_prediction_metrics, calculate_department_prediction_metrics は変更なし) ---
def calculate_prediction_metrics(df, actual_data_length, model_type):
    """病院全体の予測指標を計算"""
    # ... (内容は変更なし) ...
    if actual_data_length <= 0 or len(df) <= actual_data_length: # <= に修正
        return {"message": "メトリクス計算用の実績または予測データが不足しています"}
    actual_df = df.iloc[:actual_data_length]
    forecast_df = df.iloc[actual_data_length:]
    actual_avg = actual_df['平日1日平均件数'].mean(); forecast_avg = forecast_df['平日1日平均件数'].mean() if not forecast_df.empty else 0
    change_rate = ((forecast_avg / actual_avg) - 1) * 100 if actual_avg > 0 else 0
    return {"使用モデル": model_type, "実績平均": round(actual_avg, 1), "予測平均": round(forecast_avg, 1), "変化率(%)": round(change_rate, 1)}

def calculate_department_prediction_metrics(df, department, actual_data_length, model_type):
    """診療科別の予測指標を計算"""
    # ... (内容は変更なし) ...
    if actual_data_length <= 0 or len(df) <= actual_data_length:
         return {"message": "メトリクス計算用の実績または予測データが不足しています"}
    actual_df = df.iloc[:actual_data_length]; forecast_df = df.iloc[actual_data_length:]
    actual_avg = actual_df['月合計件数'].mean(); forecast_avg = forecast_df['月合計件数'].mean() if not forecast_df.empty else 0
    change_rate = ((forecast_avg / actual_avg) - 1) * 100 if actual_avg > 0 else 0
    return {"診療科": department, "使用モデル": model_type, "実績月平均": round(actual_avg, 1), "予測月平均": round(forecast_avg, 1), "変化率(%)": round(change_rate, 1)}


# --- 複数モデル指標取得関数 (get_multi_model_forecast_summary) ---
def get_multi_model_forecast_summary(df_gas, latest_date):
    """
    HWES, ARIMA, 移動平均モデルの予測指標サマリーを計算する関数。

    Args:
        df_gas (pd.DataFrame): 全身麻酔(20分以上)のフィルター済みデータフレーム。'手術実施日_dt' 列が必要。
        latest_date (pd.Timestamp): 分析の基準となる最新の日付。

    Returns:
        dict: 各モデルの予測指標を含む辞書。例: {'hwes': {...}, 'arima': {...}, 'moving_avg': {...}}
              エラー時は {'error': message}
    """
    if df_gas.empty or '手術実施日_dt' not in df_gas.columns:
        return {'error': '有効なデータがありません。'}
    if latest_date is None or pd.isna(latest_date):
         return {'error': '最新日付が不明です。'}

    df = df_gas.copy()

    # --- ここから月次集計を修正する ---
    # 月ごとに集計するための準備
    df.loc[:, '月'] = df['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    df.loc[:, '日'] = df['手術実施日_dt'].dt.day  # 日にちも追加
    
    # 集計対象の期間を得る
    min_date = df['手術実施日_dt'].min()
    max_date = df['手術実施日_dt'].max()
    unique_months = df['月'].unique()
    
    # 月ごとの集計結果を格納するリスト
    monthly_results = []
    
    for month_start in unique_months:
        # 月の最終日
        year = month_start.year
        month = month_start.month
        _, last_day = calendar.monthrange(year, month)
        month_end = pd.Timestamp(year, month, last_day)
        
        # この月のデータ
        month_data = df[df['月'] == month_start]
        
        if month_start.year == min_date.year and month_start.month == min_date.month:
            # 最初の月は、データが存在する最初の日から計算
            month_first_day = min_date
        
        # 該当期間の平日数を計算
        weekdays_in_period = calculate_weekdays_in_period(month_first_day, actual_month_end)
        
        # 平日1日平均件数
        avg_per_weekday = 0
        if weekdays_in_period > 0:
            avg_per_weekday = (weekday_count / weekdays_in_period)
        
        # 結果を格納
        monthly_results.append({
            '月': month_start,
            '全日件数': all_days_count,
            '平日件数': weekday_count,
            '平日日数': weekdays_in_period,
            '平日1日平均件数': round(avg_per_weekday, 1)
        })
    
    # 結果をデータフレームに変換し、必要な処理を行う
    monthly_counts = pd.DataFrame(monthly_results)
    
    # データフレームが空でないことを確認
    if monthly_counts.empty:
        return {'error': '月次集計データが作成できませんでした。'}
    
    # 日付順にソート
    monthly_counts = monthly_counts.sort_values('月')
    monthly_counts = monthly_counts.set_index('月')  
    
    # 時系列データとして取得
    ts_data = monthly_counts['平日1日平均件数']
    
    # --- ここから予測と指標計算 ---
    
    # 予測期間設定 (年度末まで)
    fiscal_year = latest_date.year if latest_date.month >= 4 else latest_date.year - 1
    period_end_date = pd.Timestamp(fiscal_year + 1, 3, 31)
    if period_end_date <= latest_date:
        return {'error': '予測期間の終了日が過去または最新データ月以前です。'}
    
    # 予測対象の月を生成
    latest_month_dt = ts_data.index.max()
    forecast_months = pd.date_range(start=latest_month_dt + pd.DateOffset(months=1), end=period_end_date, freq='MS')
    if forecast_months.empty:
        return {'error': '予測対象となる未来の月がありません。'}
    
    # 各モデルで予測と指標計算
    all_metrics = {}
    model_types_to_run = ['hwes', 'arima', 'moving_avg']
    
    for model_type in model_types_to_run:
        forecast = None
        try:
            if model_type == 'hwes':
                model = ExponentialSmoothing(ts_data, seasonal_periods=12, trend='add', seasonal='add', use_boxcox=True, initialization_method="estimated").fit()
                forecast = model.forecast(len(forecast_months))
            elif model_type == 'arima':
                model = ARIMA(ts_data, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12)).fit()
                forecast = model.forecast(len(forecast_months))
            elif model_type == 'moving_avg':
                window_size = min(6, len(ts_data))
                rolling_avg = ts_data.rolling(window=window_size).mean()
                last_avg = rolling_avg.iloc[-1]
                last_avg = ts_data.mean() if pd.isna(last_avg) else last_avg
                forecast = pd.Series([last_avg] * len(forecast_months), index=forecast_months)
            
            if forecast is None:
                 raise ValueError("Forecast calculation failed.")
                 
            # 指標計算に必要なDataFrameを作成
            forecast_df = pd.DataFrame(index=forecast_months)
            forecast_df.index.name = '月'
            forecast_weekdays = pd.Series([calculate_weekdays_in_month(m) for m in forecast_months], index=forecast_months)
            forecast_df['平日1日平均件数'] = forecast.round(1)
            forecast_df['平日日数'] = forecast_weekdays
            forecast_df['平日件数'] = np.where(forecast_df['平日日数'] > 0, (forecast_df['平日1日平均件数'] * forecast_df['平日日数']).round(), 0).astype(int)
            
            # 指標計算
            actual_data = ts_data # 実績データ
            forecast_data_series = forecast_df['平日1日平均件数']
            
            fiscal_year_start = pd.Timestamp(fiscal_year, 4, 1)
            # result_df はこの関数内では不要だが、実績と予測の期間を特定するために一時的に作成
            temp_combined_df = pd.concat([monthly_counts, forecast_df], sort=True).reset_index()
            fiscal_year_actual = temp_combined_df[(temp_combined_df['月'] >= fiscal_year_start) & (temp_combined_df['月'] <= latest_date)]
            fiscal_year_forecast = temp_combined_df[(temp_combined_df['月'] > latest_date) & (temp_combined_df['月'] <= period_end_date)]
            
            fiscal_year_actual_weekdays = fiscal_year_actual['平日日数'].sum()
            fiscal_year_forecast_weekdays = fiscal_year_forecast['平日日数'].sum(skipna=True)
            fiscal_year_total_weekdays = fiscal_year_actual_weekdays + fiscal_year_forecast_weekdays
            fiscal_year_actual_cases = fiscal_year_actual['平日件数'].sum()
            fiscal_year_forecast_cases = fiscal_year_forecast['平日件数'].sum(skipna=True)
            fiscal_year_total_cases = fiscal_year_actual_cases + fiscal_year_forecast_cases
            
            annual_target_per_day = 21
            annual_target = annual_target_per_day * fiscal_year_total_weekdays
            achievement_rate = (fiscal_year_total_cases / annual_target) * 100 if annual_target > 0 else 0
            
            metrics = {
                "予測平均": forecast_data_series.mean() if not forecast_data_series.empty else np.nan,
                "変化率(%)": ((forecast_data_series.mean() / actual_data.mean()) - 1) * 100 if actual_data.mean() > 0 and not forecast_data_series.empty else np.nan,
                "年度予測件数": fiscal_year_forecast_cases, # 予測期間のみの件数
                "年度合計予測": fiscal_year_total_cases, # 実績＋予測
                "目標達成率予測": achievement_rate
            }
            all_metrics[model_type] = metrics
            
        except Exception as e:
            print(f"指標計算エラー ({model_type}): {e}")
            # エラーが発生したモデルの指標はNaNなどで埋めるか、空の辞書にする
            all_metrics[model_type] = {
                "予測平均": np.nan, "変化率(%)": np.nan, "年度予測件数": np.nan,
                "年度合計予測": np.nan, "目標達成率予測": np.nan
            }
    
    # 実績平均を追加（全モデル共通）
    actual_avg = ts_data.mean()
    for model_key in all_metrics:
        all_metrics[model_key]['実績平均'] = actual_avg
    
    return all_metrics