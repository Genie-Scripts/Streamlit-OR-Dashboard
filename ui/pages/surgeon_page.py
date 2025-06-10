import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Optional

# 既存モジュールのインポート
from analysis import weekly, surgeon
from plotting import trend_plots, generic_plots
from ..components import chart_container
from ..error_handler import with_error_handling, ErrorHandler

@with_error_handling("術者分析ページ描画")
def render(df: pd.DataFrame, target_dict: Dict, latest_date: Optional[datetime]) -> None:
    """術者分析ページを描画"""
    
    st.title("👨‍⚕️ 術者分析")
    
    # データ検証
    if not _validate_surgeon_data(df):
        return
    
    # 分析タイプ選択
    analysis_type = st.radio(
        "📊 分析タイプ",
        ["診療科別ランキング", "術者ごと時系列"],
        horizontal=True,
        help="術者データの表示方法を選択してください"
    )
    
    # 術者データの準備
    expanded_df = _prepare_surgeon_data(df)
    if expanded_df.empty:
        return
    
    # 選択された分析タイプに応じて表示
    if analysis_type == "診療科別ランキング":
        _render_department_ranking(expanded_df)
    else:
        _render_surgeon_timeseries(expanded_df)

def _validate_surgeon_data(df: pd.DataFrame) -> bool:
    """術者データの検証"""
    if df.empty:
        ErrorHandler.display_warning("表示するデータがありません", "術者分析")
        return False
    
    required_columns = ['実施診療科']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        ErrorHandler.display_error(
            ValueError(f"必要な列が不足しています: {missing_columns}"),
            "術者分析"
        )
        return False
    
    return True

@with_error_handling("術者データ準備", show_spinner=True, spinner_text="術者データを準備中...")
def _prepare_surgeon_data(df: pd.DataFrame) -> pd.DataFrame:
    """術者データを準備"""
    try:
        expanded_df = surgeon.get_expanded_surgeon_df(df)
        return expanded_df
    except Exception as e:
        ErrorHandler.display_error(e, "術者データ準備")
        return pd.DataFrame()

@with_error_handling("診療科別ランキング表示")
def _render_department_ranking(expanded_df: pd.DataFrame) -> None:
    """診療科別ランキングを表示"""
    st.header("🏆 診療科別術者ランキング")
    
    # フィルタ設定
    col1, col2 = st.columns(2)
    
    with col1:
        departments = ["全診療科"] + sorted(expanded_df["実施診療科"].dropna().unique())
        selected_dept = st.selectbox(
            "🏥 診療科で絞り込み",
            departments,
            help="特定の診療科に絞り込むか、全診療科を表示するか選択してください"
        )
    
    with col2:
        top_n = st.slider(
            "📊 表示する術者数（上位）",
            min_value=5,
            max_value=50,
            value=15,
            step=5,
            help="ランキングに表示する術者の数を設定してください"
        )
    
    # データのフィルタリング
    target_df = expanded_df
    if selected_dept != "全診療科":
        target_df = expanded_df[expanded_df['実施診療科'] == selected_dept]
    
    if target_df.empty:
        st.warning(f"📊 {selected_dept}のデータがありません")
        return
    
    # ランキング生成と表示
    try:
        summary_df = surgeon.get_surgeon_summary(target_df)
        
        if summary_df.empty:
            st.warning(f"📊 {selected_dept}の術者サマリーを生成できませんでした")
            return
        
        # グラフ表示
        with chart_container.create_chart_container():
            fig = generic_plots.plot_surgeon_ranking(summary_df, top_n, selected_dept)
            st.plotly_chart(fig, use_container_width=True)
        
        # データ詳細表示
        _display_ranking_details(summary_df, selected_dept, top_n)
        
    except Exception as e:
        ErrorHandler.display_error(e, f"{selected_dept} ランキング生成")

def _display_ranking_details(
    summary_df: pd.DataFrame, 
    selected_dept: str, 
    top_n: int
) -> None:
    """ランキング詳細データを表示"""
    with st.expander(f"📋 {selected_dept} 術者詳細データ (Top {top_n})"):
        display_df = summary_df.head(top_n).copy()
        
        # カラム名を日本語に変更
        column_mapping = {
            '実施術者': '術者名',
            '手術件数': '件数',
            '実施診療科': '診療科'
        }
        
        display_df = display_df.rename(columns=column_mapping)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # サマリー統計
        total_surgeons = len(summary_df)
        total_cases = summary_df['手術件数'].sum() if '手術件数' in summary_df.columns else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👨‍⚕️ 総術者数", f"{total_surgeons}人")
        with col2:
            st.metric("📊 総手術件数", f"{total_cases:,}件")
        with col3:
            avg_cases = total_cases / total_surgeons if total_surgeons > 0 else 0
            st.metric("📈 術者当たり平均", f"{avg_cases:.1f}件")

