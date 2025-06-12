# ui/components/period_selector.py
"""
分析期間選択コンポーネント
"""

import streamlit as st
import pandas as pd
from typing import Optional, Tuple
import logging

from ui.session_manager import SessionManager
from analysis import weekly

logger = logging.getLogger(__name__)

class PeriodSelector:
    """分析期間の選択と管理を行う共通コンポーネント"""

    PERIOD_OPTIONS = [
        "直近4週",
        "直近8週",
        "直近12週",
        "今年度",
        "昨年度"
    ]

    @staticmethod
    def render() -> None:
        """期間選択UIを描画し、セッション状態を更新する"""
        st.subheader("📅 分析期間選択")

        latest_date = SessionManager.get_latest_date()
        if not latest_date:
            st.warning("基準となる日付データがありません。")
            return

        # 現在の選択値を取得
        current_period = SessionManager.get_analysis_period()
        try:
            current_index = PeriodSelector.PERIOD_OPTIONS.index(current_period)
        except ValueError:
            current_index = 0

        col1, col2 = st.columns([1, 3])

        with col1:
            selected_period = st.selectbox(
                "分析期間",
                PeriodSelector.PERIOD_OPTIONS,
                index=current_index,
                key="period_selector_selectbox",
                help="分析に使用する期間を選択してください"
            )

        # 期間が変更されたか、または初期化されていない場合に日付を計算・設定
        if selected_period != current_period or SessionManager.get_start_date() is None:
            start_date, end_date = PeriodSelector._calculate_period_dates(selected_period, latest_date)
            if start_date and end_date:
                SessionManager.set_analysis_period(selected_period)
                SessionManager.set_analysis_dates(start_date, end_date)
                # UIを即時更新するために再実行
                st.rerun()

        # 現在選択されている期間情報を表示
        start_date = SessionManager.get_start_date()
        end_date = SessionManager.get_end_date()

        with col2:
            if start_date and end_date:
                st.info(
                    f"📊 **選択期間**: {selected_period}  \n"
                    f"📅 **分析範囲**: {start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}  \n"
                    f"📈 **期間長**: {(end_date - start_date).days + 1}日間"
                )
            else:
                st.error("期間の計算に失敗しました。")

        st.markdown("---")

    @staticmethod
    def _calculate_period_dates(period: str, latest_date: Optional[pd.Timestamp]) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """選択された期間に基づいて開始日・終了日を計算"""
        if not latest_date:
            return None, None

        try:
            # 週単位分析の場合は分析終了日（日曜日）を使用
            if "週" in period:
                analysis_end_date = weekly.get_analysis_end_date(latest_date)
                if not analysis_end_date:
                    return None, None
                end_date = analysis_end_date
            else:
                end_date = latest_date

            if period == "直近4週":
                start_date = end_date - pd.Timedelta(days=27)
            elif period == "直近8週":
                start_date = end_date - pd.Timedelta(days=55)
            elif period == "直近12週":
                start_date = end_date - pd.Timedelta(days=83)
            elif period == "今年度":
                current_year = latest_date.year
                if latest_date.month >= 4:
                    start_date = pd.Timestamp(current_year, 4, 1)
                else:
                    start_date = pd.Timestamp(current_year - 1, 4, 1)
                end_date = latest_date
            elif period == "昨年度":
                current_year = latest_date.year
                if latest_date.month >= 4:
                    start_date = pd.Timestamp(current_year - 1, 4, 1)
                    end_date = pd.Timestamp(current_year, 3, 31)
                else:
                    start_date = pd.Timestamp(current_year - 2, 4, 1)
                    end_date = pd.Timestamp(current_year - 1, 3, 31)
            else:
                return None, None

            return start_date, end_date

        except Exception as e:
            logger.error(f"期間計算エラー: {e}")
            return None, None