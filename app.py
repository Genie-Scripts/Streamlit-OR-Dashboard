# app_dashboard.py - 改修版ダッシュボード形式手術分析アプリ（改行コード対応版）
import streamlit as st
import traceback
import pandas as pd
import numpy as np

try:
    from config.app_config import config, CUSTOM_CSS, PAGE_CONFIG
    CONFIG_LOADED = True
except ImportError as e:
    st.error(f"設定モジュールの読み込みエラー: {e}")
    CONFIG_LOADED = False

try:
    from utils.session_manager import SessionManager
    SESSION_MANAGER_LOADED = True
except ImportError as e:
    st.error(f"セッション管理モジュールの読み込みエラー: {e}")
    SESSION_MANAGER_LOADED = False

try:
    from components.kpi_cards import render_kpi_dashboard, create_summary_kpis
    KPI_CARDS_LOADED = True
except ImportError as e:
    st.error(f"KPIカードモジュールの読み込みエラー: {e}")
    KPI_CARDS_LOADED = False
    
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pytz
from pathlib import Path
try:
    # 完全週データ分析モジュール
    from complete_weeks_analyzer import (
        filter_data_by_complete_weeks,
        analyze_weekly_summary_complete,
        analyze_department_weekly_summary_complete,
        calculate_kpi_weekly_complete,
        get_latest_complete_sunday,
        get_data_cutoff_explanation,
        format_week_period_info_complete,
        get_week_period_options,
        plot_weekly_summary_graph_complete,
        plot_weekly_department_graph_complete,
        calculate_cumulative_cases_complete_weeks,
        plot_cumulative_cases_complete_weeks,
        calculate_department_achievement_rates_complete_weeks,
        plot_achievement_ranking_complete
    )
    COMPLETE_WEEKS_LOADED = True
except Exception as e:
    st.error(f"完全週データ分析モジュールの読み込みエラー: {e}")
    COMPLETE_WEEKS_LOADED = False

# ページ設定
st.set_page_config(**PAGE_CONFIG)

# カスタムCSS（外部化）
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# モジュールインポート（エラーハンドリング付き）
try:
    from loader import load_single_file, merge_base_and_updates
    from analyzer import analyze_hospital_summary, analyze_department_summary, calculate_recent_averages, filter_data_by_period
    from monthly_quarterly_analyzer import analyze_monthly_summary, analyze_quarterly_summary
    from target_loader import load_target_file
    from plotter import plot_summary_graph, plot_department_graph
    from department_ranking import calculate_department_achievement_rates, plot_achievement_ranking
    from surgeon_analyzer import create_surgeon_analysis
    from prediction_tab_enhanced import create_prediction_tab
    
    MODULES_LOADED = True
except Exception as e:
    st.error(f"モジュールの読み込み中に予期せぬエラーが発生しました。")
    st.error(f"エラー内容: {e}")
    st.code(traceback.format_exc())
    MODULES_LOADED = False

# セッション状態の初期化
def initialize_session_state():
    """セッション状態を初期化（新版）"""
    SessionManager.init_session_state()

def split_surgeon_names_by_newline(name_string):
    """改行コードで術者名を分割する関数"""
    if not name_string or pd.isna(name_string):
        return []
    
    name_string = str(name_string).strip()
    
    # 無効値のチェック
    if name_string.lower() in ['nan', 'null', '', 'なし', '-']:
        return []
    
    # 改行コードで分割（\r\n, \n両方に対応）
    if '\r\n' in name_string:
        parts = [part.strip() for part in name_string.split('\r\n')]
    elif '\n' in name_string:
        parts = [part.strip() for part in name_string.split('\n')]
    else:
        # 改行コードがない場合は単一の術者として扱う
        return [name_string]
    
    # 空文字列を除去
    return [part for part in parts if part]

def clean_surgeon_name(name):
    """術者名をクリーニングする関数"""
    if not name:
        return None
    
    name = str(name).strip()
    
    # 無効な値を除外
    if (name.lower() in ['nan', 'null', 'なし', '-', '他', 'その他', '不明', '外来', '当直'] or
        len(name) < 2):
        return None
    
    # 全角・半角の統一
    name = name.replace('（', '(').replace('）', ')').replace('　', ' ')
    
    # 括弧内の情報を除去（役職など）
    if '(' in name and ')' in name:
        name = name.split('(')[0].strip()
    
    # 敬称の除去
    suffixes = ['先生', '医師', 'Dr.', 'Dr', 'MD', '教授', '准教授', '講師', '助教']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    
    # 数字のみの場合は除外
    if name.isdigit():
        return None
    
    # 最終的な妥当性チェック
    if len(name) >= 2 and not name.isdigit():
        return name
    
    return None

def calculate_operating_room_utilization(df_gas, latest_date):
    """手術室稼働率を計算"""
    try:
        # 平日データのみを抽出（土日を除く）
        weekday_df = df_gas[df_gas['手術実施日_dt'].dt.dayofweek < 5].copy()
        
        if weekday_df.empty:
            return 0.0
        
        # 手術室情報がある場合の処理（列名を推測）
        room_columns = ['手術室', 'OR', '部屋', 'Room', '手術室番号']
        room_col = None
        for col in room_columns:
            if col in weekday_df.columns:
                room_col = col
                break
        
        # 時刻情報がある場合の処理（列名を推測）
        start_time_columns = ['入室時刻', '開始時刻', 'Start_Time', '麻酔開始時刻', '手術開始時刻']
        end_time_columns = ['退室時刻', '終了時刻', 'End_Time', '麻酔終了時刻', '手術終了時刻']
        
        start_col = None
        end_col = None
        
        for col in start_time_columns:
            if col in weekday_df.columns:
                start_col = col
                break
                
        for col in end_time_columns:
            if col in weekday_df.columns:
                end_col = col
                break
        
        # 詳細な稼働率計算（データがある場合）
        if room_col and start_col and end_col:
            target_rooms = ['OR1', 'OR2', 'OR3', 'OR4', 'OR5', 'OR6', 'OR7', 'OR8', 'OR9', 'OR10', 'OR12']
            
            # 対象手術室でフィルタリング
            filtered_df = weekday_df[weekday_df[room_col].isin(target_rooms)].copy()
            
            if filtered_df.empty:
                return 0.0
            
            total_usage_minutes = 0
            
            for _, row in filtered_df.iterrows():
                try:
                    # 時刻の解析
                    start_time = pd.to_datetime(row[start_col])
                    end_time = pd.to_datetime(row[end_col])
                    
                    # 9:00-17:15の範囲に制限
                    operation_start = pd.Timestamp.combine(start_time.date(), pd.Timestamp('09:00:00').time())
                    operation_end = pd.Timestamp.combine(end_time.date(), pd.Timestamp('17:15:00').time())
                    
                    actual_start = max(start_time, operation_start)
                    actual_end = min(end_time, operation_end)
                    
                    if actual_end > actual_start:
                        usage_minutes = (actual_end - actual_start).total_seconds() / 60
                        total_usage_minutes += usage_minutes
                        
                except (ValueError, TypeError):
                    continue
            
            # 稼働率計算
            total_operating_days = weekday_df['手術実施日_dt'].nunique()
            total_available_minutes = total_operating_days * 11 * (8 * 60 + 15)  # 8時間15分 × 11部屋
            
            if total_available_minutes > 0:
                utilization_rate = (total_usage_minutes / total_available_minutes) * 100
                return min(utilization_rate, 100.0)  # 100%を上限とする
            
        # 簡易計算（詳細データがない場合）
        total_cases = len(weekday_df)
        total_operating_days = weekday_df['手術実施日_dt'].nunique()
        
        if total_operating_days > 0:
            # 1日平均手術件数から推定稼働率を計算
            avg_cases_per_day = total_cases / total_operating_days
            estimated_utilization = min((avg_cases_per_day / 20) * 100, 100)  # 20件/日を100%稼働として推定
            return estimated_utilization
        
        return 0.0
        
    except Exception as e:
        print(f"稼働率計算エラー: {e}")
        return 0.0

def analyze_surgeon_data_enhanced(df_dept, dept_name):
    """改良版術者分析（改行コード対応版）"""
    surgeon_column = None
    
    # 術者列を特定
    for col in df_dept.columns:
        if '術者' in col or '実施術者' in col or 'surgeon' in col.lower():
            surgeon_column = col
            break
    
    if not surgeon_column:
        return pd.DataFrame()
    
    surgeon_records = []
    
    for _, row in df_dept.iterrows():
        surgeons_str = str(row[surgeon_column])
        
        # 改行コードで複数術者を分割
        individual_names = split_surgeon_names_by_newline(surgeons_str)
        
        # 各名前をクリーニング
        cleaned_names = []
        for name in individual_names:
            cleaned_name = clean_surgeon_name(name)
            if cleaned_name:
                cleaned_names.append(cleaned_name)
        
        # 重複除去（順序保持）
        unique_names = list(dict.fromkeys(cleaned_names))
        
        # 各術者に対してレコードを作成
        for surgeon_name in unique_names:
            surgeon_records.append({
                '術者': surgeon_name,
                '手術実施日_dt': row.get('手術実施日_dt', row.get('手術実施日', None)),
                '診療科': dept_name,
                '重み': 1.0 / len(unique_names) if len(unique_names) > 1 else 1.0
            })
    
    if not surgeon_records:
        return pd.DataFrame()
    
    surgeon_df = pd.DataFrame(surgeon_records)
    
    # 術者別集計（重みを考慮）
    surgeon_summary = surgeon_df.groupby('術者')['重み'].sum().round(1).sort_values(ascending=False)
    
    return surgeon_summary.head(10)

