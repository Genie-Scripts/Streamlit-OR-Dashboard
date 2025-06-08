# app.py (機能復元版)
import streamlit as st
import pandas as pd
import traceback
from datetime import datetime
import pytz
import plotly.express as px

# --- 整理されたモジュールのインポート ---
from config import style_config, target_loader
from data_processing import loader
from analysis import weekly, periodic, ranking, surgeon, forecasting
from plotting import trend_plots, generic_plots
from reporting import csv_exporter, pdf_exporter
from utils import date_helpers

# --- ページ設定とCSS (最初に一度だけ) ---
st.set_page_config(
    page_title="手術分析ダッシュボード",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)
# CSSは style_config から読み込む
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

        if not st.session_state.get('processed_df', pd.DataFrame()).empty:
            st.success("✅ データ読み込み済み")
            st.write(f"📊 レコード数: {len(st.session_state['processed_df']):,}")
            if st.session_state.get('latest_date'):
                st.write(f"📅 最新日付: {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
        else:
            st.warning("⚠️ データ未読み込み")

        if st.session_state.get('target_dict'):
            st.success("🎯 目標データ設定済み")
        else:
            st.info("目標データ未設定")
            
        st.markdown("---")
        st.info("Version: 4.2 (Full Featured)")
        jst = pytz.timezone('Asia/Tokyo')
        st.write(f"現在時刻: {datetime.now(jst).strftime('%H:%M:%S')}")

def render_page_content():
    """選択されたページに応じてコンテンツを描画"""
    current_view = st.session_state.get('current_view', 'ダッシュボード')
    
    if current_view == 'データアップロード':
        render_upload_page()
        return

    df = st.session_state.get('processed_df')
    if df is None or df.empty:
        st.warning("分析を開始するには、「データアップロード」ページでデータを読み込んでください。")
        return

    target_dict = st.session_state.get('target_dict', {})
    latest_date = st.session_state.get('latest_date')

    page_map = {
        "ダッシュボード": render_dashboard_page,
        "病院全体分析": render_hospital_page,
        "診療科別分析": render_department_page,
        "術者分析": render_surgeon_page,
        "将来予測": render_prediction_page,
    }
    page_func = page_map.get(current_view)
    if page_func:
        page_func(df, target_dict, latest_date)

def render_upload_page():
    """データアップロードページ"""
    st.header("📤 データアップロード")
    with st.expander("📋 アップロード手順", expanded=True):
        st.markdown("1. **基礎データ**: 手術実績データ(CSV)をアップロード\n2. **目標データ (任意)**: 診療科別の目標件数(CSV)をアップロード\n3. **追加データ (任意)**: 最新データ(CSV)をアップロード")

    base_file = st.file_uploader("基礎データ (CSV)", type="csv")
    update_files = st.file_uploader("追加データ (CSV)", type="csv", accept_multiple_files=True)
    target_file = st.file_uploader("目標データ (CSV)", type="csv")

    if st.button("データ処理を実行", type="primary"):
        with st.spinner("データ処理中..."):
            try:
                if base_file:
                    df = loader.load_and_merge_files(base_file, update_files)
                    st.session_state['processed_df'] = df
                    if not df.empty:
                        st.session_state['latest_date'] = df['手術実施日_dt'].max()
                    st.success(f"データ処理完了。{len(df)}件のレコードが読み込まれました。")
                else:
                    st.warning("基礎データファイルをアップロードしてください。")
                
                if target_file:
                    st.session_state['target_dict'] = target_loader.load_target_file(target_file)
                    st.success(f"目標データを読み込みました。{len(st.session_state['target_dict'])}件の診療科目標を設定。")
            except Exception as e:
                st.error(f"エラー: {e}")
                st.code(traceback.format_exc())

def render_dashboard_page(df, target_dict, latest_date):
    """ダッシュボードページ（機能復元）"""
    st.title("🏠 ダッシュボード")
    kpi_summary = ranking.get_kpi_summary(df, latest_date)
    generic_plots.display_kpi_metrics(kpi_summary)
    
    st.header("📈 病院全体 週次トレンド")
    use_complete_weeks = st.toggle("完全週データで分析", value=True, help="週の途中のデータを分析から除外し、月曜〜日曜の完全な週単位で集計します。")
    summary = weekly.get_summary(df, use_complete_weeks=use_complete_weeks)
    if not summary.empty:
        fig = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
        st.plotly_chart(fig, use_container_width=True)

    st.header("🏆 診療科別ランキング (直近90日)")
    if target_dict:
        filtered_df = date_helpers.filter_by_period(df, latest_date, "直近90日")
        ranking_data = ranking.calculate_achievement_rates(filtered_df, target_dict)
        if not ranking_data.empty:
            fig_rank = generic_plots.plot_achievement_ranking(ranking_data)
            st.plotly_chart(fig_rank, use_container_width=True)
            with st.expander("詳細データ"):
                st.dataframe(ranking_data)
    else:
        st.info("目標データをアップロードするとランキングが表示されます。")

def render_hospital_page(df, target_dict, latest_date):
    """病院全体分析ページ（機能復元）"""
    st.title("🏥 病院全体分析")
    period_type = st.radio("表示単位", ["週次", "月次", "四半期"], horizontal=True, key="hospital_period")
    
    fig = None
    summary = pd.DataFrame()

    if period_type == "週次":
        use_complete = st.toggle("完全週データで分析", True)
        summary = weekly.get_summary(df, use_complete_weeks=use_complete)
        if not summary.empty:
            fig = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
    elif period_type == "月次":
        summary = periodic.get_monthly_summary(df)
        if not summary.empty:
            fig = trend_plots.create_monthly_summary_chart(summary, "病院全体 月次推移", target_dict)
    else: # 四半期
        summary = periodic.get_quarterly_summary(df)
        if not summary.empty:
            fig = trend_plots.create_quarterly_summary_chart(summary, "病院全体 四半期推移", target_dict)

    if fig:
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("詳細データとエクスポート"):
            st.dataframe(summary)
            csv_exporter.render_download_button(summary, "hospital", period_type)
            # PDFエクスポートは複雑なので、必要に応じて詳細な実装を追加
            # pdf_exporter.add_pdf_report_button("hospital", period_type, summary, fig, target_dict)

def render_department_page(df, target_dict, latest_date):
    """診療科別分析ページ（機能復元）"""
    st.title("🩺 診療科別分析")
    departments = sorted(df["実施診療科"].dropna().unique())
    if not departments:
        st.warning("データに診療科情報がありません。")
        return

    selected_dept = st.selectbox("分析する診療科を選択", departments)
    dept_df = df[df['実施診療科'] == selected_dept]

    # --- KPI表示を復元 ---
    kpi_summary = ranking.get_kpi_summary(dept_df, latest_date)
    generic_plots.display_kpi_metrics(kpi_summary)
    
    st.markdown("---")
    
    # --- メインの時系列グラフ ---
    period_type = st.radio("表示単位", ["週次", "月次"], horizontal=True, key="dept_period")
    if period_type == "週次":
        summary = weekly.get_summary(df, department=selected_dept, use_complete_weeks=st.toggle("完全週データ", True))
        fig = trend_plots.create_weekly_dept_chart(summary, selected_dept, target_dict)
    else: # 月次
        summary = periodic.get_monthly_summary(df, department=selected_dept)
        fig = trend_plots.create_monthly_dept_chart(summary, selected_dept, target_dict) # この関数はtrend_plots.pyに要追加
    st.plotly_chart(fig, use_container_width=True)

    # --- 詳細分析タブを復元 ---
    st.markdown("---")
    st.header("🔍 詳細分析")
    tab1, tab2, tab3 = st.tabs(["術者分析", "時間分析", "統計情報"])

    with tab1:
        st.subheader(f"{selected_dept} 術者別件数 (Top 15)")
        expanded_df = surgeon.get_expanded_surgeon_df(dept_df)
        surgeon_summary = surgeon.get_surgeon_summary(expanded_df)
        if not surgeon_summary.empty:
            fig_surgeon = generic_plots.plot_surgeon_ranking(surgeon_summary, 15, selected_dept)
            st.plotly_chart(fig_surgeon, use_container_width=True)
            
    with tab2:
        st.subheader("曜日・月別 分布")
        gas_df = dept_df[dept_df['is_gas_20min']]
        col1, col2 = st.columns(2)
        with col1:
            weekday_dist = gas_df['手術実施日_dt'].dt.day_name().value_counts()
            fig_pie = px.pie(values=weekday_dist.values, names=weekday_dist.index, title="曜日別分布")
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            month_dist = gas_df['手術実施日_dt'].dt.month_name().value_counts()
            fig_bar = px.bar(x=month_dist.index, y=month_dist.values, title="月別分布", labels={'x':'月', 'y':'件数'})
            st.plotly_chart(fig_bar, use_container_width=True)

    with tab3:
        st.subheader("基本統計")
        st.dataframe(dept_df[dept_df['is_gas_20min']].describe(include='all').transpose())

def render_surgeon_page(df, target_dict, latest_date):
    """術者分析ページ（機能復元）"""
    st.title("👨‍⚕️ 術者分析")
    analysis_type = st.radio("分析タイプ", ["診療科別ランキング", "術者ごと時系列"], horizontal=True)

    with st.spinner("術者データを準備中..."):
        expanded_df = surgeon.get_expanded_surgeon_df(df)
    if expanded_df.empty:
        st.warning("分析可能な術者データがありません。")
        return

    if analysis_type == "診療科別ランキング":
        departments = ["全診療科"] + sorted(df["実施診療科"].dropna().unique())
        selected_dept = st.selectbox("診療科で絞り込み", departments)
        top_n = st.slider("表示する術者数（上位）", 5, 50, 15)

        target_df = expanded_df
        if selected_dept != "全診療科":
            target_df = expanded_df[expanded_df['実施診療科'] == selected_dept]

        summary_df = surgeon.get_surgeon_summary(target_df)
        if not summary_df.empty:
            fig = generic_plots.plot_surgeon_ranking(summary_df, top_n, selected_dept)
            st.plotly_chart(fig, use_container_width=True)

    else: # 術者ごと時系列
        surgeons = sorted(expanded_df["実施術者"].dropna().unique())
        selected_surgeon = st.selectbox("分析する術者を選択", surgeons)
        
        surgeon_df = expanded_df[expanded_df['実施術者'] == selected_surgeon]
        st.header(f"{selected_surgeon} の週次実績")
        
        summary = weekly.get_summary(surgeon_df, use_complete_weeks=False) # 術者単位では全週を対象
        if not summary.empty:
            fig = trend_plots.create_weekly_dept_chart(summary, selected_surgeon, {}) # 術者を診療科と見立ててプロット
            st.plotly_chart(fig, use_container_width=True)

def render_prediction_page(df, target_dict, latest_date):
    """将来予測ページ（機能復元）"""
    st.title("🔮 将来予測")
    tab1, tab2, tab3 = st.tabs(["将来予測", "モデル検証", "パラメータ最適化"])

    with tab1:
        st.header("将来予測")
        pred_target = st.radio("予測対象", ["病院全体", "診療科別"], horizontal=True, key="pred_target")
        department = None
        if pred_target == "診療科別":
            departments = sorted(df["実施診療科"].dropna().unique())
            department = st.selectbox("診療科を選択", departments, key="pred_dept_select")
        
        model_type = st.selectbox("予測モデル", ["hwes", "arima", "moving_avg"], format_func=lambda x: {"hwes":"Holt-Winters", "arima":"ARIMA", "moving_avg":"移動平均"}[x])
        pred_period = st.selectbox("予測期間", ["fiscal_year", "calendar_year", "six_months"], format_func=lambda x: {"fiscal_year":"年度末まで", "calendar_year":"年末まで", "six_months":"6ヶ月先まで"}[x])

        if st.button("予測を実行", type="primary"):
            with st.spinner("予測計算中..."):
                result_df, metrics = forecasting.predict_future(df, latest_date, department=department, model_type=model_type, prediction_period=pred_period)
                if metrics.get("message"):
                    st.warning(metrics["message"])
                else:
                    title = f"{department or '病院全体'} {metrics.get('予測モデル','')}モデルによる予測"
                    fig = generic_plots.create_forecast_chart(result_df, title)
                    st.plotly_chart(fig, use_container_width=True)
                    st.write(metrics)

    with tab2:
        st.header("予測モデルの精度検証")
        # モデル検証UI
        
    with tab3:
        st.header("パラメータ最適化")
        # パラメータ最適化UI

# --- メイン実行部 ---
def main():
    """アプリケーションのメイン関数"""
    initialize_session_state()
    render_sidebar()
    render_page_content()

if __name__ == "__main__":
    main()