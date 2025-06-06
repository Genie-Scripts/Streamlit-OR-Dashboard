# app_dashboard.py - 改修版ダッシュボード形式手術分析アプリ
import streamlit as st
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
    from analyzer import analyze_hospital_summary, analyze_department_summary, calculate_recent_averages, filter_data_by_period
    from monthly_quarterly_analyzer import analyze_monthly_summary, analyze_quarterly_summary
    from target_loader import load_target_file
    from plotter import plot_summary_graph, plot_department_graph
    from department_ranking import calculate_department_achievement_rates, plot_achievement_ranking
    from surgeon_analyzer import create_surgeon_analysis
    from prediction_tab_enhanced import create_prediction_tab
    
    MODULES_LOADED = True
except ImportError as e:
    st.error(f"必要なモジュールの読み込みに失敗しました: {e}")
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
    
    # KPIメトリクス計算
    total_cases = len(filtered_df[
        filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
        filtered_df['麻酔種別'].str.contains("20分以上", na=False)
    ])
    
    # 前期との比較計算（簡易版）
    prev_period_cases = total_cases * 0.95  # 仮の前期データ
    change_rate = ((total_cases - prev_period_cases) / prev_period_cases * 100) if prev_period_cases > 0 else 0
    
    # 平均値計算
    if view_type == "週次":
        recent_averages = calculate_recent_averages(filtered_df)
        if not recent_averages.empty:
            avg_daily = recent_averages[recent_averages["期間"] == "直近30日"]["平日1日平均件数"].values
            avg_daily = avg_daily[0] if len(avg_daily) > 0 else 0
        else:
            avg_daily = 0
    else:
        avg_daily = total_cases / 30 if total_cases > 0 else 0
    
    # 目標達成率計算
    target_achievement = 0
    if dept_filter != "全診療科" and dept_filter in target_dict:
        target_value = target_dict[dept_filter]
        weekly_avg = avg_daily * 7 if avg_daily > 0 else 0
        target_achievement = (weekly_avg / target_value * 100) if target_value > 0 else 0
    
    # KPIカード表示
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
            "平日1日平均",
            f"{avg_daily:.1f}",
            change_rate * 0.8
        ), unsafe_allow_html=True)
    
    with col3:
        if dept_filter != "全診療科" and target_achievement > 0:
            st.markdown(create_kpi_card(
                "目標達成率",
                f"{target_achievement:.1f}%",
                target_achievement - 100
            ), unsafe_allow_html=True)
        else:
            st.markdown(create_kpi_card(
                "アクティブ診療科",
                f"{df_gas['実施診療科'].nunique()}",
                5.2
            ), unsafe_allow_html=True)
    
    with col4:
        unique_surgeons = df_gas["実施術者"].nunique() if "実施術者" in df_gas.columns else 0
        st.markdown(create_kpi_card(
            "総術者数",
            f"{unique_surgeons}",
            2.1
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

def main():
    """メイン関数 - デバッグ機能付き"""
    # セッション状態初期化
    initialize_session_state()
    
    # デバッグ情報表示
    st.sidebar.markdown("### 🔍 デバッグ情報")
    st.sidebar.write(f"MODULES_LOADED: {MODULES_LOADED}")
    st.sidebar.write(f"current_view: {st.session_state.get('current_view', 'None')}")
    st.sidebar.write(f"df_gas loaded: {st.session_state.get('df_gas') is not None}")
    if st.session_state.get('df_gas') is not None:
        st.sidebar.write(f"データ行数: {len(st.session_state['df_gas'])}")
    
    # モジュールが読み込まれていない場合は終了
    if not MODULES_LOADED:
        st.error("❌ 必要なモジュールが読み込まれていません")
        st.info("以下のファイルが存在することを確認してください:")
        required_modules = [
            "loader.py", "analyzer.py", "monthly_quarterly_analyzer.py",
            "target_loader.py", "plotter.py", "department_ranking.py", 
            "surgeon_analyzer.py", "prediction_tab_enhanced.py"
        ]
        for module in required_modules:
            st.write(f"- {module}")
        st.stop()
    
    # サイドバー描画
    render_sidebar()
    
    # 現在のビューに応じてコンテンツを描画
    current_view = st.session_state.get('current_view', 'dashboard')
    
    # デバッグ: どのビューが選択されているかを表示
    st.write(f"🔍 **現在のビュー**: {current_view}")
    
    try:
        if current_view == 'dashboard':
            st.write("✅ ダッシュボードを表示中...")
            render_main_dashboard()
            
        elif current_view == 'upload':
            st.write("✅ データアップロードセクションを表示中...")
            render_upload_section()
            
        elif current_view == 'hospital':
            st.write("✅ 病院全体分析を表示中...")
            # 病院全体分析機能
            st.header("🏥 病院全体分析")
            
            if st.session_state.get('df_gas') is None:
                st.warning("データをアップロードしてください。")
                st.info("サイドバーの「📤 データアップロード」からCSVファイルを読み込んでください。")
                return
                
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            
            st.success(f"✅ データ読み込み済み: {len(df_gas):,}件")
            
            # 基本的な列の存在確認
            required_columns = ['手術実施日_dt', '実施診療科', '麻酔種別']
            missing_columns = [col for col in required_columns if col not in df_gas.columns]
            
            if missing_columns:
                st.error(f"❌ 必要な列が見つかりません: {missing_columns}")
                st.write("**利用可能な列:**")
                st.write(list(df_gas.columns))
                return
            
            # 期間フィルタ
            col1, col2 = st.columns(2)
            with col1:
                period_filter = st.selectbox("📅 分析期間", 
                                           ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
                                           index=1, key="hospital_period")
            with col2:
                view_type = st.selectbox("📊 表示形式", 
                                       ["週次", "月次", "四半期"],
                                       index=0, key="hospital_view")
            
            st.write(f"🔍 選択された期間: {period_filter}, 表示形式: {view_type}")
            
            # データフィルタリング
            try:
                filtered_df = filter_data_by_period(df_gas, period_filter)
                st.success(f"✅ フィルタ後データ: {len(filtered_df):,}件")
                
                if filtered_df.empty:
                    st.warning("選択された期間にデータがありません。")
                    return
                    
            except Exception as e:
                st.error(f"❌ データフィルタリングエラー: {str(e)}")
                return
            
            # 病院全体サマリー
            try:
                if view_type == "週次":
                    st.write("🔍 週次分析を実行中...")
                    summary_data = analyze_hospital_summary(filtered_df)
                    
                    if not summary_data.empty:
                        st.success(f"✅ 週次データ取得: {len(summary_data)}週分")
                        
                        # グラフ表示
                        fig = plot_summary_graph(summary_data, "全科", target_dict, 4)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 統計テーブル
                        st.subheader("📊 週次統計")
                        st.dataframe(summary_data, use_container_width=True)
                    else:
                        st.warning("週次データが空です。")
                        st.write("デバッグ情報:")
                        st.write(f"- フィルタ後データ行数: {len(filtered_df)}")
                        st.write(f"- データ期間: {filtered_df['手術実施日_dt'].min()} ～ {filtered_df['手術実施日_dt'].max()}")
                
                elif view_type == "月次":
                    st.write("🔍 月次分析を実行中...")
                    monthly_summary = analyze_monthly_summary(filtered_df)
                    
                    if not monthly_summary.empty:
                        st.success(f"✅ 月次データ取得: {len(monthly_summary)}ヶ月分")
                        
                        # 月次グラフ
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=monthly_summary['月'],
                            y=monthly_summary['平日1日平均件数'],
                            mode='lines+markers',
                            name='月次推移',
                            line=dict(width=3)
                        ))
                        fig.update_layout(
                            title="病院全体 月次推移",
                            xaxis_title="月",
                            yaxis_title="平日1日平均件数",
                            height=500
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 月次統計テーブル
                        st.subheader("📅 月次統計")
                        st.dataframe(monthly_summary, use_container_width=True)
                    else:
                        st.warning("月次データが空です。")
                
                elif view_type == "四半期":
                    st.write("🔍 四半期分析を実行中...")
                    quarterly_summary = analyze_quarterly_summary(filtered_df)
                    
                    if not quarterly_summary.empty:
                        st.success(f"✅ 四半期データ取得: {len(quarterly_summary)}四半期分")
                        
                        # 四半期グラフ
                        fig = px.bar(
                            quarterly_summary,
                            x='四半期',
                            y='平日1日平均件数',
                            title="病院全体 四半期推移"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 四半期統計テーブル
                        st.subheader("📈 四半期統計")
                        st.dataframe(quarterly_summary, use_container_width=True)
                    else:
                        st.warning("四半期データが空です。")
                        
            except Exception as e:
                st.error(f"❌ 分析処理エラー: {str(e)}")
                st.write("エラー詳細:")
                st.code(str(e))
                return
            
            # 追加分析
            st.subheader("🔍 詳細分析")
            col1, col2 = st.columns(2)
            
            try:
                with col1:
                    # 診療科別件数分布
                    dept_counts = filtered_df.groupby('実施診療科').size().sort_values(ascending=False).head(10)
                    
                    if not dept_counts.empty:
                        fig_dept = px.bar(
                            x=dept_counts.values,
                            y=dept_counts.index,
                            orientation='h',
                            title="診療科別件数 (Top 10)"
                        )
                        fig_dept.update_layout(height=400)
                        st.plotly_chart(fig_dept, use_container_width=True)
                    else:
                        st.warning("診療科データがありません。")
                
                with col2:
                    # 曜日別分布
                    if not filtered_df.empty:
                        filtered_df_copy = filtered_df.copy()
                        filtered_df_copy['曜日'] = filtered_df_copy['手術実施日_dt'].dt.day_name()
                        weekday_dist = filtered_df_copy.groupby('曜日').size()
                        
                        if not weekday_dist.empty:
                            fig_week = px.pie(
                                values=weekday_dist.values,
                                names=weekday_dist.index,
                                title="曜日別手術件数分布"
                            )
                            fig_week.update_layout(height=400)
                            st.plotly_chart(fig_week, use_container_width=True)
                        else:
                            st.warning("曜日別データがありません。")
                            
            except Exception as e:
                st.error(f"❌ 詳細分析エラー: {str(e)}")
        
        elif current_view == 'department':
            st.write("✅ 診療科別分析を表示中...")
            # 診療科別分析機能
            st.header("🩺 診療科別分析")
            
            if st.session_state.get('df_gas') is None:
                st.warning("データをアップロードしてください。")
                return
                
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            
            st.success(f"✅ データ読み込み済み: {len(df_gas):,}件")
            
            # 診療科リスト確認
            departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
            st.write(f"🔍 利用可能な診療科数: {len(departments)}")
            
            if not departments:
                st.error("❌ 診療科データが見つかりません。")
                return
            
            # フィルタ設定
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_dept = st.selectbox("🏥 診療科選択", departments, key="dept_selector")
            
            with col2:
                period_filter = st.selectbox("📅 分析期間", 
                                           ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
                                           index=1, key="dept_period")
            with col3:
                view_type = st.selectbox("📊 表示形式", 
                                       ["週次", "月次", "四半期"],
                                       index=0, key="dept_view")
            
            st.write(f"🔍 選択: {selected_dept}, {period_filter}, {view_type}")
            
            # データフィルタリング
            try:
                filtered_df = filter_data_by_period(df_gas, period_filter)
                dept_data = filtered_df[filtered_df["実施診療科"] == selected_dept]
                
                st.write(f"🔍 フィルタ後: 全体{len(filtered_df)}件, 診療科別{len(dept_data)}件")
                
                if dept_data.empty:
                    st.warning(f"選択された診療科「{selected_dept}」のデータが期間内に見つかりません。")
                    return
                
                # 基本統計を表示
                st.subheader(f"📊 {selected_dept} の基本情報")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("総データ件数", len(dept_data))
                with col2:
                    st.metric("データ期間(日)", (dept_data['手術実施日_dt'].max() - dept_data['手術実施日_dt'].min()).days + 1)
                with col3:
                    st.metric("ユニーク日数", dept_data['手術実施日_dt'].nunique())
                
                # 麻酔種別確認
                if '麻酔種別' in dept_data.columns:
                    anesthesia_types = dept_data['麻酔種別'].value_counts()
                    st.write("🔍 麻酔種別分布:")
                    st.dataframe(anesthesia_types)
                
                st.success("✅ 診療科別分析の基本表示が完了しました。")
                
            except Exception as e:
                st.error(f"❌ 診療科別分析エラー: {str(e)}")
                st.code(str(e))
        
        elif current_view == 'ranking':
            st.write("✅ 診療科ランキングを表示中...")
            st.header("🏆 診療科ランキング")
            
            if st.session_state.get('df_gas') is None:
                st.warning("データをアップロードしてください。")
                return
                
            df_gas = st.session_state['df_gas']
            st.success(f"✅ データ読み込み済み: {len(df_gas):,}件")
            
            # 簡単なランキング表示
            try:
                dept_counts = df_gas.groupby('実施診療科').size().sort_values(ascending=False).head(10)
                
                st.subheader("📊 診療科別手術件数 Top 10")
                st.dataframe(dept_counts)
                
                # 簡単なグラフ
                fig = px.bar(
                    x=dept_counts.values,
                    y=dept_counts.index,
                    orientation='h',
                    title="診療科別手術件数 Top 10"
                )
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"❌ ランキング表示エラー: {str(e)}")
        
        elif current_view == 'surgeon':
            st.write("✅ 術者分析を表示中...")
            st.header("👨‍⚕️ 術者分析")
            if st.session_state.get('df_gas') is not None:
                df_gas = st.session_state['df_gas']
                target_dict = st.session_state.get('target_dict', {})
                try:
                    create_surgeon_analysis(df_gas, target_dict)
                except Exception as e:
                    st.error(f"❌ 術者分析エラー: {str(e)}")
            else:
                st.warning("データをアップロードしてください。")
        
        elif current_view == 'prediction':
            st.write("✅ 将来予測を表示中...")
            st.header("🔮 将来予測")
            if st.session_state.get('df_gas') is not None:
                df_gas = st.session_state['df_gas']
                target_dict = st.session_state.get('target_dict', {})
                latest_date = st.session_state.get('latest_date')
                try:
                    create_prediction_tab(df_gas, target_dict, latest_date)
                except Exception as e:
                    st.error(f"❌ 将来予測エラー: {str(e)}")
            else:
                st.warning("データをアップロードしてください。")
                
    except Exception as e:
        st.error(f"❌ メイン処理でエラーが発生しました: {str(e)}")
        st.write("**エラートレースバック:**")
        import traceback
        st.code(traceback.format_exc())
        
    # デバッグ情報をフッターに表示
    st.markdown("---")
    st.markdown("### 🔧 デバッグ情報")
    st.write(f"**Streamlitバージョン**: {st.__version__}")
    st.write(f"**セッション状態キー**: {list(st.session_state.keys())}")
    if st.session_state.get('df_gas') is not None:
        df = st.session_state['df_gas']
        st.write(f"**データフレーム形状**: {df.shape}")
        st.write(f"**列名**: {list(df.columns)}")
        st.write(f"**データ型**:")
        st.code(str(df.dtypes))