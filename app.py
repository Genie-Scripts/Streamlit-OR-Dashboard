# app.py (v6.2 自己完結・最終完成版)
import streamlit as st
import pandas as pd
import traceback
from datetime import datetime, time
import pytz
import plotly.express as px
import unicodedata
import re

# --- ページ設定 (必ず最初に実行) ---
st.set_page_config(
    page_title="手術分析ダッシュボード", page_icon="🏥", layout="wide", initial_sidebar_state="expanded"
)

# --- このファイル内に必要な関数をすべて定義 ---

def _normalize_room_name(series):
    """手術室名の表記を正規化（全角→半角、数字抽出、'OR'付与）する"""
    if not pd.api.types.is_string_dtype(series):
        series = series.astype(str)
    
    def normalize_single_name(name):
        try:
            half_width_name = unicodedata.normalize('NFKC', str(name))
            match = re.search(r'(\d+)', half_width_name)
            if match:
                return f"OR{match.group(1)}"
            return None
        except:
            return None

    return series.apply(normalize_single_name)

def _convert_to_datetime(series, date_series):
    """Excelの数値時間とテキスト時間を両方考慮してdatetimeオブジェクトに変換する"""
    try:
        # 数値形式の試行
        numeric_series = pd.to_numeric(series, errors='coerce')
        # dropna()を安全に呼び出す
        valid_series = series.dropna()
        if not valid_series.empty and numeric_series.notna().sum() / len(valid_series) > 0.8:
            time_deltas = pd.to_timedelta(numeric_series * 24, unit='h', errors='coerce')
            return pd.to_datetime(date_series.astype(str)) + time_deltas
        
        # テキスト形式の試行
        time_only_series = pd.to_datetime(series, errors='coerce', format=None).dt.time
        valid_times = time_only_series.notna()
        combined_dt = pd.Series(pd.NaT, index=series.index)
        
        if valid_times.any():
            date_series_valid = date_series[valid_times]
            time_only_series_valid = time_only_series[valid_times]
            # 日付と時刻を結合
            combined_dt.loc[valid_times] = [datetime.combine(d.date(), t) if isinstance(d, datetime) else datetime.combine(d, t) for d, t in zip(date_series_valid, time_only_series_valid)]

        return combined_dt
    except Exception:
        return pd.Series(pd.NaT, index=series.index)

