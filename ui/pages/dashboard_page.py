# ui/pages/dashboard_page.py
"""
ダッシュボードページモジュール
メインダッシュボードの表示を管理
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation
from ui.components.period_selector import PeriodSelector

# 既存の分析モジュールをインポート
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots
from utils import date_helpers

# PDF出力機能をインポート
try:
    from utils.pdf_generator import StreamlitPDFExporter
    PDF_EXPORT_AVAILABLE = True
except ImportError:
    PDF_EXPORT_AVAILABLE = False

logger = logging.getLogger(__name__)


class DashboardPage:
    """ダッシュボードページクラス"""

    @staticmethod
    @safe_streamlit_operation("ダッシュボードページ描画")
    def render() -> None:
        """ダッシュボードページを描画"""
        st.title("📱 ダッシュボード - 管理者向けサマリー")

        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()

        if df.empty:
            DashboardPage._render_no_data_dashboard()
            return

        PeriodSelector.render()
        analysis_period = SessionManager.get_analysis_period()
        start_date = SessionManager.get_start_date()
        end_date = SessionManager.get_end_date()

        if not all([analysis_period, start_date, end_date]):
            st.error("分析期間が正しく設定されていません。")
            return

        period_df = df[(df['手術実施日_dt'] >= start_date) & (df['手術実施日_dt'] <= end_date)]

        pdf_kpi_data = DashboardPage._render_kpi_section_with_data(period_df, start_date, end_date)
        pdf_performance_data = DashboardPage._render_performance_dashboard_with_data(period_df, target_dict, start_date, end_date)
        DashboardPage._render_achievement_summary(period_df, target_dict, start_date, end_date)

        pdf_charts = {}
        if not df.empty:
            try:
                summary = weekly.get_summary(df, use_complete_weeks=True)
                if not summary.empty:
                    pdf_charts['週次推移'] = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
            except Exception as e:
                logger.error(f"週次推移グラフ生成エラー: {e}")

        DashboardPage._render_pdf_export_section(
            pdf_kpi_data, pdf_performance_data, analysis_period, start_date, end_date, pdf_charts
        )

    @staticmethod
    def _render_no_data_dashboard() -> None:
        """データなし時のダッシュボード"""
        st.info("📊 ダッシュボードを表示するにはデータが必要です")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🚀 はじめに\n\n**主な機能:**\n- 📈 リアルタイム手術実績分析\n- 🏆 診療科別ランキング\n- 👨‍⚕️ 術者別パフォーマンス分析\n- 🔮 将来予測とトレンド分析")
        with col2:
            st.markdown("### 📋 次のステップ\n\n1. **データアップロード**で手術データを読み込み\n2. **目標データ**を設定（オプション）\n3. **分析開始** - 各種レポートを確認\n\n**対応形式:** CSV形式の手術データ")
        st.markdown("---")
        st.subheader("⚡ クイックアクション")
        col1, col2, col3 = st.columns(3)
        if col1.button("📤 データアップロード", type="primary", use_container_width=True):
            SessionManager.set_current_view("データアップロード"); st.rerun()
        if col2.button("💾 データ管理", use_container_width=True):
            SessionManager.set_current_view("データ管理"); st.rerun()
        if col3.button("📖 ヘルプ", use_container_width=True):
            DashboardPage._show_help_dialog()

    @staticmethod
    @safe_data_operation("KPI計算")
    def _render_kpi_section_with_data(period_df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Any]:
        """KPIセクションを描画し、データも返す"""
        st.header("📊 主要指標 (選択期間)")
        try:
            kpi_data = DashboardPage._calculate_period_kpi(period_df, start_date, end_date)
            DashboardPage._display_period_kpi_metrics(kpi_data, start_date, end_date)
            return kpi_data
        except Exception as e:
            logger.error(f"KPI計算エラー: {e}")
            st.error("KPI計算中にエラーが発生しました")
            return {}

    @staticmethod
    def _calculate_period_kpi(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, Any]:
        """選択期間のKPIを計算"""
        if df.empty:
            return {}
        total_days = (end_date - start_date).days + 1
        weekdays = sum(1 for i in range(total_days) if (start_date + pd.Timedelta(days=i)).weekday() < 5)
        gas_df = df[df['is_gas_20min'] == True] if 'is_gas_20min' in df.columns else pd.DataFrame()
        gas_cases = len(gas_df)
        total_cases = len(df)
        weekday_gas_cases = len(gas_df[gas_df['is_weekday'] == True]) if not gas_df.empty and 'is_weekday' in gas_df.columns else gas_cases
        daily_avg_gas = weekday_gas_cases / weekdays if weekdays > 0 else 0
        utilization_rate, actual_minutes, max_minutes = DashboardPage._calculate_or_utilization(df, weekdays)
        return {'gas_cases': gas_cases, 'total_cases': total_cases, 'daily_avg_gas': daily_avg_gas, 'utilization_rate': utilization_rate, 'actual_minutes': actual_minutes, 'max_minutes': max_minutes, 'period_days': total_days, 'weekdays': weekdays}

    @staticmethod
    def _calculate_or_utilization(df: pd.DataFrame, weekdays: int) -> Tuple[float, int, int]:
        """手術室稼働率を時間ベースで計算"""
        try:
            weekday_df = df[df['is_weekday'] == True].copy() if 'is_weekday' in df.columns else df.copy()
            if weekday_df.empty: return 0.0, 0, 0
            
            or_column = next((col for col in ['手術室', 'OR', 'OP室', '実施手術室', '実施OP', 'OR番号'] if col in weekday_df.columns), None)
            if or_column:
                weekday_df['or_str'] = weekday_df[or_column].astype(str)
                op_rooms = weekday_df[weekday_df['or_str'].str.contains('OP|ＯＰ', na=False, case=False)]
                or_filtered_df = op_rooms[~op_rooms['or_str'].str.contains('OP-11A|OP-11B|ＯＰ－１１Ａ|ＯＰ－１１Ｂ', na=False, case=False, regex=True)] if len(op_rooms) > 0 else weekday_df
            else:
                or_filtered_df = weekday_df
            
            time_filtered_df = DashboardPage._filter_operating_hours(or_filtered_df)
            actual_minutes = DashboardPage._calculate_surgery_minutes(time_filtered_df)
            max_minutes = 495 * 11 * weekdays
            utilization_rate = (actual_minutes / max_minutes * 100) if max_minutes > 0 else 0.0
            return utilization_rate, actual_minutes, max_minutes
        except Exception as e:
            logger.error(f"手術室稼働率計算エラー: {e}")
            return 0.0, 0, 0

    @staticmethod
    def _filter_operating_hours(df: pd.DataFrame) -> pd.DataFrame:
        """手術室稼働率計算用のフィルタリング"""
        if df.empty or '入室時刻' not in df.columns or '退室時刻' not in df.columns:
            return df
        def has_valid_time(time_str):
            if pd.isna(time_str): return False
            time_str = str(time_str).strip()
            try:
                if ':' in time_str:
                    hour, minute = map(int, time_str.split(':'))
                    return 0 <= hour <= 23 and 0 <= minute <= 59
                elif len(time_str) == 4 and time_str.isdigit():
                    hour, minute = int(time_str[:2]), int(time_str[2:])
                    return 0 <= hour <= 23 and 0 <= minute <= 59
                return False
            except:
                return False
        return df[df['入室時刻'].apply(has_valid_time) & df['退室時刻'].apply(has_valid_time)].copy()

    @staticmethod
    def _calculate_surgery_minutes(df: pd.DataFrame) -> int:
        """手術時間の合計を分単位で計算"""
        if df.empty or '入室時刻' not in df.columns or '退室時刻' not in df.columns:
            return len(df) * 90  # Fallback

        def time_to_minutes(time_str):
            if pd.isna(time_str): return None
            time_str = str(time_str).strip()
            try:
                if ':' in time_str: return int(time_str.split(':')[0]) * 60 + int(time_str.split(':')[1])
                elif len(time_str) == 4 and time_str.isdigit(): return int(time_str[:2]) * 60 + int(time_str[2:])
            except: return None

        df_calc = df.copy()
        df_calc['entry_min'] = df_calc['入室時刻'].apply(time_to_minutes)
        df_calc['exit_min'] = df_calc['退室時刻'].apply(time_to_minutes)
        valid_data = df_calc.dropna(subset=['entry_min', 'exit_min']).copy()
        if valid_data.empty: return len(df) * 90

        valid_data.loc[valid_data['exit_min'] < valid_data['entry_min'], 'exit_min'] += 24 * 60
        valid_data['adjusted_entry'] = valid_data['entry_min'].clip(lower=540)
        valid_data['adjusted_exit'] = valid_data['exit_min'].clip(upper=1035)
        valid_data['actual_duration'] = valid_data['adjusted_exit'] - valid_data['adjusted_entry']
        return int(valid_data[valid_data['actual_duration'] > 0]['actual_duration'].sum())

    @staticmethod
    def _display_period_kpi_metrics(kpi_data: Dict[str, Any], start_date: Optional[pd.Timestamp], end_date: Optional[pd.Timestamp]) -> None:
        """選択期間のKPI指標を表示"""
        if not kpi_data:
            st.warning("KPIデータが計算できませんでした")
            return
        col1, col2, col3, col4 = st.columns(4)
        gas_cases = kpi_data.get('gas_cases', 0)
        col1.metric("🔴 全身麻酔手術件数", f"{gas_cases:,}件", help="選択期間内の全身麻酔手術（20分以上）総件数")
        total_cases = kpi_data.get('total_cases', 0)
        col2.metric("📊 全手術件数", f"{total_cases:,}件", help="選択期間内の全手術総件数")
        daily_avg_gas = kpi_data.get('daily_avg_gas', 0)
        from config.hospital_targets import HospitalTargets
        hospital_target = HospitalTargets.get_daily_target()
        delta_gas = daily_avg_gas - hospital_target if hospital_target > 0 else 0
        col3.metric("📈 平日1日あたり全身麻酔手術件数", f"{daily_avg_gas:.1f}件/日", delta=f"{delta_gas:+.1f}件" if hospital_target > 0 else None, help="平日（月〜金）の1日あたり全身麻酔手術件数")
        utilization = kpi_data.get('utilization_rate', 0)
        actual_hours = kpi_data.get('actual_minutes', 0) / 60
        max_hours = kpi_data.get('max_minutes', 0) / 60
        col4.metric("🏥 手術室稼働率", f"{utilization:.1f}%", delta=f"{actual_hours:.1f}h / {max_hours:.1f}h", help="OP-1〜12（11A,11Bを除く）11室の平日9:00〜17:15稼働率")

    @staticmethod
    @safe_data_operation("パフォーマンスダッシュボード表示")
    def _render_performance_dashboard_with_data(period_df: pd.DataFrame, target_dict: Dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
        """診療科別パフォーマンスダッシュボードを表示し、データも返す"""
        st.markdown("---"); st.header("📊 診療科別パフォーマンスダッシュボード")
        st.caption(f"🗓️ 分析対象期間: {start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}")
        try:
            perf_summary = DashboardPage._calculate_period_performance(period_df, target_dict, start_date, end_date)
            if perf_summary.empty:
                st.info("診療科別パフォーマンスを計算する十分なデータがありません。")
                return pd.DataFrame()
            sorted_perf = perf_summary.sort_values("達成率(%)", ascending=False)
            DashboardPage._render_performance_cards(sorted_perf)
            with st.expander("📋 詳細データテーブル"):
                st.dataframe(sorted_perf, use_container_width=True)
            return sorted_perf
        except Exception as e:
            st.error(f"パフォーマンス計算エラー: {e}"); logger.error(f"パフォーマンス計算エラー: {e}")
            return pd.DataFrame()

    @staticmethod
    def _calculate_period_performance(df: pd.DataFrame, target_dict: Dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
        """選択期間の診療科別パフォーマンスを計算"""
        if df.empty or not target_dict: return pd.DataFrame()
        gas_df = df[df['is_gas_20min'] == True] if 'is_gas_20min' in df.columns else df
        if gas_df.empty: return pd.DataFrame()
        dept_summary = []
        period_weeks = ((end_date - start_date).days + 1) / 7
        for dept, target_weekly in target_dict.items():
            if target_weekly <= 0: continue
            dept_df = gas_df[gas_df['実施診療科'] == dept]
            if dept_df.empty: continue
            total_cases = len(dept_df)
            weekly_avg = total_cases / period_weeks if period_weeks > 0 else 0
            recent_week_start = end_date - pd.Timedelta(days=6)
            recent_week_cases = len(dept_df[dept_df['手術実施日_dt'] >= recent_week_start])
            achievement_rate = (weekly_avg / target_weekly * 100) if target_weekly > 0 else 0
            dept_summary.append({'診療科': dept, '期間平均': weekly_avg, '直近週実績': recent_week_cases, '週次目標': target_weekly, '達成率(%)': achievement_rate})
        return pd.DataFrame(dept_summary)

    @staticmethod
    def _render_performance_cards(sorted_perf: pd.DataFrame) -> None:
        """パフォーマンスカードを表示"""
        cols = st.columns(3)
        for i, (_, row) in enumerate(sorted_perf.iterrows()):
            rate = row["達成率(%)"]
            color = "#28a745" if rate >= 100 else "#ffc107" if rate >= 80 else "#dc3545"
            bar_width = min(rate, 100)
            html = f"""<div style="background-color: {color}1A; border-left: 5px solid {color}; padding: 12px; border-radius: 5px; margin-bottom: 12px; height: 165px;">
                         <h5 style="margin: 0 0 10px 0; font-weight: bold; color: #333;">{row["診療科"]}</h5>
                         <div style="display: flex; justify-content: space-between; font-size: 0.9em;"><span>期間平均:</span><span style="font-weight: bold;">{row.get("期間平均", 0):.1f} 件</span></div>
                         <div style="display: flex; justify-content: space-between; font-size: 0.9em;"><span>直近週実績:</span><span style="font-weight: bold;">{row["直近週実績"]:.0f} 件</span></div>
                         <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #666;"><span>目標:</span><span>{row["週次目標"]:.1f} 件</span></div>
                         <div style="display: flex; justify-content: space-between; font-size: 1.1em; color: {color}; margin-top: 5px;"><span style="font-weight: bold;">達成率:</span><span style="font-weight: bold;">{rate:.1f}%</span></div>
                         <div style="background-color: #e9ecef; border-radius: 5px; height: 6px; margin-top: 5px;"><div style="width: {bar_width}%; background-color: {color}; height: 6px; border-radius: 5px;"></div></div></div>"""
            cols[i % 3].markdown(html, unsafe_allow_html=True)

    @staticmethod
    @safe_data_operation("目標達成状況サマリー")
    def _render_achievement_summary(period_df: pd.DataFrame, target_dict: Dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
        """目標達成状況サマリーを表示"""
        st.markdown("---"); st.header("🎯 目標達成状況サマリー")
        from config.hospital_targets import HospitalTargets
        if period_df.empty: st.info("選択期間のデータがありません"); return
        weekday_df = period_df[period_df['is_weekday']]
        if weekday_df.empty: st.info("平日データが不足しています"); return
        weekdays = sum(1 for i in range((end_date - start_date).days + 1) if (start_date + pd.Timedelta(days=i)).weekday() < 5)
        daily_avg = len(weekday_df) / weekdays if weekdays > 0 else 0
        hospital_target = HospitalTargets.get_daily_target()
        achievement_rate = (daily_avg / hospital_target * 100) if hospital_target > 0 else 0
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏥 病院全体達成率", f"{achievement_rate:.1f}%", delta=f"{achievement_rate - 100:.1f}%")
        col2.metric("📊 実績 (平日平均)", f"{daily_avg:.1f}件/日", delta=f"{daily_avg - hospital_target:+.1f}件")
        col3.metric("🎯 目標", f"{hospital_target}件/日")
        col4.metric("📋 目標設定診療科", f"{len([k for k, v in target_dict.items() if v > 0]) if target_dict else 0}科")

    @staticmethod
    def _render_pdf_export_section(kpi_data: Dict[str, Any], performance_data: pd.DataFrame, period_name: str, start_date: Optional[pd.Timestamp], end_date: Optional[pd.Timestamp], charts: Dict[str, Any] = None) -> None:
        """PDF出力セクションを表示"""
        st.markdown("---"); st.header("📄 レポート出力")
        if not PDF_EXPORT_AVAILABLE:
            st.warning("📋 PDF出力機能は現在利用できません。"); return
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("**📊 レポート内容:**\n- エグゼクティブサマリー\n- 主要業績指標 (KPI)\n- 診療科別パフォーマンス\n- 週次推移グラフ")
            if st.button("🔧 フォント設定確認", help="PDF表示品質の確認"):
                StreamlitPDFExporter.display_font_status()
        with col2:
            if start_date and end_date:
                period_info = StreamlitPDFExporter.create_period_info(period_name, start_date, end_date, kpi_data.get('period_days', 0), kpi_data.get('weekdays', 0))
                if st.button("📄 PDFレポート生成", type="primary", use_container_width=True):
                    with st.spinner("PDFレポートを生成中..."):
                        StreamlitPDFExporter.add_pdf_download_button(kpi_data, performance_data, period_info, charts, "📥 PDFをダウンロード")
            else:
                st.error("期間データが不正です。PDF生成できません。")

    @staticmethod
    def _show_help_dialog() -> None:
        """ヘルプダイアログを表示"""
        with st.expander("📖 ダッシュボードの使い方", expanded=True):
            st.markdown("### 🏠 ダッシュボード概要\n\nダッシュボードは手術分析の中心となるページです。")

# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    DashboardPage.render()