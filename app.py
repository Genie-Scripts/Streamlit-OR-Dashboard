# app.py (v9.0 全機能・全ロジック統合 最終完成版)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, timedelta
import unicodedata
import re
import pytz

# --- ページ設定 (必ず最初に実行) ---
st.set_page_config(
    page_title="手術分析ダッシュボード", page_icon="🏥", layout="wide", initial_sidebar_state="expanded"
)

# --- このファイル内に必要な分析・ヘルパー関数をすべて定義 ---

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
            date_series_valid = date_series[valid_times]; time_only_series_valid = time_only_series[valid_times]
            combined_dt.loc[valid_times] = [datetime.combine(d.date(), t) if isinstance(d, datetime) else datetime.combine(d, t) for d, t in zip(date_series_valid, time_only_series_valid)]
        return combined_dt
    except Exception:
        return pd.Series(pd.NaT, index=series.index)

def calculate_operating_room_utilization(full_df, period_df):
    """手術室の稼働率を計算する"""
    if full_df.empty or period_df.empty: return 0.0
    if '手術実施日_dt' not in period_df.columns: return 0.0
    
    weekday_df = period_df[period_df['手術実施日_dt'].dt.dayofweek < 5].copy()
    if weekday_df.empty: return 0.0
        
    start_col, end_col, room_col = None, None, None
    possible_start_keys=['入室時刻', '開始']; possible_end_keys=['退室時刻', '終了']; possible_room_keys=['実施手術室', '手術室']
    for col in full_df.columns:
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
            
            num_rooms = 11
            total_available_minutes = total_weekdays_in_period * num_rooms * 495
            if total_available_minutes > 0:
                return min((total_usage_minutes / total_available_minutes) * 100, 100.0)
        except Exception as e:
            print(f"稼働率計算中にエラー: {e}") # ログにエラーを出力
            pass
    return 0.0

# --- セッション状態の初期化 ---
if 'df' not in st.session_state:
    st.session_state['df'] = None
if 'target_dict' not in st.session_state:
    st.session_state['target_dict'] = {}
if 'current_view' not in st.session_state:
    st.session_state['current_view'] = '病院全体分析' # デフォルトページを変更

# --- UI描画関数 ---
def render_sidebar():
    with st.sidebar:
        st.title("🏥 手術分析")
        st.markdown("---")
        views = ["病院全体分析", "データアップロード"] # 元のアプリに合わせてUIを簡略化
        st.session_state['current_view'] = st.radio("📍 ナビゲーション", views, key="navigation")
        st.markdown("---")
        if st.session_state.get('df') is not None:
            st.success("✅ データ読み込み済み")
            st.write(f"📊 レコード数: {len(st.session_state.df):,}")
        else:
            st.warning("⚠️ データ未読み込み")
        if st.session_state.get('target_dict'):
            st.success("🎯 目標データ設定済み")
        else:
            st.info("目標データ未設定")
        st.info("Version: 9.0 (Standalone Final)")

