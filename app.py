# app.py (稼働率計算デバッグ専用)
import streamlit as st
import pandas as pd
from datetime import datetime, time

# モジュールから必要な関数を直接インポート
from data_processing.loader import preprocess_dataframe
from utils.date_helpers import is_weekday

# --- 時刻変換ヘルパー（デバッグ用にapp.pyに配置） ---
def _convert_to_datetime(series, date_series):
    try:
        numeric_series = pd.to_numeric(series, errors='coerce')
        if numeric_series.notna().sum() > 0 and len(series.dropna()) > 0 and (numeric_series.notna().sum() / len(series.dropna()) > 0.8):
            time_deltas = pd.to_timedelta(numeric_series * 24, unit='h', errors='coerce')
            return pd.to_datetime(date_series.astype(str)) + time_deltas
        
        time_only_series = pd.to_datetime(series, errors='coerce', format=None).dt.time
        valid_times = time_only_series.notna()
        combined_dt = pd.Series(pd.NaT, index=series.index)
        
        if valid_times.any():
            date_series_valid = date_series[valid_times]
            time_only_series_valid = time_only_series[valid_times]
            combined_dt.loc[valid_times] = [datetime.combine(d, t) for d, t in zip(date_series_valid, time_only_series_valid)]
        return combined_dt
    except Exception as e:
        st.error(f"時刻変換中にエラーが発生: {e}")
        return pd.Series(pd.NaT, index=series.index)