def calculate_operating_room_utilization(df, period_df):

    # ▼▼▼▼▼ ここからデバッグコードを挿入 ▼▼▼▼▼
    st.subheader("🔬 稼働率計算 デバッグ情報")
    st.info("この情報をお知らせください。")

    # --- チェック1: 渡されたデータの確認 ---
    st.write("#### 1. 関数に渡されたデータの先頭5行")
    st.dataframe(period_df.head())

    # --- チェック2: 列名の検出 ---
    st.write("#### 2. 検出された列名")
    start_col, end_col, room_col = None, None, None
    possible_start_keys=['入室時刻', '開始']; possible_end_keys=['退室時刻', '終了']; possible_room_keys=['実施手術室', '手術室']
    for col in period_df.columns:
        if not start_col and any(key in col for key in possible_start_keys): start_col = col
        if not end_col and any(key in col for key in possible_end_keys): end_col = col
        if not room_col and any(key in col for key in possible_room_keys): room_col = col
    
    st.write(f"- `入室時刻`として検出された列: `{start_col}`")
    st.write(f"- `退室時刻`として検出された列: `{end_col}`")
    st.write(f"- `手術室`として検出された列: `{room_col}`")
    
    if not all([start_col, end_col, room_col]):
        st.error("必要な列が見つかりませんでした。ここで処理が停止します。")
        return 0.0 # 早期リターン

    # --- チェック3: 手術室名の正規化 ---
    st.write("#### 3. 手術室名の正規化チェック")
    normalized_names = _normalize_room_name(period_df[room_col])
    check_df = pd.DataFrame({
        '元の名前': period_df[room_col],
        '正規化後の名前': normalized_names
    }).dropna(subset=['元の名前']).head(10)
    st.dataframe(check_df)

    # --- チェック4: フィルタリング結果 ---
    st.write("#### 4. フィルタリング結果")
    target_rooms = ['OR1', 'OR2', 'OR3', 'OR4', 'OR5', 'OR6', 'OR7', 'OR8', 'OR9', 'OR10', 'OR12']
    filtered_count = normalized_names.isin(target_rooms).sum()
    st.metric("対象11部屋に一致した件数", f"{filtered_count} 件")

    if filtered_count == 0:
        st.error("一致件数が0件のため、稼働率が0%になっています。正規化処理がうまくいっていないか、対象期間に対象の手術室が存在しないようです。")

    # ▲▲▲▲▲ ここまでデバッグコード ▲▲▲▲▲

    """手術室の稼働率を計算する"""
    if df.empty or period_df.empty: return 0.0

    weekday_df = period_df[period_df['手術実施日_dt'].dt.dayofweek < 5].copy()
    if weekday_df.empty: return 0.0
        
    start_col, end_col, room_col = None, None, None
    possible_start_keys=['入室時刻', '開始']; possible_end_keys=['退室時刻', '終了']; possible_room_keys=['実施手術室', '手術室']
    for col in df.columns:
        if not start_col and any(key in col for key in possible_start_keys): start_col = col
        if not end_col and any(key in col for key in possible_end_keys): end_col = col
        if not room_col and any(key in col for key in possible_room_keys): room_col = col
    
    if start_col and end_col and room_col:
        try:
            target_rooms = ['OR1', 'OR2', 'OR3', 'OR4', 'OR5', 'OR6', 'OR7', 'OR8', 'OR9', 'OR10', 'OR12']
            normalized_room_series = _normalize_room_name(weekday_df[room_col])
            
            # .locを使ってインデックスを確実に合わせる
            valid_normalized_rooms = normalized_room_series.dropna()
            filtered_weekday_df = weekday_df.loc[valid_normalized_rooms[valid_normalized_rooms.isin(target_rooms)].index].copy()

            if filtered_weekday_df.empty: return 0.0

            filtered_weekday_df['start_datetime'] = _convert_to_datetime(filtered_weekday_df[start_col], filtered_weekday_df['手術実施日_dt'])
            filtered_weekday_df['end_datetime'] = _convert_to_datetime(filtered_weekday_df[end_col], filtered_weekday_df['手術実施日_dt'])
            filtered_weekday_df.dropna(subset=['start_datetime', 'end_datetime'], inplace=True)
            
            if filtered_weekday_df.empty: return 0.0

            overnight_mask = filtered_weekday_df['end_datetime'] < filtered_weekday_df['start_datetime']
            filtered_weekday_df.loc[overnight_mask, 'end_datetime'] += pd.Timedelta(days=1)
            
            total_usage_minutes = 0
            op_start_time = time(9, 0); op_end_time = time(17, 15)
            for _, row in filtered_weekday_df.iterrows():
                day = row['手術実施日_dt'].date()
                operation_start = datetime.combine(day, op_start_time)
                operation_end = datetime.combine(day, op_end_time)
                actual_start = max(row['start_datetime'], operation_start)
                actual_end = min(row['end_datetime'], operation_end)
                if actual_end > actual_start:
                    total_usage_minutes += (actual_end - actual_start).total_seconds() / 60
            
            period_start_date = period_df['手術実施日_dt'].min()
            period_end_date = period_df['手術実施日_dt'].max()
            total_weekdays_in_period = len(pd.bdate_range(period_start_date, period_end_date)) # business day range
            
            num_rooms = 11
            total_available_minutes = total_weekdays_in_period * num_rooms * 495

            if total_available_minutes > 0:
                return min((total_usage_minutes / total_available_minutes) * 100, 100.0)
        except Exception:
            pass

    return 0.0 # フォールバック時は0を返す

# --- メインのアプリケーション ---

# セッション状態の初期化
if 'df' not in st.session_state:
    st.session_state['df'] = None

# タイトル
st.title("🏥 手術実績分析ダッシュボード")

# ファイルアップローダー
uploaded_file = st.file_uploader("手術実績データ（CSVまたはExcel）をアップロードしてください", type=['csv', 'xlsx'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='cp932', low_memory=False)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 基本的な前処理
        df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
        df.dropna(subset=['手術実施日_dt'], inplace=True)

        st.session_state['df'] = df
        st.success(f"{len(df)}件のデータを読み込みました。")
    except Exception as e:
        st.error(f"ファイルの読み込みに失敗しました: {e}")
        st.stop()

# データが読み込まれたらKPIを表示
if st.session_state['df'] is not None:
    df = st.session_state['df']
    latest_date = df['手術実施日_dt'].max()
    
    st.header(f"KPIサマリー (直近30日: {(latest_date - pd.Timedelta(days=29)).strftime('%Y/%m/%d')} - {latest_date.strftime('%Y/%m/%d')})")
    
    recent_df = df[df['手術実施日_dt'] >= (latest_date - pd.Timedelta(days=29))]
    
    # KPIの計算
    total_cases = len(recent_df)
    gas_df = recent_df[recent_df['麻酔種別'].str.contains("全身麻酔", na=False)]
    total_gas_cases = len(gas_df)
    
    # 稼働率の計算
    utilization_rate = calculate_operating_room_utilization(df, recent_df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("総手術件数", f"{total_cases:,} 件")
    col2.metric("全身麻酔件数", f"{total_gas_cases:,} 件")
    col3.metric("手術室稼働率", f"{utilization_rate:.1f} %")
else:
    st.info("データをアップロードすると、ここにダッシュボードが表示されます。")