# ui/pages/department_page.py
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
# --- ▼ここから追加▼ ---
from ui.components.period_selector import PeriodSelector
# --- ▲ここまで追加▲ ---

# 既存の分析モジュールをインポート
from analysis import weekly, ranking, surgeon
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
        target_dict = SessionManager.get_target_dict()

        # --- ▼ここから修正▼ ---
        # 期間選択UIの表示と期間の取得
        PeriodSelector.render()
        start_date = SessionManager.get_start_date()
        end_date = SessionManager.get_end_date()

        if not all([start_date, end_date]):
            st.error("分析期間が正しく設定されていません。")
            return

        # 選択された期間でデータをフィルタリング
        period_df = df[(df['手術実施日_dt'] >= start_date) & (df['手術実施日_dt'] <= end_date)]

        # 診療科選択
        selected_dept = DepartmentPage._render_department_selector(df) # 診療科リストは全データから
        if not selected_dept:
            return

        # 選択された診療科の期間データを抽出
        dept_period_df = period_df[period_df['実施診療科'] == selected_dept]

        # KPI表示
        DepartmentPage._render_department_kpi(dept_period_df, selected_dept)

        # 週次推移
        # 週次サマリーは全期間の診療科データで作成し、グラフ側で絞る
        dept_full_df = df[df['実施診療科'] == selected_dept]
        DepartmentPage._render_department_trend(dept_full_df, target_dict, selected_dept, start_date, end_date)

        # 詳細分析タブ
        DepartmentPage._render_detailed_analysis_tabs(dept_period_df, selected_dept)
        # --- ▲ここまで修正▲ ---

    @staticmethod
    def _render_department_selector(df: pd.DataFrame) -> Optional[str]:
        """診療科選択UI"""
        # (このメソッドは変更なし)
        departments = sorted(df["実施診療科"].dropna().unique())

        if not departments:
            st.warning("データに診療科情報がありません。")
            return None

        selected_dept = st.selectbox(
            "分析する診療科を選択",
            departments,
            help="分析対象の診療科を選択してください"
        )

        return selected_dept

    @staticmethod
    @safe_data_operation("診療科KPI計算")
    def _render_department_kpi(dept_period_df: pd.DataFrame, dept_name: str) -> None:
        """診療科別KPI表示"""
        st.markdown("---")
        st.subheader(f"📊 {dept_name} の主要指標")
        try:
            if dept_period_df.empty:
                st.warning("選択期間内にこの診療科のデータはありません。")
                return

            total_cases = len(dept_period_df)
            gas_cases = len(dept_period_df[dept_period_df['is_gas_20min']])
            avg_cases = total_cases / ((dept_period_df['手術実施日_dt'].max() - dept_period_df['手術実施日_dt'].min()).days / 7) if not dept_period_df.empty and (dept_period_df['手術実施日_dt'].max() - dept_period_df['手術実施日_dt'].min()).days > 0 else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("総手術件数", f"{total_cases} 件")
            with col2:
                st.metric("全身麻酔件数", f"{gas_cases} 件")
            with col3:
                st.metric("週平均件数", f"{avg_cases:.1f} 件")

        except Exception as e:
            st.error(f"KPI計算エラー: {e}")
            logger.error(f"診療科別KPI計算エラー ({dept_name}): {e}")

    @staticmethod
    @safe_data_operation("診療科別週次推移表示")
    def _render_department_trend(dept_full_df: pd.DataFrame, target_dict: Dict[str, Any],
                               dept_name: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        """診療科別週次推移表示"""
        st.markdown("---")
        st.subheader(f"📈 {dept_name} 週次推移")

        try:
            use_complete_weeks = st.toggle(
                "完全週データで分析",
                True,
                help="週の途中のデータを除外し、完全な週単位で分析します"
            )

            # 全期間でサマリーを計算
            summary = weekly.get_summary(
                dept_full_df,
                use_complete_weeks=use_complete_weeks
            )

            if not summary.empty:
                # 期間でフィルタリングして表示
                period_summary = summary[(summary.index >= start_date) & (summary.index <= end_date)]
                if period_summary.empty:
                    st.warning("選択期間内に表示できる週次データがありません。")
                    return

                fig = trend_plots.create_weekly_dept_chart(period_summary, dept_name, target_dict)
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("📊 統計サマリー (選択期間)"):
                    # (統計サマリーも期間データで計算)
                    st.dataframe(period_summary.describe().transpose().round(2))

            else:
                st.warning(f"{dept_name}の週次データがありません")

        except Exception as e:
            st.error(f"週次推移分析エラー: {e}")
            logger.error(f"診療科別週次推移エラー ({dept_name}): {e}")

    @staticmethod
    def _render_detailed_analysis_tabs(dept_period_df: pd.DataFrame, dept_name: str) -> None:
        """詳細分析タブを表示"""
        st.markdown("---")
        st.header("🔍 詳細分析 (選択期間)")

        if dept_period_df.empty:
            st.warning("選択期間内に詳細分析を行うデータがありません。")
            return

        tab1, tab2, tab3, tab4 = st.tabs(["術者分析", "時間分析", "統計情報", "累積実績"])

        with tab1:
            DepartmentPage._render_surgeon_analysis_tab(dept_period_df, dept_name)
        with tab2:
            DepartmentPage._render_time_analysis_tab(dept_period_df, dept_name)
        with tab3:
            DepartmentPage._render_statistics_tab(dept_period_df, dept_name)
        with tab4:
            DepartmentPage._render_cumulative_tab(dept_period_df, dept_name)

    @staticmethod
    @safe_data_operation("術者分析")
    def _render_surgeon_analysis_tab(dept_period_df: pd.DataFrame, dept_name: str) -> None:
        """術者分析タブ"""
        st.subheader(f"{dept_name} 術者別件数 (Top 15)")
        try:
            with st.spinner("術者データを準備中..."):
                expanded_df = surgeon.get_expanded_surgeon_df(dept_period_df)
                if not expanded_df.empty:
                    surgeon_summary = surgeon.get_surgeon_summary(expanded_df)
                    if not surgeon_summary.empty:
                        fig = generic_plots.plot_surgeon_ranking(surgeon_summary, 15, dept_name)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("分析可能な術者データがありません")
        except Exception as e:
            st.error(f"術者分析エラー: {e}")

    @staticmethod
    @safe_data_operation("時間分析")
    def _render_time_analysis_tab(dept_period_df: pd.DataFrame, dept_name: str) -> None:
        """時間分析タブ"""
        # (このメソッドは期間でフィルタ済みのデータを受け取る以外変更なし)
        st.subheader("曜日・月別 分布")
        try:
            gas_df = dept_period_df[dept_period_df['is_gas_20min']]
            if not gas_df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    weekday_dist = gas_df['手術実施日_dt'].dt.day_name().value_counts()
                    fig_weekday = px.pie(values=weekday_dist.values, names=weekday_dist.index, title="曜日別分布")
                    st.plotly_chart(fig_weekday, use_container_width=True)
                with col2:
                    month_dist = gas_df['手術実施日_dt'].dt.month_name().value_counts()
                    fig_month = px.bar(x=month_dist.index, y=month_dist.values, title="月別分布", labels={'x': '月', 'y': '件数'})
                    st.plotly_chart(fig_month, use_container_width=True)
            else:
                st.info("全身麻酔20分以上の手術データがありません")
        except Exception as e:
            st.error(f"時間分析エラー: {e}")

    @staticmethod
    def _render_statistics_tab(dept_period_df: pd.DataFrame, dept_name: str) -> None:
        """統計情報タブ"""
        # (このメソッドは期間でフィルタ済みのデータを受け取る以外変更なし)
        st.subheader("基本統計")
        try:
            gas_df = dept_period_df[dept_period_df['is_gas_20min']]
            if not gas_df.empty:
                desc_df = gas_df.describe(include='all').transpose()
                st.dataframe(desc_df.astype(str), use_container_width=True)
            else:
                st.info("統計情報を計算するデータがありません")
        except Exception as e:
            st.error(f"統計情報エラー: {e}")

    @staticmethod
    @safe_data_operation("累積実績")
    def _render_cumulative_tab(dept_period_df: pd.DataFrame, dept_name: str) -> None:
        """累積実績タブ"""
        # (このメソッドは期間でフィルタ済みのデータを受け取る以外変更なし)
        st.subheader(f"{dept_name} 今年度 累積実績")
        try:
            target_dict = SessionManager.get_target_dict()
            weekly_target = target_dict.get(dept_name)
            if weekly_target:
                cum_data = ranking.calculate_cumulative_cases(dept_period_df, weekly_target)
                if not cum_data.empty:
                    fig = generic_plots.plot_cumulative_cases_chart(cum_data, f"{dept_name} 累積実績")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("この診療科の目標値が設定されていないため、累積目標は表示できません。")
        except Exception as e:
            st.error(f"累積実績分析エラー: {e}")

# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    DepartmentPage.render()