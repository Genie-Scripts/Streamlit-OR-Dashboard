# app.py
import streamlit as st
import pandas as pd
import traceback
from datetime import datetime
import pytz

# --- 整理されたモジュールのインポート ---
from config import style_config, target_loader
from data_processing import loader
from analysis import weekly, periodic, ranking, surgeon, forecasting
from plotting import trend_plots, generic_plots
from reporting import csv_exporter, pdf_exporter

# --- ページ設定とCSS (最初に一度だけ) ---
st.set_page_config(
    page_title="手術分析ダッシュボード",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)
style_config.load_dashboard_css()

# --- セッション状態の初期化 ---
def initialize_session_state():
    """セッション状態を初期化"""
    if 'processed_df' not in st.session_state:
        st.session_state['processed_df'] = pd.DataFrame()
    if 'target_dict' not in st.session_state:
        st.session_state['target_dict'] = {}
    if 'latest_date' not in st.session_state:
        st.session_state['latest_date'] = None
    if 'current_view' not in st.session_state:
        st.session_state['current_view'] = 'ダッシュボード'

# --- UI描画関数 ---
def render_sidebar():
    """サイドバーを描画"""
    with st.sidebar:
        st.title("🏥 手術分析")
        st.markdown("---")
        views = ["ダッシュボード", "データアップロード", "病院全体分析", "診療科別分析", "術者分析", "将来予測"]
        st.session_state['current_view'] = st.radio("📍 ナビゲーション", views, key="navigation")
        st.markdown("---")

        if not st.session_state['processed_df'].empty:
            st.success("✅ データ読み込み済み")
            st.write(f"📊 レコード数: {len(st.session_state['processed_df']):,}")
            st.write(f"📅 最新日付: {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
        else:
            st.warning("⚠️ データ未読み込み")

        st.info(f"Version: 4.0 (Refactored)")

def render_page_content():
    """選択されたページに応じてコンテンツを描画"""
    df = st.session_state.processed_df
    target_dict = st.session_state.target_dict
    latest_date = st.session_state.latest_date

    if st.session_state['current_view'] == 'データアップロード':
        render_upload_page()
        return

    # データがなければここで終了
    if df.empty:
        st.warning("分析を開始するには、「データアップロード」ページでデータを読み込んでください。")
        return

    page_map = {
        "ダッシュボード": render_dashboard_page,
        "病院全体分析": render_hospital_page,
        "診療科別分析": render_department_page,
        "術者分析": render_surgeon_page,
        "将来予測": render_prediction_page,
    }
    page_func = page_map.get(st.session_state['current_view'])
    if page_func:
        page_func(df, target_dict, latest_date)

def render_upload_page():
    # (app.pyに記載していた元のUIロジックをここに配置)
    st.header("📤 データアップロード")
    base_file = st.file_uploader("基礎データ (CSV)", type="csv")
    update_files = st.file_uploader("追加データ (CSV)", type="csv", accept_multiple_files=True)
    target_file = st.file_uploader("目標データ (CSV)", type="csv")

    if st.button("データ処理を実行", type="primary"):
        with st.spinner("データ処理中..."):
            try:
                df = loader.load_and_merge_files(base_file, update_files)
                st.session_state['processed_df'] = df
                st.session_state['latest_date'] = df['手術実施日_dt'].max()
                st.success(f"データ処理完了。{len(df)}件")
                if target_file:
                    st.session_state['target_dict'] = target_loader.load_target_file(target_file)
                    st.success("目標データを読み込みました。")
            except Exception as e:
                st.error(f"エラー: {e}")

def render_dashboard_page(df, target_dict, latest_date):
    st.title("🏠 ダッシュボード")
    kpi_summary = ranking.get_kpi_summary(df, latest_date)
    generic_plots.display_kpi_metrics(kpi_summary)
    
    st.header("📈 病院全体 週次トレンド")
    use_complete_weeks = st.toggle("完全週データで分析", value=True)
    summary = weekly.get_summary(df, use_complete_weeks=use_complete_weeks)
    fig = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
    st.plotly_chart(fig, use_container_width=True)

    st.header("🏆 診療科別ランキング (直近90日)")
    if target_dict:
        filtered_df = df[df['手術実施日_dt'] >= (latest_date - pd.Timedelta(days=89))]
        ranking_data = ranking.calculate_achievement_rates(filtered_df, target_dict)
        fig_rank = generic_plots.plot_achievement_ranking(ranking_data)
        st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.info("目標データをアップロードするとランキングが表示されます。")

def render_hospital_page(df, target_dict, latest_date):
    st.title("🏥 病院全体分析")
    # (app.pyに記載していた元のUIロジックをここに配置)
    period_type = st.radio("表示単位", ["週次", "月次", "四半期"], horizontal=True)
    if period_type == "週次":
        summary = weekly.get_summary(df, use_complete_weeks=st.toggle("完全週データ", True))
        fig = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
    # ... 月次・四半期も同様に ...
    st.plotly_chart(fig, use_container_width=True)
    
def render_department_page(df, target_dict, latest_date):
    st.title("🩺 診療科別分析")
    # (app.pyに記載していた元のUIロジックをここに配置)
    
def render_surgeon_page(df, target_dict, latest_date):
    st.title("👨‍⚕️ 術者分析")
    # (app.pyに記載していた元のUIロジックをここに配置)

def render_prediction_page(df, target_dict, latest_date):
    st.title("🔮 将来予測")
    # (app.pyに記載していた元のUIロジックをここに配置)
    
# --- メイン実行部 ---
def main():
    initialize_session_state()
    render_sidebar()
    render_page_content()

if __name__ == "__main__":
    main()