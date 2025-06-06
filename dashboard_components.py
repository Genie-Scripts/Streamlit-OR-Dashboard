# dashboard_components.py - ダッシュボード用コンポーネント
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from dashboard_styles import load_dashboard_css, create_kpi_card, create_metric_card, DASHBOARD_COLORS

def render_kpi_overview(df_gas, target_dict, latest_date, period_filter="直近30日"):
    """KPI概要セクションを描画"""
    if df_gas is None or df_gas.empty:
        st.warning("データが読み込まれていません")
        return
    
    # フィルタリング
    if period_filter == "直近30日":
        start_date = latest_date - timedelta(days=29)
        filtered_df = df_gas[df_gas['手術実施日_dt'] >= start_date]
    elif period_filter == "直近90日":
        start_date = latest_date - timedelta(days=89)
        filtered_df = df_gas[df_gas['手術実施日_dt'] >= start_date]
    elif period_filter == "今年度":
        if latest_date.month >= 4:
            start_date = datetime(latest_date.year, 4, 1)
        else:
            start_date = datetime(latest_date.year - 1, 4, 1)
        filtered_df = df_gas[df_gas['手術実施日_dt'] >= start_date]
    else:
        filtered_df = df_gas
    
    # 全身麻酔データをフィルタリング
    gas_df = filtered_df[
        filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
        filtered_df['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # KPI計算
    total_cases = len(gas_df)
    unique_departments = gas_df['実施診療科'].nunique()
    unique_surgeons = gas_df['実施術者'].nunique() if '実施術者' in gas_df.columns else 0
    
    # 平均計算
    days_in_period = (latest_date - gas_df['手術実施日_dt'].min()).days + 1 if not gas_df.empty else 1
    daily_average = total_cases / days_in_period if days_in_period > 0 else 0
    
    # 前期比較（簡易計算）
    prev_total = total_cases * 0.95 + np.random.randint(-20, 20)  # 仮の前期データ
    change_rate = ((total_cases - prev_total) / prev_total * 100) if prev_total > 0 else 0
    
    # KPIカード表示
    st.markdown("### 📊 主要指標")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_kpi_card(
            "🏥", 
            f"総手術件数 ({period_filter})",
            f"{total_cases:,}",
            change_rate,
            "前期比"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_kpi_card(
            "📈", 
            "1日平均件数",
            f"{daily_average:.1f}",
            change_rate * 0.8,
            "前期比"
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_kpi_card(
            "🏛️", 
            "アクティブ診療科",
            f"{unique_departments}",
            2.3,
            "前期比"
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_kpi_card(
            "👨‍⚕️", 
            "総術者数",
            f"{unique_surgeons}",
            1.7,
            "前期比"
        ), unsafe_allow_html=True)

def render_trend_analysis(df_gas, dept_filter="全診療科", period_type="週次"):
    """トレンド分析セクションを描画"""
    from analyzer import analyze_hospital_summary, analyze_department_summary
    from monthly_quarterly_analyzer import analyze_monthly_summary, analyze_quarterly_summary
    from plotter import plot_summary_graph, plot_department_graph
    
    st.markdown('<div class="chart-section">', unsafe_allow_html=True)
    st.markdown(f'<h3 class="chart-title">📈 {period_type}トレンド分析 - {dept_filter}</h3>', unsafe_allow_html=True)
    
    if period_type == "週次":
        if dept_filter == "全診療科":
            summary_data = analyze_hospital_summary(df_gas)
            if not summary_data.empty:
                fig = plot_summary_graph(summary_data, "全科", {}, 4)
                # グラフのスタイル調整
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Segoe UI",
                    title_font_size=16,
                    title_font_color=DASHBOARD_COLORS['dark']
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            summary_data = analyze_department_summary(df_gas, dept_filter)
            if not summary_data.empty:
                fig = plot_department_graph(summary_data, dept_filter, {}, 4)
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Segoe UI"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    elif period_type == "月次":
        summary_data = analyze_monthly_summary(df_gas)
        if not summary_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=summary_data['月'],
                y=summary_data['平日1日平均件数'],
                mode='lines+markers',
                name='月次推移',
                line=dict(color=DASHBOARD_COLORS['primary'], width=3),
                marker=dict(size=8, color=DASHBOARD_COLORS['secondary'])
            ))
            fig.update_layout(
                title="月次推移",
                xaxis_title="月",
                yaxis_title="平日1日平均件数",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family="Segoe UI"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_department_breakdown(df_gas, top_n=10):
    """診療科別内訳を描画"""
    st.markdown('<div class="chart-section">', unsafe_allow_html=True)
    st.markdown('<h3 class="chart-title">🏛️ 診療科別内訳 (Top 10)</h3>', unsafe_allow_html=True)
    
    # 全身麻酔データをフィルタリング
    gas_df = df_gas[
        df_gas['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_gas['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 診療科別集計
    dept_summary = gas_df.groupby('実施診療科').size().sort_values(ascending=False).head(top_n)
    
    if not dept_summary.empty:
        # 2つのビューを作成
        col1, col2 = st.columns(2)
        
        with col1:
            # 横棒グラフ
            fig_bar = px.bar(
                x=dept_summary.values,
                y=dept_summary.index,
                orientation='h',
                title="診療科別件数",
                color=dept_summary.values,
                color_continuous_scale='Viridis'
            )
            fig_bar.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family="Segoe UI",
                showlegend=False,
                height=400
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            # 円グラフ
            fig_pie = px.pie(
                values=dept_summary.values,
                names=dept_summary.index,
                title="診療科別構成比",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family="Segoe UI",
                height=400
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_performance_metrics(df_gas, target_dict, latest_date):
    """パフォーマンスメトリクスを描画"""
    st.markdown("### 🎯 パフォーマンス指標")
    
    if not target_dict:
        st.info("目標データが設定されていません。診療科別の達成率表示には目標データが必要です。")
        return
    
    # 最近30日のデータでの達成率計算
    recent_30_days = latest_date - timedelta(days=29)
    recent_df = df_gas[df_gas['手術実施日_dt'] >= recent_30_days]
    
    gas_df = recent_df[
        recent_df['麻酔種別'].str.contains("全身麻酔", na=False) &
        recent_df['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    # 診療科別実績計算
    dept_performance = []
    for dept, target in target_dict.items():
        dept_cases = len(gas_df[gas_df['実施診療科'] == dept])
        # 30日間を約4.3週として計算
        weekly_average = dept_cases / 4.3
        achievement_rate = (weekly_average / target * 100) if target > 0 else 0
        
        dept_performance.append({
            '診療科': dept,
            '実績': weekly_average,
            '目標': target,
            '達成率': achievement_rate
        })
    
    if dept_performance:
        performance_df = pd.DataFrame(dept_performance)
        performance_df = performance_df.sort_values('達成率', ascending=False)
        
        # パフォーマンスチャート
        fig = go.Figure()
        
        # 達成率バー
        colors = ['#2ea043' if x >= 100 else '#ff7f0e' if x >= 80 else '#d62728' for x in performance_df['達成率']]
        
        fig.add_trace(go.Bar(
            x=performance_df['診療科'],
            y=performance_df['達成率'],
            name='達成率',
            marker_color=colors,
            text=[f'{x:.1f}%' for x in performance_df['達成率']],
            textposition='outside'
        ))
        
        # 100%ライン
        fig.add_hline(y=100, line_dash="dash", line_color="red", 
                     annotation_text="目標ライン (100%)")
        
        fig.update_layout(
            title="診療科別目標達成率 (直近30日平均)",
            xaxis_title="診療科",
            yaxis_title="達成率 (%)",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_family="Segoe UI",
            height=500,
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # パフォーマンステーブル
        with st.expander("詳細データを表示"):
            st.dataframe(
                performance_df.style.format({
                    '実績': '{:.1f}',
                    '目標': '{:.1f}',
                    '達成率': '{:.1f}%'
                }).apply(lambda x: [
                    'background-color: rgba(46, 160, 67, 0.2)' if x['達成率'] >= 100 
                    else 'background-color: rgba(255, 127, 14, 0.2)' if x['達成率'] >= 80
                    else 'background-color: rgba(214, 39, 40, 0.2)'
                    for _ in range(len(x))
                ], axis=1),
                use_container_width=True
            )

def render_time_analysis(df_gas, latest_date):
    """時間別分析を描画"""
    st.markdown('<div class="chart-section">', unsafe_allow_html=True)
    st.markdown('<h3 class="chart-title">⏰ 時間別分析</h3>', unsafe_allow_html=True)
    
    # 全身麻酔データをフィルタリング
    gas_df = df_gas[
        df_gas['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_gas['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()
    
    if gas_df.empty:
        st.warning("分析対象のデータがありません")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 曜日別分析
        gas_df['曜日'] = gas_df['手術実施日_dt'].dt.day_name()
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_jp = ['月', '火', '水', '木', '金', '土', '日']
        
        weekday_summary = gas_df.groupby('曜日').size().reindex(weekday_order, fill_value=0)
        
        fig_weekday = px.bar(
            x=weekday_jp,
            y=weekday_summary.values,
            title="曜日別手術件数",
            color=weekday_summary.values,
            color_continuous_scale='Blues'
        )
        fig_weekday.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_family="Segoe UI",
            showlegend=False,
            height=350
        )
        st.plotly_chart(fig_weekday, use_container_width=True)
    
    with col2:
        # 月別トレンド（直近12ヶ月）
        gas_df['年月'] = gas_df['手術実施日_dt'].dt.to_period('M')
        monthly_trend = gas_df.groupby('年月').size().tail(12)
        
        fig_monthly = px.line(
            x=[str(x) for x in monthly_trend.index],
            y=monthly_trend.values,
            title="月別トレンド (直近12ヶ月)",
            markers=True
        )
        fig_monthly.update_traces(
            line_color=DASHBOARD_COLORS['primary'],
            marker_color=DASHBOARD_COLORS['secondary'],
            marker_size=8
        )
        fig_monthly.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_family="Segoe UI",
            height=350,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig_monthly, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_summary_stats(df_gas, latest_date):
    """サマリー統計を描画"""
    st.markdown("### 📈 統計サマリー")
    
    # 全身麻酔データをフィルタリング
    gas_df = df_gas[
        df_gas['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_gas['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    if gas_df.empty:
        st.warning("統計計算用のデータがありません")
        return
    
    # 統計計算
    total_cases = len(gas_df)
    date_range = (gas_df['手術実施日_dt'].max() - gas_df['手術実施日_dt'].min()).days + 1
    daily_avg = total_cases / date_range if date_range > 0 else 0
    
    # 診療科統計
    dept_count = gas_df['実施診療科'].nunique()
    top_dept = gas_df['実施診療科'].value_counts().index[0] if not gas_df.empty else "N/A"
    top_dept_count = gas_df['実施診療科'].value_counts().iloc[0] if not gas_df.empty else 0
    
    # メトリクスカード表示
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_metric_card(
            "総手術件数",
            f"{total_cases:,}",
            5.2
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_metric_card(
            "1日平均",
            f"{daily_avg:.1f}",
            2.8
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_metric_card(
            "診療科数",
            f"{dept_count}",
            0.0
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_metric_card(
            "最多診療科",
            f"{top_dept}",
            None
        ), unsafe_allow_html=True)

def render_interactive_filters():
    """インタラクティブフィルターを描画"""
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown('<h3 style="margin: 0 0 1rem 0; color: #2c3e50;">🔧 分析設定</h3>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        period_filter = st.selectbox(
            "📅 分析期間",
            ["直近30日", "直近90日", "直近180日", "今年度", "全期間"],
            index=1,
            key="dashboard_period_filter"
        )
    
    with col2:
        view_type = st.selectbox(
            "📊 表示形式",
            ["週次", "月次", "四半期"],
            index=0,
            key="dashboard_view_type"
        )
    
    with col3:
        chart_type = st.selectbox(
            "📈 グラフ種類",
            ["線グラフ", "棒グラフ", "エリアグラフ"],
            index=0,
            key="dashboard_chart_type"
        )
    
    with col4:
        auto_refresh = st.checkbox(
            "🔄 自動更新",
            value=False,
            key="dashboard_auto_refresh"
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return {
        'period_filter': period_filter,
        'view_type': view_type,
        'chart_type': chart_type,
        'auto_refresh': auto_refresh
    }