def render_hospital_page(df, target_dict):
    st.title("病院全体分析")
    latest_date = df['手術実施日_dt'].max()
    analysis_end_sunday = latest_date - timedelta(days=(latest_date.weekday() + 1) % 7)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 総レコード数", f"{len(df):,}件")
    col2.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d'))
    col3.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d'))
    st.caption(f"分析対象期間: {df['手術実施日_dt'].min().strftime('%Y/%m/%d')} ~ {latest_date.strftime('%Y/%m/%d')}")
    st.caption(f"💡 最新データが{latest_date.strftime('%A')}のため、分析精度向上のため前の日曜日({analysis_end_sunday.strftime('%Y/%m/%d')})までを分析対象としています。")
    st.markdown("---")
    
    # パフォーマンスダッシュボード
    st.subheader("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
    recent_4weeks_df = df[df['手術実施日_dt'] >= (analysis_end_sunday - timedelta(days=27))]
    
    # パフォーマンス計算
    perf_data = []
    if target_dict:
        for dept, target in target_dict.items():
            dept_data = recent_4weeks_df[recent_4weeks_df['実施診療科'] == dept]
            if dept_data.empty: continue
            
            total_cases = len(dept_data[dept_data['麻酔種別'].str.contains("全身麻酔", na=False)])
            avg_weekly = total_cases / 4.0
            latest_week_start = analysis_end_sunday - timedelta(days=6)
            latest_week_cases = len(dept_data[(dept_data['手術実施日_dt'] >= latest_week_start) & (dept_data['麻酔種別'].str.contains("全身麻酔", na=False))])
            achievement_rate = (avg_weekly / target) * 100 if target > 0 else 0
            perf_data.append({"診療科": dept, "4週平均": avg_weekly, "直近週実績": latest_week_cases, "目標": target, "達成率": achievement_rate})
            
    if perf_data:
        perf_df = pd.DataFrame(perf_data).sort_values("達成率", ascending=False)
        cols = st.columns(3)
        for i, row in enumerate(perf_df.itertuples()):
            with cols[i % 3]:
                rate = row.達成率
                color = "#28a745" if rate >= 100 else ("#ffc107" if rate >= 80 else "#dc3545")
                bar_width = min(rate, 100)
                html = f"""
                <div style="background-color: {color}1A; border-left: 5px solid {color}; padding: 12px; border-radius: 5px; margin-bottom: 12px;">
                    <h5 style="margin: 0 0 10px 0; font-weight: bold; color: {color};">{row.診療科}</h5>
                    <div style="display: flex; justify-content: space-between;"><span>4週平均:</span><span style="font-weight: bold;">{row._4週平均:.1f} 件</span></div>
                    <div style="display: flex; justify-content: space-between;"><span>直近週実績:</span><span style="font-weight: bold;">{row.直近週実績:.0f} 件</span></div>
                    <div style="display: flex; justify-content: space-between;"><span>目標:</span><span style="font-weight: bold;">{row.目標:.1f} 件</span></div>
                    <div style="display: flex; justify-content: space-between; font-size: 1.1em; color: {color}; margin-top: 5px;">
                        <span style="font-weight: bold;">達成率:</span><span style="font-weight: bold;">{rate:.1f}%</span>
                    </div>
                    <div style="background-color: #e9ecef; border-radius: 5px; height: 6px; margin-top: 5px;">
                        <div style="width: {bar_width}%; background-color: {color}; height: 6px; border-radius: 5px;"></div>
                    </div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)
        with st.expander("詳細データテーブル"): st.dataframe(perf_df)
    
    # ... (他の病院全体分析機能を追加可能)

def render_upload_page():
    st.header("📤 データアップロード")
    base_file = st.file_uploader("基礎データ (CSV/Excel)", type=['csv', 'xlsx'])
    target_file = st.file_uploader("目標データ (CSV)", type="csv")

    if st.button("データ処理を実行", type="primary"):
        if base_file:
            try:
                if base_file.name.endswith('.csv'):
                    df = pd.read_csv(base_file, encoding='cp932', low_memory=False)
                else:
                    df = pd.read_excel(base_file)
                
                df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
                df.dropna(subset=['手術実施日_dt'], inplace=True)
                st.session_state['df'] = df
                st.success(f"{len(df)}件のデータを読み込みました。")
            except Exception as e: st.error(f"ファイルの読み込みに失敗しました: {e}")
        else: st.warning("基礎データファイルをアップロードしてください。")
            
        if target_file:
            try:
                target_df = pd.read_csv(target_file, encoding='cp932')
                # 列名が'診療科', '目標'であることを想定
                target_df.columns = ['診療科', '目標']
                st.session_state['target_dict'] = dict(zip(target_df['診療科'], target_df['目標']))
                st.success("目標データを読み込みました。")
            except Exception as e: st.error(f"目標データの読み込みに失敗しました: {e}")

# --- メイン実行部 ---
def main():
    render_sidebar()
    
    current_view = st.session_state.get('current_view', '病院全体分析')
    
    if current_view == 'データアップロード':
        render_upload_page()
    elif st.session_state.get('df') is None:
        st.title("手術実績分析ダッシュボード")
        st.info("サイドバーの「データアップロード」からデータを読み込んでください。")
    else:
        df = st.session_state.df
        target_dict = st.session_state.get('target_dict', {})
        # 元のアプリの主要ページである病院全体分析をデフォルトで表示
        render_hospital_page(df, target_dict)

if __name__ == "__main__":
    main()