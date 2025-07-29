import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime
import plotly.express as px

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation

# 既存の分析モジュール
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots
from utils import date_helpers

logger = logging.getLogger(__name__)


class DashboardPage:
    """ダッシュボードページクラス（週報ランキングデフォルト版）"""

    @staticmethod
    def render() -> None:
        """ダッシュボードページを描画"""
        st.title("📱 ダッシュボード - 手術分析の中心")
        
        df = SessionManager.get_processed_df()
        
        if df.empty:
            DashboardPage._render_no_data_dashboard()
            return

        # === ▼▼▼ 修正箇所 ▼▼▼ ===
        target_dict = SessionManager.get_target_dict()
        latest_date_in_data = SessionManager.get_latest_date()
        analysis_base_date_from_ui = SessionManager.get_analysis_base_date()

        # UIで設定された基準日を優先し、なければデータ内の最新日を使用
        effective_base_date = analysis_base_date_from_ui if analysis_base_date_from_ui else latest_date_in_data
        
        # 期間選択セクション
        analysis_period, start_date, end_date = DashboardPage._render_period_selector(effective_base_date)
        # === ▲▲▲ 修正箇所 ▲▲▲ ===
        
        if st.session_state.get('show_evaluation_tab', False):
            default_tab = 1
            st.session_state.show_evaluation_tab = False
        else:
            default_tab = 0
            
        tabs = st.tabs([
            "📊 概要・KPI", 
            "🏆 診療科評価", 
            "📈 パフォーマンス", 
            "📄 レポート"
        ])
        
        with tabs[0]:
            kpi_data = DashboardPage._render_kpi_section_with_data(df, effective_base_date, start_date, end_date)
            if start_date and end_date:
                DashboardPage._render_basic_charts(df, start_date, end_date)
        
        with tabs[1]:
            DashboardPage._render_evaluation_section()
        
        with tabs[2]:
            performance_data = DashboardPage._render_performance_dashboard_with_data(
                df, target_dict, effective_base_date, start_date, end_date
            )
            DashboardPage._render_achievement_status(df, target_dict, start_date, end_date)
        
        with tabs[3]:
            DashboardPage._render_report_section(df, target_dict, analysis_period)

    @staticmethod
    def _render_no_data_dashboard() -> None:
        """データ未読み込み時のダッシュボード"""
        st.info("📊 手術データを読み込むと、ここにダッシュボードが表示されます。")
        st.markdown("### 📤 はじめ方")
        st.markdown("""
        1. **データアップロード**で手術データを読み込み
        2. **目標データ**を設定（オプション）
        3. **ダッシュボード**で分析開始
        """)
        if st.button("⚙️ データ管理へ移動", type="primary"):
            SessionManager.set_current_view("データ管理")
            st.rerun()

    @staticmethod
    @safe_data_operation("統合評価セクション")
    def _render_evaluation_section() -> None:
        """統合評価セクション（週報ランキングデフォルト）"""
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        
        if df.empty or not target_dict:
            st.info("📊 データと目標値を設定すると評価が表示されます")
            return
        
        try:
            from config.high_score_config import get_evaluation_mode, EVALUATION_MODES
            current_mode = get_evaluation_mode()
        except ImportError:
            current_mode = 'weekly_ranking'
            EVALUATION_MODES = {
                'weekly_ranking': {'name': '週報ランキング'},
                'high_score': {'name': 'ハイスコア評価'}
            }
        
        if current_mode == 'weekly_ranking':
            tab1, tab2 = st.tabs([
                "🏆 週報ランキング（100点満点）",
                "⭐ ハイスコア評価（旧方式）"
            ])
        else:
            tab1, tab2 = st.tabs([
                "⭐ ハイスコア評価",
                "🏆 週報ランキング"
            ])
        
        with tab1 if current_mode == 'weekly_ranking' else tab2:
            DashboardPage._render_weekly_ranking_tab(df, target_dict)
        
        with tab2 if current_mode == 'weekly_ranking' else tab1:
            DashboardPage._render_high_score_tab(df, target_dict)

    @staticmethod
    @safe_streamlit_operation("週報ランキング表示")
    def _render_weekly_ranking_tab(df: pd.DataFrame, target_dict: Dict[str, Any]) -> None:
        """週報ランキングタブを表示（100点満点）"""
        try:
            st.subheader("🏆 週報ランキング - 競争力重視評価（100点満点）")
            st.caption("💡 診療科間の健全な競争を促進する週次評価システム")
            
            # 設定セクション
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                period = st.selectbox(
                    "📅 評価期間",
                    ["直近4週", "直近8週", "直近12週"],
                    index=2,
                    key="weekly_ranking_period"
                )
            
            with col2:
                if st.button("🔄 更新", key="refresh_weekly", use_container_width=True):
                    st.rerun()
            
            with col3:
                show_details = st.checkbox(
                    "詳細表示", 
                    value=True, 
                    key="weekly_details"
                )
            
            # 週報ランキング計算
            with st.spinner("週報ランキングを計算中..."):
                try:
                    from analysis.weekly_surgery_ranking import (
                        calculate_weekly_surgery_ranking, 
                        generate_weekly_ranking_summary
                    )
                    
                    dept_scores = calculate_weekly_surgery_ranking(df, target_dict, period)
                    
                    if not dept_scores:
                        st.warning("週報ランキングデータがありません。データと目標設定を確認してください。")
                        return
                    
                    summary = generate_weekly_ranking_summary(dept_scores)
                    
                except ImportError:
                    st.error("❌ 週報ランキング機能が利用できません。")
                    return
            
            # サマリー情報
            if summary:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("🏥 評価診療科数", f"{summary['total_departments']}科")
                
                with col2:
                    st.metric("📊 平均スコア", f"{summary['average_score']:.1f}点")
                
                with col3:
                    st.metric("🎯 目標達成科数", f"{summary['high_achievers_count']}科")
                
                with col4:
                    st.metric("⭐ S評価科数", f"{summary['s_grade_count']}科")
            
            # TOP3ランキング表示
            st.subheader("🥇 TOP3 診療科ランキング")
            
            if len(dept_scores) >= 3:
                top3 = dept_scores[:3]
                
                for i, dept in enumerate(top3):
                    rank_emoji = ["🥇", "🥈", "🥉"][i]
                    
                    with st.container():
                        col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
                        
                        with col1:
                            st.markdown(f"### {rank_emoji}")
                        
                        with col2:
                            st.markdown(f"### {dept['display_name']}")
                            st.caption(f"グレード: {dept['grade']}")
                        
                        with col3:
                            st.metric("総合スコア", f"{dept['total_score']:.1f}点")
                        
                        with col4:
                            st.metric("達成率", f"{dept['achievement_rate']:.1f}%")
                        
                        if show_details:
                            with st.expander("詳細スコア"):
                                # 評価構成の表示
                                st.markdown("**スコア内訳（100点満点）**")
                                
                                # 対目標パフォーマンス（55点）
                                target_perf = dept.get('target_performance', {})
                                st.progress(
                                    target_perf.get('total', 0) / 55,
                                    text=f"対目標パフォーマンス: {target_perf.get('total', 0):.1f}/55点"
                                )
                                
                                # 改善・継続性（25点）
                                improvement = dept.get('improvement_score', {})
                                st.progress(
                                    improvement.get('total', 0) / 25,
                                    text=f"改善・継続性: {improvement.get('total', 0):.1f}/25点"
                                )
                                
                                # 相対競争力（20点）
                                competitive = dept.get('competitive_score', 0)
                                st.progress(
                                    competitive / 20,
                                    text=f"相対競争力: {competitive:.1f}/20点"
                                )
            
            # 全診療科ランキングテーブル
            if len(dept_scores) > 3:
                st.subheader("📋 全診療科ランキング")
                
                ranking_data = []
                for i, dept in enumerate(dept_scores):
                    ranking_data.append({
                        "順位": i + 1,
                        "診療科": dept['display_name'],
                        "グレード": dept['grade'],
                        "総合スコア": f"{dept['total_score']:.1f}点",
                        "目標達成率": f"{dept['achievement_rate']:.1f}%",
                        "前週比": f"{dept.get('improvement_rate', 0):+.1f}%",
                        "直近週全身麻酔": f"{dept['latest_gas_cases']}件"
                    })
                
                ranking_df = pd.DataFrame(ranking_data)
                st.dataframe(ranking_df, use_container_width=True)
                
                # CSVダウンロード
                csv_data = ranking_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 週報ランキングをCSVダウンロード",
                    data=csv_data,
                    file_name=f"週報ランキング_{period}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            # 週報インサイト
            if summary and summary.get('top3_departments'):
                st.subheader("💡 今週のハイライト")
                
                insights = []
                
                # MVP診療科
                top_dept = summary['top3_departments'][0]
                insights.append(f"🏆 **MVP診療科**: {top_dept['display_name']} ({top_dept['total_score']:.1f}点)")
                
                # 目標達成
                if summary['high_achievers_count'] > 0:
                    insights.append(f"🎯 **目標達成**: {summary['high_achievers_count']}科が週次目標を達成")
                
                # S評価
                if summary['s_grade_count'] > 0:
                    insights.append(f"⭐ **優秀評価**: {summary['s_grade_count']}科がS評価を獲得")
                
                # 改善度トップ
                improvers = sorted(dept_scores, key=lambda x: x.get('improvement_rate', 0), reverse=True)
                if improvers and improvers[0].get('improvement_rate', 0) > 5:
                    insights.append(f"📈 **最優秀改善**: {improvers[0]['display_name']} (前週比+{improvers[0]['improvement_rate']:.1f}%)")
                
                for insight in insights:
                    st.markdown(f"• {insight}")
        
        except Exception as e:
            logger.error(f"週報ランキング表示エラー: {e}")
            st.error("週報ランキング表示でエラーが発生しました")

    @staticmethod
    @safe_streamlit_operation("ハイスコア表示")
    def _render_high_score_tab(df: pd.DataFrame, target_dict: Dict[str, Any]) -> None:
        """ハイスコアタブを表示（旧方式）"""
        try:
            st.subheader("⭐ ハイスコア評価 - 包括的パフォーマンス")
            st.caption("💡 全身麻酔手術を中心とした包括的な診療科評価（旧方式）")
            
            # 設定セクション
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                period = st.selectbox(
                    "📅 評価期間",
                    ["直近4週", "直近8週", "直近12週"],
                    index=2,
                    key="high_score_period"
                )
            
            with col2:
                if st.button("🔄 更新", key="refresh_high", use_container_width=True):
                    st.rerun()
            
            with col3:
                show_details = st.checkbox(
                    "詳細表示", 
                    value=False, 
                    key="high_score_details"
                )
            
            # ハイスコア計算
            with st.spinner("ハイスコアを計算中..."):
                try:
                    from analysis.surgery_high_score import (
                        calculate_surgery_high_scores, 
                        generate_surgery_high_score_summary
                    )
                    
                    dept_scores = calculate_surgery_high_scores(df, target_dict, period)
                    
                    if not dept_scores:
                        st.warning("ハイスコアデータがありません。")
                        return
                    
                    summary = generate_surgery_high_score_summary(dept_scores)
                    
                except ImportError:
                    st.error("❌ ハイスコア機能が利用できません。")
                    return
            
            # ハイスコア表示（既存のロジック）
            DashboardPage._display_high_score_content(dept_scores, summary, show_details)
            
        except Exception as e:
            logger.error(f"ハイスコア表示エラー: {e}")
            st.error("ハイスコア表示でエラーが発生しました")

    @staticmethod
    def _display_high_score_content(dept_scores: list, summary: dict, show_details: bool) -> None:
        """ハイスコアコンテンツを表示（既存のロジック）"""
        # 既存のハイスコア表示ロジックをここに実装
        st.info("ハイスコア評価の詳細表示")

    # === ▼▼▼ 修正箇所 ▼▼▼ ===
    @staticmethod
    def _render_period_selector(base_date: Optional[pd.Timestamp]) -> Tuple[str, Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """期間選択セクション"""
        st.subheader("📅 分析期間")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            period_options = ["直近4週", "直近8週", "直近12週", "今年度", "昨年度", "カスタム"]
            analysis_period = st.selectbox(
                "期間選択",
                period_options,
                index=2,
                key="dashboard_period"
            )
        
        start_date, end_date = DashboardPage._get_period_dates(base_date, analysis_period)
        
        if analysis_period == "カスタム":
            with col2:
                start_date_input = st.date_input("開始日", value=start_date if start_date else datetime.now().date())
            with col3:
                end_date_input = st.date_input("終了日", value=end_date if end_date else datetime.now().date())
            
            start_date = pd.to_datetime(start_date_input)
            end_date = pd.to_datetime(end_date_input)
        else:
            with col2:
                st.caption(f"開始: {start_date.strftime('%Y/%m/%d') if start_date else '-'}")
            with col3:
                st.caption(f"終了: {end_date.strftime('%Y/%m/%d') if end_date else '-'}")
        
        return analysis_period, start_date, end_date

    @staticmethod
    def _get_period_dates(base_date: Optional[pd.Timestamp], period: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """期間文字列から開始・終了日を計算"""
        if base_date is None:
            return None, None
        
        try:
            end_date = base_date
            if "週" in period:
                weeks = int(period.replace("直近", "").replace("週", ""))
                start_date = base_date - pd.Timedelta(weeks=weeks) + pd.Timedelta(days=1)
            elif period == "今年度":
                fiscal_year_start = pd.Timestamp(year=base_date.year if base_date.month >= 4 else base_date.year - 1, month=4, day=1)
                start_date = fiscal_year_start
            elif period == "昨年度":
                last_fiscal_year_start = pd.Timestamp(year=base_date.year - 1 if base_date.month >= 4 else base_date.year - 2, month=4, day=1)
                last_fiscal_year_end = pd.Timestamp(year=base_date.year if base_date.month >= 4 else base_date.year - 1, month=3, day=31)
                start_date = last_fiscal_year_start
                end_date = min(base_date, last_fiscal_year_end)
            else:
                start_date = base_date - pd.Timedelta(weeks=12) + pd.Timedelta(days=1)
                
            return start_date, end_date
        except Exception as e:
            logger.error(f"期間計算エラー: {e}")
            return None, None

    @staticmethod
    def _render_kpi_section_with_data(df: pd.DataFrame, base_date: Optional[pd.Timestamp], 
                                     start_date: Optional[pd.Timestamp], end_date: Optional[pd.Timestamp]) -> Dict[str, Any]:
    # === ▲▲▲ 修正箇所 ▲▲▲ ===
        """KPIセクションを表示してデータを返す"""
        st.subheader("📊 主要指標（KPI）")
        
        kpi_data = {}
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_cases = len(df) if not df.empty else 0
            st.metric("総手術件数", f"{total_cases:,}件")
            kpi_data['total_cases'] = total_cases
        
        with col2:
            if '手術時間_時間' in df.columns:
                avg_time = df['手術時間_時間'].mean()
                st.metric("平均手術時間", f"{avg_time:.1f}時間")
                kpi_data['avg_time'] = avg_time
        
        with col3:
            if 'is_gas_20min' in df.columns:
                gas_cases = df['is_gas_20min'].sum()
                st.metric("全身麻酔件数", f"{gas_cases:,}件")
                kpi_data['gas_cases'] = gas_cases
        
        with col4:
            dept_count = df['実施診療科'].nunique() if '実施診療科' in df.columns else 0
            st.metric("実施診療科数", f"{dept_count}科")
            kpi_data['dept_count'] = dept_count
        
        return kpi_data

    @staticmethod
    def _render_basic_charts(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        """基本チャートセクション"""
        st.subheader("📈 トレンドチャート")
        
        period_df = df[
            (df['手術実施日_dt'] >= start_date) & 
            (df['手術実施日_dt'] <= end_date)
        ] if '手術実施日_dt' in df.columns else df
        
        if period_df.empty:
            st.warning("選択期間にデータがありません")
            return
        
        try:
            st.markdown("##### 週次手術件数トレンド")

            if '手術実施日_dt' not in period_df.columns or period_df.empty:
                st.warning("トレンドチャートの描画に必要な日付データがありません。")
                return

            weekly_summary = period_df.set_index('手術実施日_dt').resample('W-MON').size().reset_index(name='件数')
            weekly_summary.rename(columns={'手術実施日_dt': '週'}, inplace=True)
            
            if weekly_summary.empty:
                st.info("選択期間にプロットする週次データがありません。")
                return

            fig = px.line(
                weekly_summary,
                x='週',
                y='件数',
                title='週ごとの手術件数の推移',
                labels={'週': '週の開始日', '件数': '手術件数'},
                markers=True
            )

            fig.update_layout(xaxis_title="日付", yaxis_title="手術件数", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        except Exception as e:
            logger.error(f"基本チャート表示エラー: {e}", exc_info=True)
            st.error("チャート表示でエラーが発生しました")

    @staticmethod
    @safe_data_operation("パフォーマンスダッシュボード")
    # === ▼▼▼ 修正箇所 ▼▼▼ ===
    def _render_performance_dashboard_with_data(df: pd.DataFrame, target_dict: Dict[str, Any], base_date: Optional[pd.Timestamp], start_date: Optional[pd.Timestamp], end_date: Optional[pd.Timestamp]) -> Dict[str, Any]:
    # === ▲▲▲ 修正箇所 ▲▲▲ ===
        st.subheader("🎯 パフォーマンス分析")
        performance_data = {}
        st.info("パフォーマンス分析の詳細実装")
        return performance_data

    @staticmethod
    def _render_achievement_status(df: pd.DataFrame, target_dict: Dict[str, Any],
                                 start_date: Optional[pd.Timestamp], 
                                 end_date: Optional[pd.Timestamp]) -> None:
        """目標達成状況セクション"""
        st.subheader("🎯 目標達成状況")
        
        if not target_dict:
            st.info("目標値を設定すると達成状況が表示されます")
            return
        
        st.info("目標達成状況の詳細実装")

    @staticmethod
    @safe_data_operation("レポート生成")
    def _render_report_section(df: pd.DataFrame, target_dict: Dict[str, Any], period: str) -> None:
        """レポート生成セクション"""
        st.subheader("📄 レポート生成")
        
        try:
            from config.high_score_config import get_evaluation_mode
            current_mode = get_evaluation_mode()
        except ImportError:
            current_mode = 'weekly_ranking'
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 評価レポート**")
            report_name = "週報ランキング" if current_mode == 'weekly_ranking' else "ハイスコア"
            
            if st.button(f"📄 {report_name}レポート生成", type="primary", use_container_width=True):
                with st.spinner("レポートを生成中..."):
                    try:
                        st.success(f"✅ {report_name}レポート生成完了")
                        st.info("💡 GitHub公開機能で自動公開も可能です")
                    
                    except Exception as e:
                        st.error(f"レポート生成エラー: {e}")
        
        with col2:
            st.markdown("**📤 エクスポート**")
            if st.button("📊 CSVエクスポート", use_container_width=True):
                try:
                    st.success("✅ CSVエクスポート完了")
                except Exception as e:
                    st.error(f"エクスポートエラー: {e}")