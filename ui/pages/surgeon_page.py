# ui/pages/surgeon_page.py (期間選択機能追加版)
"""
術者分析ページモジュール
術者別の詳細分析を表示（期間選択機能追加）
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, Any, Optional, List
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
from ui.components.period_selector import PeriodSelector

# 既存の分析モジュールをインポート
from analysis import surgeon, weekly, ranking
from plotting import generic_plots

logger = logging.getLogger(__name__)


class SurgeonPage:
    """術者分析ページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("術者分析ページ描画")
    def render() -> None:
        """術者分析ページを描画"""
        st.title("👨‍⚕️ 術者分析")
        
        # データ取得
        df = SessionManager.get_processed_df()
        
        if df.empty:
            st.warning("⚠️ データが読み込まれていません")
            return
        
        # 期間選択セクション
        st.markdown("---")
        period_name, start_date, end_date = PeriodSelector.render(
            page_name="surgeon_analysis",
            show_info=True,
            key_suffix="surgeon"
        )
        
        # 期間に基づいてデータをフィルタリング
        filtered_df = PeriodSelector.filter_data_by_period(df, start_date, end_date)
        
        if filtered_df.empty:
            st.warning(f"⚠️ 選択期間（{period_name}）にデータがありません")
            return
        
        # 期間サマリー表示
        if start_date and end_date:
            st.markdown("---")
            PeriodSelector.render_period_summary(period_name, start_date, end_date, filtered_df)
        
        st.markdown("---")
        
        # 術者データの前処理
        try:
            with st.spinner("術者データを処理中..."):
                expanded_df = surgeon.get_expanded_surgeon_df(filtered_df)
                
                if expanded_df.empty:
                    st.warning("選択期間に分析可能な術者データがありません")
                    return
                
                surgeon_summary = surgeon.get_surgeon_summary(expanded_df)
                
                if surgeon_summary.empty:
                    st.warning("術者サマリーの生成に失敗しました")
                    return
        except Exception as e:
            st.error(f"術者データ処理エラー: {e}")
            logger.error(f"術者データ処理エラー: {e}")
            return
        
        # 分析タブ
        tab1, tab2, tab3, tab4 = st.tabs([
            "全体ランキング", 
            "診療科別分析", 
            "詳細統計", 
            "期間比較"
        ])
        
        with tab1:
            SurgeonPage._render_overall_ranking_tab(
                surgeon_summary, expanded_df, period_name
            )
        
        with tab2:
            SurgeonPage._render_department_analysis_tab(
                expanded_df, surgeon_summary, period_name
            )
        
        with tab3:
            SurgeonPage._render_detailed_statistics_tab(
                surgeon_summary, expanded_df, period_name
            )
        
        with tab4:
            SurgeonPage._render_period_comparison_tab(period_name)
    
    @staticmethod
    @safe_data_operation("全体ランキング表示")
    def _render_overall_ranking_tab(surgeon_summary: pd.DataFrame, 
                                  expanded_df: pd.DataFrame,
                                  period_name: str) -> None:
        """全体ランキングタブ"""
        st.subheader(f"🏆 術者ランキング - {period_name}")
        
        try:
            # ランキング表示件数選択
            col1, col2 = st.columns([1, 3])
            
            with col1:
                display_count = st.selectbox(
                    "表示件数",
                    [10, 15, 20, 30, 50],
                    index=1,  # デフォルト15件
                    key="surgeon_ranking_count"
                )
            
            with col2:
                st.info(f"💡 選択期間（{period_name}）の術者ランキング Top {display_count}")
            
            # ランキングチャート
            if len(surgeon_summary) > 0:
                fig = generic_plots.plot_surgeon_ranking(
                    surgeon_summary, 
                    display_count, 
                    f"術者ランキング ({period_name})"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 術者統計サマリー
                SurgeonPage._render_surgeon_summary_metrics(surgeon_summary, expanded_df)
                
                # 詳細ランキングテーブル
                with st.expander(f"📋 詳細ランキングテーブル (Top {display_count})"):
                    display_df = surgeon_summary.head(display_count).copy()
                    
                    # ランキング列を追加
                    display_df['順位'] = range(1, len(display_df) + 1)
                    
                    # 列の順序を調整
                    columns = ['順位'] + [col for col in display_df.columns if col != '順位']
                    display_df = display_df[columns]
                    
                    st.dataframe(display_df, use_container_width=True)
                
                # TOP3術者の詳細
                SurgeonPage._render_top3_surgeons_detail(surgeon_summary, expanded_df)
                
            else:
                st.warning("表示する術者データがありません")
                
        except Exception as e:
            st.error(f"全体ランキング表示エラー: {e}")
            logger.error(f"全体ランキング表示エラー: {e}")
    
    @staticmethod
    def _render_surgeon_summary_metrics(surgeon_summary: pd.DataFrame, 
                                      expanded_df: pd.DataFrame) -> None:
        """術者統計サマリーメトリクス"""
        try:
            # 件数列の列名を特定
            count_column = None
            for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                if col in surgeon_summary.columns:
                    count_column = col
                    break
            
            if count_column is None:
                # 数値列の最初の列を使用
                numeric_cols = surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    count_column = numeric_cols[0]
                    logger.warning(f"件数列が見つからないため、{count_column}を使用")
                else:
                    st.warning("術者サマリーに件数データが含まれていません")
                    return
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_surgeons = len(surgeon_summary)
                st.metric("👨‍⚕️ 総術者数", f"{total_surgeons}名")
            
            with col2:
                total_cases = surgeon_summary[count_column].sum()
                st.metric("📊 総手術件数", f"{total_cases:,}件")
            
            with col3:
                avg_cases = surgeon_summary[count_column].mean()
                st.metric("📈 平均件数", f"{avg_cases:.1f}件/人")
            
            with col4:
                if total_surgeons > 0:
                    top_surgeon_cases = surgeon_summary.iloc[0][count_column]
                    st.metric("🏆 最多術者", f"{top_surgeon_cases}件")
                else:
                    st.metric("🏆 最多術者", "0件")
            
            # 術者分布分析
            if len(surgeon_summary) >= 5:
                col1, col2 = st.columns(2)
                
                with col1:
                    # 件数分布
                    high_volume = len(surgeon_summary[surgeon_summary[count_column] >= 10])
                    medium_volume = len(surgeon_summary[
                        (surgeon_summary[count_column] >= 5) & (surgeon_summary[count_column] < 10)
                    ])
                    low_volume = len(surgeon_summary[surgeon_summary[count_column] < 5])
                    
                    st.write("**術者分布 (件数別):**")
                    st.write(f"• 高ボリューム (10件以上): {high_volume}名")
                    st.write(f"• 中ボリューム (5-9件): {medium_volume}名") 
                    st.write(f"• 低ボリューム (5件未満): {low_volume}名")
                
                with col2:
                    # 集中度分析
                    top10_cases = surgeon_summary.head(10)[count_column].sum()
                    concentration_rate = (top10_cases / total_cases * 100) if total_cases > 0 else 0
                    
                    st.write("**手術件数集中度:**")
                    st.write(f"• TOP10術者の件数: {top10_cases}件")
                    st.write(f"• 全体に占める割合: {concentration_rate:.1f}%")
                    
                    if concentration_rate > 70:
                        st.warning("⚠️ 特定術者への集中度が高い")
                    elif concentration_rate > 50:
                        st.info("💡 中程度の集中度")
                    else:
                        st.success("✅ バランスの良い分散")
            
        except Exception as e:
            logger.error(f"術者サマリーメトリクス表示エラー: {e}")

    @staticmethod
    def _render_top3_surgeons_detail(surgeon_summary: pd.DataFrame, 
                                expanded_df: pd.DataFrame) -> None:
        """TOP3術者の詳細情報"""
        try:
            if len(surgeon_summary) >= 3:
                st.subheader("🥇 TOP3術者 詳細")
                
                # 件数列の列名を特定
                count_column = None
                for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                    if col in surgeon_summary.columns:
                        count_column = col
                        break
                
                if count_column is None:
                    numeric_cols = surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                    if len(numeric_cols) > 0:
                        count_column = numeric_cols[0]
                
                if count_column is None:
                    st.warning("術者サマリーに件数データが含まれていません")
                    return
                
                # 術者名列を特定
                name_column = None
                for col in ['術者名', '術者', 'surgeon', 'Surgeon', 'name']:
                    if col in surgeon_summary.columns:
                        name_column = col
                        break
                
                if name_column is None:
                    # 最初の文字列列を術者名として使用
                    str_cols = surgeon_summary.select_dtypes(include=['object']).columns
                    if len(str_cols) > 0:
                        name_column = str_cols[0]
                
                if name_column is None:
                    st.warning("術者名の列が見つかりません")
                    return
                
                for i in range(min(3, len(surgeon_summary))):
                    surgeon_data = surgeon_summary.iloc[i]
                    surgeon_name = surgeon_data[name_column]
                    surgeon_cases = surgeon_data[count_column]
                    
                    # 該当術者のデータを取得
                    surgeon_expanded = expanded_df[expanded_df['術者名'] == surgeon_name]
                    
                    with st.expander(f"🏆 {i+1}位: {surgeon_name} ({surgeon_cases}件)"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**基本情報:**")
                            st.write(f"• 手術件数: {surgeon_cases}件")
                            
                            if '実施診療科' in surgeon_expanded.columns:
                                departments = surgeon_expanded['実施診療科'].value_counts()
                                main_dept = departments.index[0] if len(departments) > 0 else "不明"
                                st.write(f"• 主要診療科: {main_dept}")
                                st.write(f"• 関連診療科数: {len(departments)}科")
                        
                        with col2:
                            if len(surgeon_expanded) > 0:
                                st.write("**活動パターン:**")
                                
                                # 平日・休日比率
                                if 'is_weekday' in surgeon_expanded.columns:
                                    weekday_cases = len(surgeon_expanded[surgeon_expanded['is_weekday']])
                                    weekday_ratio = (weekday_cases / len(surgeon_expanded) * 100)
                                    st.write(f"• 平日手術: {weekday_cases}件 ({weekday_ratio:.1f}%)")
                                
                                # 期間内分布
                                if len(surgeon_expanded) >= 7:
                                    date_range = (
                                        surgeon_expanded['手術実施日_dt'].max() - 
                                        surgeon_expanded['手術実施日_dt'].min()
                                    ).days + 1
                                    frequency = len(surgeon_expanded) / date_range if date_range > 0 else 0
                                    st.write(f"• 実施頻度: {frequency:.2f}件/日")
        except Exception as e:
        logger.error(f"TOP3術者詳細表示エラー: {e}")
    
    @staticmethod
    @safe_data_operation("診療科別分析表示")
    def _render_department_analysis_tab(expanded_df: pd.DataFrame,
                                      surgeon_summary: pd.DataFrame, 
                                      period_name: str) -> None:
        """診療科別分析タブ"""
        st.subheader(f"🏥 診療科別術者分析 - {period_name}")
        
        try:
            if '実施診療科' not in expanded_df.columns:
                st.warning("診療科情報が不足しています")
                return
            
            # 診療科選択
            departments = sorted(expanded_df['実施診療科'].dropna().unique())
            
            if not departments:
                st.warning("分析可能な診療科データがありません")
                return
            
            selected_dept = st.selectbox(
                "分析する診療科を選択",
                ["全診療科"] + departments,
                key="surgeon_dept_selector"
            )
            
            if selected_dept == "全診療科":
                SurgeonPage._render_all_departments_analysis(expanded_df, surgeon_summary)
            else:
                SurgeonPage._render_single_department_analysis(
                    expanded_df, surgeon_summary, selected_dept, period_name
                )
                
        except Exception as e:
            st.error(f"診療科別分析エラー: {e}")
            logger.error(f"診療科別分析エラー: {e}")

    @staticmethod
    def _render_all_departments_analysis(expanded_df: pd.DataFrame,
                                    surgeon_summary: pd.DataFrame) -> None:
        """全診療科分析"""
        try:
            st.markdown("**🏥 診療科別サマリー**")
            
            # 診療科別統計
            dept_stats = expanded_df.groupby('実施診療科').agg({
                '手術実施日_dt': 'count',
                '術者名': 'nunique'
            }).rename(columns={
                '手術実施日_dt': '手術件数',
                '術者名': '術者数'
            }).sort_values('手術件数', ascending=False)
            
            # 平均件数/術者を計算
            dept_stats['平均件数/術者'] = (dept_stats['手術件数'] / dept_stats['術者数']).round(1)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**診療科別手術件数:**")
                st.dataframe(dept_stats.head(10), use_container_width=True)
            
            with col2:
                # 診療科別術者数の可視化
                if len(dept_stats) > 0:
                    fig = px.bar(
                        x=dept_stats.head(10).index,
                        y=dept_stats.head(10)['術者数'],
                        title="診療科別術者数 (Top 10)",
                        labels={'x': '診療科', 'y': '術者数'}
                    )
                    fig.update_xaxis(tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)
            
            # 診療科別TOP術者
            st.markdown("**🏆 診療科別TOP術者**")
            
            top_surgeons_by_dept = []
            for dept in dept_stats.head(5).index:  # TOP5診療科
                dept_data = expanded_df[expanded_df['実施診療科'] == dept]
                dept_surgeon_summary = surgeon.get_surgeon_summary(dept_data)
                
                if not dept_surgeon_summary.empty:
                    # 件数列の列名を特定
                    count_column = None
                    for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                        if col in dept_surgeon_summary.columns:
                            count_column = col
                            break
                    
                    if count_column is None:
                        numeric_cols = dept_surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                        if len(numeric_cols) > 0:
                            count_column = numeric_cols[0]
                    
                    # 術者名列を特定
                    name_column = None
                    for col in ['術者名', '術者', 'surgeon', 'Surgeon', 'name']:
                        if col in dept_surgeon_summary.columns:
                            name_column = col
                            break
                    
                    if name_column is None:
                        str_cols = dept_surgeon_summary.select_dtypes(include=['object']).columns
                        if len(str_cols) > 0:
                            name_column = str_cols[0]
                    
                    if count_column and name_column:
                        top_surgeon = dept_surgeon_summary.iloc[0]
                        top_surgeons_by_dept.append({
                            '診療科': dept,
                            'TOP術者': top_surgeon[name_column],
                            '件数': top_surgeon[count_column]
                        })
            
            if top_surgeons_by_dept:
                top_surgeons_df = pd.DataFrame(top_surgeons_by_dept)
                st.dataframe(top_surgeons_df, use_container_width=True)
                
        except Exception as e:
            logger.error(f"全診療科分析エラー: {e}")
            st.error("全診療科分析でエラーが発生しました")

    @staticmethod
    def _render_single_department_analysis(expanded_df: pd.DataFrame,
                                        surgeon_summary: pd.DataFrame,
                                        dept_name: str,
                                        period_name: str) -> None:
        """単一診療科分析"""
        try:
            st.markdown(f"**🩺 {dept_name} 術者分析**")
            
            # 診療科データを抽出
            dept_df = expanded_df[expanded_df['実施診療科'] == dept_name]
            
            if dept_df.empty:
                st.warning(f"{dept_name}のデータがありません")
                return
            
            # 診療科内術者ランキング
            dept_surgeon_summary = surgeon.get_surgeon_summary(dept_df)
            
            if not dept_surgeon_summary.empty:
                # 件数列の列名を特定
                count_column = None
                for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                    if col in dept_surgeon_summary.columns:
                        count_column = col
                        break
                
                if count_column is None:
                    numeric_cols = dept_surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                    if len(numeric_cols) > 0:
                        count_column = numeric_cols[0]
                    else:
                        st.warning("件数データが見つかりません")
                        return
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 術者ランキングチャート
                    fig = generic_plots.plot_surgeon_ranking(
                        dept_surgeon_summary,
                        min(15, len(dept_surgeon_summary)),
                        f"{dept_name} 術者ランキング"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # 診療科統計
                    st.write("**診療科統計:**")
                    st.metric("術者数", f"{len(dept_surgeon_summary)}名")
                    st.metric("総手術件数", f"{dept_surgeon_summary[count_column].sum()}件")
                    st.metric("平均件数/術者", f"{dept_surgeon_summary[count_column].mean():.1f}件")
                    
                    if len(dept_surgeon_summary) > 0:
                        top_surgeon_cases = dept_surgeon_summary.iloc[0][count_column]
                        st.metric("TOP術者件数", f"{top_surgeon_cases}件")
                
                # 詳細テーブル
                with st.expander(f"📋 {dept_name} 術者詳細リスト"):
                    display_df = dept_surgeon_summary.copy()
                    display_df['順位'] = range(1, len(display_df) + 1)
                    columns = ['順位'] + [col for col in display_df.columns if col != '順位']
                    display_df = display_df[columns]
                    st.dataframe(display_df, use_container_width=True)
                
                # 時系列分析（データが十分にある場合）
                if len(dept_df) >= 10:
                    SurgeonPage._render_department_time_series(dept_df, dept_name, period_name)
            else:
                st.warning(f"{dept_name}の術者データを生成できませんでした")
                
        except Exception as e:
        logger.error(f"単一診療科分析エラー: {e}")
        st.error("診療科分析でエラーが発生しました")
    
    @staticmethod
    def _render_department_time_series(dept_df: pd.DataFrame, 
                                     dept_name: str,
                                     period_name: str) -> None:
        """診療科の時系列分析"""
        try:
            st.markdown(f"**📈 {dept_name} 時系列分析**")
            
            # 日別件数推移
            daily_counts = dept_df.groupby('手術実施日_dt').size().reset_index(name='件数')
            
            if len(daily_counts) >= 7:
                fig = px.line(
                    daily_counts,
                    x='手術実施日_dt',
                    y='件数',
                    title=f"{dept_name} 日別手術件数推移 - {period_name}",
                    labels={'手術実施日_dt': '日付', '件数': '手術件数'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # 術者別時系列（主要術者のみ）
            surgeon_counts = dept_df['術者名'].value_counts()
            main_surgeons = surgeon_counts.head(5).index  # TOP5術者
            
            if len(main_surgeons) > 1:
                surgeon_daily = []
                for surgeon_name in main_surgeons:
                    surgeon_data = dept_df[dept_df['術者名'] == surgeon_name]
                    surgeon_daily_counts = surgeon_data.groupby('手術実施日_dt').size().reset_index(name='件数')
                    surgeon_daily_counts['術者名'] = surgeon_name
                    surgeon_daily.append(surgeon_daily_counts)
                
                if surgeon_daily:
                    all_surgeon_daily = pd.concat(surgeon_daily, ignore_index=True)
                    
                    fig = px.line(
                        all_surgeon_daily,
                        x='手術実施日_dt',
                        y='件数',
                        color='術者名',
                        title=f"{dept_name} 主要術者別推移 - {period_name}",
                        labels={'手術実施日_dt': '日付', '件数': '手術件数'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
        except Exception as e:
            logger.error(f"診療科時系列分析エラー: {e}")

    @staticmethod
    @safe_data_operation("詳細統計表示")
    def _render_detailed_statistics_tab(surgeon_summary: pd.DataFrame,
                                    expanded_df: pd.DataFrame,
                                    period_name: str) -> None:
        """詳細統計タブ"""
        st.subheader(f"📊 術者詳細統計 - {period_name}")
        
        try:
            if surgeon_summary.empty:
                st.warning("統計分析用データがありません")
                return
            
            # 件数列の列名を特定
            count_column = None
            for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                if col in surgeon_summary.columns:
                    count_column = col
                    break
            
            if count_column is None:
                numeric_cols = surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    count_column = numeric_cols[0]
                else:
                    st.warning("件数データが見つかりません")
                    return
            
            # 統計分析
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📈 件数分布統計**")
                
                # 基本統計
                stats = surgeon_summary[count_column].describe()
                for stat_name, value in stats.items():
                    st.write(f"• {stat_name}: {value:.1f}")
                
                # パーセンタイル分析
                percentiles = [90, 75, 50, 25, 10]
                st.write("\n**パーセンタイル分析:**")
                for p in percentiles:
                    value = surgeon_summary[count_column].quantile(p/100)
                    st.write(f"• {p}パーセンタイル: {value:.1f}件")
            
            with col2:
                st.markdown("**📊 分布可視化**")
                
                # ヒストグラム
                fig = px.histogram(
                    surgeon_summary,
                    x=count_column,
                    bins=20,
                    title="術者別手術件数分布",
                    labels={count_column: '手術件数', 'count': '術者数'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # 詳細分析
            st.markdown("**🔍 詳細分析**")
            
            # 件数区分別分析
            SurgeonPage._render_volume_category_analysis(surgeon_summary)
            
            # 診療科横断術者分析（複数診療科で手術している術者）
            if '実施診療科' in expanded_df.columns:
                SurgeonPage._render_cross_department_analysis(expanded_df)
            
            # パフォーマンス指標
            SurgeonPage._render_performance_indicators(surgeon_summary, expanded_df)
            
        except Exception as e:
            st.error(f"詳細統計表示エラー: {e}")
            logger.error(f"詳細統計表示エラー: {e}")

    @staticmethod
    def _render_volume_category_analysis(surgeon_summary: pd.DataFrame) -> None:
        """件数区分別分析"""
        try:
            # 件数列の列名を特定
            count_column = None
            for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                if col in surgeon_summary.columns:
                    count_column = col
                    break
            
            if count_column is None:
                numeric_cols = surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    count_column = numeric_cols[0]
                else:
                    st.warning("件数データが見つかりません")
                    return
            
            # 件数区分を定義
            categories = {
                'ハイボリューム (20件以上)': surgeon_summary[surgeon_summary[count_column] >= 20],
                'ミドルボリューム (10-19件)': surgeon_summary[
                    (surgeon_summary[count_column] >= 10) & (surgeon_summary[count_column] < 20)
                ],
                'ローボリューム (5-9件)': surgeon_summary[
                    (surgeon_summary[count_column] >= 5) & (surgeon_summary[count_column] < 10)
                ],
                'ベリーロー (5件未満)': surgeon_summary[surgeon_summary[count_column] < 5]
            }
            
            st.markdown("**📊 ボリューム区分別分析**")
            
            # サマリーテーブル
            category_summary = []
            for category_name, category_data in categories.items():
                if not category_data.empty:
                    category_summary.append({
                        '区分': category_name,
                        '術者数': len(category_data),
                        '総件数': category_data[count_column].sum(),
                        '平均件数': category_data[count_column].mean(),
                        '割合': f"{len(category_data) / len(surgeon_summary) * 100:.1f}%"
                    })
            
            if category_summary:
                category_df = pd.DataFrame(category_summary)
                st.dataframe(category_df, use_container_width=True)
                
                # 可視化
                fig = px.pie(
                    category_df,
                    values='術者数',
                    names='区分',
                    title="術者のボリューム区分分布"
                )
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            logger.error(f"ボリューム区分別分析エラー: {e}")
    
    @staticmethod
    def _render_cross_department_analysis(expanded_df: pd.DataFrame) -> None:
        """診療科横断術者分析"""
        try:
            st.markdown("**🔄 診療科横断術者分析**")
            
            # 術者別診療科数を計算
            surgeon_dept_counts = expanded_df.groupby('術者名')['実施診療科'].nunique()
            multi_dept_surgeons = surgeon_dept_counts[surgeon_dept_counts > 1]
            
            if not multi_dept_surgeons.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("複数診療科術者", f"{len(multi_dept_surgeons)}名")
                    st.metric("最大診療科数", f"{multi_dept_surgeons.max()}科")
                
                with col2:
                    # 複数診療科術者の詳細
                    multi_dept_details = []
                    for surgeon_name in multi_dept_surgeons.head(10).index:
                        surgeon_data = expanded_df[expanded_df['術者名'] == surgeon_name]
                        dept_list = surgeon_data['実施診療科'].unique()
                        multi_dept_details.append({
                            '術者名': surgeon_name,
                            '診療科数': len(dept_list),
                            '手術件数': len(surgeon_data),
                            '関連診療科': ', '.join(dept_list[:3]) + ('...' if len(dept_list) > 3 else '')
                        })
                    
                    if multi_dept_details:
                        multi_dept_df = pd.DataFrame(multi_dept_details)
                        st.dataframe(multi_dept_df, use_container_width=True)
            else:
                st.info("複数診療科で手術を行っている術者はいません")
                
        except Exception as e:
            logger.error(f"診療科横断分析エラー: {e}")

    @staticmethod
    def _render_performance_indicators(surgeon_summary: pd.DataFrame, 
                                    expanded_df: pd.DataFrame) -> None:
        """パフォーマンス指標"""
        try:
            st.markdown("**📈 パフォーマンス指標**")
            
            # 件数列の列名を特定
            count_column = None
            for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                if col in surgeon_summary.columns:
                    count_column = col
                    break
            
            if count_column is None:
                numeric_cols = surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    count_column = numeric_cols[0]
                else:
                    st.warning("件数データが見つかりません")
                    return
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # 集中度指標（ジニ係数的な）
                total_cases = surgeon_summary[count_column].sum()
                sorted_cases = surgeon_summary[count_column].sort_values(ascending=False)
                
                # TOP10%の術者が実施する手術の割合
                top10_percent_count = max(1, len(surgeon_summary) // 10)
                top10_percent_cases = sorted_cases.head(top10_percent_count).sum()
                concentration_ratio = (top10_percent_cases / total_cases * 100) if total_cases > 0 else 0
                
                st.metric("TOP10%集中度", f"{concentration_ratio:.1f}%")
                
                if concentration_ratio > 60:
                    st.warning("高い集中度")
                elif concentration_ratio > 40:
                    st.info("中程度の集中度")
                else:
                    st.success("分散型")
            
            with col2:
                # 活動レベル指標
                active_surgeons = len(surgeon_summary[surgeon_summary[count_column] >= 5])
                activity_rate = (active_surgeons / len(surgeon_summary) * 100) if len(surgeon_summary) > 0 else 0
                
                st.metric("活発術者率", f"{activity_rate:.1f}%")
                st.caption("5件以上実施術者の割合")
            
            with col3:
                # 平日手術比率（データがある場合）
                if 'is_weekday' in expanded_df.columns:
                    weekday_cases = len(expanded_df[expanded_df['is_weekday']])
                    weekday_ratio = (weekday_cases / len(expanded_df) * 100) if len(expanded_df) > 0 else 0
                    
                    st.metric("平日手術比率", f"{weekday_ratio:.1f}%")
                else:
                    st.metric("平日手術比率", "N/A")
                    
    except Exception as e:
        logger.error(f"パフォーマンス指標表示エラー: {e}")
    
    @staticmethod
    def _render_period_comparison_tab(current_period_name: str) -> None:
        """期間比較タブ"""
        st.subheader("📅 術者分析期間比較")
        
        try:
            st.markdown("**比較期間を選択してください:**")
            
            # 比較期間選択
            compare_period, compare_start, compare_end = PeriodSelector.render(
                page_name="surgeon_compare",
                show_info=False,
                key_suffix="surgeon_compare"
            )
            
            if compare_start and compare_end:
                # 全データを取得して比較期間でフィルタ
                full_df = SessionManager.get_processed_df()
                compare_df = PeriodSelector.filter_data_by_period(full_df, compare_start, compare_end)
                
                if not compare_df.empty:
                    # 比較期間の術者データを処理
                    compare_expanded = surgeon.get_expanded_surgeon_df(compare_df)
                    
                    if not compare_expanded.empty:
                        compare_surgeon_summary = surgeon.get_surgeon_summary(compare_expanded)
                        
                        # 比較分析を実行
                        SurgeonPage._perform_surgeon_period_comparison(
                            current_period_name,
                            compare_period,
                            compare_surgeon_summary,
                            compare_expanded
                        )
                    else:
                        st.warning(f"比較期間（{compare_period}）に術者データがありません")
                else:
                    st.warning(f"比較期間（{compare_period}）にデータがありません")
            else:
                st.info("比較期間を選択すると、術者分析の比較ができます")
                
        except Exception as e:
            st.error(f"期間比較エラー: {e}")
            logger.error(f"術者期間比較エラー: {e}")

    @staticmethod
    def _perform_surgeon_period_comparison(current_period: str,
                                        compare_period: str,
                                        compare_surgeon_summary: pd.DataFrame,
                                        compare_expanded: pd.DataFrame) -> None:
        """術者期間比較分析を実行"""
        try:
            st.markdown("**📊 期間比較結果**")
            
            # 件数列の列名を特定
            count_column = None
            if not compare_surgeon_summary.empty:
                for col in ['手術件数', '件数', 'count', 'Count', 'surgery_count']:
                    if col in compare_surgeon_summary.columns:
                        count_column = col
                        break
                
                if count_column is None:
                    numeric_cols = compare_surgeon_summary.select_dtypes(include=['int64', 'float64']).columns
                    if len(numeric_cols) > 0:
                        count_column = numeric_cols[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**{current_period}** (現在選択中)")
                st.write("詳細は上記タブで確認")
            
            with col2:
                st.write(f"**{compare_period}** (比較期間)")
                
                # 比較期間の基本統計
                compare_total_surgeons = len(compare_surgeon_summary)
                compare_total_cases = 0
                compare_avg_cases = 0
                
                if count_column and not compare_surgeon_summary.empty:
                    compare_total_cases = compare_surgeon_summary[count_column].sum()
                    compare_avg_cases = compare_surgeon_summary[count_column].mean()
                
                st.metric("術者数", f"{compare_total_surgeons}名")
                st.metric("総手術件数", f"{compare_total_cases}件")
                st.metric("平均件数/術者", f"{compare_avg_cases:.1f}件")
            
            # 比較チャート（可能であれば）
            if not compare_surgeon_summary.empty and len(compare_surgeon_summary) >= 5:
                st.markdown("**📈 比較期間 術者ランキング（TOP10）**")
                
                fig = generic_plots.plot_surgeon_ranking(
                    compare_surgeon_summary,
                    10,
                    f"術者ランキング - {compare_period}"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # 簡単な比較サマリー
            st.markdown("**💡 比較のポイント**")
            st.info(
                f"現在期間（{current_period}）と比較期間（{compare_period}）の詳細比較は、"
                "各タブのデータを参照してご確認ください。"
            )
            
        except Exception as e:
            logger.error(f"術者期間比較実行エラー: {e}")
            st.error("期間比較の実行中にエラーが発生しました")


# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    SurgeonPage.render()