def create_comprehensive_surgeon_analysis(df_gas, target_dict):
    """全診療科の術者分析を作成（改行コード対応版）"""
    st.header("👨‍⚕️ 総合術者分析（改行コード対応版）")
    
    if df_gas is None or df_gas.empty:
        st.warning("データが読み込まれていません。")
        return
    
    # 術者列を特定
    surgeon_column = None
    for col in df_gas.columns:
        if '術者' in col or '実施術者' in col or 'surgeon' in col.lower():
            surgeon_column = col
            break
    
    if not surgeon_column:
        st.error("術者列が見つかりません。利用可能な列:")
        st.write(list(df_gas.columns))
        return
    
    # 分割処理のテスト表示（実際のデータ例で）
    st.subheader("🔍 分割処理テスト（実データ例）")
    
    sample_data = df_gas[surgeon_column].dropna().head(10)
    st.write(f"**実データでの分割処理例（{surgeon_column}列）:**")
    
    for i, example in enumerate(sample_data):
        if example and len(str(example)) > 5:  # 複数術者っぽいデータのみ表示
            split_result = split_surgeon_names_by_newline(example)
            if len(split_result) > 1:
                st.write(f"例{i+1}: `{example}` → {split_result}")
    
    st.markdown("---")
    
    # 全診療科の術者データを統合分析
    all_surgeon_records = []
    
    for dept in df_gas['実施診療科'].dropna().unique():
        dept_data = df_gas[df_gas['実施診療科'] == dept]
        
        for _, row in dept_data.iterrows():
            surgeons_str = str(row[surgeon_column])
            
            # 改行コードで複数術者を分割
            individual_names = split_surgeon_names_by_newline(surgeons_str)
            
            # 各名前をクリーニング
            cleaned_names = []
            for name in individual_names:
                cleaned_name = clean_surgeon_name(name)
                if cleaned_name:
                    cleaned_names.append(cleaned_name)
            
            # 重複除去
            unique_names = list(dict.fromkeys(cleaned_names))
            
            # 各術者のレコードを作成
            for surgeon_name in unique_names:
                all_surgeon_records.append({
                    '術者': surgeon_name,
                    '診療科': dept,
                    '手術実施日_dt': row.get('手術実施日_dt', row.get('手術実施日', None)),
                    '重み': 1.0 / len(unique_names) if len(unique_names) > 1 else 1.0
                })
    
    if not all_surgeon_records:
        st.warning("分析可能な術者データがありません。")
        return
    
    all_surgeon_df = pd.DataFrame(all_surgeon_records)
    
    # 全体ランキング
    surgeon_ranking = all_surgeon_df.groupby('術者')['重み'].sum().round(1).sort_values(ascending=False)
    
    # 表示
    st.subheader("🏆 個別術者ランキング (Top 30)")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # トップ30のグラフ
        top_30 = surgeon_ranking.head(30)
        fig_all = px.bar(
            x=top_30.values,
            y=top_30.index,
            orientation='h',
            title="術者別手術件数 (Top 30) - 改行コード分割対応",
            text=top_30.values
        )
        fig_all.update_traces(texttemplate='%{text:.1f}', textposition='outside')
        fig_all.update_layout(height=900, showlegend=False)
        fig_all.update_xaxes(title="手術件数")
        fig_all.update_yaxes(title="術者", categoryorder='total ascending')
        st.plotly_chart(fig_all, use_container_width=True)
    
    with col2:
        # 統計情報
        st.markdown("#### 📊 分割後統計")
        st.metric("総術者数", len(surgeon_ranking))
        st.metric("総手術件数", f"{surgeon_ranking.sum():.1f}")
        st.metric("平均件数/術者", f"{surgeon_ranking.mean():.1f}")
        st.metric("最多術者件数", f"{surgeon_ranking.iloc[0]:.1f}")
        
        st.markdown("#### 🔍 分割効果")
        # 分割前のデータサンプル表示
        original_surgeons = df_gas[surgeon_column].value_counts().head(10)
        st.write("**分割前Top5:**")
        for surgeon, count in original_surgeons.head(5).items():
            # 長い場合は省略表示
            display_name = surgeon if len(str(surgeon)) < 30 else str(surgeon)[:30] + "..."
            st.write(f"{display_name}: {count}")
        
        st.write("**分割後Top5:**")
        for surgeon, count in surgeon_ranking.head(5).items():
            st.write(f"{surgeon}: {count:.1f}")
    
    # 詳細テーブル
    st.subheader("📋 詳細ランキングテーブル (Top 50)")
    
    # 診療科別件数も追加
    surgeon_dept_summary = all_surgeon_df.groupby(['術者', '診療科'])['重み'].sum().unstack(fill_value=0)
    surgeon_total = surgeon_dept_summary.sum(axis=1).round(1).sort_values(ascending=False)
    
    # トップ50の詳細テーブル
    top_50_surgeons = surgeon_total.head(50).index
    detail_data = []
    
    for i, surgeon in enumerate(top_50_surgeons, 1):
        total_cases = surgeon_total[surgeon]
        main_dept = surgeon_dept_summary.loc[surgeon].idxmax()  # 最も件数が多い診療科
        main_dept_cases = surgeon_dept_summary.loc[surgeon, main_dept]
        
        detail_data.append({
            '順位': i,
            '術者': surgeon,
            '総件数': total_cases,
            '主要診療科': main_dept,
            '主要診療科件数': main_dept_cases,
            '診療科数': (surgeon_dept_summary.loc[surgeon] > 0).sum()
        })
    
    detail_df = pd.DataFrame(detail_data)
    
    st.dataframe(
        detail_df.style.format({
            '総件数': '{:.1f}',
            '主要診療科件数': '{:.1f}'
        }).apply(lambda x: [
            'background-color: rgba(255, 215, 0, 0.3)' if x['順位'] <= 3 else
            'background-color: rgba(192, 192, 192, 0.3)' if x['順位'] <= 10 else
            'background-color: rgba(31, 119, 180, 0.1)' if x['順位'] % 2 == 0 else ''
            for _ in range(len(x))
        ], axis=1),
        use_container_width=True,
        hide_index=True
    )

