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
# --- ▼ここから追加▼ ---
from ui.components.period_selector import PeriodSelector
# --- ▲ここまで追加▲ ---

# 既存の分析モジュールをインポート
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots

# 追加の統計分析用ライブラリ（オプション）
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
        """病院全体分析ページを描画"""
        st.title("🏥 病院全体分析 - 詳細分析")

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

        # 週次推移グラフ（複数パターン）
        # 週次サマリーは全期間データから作成し、グラフ側で表示範囲を調整
        full_summary = weekly.get_summary(df, use_complete_weeks=True)
        HospitalPage._render_multiple_trend_patterns(full_summary, target_dict, start_date, end_date)

        # 統計分析セクション
        HospitalPage._render_statistical_analysis(period_df)

        # 期間別比較セクション (この機能は期間選択と重複するため、より詳細な内訳に変更)
        HospitalPage._render_breakdown_analysis(period_df)

        # トレンド分析セクション
        HospitalPage._render_trend_analysis(period_df)
        # --- ▲ここまで修正▲ ---

    @staticmethod
    @safe_data_operation("複数トレンドパターン表示")
    def _render_multiple_trend_patterns(summary: pd.DataFrame, target_dict: Dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        """複数の週次推移パターンを表示"""
        st.subheader("📈 週次推移分析（複数パターン）")

        try:
            if summary.empty:
                st.warning("週次推移データがありません。")
                return

            # 表示期間でサマリーをフィルタリング
            period_summary = summary[(summary.index >= start_date) & (summary.index <= end_date)]
            if period_summary.empty:
                st.warning("選択期間内の週次データがありません。")
                return

            if '平日1日平均件数' not in period_summary.columns:
                st.error("必要なデータ列（平日1日平均件数）が見つかりません。")
                return

            tab1, tab2, tab3 = st.tabs(["📊 標準推移", "📈 移動平均", "🎯 目標比較"])

            with tab1:
                st.markdown("**標準的な週次推移（平日1日平均）**")
                fig1 = trend_plots.create_weekly_summary_chart(period_summary, "病院全体 週次推移", target_dict)
                st.plotly_chart(fig1, use_container_width=True)

            with tab2:
                # 移動平均は全期間のサマリーで計算し、表示を期間で絞る
                if len(summary) >= 4:
                    summary_ma = summary.copy()
                    summary_ma['4週移動平均'] = summary_ma['平日1日平均件数'].rolling(window=4).mean()
                    period_summary_ma = summary_ma.loc[period_summary.index]

                    fig2 = trend_plots.create_weekly_summary_chart(
                        period_summary_ma, "移動平均トレンド（4週移動平均）", target_dict
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("移動平均計算には最低4週間のデータが必要です。")

            with tab3:
                st.markdown("**目標達成率推移**")
                if target_dict:
                    from config.hospital_targets import HospitalTargets
                    hospital_target = HospitalTargets.get_daily_target()

                    summary_target = period_summary.copy()
                    summary_target['達成率(%)'] = (summary_target['平日1日平均件数'] / hospital_target * 100)
                    fig3 = trend_plots.create_weekly_summary_chart(summary_target, "目標達成率推移", target_dict)
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("目標データが設定されていません。")

        except Exception as e:
            st.error(f"週次推移分析エラー: {e}")
            logger.error(f"週次推移分析エラー: {e}")


    @staticmethod
    @safe_data_operation("統計分析表示")
    def _render_statistical_analysis(period_df: pd.DataFrame) -> None:
        """統計分析セクションを表示"""
        st.markdown("---")
        st.subheader("📊 統計分析・パフォーマンス指標")

        try:
            if period_df.empty:
                st.warning("選択期間内に分析対象データがありません。")
                return

            gas_df = period_df[period_df['is_gas_20min'] == True]
            if gas_df.empty:
                st.warning("選択期間内に全身麻酔のデータがありません。")
                return

            # 診療科別統計
            st.markdown("**🏥 診療科別統計分析**")
            dept_stats = HospitalPage._calculate_department_statistics(gas_df)

            if not dept_stats.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**上位5診療科 (件数)**")
                    top5 = dept_stats.head().round(1)
                    st.dataframe(top5, use_container_width=True)
                with col2:
                    st.markdown("**統計サマリー**")
                    st.write(f"• 診療科数: {len(dept_stats)}科")
                    st.write(f"• 平均件数/科: {dept_stats['合計件数'].mean():.1f}件")
                    st.write(f"• 最大差: {dept_stats['合計件数'].max() - dept_stats['合計件数'].min():.1f}件")
            else:
                st.warning("診療科別統計を計算できませんでした。")

            # 時系列統計（機械学習が利用可能な場合）
            if SKLEARN_AVAILABLE:
                HospitalPage._render_advanced_statistics(gas_df)

        except Exception as e:
            st.error(f"統計分析エラー: {e}")
            logger.error(f"統計分析エラー: {e}")

    @staticmethod
    def _calculate_department_statistics(df: pd.DataFrame) -> pd.DataFrame:
        """診療科別統計を計算"""
        # (このメソッドは変更なし)
        try:
            dept_stats = df.groupby('実施診療科').agg({
                '手術実施日_dt': 'count',
                'is_weekday': 'sum'
            }).rename(columns={
                '手術実施日_dt': '合計件数',
                'is_weekday': '平日件数'
            })

            dept_stats['平日割合(%)'] = (dept_stats['平日件数'] / dept_stats['合計件数'] * 100).round(1)
            dept_stats = dept_stats.sort_values('合計件数', ascending=False)

            return dept_stats

        except Exception as e:
            logger.error(f"診療科別統計計算エラー: {e}")
            return pd.DataFrame()

    @staticmethod
    def _render_advanced_statistics(df: pd.DataFrame) -> None:
        """高度統計分析（機械学習を使用）"""
        # (このメソッドは変更なし)
        try:
            st.markdown("**🔬 高度統計分析**")

            # 日次件数の時系列データ準備
            daily_counts = df.groupby('手術実施日_dt').size().reset_index(name='件数')
            daily_counts = daily_counts.sort_values('手術実施日_dt')

            if len(daily_counts) >= 7:
                # 線形回帰でトレンド分析
                X = np.arange(len(daily_counts)).reshape(-1, 1)
                y = daily_counts['件数'].values

                model = LinearRegression()
                model.fit(X, y)

                trend_slope = model.coef_[0]
                r_squared = model.score(X, y)

                col1, col2, col3 = st.columns(3)

                with col1:
                    trend_direction = "上昇" if trend_slope > 0 else "下降"
                    st.metric("📈 トレンド傾向", trend_direction)

                with col2:
                    st.metric("📊 回帰係数", f"{trend_slope:.3f}")

                with col3:
                    st.metric("🎯 決定係数 (R²)", f"{r_squared:.3f}")

                st.caption("💡 決定係数が高いほど、トレンドの予測精度が高くなります")
            else:
                st.info("高度統計分析には最低7日分のデータが必要です。")

        except Exception as e:
            logger.error(f"高度統計分析エラー: {e}")
            st.warning("高度統計分析でエラーが発生しました。")

    @staticmethod
    @safe_data_operation("内訳分析表示")
    def _render_breakdown_analysis(period_df: pd.DataFrame) -> None:
        """内訳分析セクションを表示"""
        st.markdown("---")
        st.subheader("🍰 内訳分析")
        try:
            if period_df.empty:
                st.warning("選択期間内にデータがありません。")
                return

            gas_df = period_df[period_df['is_gas_20min'] == True]
            if gas_df.empty:
                st.warning("選択期間内に全身麻酔のデータがありません。")
                return

            tab1, tab2 = st.tabs(["曜日別", "手術室別"])

            with tab1:
                st.markdown("**曜日別 手術件数**")
                dow_df = gas_df.copy()
                dow_df['曜日'] = dow_df['手術実施日_dt'].dt.day_name()
                dow_analysis = dow_df.groupby('曜日').size().reindex([
                    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
                ]).dropna()
                st.bar_chart(dow_analysis)

            with tab2:
                st.markdown("**手術室別 手術件数 (上位10)**")
                or_df = gas_df.copy()
                if '手術室' in or_df.columns:
                    or_counts = or_df['手術室'].value_counts().head(10)
                    st.bar_chart(or_counts)
                else:
                    st.info("「手術室」列がデータにありません。")
        except Exception as e:
            st.error(f"内訳分析エラー: {e}")
            logger.error(f"内訳分析エラー: {e}")

    @staticmethod
    @safe_data_operation("トレンド分析表示")
    def _render_trend_analysis(period_df: pd.DataFrame) -> None:
        """トレンド分析セクションを表示"""
        # (このメソッドは簡略化・期間対応)
        st.markdown("---")
        st.subheader("🔮 詳細トレンド分析")
        try:
            if period_df.empty:
                st.warning("トレンド分析用データがありません。")
                return

            summary = weekly.get_summary(period_df, use_complete_weeks=True)
            if summary.empty:
                st.warning("週次サマリーデータがありません。")
                return

            HospitalPage._render_basic_trend_analysis(summary)

        except Exception as e:
            st.error(f"トレンド分析エラー: {e}")
            logger.error(f"トレンド分析エラー: {e}")

    @staticmethod
    def _render_basic_trend_analysis(summary: pd.DataFrame) -> None:
        """基本トレンド分析"""
        st.markdown("**📈 基本トレンド指標**")

        if len(summary) < 2:
            st.info("トレンド比較には最低2週間のデータが必要です。")
            return

        # 期間全体の平均と比較
        total_avg = summary['平日1日平均件数'].mean()
        recent_avg = summary.tail(1)['平日1日平均件数'].iloc[0] if len(summary.tail(1)) > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 期間平均", f"{total_avg:.1f}件/日")
        with col2:
            st.metric("📈 直近週実績", f"{recent_avg:.1f}件/日", delta=f"{recent_avg-total_avg:+.1f}件")
        with col3:
            volatility = summary['平日1日平均件数'].std()
            st.metric("📊 変動度 (標準偏差)", f"{volatility:.1f}")

# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    HospitalPage.render()