# ui/pages/hospital_page.py
"""
病院全体分析ページモジュール
病院全体のパフォーマンス分析を表示
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
from ui.components.period_selector import PeriodSelector

from analysis import weekly, ranking
from plotting import trend_plots, generic_plots

try:
    from sklearn.linear_model import LinearRegression
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class HospitalPage:
    """病院全体分析ページクラス"""

    @staticmethod
    @safe_streamlit_operation("病院全体分析ページ描画")
    def render() -> None:
        st.title("🏥 病院全体分析 - 詳細分析")
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()

        PeriodSelector.render()
        start_date = SessionManager.get_start_date()
        end_date = SessionManager.get_end_date()

        if not all([start_date, end_date]):
            st.error("分析期間が正しく設定されていません。"); return

        period_df = df[(df['手術実施日_dt'] >= start_date) & (df['手術実施日_dt'] <= end_date)]
        full_summary = weekly.get_summary(df, use_complete_weeks=True)

        HospitalPage._render_multiple_trend_patterns(full_summary, target_dict, start_date, end_date)
        HospitalPage._render_statistical_analysis(period_df)
        HospitalPage._render_breakdown_analysis(period_df)

    @staticmethod
    @safe_data_operation("複数トレンドパターン表示")
    def _render_multiple_trend_patterns(summary: pd.DataFrame, target_dict: Dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        st.subheader("📈 週次推移分析（複数パターン）")
        try:
            if summary.empty:
                st.warning("週次推移データがありません。"); return

            # --- ▼ここからが最終修正箇所▼ ---
            # 堅牢な日付列の特定とフィルタリング
            date_col = None
            summary_for_filter = summary.copy()

            # 1. インデックスが日付型かチェック
            if pd.api.types.is_datetime64_any_dtype(summary_for_filter.index):
                summary_for_filter.index.name = '週' # 念のため名前を統一
                summary_with_date_col = summary_for_filter.reset_index()
                date_col = '週'
            else:
                # 2. インデックスが日付でなければ、列から日付型を探す
                for col in summary_for_filter.columns:
                    if pd.api.types.is_datetime64_any_dtype(summary_for_filter[col]):
                        date_col = col
                        break
                summary_with_date_col = summary_for_filter

            if date_col is None:
                st.error("週次サマリーに日付情報が見つかりませんでした。"); return

            period_summary_df = summary_with_date_col[
                (summary_with_date_col[date_col] >= start_date) & 
                (summary_with_date_col[date_col] <= end_date)
            ]
            # --- ▲ここまで▲ ---
            
            if period_summary_df.empty:
                st.warning("選択期間内の週次データがありません。"); return
            
            period_summary_for_plotting = period_summary_df.set_index(date_col)

            tab1, tab2, tab3 = st.tabs(["📊 標準推移", "📈 移動平均", "🎯 目標比較"])
            # (以降のタブ内ロジックは変更なし)
            with tab1:
                st.markdown("**標準的な週次推移（平日1日平均）**")
                fig1 = trend_plots.create_weekly_summary_chart(period_summary_for_plotting, "病院全体 週次推移", target_dict)
                st.plotly_chart(fig1, use_container_width=True)
            with tab2:
                st.markdown("**移動平均トレンド（4週移動平均）**")
                if len(period_summary_for_plotting) >= 4:
                    summary_ma = period_summary_for_plotting.copy()
                    summary_ma['4週移動平均'] = summary_ma['平日1日平均件数'].rolling(window=4).mean()
                    fig2 = trend_plots.create_weekly_summary_chart(summary_ma, "移動平均トレンド", target_dict)
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("移動平均計算には選択期間内に最低4週間のデータが必要です。")
            with tab3:
                st.markdown("**目標達成率推移**")
                if target_dict:
                    from config.hospital_targets import HospitalTargets
                    hospital_target = HospitalTargets.get_daily_target()
                    summary_target = period_summary_for_plotting.copy()
                    summary_target['達成率(%)'] = (summary_target['平日1日平均件数'] / hospital_target * 100)
                    fig3 = trend_plots.create_weekly_summary_chart(summary_target, "目標達成率推移", target_dict)
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("目標データが設定されていません。")
        except Exception as e:
            st.error(f"週次推移分析エラー: {e}"); logger.error(f"週次推移分析エラー: {e}")

    # (以降のメソッドは変更なし)
    @staticmethod
    @safe_data_operation("統計分析表示")
    def _render_statistical_analysis(period_df: pd.DataFrame) -> None:
        st.markdown("---"); st.subheader("📊 統計分析・パフォーマンス指標")
        try:
            if period_df.empty: st.warning("選択期間内に分析対象データがありません。"); return
            gas_df = period_df[period_df['is_gas_20min'] == True]
            if gas_df.empty: st.warning("選択期間内に全身麻酔のデータがありません。"); return
            st.markdown("**🏥 診療科別統計分析**")
            dept_stats = HospitalPage._calculate_department_statistics(gas_df)
            if not dept_stats.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**上位5診療科 (件数)**"); st.dataframe(dept_stats.head().round(1), use_container_width=True)
                with col2:
                    st.markdown("**統計サマリー**")
                    st.write(f"• 診療科数: {len(dept_stats)}科")
                    st.write(f"• 平均件数/科: {dept_stats['合計件数'].mean():.1f}件")
            if SKLEARN_AVAILABLE:
                HospitalPage._render_advanced_statistics(gas_df)
        except Exception as e:
            st.error(f"統計分析エラー: {e}"); logger.error(f"統計分析エラー: {e}")

    @staticmethod
    def _calculate_department_statistics(df: pd.DataFrame) -> pd.DataFrame:
        try:
            dept_stats = df.groupby('実施診療科').agg({'手術実施日_dt': 'count', 'is_weekday': 'sum'}).rename(columns={'手術実施日_dt': '合計件数', 'is_weekday': '平日件数'})
            dept_stats['平日割合(%)'] = (dept_stats['平日件数'] / dept_stats['合計件数'] * 100).round(1)
            return dept_stats.sort_values('合計件数', ascending=False)
        except Exception as e:
            logger.error(f"診療科別統計計算エラー: {e}"); return pd.DataFrame()

    @staticmethod
    def _render_advanced_statistics(df: pd.DataFrame) -> None:
        st.markdown("**🔬 高度統計分析**")
        daily_counts = df.groupby('手術実施日_dt').size().reset_index(name='件数').sort_values('手術実施日_dt')
        if len(daily_counts) >= 7:
            X = np.arange(len(daily_counts)).reshape(-1, 1); y = daily_counts['件数'].values
            model = LinearRegression().fit(X, y)
            col1, col2, col3 = st.columns(3)
            col1.metric("📈 トレンド傾向", "上昇" if model.coef_[0] > 0 else "下降")
            col2.metric("📊 回帰係数", f"{model.coef_[0]:.3f}")
            col3.metric("🎯 決定係数 (R²)", f"{model.score(X, y):.3f}")
        else:
            st.info("高度統計分析には最低7日分のデータが必要です。")

    @staticmethod
    @safe_data_operation("内訳分析表示")
    def _render_breakdown_analysis(period_df: pd.DataFrame) -> None:
        st.markdown("---"); st.subheader("🍰 内訳分析")
        try:
            if period_df.empty: st.warning("選択期間内にデータがありません。"); return
            gas_df = period_df[period_df['is_gas_20min'] == True]
            if gas_df.empty: st.warning("選択期間内に全身麻酔のデータがありません。"); return
            tab1, tab2 = st.tabs(["曜日別", "手術室別"])
            with tab1:
                st.markdown("**曜日別 手術件数**")
                dow_analysis = gas_df['手術実施日_dt'].dt.day_name().value_counts().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']).dropna()
                st.bar_chart(dow_analysis)
            with tab2:
                st.markdown("**手術室別 手術件数 (上位10)**")
                if '手術室' in gas_df.columns:
                    st.bar_chart(gas_df['手術室'].value_counts().head(10))
                else:
                    st.info("「手術室」列がデータにありません。")
        except Exception as e:
            st.error(f"内訳分析エラー: {e}"); logger.error(f"内訳分析エラー: {e}")

def render():
    HospitalPage.render()