def create_kpi_card(title, value, change=None, change_label="前期比"):
    """KPIカードを作成"""
    # 変化の色を決定
    change_class = ""
    change_icon = ""
    if change is not None:
        if change > 0:
            change_class = "positive"
            change_icon = "↗"
        elif change < 0:
            change_class = "negative"
            change_icon = "↘"
        else:
            change_class = "neutral"
            change_icon = "→"
    
    change_text = f"{change_icon} {change:+.1f}% {change_label}" if change is not None else ""
    
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-change {change_class}">{change_text}</div>
    </div>
    """

def render_main_dashboard():
    """メインダッシュボード - 統合版（完全週データ機能の有無で分岐）"""
    if not MODULES_LOADED:
        st.error("必要なモジュールが読み込まれていません。")
        return
    
    # 完全週データ機能が利用可能な場合
    if COMPLETE_WEEKS_LOADED:
        render_main_dashboard_complete_weeks()
    else:
        # 従来版にフォールバック
        render_main_dashboard_legacy()

def render_main_dashboard_legacy():
    """メインダッシュボード（従来版）"""
    # ヘッダー
    st.markdown("""
    <div class="main-header">
        <h1 class="dashboard-title">🏥 手術分析ダッシュボード</h1>
        <p class="dashboard-subtitle">全身麻酔手術件数の包括的分析と予測</p>
    </div>
    """, unsafe_allow_html=True)
    
    # データが読み込まれているかチェック
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("📊 データをアップロードしてください")
        st.info("サイドバーの「データアップロード」からCSVファイルを読み込んでください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    # フィルタセクション
    with st.container():
        st.markdown('<div class="filter-section">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            period_filter = st.selectbox("📅 分析期間", 
                                       ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
                                       index=1)
        
        with col2:
            departments = ["全診療科"] + sorted(df_gas["実施診療科"].dropna().unique().tolist())
            dept_filter = st.selectbox("🏥 診療科", departments)
        
        with col3:
            view_type = st.selectbox("📊 表示形式", 
                                   ["週次", "月次", "四半期"],
                                   index=0)
        
        with col4:
            auto_refresh = st.checkbox("🔄 自動更新", value=False)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # データフィルタリング
    filtered_df = filter_data_by_period(df_gas, period_filter)
    if dept_filter != "全診療科":
        filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
    
    # KPI計算
    # 1. 総手術件数
    total_cases = len(filtered_df)
    
    # 2. 全身麻酔手術件数
    gas_cases = len(filtered_df[
        filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
        filtered_df['麻酔種別'].str.contains("20分以上", na=False)
    ])
    
    # 3. 平日データを抽出
    weekday_df = filtered_df[filtered_df['手術実施日_dt'].dt.dayofweek < 5]
    gas_weekday_df = weekday_df[
        weekday_df['麻酔種別'].str.contains("全身麻酔", na=False) &
        weekday_df['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 平日1日平均全身麻酔手術件数
    weekday_count = weekday_df['手術実施日_dt'].nunique()
    daily_avg_gas = len(gas_weekday_df) / weekday_count if weekday_count > 0 else 0
    
    # 4. 稼働率計算
    utilization_rate = calculate_operating_room_utilization(filtered_df, latest_date)
    
    # 前期比較計算（簡易版）
    prev_total = total_cases * 0.95  # 仮の前期データ
    change_rate = ((total_cases - prev_total) / prev_total * 100) if prev_total > 0 else 0
    
    # KPIカード表示（修正版）
    st.markdown("### 📊 主要指標")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_kpi_card(
            f"総手術件数 ({period_filter})",
            f"{total_cases:,}",
            change_rate
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_kpi_card(
            "全身麻酔手術件数",
            f"{gas_cases:,}",
            change_rate * 0.9
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_kpi_card(
            "平日1日平均全身麻酔",
            f"{daily_avg_gas:.1f}",
            change_rate * 0.8
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_kpi_card(
            "稼働率",
            f"{utilization_rate:.1f}%",
            2.3
        ), unsafe_allow_html=True)
    
    # メインチャートエリア
    st.markdown("### 📈 トレンド分析")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.container():
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            
            # トレンドグラフ
            if view_type == "週次":
                if dept_filter == "全診療科":
                    summary_data = analyze_hospital_summary(filtered_df)
                    if not summary_data.empty:
                        fig = plot_summary_graph(summary_data, "全科", target_dict, 4)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    summary_data = analyze_department_summary(filtered_df, dept_filter)
                    if not summary_data.empty:
                        fig = plot_department_graph(summary_data, dept_filter, target_dict, 4)
                        st.plotly_chart(fig, use_container_width=True)
            elif view_type == "月次":
                summary_data = analyze_monthly_summary(filtered_df)
                if not summary_data.empty:
                    # 月次グラフの作成（簡易版）
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=summary_data['月'],
                        y=summary_data['平日1日平均件数'],
                        mode='lines+markers',
                        name='月次推移'
                    ))
                    fig.update_layout(title="月次推移", xaxis_title="月", yaxis_title="平日1日平均件数")
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.markdown("#### 🎯 診療科別実績")
            
            # 診療科別実績表示
            if dept_filter == "全診療科":
                # トップ診療科の表示
                dept_summary = filtered_df.groupby('実施診療科').size().sort_values(ascending=False).head(10)
                
                # 棒グラフ
                fig = px.bar(
                    x=dept_summary.values,
                    y=dept_summary.index,
                    orientation='h',
                    title="診療科別件数 (Top 10)"
                )
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                # 選択された診療科の詳細
                dept_data = filtered_df[filtered_df["実施診療科"] == dept_filter]
                dept_cases = len(dept_data[
                    dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
                    dept_data['麻酔種別'].str.contains("20分以上", na=False)
                ])
                
                st.metric("選択診療科件数", dept_cases)
                
                # 週間分布
                if not dept_data.empty:
                    dept_data_copy = dept_data.copy()
                    dept_data_copy['曜日'] = dept_data_copy['手術実施日_dt'].dt.day_name()
                    weekday_dist = dept_data_copy.groupby('曜日').size()
                    
                    fig = px.pie(
                        values=weekday_dist.values,
                        names=weekday_dist.index,
                        title="曜日別分布"
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # 詳細分析セクション
    st.markdown("### 📋 詳細分析")
    
    tab1, tab2, tab3 = st.tabs(["📊 統計情報", "🏆 ランキング", "📈 予測"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # 統計テーブル
            if view_type == "週次":
                recent_stats = calculate_recent_averages(filtered_df)
                if not recent_stats.empty:
                    st.dataframe(recent_stats, use_container_width=True)
        
        with col2:
            # 期間分析
            if not filtered_df.empty:
                st.write("📅 データ期間")
                st.write(f"開始日: {filtered_df['手術実施日_dt'].min().strftime('%Y/%m/%d')}")
                st.write(f"終了日: {filtered_df['手術実施日_dt'].max().strftime('%Y/%m/%d')}")
                st.write(f"総日数: {(filtered_df['手術実施日_dt'].max() - filtered_df['手術実施日_dt'].min()).days + 1}日")
    
    with tab2:
        # ランキング表示
        if target_dict and dept_filter == "全診療科":
            achievement_rates, achievement_summary = calculate_department_achievement_rates(filtered_df, target_dict)
            if not achievement_rates.empty:
                fig_rank = plot_achievement_ranking(achievement_rates, 10)
                st.plotly_chart(fig_rank, use_container_width=True)
                
                st.dataframe(achievement_rates.head(10), use_container_width=True)
        else:
            st.info("目標データがセットされている場合に診療科別ランキングが表示されます。")
    
    with tab3:
        # 簡易予測表示
        st.info("詳細な予測分析は「将来予測」セクションをご利用ください。")
        
        # 簡易トレンド分析
        if not filtered_df.empty:
            recent_trend = filtered_df.groupby(filtered_df['手術実施日_dt'].dt.date).size().tail(7).mean()
            st.metric("直近7日平均", f"{recent_trend:.1f} 件/日")

def render_main_dashboard_complete_weeks():
    """メインダッシュボード（完全週データ対応版）"""
    # ヘッダー
    st.markdown("""
    <div class="main-header">
        <h1 class="dashboard-title">🏥 手術分析ダッシュボード</h1>
        <p class="dashboard-subtitle">完全週データ（月曜〜日曜）による全身麻酔手術件数の精密分析</p>
    </div>
    """, unsafe_allow_html=True)
    
    # データが読み込まれているかチェック
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("📊 データをアップロードしてください")
        st.info("サイドバーの「データアップロード」からCSVファイルを読み込んでください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    # データの状況を先に表示
    st.markdown("### 📅 データ状況")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 総レコード数", f"{len(df_gas):,}件")
    
    with col2:
        st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d (%A)'))
    
    with col3:
        analysis_end_sunday = get_latest_complete_sunday(latest_date)
        st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d (%A)'))
    
    # データカットオフの説明
    cutoff_explanation = get_data_cutoff_explanation(latest_date, analysis_end_sunday)
    
    if latest_date.date() != analysis_end_sunday.date():
        st.info(f"💡 **分析精度向上のため完全な週のみを使用**: {cutoff_explanation}")
    else:
        st.success(f"✅ **最新データが日曜日のため現在週まで分析可能**: {cutoff_explanation}")
    
    # フィルタセクション
    st.markdown("### ⚙️ 分析設定")
    with st.container():
        st.markdown('<div class="filter-section">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            period_filter = st.selectbox("📅 分析期間", 
                                       get_week_period_options(),
                                       index=1,  # 直近4週をデフォルト
                                       help="完全な週（月曜〜日曜）のデータのみを使用")
        
        with col2:
            departments = ["全診療科"] + sorted(df_gas["実施診療科"].dropna().unique().tolist())
            dept_filter = st.selectbox("🏥 診療科", departments)
        
        with col3:
            view_type = st.selectbox("📊 表示形式", 
                                   ["週次", "月次", "四半期"],
                                   index=0)
        
        with col4:
            show_incomplete_warning = st.checkbox("⚠️ 不完全週警告", value=True,
                                                help="週の途中でデータが切れている場合に警告を表示")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # データフィルタリング（完全週のみ）
    filtered_df = filter_data_by_complete_weeks(df_gas, period_filter, latest_date)
    if dept_filter != "全診療科":
        filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
    
    # 期間情報表示
    if not filtered_df.empty:
        start_date = filtered_df['手術実施日_dt'].min()
        end_date = filtered_df['手術実施日_dt'].max()
        total_weeks = int((end_date - start_date).days / 7) + 1
        
        period_info = format_week_period_info_complete(
            period_filter, start_date, end_date, total_weeks, latest_date
        )
        st.info(period_info)
    else:
        st.warning("選択した条件に該当する完全週データがありません。")
        return
    
    # KPI計算（完全週のみ）
    kpi_data = calculate_kpi_weekly_complete(filtered_df, latest_date)
    
    # 稼働率計算
    utilization_rate = calculate_operating_room_utilization(filtered_df, latest_date)
    
    # KPIカード表示（完全週対応）
    st.markdown("### 📊 主要指標（完全週データ分析）")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        latest_week_label = f"{kpi_data.get('latest_week_start', latest_date).strftime('%m/%d')}～{kpi_data.get('latest_week_end', latest_date).strftime('%m/%d')}"
        st.markdown(create_kpi_card(
            f"最新完全週 ({latest_week_label})",
            f"{kpi_data.get('latest_week_weekday', 0)}件",
            kpi_data.get('weekday_change', 0)
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_kpi_card(
            "最新週総手術件数",
            f"{kpi_data.get('latest_week_total', 0)}件",
            kpi_data.get('total_change', 0)
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_kpi_card(
            "過去4週平均",
            f"{kpi_data.get('avg_4week_weekday', 0):.1f}件/週",
            2.3  # 仮の変化率
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_kpi_card(
            "手術室稼働率",
            f"{utilization_rate:.1f}%",
            1.5
        ), unsafe_allow_html=True)
    
    # メインチャートエリア
    st.markdown("### 📈 週次トレンド分析（完全週データ）")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.container():
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            
            # 週次トレンドグラフ
            if dept_filter == "全診療科":
                summary_data = analyze_weekly_summary_complete(filtered_df, target_dict, latest_date)
                if not summary_data.empty:
                    fig = plot_weekly_summary_graph_complete(summary_data, "全科", target_dict, show_incomplete_warning)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                summary_data = analyze_department_weekly_summary_complete(filtered_df, dept_filter, target_dict, latest_date)
                if not summary_data.empty:
                    fig = plot_weekly_department_graph_complete(summary_data, dept_filter, target_dict, show_incomplete_warning)
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.markdown("#### 🎯 最新週次実績")
            
            # 最新完全週の詳細情報
            if kpi_data:
                latest_week_start = kpi_data.get('latest_week_start')
                latest_week_end = kpi_data.get('latest_week_end')
                
                if latest_week_start and latest_week_end:
                    st.write(f"**分析対象週**: {latest_week_start.strftime('%Y/%m/%d')} ～ {latest_week_end.strftime('%Y/%m/%d')}")
                    
                    # 曜日別実績（最新週）
                    latest_week_data = filtered_df[
                        (filtered_df['手術実施日_dt'] >= latest_week_start) &
                        (filtered_df['手術実施日_dt'] <= latest_week_end)
                    ]
                    
                    if not latest_week_data.empty:
                        if dept_filter != "全診療科":
                            latest_week_data = latest_week_data[latest_week_data["実施診療科"] == dept_filter]
                        
                        # 全身麻酔手術のみ
                        gas_data = latest_week_data[
                            latest_week_data['麻酔種別'].str.contains("全身麻酔", na=False) &
                            latest_week_data['麻酔種別'].str.contains("20分以上", na=False)
                        ]
                        
                        if not gas_data.empty:
                            # 曜日別件数
                            daily_counts = gas_data.groupby(gas_data['手術実施日_dt'].dt.day_name()).size()
                            
                            # 曜日順に並び替え
                            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                            daily_counts = daily_counts.reindex(weekday_order, fill_value=0)
                            
                            # 日本語曜日に変換
                            jp_weekdays = ['月', '火', '水', '木', '金', '土', '日']
                            
                            st.write("**曜日別件数**:")
                            for i, (eng_day, count) in enumerate(daily_counts.items()):
                                jp_day = jp_weekdays[i]
                                if i < 5:  # 平日
                                    st.write(f"• {jp_day}曜日: {count}件")
                                else:  # 土日
                                    st.write(f"• {jp_day}曜日: {count}件 (休日)")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # 詳細分析セクション
    st.markdown("### 📋 詳細分析（完全週データ）")
    
    tab1, tab2, tab3 = st.tabs(["📊 週次統計", "🏆 診療科ランキング", "⚠️ データ品質"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # 週次統計テーブル
            if dept_filter == "全診療科":
                summary_data = analyze_weekly_summary_complete(filtered_df, target_dict, latest_date)
            else:
                summary_data = analyze_department_weekly_summary_complete(filtered_df, dept_filter, target_dict, latest_date)
            
            if not summary_data.empty:
                st.subheader("📊 週次実績一覧")
                display_columns = ['週ラベル', '平日件数', '平日1日平均']
                if '目標件数' in summary_data.columns:
                    display_columns.extend(['目標件数', '達成率'])
                
                # 最新8週を表示
                recent_summary = summary_data[display_columns].tail(8)
                
                st.dataframe(
                    recent_summary.style.apply(lambda x: [
                        'background-color: rgba(76, 175, 80, 0.2)' if i == len(x) - 1 else
                        'background-color: rgba(31, 119, 180, 0.1)' if i % 2 == 0 else ''
                        for i in range(len(x))
                    ], axis=1),
                    use_container_width=True
                )
        
        with col2:
            # 週次統計サマリー
            if not summary_data.empty:
                st.subheader("📈 統計サマリー")
                st.metric("分析週数", len(summary_data))
                st.metric("週平均件数", f"{summary_data['平日件数'].mean():.1f}")
                st.metric("最高週件数", summary_data['平日件数'].max())
                st.metric("最低週件数", summary_data['平日件数'].min())
                
                if '達成率' in summary_data.columns:
                    avg_achievement = summary_data['達成率'].mean()
                    st.metric("平均達成率", f"{avg_achievement:.1f}%")
                
                # 傾向分析
                if len(summary_data) >= 4:
                    recent_4_avg = summary_data['平日件数'].tail(4).mean()
                    prev_4_avg = summary_data['平日件数'].iloc[-8:-4].mean() if len(summary_data) >= 8 else 0
                    
                    if prev_4_avg > 0:
                        trend = (recent_4_avg - prev_4_avg) / prev_4_avg * 100
                        st.metric("直近4週vs前4週", f"{trend:+.1f}%")
    
    with tab2:
        # ランキング表示
        if target_dict and dept_filter == "全診療科":
            st.subheader("🏆 診療科別達成率ランキング（完全週データ）")
            
            # 完全週データで診療科別達成率を計算
            achievement_rates_complete = calculate_department_achievement_rates_complete_weeks(
                filtered_df, target_dict, latest_date
            )
            
            if not achievement_rates_complete.empty:
                fig_rank = plot_achievement_ranking_complete(achievement_rates_complete, 10)
                st.plotly_chart(fig_rank, use_container_width=True)
                
                st.dataframe(achievement_rates_complete.head(10), use_container_width=True)
        else:
            st.info("目標データがセットされている場合に診療科別ランキングが表示されます。")
    
    with tab3:
        # データ品質情報
        st.subheader("📊 データ品質情報")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**完全週データの利点**:")
            st.write("• 週の途中で切れたデータによる誤解を防止")
            st.write("• 前週や過去との正確な比較が可能")
            st.write("• 一貫した週単位での分析")
            st.write("• 曜日効果の正確な評価")
        
        with col2:
            st.write("**データカットオフ情報**:")
            st.write(f"• 最新データ日: {latest_date.strftime('%Y/%m/%d (%A)')}")
            st.write(f"• 分析終了日: {analysis_end_sunday.strftime('%Y/%m/%d (%A)')}")
            
            if latest_date.date() != analysis_end_sunday.date():
                excluded_days = (latest_date - analysis_end_sunday).days
                st.write(f"• 除外された日数: {excluded_days}日")
                st.write("• 理由: 週の途中でデータが切れているため")
            else:
                st.write("• 除外された日数: 0日")
                st.write("• 理由: 最新データが日曜日のため")

def render_upload_section():
    """データアップロードセクション"""
    st.header("📤 データアップロード")
    
    # アップロード手順の説明
    with st.expander("📋 アップロード手順", expanded=True):
        st.markdown("""
        ### ステップ1: 基礎データのアップロード
        - 手術実績データ(CSV)をアップロードしてください
        - 必須列: 手術実施日, 麻酔種別, 実施診療科
        
        ### ステップ2: 目標データのアップロード（任意）
        - 診療科別の目標件数データ(CSV)をアップロードしてください
        - 必須列: 診療科, 目標件数
        
        ### ステップ3: 追加データのアップロード（任意）
        - 基礎データ以降の最新データがあればアップロードしてください
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔧 基礎データ")
        uploaded_base_file = st.file_uploader(
            "基礎データCSV", 
            type="csv", 
            key="base_uploader",
            help="必須。手術実績データ全体。"
        )
        
        if uploaded_base_file:
            try:
                with st.spinner("基礎データを読み込み中..."):
                    st.session_state['base_df'] = load_single_file(uploaded_base_file)
                st.success("✅ 基礎データを読み込みました。")
                
                with st.expander("📊 基礎データ概要"):
                    base_df = st.session_state['base_df']
                    st.write(f"レコード数: {len(base_df):,}件")
                    if '手術実施日_dt' in base_df.columns:
                        st.write(f"期間: {base_df['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {base_df['手術実施日_dt'].max().strftime('%Y/%m/%d')}")
                        st.session_state['latest_date'] = base_df['手術実施日_dt'].max()
                    st.dataframe(base_df.head(), use_container_width=True)
                    
            except Exception as e:
                st.error(f"❌ 基礎データ読込エラー: {e}")
    
    with col2:
        st.subheader("🎯 目標データ")
        uploaded_target_file = st.file_uploader(
            "目標データCSV", 
            type="csv", 
            key="target_uploader",
            help="任意。列名例: '診療科', '目標'"
        )
        
        if uploaded_target_file:
            try:
                with st.spinner("目標データを読み込み中..."):
                    st.session_state['target_dict'] = load_target_file(uploaded_target_file)
                st.success("✅ 目標データを読み込みました。")
                
                with st.expander("🎯 目標データ概要"):
                    if st.session_state['target_dict']:
                        target_df = pd.DataFrame({
                            '診療科': list(st.session_state['target_dict'].keys()),
                            '目標件数/週': list(st.session_state['target_dict'].values())
                        })
                        st.dataframe(target_df, use_container_width=True)
                    else:
                        st.write("目標データは空です。")
                        
            except Exception as e:
                st.error(f"❌ 目標データ読込エラー: {e}")
    
    # 追加データアップロード
    st.subheader("📈 追加データ（任意）")
    uploaded_update_files = st.file_uploader(
        "追加データCSV", 
        type="csv", 
        accept_multiple_files=True,
        key="update_uploader",
        help="基礎データと同じ形式のCSV。"
    )
    
    # データ統合処理
    if st.session_state.get('base_df') is not None:
        base_to_merge = st.session_state['base_df'].copy()
        
        try:
            if uploaded_update_files:
                with st.spinner("データを統合中..."):
                    st.session_state['df_gas'] = merge_base_and_updates(base_to_merge, uploaded_update_files)
            else:
                st.session_state['df_gas'] = base_to_merge
            
            st.success("✅ データ準備完了")
            
            # 統合後の情報表示
            if st.session_state.get('df_gas') is not None:
                final_df = st.session_state['df_gas']
                if '手術実施日_dt' in final_df.columns:
                    st.session_state['latest_date'] = final_df['手術実施日_dt'].max()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 総レコード数", f"{len(final_df):,}")
                    with col2:
                        st.metric("📅 データ期間", 
                                f"{final_df['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
                    with col3:
                        st.metric("🏥 診療科数", final_df['実施診療科'].nunique())
                        
        except Exception as e:
            st.error(f"❌ データ統合エラー: {e}")

def render_hospital_analysis():
    """病院全体分析画面 - 統合版（完全週データ機能の有無で分岐）"""
    if not MODULES_LOADED:
        st.error("必要なモジュールが読み込まれていません。")
        return
    
    # 完全週データ機能が利用可能な場合
    if COMPLETE_WEEKS_LOADED:
        render_hospital_analysis_complete_weeks()
    else:
        # 従来版にフォールバック
        render_hospital_analysis_legacy()

def render_hospital_analysis_legacy():
    """病院全体分析画面（従来版）"""
    st.header("🏥 病院全体分析")
    
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("データをアップロードしてください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    st.info(f"分析対象期間: {df_gas['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {latest_date.strftime('%Y/%m/%d')}")
    
    # 診療科別パフォーマンスダッシュボードを追加
    create_department_dashboard(df_gas, target_dict, latest_date)
    
    st.markdown("---")
    
    # 分析設定
    col1, col2, col3 = st.columns(3)
    
    with col1:
        analysis_type = st.radio("📊 分析対象", ["全身麻酔手術", "全手術"], horizontal=True, key="hospital_analysis_type")
    
    with col2:
        period_filter = st.selectbox("📅 分析期間", 
                                   ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
                                   index=1, key="hospital_period_filter")
    
    with col3:
        view_type = st.selectbox("📊 表示形式", 
                               ["週次", "月次", "四半期"],
                               index=0, key="hospital_view_type")
    
    # データフィルタリング
    filtered_df = filter_data_by_period(df_gas, period_filter)
    
    # 分析対象に応じてデータを絞り込み
    if analysis_type == "全身麻酔手術":
        analysis_df = filtered_df[
            filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
            filtered_df['麻酔種別'].str.contains("20分以上", na=False)
        ]
    else:
        analysis_df = filtered_df
    
    # 週次分析
    if view_type == "週次":
        st.subheader(f"📈 {analysis_type} - 週次推移")
        
        summary_data = analyze_hospital_summary(analysis_df)
        if not summary_data.empty:
            fig = plot_summary_graph(summary_data, f"全科({analysis_type})", target_dict, 4)
            st.plotly_chart(fig, use_container_width=True)
            
            # 統計情報
            with st.expander("週次統計詳細"):
                st.dataframe(summary_data, use_container_width=True)
        else:
            st.warning("表示可能なデータがありません。")
    
    # 月次分析
    elif view_type == "月次":
        st.subheader(f"📅 {analysis_type} - 月次推移")
        
        monthly_data = analyze_monthly_summary(analysis_df)
        if not monthly_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=monthly_data['月'],
                y=monthly_data['平日1日平均件数'],
                mode='lines+markers',
                name=f'{analysis_type} 月次推移',
                line=dict(width=3)
            ))
            fig.update_layout(
                title=f"{analysis_type} 月次推移",
                xaxis_title="月",
                yaxis_title="平日1日平均件数",
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("月次統計詳細"):
                st.dataframe(monthly_data, use_container_width=True)
    
    # 四半期分析
    elif view_type == "四半期":
        st.subheader(f"🗓️ {analysis_type} - 四半期推移")
        
        from monthly_quarterly_analyzer import analyze_quarterly_summary
        quarterly_data = analyze_quarterly_summary(analysis_df)
        if not quarterly_data.empty:
            fig = px.bar(
                quarterly_data,
                x='四半期ラベル',
                y='平日1日平均件数',
                title=f"{analysis_type} 四半期推移"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("四半期統計詳細"):
                st.dataframe(quarterly_data, use_container_width=True)
    
    # 診療科別分析
    st.markdown("---")
    st.subheader(f"🏛️ 診療科別 {analysis_type} 内訳")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 診療科別件数
        dept_counts = analysis_df.groupby('実施診療科').size().sort_values(ascending=False).head(10)
        
        fig_dept = px.bar(
            x=dept_counts.values,
            y=dept_counts.index,
            orientation='h',
            title=f"診療科別{analysis_type}件数 (Top 10)"
        )
        fig_dept.update_layout(height=400)
        st.plotly_chart(fig_dept, use_container_width=True)
    
    with col2:
        # 時間分析
        if not analysis_df.empty:
            analysis_df_copy = analysis_df.copy()
            analysis_df_copy['曜日'] = analysis_df_copy['手術実施日_dt'].dt.day_name()
            weekday_dist = analysis_df_copy.groupby('曜日').size()
            
            fig_week = px.pie(
                values=weekday_dist.values,
                names=weekday_dist.index,
                title=f"曜日別{analysis_type}分布"
            )
            fig_week.update_layout(height=400)
            st.plotly_chart(fig_week, use_container_width=True)
            
def render_hospital_analysis_complete_weeks():
    """病院全体分析画面（完全週データ対応版）"""
    st.header("🏥 病院全体分析（完全週データ）")
    
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("データをアップロードしてください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    # データ状況を明確に表示
    analysis_end_sunday = get_latest_complete_sunday(latest_date)
    cutoff_explanation = get_data_cutoff_explanation(latest_date, analysis_end_sunday)
    
    # データ概要表示
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 総レコード数", f"{len(df_gas):,}件")
    with col2:
        st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d'))
    with col3:
        st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d'))
    with col4:
        excluded_days = (latest_date - analysis_end_sunday).days
        st.metric("⚠️ 除外日数", f"{excluded_days}日")
    
    if excluded_days > 0:
        st.info(f"💡 **分析精度向上**: {cutoff_explanation}")
    else:
        st.success(f"✅ **最新週まで分析可能**: {cutoff_explanation}")
    
    # 診療科別パフォーマンスダッシュボード（完全週データ対応）
    st.markdown("---")
    create_department_dashboard_weekly_complete(df_gas, target_dict, latest_date)
    
    st.markdown("---")
    
    # 分析設定
    col1, col2, col3 = st.columns(3)
    
    with col1:
        analysis_type = st.radio("📊 分析対象", ["全身麻酔手術", "全手術"], horizontal=True, key="hospital_analysis_type")
    
    with col2:
        period_filter = st.selectbox("📅 分析期間", 
                                   get_week_period_options(),
                                   index=2, key="hospital_period_filter")  # 直近12週をデフォルト
    
    with col3:
        view_type = st.selectbox("📊 表示形式", 
                               ["週次", "月次", "四半期"],
                               index=0, key="hospital_view_type")
    
    # データフィルタリング（完全週データ）
    filtered_df = filter_data_by_complete_weeks(df_gas, period_filter, latest_date)
    
    # 分析対象に応じてデータを絞り込み
    if analysis_type == "全身麻酔手術":
        analysis_df = filtered_df[
            filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
            filtered_df['麻酔種別'].str.contains("20分以上", na=False)
        ]
    else:
        analysis_df = filtered_df
    
    # 期間情報表示
    if not analysis_df.empty:
        start_date = analysis_df['手術実施日_dt'].min()
        end_date = analysis_df['手術実施日_dt'].max()
        total_weeks = int((end_date - start_date).days / 7) + 1
        
        period_info = format_week_period_info_complete(period_filter, start_date, end_date, total_weeks, latest_date)
        st.info(period_info)
    
    # 週次分析
    if view_type == "週次":
        st.subheader(f"📈 {analysis_type} - 週次推移（完全週データ）")
        
        summary_data = analyze_weekly_summary_complete(analysis_df, target_dict, latest_date)
        if not summary_data.empty:
            fig = plot_weekly_summary_graph_complete(summary_data, f"全科({analysis_type})", target_dict)
            st.plotly_chart(fig, use_container_width=True)
            
            # 統計情報
            with st.expander("週次統計詳細（完全週データ）"):
                st.dataframe(summary_data, use_container_width=True)
        else:
            st.warning("表示可能な完全週データがありません。")

def create_department_dashboard_weekly_complete(df_gas, target_dict, latest_date):
    """診療科パフォーマンスダッシュボード（完全週データ対応版）"""
    
    # 最新の完全な週の日曜日を取得
    analysis_end_sunday = get_latest_complete_sunday(latest_date)
    
    # 直近4週のデータを取得（完全週のみ）
    recent_4weeks_df = filter_data_by_complete_weeks(df_gas, "直近4週", latest_date)
    
    # 分析期間を表示
    if not recent_4weeks_df.empty:
        start_date = recent_4weeks_df['手術実施日_dt'].min()
        end_date = recent_4weeks_df['手術実施日_dt'].max()
        
        # 週の境界に調整
        from complete_weeks_analyzer import get_week_start_monday, get_week_end_sunday
        period_start = get_week_start_monday(start_date)
        period_end = get_week_end_sunday(end_date)
        
        st.subheader("📊 診療科別パフォーマンスダッシュボード（完全週データ分析）")
        
        # データカットオフの説明
        cutoff_explanation = get_data_cutoff_explanation(latest_date, analysis_end_sunday)
        st.caption(f"🗓️ 分析期間: {period_start.strftime('%Y/%m/%d')}〜{period_end.strftime('%Y/%m/%d')} (完全な4週間)")
        st.caption(f"💡 {cutoff_explanation}")
    
    # ターゲット診療科
    target_departments = [
        "皮膚科", "整形外科", "産婦人科", "歯科口腔外科", "耳鼻咽喉科", 
        "泌尿器科", "一般消化器外科", "呼吸器外科", "心臓血管外科", 
        "乳腺外科", "形成外科", "脳神経外科"
    ]
    
    # メトリクスの準備
    metrics_data = []
    
    for dept in target_departments:
        if dept in target_dict and dept in df_gas['実施診療科'].unique():
            # 診療科の直近4週データ
            dept_4weeks_df = recent_4weeks_df[
                (recent_4weeks_df['実施診療科'] == dept) &
                (recent_4weeks_df['麻酔種別'].str.contains("全身麻酔", na=False)) &
                (recent_4weeks_df['麻酔種別'].str.contains("20分以上", na=False))
            ]
            
            if not dept_4weeks_df.empty:
                # 週次分析
                weekly_summary = analyze_department_weekly_summary_complete(dept_4weeks_df, dept, target_dict, latest_date)
                
                if not weekly_summary.empty:
                    # 4週平均
                    avg_weekly_count = weekly_summary['週件数'].mean()
                    
                    # 目標値と達成率
                    target = target_dict.get(dept, 0)
                    achievement_rate = (avg_weekly_count / target * 100) if target > 0 else 0
                    
                    # 直近週の実績
                    latest_week_count = weekly_summary['週件数'].iloc[-1] if len(weekly_summary) > 0 else 0
                    
                    metrics_data.append({
                        "診療科": dept,
                        "4週平均": avg_weekly_count,
                        "直近週実績": latest_week_count,
                        "週間目標": target,
                        "達成率": achievement_rate,
                        "状態": "達成" if achievement_rate >= 100 else 
                               "注意" if achievement_rate >= 80 else "未達成"
                    })
    
    if not metrics_data:
        st.warning("表示可能な診療科データがありません。")
        return
    
    # データフレーム作成と降順ソート
    metrics_df = pd.DataFrame(metrics_data)
    metrics_df = metrics_df.sort_values("達成率", ascending=False)
    
    # ダッシュボード表示（3列レイアウト）
    cols = st.columns(3)
    
    for i, (_, row) in enumerate(metrics_df.iterrows()):
        col_index = i % 3
        with cols[col_index]:
            # メトリクスカードの背景色を達成状況に応じて設定
            if row["状態"] == "達成":
                card_color = "rgba(76, 175, 80, 0.1)"
                text_color = "#4CAF50"
                border_color = "#4CAF50"
            elif row["状態"] == "注意":
                card_color = "rgba(255, 152, 0, 0.1)"
                text_color = "#FF9800"
                border_color = "#FF9800"
            else:
                card_color = "rgba(244, 67, 54, 0.1)"
                text_color = "#F44336"
                border_color = "#F44336"
            
            # カスタムHTMLを使用してメトリクスカードを作成
            html = f"""
            <div style="background-color: {card_color}; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; border-left: 4px solid {border_color};">
                <h4 style="margin-top: 0; color: {text_color}; font-size: 1.1rem;">{row["診療科"]}</h4>
                <div style="margin-bottom: 0.5rem;">
                    <span style="font-size: 0.9rem; color: #666;">4週平均:</span>
                    <span style="font-weight: bold; font-size: 1.1rem; color: #333;">{row["4週平均"]:.1f} 件/週</span>
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span style="font-size: 0.9rem; color: #666;">直近週:</span>
                    <span style="font-size: 1rem; color: #333;">{row["直近週実績"]:.0f} 件</span>
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span style="font-size: 0.9rem; color: #666;">目標:</span>
                    <span style="font-size: 1rem; color: #333;">{row["週間目標"]} 件/週</span>
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span style="font-size: 0.9rem; color: #666;">達成率:</span>
                    <span style="font-weight: bold; color: {text_color}; font-size: 1.1rem;">{row["達成率"]:.1f}%</span>
                </div>
                <div style="background-color: #e0e0e0; height: 6px; border-radius: 3px; margin-top: 0.5rem;">
                    <div style="background-color: {border_color}; width: {min(row["達成率"], 100)}%; height: 100%; border-radius: 3px;"></div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
    
    # 詳細テーブルを折りたたみセクションで表示
    with st.expander("詳細データテーブル（完全週データ）", expanded=False):
        st.dataframe(
            metrics_df.style
                .format({"4週平均": "{:.1f}", "達成率": "{:.1f}%", "直近週実績": "{:.0f}"})
                .apply(lambda x: [
                    f"background-color: rgba(76, 175, 80, 0.2)" if x["達成率"] >= 100 else
                    f"background-color: rgba(255, 152, 0, 0.2)" if x["達成率"] >= 80 else
                    f"background-color: rgba(244, 67, 54, 0.2)"
                    for _ in range(len(x))
                ], axis=1),
            hide_index=True,
            use_container_width=True
        )

def render_department_analysis_complete_weeks():
    """診療科別分析画面（完全週データ対応版）"""
    st.header("🩺 診療科別分析（完全週データ）")
    
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("データをアップロードしてください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    # 診療科選択
    departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
    selected_dept = st.selectbox("🏥 診療科選択", departments, key="dept_analysis_select")
    
    # データフィルタリング
    dept_data = df_gas[df_gas["実施診療科"] == selected_dept]
    
    if dept_data.empty:
        st.warning(f"選択された診療科「{selected_dept}」のデータが見つかりません。")
        return
    
    # 完全週データ分析の設定
    try:
        # 最新の完全な週の日曜日を取得
        analysis_end_sunday = get_latest_complete_sunday(latest_date)
        cutoff_explanation = get_data_cutoff_explanation(latest_date, analysis_end_sunday)
        excluded_days = (latest_date - analysis_end_sunday).days
        
        # 完全週データでフィルタリング
        complete_weeks_dept_data = dept_data[dept_data['手術実施日_dt'] <= analysis_end_sunday]
        
        COMPLETE_WEEKS_AVAILABLE = True
    except Exception as e:
        st.warning(f"完全週データ分析機能に問題があります: {e}")
        st.info("従来の分析方法を使用します。")
        complete_weeks_dept_data = dept_data
        analysis_end_sunday = latest_date
        excluded_days = 0
        COMPLETE_WEEKS_AVAILABLE = False
    
    # データ状況の表示
    st.markdown("### 📅 データ状況")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏥 診療科", selected_dept)
    with col2:
        st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d (%a)'))
    with col3:
        st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d (%a)'))
    with col4:
        st.metric("⚠️ 除外日数", f"{excluded_days}日")
    
    # データカットオフの説明
    if excluded_days > 0:
        st.info(f"💡 **完全週データ分析**: {cutoff_explanation}")
    else:
        st.success(f"✅ **最新週まで分析可能**: {cutoff_explanation}")
    
    # KPI計算（完全週データ対応）
    if COMPLETE_WEEKS_AVAILABLE:
        try:
            kpi_data = calculate_kpi_weekly_complete(complete_weeks_dept_data, latest_date)
            
            # 完全週データでのKPI計算
            total_cases = len(complete_weeks_dept_data)
            gas_cases = len(complete_weeks_dept_data[
                complete_weeks_dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
                complete_weeks_dept_data['麻酔種別'].str.contains("20分以上", na=False)
            ])
            
            # 週平均計算
            total_weeks = int((analysis_end_sunday - complete_weeks_dept_data['手術実施日_dt'].min()).days / 7) + 1
            weekly_avg_gas = gas_cases / total_weeks if total_weeks > 0 else 0
            
            # 目標達成率計算
            target_value = target_dict.get(selected_dept, 0) if target_dict else 0
            achievement_rate = (weekly_avg_gas / target_value * 100) if target_value > 0 else 0
            
            # 最新完全週の実績
            latest_week_weekday = kpi_data.get('latest_week_weekday', 0)
            latest_week_total = kpi_data.get('latest_week_total', 0)
            prev_week_weekday = kpi_data.get('prev_week_weekday', 0)
            weekday_change = kpi_data.get('weekday_change', 0)
            
        except Exception as e:
            st.error(f"KPI計算でエラーが発生しました: {e}")
            # フォールバック計算
            total_cases = len(dept_data)
            gas_cases = len(dept_data[
                dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
                dept_data['麻酔種別'].str.contains("20分以上", na=False)
            ])
            weekly_avg_gas = gas_cases / 4  # 仮の週平均
            target_value = target_dict.get(selected_dept, 0)
            achievement_rate = (weekly_avg_gas / target_value * 100) if target_value > 0 else 0
            latest_week_weekday = 0
            latest_week_total = 0
            weekday_change = 0
    else:
        # 従来の計算方法
        total_cases = len(dept_data)
        gas_cases = len(dept_data[
            dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
            dept_data['麻酔種別'].str.contains("20分以上", na=False)
        ])
        
        # 平日データを抽出
        weekday_dept_data = dept_data[dept_data['手術実施日_dt'].dt.dayofweek < 5]
        gas_weekday_data = weekday_dept_data[
            weekday_dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
            weekday_dept_data['麻酔種別'].str.contains("20分以上", na=False)
        ]
        
        # 平日1日平均全身麻酔手術件数
        weekday_count = weekday_dept_data['手術実施日_dt'].nunique()
        daily_avg_gas = len(gas_weekday_data) / weekday_count if weekday_count > 0 else 0
        
        # 週次全身麻酔手術件数を計算
        weeks_count = (dept_data['手術実施日_dt'].max() - dept_data['手術実施日_dt'].min()).days / 7
        weekly_avg_gas = gas_cases / weeks_count if weeks_count > 0 else 0
        
        target_value = target_dict.get(selected_dept, 0) if target_dict else 0
        achievement_rate = (weekly_avg_gas / target_value * 100) if target_value > 0 else 0
        latest_week_weekday = daily_avg_gas * 5  # 仮の週次換算
        latest_week_total = total_cases
        weekday_change = 0
    
    # KPIカード表示（完全週データ対応）
    st.markdown(f"### 📊 {selected_dept} の主要指標")
    if COMPLETE_WEEKS_AVAILABLE and kpi_data:
        latest_week_start = kpi_data.get('latest_week_start', latest_date)
        latest_week_end = kpi_data.get('latest_week_end', latest_date)
        week_label = f"{latest_week_start.strftime('%m/%d')}～{latest_week_end.strftime('%m/%d')}"
        st.caption(f"📅 最新完全週: {week_label}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if COMPLETE_WEEKS_AVAILABLE:
            st.markdown(create_kpi_card(
                "最新完全週実績",
                f"{latest_week_weekday}件",
                weekday_change
            ), unsafe_allow_html=True)
        else:
            st.markdown(create_kpi_card(
                "総手術件数",
                f"{total_cases:,}件",
                2.5
            ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_kpi_card(
            "全身麻酔手術総数",
            f"{gas_cases:,}件",
            1.8
        ), unsafe_allow_html=True)
    
    with col3:
        if COMPLETE_WEEKS_AVAILABLE:
            st.markdown(create_kpi_card(
                "週平均全身麻酔",
                f"{weekly_avg_gas:.1f}件/週",
                3.2
            ), unsafe_allow_html=True)
        else:
            st.markdown(create_kpi_card(
                "平日1日平均全身麻酔",
                f"{daily_avg_gas:.1f}件/日",
                3.2
            ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_kpi_card(
            "目標達成率",
            f"{achievement_rate:.1f}%",
            achievement_rate - 100 if target_value > 0 else None
        ), unsafe_allow_html=True)
    
    # トレンド分析
    st.markdown("### 📈 トレンド分析（完全週データ）")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        view_type = st.radio("表示形式", ["週次", "月次"], horizontal=True, key="dept_view_type")
    
    with col2:
        analysis_period = st.selectbox(
            "分析期間", 
            get_week_period_options() if COMPLETE_WEEKS_AVAILABLE else ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
            index=2,  # 直近12週をデフォルト
            key="dept_analysis_period"
        )
    
    if view_type == "週次":
        if COMPLETE_WEEKS_AVAILABLE:
            try:
                # 完全週データでの分析期間フィルタリング
                period_filtered_data = filter_data_by_complete_weeks(dept_data, analysis_period, latest_date)
                summary_data = analyze_department_weekly_summary_complete(
                    period_filtered_data, selected_dept, target_dict, latest_date
                )
                
                if not summary_data.empty:
                    fig = plot_weekly_department_graph_complete(summary_data, selected_dept, target_dict)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 期間情報表示
                    start_date = period_filtered_data['手術実施日_dt'].min()
                    end_date = period_filtered_data['手術実施日_dt'].max()
                    total_weeks = len(summary_data)
                    
                    period_info = format_week_period_info_complete(
                        analysis_period, start_date, end_date, total_weeks, latest_date
                    )
                    st.info(period_info)
                else:
                    st.warning("選択した期間に完全週データがありません。")
            except Exception as e:
                st.error(f"週次分析でエラーが発生しました: {e}")
        else:
            # 従来の週次分析
            summary_data = analyze_department_summary(dept_data, selected_dept)
            if not summary_data.empty:
                fig = plot_department_graph(summary_data, selected_dept, target_dict, 4)
                st.plotly_chart(fig, use_container_width=True)
    else:
        # 月次分析は従来通り
        st.info("月次分析は従来の日次データベースで表示されます。")
    
    # 詳細分析
    st.markdown("### 🔍 詳細分析")
    
    tab1, tab2, tab3, tab4 = st.tabs(["👨‍⚕️ 術者分析", "📅 時間分析", "📊 統計情報", "📈 累積実績"])
    
    with tab1:
        st.subheader(f"{selected_dept} 術者別分析 (Top 10)")
        
        # 完全週データまたは全データを使用
        analysis_data = complete_weeks_dept_data if COMPLETE_WEEKS_AVAILABLE else dept_data
        
        # 強化された術者分析を使用（改行コード対応）
        surgeon_summary = analyze_surgeon_data_enhanced(analysis_data, selected_dept)
        
        if not surgeon_summary.empty:
            # 棒グラフ
            fig_surgeon = px.bar(
                x=surgeon_summary.values,
                y=surgeon_summary.index,
                orientation='h',
                title=f"{selected_dept} 術者別件数 (Top 10) - 完全週データ対応",
                text=surgeon_summary.values
            )
            fig_surgeon.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig_surgeon.update_layout(height=500, showlegend=False)
            fig_surgeon.update_xaxes(title="手術件数")
            fig_surgeon.update_yaxes(title="術者", categoryorder='total ascending')
            st.plotly_chart(fig_surgeon, use_container_width=True)
            
            # 詳細テーブル
            surgeon_df = pd.DataFrame({
                '順位': range(1, len(surgeon_summary) + 1),
                '術者': surgeon_summary.index,
                '件数': surgeon_summary.values,
                '割合(%)': (surgeon_summary.values / surgeon_summary.sum() * 100).round(1)
            })
            
            st.markdown("#### 📋 術者別詳細データ")
            st.dataframe(
                surgeon_df.style.format({
                    '件数': '{:.1f}',
                    '割合(%)': '{:.1f}%'
                }).apply(lambda x: [
                    'background-color: rgba(76, 175, 80, 0.2)' if x['順位'] <= 3 else
                    'background-color: rgba(192, 192, 192, 0.2)' if x['順位'] <= 5 else
                    'background-color: rgba(31, 119, 180, 0.1)' if x['順位'] % 2 == 0 else ''
                    for _ in range(len(x))
                ], axis=1),
                use_container_width=True,
                hide_index=True
            )
            
            # 統計情報
            st.markdown("#### 📈 術者統計サマリー")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("総術者数", len(surgeon_summary))
            with col2:
                st.metric("平均件数/術者", f"{surgeon_summary.mean():.1f}")
            with col3:
                st.metric("最多術者件数", f"{surgeon_summary.iloc[0]:.1f}")
                
        else:
            st.info("術者情報が利用できません。")
    
    with tab2:
        # 時間分析
        col1, col2 = st.columns(2)
        
        analysis_data = complete_weeks_dept_data if COMPLETE_WEEKS_AVAILABLE else dept_data
        
        with col1:
            # 曜日別分布
            analysis_data_copy = analysis_data.copy()
            analysis_data_copy['曜日'] = analysis_data_copy['手術実施日_dt'].dt.day_name()
            weekday_dist = analysis_data_copy.groupby('曜日').size()
            
            fig_week = px.pie(
                values=weekday_dist.values,
                names=weekday_dist.index,
                title="曜日別手術分布"
            )
            fig_week.update_layout(height=400)
            st.plotly_chart(fig_week, use_container_width=True)
        
        with col2:
            # 月別分析
            analysis_data_copy['月'] = analysis_data_copy['手術実施日_dt'].dt.month
            monthly_dist = analysis_data_copy.groupby('月').size()
            
            fig_month = px.bar(
                x=monthly_dist.index,
                y=monthly_dist.values,
                title="月別手術件数"
            )
            fig_month.update_layout(height=400)
            st.plotly_chart(fig_month, use_container_width=True)
    
    with tab3:
        # 統計情報
        col1, col2 = st.columns(2)
        
        analysis_data = complete_weeks_dept_data if COMPLETE_WEEKS_AVAILABLE else dept_data
        
        with col1:
            st.write("📊 基本統計")
            st.write(f"**データ期間**: {analysis_data['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {analysis_data['手術実施日_dt'].max().strftime('%Y/%m/%d')}")
            st.write(f"**総手術日数**: {analysis_data['手術実施日_dt'].nunique()}日")
            st.write(f"**総手術件数**: {len(analysis_data)}件")
            st.write(f"**1日最大件数**: {analysis_data.groupby('手術実施日_dt').size().max()}件")
            st.write(f"**1日平均件数**: {analysis_data.groupby('手術実施日_dt').size().mean():.1f}件")
            
            if COMPLETE_WEEKS_AVAILABLE:
                total_weeks = int((analysis_end_sunday - analysis_data['手術実施日_dt'].min()).days / 7) + 1
                st.write(f"**分析週数**: {total_weeks}週")
                st.write(f"**週平均件数**: {len(analysis_data) / total_weeks:.1f}件")
        
        with col2:
            st.write("🎯 目標関連")
            if target_value > 0:
                st.write(f"**週間目標**: {target_value}件")
                st.write(f"**現在週平均**: {weekly_avg_gas:.1f}件")
                gap = weekly_avg_gas - target_value
                if gap >= 0:
                    st.success(f"**目標との差**: +{gap:.1f}件 (達成)")
                else:
                    st.warning(f"**目標との差**: {gap:.1f}件 (未達)")
            else:
                st.info("この診療科の目標は設定されていません。")
            
            # 完全週データ分析の詳細
            if COMPLETE_WEEKS_AVAILABLE:
                st.write("🔍 完全週データ分析")
                st.write(f"**分析方式**: 完全週データのみ使用")
                st.write(f"**除外日数**: {excluded_days}日")
                st.write(f"**分析終了**: {analysis_end_sunday.strftime('%Y/%m/%d (%a)')}")
    
    with tab4:
        # 累積実績 vs 目標 推移（完全週対応）
        st.subheader(f"📊 {selected_dept}：累積実績 vs 目標 推移 (今年度週次)")
        
        current_year = latest_date.year
        fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
        cum_start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')
        cum_end_date = analysis_end_sunday if COMPLETE_WEEKS_AVAILABLE else latest_date
        
        st.caption(f"集計期間: {cum_start_date.strftime('%Y/%m/%d')} ～ {cum_end_date.strftime('%Y/%m/%d')}")
        
        current_weekly_target = target_dict.get(selected_dept, 0) if target_dict else 0
        
        if current_weekly_target <= 0:
            st.warning(f"{selected_dept} の週次目標値が0または未設定のため、目標ラインは表示されません。")
        
        if cum_start_date <= cum_end_date:
            # フィルタリング条件
            df_dept_period_for_cum = df_gas[
                (df_gas["実施診療科"] == selected_dept) &
                (df_gas["手術実施日_dt"] >= cum_start_date) &
                (df_gas["手術実施日_dt"] <= cum_end_date)
            ].copy()
            
            if not df_dept_period_for_cum.empty:
                if COMPLETE_WEEKS_AVAILABLE:
                    try:
                        # 完全週データ対応の累積分析
                        cumulative_data = calculate_cumulative_cases_complete_weeks(
                            df_dept_period_for_cum, selected_dept, current_weekly_target, latest_date
                        )
                        
                        if not cumulative_data.empty:
                            fig_cumulative = plot_cumulative_cases_complete_weeks(cumulative_data, selected_dept)
                            st.plotly_chart(fig_cumulative, use_container_width=True)
                            
                            with st.expander("累積データテーブル (今年度週次・完全週データ)"):
                                display_cols_cum = ['週','週次実績','累積実績件数', '累積目標件数', '達成率']
                                valid_display_cols = [col for col in display_cols_cum if col in cumulative_data.columns]
                                if valid_display_cols:
                                    st.dataframe(cumulative_data[valid_display_cols], use_container_width=True)
                        else:
                            st.info(f"今年度の {selected_dept} の完全週累積データがありません。")
                    except Exception as e:
                        st.error(f"完全週累積分析でエラーが発生しました: {e}")
                        st.info("従来の累積分析を表示します。")
                        # フォールバック: 従来の累積分析
                        cumulative_data = calculate_cumulative_cases(df_dept_period_for_cum, selected_dept, current_weekly_target)
                        if not cumulative_data.empty:
                            fig_cumulative = plot_cumulative_cases(cumulative_data, selected_dept)
                            st.plotly_chart(fig_cumulative, use_container_width=True)
                else:
                    # 従来の累積分析
                    cumulative_data = calculate_cumulative_cases(df_dept_period_for_cum, selected_dept, current_weekly_target)
                    
                    if not cumulative_data.empty:
                        fig_cumulative = plot_cumulative_cases(cumulative_data, selected_dept)
                        st.plotly_chart(fig_cumulative, use_container_width=True)
                        
                        with st.expander("累積データテーブル (今年度週次)"):
                            display_cols_cum = ['週','週次実績','累積実績件数', '累積目標件数']
                            valid_display_cols = [col for col in display_cols_cum if col in cumulative_data.columns]
                            if valid_display_cols:
                                st.dataframe(cumulative_data[valid_display_cols], use_container_width=True)
                    else:
                        st.info(f"今年度の {selected_dept} の累積データがありません。")
            else:
                st.info(f"今年度に {selected_dept} のデータがありません。")

def render_department_analysis():
    """診療科別分析画面 - 統合版（完全週データ機能の有無で分岐）"""
    if not MODULES_LOADED:
        st.error("必要なモジュールが読み込まれていません。")
        return
    
    # 完全週データ機能が利用可能な場合
    if COMPLETE_WEEKS_LOADED:
        render_department_analysis_complete_weeks()
    else:
        # 従来版にフォールバック
        render_department_analysis_legacy()

def render_department_analysis_legacy():
    """診療科別分析画面（従来版）"""
    st.header("🩺 診療科別分析")
    
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("データをアップロードしてください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    # 診療科選択
    departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
    selected_dept = st.selectbox("🏥 診療科選択", departments, key="dept_analysis_select")
    
    # データフィルタリング
    dept_data = df_gas[df_gas["実施診療科"] == selected_dept]
    
    if dept_data.empty:
        st.warning(f"選択された診療科「{selected_dept}」のデータが見つかりません。")
        return
    
    # KPI計算（従来版）
    # 1. 総手術件数
    total_cases = len(dept_data)
    
    # 2. 全身麻酔手術件数
    gas_cases = len(dept_data[
        dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
        dept_data['麻酔種別'].str.contains("20分以上", na=False)
    ])
    
    # 3. 平日データを抽出
    weekday_dept_data = dept_data[dept_data['手術実施日_dt'].dt.dayofweek < 5]
    gas_weekday_data = weekday_dept_data[
        weekday_dept_data['麻酔種別'].str.contains("全身麻酔", na=False) &
        weekday_dept_data['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 平日1日平均全身麻酔手術件数
    weekday_count = weekday_dept_data['手術実施日_dt'].nunique()
    daily_avg_gas = len(gas_weekday_data) / weekday_count if weekday_count > 0 else 0
    
    # 4. 目標達成率計算
    # 週次全身麻酔手術件数を計算
    weeks_count = (dept_data['手術実施日_dt'].max() - dept_data['手術実施日_dt'].min()).days / 7
    weekly_avg_gas = gas_cases / weeks_count if weeks_count > 0 else 0
    
    target_value = target_dict.get(selected_dept, 0) if target_dict else 0
    achievement_rate = (weekly_avg_gas / target_value * 100) if target_value > 0 else 0
    
    # KPIカード表示
    st.markdown(f"### 📊 {selected_dept} の主要指標")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_kpi_card(
            "総手術件数",
            f"{total_cases:,}",
            2.5
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_kpi_card(
            "全身麻酔手術件数",
            f"{gas_cases:,}",
            1.8
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_kpi_card(
            "平日1日平均全身麻酔",
            f"{daily_avg_gas:.1f}",
            3.2
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_kpi_card(
            "目標達成率",
            f"{achievement_rate:.1f}%",
            achievement_rate - 100 if target_value > 0 else None
        ), unsafe_allow_html=True)
    
    # トレンド分析
    st.markdown("### 📈 トレンド分析")
    
    view_type = st.radio("表示形式", ["週次", "月次"], horizontal=True, key="dept_view_type")
    
    if view_type == "週次":
        summary_data = analyze_department_summary(dept_data, selected_dept)
        if not summary_data.empty:
            fig = plot_department_graph(summary_data, selected_dept, target_dict, 4)
            st.plotly_chart(fig, use_container_width=True)
    
    # 詳細分析
    st.markdown("### 🔍 詳細分析")
    
    tab1, tab2, tab3, tab4 = st.tabs(["👨‍⚕️ 術者分析", "📅 時間分析", "📊 統計情報", "📈 累積実績"])
    
    with tab1:
        st.subheader(f"{selected_dept} 術者別分析 (Top 10)")
        
        # 強化された術者分析を使用（改行コード対応）
        surgeon_summary = analyze_surgeon_data_enhanced(dept_data, selected_dept)
        
        if not surgeon_summary.empty:
            # 棒グラフ
            fig_surgeon = px.bar(
                x=surgeon_summary.values,
                y=surgeon_summary.index,
                orientation='h',
                title=f"{selected_dept} 術者別件数 (Top 10) - 改行コード対応",
                text=surgeon_summary.values
            )
            fig_surgeon.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig_surgeon.update_layout(height=500, showlegend=False)
            fig_surgeon.update_xaxes(title="手術件数")
            fig_surgeon.update_yaxes(title="術者", categoryorder='total ascending')
            st.plotly_chart(fig_surgeon, use_container_width=True)
            
            # 詳細テーブル
            surgeon_df = pd.DataFrame({
                '順位': range(1, len(surgeon_summary) + 1),
                '術者': surgeon_summary.index,
                '件数': surgeon_summary.values,
                '割合(%)': (surgeon_summary.values / surgeon_summary.sum() * 100).round(1)
            })
            
            st.markdown("#### 📋 術者別詳細データ")
            st.dataframe(
                surgeon_df.style.format({
                    '件数': '{:.1f}',
                    '割合(%)': '{:.1f}%'
                }).apply(lambda x: [
                    'background-color: rgba(31, 119, 180, 0.1)' if i % 2 == 0 else ''
                    for i in range(len(x))
                ], axis=1),
                use_container_width=True,
                hide_index=True
            )
            
            # 統計情報
            st.markdown("#### 📈 術者統計サマリー")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("総術者数", len(surgeon_summary))
            with col2:
                st.metric("平均件数/術者", f"{surgeon_summary.mean():.1f}")
            with col3:
                st.metric("最多術者件数", f"{surgeon_summary.iloc[0]:.1f}")
                
        else:
            st.info("術者情報が利用できません。")
    
    with tab2:
        # 時間分析
        col1, col2 = st.columns(2)
        
        with col1:
            # 曜日別分布
            dept_data_copy = dept_data.copy()
            dept_data_copy['曜日'] = dept_data_copy['手術実施日_dt'].dt.day_name()
            weekday_dist = dept_data_copy.groupby('曜日').size()
            
            fig_week = px.pie(
                values=weekday_dist.values,
                names=weekday_dist.index,
                title="曜日別手術分布"
            )
            fig_week.update_layout(height=400)
            st.plotly_chart(fig_week, use_container_width=True)
        
        with col2:
            # 月別分析
            dept_data_copy['月'] = dept_data_copy['手術実施日_dt'].dt.month
            monthly_dist = dept_data_copy.groupby('月').size()
            
            fig_month = px.bar(
                x=monthly_dist.index,
                y=monthly_dist.values,
                title="月別手術件数"
            )
            fig_month.update_layout(height=400)
            st.plotly_chart(fig_month, use_container_width=True)
    
    with tab3:
        # 統計情報
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("📊 基本統計")
            st.write(f"**データ期間**: {dept_data['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {dept_data['手術実施日_dt'].max().strftime('%Y/%m/%d')}")
            st.write(f"**総手術日数**: {dept_data['手術実施日_dt'].nunique()}日")
            st.write(f"**総手術件数**: {len(dept_data)}件")
            st.write(f"**1日最大件数**: {dept_data.groupby('手術実施日_dt').size().max()}件")
            st.write(f"**1日平均件数**: {dept_data.groupby('手術実施日_dt').size().mean():.1f}件")
        
        with col2:
            st.write("🎯 目標関連")
            if target_value > 0:
                st.write(f"**週間目標**: {target_value}件")
                st.write(f"**現在週平均**: {weekly_avg_gas:.1f}件")
                gap = weekly_avg_gas - target_value
                if gap >= 0:
                    st.success(f"**目標との差**: +{gap:.1f}件 (達成)")
                else:
                    st.warning(f"**目標との差**: {gap:.1f}件 (未達)")
            else:
                st.info("この診療科の目標は設定されていません。")
    
    with tab4:
        # 累積実績 vs 目標 推移 (今年度週次)
        st.subheader(f"📊 {selected_dept}：累積実績 vs 目標 推移 (今年度週次)")
        
        current_year = latest_date.year
        fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
        cum_start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')
        cum_end_date = latest_date
        
        st.caption(f"集計期間: {cum_start_date.strftime('%Y/%m/%d')} ～ {cum_end_date.strftime('%Y/%m/%d')}")
        
        current_weekly_target = target_dict.get(selected_dept, 0) if target_dict else 0
        
        if current_weekly_target <= 0:
            st.warning(f"{selected_dept} の週次目標値が0または未設定のため、目標ラインは表示されません。")
        
        if cum_start_date <= cum_end_date:
            # フィルタリング条件
            df_dept_period_for_cum = df_gas[
                (df_gas["実施診療科"] == selected_dept) &
                (df_gas["手術実施日_dt"] >= cum_start_date) &
                (df_gas["手術実施日_dt"] <= cum_end_date)
            ].copy()
            
            if not df_dept_period_for_cum.empty:
                cumulative_data = calculate_cumulative_cases(df_dept_period_for_cum, selected_dept, current_weekly_target)
                
                if not cumulative_data.empty:
                    fig_cumulative = plot_cumulative_cases(cumulative_data, selected_dept)
                    st.plotly_chart(fig_cumulative, use_container_width=True)
                    
                    with st.expander("累積データテーブル (今年度週次)"):
                        display_cols_cum = ['週','週次実績','累積実績件数', '累積目標件数']
                        valid_display_cols = [col for col in display_cols_cum if col in cumulative_data.columns]
                        if valid_display_cols:
                            st.dataframe(cumulative_data[valid_display_cols], use_container_width=True)
                else:
                    st.info(f"今年度の {selected_dept} の累積データがありません。")
            else:
                st.info(f"今年度に {selected_dept} のデータがありません。")

def render_sidebar():
    """サイドバーを描画"""
    with st.sidebar:
        st.title("🏥 手術分析")
        st.markdown("---")
        
        # ナビゲーションメニュー
        current_view = st.radio(
            "📍 ナビゲーション",
            ["🏠 ダッシュボード", "📤 データアップロード", "🏥 病院全体分析", 
             "🩺 診療科別分析", "🏆 診療科ランキング", "👨‍⚕️ 術者分析", "🔮 将来予測"],
            key="navigation"
        )
        
        # 現在のビューを更新
        view_mapping = {
            "🏠 ダッシュボード": "dashboard",
            "📤 データアップロード": "upload",
            "🏥 病院全体分析": "hospital",
            "🩺 診療科別分析": "department", 
            "🏆 診療科ランキング": "ranking",
            "👨‍⚕️ 術者分析": "surgeon",
            "🔮 将来予測": "prediction"
        }
        
        st.session_state['current_view'] = view_mapping[current_view]
        
        st.markdown("---")
        
        # データ状態表示
        if st.session_state.get('df_gas') is not None:
            df = st.session_state['df_gas']
            st.success("✅ データ読み込み済み")
            st.write(f"📊 総レコード数: {len(df):,}")
            if st.session_state.get('latest_date'):
                st.write(f"📅 最新日付: {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
        else:
            st.warning("⚠️ データ未読み込み")
        
        # 目標データ状態
        if st.session_state.get('target_dict'):
            st.success("🎯 目標データ設定済み")
            st.write(f"診療科数: {len(st.session_state['target_dict'])}")
        else:
            st.info("目標データ未設定")
        
        st.markdown("---")
        
        # アプリ情報
        st.markdown("### ℹ️ アプリ情報")
        st.write("**バージョン**: 3.0 (完全週データ対応版)")
        st.write("**最終更新**: 2024/12/19")
        st.write("**特徴**: 週途中データ除外による高精度分析")
        
        # リアルタイム時刻表示
        jst = pytz.timezone('Asia/Tokyo')
        current_time = datetime.now(jst)
        st.write(f"**現在時刻**: {current_time.strftime('%H:%M:%S')}")

def main():
    """メイン関数"""
    # セッション状態初期化
    initialize_session_state()
    
    # モジュールが読み込まれていない場合は終了
    if not MODULES_LOADED:
        st.stop()
    
    # サイドバー描画
    render_sidebar()
    
    # 現在のビューに応じてコンテンツを描画
    current_view = st.session_state.get('current_view', 'dashboard')
    
    if current_view == 'dashboard':
        render_main_dashboard()
    elif current_view == 'upload':
        render_upload_section()
    elif current_view == 'hospital':
        render_hospital_analysis()
    elif current_view == 'department':
        render_department_analysis()
    elif current_view == 'ranking':
        # 診療科ランキング機能
        st.header("🏆 診療科ランキング")
        if st.session_state.get('df_gas') is not None:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            
            if target_dict:
                # 期間選択
                period_filter = st.selectbox("📅 分析期間", 
                                           ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
                                           index=1, key="ranking_period_filter")
                
                # データフィルタリング
                filtered_df = filter_data_by_period(df_gas, period_filter)
                
                # 達成率計算とランキング表示
                achievement_rates, achievement_summary = calculate_department_achievement_rates(filtered_df, target_dict)
                
                if not achievement_rates.empty:
                    fig_rank = plot_achievement_ranking(achievement_rates, 15)
                    st.plotly_chart(fig_rank, use_container_width=True)
                    
                    st.subheader("📊 目標達成率ランキング")
                    st.dataframe(achievement_rates, use_container_width=True)
                else:
                    st.warning("ランキングデータがありません。")
            else:
                st.warning("ランキング表示には目標データが必要です。")
        else:
            st.warning("データをアップロードしてください。")
    elif current_view == 'surgeon':
        # 術者分析機能（改良版）
        st.header("👨‍⚕️ 術者分析")
        if st.session_state.get('df_gas') is not None:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            
            # 分析タイプを選択
            analysis_mode = st.radio(
                "分析モード選択",
                ["📊 改行コード対応ランキング", "🔍 従来の術者分析"],
                horizontal=True
            )
            
            if analysis_mode == "📊 改行コード対応ランキング":
                create_comprehensive_surgeon_analysis(df_gas, target_dict)
            else:
                create_surgeon_analysis(df_gas, target_dict)
        else:
            st.warning("データをアップロードしてください。")
    elif current_view == 'prediction':
        # 将来予測機能
        st.header("🔮 将来予測")
        if st.session_state.get('df_gas') is not None:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            latest_date = st.session_state.get('latest_date')
            create_prediction_tab(df_gas, target_dict, latest_date)
        else:
            st.warning("データをアップロードしてください。")

if __name__ == "__main__":
    main()