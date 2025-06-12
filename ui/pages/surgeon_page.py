# ui/pages/surgeon_page.py
"""
術者分析ページモジュール
術者別のパフォーマンス分析を表示
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
from ui.components.period_selector import PeriodSelector

from analysis import weekly, surgeon
from plotting import trend_plots, generic_plots

logger = logging.getLogger(__name__)


class SurgeonPage:
    """術者分析ページクラス"""

    @staticmethod
    @safe_streamlit_operation("術者分析ページ描画")
    def render() -> None:
        st.title("👨‍⚕️ 術者分析")
        df = SessionManager.get_processed_df()

        PeriodSelector.render()
        start_date = SessionManager.get_start_date()
        end_date = SessionManager.get_end_date()

        if not all([start_date, end_date]):
            st.error("分析期間が正しく設定されていません。"); return
        
        expanded_df = SurgeonPage._prepare_surgeon_data(df)
        if expanded_df.empty:
            st.warning("分析可能な術者データがありません。"); return
        
        period_expanded_df = expanded_df[
            (expanded_df['手術実施日_dt'] >= start_date) &
            (expanded_df['手術実施日_dt'] <= end_date)
        ]

        analysis_type = st.radio("分析タイプ", ["診療科別ランキング", "術者ごと時系列"], horizontal=True)

        if analysis_type == "診療科別ランキング":
            SurgeonPage._render_ranking_analysis(period_expanded_df)
        else:
            SurgeonPage._render_individual_surgeon_analysis(expanded_df, start_date, end_date)

    @staticmethod
    @safe_data_operation("術者データ準備")
    def _prepare_surgeon_data(df: pd.DataFrame) -> pd.DataFrame:
        try:
            with st.spinner("術者データを準備中..."):
                return surgeon.get_expanded_surgeon_df(df)
        except Exception as e:
            st.error(f"術者データ準備エラー: {e}"); return pd.DataFrame()

    @staticmethod
    @safe_data_operation("ランキング分析")
    def _render_ranking_analysis(period_expanded_df: pd.DataFrame) -> None:
        st.subheader("🏆 術者別ランキング (選択期間)")
        col1, col2 = st.columns(2)
        with col1:
            departments = ["全診療科"] + sorted(period_expanded_df["実施診療科"].dropna().unique())
            selected_dept = st.selectbox("診療科で絞り込み", departments)
        with col2:
            top_n = st.slider("表示する術者数（上位）", 5, 50, 15)
        
        target_df = period_expanded_df if selected_dept == "全診療科" else period_expanded_df[period_expanded_df['実施診療科'] == selected_dept]
        if target_df.empty:
            st.info("選択された条件に一致するデータがありません。"); return

        surgeon_summary = surgeon.get_surgeon_summary(target_df)
        if not surgeon_summary.empty:
            fig = generic_plots.plot_surgeon_ranking(surgeon_summary, top_n, selected_dept)
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("📋 詳細ランキングデータ"):
                st.dataframe(surgeon_summary.head(top_n), use_container_width=True, hide_index=True)

    @staticmethod
    @safe_data_operation("個別術者分析")
    def _render_individual_surgeon_analysis(expanded_df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        st.subheader("📈 術者別時系列分析")
        surgeons = sorted(expanded_df["実施術者"].dropna().unique())
        selected_surgeon = st.selectbox("分析する術者を選択", surgeons)
        if not selected_surgeon: return

        surgeon_full_df = expanded_df[expanded_df['実施術者'] == selected_surgeon]
        surgeon_period_df = surgeon_full_df[(surgeon_full_df['手術実施日_dt'] >= start_date) & (surgeon_full_df['手術実施日_dt'] <= end_date)]

        if surgeon_period_df.empty:
            st.warning(f"{selected_surgeon}のデータが選択期間内に見つかりません"); return

        SurgeonPage._render_surgeon_info(surgeon_period_df)
        SurgeonPage._render_surgeon_weekly_trend(surgeon_full_df, selected_surgeon, start_date, end_date)

    @staticmethod
    def _render_surgeon_info(surgeon_period_df: pd.DataFrame) -> None:
        total_cases = len(surgeon_period_df[surgeon_period_df['is_gas_20min']])
        departments = surgeon_period_df['実施診療科'].nunique()
        date_range_days = (surgeon_period_df['手術実施日_dt'].max() - surgeon_period_df['手術実施日_dt'].min()).days
        col1, col2, col3 = st.columns(3)
        col1.metric("総手術件数 (期間)", f"{total_cases}件")
        col2.metric("関連診療科数", f"{departments}科")
        col3.metric("活動期間", f"{date_range_days + 1}日")

    @staticmethod
    @safe_data_operation("術者週次推移")
    def _render_surgeon_weekly_trend(surgeon_full_df: pd.DataFrame, surgeon_name: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        st.subheader(f"{surgeon_name} の週次実績")
        try:
            summary = weekly.get_summary(surgeon_full_df, use_complete_weeks=False)
            if not summary.empty:
                # 術者分析でも同様に '週' 列でフィルタリング
                date_col = '週'
                if date_col not in summary.columns:
                    st.error(f"週次サマリーに日付情報列 '{date_col}' が見つかりません。"); return
                
                summary[date_col] = pd.to_datetime(summary[date_col])
                period_summary = summary[(summary[date_col] >= start_date) & (summary[date_col] <= end_date)].copy()
                
                if period_summary.empty:
                    st.info("選択期間内にこの術者の週次データはありません。"); return

                period_summary_for_plotting = period_summary.set_index(date_col)
                fig = trend_plots.create_weekly_dept_chart(period_summary_for_plotting, surgeon_name, {})
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"術者週次推移分析エラー: {e}")

def render():
    SurgeonPage.render()