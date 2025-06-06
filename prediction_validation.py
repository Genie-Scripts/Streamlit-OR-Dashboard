# prediction_validation.py (Import修正)
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
import plotly.graph_objects as go
import calendar
import style_config as sc

# --- sklearn.metrics から評価指標関数をインポート ---
from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error
# -------------------------------------------------

try:
    from holiday_handler import is_weekday
except ImportError:
    print("Warning: holiday_handler.py not found. Assuming standard weekdays.")
    def is_weekday(date):
        return date.weekday() < 5

# --- 月の平日数計算 ---
def calculate_weekdays_in_month(month_start):
    """指定された月に含まれる平日の日数を計算"""
    year = month_start.year; month = month_start.month
    try:
        _, last_day = calendar.monthrange(year, month)
        all_days = pd.date_range(start=month_start, end=pd.Timestamp(year, month, last_day))
        weekday_count = sum(is_weekday(day) for day in all_days)
    except ValueError:
        weekday_count = 20
    return weekday_count


def validate_prediction_model(df, department=None, model_types=None, validation_period=6):
    """予測モデルの精度を検証する (Import修正済み)"""
    df = df.copy(); df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce'); df = df.dropna(subset=['手術実施日_dt'])
    df_gas = df[df['麻酔種別'].str.contains("全身麻酔", na=False) & df['麻酔種別'].str.contains("20分以上", na=False)].copy()
    if department is not None: df_gas = df_gas[df_gas['実施診療科'] == department]
    if df_gas.empty: return pd.DataFrame(), None, "検証対象のデータが見つかりません"

    # 月次集計
    df_gas.loc[:, '月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    if department is None: # Hospital Overall
        monthly_counts = df_gas.groupby('月').size().reset_index(name='全日件数')
        df_gas_weekday = df_gas[df_gas['手術実施日_dt'].apply(is_weekday)]; monthly_weekday_counts = df_gas_weekday.groupby('月').size().reset_index(name='平日件数')
        monthly_counts = pd.merge(monthly_counts, monthly_weekday_counts, on='月', how='left'); monthly_counts['平日件数'] = monthly_counts['平日件数'].fillna(0).astype(int)
        monthly_counts['平日日数'] = monthly_counts['月'].apply(calculate_weekdays_in_month)
        monthly_counts['平日1日平均件数'] = np.where(monthly_counts['平日日数'] > 0, (monthly_counts['平日件数'] / monthly_counts['平日日数']).round(1), 0)
        ts_column = '平日1日平均件数'
    else: # Department
        monthly_counts = df_gas.groupby('月').size().reset_index(name='月合計件数'); ts_column = '月合計件数'
    monthly_counts = monthly_counts.sort_values('月')

    # データ期間チェック
    min_required_months = validation_period + 12
    if len(monthly_counts) < min_required_months:
        return pd.DataFrame(), None, f"モデル検証には最低{min_required_months}ヶ月分のデータが必要です"

    # データ分割
    train_data = monthly_counts.iloc[:-validation_period].copy(); test_data = monthly_counts.iloc[-validation_period:].copy()
    if train_data.empty or test_data.empty:
        return pd.DataFrame(), None, "訓練データまたはテストデータの作成に失敗しました。"

    # モデルタイプ設定
    if model_types is None: model_types = ['hwes', 'arima', 'moving_avg']

    # 予測実行
    predictions = {}; model_names = {'hwes': '季節性Holt-Winters', 'arima': 'ARIMA', 'moving_avg': '移動平均'}
    ts_train = train_data.set_index('月')[ts_column]

    for model_type in model_types:
        pred_values = np.array([ts_train.mean()] * validation_period) # Default forecast
        try:
            if model_type == 'hwes' and len(ts_train) >= 12:
                 # HWESモデル: 収束エラーが発生しやすい場合がある
                 model = ExponentialSmoothing(ts_train, seasonal_periods=12, trend='add', seasonal='add', use_boxcox=True, initialization_method="estimated").fit()
                 pred_values = model.forecast(validation_period).values
            elif model_type == 'arima' and len(ts_train) >= 12:
                 # ARIMAモデル: こちらも収束エラーの可能性あり
                 model = ARIMA(ts_train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12)).fit()
                 pred_values = model.forecast(validation_period).values
            elif model_type == 'moving_avg':
                 window_size = min(6, len(ts_train)); avg_value = ts_train.rolling(window=window_size).mean().iloc[-1]
                 pred_values = np.array([avg_value if pd.notna(avg_value) else ts_train.mean()] * validation_period)
            else:
                 print(f"Skipping model {model_type} due to insufficient data or type.")
                 continue

            # 予測結果がNaNやinfでないか確認
            if not np.isfinite(pred_values).all():
                 print(f"Warning: Non-finite values predicted by {model_type}. Using fallback.")
                 # Fallback: 移動平均を使う
                 window_size = min(6, len(ts_train)); avg_value = ts_train.rolling(window=window_size).mean().iloc[-1]
                 pred_values = np.array([avg_value if pd.notna(avg_value) else ts_train.mean()] * validation_period)


            predictions[model_type] = pred_values # 予測結果を格納

        except Exception as e:
            print(f"Validation model {model_type} failed: {e}")
            # エラー時もデフォルト予測 (移動平均相当) を使う
            window_size = min(6, len(ts_train)); avg_value = ts_train.rolling(window=window_size).mean().iloc[-1]
            predictions[model_type] = np.array([avg_value if pd.notna(avg_value) else ts_train.mean()] * validation_period)

    # 有効な予測がない場合は終了
    if not predictions:
         return pd.DataFrame(), None, "どのモデルでも予測を生成できませんでした。"

    # 評価指標計算
    actual_values = test_data[ts_column].values
    metrics = {}
    valid_predictions = {} # グラフ用に有効な予測を保存

    for model_type in model_types:
        if model_type in predictions:
            pred = predictions[model_type]
            # Check for NaN/inf just before metric calculation as well
            pred = np.nan_to_num(pred, nan=np.nanmean(actual_values))
            if not np.isfinite(pred).all() or len(actual_values) != len(pred):
                 print(f"Skipping metrics for {model_type} due to invalid prediction shape or content.")
                 continue

            try:
                # --- ここで sklearn.metrics の関数を使用 ---
                mae = mean_absolute_error(actual_values, pred)
                rmse = np.sqrt(mean_squared_error(actual_values, pred))
                non_zero_actuals = actual_values != 0
                if np.any(non_zero_actuals):
                     mape = mean_absolute_percentage_error(actual_values[non_zero_actuals], pred[non_zero_actuals]) * 100
                else: mape = np.nan
                # ------------------------------------------
                metrics[model_type] = {'モデル名': model_names.get(model_type, model_type), 'MAE': round(mae, 2), 'RMSE': round(rmse, 2), 'MAPE(%)': round(mape, 1) if pd.notna(mape) else 'N/A'}
                valid_predictions[model_type] = pred
            except Exception as metric_e:
                print(f"Error calculating metrics for {model_type}: {metric_e}")


    if not metrics:
        return pd.DataFrame(), None, "有効な予測モデルの評価指標を計算できませんでした。"

    metrics_df = pd.DataFrame(metrics.values())
    rmse_valid_models = {k: v['RMSE'] for k, v in metrics.items() if pd.notna(v['RMSE'])}
    if rmse_valid_models:
        best_model_type = min(rmse_valid_models, key=rmse_valid_models.get)
        recommendation = f"推奨モデル (RMSE最小): {metrics[best_model_type]['モデル名']}"
    else: recommendation = "RMSEに基づいて推奨モデルを決定できませんでした。"

    # グラフ作成
    fig = create_validation_graph(train_data, test_data, valid_predictions, ts_column, model_names)

    return metrics_df, fig, recommendation


