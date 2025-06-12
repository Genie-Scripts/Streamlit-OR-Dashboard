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

# 既存の分析モジュールをインポート
from analysis import weekly, surgeon
from plotting import trend_plots, generic_plots

logger = logging.getLogger(__name__)


class SurgeonPage:
    """術者分析ページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("術者分析ページ描画")
    def render() -> None:
        """術者分析ページを描画"""
        st.title("👨‍⚕️ 術者分析")
        
        # データ取得
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        latest_date = SessionManager.get_latest_date()
        
        # 分析タイプ選択
        analysis_type = st.radio(
            "分析タイプ", 
            ["診療科別ランキング", "術者ごと時系列"], 
            horizontal=True,
            help="分析の種類を選択してください"
        )
        
        # 術者データの準備
        expanded_df = SurgeonPage._prepare_surgeon_data(df)
        if expanded_df.empty:
            st.warning("分析可能な術者データがありません。")
            return
        
        if analysis_type == "診療科別ランキング":
            SurgeonPage._render_ranking_analysis(expanded_df)
        else:  # 術者ごと時系列
            SurgeonPage._render_individual_surgeon_analysis(expanded_df)
    
    @staticmethod
    @safe_data_operation("術者データ準備")
    def _prepare_surgeon_data(df: pd.DataFrame) -> pd.DataFrame:
        """術者データを準備"""
        try:
            with st.spinner("術者データを準備中..."):
                expanded_df = surgeon.get_expanded_surgeon_df(df)
                return expanded_df
                
        except Exception as e:
            st.error(f"術者データ準備エラー: {e}")
            logger.error(f"術者データ準備エラー: {e}")
            return pd.DataFrame()
    
    @staticmethod
    @safe_data_operation("ランキング分析")
    def _render_ranking_analysis(expanded_df: pd.DataFrame) -> None:
        """診療科別ランキング分析を表示"""
        st.subheader("🏆 術者別ランキング")
        
        # フィルタオプション
        col1, col2 = st.columns(2)
        
        with col1:
            departments = ["全診療科"] + sorted(expanded_df["実施診療科"].dropna().unique())
            selected_dept = st.selectbox("診療科で絞り込み", departments)
        
        with col2:
            top_n = st.slider("表示する術者数（上位）", 5, 50, 15)
        
        try:
            # データフィルタリング
            target_df = expanded_df
            if selected_dept != "全診療科":
                target_df = expanded_df[expanded_df['実施診療科'] == selected_dept]
            
            # 術者サマリー計算
            surgeon_summary = surgeon.get_surgeon_summary(target_df)
            
            if not surgeon_summary.empty:
                # ランキンググラフ
                fig = generic_plots.plot_surgeon_ranking(surgeon_summary, top_n, selected_dept)
                st.plotly_chart(fig, use_container_width=True)
                
                # 統計情報
                SurgeonPage._render_ranking_statistics(surgeon_summary, selected_dept, top_n)
                
                # 詳細データテーブル
                with st.expander("📋 詳細ランキングデータ"):
                    st.dataframe(
                        surgeon_summary.head(top_n), 
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.info("ランキングデータを計算できませんでした")
                
        except Exception as e:
            st.error(f"ランキング分析エラー: {e}")
            logger.error(f"術者ランキング分析エラー: {e}")
    
    @staticmethod
    def _render_ranking_statistics(surgeon_summary: pd.DataFrame, selected_dept: str, top_n: int) -> None:
        """ランキング統計情報を表示"""
        with st.expander("📊 ランキング統計"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**基本統計:**")
                st.write(f"• 対象術者数: {len(surgeon_summary)}人")
                st.write(f"• 表示術者数: {min(top_n, len(surgeon_summary))}人")
                st.write(f"• 対象診療科: {selected_dept}")
            
            with col2:
                st.write("**実績統計:**")
                if '手術件数' in surgeon_summary.columns:
                    total_cases = surgeon_summary['手術件数'].sum()
                    avg_cases = surgeon_summary['手術件数'].mean()
                    st.write(f"• 総手術件数: {total_cases:,}件")
                    st.write(f"• 平均件数/術者: {avg_cases:.1f}件")
                else:
                    # 列名を確認して適切な列を使用
                    available_cols = surgeon_summary.columns.tolist()
                    st.write(f"• 利用可能な列: {available_cols}")
                    
                    # 件数に関連する列を探す
                    count_cols = [col for col in available_cols if '件数' in col or 'count' in col.lower()]
                    if count_cols:
                        count_col = count_cols[0]
                        total_cases = surgeon_summary[count_col].sum()
                        avg_cases = surgeon_summary[count_col].mean()
                        st.write(f"• 総手術件数: {total_cases:,}件")
                        st.write(f"• 平均件数/術者: {avg_cases:.1f}件")
                    else:
                        st.write("• 手術件数データが見つかりません")
            
            with col3:
                st.write("**分布統計:**")
                if '手術件数' in surgeon_summary.columns:
                    max_cases = surgeon_summary['手術件数'].max()
                    min_cases = surgeon_summary['手術件数'].min()
                    st.write(f"• 最多件数: {max_cases}件")
                    st.write(f"• 最少件数: {min_cases}件")
                    
                    if len(surgeon_summary) >= 2:
                        top_surgeon = surgeon_summary.iloc[0]
                        surgeon_name = top_surgeon.get('実施術者', '不明')
                        surgeon_cases = top_surgeon.get('手術件数', 0)
                        st.write(f"• トップ術者: {surgeon_name} ({surgeon_cases}件)")
                else:
                    # 列名を確認して適切な列を使用
                    available_cols = surgeon_summary.columns.tolist()
                    count_cols = [col for col in available_cols if '件数' in col or 'count' in col.lower()]
                    if count_cols:
                        count_col = count_cols[0]
                        max_cases = surgeon_summary[count_col].max()
                        min_cases = surgeon_summary[count_col].min()
                        st.write(f"• 最多件数: {max_cases}件")
                        st.write(f"• 最少件数: {min_cases}件")
                        
                        if len(surgeon_summary) >= 2:
                            top_surgeon = surgeon_summary.iloc[0]
                            surgeon_name = top_surgeon.get('実施術者', '不明')
                            surgeon_cases = top_surgeon.get(count_col, 0)
                            st.write(f"• トップ術者: {surgeon_name} ({surgeon_cases}件)")
                    else:
                        st.write("• 分布統計データが見つかりません")
    
    @staticmethod
    @safe_data_operation("個別術者分析")
    def _render_individual_surgeon_analysis(expanded_df: pd.DataFrame) -> None:
        """個別術者時系列分析を表示"""
        st.subheader("📈 術者別時系列分析")
        
        # 術者選択
        surgeons = sorted(expanded_df["実施術者"].dropna().unique())
        selected_surgeon = st.selectbox(
            "分析する術者を選択", 
            surgeons,
            help="時系列分析を行う術者を選択してください"
        )
        
        if not selected_surgeon:
            st.info("術者を選択してください")
            return
        
        try:
            # 選択された術者のデータを抽出
            surgeon_df = expanded_df[expanded_df['実施術者'] == selected_surgeon]
            
            if surgeon_df.empty:
                st.warning(f"{selected_surgeon}のデータが見つかりません")
                return
            
            # 術者情報表示
            SurgeonPage._render_surgeon_info(surgeon_df, selected_surgeon)
            
            # 週次実績グラフ
            SurgeonPage._render_surgeon_weekly_trend(surgeon_df, selected_surgeon)
            
            # 術者詳細分析
            SurgeonPage._render_surgeon_detailed_analysis(surgeon_df, selected_surgeon)
            
        except Exception as e:
            st.error(f"個別術者分析エラー: {e}")
            logger.error(f"個別術者分析エラー ({selected_surgeon}): {e}")
    
    @staticmethod
    def _render_surgeon_info(surgeon_df: pd.DataFrame, surgeon_name: str) -> None:
        """術者基本情報を表示"""
        # 基本統計
        total_cases = len(surgeon_df[surgeon_df['is_gas_20min']])
        departments = surgeon_df['実施診療科'].nunique()
        date_range = (surgeon_df['手術実施日_dt'].max() - surgeon_df['手術実施日_dt'].min()).days
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("総手術件数", f"{total_cases}件")
        with col2:
            st.metric("関連診療科", f"{departments}科")
        with col3:
            st.metric("活動期間", f"{date_range}日")
        with col4:
            if date_range > 0:
                avg_per_day = total_cases / date_range
                st.metric("平均件数/日", f"{avg_per_day:.2f}件")
    
    @staticmethod
    @safe_data_operation("術者週次推移")
    def _render_surgeon_weekly_trend(surgeon_df: pd.DataFrame, surgeon_name: str) -> None:
        """術者の週次推移を表示"""
        st.subheader(f"{surgeon_name} の週次実績")
        
        try:
            summary = weekly.get_summary(surgeon_df, use_complete_weeks=False)
            
            if not summary.empty:
                # 目標辞書は空（術者個人の目標は設定なし）
                fig = trend_plots.create_weekly_dept_chart(summary, surgeon_name, {})
                st.plotly_chart(fig, use_container_width=True)
                
                # 統計サマリー
                with st.expander("📊 週次統計"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**活動統計:**")
                        st.write(f"• 活動週数: {len(summary)}週")
                        st.write(f"• 最多週: {summary['週合計件数'].max():.0f}件")
                        st.write(f"• 最少週: {summary['週合計件数'].min():.0f}件")
                        st.write(f"• 平均/週: {summary['週合計件数'].mean():.1f}件")
                    
                    with col2:
                        st.write("**傾向分析:**")
                        if len(summary) >= 4:
                            recent_avg = summary.tail(4)['週合計件数'].mean()
                            earlier_avg = summary.head(4)['週合計件数'].mean()
                            
                            if recent_avg > earlier_avg:
                                trend = "増加傾向"
                                trend_color = "🔼"
                            else:
                                trend = "減少傾向"
                                trend_color = "🔽"
                            
                            change_rate = ((recent_avg / earlier_avg) - 1) * 100
                            st.write(f"• 傾向: {trend_color} {trend}")
                            st.write(f"• 変化率: {change_rate:+.1f}%")
                        else:
                            st.write("• 傾向分析には4週以上のデータが必要です")
            else:
                st.info(f"{surgeon_name}の週次データがありません")
                
        except Exception as e:
            st.error(f"週次推移分析エラー: {e}")
            logger.error(f"術者週次推移エラー ({surgeon_name}): {e}")
    
    @staticmethod
    def _render_surgeon_detailed_analysis(surgeon_df: pd.DataFrame, surgeon_name: str) -> None:
        """術者詳細分析を表示"""
        st.subheader("📋 詳細分析")
        
        tab1, tab2, tab3 = st.tabs(["診療科別分布", "時間分析", "月次推移"])
        
        with tab1:
            SurgeonPage._render_department_distribution(surgeon_df, surgeon_name)
        
        with tab2:
            SurgeonPage._render_time_distribution(surgeon_df, surgeon_name)
        
        with tab3:
            SurgeonPage._render_monthly_trend(surgeon_df, surgeon_name)
    
    @staticmethod
    def _render_department_distribution(surgeon_df: pd.DataFrame, surgeon_name: str) -> None:
        """診療科別分布を表示"""
        try:
            gas_df = surgeon_df[surgeon_df['is_gas_20min']]
            
            if not gas_df.empty:
                dept_dist = gas_df['実施診療科'].value_counts()
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.bar_chart(dept_dist)
                
                with col2:
                    st.write("**診療科別件数:**")
                    for dept, count in dept_dist.items():
                        percentage = (count / len(gas_df)) * 100
                        st.write(f"• {dept}: {count}件 ({percentage:.1f}%)")
            else:
                st.info("診療科別分布データがありません")
                
        except Exception as e:
            st.error(f"診療科別分布分析エラー: {e}")
    
    @staticmethod
    def _render_time_distribution(surgeon_df: pd.DataFrame, surgeon_name: str) -> None:
        """時間分析を表示"""
        try:
            gas_df = surgeon_df[surgeon_df['is_gas_20min']]
            
            if not gas_df.empty:
                # 曜日別分布
                weekday_dist = gas_df['手術実施日_dt'].dt.day_name().value_counts()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**曜日別分布:**")
                    st.bar_chart(weekday_dist)
                
                with col2:
                    st.write("**時間統計:**")
                    
                    # 平日・休日分布
                    if 'is_weekday' in gas_df.columns:
                        weekday_count = len(gas_df[gas_df['is_weekday']])
                        weekend_count = len(gas_df[~gas_df['is_weekday']])
                        
                        st.metric("平日手術", f"{weekday_count}件")
                        st.metric("休日手術", f"{weekend_count}件")
                        
                        if weekday_count > 0:
                            weekend_ratio = (weekend_count / (weekday_count + weekend_count)) * 100
                            st.metric("休日比率", f"{weekend_ratio:.1f}%")
            else:
                st.info("時間分析データがありません")
                
        except Exception as e:
            st.error(f"時間分析エラー: {e}")
    
    @staticmethod
    def _render_monthly_trend(surgeon_df: pd.DataFrame, surgeon_name: str) -> None:
        """月次推移を表示"""
        try:
            gas_df = surgeon_df[surgeon_df['is_gas_20min']]
            
            if not gas_df.empty:
                # 月次集計
                gas_df = gas_df.copy()
                gas_df['月'] = gas_df['手術実施日_dt'].dt.to_period('M')
                monthly_counts = gas_df.groupby('月').size()
                
                if len(monthly_counts) > 1:
                    st.line_chart(monthly_counts)
                    
                    # 月次統計
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**月次統計:**")
                        st.write(f"• 活動月数: {len(monthly_counts)}ヶ月")
                        st.write(f"• 最多月: {monthly_counts.max()}件")
                        st.write(f"• 最少月: {monthly_counts.min()}件")
                        st.write(f"• 平均/月: {monthly_counts.mean():.1f}件")
                    
                    with col2:
                        st.write("**月別実績:**")
                        for month, count in monthly_counts.tail(6).items():
                            st.write(f"• {month}: {count}件")
                else:
                    st.info("月次推移には複数月のデータが必要です")
            else:
                st.info("月次推移データがありません")
                
        except Exception as e:
            st.error(f"月次推移分析エラー: {e}")


# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    SurgeonPage.render()