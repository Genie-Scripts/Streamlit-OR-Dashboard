import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from typing import Dict, Optional

# 既存モジュールのインポート
from analysis import weekly, ranking, surgeon
from plotting import trend_plots, generic_plots
from ..components import kpi_display, chart_container
from ..error_handler import with_error_handling, ErrorHandler

@with_error_handling("診療科別分析ページ描画")
def render(df: pd.DataFrame, target_dict: Dict, latest_date: Optional[datetime]) -> None:
    """診療科別分析ページを描画"""
    
    st.title("🩺 診療科別分析")
    
    # データ検証
    if not _validate_department_data(df):
        return
    
    # 診療科選択
    selected_dept = _render_department_selector(df)
    if not selected_dept:
        return
    
    # 選択された診療科のデータをフィルタ
    dept_df = df[df['実施診療科'] == selected_dept]
    
    # KPIサマリー表示
    _render_department_kpi(dept_df, latest_date, selected_dept)
    
    # 週次推移表示
    _render_department_weekly_trends(df, selected_dept, target_dict)
    
    # 詳細分析タブ
    _render_detailed_analysis_tabs(dept_df, selected_dept, target_dict)

def _validate_department_data(df: pd.DataFrame) -> bool:
    """診療科データの検証"""
    if df.empty:
        ErrorHandler.display_warning("表示するデータがありません", "診療科別分析")
        return False
    
    if '実施診療科' not in df.columns:
        ErrorHandler.display_error(
            ValueError("実施診療科の列が見つかりません"),
            "診療科別分析"
        )
        return False
    
    return True

def _render_department_selector(df: pd.DataFrame) -> Optional[str]:
    """診療科選択セクション"""
    departments = sorted(df["実施診療科"].dropna().unique())
    
    if not departments:
        st.warning("データに診療科情報がありません。")
        return None
    
    selected_dept = st.selectbox(
        "🏥 分析する診療科を選択",
        departments,
        help="分析したい診療科を選択してください"
    )
    
    return selected_dept

@with_error_handling("診療科KPI表示")
def _render_department_kpi(
    dept_df: pd.DataFrame, 
    latest_date: Optional[datetime], 
    selected_dept: str
) -> None:
    """診療科別KPIを表示"""
    try:
        kpi_summary = ranking.get_kpi_summary(dept_df, latest_date)
        
        # タイトルとKPI表示
        st.subheader(f"📊 {selected_dept} - KPIサマリー")
        kpi_display.display_kpi_metrics(kpi_summary)
        
    except Exception as e:
        ErrorHandler.display_warning(f"KPI計算でエラーが発生しました: {str(e)}", f"{selected_dept} KPI")

@with_error_handling("診療科週次推移表示")
def _render_department_weekly_trends(
    df: pd.DataFrame, 
    selected_dept: str, 
    target_dict: Dict
) -> None:
    """診療科別週次推移を表示"""
    st.markdown("---")
    st.subheader(f"📈 {selected_dept} - 週次推移")
    
    # 完全週データ使用のトグル
    use_complete_weeks = st.toggle(
        "完全週データで分析", 
        value=True,
        help="週の途中のデータを分析から除外し、月曜〜日曜の完全な週単位で集計します。",
        key=f"dept_complete_weeks_{selected_dept}"
    )
    
    try:
        summary = weekly.get_summary(
            df, 
            department=selected_dept, 
            use_complete_weeks=use_complete_weeks
        )
        
        if summary.empty:
            st.warning(f"📊 {selected_dept}の週次データが生成できませんでした")
            return
        
        with chart_container.create_chart_container():
            fig = trend_plots.create_weekly_dept_chart(summary, selected_dept, target_dict)
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        ErrorHandler.display_error(e, f"{selected_dept} 週次推移生成")

def _render_detailed_analysis_tabs(
    dept_df: pd.DataFrame, 
    selected_dept: str, 
    target_dict: Dict
) -> None:
    """詳細分析タブを描画"""
    st.markdown("---")
    st.header("🔍 詳細分析")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "術者分析", 
        "時間分析", 
        "統計情報", 
        "累積実績"
    ])
    
    with tab1:
        _render_surgeon_analysis_tab(dept_df, selected_dept)
    
    with tab2:
        _render_time_analysis_tab(dept_df)
    
    with tab3:
        _render_statistics_tab(dept_df)
    
    with tab4:
        _render_cumulative_tab(dept_df, selected_dept, target_dict)

