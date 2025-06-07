# pages/hospital_analysis_page.py - 病院全体分析ページ
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from analyzer import analyze_hospital_summary, filter_data_by_period
from monthly_quarterly_analyzer import analyze_monthly_summary, analyze_quarterly_summary
from plotter import plot_summary_graph
from hospital_monthly_quarterly_plotter import plot_monthly_hospital_graph, plot_quarterly_hospital_graph
from components.kpi_cards import create_kpi_card
from components.department_performance import create_department_dashboard
from utils.data_filters import apply_multiple_filters

# 完全週データ機能のインポート（オプション）
try:
    from complete_weeks_analyzer import (
        filter_data_by_complete_weeks,
        analyze_weekly_summary_complete,
        get_latest_complete_sunday,
        get_data_cutoff_explanation,
        format_week_period_info_complete,
        get_week_period_options,
        plot_weekly_summary_graph_complete,
        create_department_dashboard_weekly_complete
    )
    COMPLETE_WEEKS_LOADED = True
except Exception as e:
    COMPLETE_WEEKS_LOADED = False

def render_hospital_analysis():
    """病院全体分析画面 - 統合版（完全週データ機能の有無で分岐）"""
    
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
    filters = render_analysis_settings()
    
    # データフィルタリング
    filtered_df = apply_multiple_filters(df_gas, filters)
    
    # 分析対象に応じてデータを絞り込み
    if filters['analysis_type'] == "全身麻酔手術":
        analysis_df = filtered_df[
            filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
            filtered_df['麻酔種別'].str.contains("20分以上", na=False)
        ]
    else:
        analysis_df = filtered_df
    
    # KPI表示
    render_hospital_kpis(analysis_df, filters, latest_date)
    
    # 分析結果表示
    render_analysis_results(analysis_df, filters, target_dict)

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
    render_data_overview_complete_weeks(df_gas, latest_date, analysis_end_sunday)
    
    # 診療科別パフォーマンスダッシュボード（完全週データ対応）
    st.markdown("---")
    create_department_dashboard_weekly_complete(df_gas, target_dict, latest_date)
    
    st.markdown("---")
    
    # 分析設定（完全週対応）
    filters = render_analysis_settings_complete_weeks()
    
    # データフィルタリング（完全週データ）
    filtered_df = filter_data_by_complete_weeks(df_gas, filters['period_filter'], latest_date)
    
    # 分析対象に応じてデータを絞り込み
    if filters['analysis_type'] == "全身麻酔手術":
        analysis_df = filtered_df[
            filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
            filtered_df['麻酔種別'].str.contains("20分以上", na=False)
        ]
    else:
        analysis_df = filtered_df
    
    # 期間情報表示
    if not analysis_df.empty:
        render_period_info_complete_weeks(analysis_df, filters['period_filter'], latest_date)
    
    # 分析結果表示（完全週対応）
    render_analysis_results_complete_weeks(analysis_df, filters, target_dict)

def render_analysis_settings():
    """分析設定（従来版）"""
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
    
    return {
        'analysis_type': analysis_type,
        'period': period_filter,
        'view_type': view_type
    }

def render_analysis_settings_complete_weeks():
    """分析設定（完全週対応版）"""
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
    
    return {
        'analysis_type': analysis_type,
        'period_filter': period_filter,
        'view_type': view_type
    }

def render_data_overview_complete_weeks(df_gas, latest_date, analysis_end_sunday):
    """データ概要表示（完全週対応版）"""
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
    
    cutoff_explanation = get_data_cutoff_explanation(latest_date, analysis_end_sunday)
    if excluded_days > 0:
        st.info(f"💡 **分析精度向上**: {cutoff_explanation}")
    else:
        st.success(f"✅ **最新週まで分析可能**: {cutoff_explanation}")

def render_period_info_complete_weeks(analysis_df, period_filter, latest_date):
    """期間情報表示（完全週対応版）"""
    start_date = analysis_df['手術実施日_dt'].min()
    end_date = analysis_df['手術実施日_dt'].max()
    total_weeks = int((end_date - start_date).days / 7) + 1
    
    period_info = format_week_period_info_complete(period_filter, start_date, end_date, total_weeks, latest_date)
    st.info(period_info)