@with_error_handling("術者時系列表示")
def _render_surgeon_timeseries(expanded_df: pd.DataFrame) -> None:
    """術者ごと時系列を表示"""
    st.header("📈 術者別 時系列分析")
    
    # 術者選択
    surgeons = sorted(expanded_df["実施術者"].dropna().unique())
    
    if not surgeons:
        st.warning("📊 分析可能な術者データがありません")
        return
    
    selected_surgeon = st.selectbox(
        "👨‍⚕️ 分析する術者を選択",
        surgeons,
        help="時系列分析を行う術者を選択してください"
    )
    
    # 選択された術者のデータをフィルタ
    surgeon_df = expanded_df[expanded_df['実施術者'] == selected_surgeon]
    
    if surgeon_df.empty:
        st.warning(f"📊 {selected_surgeon}のデータがありません")
        return
    
    # 術者情報の表示
    _display_surgeon_info(surgeon_df, selected_surgeon)
    
    # 週次実績の表示
    _display_surgeon_weekly_performance(surgeon_df, selected_surgeon)

def _display_surgeon_info(surgeon_df: pd.DataFrame, selected_surgeon: str) -> None:
    """術者基本情報を表示"""
    # 術者の基本統計
    total_cases = len(surgeon_df[surgeon_df.get('is_gas_20min', False)])
    departments = surgeon_df['実施診療科'].nunique()
    date_range = surgeon_df['手術実施日_dt'].agg(['min', 'max']) if '手術実施日_dt' in surgeon_df.columns else None
    
    st.subheader(f"👨‍⚕️ {selected_surgeon} - 基本情報")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 総手術件数", f"{total_cases:,}件")
    
    with col2:
        st.metric("🏥 関連診療科数", f"{departments}科")
    
    with col3:
        if date_range is not None and not pd.isna(date_range['min']):
            st.metric("📅 活動開始", date_range['min'].strftime('%Y/%m'))
        else:
            st.metric("📅 活動開始", "データなし")
    
    with col4:
        if date_range is not None and not pd.isna(date_range['max']):
            st.metric("📅 最新実績", date_range['max'].strftime('%Y/%m'))
        else:
            st.metric("📅 最新実績", "データなし")

@with_error_handling("術者週次パフォーマンス表示")
def _display_surgeon_weekly_performance(surgeon_df: pd.DataFrame, selected_surgeon: str) -> None:
    """術者の週次パフォーマンスを表示"""
    st.subheader(f"📈 {selected_surgeon} の週次実績")
    
    try:
        summary = weekly.get_summary(surgeon_df, use_complete_weeks=False)
        
        if summary.empty:
            st.warning(f"📊 {selected_surgeon}の週次データが生成できませんでした")
            return
        
        with chart_container.create_chart_container():
            fig = trend_plots.create_weekly_dept_chart(
                summary, 
                selected_surgeon, 
                {}  # 個人目標は通常設定されていないため空辞書
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 週次データの詳細
        _display_weekly_details(summary, selected_surgeon)
        
    except Exception as e:
        ErrorHandler.display_error(e, f"{selected_surgeon} 週次実績生成")

def _display_weekly_details(summary: pd.DataFrame, selected_surgeon: str) -> None:
    """週次データの詳細を表示"""
    if summary.empty:
        return
    
    with st.expander(f"📋 {selected_surgeon} 週次データ詳細"):
        # サマリー統計
        total_weeks = len(summary)
        total_cases = summary.sum().iloc[0] if len(summary.columns) > 0 else 0
        avg_per_week = total_cases / total_weeks if total_weeks > 0 else 0
        max_week = summary.max().iloc[0] if len(summary.columns) > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 分析週数", f"{total_weeks}週")
        
        with col2:
            st.metric("📈 総手術件数", f"{total_cases:.0f}件")
        
        with col3:
            st.metric("📊 週平均", f"{avg_per_week:.1f}件")
        
        with col4:
            st.metric("🏆 最大週", f"{max_week:.0f}件")
        
        # 詳細データテーブル
        st.subheader("📋 週別データ")
        display_summary = summary.copy()
        display_summary.index = display_summary.index.strftime('%Y-%m-%d')
        
        st.dataframe(
            display_summary,
            use_container_width=True
        )