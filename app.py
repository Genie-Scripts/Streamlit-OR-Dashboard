# app.py (v7.0 最終統合版)
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

# --- このファイル内に必要なヘルパー関数をすべて定義 ---

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
        numeric_series = pd.to_numeric(series, errors='coerce')
        valid_series = series.dropna()
        if not valid_series.empty and numeric_series.notna().sum() / len(valid_series) > 0.8:
            time_deltas = pd.to_timedelta(numeric_series * 24, unit='h', errors='coerce')
            return pd.to_datetime(date_series.astype(str)) + time_deltas
        
        time_only_series = pd.to_datetime(series, errors='coerce', format=None).dt.time
        valid_times = time_only_series.notna()
        combined_dt = pd.Series(pd.NaT, index=series.index)
        if valid_times.any():
            date_series_valid = date_series[valid_times]
            time_only_series_valid = time_only_series[valid_times]
            combined_dt.loc[valid_times] = [datetime.combine(d.date(), t) if isinstance(d, datetime) else datetime.combine(d, t) for d, t in zip(date_series_valid, time_only_series_valid)]
        return combined_dt
    except Exception:
        return pd.Series(pd.NaT, index=series.index)

def calculate_operating_room_utilization(df, period_df):
    """手術室の稼働率を計算する"""
    if df.empty or period_df.empty: return 0.0
    
    # is_weekday列がない場合は仮作成
    if 'is_weekday' not in period_df.columns:
        period_df['is_weekday'] = period_df['手術実施日_dt'].dt.dayofweek < 5

    weekday_df = period_df[period_df['is_weekday']].copy()
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
                operation_start = datetime.combine(day, op_start_time); operation_end = datetime.combine(day, op_end_time)
                actual_start = max(row['start_datetime'], operation_start); actual_end = min(row['end_datetime'], operation_end)
                if actual_end > actual_start: total_usage_minutes += (actual_end - actual_start).total_seconds() / 60
            
            period_start_date = period_df['手術実施日_dt'].min(); period_end_date = period_df['手術実施日_dt'].max()
            total_weekdays_in_period = len(pd.bdate_range(period_start_date, period_end_date))
            num_rooms = 11; total_available_minutes = total_weekdays_in_period * num_rooms * 495
            if total_available_minutes > 0: return min((total_usage_minutes / total_available_minutes) * 100, 100.0)
        except Exception: pass
    return 0.0

# --- セッション状態の初期化 ---
if 'df' not in st.session_state:
    st.session_state['df'] = None

# --- UI描画関数 ---
def render_sidebar():
    with st.sidebar:
        st.title("🏥 手術分析")
        st.markdown("---")
        views = ["ダッシュボード", "データアップロード"]
        st.session_state['current_view'] = st.radio("📍 ナビゲーション", views, key="navigation")
        st.markdown("---")
        if st.session_state.get('df') is not None:
            st.success("✅ データ読み込み済み")
            st.write(f"📊 レコード数: {len(st.session_state.df):,}")
        else: st.warning("⚠️ データ未読み込み")
        st.info("Version: 7.0 (Standalone)")

def render_dashboard_page(df):
    latest_date = df['手術実施日_dt'].max()
    st.header(f"KPIサマリー (直近30日: {(latest_date - pd.Timedelta(days=29)).strftime('%Y/%m/%d')} - {latest_date.strftime('%Y/%m/%d')})")
    
    recent_df = df[df['手術実施日_dt'] >= (latest_date - pd.Timedelta(days=29))]
    total_cases = len(recent_df)
    gas_df = recent_df[recent_df['麻酔種別'].str.contains("全身麻酔", na=False)]
    total_gas_cases = len(gas_df)
    utilization_rate = calculate_operating_room_utilization(df, recent_df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("総手術件数", f"{total_cases:,} 件")
    col2.metric("全身麻酔件数", f"{total_gas_cases:,} 件")
    col3.metric("手術室稼働率", f"{utilization_rate:.1f} %")

def render_upload_page():
    st.header("📤 データアップロード")
    uploaded_file = st.file_uploader("手術実績データ（CSVまたはExcel）をアップロードしてください", type=['csv', 'xlsx'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='cp932', low_memory=False)
            else:
                df = pd.read_excel(uploaded_file)
            
            df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
            df.dropna(subset=['手術実施日_dt'], inplace=True)

            st.session_state['df'] = df
            st.success(f"{len(df)}件のデータを読み込みました。")
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {e}")

# --- メイン実行部 ---
def main():
    render_sidebar()
    
    st.title("🏥 手術実績分析ダッシュボード")

    if st.session_state.get('current_view') == 'データアップロード':
        render_upload_page()
    else:
        if st.session_state.get('df') is not None:
            render_dashboard_page(st.session_state.df)
        else:
            st.info("サイドバーの「データアップロード」からデータを読み込んでください。")

if __name__ == "__main__":
    main()