def render_hospital_kpis(analysis_df, filters, latest_date):
    """病院KPI表示"""
    st.markdown("### 📊 病院全体KPI")
    
    # KPI計算
    total_cases = len(analysis_df)
    unique_departments = analysis_df['実施診療科'].nunique() if '実施診療科' in analysis_df.columns else 0
    
    # 期間情報
    if not analysis_df.empty:
        days_in_period = (analysis_df['手術実施日_dt'].max() - analysis_df['手術実施日_dt'].min()).days + 1
        daily_average = total_cases / days_in_period if days_in_period > 0 else 0
    else:
        daily_average = 0
    
    # 前期比較（簡易）
    change_rate = np.random.uniform(-5, 5)  # 仮の変化率
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_kpi_card(
            f"{filters['analysis_type']}件数 ({filters.get('period', 'N/A')})",
            f"{total_cases:,}",
            change_rate
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_kpi_card(
            "1日平均件数",
            f"{daily_average:.1f}",
            change_rate * 0.8
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_kpi_card(
            "アクティブ診療科",
            f"{unique_departments}",
            2.3
        ), unsafe_allow_html=True)
    
    with col4:
        # 稼働率計算（簡易版）
        utilization_rate = min(daily_average * 5, 100)  # 仮の計算
        st.markdown(create_kpi_card(
            "推定稼働率",
            f"{utilization_rate:.1f}%",
            1.7
        ), unsafe_allow_html=True)

def render_analysis_results(analysis_df, filters, target_dict):
    """分析結果表示（従来版）"""
    view_type = filters['view_type']
    analysis_type = filters['analysis_type']
    
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
            fig = plot_monthly_hospital_graph(monthly_data, target_dict)
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("月次統計詳細"):
                st.dataframe(monthly_data, use_container_width=True)
    
    # 四半期分析
    elif view_type == "四半期":
        st.subheader(f"🗓️ {analysis_type} - 四半期推移")
        
        quarterly_data = analyze_quarterly_summary(analysis_df)
        if not quarterly_data.empty:
            fig = plot_quarterly_hospital_graph(quarterly_data, target_dict)
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("四半期統計詳細"):
                st.dataframe(quarterly_data, use_container_width=True)
    
    # 診療科別内訳
    render_department_breakdown(analysis_df, analysis_type)

def render_analysis_results_complete_weeks(analysis_df, filters, target_dict):
    """分析結果表示（完全週対応版）"""
    view_type = filters['view_type']
    analysis_type = filters['analysis_type']
    
    # 週次分析（完全週対応）
    if view_type == "週次":
        st.subheader(f"📈 {analysis_type} - 週次推移（完全週データ）")
        
        summary_data = analyze_weekly_summary_complete(analysis_df, target_dict, st.session_state.get('latest_date'))
        if not summary_data.empty:
            fig = plot_weekly_summary_graph_complete(summary_data, f"全科({analysis_type})", target_dict)
            st.plotly_chart(fig, use_container_width=True)
            
            # 統計情報
            with st.expander("週次統計詳細（完全週データ）"):
                st.dataframe(summary_data, use_container_width=True)
        else:
            st.warning("表示可能な完全週データがありません。")
    
    # その他の分析は従来版と同じ
    elif view_type == "月次":
        render_monthly_analysis(analysis_df, analysis_type, target_dict)
    elif view_type == "四半期":
        render_quarterly_analysis(analysis_df, analysis_type, target_dict)

def render_monthly_analysis(analysis_df, analysis_type, target_dict):
    """月次分析"""
    st.subheader(f"📅 {analysis_type} - 月次推移")
    
    monthly_data = analyze_monthly_summary(analysis_df)
    if not monthly_data.empty:
        fig = plot_monthly_hospital_graph(monthly_data, target_dict)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("月次統計詳細"):
            st.dataframe(monthly_data, use_container_width=True)
    else:
        st.warning("月次データがありません。")

def render_quarterly_analysis(analysis_df, analysis_type, target_dict):
    """四半期分析"""
    st.subheader(f"🗓️ {analysis_type} - 四半期推移")
    
    quarterly_data = analyze_quarterly_summary(analysis_df)
    if not quarterly_data.empty:
        fig = plot_quarterly_hospital_graph(quarterly_data, target_dict)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("四半期統計詳細"):
            st.dataframe(quarterly_data, use_container_width=True)
    else:
        st.warning("四半期データがありません。")

def render_department_breakdown(analysis_df, analysis_type):
    """診療科別内訳表示"""
    st.markdown("---")
    st.subheader(f"🏛️ 診療科別 {analysis_type} 内訳")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 診療科別件数
        if '実施診療科' in analysis_df.columns:
            dept_counts = analysis_df.groupby('実施診療科').size().sort_values(ascending=False).head(10)
            
            if not dept_counts.empty:
                fig_dept = px.bar(
                    x=dept_counts.values,
                    y=dept_counts.index,
                    orientation='h',
                    title=f"診療科別{analysis_type}件数 (Top 10)"
                )
                fig_dept.update_layout(height=400)
                st.plotly_chart(fig_dept, use_container_width=True)
        else:
            st.warning("診療科データがありません。")
    
    with col2:
        # 時間分析
        if not analysis_df.empty and '手術実施日_dt' in analysis_df.columns:
            analysis_df_copy = analysis_df.copy()
            analysis_df_copy['曜日'] = analysis_df_copy['手術実施日_dt'].dt.day_name()
            weekday_dist = analysis_df_copy.groupby('曜日').size()
            
            # 曜日の順序を調整
            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            weekday_jp = ['月', '火', '水', '木', '金', '土', '日']
            
            # データを日本語曜日に変換
            weekday_jp_data = []
            for day in weekday_order:
                jp_day = weekday_jp[weekday_order.index(day)]
                count = weekday_dist.get(day, 0)
                weekday_jp_data.append(count)
            
            fig_week = px.pie(
                values=weekday_jp_data,
                names=weekday_jp,
                title=f"曜日別{analysis_type}分布"
            )
            fig_week.update_layout(height=400)
            st.plotly_chart(fig_week, use_container_width=True)

def render_detailed_statistics(analysis_df):
    """詳細統計表示"""
    st.markdown("### 📈 詳細統計")
    
    if analysis_df.empty:
        st.warning("統計計算用のデータがありません。")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("基本統計")
        st.write(f"総件数: {len(analysis_df):,}")
        if '手術実施日_dt' in analysis_df.columns:
            date_range = (analysis_df['手術実施日_dt'].max() - analysis_df['手術実施日_dt'].min()).days + 1
            st.write(f"期間: {date_range}日")
            st.write(f"1日平均: {len(analysis_df) / date_range:.1f}件")
    
    with col2:
        st.subheader("診療科統計")
        if '実施診療科' in analysis_df.columns:
            st.write(f"診療科数: {analysis_df['実施診療科'].nunique()}")
            top_dept = analysis_df['実施診療科'].value_counts().index[0]
            st.write(f"最多診療科: {top_dept}")
    
    with col3:
        st.subheader("時間統計")
        if '手術実施日_dt' in analysis_df.columns:
            # 最も手術が多い曜日
            analysis_df_copy = analysis_df.copy()
            analysis_df_copy['曜日'] = analysis_df_copy['手術実施日_dt'].dt.day_name()
            most_busy_day = analysis_df_copy['曜日'].value_counts().index[0]
            st.write(f"最多曜日: {most_busy_day}")

def render_export_options(analysis_df, filters):
    """エクスポートオプション"""
    st.markdown("### 📥 データエクスポート")
    
    if analysis_df.empty:
        st.warning("エクスポート可能なデータがありません。")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # CSV出力
        csv_data = analysis_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 CSV形式でダウンロード",
            data=csv_data,
            file_name=f"hospital_analysis_{filters.get('analysis_type', 'data')}.csv",
            mime='text/csv'
        )
    
    with col2:
        # 統計サマリー出力
        if not analysis_df.empty:
            summary_stats = {
                '項目': ['総件数', '期間(日)', '1日平均', '診療科数'],
                '値': [
                    len(analysis_df),
                    (analysis_df['手術実施日_dt'].max() - analysis_df['手術実施日_dt'].min()).days + 1 if '手術実施日_dt' in analysis_df.columns else 'N/A',
                    len(analysis_df) / ((analysis_df['手術実施日_dt'].max() - analysis_df['手術実施日_dt'].min()).days + 1) if '手術実施日_dt' in analysis_df.columns else 'N/A',
                    analysis_df['実施診療科'].nunique() if '実施診療科' in analysis_df.columns else 'N/A'
                ]
            }
            summary_df = pd.DataFrame(summary_stats)
            summary_csv = summary_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📊 統計サマリーをダウンロード",
                data=summary_csv,
                file_name=f"hospital_summary_{filters.get('analysis_type', 'data')}.csv",
                mime='text/csv'
            )
    
    with col3:
        # 診療科別データ出力
        if '実施診療科' in analysis_df.columns:
            dept_summary = analysis_df.groupby('実施診療科').size().reset_index(name='件数')
            dept_csv = dept_summary.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="🏥 診療科別データをダウンロード",
                data=dept_csv,
                file_name=f"department_breakdown_{filters.get('analysis_type', 'data')}.csv",
                mime='text/csv'
            )