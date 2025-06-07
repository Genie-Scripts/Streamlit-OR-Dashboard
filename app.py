# app.py
import streamlit as st
import pandas as pd
import traceback
from datetime import datetime
import pytz

# --- モジュールのインポート ---
from config import style_config, target_loader
from data_processing import loader
from analysis import weekly as weekly_analyzer, periodic as periodic_analyzer, ranking as ranking_analyzer, surgeon as surgeon_analyzer, forecasting as forecast_analyzer
from plotting import trend_plots, generic_plots
from reporting import csv_exporter, pdf_exporter
from utils import date_helpers

# --- ページ設定 (最初に一度だけ呼び出す) ---
st.set_page_config(
    page_title="🏥 手術分析ダッシュボード",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- カスタムCSSの読み込み ---
style_config.load_dashboard_css()


# --- セッション状態の初期化 ---
def initialize_session_state():
    """セッション状態を初期化する"""
    if 'processed_df' not in st.session_state:
        st.session_state['processed_df'] = None
    if 'target_dict' not in st.session_state:
        st.session_state['target_dict'] = {}
    if 'latest_date' not in st.session_state:
        st.session_state['latest_date'] = None
    if 'current_view' not in st.session_state:
        st.session_state['current_view'] = 'ダッシュボード'

# --- サイドバーの描画 ---
def render_sidebar():
    """サイドバーを描画する"""
    with st.sidebar:
        st.title("🏥 手術分析")
        st.markdown("---")

        # ナビゲーション
        views = ["ダッシュボード", "データアップロード", "病院全体分析", "診療科別分析", "術者分析", "将来予測"]
        st.session_state['current_view'] = st.radio("📍 ナビゲーション", views, key="navigation")

        st.markdown("---")

        # データ状態
        if st.session_state.get('processed_df') is not None and not st.session_state['processed_df'].empty:
            st.success("✅ データ読み込み済み")
            st.write(f"📊 総レコード数: {len(st.session_state['processed_df']):,}")
            if st.session_state.get('latest_date'):
                st.write(f"📅 最新日付: {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
        else:
            st.warning("⚠️ データ未読み込み")

        # 目標データ状態
        if st.session_state.get('target_dict'):
            st.success("🎯 目標データ設定済み")
            st.write(f"診療科数: {len(st.session_state['target_dict'])}")
        else:
            st.info("目標データ未設定")

        st.markdown("---")
        st.info("Version: 4.0 (Refactored)")
        jst = pytz.timezone('Asia/Tokyo')
        st.write(f"現在時刻: {datetime.now(jst).strftime('%H:%M:%S')}")


# --- 各ページの描画関数 ---

def render_upload_page():
    """データアップロードページを描画"""
    st.header("📤 データアップロード")
    with st.expander("📋 アップロード手順", expanded=True):
        st.markdown("""
        1. **基礎データ**: 手術実績データ(CSV)をアップロードしてください。
        2. **目標データ (任意)**: 診療科別の目標件数データ(CSV)をアップロードしてください。
        3. **追加データ (任意)**: 基礎データ以降の最新データがあればアップロードしてください。
        """)

    base_file = st.file_uploader("基礎データ (CSV)", type="csv", key="base_uploader")
    update_files = st.file_uploader("追加データ (CSV)", type="csv", accept_multiple_files=True, key="update_uploader")
    target_file = st.file_uploader("目標データ (CSV)", type="csv", key="target_uploader")

    if st.button("データ処理を実行", type="primary"):
        with st.spinner("データ処理中..."):
            try:
                # データ読み込みと結合
                df = loader.load_and_merge_files(base_file, update_files)
                if not df.empty:
                    st.session_state['processed_df'] = df
                    st.session_state['latest_date'] = df['手術実施日_dt'].max()
                    st.success(f"データ処理完了。{len(df)}件のレコードが読み込まれました。")
                    st.dataframe(df.head())
                else:
                    st.warning("有効なデータがありませんでした。")

                # 目標データの読み込み
                if target_file:
                    st.session_state['target_dict'] = target_loader.load_target_file(target_file)
                    st.success(f"目標データを読み込みました。{len(st.session_state['target_dict'])}件の診療科目標を設定。")

            except Exception as e:
                st.error("データ処理中にエラーが発生しました。")
                st.error(f"エラー詳細: {e}")
                st.code(traceback.format_exc())

def render_dashboard_page():
    """ダッシュボードページを描画"""
    st.title("🏠 ダッシュボード")
    if st.session_state['processed_df'] is None:
        st.warning("データをアップロードしてください。")
        return

    df = st.session_state['processed_df']
    latest_date = st.session_state['latest_date']
    target_dict = st.session_state['target_dict']

    # KPIサマリー
    kpi_summary = ranking_analyzer.get_kpi_summary(df, latest_date)
    generic_plots.display_kpi_metrics(kpi_summary)

    # 病院全体の週次トレンド
    st.header("📈 病院全体 週次トレンド")
    use_complete_weeks = st.toggle("完全週データで分析", value=True, help="週の途中でデータが途切れる不正確さを排除し、月曜〜日曜の完全な週単位で分析します。")

    weekly_summary = weekly_analyzer.get_summary(df, use_complete_weeks=use_complete_weeks)

    if not weekly_summary.empty:
        fig = trend_plots.create_weekly_summary_chart(weekly_summary, "病院全体 週次推移", target_dict)
        st.plotly_chart(fig, use_container_width=True)

    # 診療科別ランキング
    st.header("🏆 診療科別ランキング (直近90日)")
    if not target_dict:
        st.info("目標データをアップロードすると、診療科別の目標達成率ランキングが表示されます。")
    else:
        filtered_df = date_helpers.filter_by_period(df, latest_date, "直近90日")
        ranking_data = ranking_analyzer.calculate_achievement_rates(filtered_df, target_dict)
        if not ranking_data.empty:
            fig_rank = generic_plots.plot_achievement_ranking(ranking_data, 15)
            st.plotly_chart(fig_rank, use_container_width=True)
            with st.expander("詳細データ"):
                st.dataframe(ranking_data)
                csv_exporter.render_download_button(ranking_data, "ranking", "90_days")


def render_hospital_page():
    """病院全体分析ページを描画"""
    st.title("🏥 病院全体分析")
    if st.session_state['processed_df'] is None:
        st.warning("データをアップロードしてください。")
        return

    df = st.session_state['processed_df']
    target_dict = st.session_state['target_dict']

    period_type = st.radio("表示単位", ["週次", "月次", "四半期"], horizontal=True, key="hospital_period")

    if period_type == "週次":
        use_complete_weeks = st.toggle("完全週データで分析", value=True)
        summary = weekly_analyzer.get_summary(df, use_complete_weeks=use_complete_weeks)
        fig = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
    elif period_type == "月次":
        summary = periodic_analyzer.get_monthly_summary(df)
        fig = trend_plots.create_monthly_summary_chart(summary, "病院全体 月次推移", target_dict)
    else: # 四半期
        summary = periodic_analyzer.get_quarterly_summary(df)
        fig = trend_plots.create_quarterly_summary_chart(summary, "病院全体 四半期推移", target_dict)

    if not summary.empty:
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("詳細データとエクスポート"):
            st.dataframe(summary)
            csv_exporter.render_download_button(summary, "hospital_summary", period_type)
            pdf_exporter.add_pdf_report_button("hospital", period_type, summary, fig, target_dict=target_dict)

def render_department_page():
    """診療科別分析ページを描画"""
    st.title("🩺 診療科別分析")
    if st.session_state['processed_df'] is None:
        st.warning("データをアップロードしてください。")
        return

    df = st.session_state['processed_df']
    target_dict = st.session_state['target_dict']
    departments = sorted(df["実施診療科"].dropna().unique())
    selected_dept = st.selectbox("分析する診療科を選択", departments)

    period_type = st.radio("表示単位", ["週次", "月次", "四半期"], horizontal=True, key="dept_period")

    if period_type == "週次":
        use_complete_weeks = st.toggle("完全週データで分析", value=True)
        summary = weekly_analyzer.get_summary(df, department=selected_dept, use_complete_weeks=use_complete_weeks)
        fig = trend_plots.create_weekly_dept_chart(summary, selected_dept, target_dict)
    elif period_type == "月次":
        summary = periodic_analyzer.get_monthly_summary(df, department=selected_dept)
        fig = trend_plots.create_monthly_dept_chart(summary, selected_dept, target_dict)
    else: # 四半期
        summary = periodic_analyzer.get_quarterly_summary(df, department=selected_dept)
        fig = trend_plots.create_quarterly_dept_chart(summary, selected_dept, target_dict)

    if not summary.empty:
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("詳細データとエクスポート"):
            st.dataframe(summary)
            csv_exporter.render_download_button(summary, "dept_summary", period_type, department=selected_dept)
            pdf_exporter.add_pdf_report_button("department", period_type, summary, fig, department=selected_dept, target_dict=target_dict)

def render_surgeon_page():
    """術者分析ページを描画"""
    st.title("👨‍⚕️ 術者分析")
    if st.session_state['processed_df'] is None:
        st.warning("データをアップロードしてください。")
        return

    df = st.session_state['processed_df']

    # 術者データの展開（キャッシュ活用）
    with st.spinner("術者データを準備中..."):
        expanded_df = surgeon_analyzer.get_expanded_surgeon_df(df)

    st.info(f"1つの手術に複数の術者がいる場合、それぞれカウントされます。延べ術者数: {len(expanded_df)}件")

    departments = ["全診療科"] + sorted(df["実施診療科"].dropna().unique())
    selected_dept = st.selectbox("診療科で絞り込み", departments)

    top_n = st.slider("表示する術者数（上位）", 5, 50, 15)

    if selected_dept != "全診療科":
        target_df = expanded_df[expanded_df['実施診療科'] == selected_dept]
    else:
        target_df = expanded_df

    summary_df = surgeon_analyzer.get_surgeon_summary(target_df)

    if not summary_df.empty:
        fig = generic_plots.plot_surgeon_ranking(summary_df, top_n, selected_dept)
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("詳細データ"):
            st.dataframe(summary_df)
            csv_exporter.render_download_button(summary_df, "surgeon_ranking", "all_time", department=selected_dept)


def render_prediction_page():
    """将来予測ページを描画"""
    st.title("🔮 将来予測")
    if st.session_state['processed_df'] is None:
        st.warning("データをアップロードしてください。")
        return

    df = st.session_state['processed_df']
    latest_date = st.session_state['latest_date']

    tab1, tab2, tab3 = st.tabs(["将来予測", "モデル検証", "パラメータ最適化"])

    with tab1:
        forecast_analyzer.create_future_prediction_tab(df, latest_date)
    with tab2:
        forecast_analyzer.create_model_validation_tab(df, latest_date)
    with tab3:
        forecast_analyzer.create_parameter_optimization_tab(df, latest_date)


# --- メイン実行部 ---
def main():
    """アプリケーションのメイン関数"""
    initialize_session_state()
    render_sidebar()

    page_map = {
        "ダッシュボード": render_dashboard_page,
        "データアップロード": render_upload_page,
        "病院全体分析": render_hospital_page,
        "診療科別分析": render_department_page,
        "術者分析": render_surgeon_page,
        "将来予測": render_prediction_page,
    }

    # 選択されたページの描画関数を実行
    render_function = page_map.get(st.session_state['current_view'])
    if render_function:
        render_function()
    else:
        st.error("ページが見つかりません。")

if __name__ == "__main__":
    main()