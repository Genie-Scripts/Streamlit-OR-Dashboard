# pages/dashboard.py - 改善されたダッシュボードページ
import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# 新しいモジュールをインポート
from config.app_config import config, CUSTOM_CSS, TARGET_DEPARTMENTS
from utils.session_manager import SessionManager
from components.kpi_cards import render_kpi_dashboard, create_summary_kpis

# 既存の分析モジュールを活用
try:
    from complete_weeks_analyzer import (
        filter_data_by_complete_weeks,
        analyze_weekly_summary_complete,
        calculate_kpi_weekly_complete,
        get_latest_complete_sunday,
        get_data_cutoff_explanation,
        format_week_period_info_complete,
        get_week_period_options,
        plot_weekly_summary_graph_complete
    )
    COMPLETE_WEEKS_AVAILABLE = True
except ImportError:
    COMPLETE_WEEKS_AVAILABLE = False
    st.warning("完全週データ分析モジュールが利用できません。")

from analyzer import filter_data_by_period
from plotter import plot_summary_graph

def render_dashboard_header():
    """ダッシュボードヘッダーの描画"""
    st.markdown(f"""
    <div class="main-header">
        <h1 class="dashboard-title">{config.PAGE_TITLE}</h1>
        <p class="dashboard-subtitle">
            {'完全週データ（月曜〜日曜）による' if COMPLETE_WEEKS_AVAILABLE else ''}
            全身麻酔手術件数の包括的分析と予測
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_data_status_section():
    """データ状況セクションの描画"""
    data_info = SessionManager.get_data_info()
    target_info = SessionManager.get_target_info()
    
    if not data_info['loaded']:
        st.warning("📊 データをアップロードしてください")
        st.info("サイドバーの「データアップロード」からCSVファイルを読み込んでください。")
        return False
    
    # データ概要表示
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 総レコード数", f"{data_info['record_count']:,}件")
    
    with col2:
        if data_info['latest_date']:
            latest_date = pd.to_datetime(data_info['latest_date'])
            st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d (%A)'))
    
    with col3:
        if COMPLETE_WEEKS_AVAILABLE and data_info['latest_date']:
            latest_date = pd.to_datetime(data_info['latest_date'])
            analysis_end_sunday = get_latest_complete_sunday(latest_date)
            st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d (%A)'))
        else:
            st.metric("🏥 診療科数", data_info['department_count'])
    
    # データカットオフの説明（完全週データの場合）
    if COMPLETE_WEEKS_AVAILABLE and data_info['latest_date']:
        latest_date = pd.to_datetime(data_info['latest_date'])
        analysis_end_sunday = get_latest_complete_sunday(latest_date)
        cutoff_explanation = get_data_cutoff_explanation(latest_date, analysis_end_sunday)
        
        if latest_date.date() != analysis_end_sunday.date():
            st.info(f"💡 **分析精度向上のため完全な週のみを使用**: {cutoff_explanation}")
        else:
            st.success(f"✅ **最新データが日曜日のため現在週まで分析可能**: {cutoff_explanation}")
    
    return True

def render_filter_section():
    """フィルターセクションの描画"""
    st.markdown("### ⚙️ 分析設定")
    
    with st.container():
        st.markdown('<div class="filter-section">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            period_options = get_week_period_options() if COMPLETE_WEEKS_AVAILABLE else ["直近30日", "直近90日", "直近180日", "今年度", "全期間"]
            period_filter = st.selectbox(
                "📅 分析期間", 
                period_options,
                index=1,  # 直近4週をデフォルト
                help="完全な週（月曜〜日曜）のデータのみを使用" if COMPLETE_WEEKS_AVAILABLE else None
            )
        
        with col2:
            data_info = SessionManager.get_data_info()
            departments = ["全診療科"] + data_info['departments']
            dept_filter = st.selectbox("🏥 診療科", departments)
        
        with col3:
            view_type = st.selectbox("📊 表示形式", ["週次", "月次", "四半期"], index=0)
        
        with col4:
            auto_refresh = st.checkbox(
                "🔄 自動更新", 
                value=SessionManager.get_user_preference('auto_refresh', False)
            )
            SessionManager.set_user_preference('auto_refresh', auto_refresh)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    return period_filter, dept_filter, view_type, auto_refresh

def render_main_kpis(period_filter, dept_filter):
    """メインKPIセクションの描画"""
    df_gas = SessionManager.get('df_gas')
    
    st.markdown("### 📊 主要指標")
    
    if COMPLETE_WEEKS_AVAILABLE:
        # 完全週データでのKPI計算
        latest_date = SessionManager.get('latest_date')
        filtered_df = filter_data_by_complete_weeks(df_gas, period_filter, latest_date)
        
        if dept_filter != "全診療科":
            filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
        
        # 完全週データ用のKPI計算
        kpi_data = calculate_kpi_weekly_complete(filtered_df, latest_date)
        
        # KPIカードデータを作成
        kpi_cards = []
        
        if kpi_data:
            latest_week_start = kpi_data.get('latest_week_start', latest_date)
            latest_week_end = kpi_data.get('latest_week_end', latest_date)
            latest_week_label = f"{latest_week_start.strftime('%m/%d')}～{latest_week_end.strftime('%m/%d')}"
            
            kpi_cards = [
                {
                    'title': f'最新完全週 ({latest_week_label})',
                    'value': f"{kpi_data.get('latest_week_weekday', 0)}件",
                    'change': kpi_data.get('weekday_change', 0),
                    'icon': '📅',
                    'color': 'primary'
                },
                {
                    'title': '最新週総手術件数',
                    'value': f"{kpi_data.get('latest_week_total', 0)}件",
                    'change': kpi_data.get('total_change', 0),
                    'icon': '🏥',
                    'color': 'success'
                },
                {
                    'title': '過去4週平均',
                    'value': f"{kpi_data.get('avg_4week_weekday', 0):.1f}件/週",
                    'change': 2.3,
                    'icon': '📈',
                    'color': 'warning'
                },
                {
                    'title': '分析データ品質',
                    'value': '完全週データ',
                    'change': None,
                    'icon': '✅',
                    'color': 'success'
                }
            ]
    else:
        # 従来のKPI計算
        filtered_df = filter_data_by_period(df_gas, period_filter)
        kpi_cards = create_summary_kpis(filtered_df, period_filter, dept_filter)
    
    # KPIカードを表示
    if kpi_cards:
        render_kpi_dashboard(kpi_cards, columns=4)
    else:
        st.warning("KPIデータの計算に失敗しました。")

def render_trend_analysis(period_filter, dept_filter, view_type):
    """トレンド分析セクションの描画"""
    st.markdown("### 📈 トレンド分析")
    
    df_gas = SessionManager.get('df_gas')
    target_dict = SessionManager.get('target_dict', {})
    latest_date = SessionManager.get('latest_date')
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        
        if view_type == "週次":
            if COMPLETE_WEEKS_AVAILABLE:
                # 完全週データでのトレンド分析
                filtered_df = filter_data_by_complete_weeks(df_gas, period_filter, latest_date)
                
                if dept_filter != "全診療科":
                    filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
                
                if not filtered_df.empty:
                    if dept_filter == "全診療科":
                        summary_data = analyze_weekly_summary_complete(filtered_df, target_dict, latest_date)
                        if not summary_data.empty:
                            fig = plot_weekly_summary_graph_complete(summary_data, "全科（完全週データ）", target_dict)
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        from complete_weeks_analyzer import analyze_department_weekly_summary_complete
                        summary_data = analyze_department_weekly_summary_complete(filtered_df, dept_filter, target_dict, latest_date)
                        if not summary_data.empty:
                            from complete_weeks_analyzer import plot_weekly_department_graph_complete
                            fig = plot_weekly_department_graph_complete(summary_data, dept_filter, target_dict)
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("選択した条件に該当する完全週データがありません。")
            else:
                # 従来のトレンド分析
                filtered_df = filter_data_by_period(df_gas, period_filter)
                if dept_filter != "全診療科":
                    filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
                
                from analyzer import analyze_hospital_summary, analyze_department_summary
                
                if dept_filter == "全診療科":
                    summary_data = analyze_hospital_summary(filtered_df)
                    if not summary_data.empty:
                        fig = plot_summary_graph(summary_data, "全科", target_dict, 4)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    summary_data = analyze_department_summary(filtered_df, dept_filter)
                    if not summary_data.empty:
                        from plotter import plot_department_graph
                        fig = plot_department_graph(summary_data, dept_filter, target_dict, 4)
                        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        render_analysis_summary(dept_filter, period_filter)

def render_analysis_summary(dept_filter, period_filter):
    """分析サマリーの表示"""
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("#### 🎯 分析サマリー")
    
    data_info = SessionManager.get_data_info()
    target_info = SessionManager.get_target_info()
    
    if dept_filter == "全診療科":
        st.write("**分析対象**: 病院全体")
        if target_info['loaded']:
            st.write(f"**目標設定診療科数**: {target_info['department_count']}")
            st.write(f"**総合目標**: {target_info['total_target']}件/週")
    else:
        st.write(f"**分析対象**: {dept_filter}")
        if target_info['loaded'] and dept_filter in target_info['targets']:
            target_value = target_info['targets'][dept_filter]
            st.write(f"**週次目標**: {target_value}件")
    
    st.write(f"**分析期間**: {period_filter}")
    
    if COMPLETE_WEEKS_AVAILABLE:
        st.write("**分析方式**: 完全週データ")
        st.info("📊 月曜〜日曜の完全な週のみを使用し、週の途中で切れるデータは除外")
    else:
        st.write("**分析方式**: 従来方式")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_main_dashboard():
    """メインダッシュボード（改良版）"""
    # CSSを適用
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    # ヘッダー描画
    render_dashboard_header()
    
    # データ状況チェック
    if not render_data_status_section():
        return
    
    # フィルターセクション
    period_filter, dept_filter, view_type, auto_refresh = render_filter_section()
    
    # KPIセクション
    render_main_kpis(period_filter, dept_filter)
    
    # トレンド分析セクション
    render_trend_analysis(period_filter, dept_filter, view_type)
    
    # 詳細分析タブ（簡略化）
    st.markdown("### 📋 詳細分析")
    
    tab1, tab2, tab3 = st.tabs(["📊 統計情報", "🏆 ランキング", "📈 予測"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**データ統計**")
            data_info = SessionManager.get_data_info()
            st.write(f"期間: {data_info['date_range']['start']} ～ {data_info['date_range']['end']}")
            st.write(f"レコード数: {data_info['record_count']:,}件")
        
        with col2:
            st.write("**分析設定**")
            st.write(f"期間フィルター: {period_filter}")
            st.write(f"診療科: {dept_filter}")
            st.write(f"表示形式: {view_type}")
    
    with tab2:
        st.info("診療科別ランキングは「診療科ランキング」ページをご利用ください。")
    
    with tab3:
        st.info("詳細な予測分析は「将来予測」ページをご利用ください。")