@with_error_handling("術者分析タブ")
def _render_surgeon_analysis_tab(dept_df: pd.DataFrame, selected_dept: str) -> None:
    """術者分析タブを描画"""
    st.subheader(f"{selected_dept} 術者別件数 (Top 15)")
    
    try:
        expanded_df = surgeon.get_expanded_surgeon_df(dept_df)
        
        if expanded_df.empty:
            st.info("術者データがありません")
            return
        
        surgeon_summary = surgeon.get_surgeon_summary(expanded_df)
        
        if surgeon_summary.empty:
            st.info("術者サマリーを生成できませんでした")
            return
        
        with chart_container.create_chart_container():
            fig = generic_plots.plot_surgeon_ranking(surgeon_summary, 15, selected_dept)
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        ErrorHandler.display_error(e, "術者分析")

@with_error_handling("時間分析タブ")
def _render_time_analysis_tab(dept_df: pd.DataFrame) -> None:
    """時間分析タブを描画"""
    st.subheader("曜日・月別 分布")
    
    gas_df = dept_df[dept_df['is_gas_20min']]
    
    if gas_df.empty:
        st.info("分析対象となる全身麻酔手術データがありません")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        try:
            weekday_dist = gas_df['手術実施日_dt'].dt.day_name().value_counts()
            
            if not weekday_dist.empty:
                fig_weekday = px.pie(
                    values=weekday_dist.values, 
                    names=weekday_dist.index, 
                    title="曜日別分布"
                )
                st.plotly_chart(fig_weekday, use_container_width=True)
            else:
                st.info("曜日別データがありません")
                
        except Exception as e:
            ErrorHandler.display_warning(f"曜日別分析エラー: {str(e)}", "時間分析")
    
    with col2:
        try:
            month_dist = gas_df['手術実施日_dt'].dt.month_name().value_counts()
            
            if not month_dist.empty:
                fig_month = px.bar(
                    x=month_dist.index, 
                    y=month_dist.values, 
                    title="月別分布",
                    labels={'x': '月', 'y': '件数'}
                )
                st.plotly_chart(fig_month, use_container_width=True)
            else:
                st.info("月別データがありません")
                
        except Exception as e:
            ErrorHandler.display_warning(f"月別分析エラー: {str(e)}", "時間分析")

def _render_statistics_tab(dept_df: pd.DataFrame) -> None:
    """統計情報タブを描画"""
    st.subheader("基本統計")
    
    try:
        gas_df = dept_df[dept_df['is_gas_20min']]
        
        if gas_df.empty:
            st.info("統計計算用のデータがありません")
            return
        
        desc_df = gas_df.describe(include='all').transpose()
        
        # 数値データのみを文字列に変換
        desc_df_display = desc_df.copy()
        for col in desc_df_display.columns:
            desc_df_display[col] = desc_df_display[col].apply(
                lambda x: f"{x:.2f}" if pd.notnull(x) and isinstance(x, (int, float)) else str(x)
            )
        
        st.dataframe(desc_df_display, use_container_width=True)
        
    except Exception as e:
        ErrorHandler.display_error(e, "基本統計計算")

@with_error_handling("累積実績タブ")
def _render_cumulative_tab(
    dept_df: pd.DataFrame, 
    selected_dept: str, 
    target_dict: Dict
) -> None:
    """累積実績タブを描画"""
    st.subheader(f"{selected_dept} 今年度 累積実績")
    
    weekly_target = target_dict.get(selected_dept)
    
    if not weekly_target:
        st.info("この診療科の目標値が設定されていないため、累積目標は表示できません。")
        return
    
    try:
        cum_data = ranking.calculate_cumulative_cases(dept_df, weekly_target)
        
        if cum_data.empty:
            st.info("累積実績を計算するデータがありません")
            return
        
        with chart_container.create_chart_container():
            fig = generic_plots.plot_cumulative_cases_chart(
                cum_data, 
                f"{selected_dept} 累積実績"
            )
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        ErrorHandler.display_error(e, "累積実績計算")