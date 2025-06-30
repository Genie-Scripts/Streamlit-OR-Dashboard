# ui/pages/department_page.py (修正後)
"""
診療科別分析ページモジュール
特定診療科の詳細分析を表示
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Dict, Any, Optional
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
from analysis import weekly, surgeon
from plotting import trend_plots, generic_plots

logger = logging.getLogger(__name__)

class DepartmentPage:
    """診療科別分析ページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("診療科別分析ページ描画")
    def render() -> None:
        """診療科別分析ページを描画"""
        st.title("🩺 診療科別分析")
        
        # データ取得
        df = SessionManager.get_processed_df()
        target_df = SessionManager.get_target_df() # ← target_df を取得
        latest_date = SessionManager.get_latest_date()
        
        # 診療科選択
        selected_dept = DepartmentPage._render_department_selector(df)
        if not selected_dept:
            return
        
        dept_df = df[df['実施診療科'] == selected_dept]
        
        # KPI表示
        DepartmentPage._render_department_kpi(dept_df, latest_date, selected_dept)
        
        # 週次推移 (target_df を渡すように変更)
        DepartmentPage._render_department_trend(df, target_df, selected_dept)
        
        # 詳細分析タブ
        DepartmentPage._render_detailed_analysis_tabs(dept_df, selected_dept)

    @staticmethod
    def _render_department_selector(df: pd.DataFrame) -> Optional[str]:
        """診療科選択UI"""
        departments = sorted(df["実施診療科"].dropna().unique())
        if not departments:
            st.warning("データに診療科情報がありません。")
            return None
        return st.selectbox("分析する診療科を選択", departments)

    @staticmethod
    @safe_data_operation("診療科KPI計算")
    def _render_department_kpi(dept_df: pd.DataFrame, latest_date: Optional[pd.Timestamp], dept_name: str):
        """診療科別KPI表示"""
        kpi_summary = ranking.get_kpi_summary(dept_df, latest_date)
        generic_plots.display_kpi_metrics(kpi_summary)

    @staticmethod
    @safe_data_operation("診療科別週次推移表示")
    def _render_department_trend(df: pd.DataFrame, target_df: pd.DataFrame, dept_name: str) -> None:
        """診療科別週次推移表示 (target_df対応版)"""
        st.markdown("---")
        st.subheader(f"📈 {dept_name} 週次推移")
        
        use_complete_weeks = st.toggle("完全週データのみで分析", True, help="週の途中のデータを除外し、完全な週単位で分析します")
        
        summary = weekly.get_summary(df, department=dept_name, use_complete_weeks=use_complete_weeks)
        
        if not summary.empty:
            # グラフ描画関数に target_df を渡す
            fig = trend_plots.create_weekly_dept_chart(summary, dept_name, target_df)
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("📊 統計サマリー"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**基本統計:**")
                    st.write(f"• 分析週数: {len(summary)}週")
                    st.write(f"• 最大値: {summary['週合計件数'].max():.0f}件/週")
                    st.write(f"• 最小値: {summary['週合計件数'].min():.0f}件/週")
                    st.write(f"• 平均値: {summary['週合計件数'].mean():.1f}件/週")
                
                with col2:
                    st.write("**目標との比較:**")
                    
                    # DataFrameから該当の目標値を取得
                    # メトリック名は'weekly_total_cases'など、目標設定ファイルで定義したものを使用
                    target_series = target_df[
                        (target_df['target_type'] == 'department') &
                        (target_df['code'] == dept_name) &
                        (target_df['metric'] == 'weekly_total_cases') # ← metric名は要確認
                    ]['value']
                    
                    target_value = target_series.iloc[0] if not target_series.empty else None

                    if target_value:
                        avg_actual = summary['週合計件数'].mean()
                        achievement_rate = (avg_actual / target_value) * 100 if target_value > 0 else 0
                        st.write(f"• 目標値: {target_value:.1f}件/週")
                        st.write(f"• 平均達成率: {achievement_rate:.1f}%")
                        
                        if achievement_rate >= 100:
                            st.success("🎯 目標達成！")
                        else:
                            shortfall = target_value - avg_actual
                            st.warning(f"⚠️ 目標まで {shortfall:.1f}件/週不足")
                    else:
                        st.info("この診療科の週次目標は設定されていません")
        else:
            st.warning(f"{dept_name}の週次データがありません")
            
    @staticmethod
    def _render_detailed_analysis_tabs(dept_df: pd.DataFrame, dept_name: str) -> None:
        """詳細分析タブを表示"""
        st.markdown("---")
        st.header("🔍 詳細分析")
        
        tab1, tab2, tab3, tab4 = st.tabs(["術者分析", "時間分析", "統計情報", "累積実績"])
        
        with tab1:
            DepartmentPage._render_surgeon_analysis_tab(dept_df, dept_name)
        
        with tab2:
            DepartmentPage._render_time_analysis_tab(dept_df, dept_name)
        
        with tab3:
            DepartmentPage._render_statistics_tab(dept_df, dept_name)
        
        with tab4:
            DepartmentPage._render_cumulative_tab(dept_df, dept_name)
    
    @staticmethod
    @safe_data_operation("術者分析")
    def _render_surgeon_analysis_tab(dept_df: pd.DataFrame, dept_name: str) -> None:
        """術者分析タブ"""
        st.subheader(f"{dept_name} 術者別件数 (Top 15)")
        
        try:
            with st.spinner("術者データを準備中..."):
                expanded_df = surgeon.get_expanded_surgeon_df(dept_df)
                
                if not expanded_df.empty:
                    surgeon_summary = surgeon.get_surgeon_summary(expanded_df)
                    
                    if not surgeon_summary.empty:
                        fig = generic_plots.plot_surgeon_ranking(surgeon_summary, 15, dept_name)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 詳細データテーブル
                        with st.expander("術者別詳細データ"):
                            st.dataframe(surgeon_summary.head(15), use_container_width=True)
                    else:
                        st.info("術者データを集計できませんでした")
                else:
                    st.info("分析可能な術者データがありません")
                    
        except Exception as e:
            st.error(f"術者分析エラー: {e}")
            logger.error(f"術者分析エラー ({dept_name}): {e}")
    
    @staticmethod
    @safe_data_operation("時間分析")
    def _render_time_analysis_tab(dept_df: pd.DataFrame, dept_name: str) -> None:
        """時間分析タブ"""
        st.subheader("曜日・月別 分布")
        
        try:
            gas_df = dept_df[dept_df['is_gas_20min']]
            
            if not gas_df.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    # 曜日別分布
                    weekday_dist = gas_df['手術実施日_dt'].dt.day_name().value_counts()
                    fig_weekday = px.pie(
                        values=weekday_dist.values, 
                        names=weekday_dist.index, 
                        title="曜日別分布"
                    )
                    st.plotly_chart(fig_weekday, use_container_width=True)
                
                with col2:
                    # 月別分布
                    month_dist = gas_df['手術実施日_dt'].dt.month_name().value_counts()
                    fig_month = px.bar(
                        x=month_dist.index, 
                        y=month_dist.values, 
                        title="月別分布", 
                        labels={'x': '月', 'y': '件数'}
                    )
                    st.plotly_chart(fig_month, use_container_width=True)
                
                # 時間統計
                st.subheader("時間別統計")
                
                # 平日・休日分布
                if 'is_weekday' in gas_df.columns:
                    weekday_count = len(gas_df[gas_df['is_weekday']])
                    weekend_count = len(gas_df[~gas_df['is_weekday']])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("平日手術", f"{weekday_count}件")
                    with col2:
                        st.metric("休日手術", f"{weekend_count}件")
            else:
                st.info("全身麻酔20分以上の手術データがありません")
                
        except Exception as e:
            st.error(f"時間分析エラー: {e}")
            logger.error(f"時間分析エラー ({dept_name}): {e}")
    
    @staticmethod
    def _render_statistics_tab(dept_df: pd.DataFrame, dept_name: str) -> None:
        """統計情報タブ"""
        st.subheader("基本統計")
        
        try:
            gas_df = dept_df[dept_df['is_gas_20min']]
            
            if not gas_df.empty:
                desc_df = gas_df.describe(include='all').transpose()
                st.dataframe(desc_df.astype(str), use_container_width=True)
                
                # データ概要
                st.subheader("データ概要")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("総件数", f"{len(gas_df)}件")
                with col2:
                    st.metric("期間", f"{gas_df['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {gas_df['手術実施日_dt'].max().strftime('%Y/%m/%d')}")
                with col3:
                    if 'is_weekday' in gas_df.columns:
                        weekday_ratio = (gas_df['is_weekday'].sum() / len(gas_df)) * 100
                        st.metric("平日比率", f"{weekday_ratio:.1f}%")
            else:
                st.info("統計情報を計算するデータがありません")
                
        except Exception as e:
            st.error(f"統計情報エラー: {e}")
            logger.error(f"統計情報エラー ({dept_name}): {e}")
    
    @staticmethod
    @safe_data_operation("累積実績")
    def _render_cumulative_tab(dept_df: pd.DataFrame, dept_name: str) -> None:
        """累積実績タブ"""
        st.subheader(f"{dept_name} 今年度 累積実績")
        
        try:
            target_dict = SessionManager.get_target_dict()
            weekly_target = target_dict.get(dept_name)
            
            if weekly_target:
                cum_data = ranking.calculate_cumulative_cases(dept_df, weekly_target)
                
                if not cum_data.empty:
                    fig = generic_plots.plot_cumulative_cases_chart(
                        cum_data, 
                        f"{dept_name} 累積実績"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 累積統計
                    with st.expander("累積統計詳細"):
                        st.dataframe(cum_data, use_container_width=True)
                else:
                    st.info("累積実績データを計算できませんでした")
            else:
                st.info("この診療科の目標値が設定されていないため、累積目標は表示できません。")
                
        except Exception as e:
            st.error(f"累積実績分析エラー: {e}")
            logger.error(f"累積実績分析エラー ({dept_name}): {e}")


# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    DepartmentPage.render()