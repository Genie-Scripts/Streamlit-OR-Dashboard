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

# 既存の分析モジュールをインポート
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots

logger = logging.getLogger(__name__)


class HospitalPage:
    """病院全体分析ページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("病院全体分析ページ描画")
    def render() -> None:
        """病院全体分析ページを描画"""
        st.title("🏥 病院全体分析 (完全週データ)")
        
        # データ取得
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        latest_date = SessionManager.get_latest_date()
        
        # 分析期間情報の表示
        HospitalPage._render_analysis_period_info(df, latest_date)
        
        # 診療科別パフォーマンスダッシュボード
        HospitalPage._render_performance_dashboard(df, target_dict, latest_date)
        
        # 週次推移グラフ
        HospitalPage._render_weekly_trend_section(df, target_dict)
    
    @staticmethod
    @safe_data_operation("分析期間情報表示")
    def _render_analysis_period_info(df: pd.DataFrame, latest_date: Optional[pd.Timestamp]) -> None:
        """分析期間情報を表示"""
        if latest_date is None:
            st.warning("分析可能な日付データがありません。")
            return
        
        analysis_end_sunday = weekly.get_analysis_end_date(latest_date)
        if analysis_end_sunday is None:
            st.warning("分析可能な日付データがありません。")
            return
        
        excluded_days = (latest_date - analysis_end_sunday).days
        df_complete_weeks = df[df['手術実施日_dt'] <= analysis_end_sunday]
        total_records = len(df_complete_weeks)
        
        # メトリクス表示
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 総レコード数", f"{total_records:,}件")
        with col2:
            st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d'))
        with col3:
            st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d'))
        with col4:
            st.metric("⚠️ 除外日数", f"{excluded_days}日")
        
        st.caption(
            f"💡 最新データが{latest_date.strftime('%A')}のため、"
            f"分析精度向上のため前の日曜日({analysis_end_sunday.strftime('%Y/%m/%d')})までを分析対象としています。"
        )
        st.markdown("---")
    
    @staticmethod
    @safe_data_operation("パフォーマンスダッシュボード表示")
    def _render_performance_dashboard(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                    latest_date: Optional[pd.Timestamp]) -> None:
        """診療科別パフォーマンスダッシュボードを表示"""
        st.subheader("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
        
        if latest_date:
            analysis_end_sunday = weekly.get_analysis_end_date(latest_date)
            if analysis_end_sunday:
                four_weeks_ago = analysis_end_sunday - pd.Timedelta(days=27)
                st.caption(f"🗓️ 分析対象期間: {four_weeks_ago.strftime('%Y/%m/%d')} ~ {analysis_end_sunday.strftime('%Y/%m/%d')}")
        
        # パフォーマンスサマリーを取得
        try:
            perf_summary = ranking.get_department_performance_summary(df, target_dict, latest_date)
            
            if not perf_summary.empty:
                if '達成率(%)' not in perf_summary.columns:
                    st.warning("パフォーマンスデータに達成率の列が見つかりません。")
                    return
                
                # 達成率順にソート
                sorted_perf = perf_summary.sort_values("達成率(%)", ascending=False)
                
                # パフォーマンスカードの表示
                HospitalPage._render_performance_cards(sorted_perf)
                
                # 詳細データテーブル
                with st.expander("詳細データテーブル"):
                    st.dataframe(sorted_perf, use_container_width=True)
            else:
                st.info("診療科別パフォーマンスを計算する十分なデータがありません。")
                
        except Exception as e:
            st.error(f"パフォーマンス計算エラー: {e}")
            logger.error(f"パフォーマンス計算エラー: {e}")
    
    @staticmethod
    def _render_performance_cards(sorted_perf: pd.DataFrame) -> None:
        """パフォーマンスカードを表示"""
        def get_color_for_rate(rate):
            if rate >= 100:
                return "#28a745"
            if rate >= 80:
                return "#ffc107"
            return "#dc3545"
        
        cols = st.columns(3)
        for i, (idx, row) in enumerate(sorted_perf.iterrows()):
            with cols[i % 3]:
                rate = row["達成率(%)"]
                color = get_color_for_rate(rate)
                bar_width = min(rate, 100)
                
                html = f"""
                <div style="
                    background-color: {color}1A; 
                    border-left: 5px solid {color}; 
                    padding: 12px; 
                    border-radius: 5px; 
                    margin-bottom: 12px; 
                    height: 165px;
                ">
                    <h5 style="margin: 0 0 10px 0; font-weight: bold; color: #333;">{row["診療科"]}</h5>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <span>4週平均:</span>
                        <span style="font-weight: bold;">{row["4週平均"]:.1f} 件</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <span>直近週実績:</span>
                        <span style="font-weight: bold;">{row["直近週実績"]:.0f} 件</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #666;">
                        <span>目標:</span>
                        <span>{row["週次目標"]:.1f} 件</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 1.1em; color: {color}; margin-top: 5px;">
                        <span style="font-weight: bold;">達成率:</span>
                        <span style="font-weight: bold;">{rate:.1f}%</span>
                    </div>
                    <div style="background-color: #e9ecef; border-radius: 5px; height: 6px; margin-top: 5px;">
                        <div style="width: {bar_width}%; background-color: {color}; height: 6px; border-radius: 5px;"></div>
                    </div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)
    
    @staticmethod
    @safe_data_operation("週次推移表示")
    def _render_weekly_trend_section(df: pd.DataFrame, target_dict: Dict[str, Any]) -> None:
        """週次推移セクションを表示"""
        st.markdown("---")
        st.subheader("📈 全身麻酔手術件数 週次推移（完全週データ）")
        
        try:
            summary = weekly.get_summary(df, use_complete_weeks=True)
            
            if not summary.empty:
                fig = trend_plots.create_weekly_summary_chart(summary, "", target_dict)
                st.plotly_chart(fig, use_container_width=True)
                
                # 統計情報
                with st.expander("📊 統計情報"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**基本統計:**")
                        st.write(f"• 週数: {len(summary)}週")
                        st.write(f"• 最大値: {summary['平日1日平均件数'].max():.1f}件/日")
                        st.write(f"• 最小値: {summary['平日1日平均件数'].min():.1f}件/日")
                        st.write(f"• 平均値: {summary['平日1日平均件数'].mean():.1f}件/日")
                    
                    with col2:
                        st.write("**トレンド分析:**")
                        if len(summary) >= 2:
                            recent_avg = summary.tail(4)['平日1日平均件数'].mean()
                            earlier_avg = summary.head(4)['平日1日平均件数'].mean()
                            trend = "上昇" if recent_avg > earlier_avg else "下降"
                            st.write(f"• 直近トレンド: {trend}")
                            st.write(f"• 変化率: {((recent_avg/earlier_avg - 1)*100):+.1f}%")
            else:
                st.warning("週次トレンドデータがありません")
                
        except Exception as e:
            st.error(f"週次推移分析エラー: {e}")
            logger.error(f"週次推移分析エラー: {e}")


# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    HospitalPage.render()