# --- メインのデバッグ関数 ---
def run_utilization_debug(df):
    st.header("🔬 稼働率計算 デバッグ結果")

    # --- ステップ1: 初期データと列名の確認 ---
    st.subheader("ステップ1: 初期データと列名の検出")
    start_col, end_col, room_col = None, None, None
    possible_start_keys = ['入室時刻', '開始']; possible_end_keys = ['退室時刻', '終了']; possible_room_keys = ['実施手術室', '手術室']
    for col in df.columns:
        if not start_col and any(key in col for key in possible_start_keys): start_col = col
        if not end_col and any(key in col for key in possible_end_keys): end_col = col
        if not room_col and any(key in col for key in possible_room_keys): room_col = col
        if not start_col and 'üº' in col: start_col = col
        if not end_col and 'Þº' in col: end_col = col

    if start_col: st.success(f"✅ 開始時刻の列を検出しました: `{start_col}`")
    else: st.error("❌ 開始時刻の列が見つかりません。"); return
    if end_col: st.success(f"✅ 終了時刻の列を検出しました: `{end_col}`")
    else: st.error("❌ 終了時刻の列が見つかりません。"); return
    if room_col: st.success(f"✅ 手術室の列を検出しました: `{room_col}`")
    else: st.error("❌ 手術室の列が見つかりません。"); return

    # --- ステップ2: 対象期間・曜日のフィルタリング ---
    st.subheader("ステップ2: 期間・曜日のフィルタリング")
    period_df = df[df['手術実施日_dt'] >= (df['手術実施日_dt'].max() - pd.Timedelta(days=29))]
    weekday_df = period_df[period_df['is_weekday']].copy()
    st.write(f"直近30日間のデータ: {len(period_df)}件 → うち平日データ: {len(weekday_df)}件")
    if weekday_df.empty: st.error("平日データが0件のため計算できません。"); return

    # --- ステップ3: 対象手術室のフィルタリング ---
    st.subheader("ステップ3: 対象手術室のフィルタリング")
    target_rooms = ['OR1', 'OR2', 'OR3', 'OR4', 'OR5', 'OR6', 'OR7', 'OR8', 'OR9', 'OR10', 'OR12']
    st.write(f"対象の手術室リスト: `{target_rooms}`")
    
    weekday_df['normalized_room'] = weekday_df[room_col].astype(str).str.upper().str.replace(' ', '').str.replace('OP-', 'OR')
    st.write("データ内の手術室名を正規化（大文字化、スペース削除、'OP-'を'OR'に置換）しました。")
    st.write("**正規化後の手術室名（先頭5件）:**")
    st.dataframe(weekday_df[[room_col, 'normalized_room']].head())

    filtered_df = weekday_df[weekday_df['normalized_room'].isin(target_rooms)].copy()
    st.write(f"平日データ: {len(weekday_df)}件 → 対象11部屋のデータ: **{len(filtered_df)}件**")
    if filtered_df.empty: st.error("対象となる11部屋の手術が1件もありませんでした。これが0%の原因です。"); return
    
    # --- ステップ4: 時刻データの変換 ---
    st.subheader("ステップ4: 時刻データの変換")
    filtered_df['start_datetime'] = _convert_to_datetime(filtered_df[start_col], filtered_df['手術実施日_dt'].dt.date)
    filtered_df['end_datetime'] = _convert_to_datetime(filtered_df[end_col], filtered_df['手術実施日_dt'].dt.date)
    st.write("時刻データを日付と結合し、datetime形式に変換しました。")
    st.write("**変換結果（先頭5件）:**")
    st.dataframe(filtered_df[[start_col, 'start_datetime', end_col, 'end_datetime']].head())
    
    valid_times_df = filtered_df.dropna(subset=['start_datetime', 'end_datetime'])
    st.write(f"有効な時刻データを持つ手術: **{len(valid_times_df)}件**")
    if valid_times_df.empty: st.error("有効な時刻データが1件もありません。時刻形式の変換に失敗している可能性があります。"); return

    # --- ステップ5: 稼働時間（分子）の計算 ---
    st.subheader("ステップ5: 総利用時間（分子）の計算")
    st.write("稼働時間（9:00～17:15）と手術時間が重なる部分を分単位で合計します。")
    
    total_usage_minutes = 0
    op_start_time = time(9, 0); op_end_time = time(17, 15)
    for _, row in valid_times_df.iterrows():
        day = row['手術実施日_dt'].date()
        operation_start = datetime.combine(day, op_start_time)
        operation_end = datetime.combine(day, op_end_time)
        actual_start = max(row['start_datetime'], operation_start)
        actual_end = min(row['end_datetime'], operation_end)
        if actual_end > actual_start:
            total_usage_minutes += (actual_end - actual_start).total_seconds() / 60

    st.metric("計算された総利用時間（分子）", f"{total_usage_minutes:,.1f} 分")
    if total_usage_minutes == 0: st.error("利用時間が0分と計算されました。全ての手術が稼働時間外であるか、時刻データに問題がある可能性があります。")

    # --- ステップ6: 利用可能時間（分母）の計算 ---
    st.subheader("ステップ6: 総利用可能時間（分母）の計算")
    period_start_date = period_df['手術実施日_dt'].min()
    period_end_date = period_df['手術実施日_dt'].max()
    total_weekdays_in_period = sum(1 for d in pd.date_range(period_start_date, period_end_date) if is_weekday(d))
    num_rooms = 11
    total_available_minutes = total_weekdays_in_period * num_rooms * 495

    st.metric("分析期間内の総平日数", f"{total_weekdays_in_period} 日")
    st.metric("対象手術室数", f"{num_rooms} 部屋")
    st.metric("計算された総利用可能時間（分母）", f"{total_available_minutes:,.1f} 分")

    # --- ステップ7: 最終結果 ---
    st.subheader("ステップ7: 最終稼働率")
    final_rate = (total_usage_minutes / total_available_minutes) * 100 if total_available_minutes > 0 else 0
    st.metric("最終算出値", f"{final_rate:.1f} %")


# --- メイン実行部 ---
st.title("稼働率計算デバッグツール")
uploaded_file = st.file_uploader("0512.csv をアップロードしてください", type="csv")

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, encoding='cp932', low_memory=False)
        df = preprocess_dataframe(df) # 共通の前処理を適用
        run_utilization_debug(df)
    except Exception as e:
        st.error("ファイルの読み込みまたは前処理中にエラーが発生しました。")
        st.exception(e)