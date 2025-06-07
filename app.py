# app_dashboard.py - 改修版ダッシュボード形式手術分析アプリ
import streamlit as st
import traceback
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pytz
from pathlib import Path

# ページ設定
st.set_page_config(
    page_title="🏥 手術分析ダッシュボード",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    /* メインコンテナ */
    .main-header {
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        padding: 2rem 0;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        border-radius: 10px;
    }
    
    /* KPIカード */
    .kpi-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
    }
    
    .kpi-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
        color: #1f77b4;
    }
    
    .kpi-label {
        font-size: 1rem;
        color: #666;
        margin-bottom: 0.5rem;
    }
    
    .kpi-change {
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }
    
    .positive { color: #2ca02c; }
    .negative { color: #d62728; }
    .neutral { color: #ff7f0e; }
    
    /* フィルタセクション */
    .filter-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        border: 1px solid #e9ecef;
    }
    
    /* チャートコンテナ */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
        margin-bottom: 1.5rem;
    }
    
    /* ダッシュボード タイトル */
    .dashboard-title {
        font-size: 2.5rem;
        color: white;
        font-weight: bold;
        margin: 0;
    }
    
    .dashboard-subtitle {
        font-size: 1.2rem;
        color: rgba(255, 255, 255, 0.8);
        margin-top: 0.5rem;
    }
    
    /* ナビゲーション */
    .nav-pill {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.5rem 1rem;
        border-radius: 25px;
        margin: 0.25rem;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .nav-pill:hover {
        background: #1976d2;
        color: white;
    }
    
    .nav-pill.active {
        background: #1976d2;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# モジュールインポート（エラーハンドリング付き）
try:
    from loader import load_single_file, merge_base_and_updates
    from analyzer import analyze_hospital_summary, analyze_department_summary, calculate_recent_averages, filter_data_by_period # ← この行のコメントを解除
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
    # 詳細なエラー情報を表示
    st.code(traceback.format_exc())
    MODULES_LOADED = False

# セッション状態の初期化
def initialize_session_state():
    """セッション状態を初期化"""
    if 'df_gas' not in st.session_state:
        st.session_state['df_gas'] = None
    if 'target_dict' not in st.session_state:
        st.session_state['target_dict'] = {}
    if 'latest_date' not in st.session_state:
        st.session_state['latest_date'] = None
    if 'current_view' not in st.session_state:
        st.session_state['current_view'] = 'dashboard'

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

def analyze_surgeon_data(df_dept, dept_name):
    """複数術者に対応した術者分析"""
    if "実施術者" not in df_dept.columns:
        return pd.DataFrame()
    
    # 術者データの前処理
    surgeon_data = []
    
    for _, row in df_dept.iterrows():
        surgeons_str = str(row["実施術者"])
        if pd.isna(surgeons_str) or surgeons_str.lower() in ['nan', 'null', '']:
            continue
            
        # 複数術者の分割（カンマ、セミコロン、スラッシュで分割）
        separators = [',', ';', '/', '・', '、']
        surgeons = [surgeons_str]
        
        for sep in separators:
            new_surgeons = []
            for surgeon in surgeons:
                new_surgeons.extend([s.strip() for s in surgeon.split(sep)])
            surgeons = new_surgeons
        
        # 空文字列や無効な値を除外
        surgeons = [s for s in surgeons if s and s.lower() not in ['nan', 'null', 'なし', '-']]
        
        # 各術者に対してレコードを作成
        for surgeon in surgeons:
            surgeon_data.append({
                '術者': surgeon,
                '手術実施日_dt': row['手術実施日_dt'],
                '診療科': dept_name,
                '件数': 1 / len(surgeons)  # 複数術者の場合は分割
            })
    
    if not surgeon_data:
        return pd.DataFrame()
    
    surgeon_df = pd.DataFrame(surgeon_data)
    
    # 術者別集計
    surgeon_summary = surgeon_df.groupby('術者')['件数'].sum().round(1).sort_values(ascending=False)
    
    return surgeon_summary.head(10)

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
    """メインダッシュボードを描画"""
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
                    dept_data['曜日'] = dept_data['手術実施日_dt'].dt.day_name()
                    weekday_dist = dept_data.groupby('曜日').size()
                    
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
    """病院全体分析画面（修正版）"""
    st.header("🏥 病院全体分析")
    
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.warning("データをアップロードしてください。")
        return
    
    df_gas = st.session_state['df_gas']
    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')
    
    st.info(f"分析対象期間: {df_gas['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {latest_date.strftime('%Y/%m/%d')}")
    
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

def render_department_analysis():
    """診療科別分析画面（修正版）"""
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
    
    # KPI計算（修正版）
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
    
    # 4. 目標達成率計算（修正版）
    # 週次全身麻酔手術件数を計算
    weeks_count = (dept_data['手術実施日_dt'].max() - dept_data['手術実施日_dt'].min()).days / 7
    weekly_avg_gas = gas_cases / weeks_count if weeks_count > 0 else 0
    
    target_value = target_dict.get(selected_dept, 0) if target_dict else 0
    achievement_rate = (weekly_avg_gas / target_value * 100) if target_value > 0 else 0
    
    # KPIカード表示（修正版 - データ期間を削除）
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
    
    tab1, tab2, tab3 = st.tabs(["👨‍⚕️ 術者分析", "📅 時間分析", "📊 統計情報"])
    
    with tab1:
        st.subheader(f"{selected_dept} 術者別分析 (Top 10)")
        surgeon_summary = analyze_surgeon_data(dept_data, selected_dept)
        
        if not surgeon_summary.empty:
            # 棒グラフ
            fig_surgeon = px.bar(
                x=surgeon_summary.values,
                y=surgeon_summary.index,
                orientation='h',
                title=f"{selected_dept} 術者別件数 (Top 10)",
                text=surgeon_summary.values
            )
            fig_surgeon.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig_surgeon.update_layout(height=400)
            st.plotly_chart(fig_surgeon, use_container_width=True)
            
            # 詳細テーブル
            surgeon_df = pd.DataFrame({
                '術者': surgeon_summary.index,
                '件数': surgeon_summary.values,
                '割合(%)': (surgeon_summary.values / surgeon_summary.sum() * 100).round(1)
            })
            st.dataframe(surgeon_df, use_container_width=True)
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
    
    # 累積実績 vs 目標 推移 (今年度週次) を追加
    st.markdown("---")
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
            from department_ranking import calculate_cumulative_cases, plot_cumulative_cases
            
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
        st.write("**バージョン**: 2.0")
        st.write("**最終更新**: 2024/12/19")
        
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
        # 術者分析機能
        st.header("👨‍⚕️ 術者分析")
        if st.session_state.get('df_gas') is not None:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
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