# --- グラフ作成関数 (変更なし) ---
def create_validation_graph(train_data, test_data, predictions, ts_column, model_names):
    """予測検証結果のグラフを作成 (スタイル適用済み)"""
    fig = go.Figure()
    if train_data.empty or test_data.empty:
        fig.update_layout(title="検証グラフデータ不足")
        return fig
    fig.add_trace(go.Scatter(x=train_data['月'], y=train_data[ts_column], mode='lines', name='訓練データ', line=dict(color=sc.PRIMARY_COLOR, width=1.5)))
    fig.add_trace(go.Scatter(x=test_data['月'], y=test_data[ts_column], mode='lines+markers', name='実際の値', line=dict(color=sc.SECONDARY_COLOR, width=2.5), marker=dict(size=7, color=sc.SECONDARY_COLOR)))
    pred_colors = [sc.PREDICTION_COLOR, 'firebrick', 'darkorchid', 'slategray']
    color_idx = 0
    for model_type, pred_values in predictions.items():
        if pred_values is not None:
            fig.add_trace(go.Scatter(x=test_data['月'], y=pred_values, mode='lines', name=f'予測: {model_names.get(model_type, model_type)}', line=dict(color=pred_colors[color_idx % len(pred_colors)], width=1.5, dash='dash')))
            color_idx += 1
    boundary_date = train_data['月'].iloc[-1]
    all_y = pd.concat([train_data[ts_column], test_data[ts_column]]).dropna()
    y_max_val = all_y.max() * 1.1 if not all_y.empty else 1
    fig.add_shape(type="line", x0=boundary_date, y0=0, x1=boundary_date, y1=y_max_val, line=dict(color="grey", width=1, dash="dot"))
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(title="予測モデル検証結果", xaxis_title="月", yaxis_title=ts_column, xaxis=dict(tickformat="%Y-%m", tickangle=-45), yaxis=dict(rangemode='tozero'))
    return fig


