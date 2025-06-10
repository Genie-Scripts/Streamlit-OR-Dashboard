import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Optional

# 既存モジュールのインポート
from analysis import weekly, ranking
from plotting import trend_plots
from ..components import kpi_display, chart_container
from ..error_handler import with_error_handling, ErrorHandler

@with_error_handling("病院全体分析ページ描画")
def render(df: pd.DataFrame, target_dict: Dict, latest_date: Optional[datetime]) -> None:
    """病院全体分析ページを描画"""
    
    st.title("🏥 病院全体分析 (完全週データ)")
    
    # データ検証
    if not _validate_hospital_data(df, latest_date):
        return
    
    # 分析期間の計算と表示
    analysis_end_sunday = weekly.get_analysis_end_date(latest_date)
    
    if analysis_end_sunday is None:
        st.warning("分析可能な日付データがありません。")
        return
    
    # 概要メトリクス表示
    _render_overview_metrics(df, latest_date, analysis_end_sunday)
    
    # パフォーマンスダッシュボード
    _render_performance_dashboard(df, target_dict, latest_date, analysis_end_sunday)
    
    # 週次推移グラフ
    _render_weekly_trends(df, target_dict)

def _validate_hospital_data(df: pd.DataFrame, latest_date: Optional[datetime]) -> bool:
    """病院データの検証"""
    if df.empty:
        ErrorHandler.display_warning("表示するデータがありません", "病院全体分析")
        return False
    
    if latest_date is None:
        ErrorHandler.display_warning("日付データが見つかりません", "病院全体分析")
        return False
    
    required_columns = ['手術実施日_dt', '実施診療科', 'is_gas_20min']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        ErrorHandler.display_error(
            ValueError(f"必要な列が不足しています: {missing_columns}"),
            "病院全体分析"
        )
        return False
    
    return True

def _render_overview_metrics(
    df: pd.DataFrame, 
    latest_date: datetime, 
    analysis_end_sunday: datetime
) -> None:
    """概要メトリクス表示"""
    excluded_days = (latest_date - analysis_end_sunday).days
    df_complete_weeks = df[df['手術実施日_dt'] <= analysis_end_sunday]
    total_records = len(df_complete_weeks)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 総レコード数", f"{total_records:,}件")
    
    with col2:
        st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d'))
    
    with col3:
        st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d'))
    
    with col4:
        st.metric("⚠️ 除外日数", f"{excluded_days}日")
    
    # 説明キャプション
    st.caption(
        f"💡 最新データが{latest_date.strftime('%A')}のため、"
        f"分析精度向上のため前の日曜日({analysis_end_sunday.strftime('%Y/%m/%d')})までを分析対象としています。"
    )
    
    st.markdown("---")

@with_error_handling("パフォーマンスダッシュボード表示")
def _render_performance_dashboard(
    df: pd.DataFrame, 
    target_dict: Dict, 
    latest_date: datetime, 
    analysis_end_sunday: datetime
) -> None:
    """診療科別パフォーマンスダッシュボードを描画"""
    
    st.subheader("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
    
    four_weeks_ago = analysis_end_sunday - pd.Timedelta(days=27)
    st.caption(f"🗓️ 分析対象期間: {four_weeks_ago.strftime('%Y/%m/%d')} ~ {analysis_end_sunday.strftime('%Y/%m/%d')}")
    
    try:
        perf_summary = ranking.get_department_performance_summary(df, target_dict, latest_date)
        
        if perf_summary.empty:
            st.info("診療科別パフォーマンスを計算する十分なデータがありません。")
            return
        
        if '達成率(%)' not in perf_summary.columns:
            st.warning("パフォーマンスデータに達成率の列が見つかりません。")
            return
        
        # パフォーマンスカード表示
        _render_performance_cards(perf_summary)
        
        # 詳細データテーブル
        with st.expander("詳細データテーブル"):
            st.dataframe(perf_summary, use_container_width=True)
            
    except Exception as e:
        ErrorHandler.display_error(e, "パフォーマンスダッシュボード生成")

def _render_performance_cards(perf_summary: pd.DataFrame) -> None:
    """パフォーマンスカードを描画"""
    sorted_perf = perf_summary.sort_values("達成率(%)", ascending=False)
    
    # 3列でカード表示
    cols = st.columns(3)
    
    for i, (index, row) in enumerate(sorted_perf.iterrows()):
        with cols[i % 3]:
            _create_department_card(row)

def _create_department_card(row: pd.Series) -> None:
    """診療科別カードを作成"""
    rate = row["達成率(%)"]
    color = _get_color_for_rate(rate)
    bar_width = min(rate, 100)
    
    html = f"""
    <div style="background-color: {color}1A; border-left: 5px solid {color}; 
                padding: 12px; border-radius: 5px; margin-bottom: 12px; height: 165px;">
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
        <div style="display: flex; justify-content: space-between; font-size: 1.1em; 
                    color: {color}; margin-top: 5px;">
            <span style="font-weight: bold;">達成率:</span>
            <span style="font-weight: bold;">{rate:.1f}%</span>
        </div>
        <div style="background-color: #e9ecef; border-radius: 5px; height: 6px; margin-top: 5px;">
            <div style="width: {bar_width}%; background-color: {color}; 
                        height: 6px; border-radius: 5px;"></div>
        </div>
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)

def _get_color_for_rate(rate: float) -> str:
    """達成率に応じた色を取得"""
    if rate >= 100:
        return "#28a745"  # 緑
    elif rate >= 80:
        return "#ffc107"  # 黄
    else:
        return "#dc3545"  # 赤

@with_error_handling("週次推移表示")
def _render_weekly_trends(df: pd.DataFrame, target_dict: Dict) -> None:
    """週次推移グラフを描画"""
    st.markdown("---")
    st.subheader("📈 全身麻酔手術件数 週次推移（完全週データ）")
    
    try:
        summary = weekly.get_summary(df, use_complete_weeks=True)
        
        if summary.empty:
            st.warning("📊 週次データが生成できませんでした")
            return
        
        with chart_container.create_chart_container():
            fig = trend_plots.create_weekly_summary_chart(summary, "", target_dict)
            st.plotly_chart(fig, use_container_width=True)
            
        # データ期間の表示
        if not summary.empty:
            period_start = summary.index.min()
            period_end = summary.index.max()
            weeks_count = len(summary)
            
            st.caption(f"""
            📊 表示期間: {weeks_count}週間のデータ 
            ({period_start.strftime('%Y/%m/%d')} ～ {period_end.strftime('%Y/%m/%d')})
            """)
            
    except Exception as e:
        ErrorHandler.display_error(e, "週次推移グラフ生成")