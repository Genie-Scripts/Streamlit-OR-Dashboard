# ui/pages/dashboard_page.py
"""
ダッシュボードページモジュール
メインダッシュボードの表示を管理
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
# コンポーネントは一時的にコメントアウト
# from ui.components.kpi_display import KPIDisplay
# from ui.components.chart_container import ChartContainer

# 既存の分析モジュールをインポート
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots
from utils import date_helpers

logger = logging.getLogger(__name__)


class DashboardPage:
    """ダッシュボードページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("ダッシュボードページ描画")
    def render() -> None:
        """ダッシュボードページを描画"""
        st.title("📱 ダッシュボード - 管理者向けサマリー")
        
        # データ取得
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        latest_date = SessionManager.get_latest_date()
        
        if df.empty:
            DashboardPage._render_no_data_dashboard()
            return
        
        # 分析期間情報
        DashboardPage._render_analysis_period_info(latest_date)
        
        # 主要指標セクション
        DashboardPage._render_kpi_section(df, latest_date)
        
        # 診療科別パフォーマンスダッシュボード
        DashboardPage._render_performance_dashboard(df, target_dict, latest_date)
        
        # 目標達成状況サマリー  
        DashboardPage._render_achievement_summary(df, target_dict, latest_date)
    
    @staticmethod
    def _render_no_data_dashboard() -> None:
        """データなし時のダッシュボード"""
        st.info("📊 ダッシュボードを表示するにはデータが必要です")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🚀 はじめに
            
            手術分析ダッシュボードへようこそ！
            
            **主な機能:**
            - 📈 リアルタイム手術実績分析
            - 🏆 診療科別ランキング
            - 👨‍⚕️ 術者別パフォーマンス分析
            - 🔮 将来予測とトレンド分析
            """)
        
        with col2:
            st.markdown("""
            ### 📋 次のステップ
            
            1. **データアップロード**で手術データを読み込み
            2. **目標データ**を設定（オプション）
            3. **分析開始** - 各種レポートを確認
            
            **対応形式:** CSV形式の手術データ
            """)
        
        # クイックアクション
        st.markdown("---")
        st.subheader("⚡ クイックアクション")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📤 データアップロード", type="primary", use_container_width=True):
                SessionManager.set_current_view("データアップロード")
                st.rerun()
        
        with col2:
            if st.button("💾 データ管理", use_container_width=True):
                SessionManager.set_current_view("データ管理")
                st.rerun()
        
        with col3:
            if st.button("📖 ヘルプ", use_container_width=True):
                DashboardPage._show_help_dialog()
    
    @staticmethod
    @safe_data_operation("KPI計算")
    def _render_kpi_section(df: pd.DataFrame, latest_date: Optional[pd.Timestamp]) -> None:
        """KPIセクションを描画"""
        st.header("📊 主要指標 (直近4週間)")
        
        try:
            # KPIサマリーを計算
            kpi_summary = ranking.get_kpi_summary(df, latest_date)
            
            # 一時的に直接表示
            # KPIDisplay.render_kpi_metrics(kpi_summary)
            generic_plots.display_kpi_metrics(kpi_summary)
            
        except Exception as e:
            logger.error(f"KPI計算エラー: {e}")
            st.error("KPI計算中にエラーが発生しました")
    
    @staticmethod
    def _render_analysis_period_info(latest_date: Optional[pd.Timestamp]) -> None:
        """分析期間情報を表示"""
        if not latest_date:
            return
            
        # 週単位分析の説明
        analysis_end_date = weekly.get_analysis_end_date(latest_date)
        
        if analysis_end_date:
            four_weeks_ago = analysis_end_date - pd.Timedelta(days=27)
            twelve_weeks_ago = analysis_end_date - pd.Timedelta(days=83)
            
            st.info(
                f"📊 **完全週単位分析** - 月曜日起算の完全な週データで分析  \n"
                f"📅 KPI期間: {four_weeks_ago.strftime('%Y/%m/%d')} ～ {analysis_end_date.strftime('%Y/%m/%d')} (直近4週)  \n"
                f"📈 ランキング期間: {twelve_weeks_ago.strftime('%Y/%m/%d')} ～ {analysis_end_date.strftime('%Y/%m/%d')} (直近12週)"
            )
    
    @staticmethod
    @safe_data_operation("パフォーマンスダッシュボード表示")
    def _render_performance_dashboard(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                    latest_date: Optional[pd.Timestamp]) -> None:
        """診療科別パフォーマンスダッシュボードを表示"""
        st.markdown("---")
        st.header("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
        
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
                DashboardPage._render_performance_cards(sorted_perf)
                
                # 詳細データテーブル
                with st.expander("📋 詳細データテーブル"):
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
    @safe_data_operation("目標達成状況サマリー")
    def _render_achievement_summary(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                  latest_date: Optional[pd.Timestamp]) -> None:
        """目標達成状況サマリーを表示"""
        st.markdown("---")
        st.header("🎯 目標達成状況サマリー")
        
        try:
            # 病院全体の目標達成状況
            from config.hospital_targets import HospitalTargets
            
            # 直近4週の平均実績を計算
            if latest_date:
                analysis_end_date = weekly.get_analysis_end_date(latest_date)
                if analysis_end_date:
                    four_weeks_ago = analysis_end_date - pd.Timedelta(days=27)
                    recent_df = df[
                        (df['手術実施日_dt'] >= four_weeks_ago) & 
                        (df['手術実施日_dt'] <= analysis_end_date) &
                        (df['is_gas_20min'] == True)
                    ]
                    
                    if not recent_df.empty:
                        # 平日のみの日次平均を計算
                        weekday_df = recent_df[recent_df['is_weekday']]
                        if not weekday_df.empty:
                            total_days = (analysis_end_date - four_weeks_ago).days + 1
                            weekdays = sum(1 for i in range(total_days) 
                                         if (four_weeks_ago + pd.Timedelta(days=i)).weekday() < 5)
                            daily_avg = len(weekday_df) / weekdays if weekdays > 0 else 0
                            
                            hospital_target = HospitalTargets.get_daily_target()
                            achievement_rate = (daily_avg / hospital_target * 100) if hospital_target > 0 else 0
                            
                            # サマリーカード表示
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric(
                                    "🏥 病院全体達成率", 
                                    f"{achievement_rate:.1f}%",
                                    delta=f"{achievement_rate - 100:.1f}%" if achievement_rate != 100 else "目標達成"
                                )
                            
                            with col2:
                                st.metric(
                                    "📊 実績 (平日平均)", 
                                    f"{daily_avg:.1f}件/日",
                                    delta=f"{daily_avg - hospital_target:+.1f}件"
                                )
                            
                            with col3:
                                st.metric("🎯 目標", f"{hospital_target}件/日")
                            
                            with col4:
                                dept_count = len([k for k, v in target_dict.items() if v > 0]) if target_dict else 0
                                st.metric("📋 目標設定診療科", f"{dept_count}科")
                            
                            # 診療科別達成状況サマリー
                            if target_dict:
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.subheader("📈 診療科別達成状況")
                                    ranking_data = ranking.calculate_achievement_rates(recent_df, target_dict)
                                    
                                    if not ranking_data.empty:
                                        # TOP3とWORST3を表示
                                        top3 = ranking_data.head(3)
                                        st.write("**🏆 TOP 3:**")
                                        for idx, row in top3.iterrows():
                                            st.write(f"• {row['診療科']}: {row['達成率(%)']:.1f}%")
                                
                                with col2:
                                    if len(ranking_data) >= 3:
                                        st.subheader("📉 要注意診療科")
                                        bottom3 = ranking_data.tail(3)
                                        st.write("**⚠️ 達成率が低い科:**")
                                        for idx, row in bottom3.iterrows():
                                            if row['達成率(%)'] < 80:
                                                st.write(f"• {row['診療科']}: {row['達成率(%)']:.1f}%")
                                        
                                        # 改善アクション提案
                                        low_performers = ranking_data[ranking_data['達成率(%)'] < 80]
                                        if not low_performers.empty:
                                            st.write("**💡 推奨アクション:**")
                                            st.write("• 個別面談実施")
                                            st.write("• リソース配分見直し")
                                            st.write("• 詳細分析実施")
                        else:
                            st.info("平日データが不足しています")
                    else:
                        st.info("直近4週間のデータがありません")
                else:
                    st.info("分析期間を設定できませんでした")
            else:
                st.info("最新日付データがありません")
                
        except Exception as e:
            st.error(f"目標達成状況計算エラー: {e}")
            logger.error(f"目標達成状況計算エラー: {e}")
    
    @staticmethod
    def _render_analysis_info(latest_date: Optional[pd.Timestamp]) -> None:
        """分析情報セクションを描画"""
        if not latest_date:
            return
        
        # 週単位分析の説明
        analysis_end_date = weekly.get_analysis_end_date(latest_date)
        
        if analysis_end_date:
            four_weeks_ago = analysis_end_date - pd.Timedelta(days=27)
            twelve_weeks_ago = analysis_end_date - pd.Timedelta(days=83)
            
            st.info(
                f"📊 **完全週単位分析** - 月曜日起算の完全な週データで分析  \n"
                f"📅 KPI期間: {four_weeks_ago.strftime('%Y/%m/%d')} ～ {analysis_end_date.strftime('%Y/%m/%d')} (直近4週)  \n"
                f"📈 ランキング期間: {twelve_weeks_ago.strftime('%Y/%m/%d')} ～ {analysis_end_date.strftime('%Y/%m/%d')} (直近12週)"
            )
    
    @staticmethod
    @safe_data_operation("週次トレンド分析")
    def _render_weekly_trend(df: pd.DataFrame, target_dict: Dict[str, Any]) -> None:
        """週次トレンドセクションを描画"""
        st.header("📈 病院全体 週次トレンド")
        
        # 完全週データオプション
        use_complete_weeks = st.toggle(
            "完全週データで分析", 
            value=True, 
            help="週の途中のデータを分析から除外し、月曜〜日曜の完全な週単位で集計します。"
        )
        
        try:
            # 週次サマリーを取得
            summary = weekly.get_summary(df, use_complete_weeks=use_complete_weeks)
            
            if not summary.empty:
                # チャートを作成
                fig = trend_plots.create_weekly_summary_chart(
                    summary, "病院全体 週次推移", target_dict
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("週次トレンドデータがありません")
                
        except Exception as e:
            logger.error(f"週次トレンド分析エラー: {e}")
            st.error("週次トレンド分析中にエラーが発生しました")
    
    @staticmethod
    @safe_data_operation("ランキング分析")
    def _render_ranking_section(df: pd.DataFrame, target_dict: Dict[str, Any], 
                               latest_date: Optional[pd.Timestamp]) -> None:
        """ランキングセクションを描画"""
        st.header("🏆 診療科別ランキング (直近12週)")
        
        if not target_dict:
            st.info("目標データをアップロードするとランキングが表示されます。")
            
            # 目標データアップロードへのリンク
            if st.button("🎯 目標データを設定"):
                SessionManager.set_current_view("データアップロード")
                st.rerun()
            return
        
        try:
            # 分析終了日を取得
            analysis_end_date = weekly.get_analysis_end_date(latest_date)
            
            if analysis_end_date:
                # 直近12週間のデータでランキング計算
                twelve_weeks_ago = analysis_end_date - pd.Timedelta(days=83)  # 12週間 - 1日
                filtered_df = df[
                    (df['手術実施日_dt'] >= twelve_weeks_ago) & 
                    (df['手術実施日_dt'] <= analysis_end_date)
                ]
            else:
                # フォールバック：従来の方法
                filtered_df = date_helpers.filter_by_period(df, latest_date, "直近90日")
            
            # ランキングデータを計算
            ranking_data = ranking.calculate_achievement_rates(filtered_df, target_dict)
            
            if not ranking_data.empty:
                # ランキングチャートを作成
                fig_rank = generic_plots.plot_achievement_ranking(ranking_data)
                
                # 一時的に直接表示
                # ChartContainer.render_chart(
                #     fig_rank,
                #     title="診療科別達成率ランキング",
                #     help_text="直近12週間の目標達成率ランキングです"
                # )
                st.plotly_chart(fig_rank, use_container_width=True)
                
                # 期間情報の表示
                st.caption(
                    f"📊 分析期間: {len(filtered_df)}件のデータ "
                    f"({filtered_df['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ "
                    f"{filtered_df['手術実施日_dt'].max().strftime('%Y/%m/%d')})"
                )
                
                # 詳細データテーブル（オプション）
                with st.expander("📋 詳細ランキングデータ"):
                    st.dataframe(
                        ranking_data.round(2),
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.warning("ランキングデータを計算できませんでした")
                
        except Exception as e:
            logger.error(f"ランキング分析エラー: {e}")
            st.error("ランキング分析中にエラーが発生しました")
    
    @staticmethod
    def _show_help_dialog() -> None:
        """ヘルプダイアログを表示"""
        with st.expander("📖 ダッシュボードの使い方", expanded=True):
            st.markdown("""
            ### 🏠 ダッシュボード概要
            
            ダッシュボードは手術分析の中心となるページです。
            
            #### 📊 主要指標 (KPI)
            - **総手術件数**: 全身麻酔手術の総件数
            - **週平均**: 週あたりの平均手術件数
            - **目標達成率**: 設定された目標に対する達成率
            - **前週比**: 前週との比較増減
            
            #### 📈 週次トレンド
            - 時系列での手術件数推移
            - 完全週データ（月-日）での正確な分析
            - 目標値との比較
            
            #### 🏆 診療科別ランキング
            - 目標達成率順のランキング
            - 直近12週間のパフォーマンス評価
            - 診療科間の比較分析
            
            #### 🚀 次のアクション
            - **病院全体分析**: より詳細な全体分析
            - **診療科別分析**: 特定診療科の深掘り分析
            - **術者分析**: 個別術者のパフォーマンス
            - **将来予測**: 将来のトレンド予測
            """)
    
    @staticmethod
    def get_dashboard_summary() -> Dict[str, Any]:
        """ダッシュボードサマリー情報を取得"""
        try:
            df = SessionManager.get_processed_df()
            target_dict = SessionManager.get_target_dict()
            latest_date = SessionManager.get_latest_date()
            
            if df.empty:
                return {"status": "no_data"}
            
            # 基本統計
            total_records = len(df)
            gas_records = len(df[df['is_gas_20min']]) if 'is_gas_20min' in df.columns else 0
            departments = len(df['実施診療科'].dropna().unique()) if '実施診療科' in df.columns else 0
            
            return {
                "status": "active",
                "total_records": total_records,
                "gas_records": gas_records,
                "departments": departments,
                "has_targets": bool(target_dict),
                "target_count": len(target_dict),
                "latest_date": latest_date.strftime('%Y/%m/%d') if latest_date else None,
                "data_range_days": (latest_date - df['手術実施日_dt'].min()).days if latest_date and '手術実施日_dt' in df.columns else None
            }
            
        except Exception as e:
            logger.error(f"ダッシュボードサマリー取得エラー: {e}")
            return {"status": "error", "message": str(e)}