# --- パラメータ最適化関数 (変更なし) ---
def optimize_seasonal_model_params(df, department=None, validation_period=6):
    """季節性モデルの最適なパラメータを検索"""
    # ... (内容は変更なし) ...
    df = df.copy(); df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce'); df = df.dropna(subset=['手術実施日_dt'])
    df_gas = df[df['麻酔種別'].str.contains("全身麻酔", na=False) & df['麻酔種別'].str.contains("20分以上", na=False)].copy()
    if department is not None: df_gas = df_gas[df_gas['実施診療科'] == department]
    if df_gas.empty: return {}, "データ不足"
    df_gas.loc[:, '月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
    if department is None: # Hospital Overall
        monthly_counts = df_gas.groupby('月').size().reset_index(name='全日件数')
        df_gas_weekday = df_gas[df_gas['手術実施日_dt'].apply(is_weekday)]; monthly_weekday_counts = df_gas_weekday.groupby('月').size().reset_index(name='平日件数')
        monthly_counts = pd.merge(monthly_counts, monthly_weekday_counts, on='月', how='left'); monthly_counts['平日件数'] = monthly_counts['平日件数'].fillna(0).astype(int)
        monthly_counts['平日日数'] = monthly_counts['月'].apply(calculate_weekdays_in_month)
        monthly_counts['平日1日平均件数'] = np.where(monthly_counts['平日日数'] > 0, (monthly_counts['平日件数'] / monthly_counts['平日日数']).round(1), 0); ts_column = '平日1日平均件数'
    else: # Department
        monthly_counts = df_gas.groupby('月').size().reset_index(name='月合計件数'); ts_column = '月合計件数'
    monthly_counts = monthly_counts.sort_values('月')
    min_required_months = validation_period + 12
    if len(monthly_counts) < min_required_months: return {}, f"最適化には最低{min_required_months}ヶ月分のデータが必要です"
    train_data = monthly_counts.iloc[:-validation_period].copy(); test_data = monthly_counts.iloc[-validation_period:].copy()
    ts_train = train_data.set_index('月')[ts_column]
    seasonal_periods = [4, 6, 12]; trends = ['add', 'mul']; seasonals = ['add', 'mul']; use_boxcox_options = [True, False]
    best_rmse = float('inf'); best_params = {}
    for sp in seasonal_periods:
        for trend in trends:
            for seasonal in seasonals:
                for use_boxcox in use_boxcox_options:
                    if sp >= len(ts_train) / 2: continue
                    try:
                        model = ExponentialSmoothing(ts_train, seasonal_periods=sp, trend=trend, seasonal=seasonal, use_boxcox=use_boxcox, initialization_method="estimated").fit()
                        forecast = model.forecast(validation_period)
                        if not np.isfinite(forecast.values).all(): continue
                        rmse = np.sqrt(mean_squared_error(test_data[ts_column].values, forecast.values))
                        if rmse < best_rmse: best_rmse = rmse; best_params = {'seasonal_periods': sp, 'trend': trend, 'seasonal': seasonal, 'use_boxcox': use_boxcox, 'rmse': rmse}
                    except Exception as e: continue
    if not best_params: return {}, "最適化失敗（試行したパラメータで有効なモデル構築不可）"
    model_description = f"季節周期:{best_params['seasonal_periods']}ヶ月, トレンド:{best_params['trend']}, 季節:{best_params['seasonal']}, BoxCox:{'有' if best_params['use_boxcox'] else '無'}"
    return best_params, model_description