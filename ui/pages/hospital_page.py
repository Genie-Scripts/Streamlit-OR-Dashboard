# ui/pages/hospital_page.py
"""
病院全体分析ページモジュール
病院全体のパフォーマンス分析を表示
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from io import StringIO
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
from ui.components.period_selector import PeriodSelector

from analysis import weekly
from plotting import trend_plots

logger = logging.getLogger(__name__)


class HospitalPage:
    """病院全体分析ページクラス"""

    @staticmethod
    @safe_streamlit_operation("病院全体分析ページ描画")
    def render() -> None:
        st.title("🏥 病院全体分析 - 詳細分析")

        df = SessionManager.get_processed_df()
        if df.empty:
            st.warning("分析するデータがありません。")
            return

        # --- ▼最重要デバッグコード▼ ---
        # weekly.get_summaryの戻り値を直接確認します
        st.markdown("---")
        st.subheader("🐞【最重要デバッグ情報】🐞")
        st.write("`weekly.get_summary()` が返した生の `summary` データフレームの構造です。")
        st.write("お手数ですが、この枠内の情報をすべてコピーしてご提供ください。")
        
        try:
            summary_for_debug = weekly.get_summary(df, use_complete_weeks=True)
            if not summary_for_debug.empty:
                st.write("**1. データフレームの先頭5行 (`summary.head()`):**")
                st.dataframe(summary_for_debug.head())

                st.write("**2. データフレームのインデックス (`summary.index`):**")
                st.write(summary_for_debug.index)

                st.write("**3. データフレームのカラム一覧 (`summary.columns`):**")
                st.write(summary_for_debug.columns.to_list())

                buffer = StringIO()
                summary_for_debug.info(buf=buffer)
                s = buffer.getvalue()
                st.write("**4. データフレーム情報 (`summary.info()`):**")
                st.text(s)
            else:
                st.warning("デバッグ用の週次サマリーデータが空です。")
        except Exception as e:
            st.error(f"デバッグ情報生成中にエラーが発生しました: {e}")
        
        st.markdown("---", help="デバッグはここまで")
        # --- ▲最重要デバッグコード▲ ---
        
        # 期間選択と後続の処理（エラーが出てもデバッグ情報は表示されるように）
        try:
            target_dict = SessionManager.get_target_dict()
            PeriodSelector.render()
            start_date = SessionManager.get_start_date()
            end_date = SessionManager.get_end_date()

            if not all([start_date, end_date]):
                st.error("分析期間が正しく設定されていません。"); return

            period_df = df[(df['手術実施日_dt'] >= start_date) & (df['手術実施日_dt'] <= end_date)]
            full_summary = weekly.get_summary(df, use_complete_weeks=True)
            
            # デバッグ情報表示後は、エラーが出てもアプリが停止しないようにする
            if not full_summary.empty:
                HospitalPage._render_multiple_trend_patterns(full_summary, target_dict, start_date, end_date)
            
            HospitalPage._render_statistical_analysis(period_df)
            HospitalPage._render_breakdown_analysis(period_df)

        except Exception as e:
             st.error(f"ページ描画中にエラーが発生しました: {e}")


    @staticmethod
    @safe_data_operation("複数トレンドパターン表示")
    def _render_multiple_trend_patterns(summary: pd.DataFrame, target_dict: Dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        st.subheader("📈 週次推移分析（複数パターン）")
        
        # ★★★ ここに以前の修正コードがありますが、一旦デバッグ情報取得を優先します ★★★
        st.info("現在、根本原因調査のためグラフ表示を一時停止しています。上記のデバッグ情報をご提供ください。")
        

    # (以降のメソッドは修正の影響を受けないため、簡略化のため省略)
    @staticmethod
    def _render_statistical_analysis(period_df: pd.DataFrame) -> None:
        pass

    @staticmethod
    def _render_breakdown_analysis(period_df: pd.DataFrame) -> None:
        pass


def render():
    HospitalPage.render()