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
    page_title="手術分析ダッシュボード", page_icon="🏥", layout="wide", initial_sidebar_state="expanded"
)
style_config.load_dashboard_css()

# --- セッション状態の初期化 ---
def initialize_session_state():
    if 'processed_df' not in st.session_state: st.session_state['processed_df'] = pd.DataFrame()
    if 'target_dict' not in st.session_state: st.session_state['target_dict'] = {}
    if 'latest_date' not in st.session_state: st.session_state['latest_date'] = None
    if 'current_view' not in st.session_state: st.session_state['current_view'] = 'ダッシュボード'

# --- UI描画関数 ---
def render_sidebar():
    with st.sidebar:
        st.title("🏥 手術分析")
        st.markdown("---")
        views = ["ダッシュボード", "データアップロード", "病院全体分析", "診療科別分析", "術者分析", "将来予測"]
        st.session_state['current_view'] = st.radio("📍 ナビゲーション", views, key="navigation")
        st.markdown("---")
        if not st.session_state.get('processed_df', pd.DataFrame()).empty:
            st.success("✅ データ読み込み済み")
            st.write(f"📊 レコード数: {len(st.session_state['processed_df']):,}")
            if st.session_state.get('latest_date'): st.write(f"📅 最新日付: {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
        else: st.warning("⚠️ データ未読み込み")
        if st.session_state.get('target_dict'): st.success("🎯 目標データ設定済み")
        else: st.info("目標データ未設定")
        st.markdown("---")
        st.info("Version: 5.2 (Attribute Fix)")
        jst = pytz.timezone('Asia/Tokyo')
        st.write(f"現在時刻: {datetime.now(jst).strftime('%H:%M:%S')}")

def render_page_content():
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
    if page_func: page_func(df, target_dict, latest_date)

def render_upload_page():
    st.header("📤 データアップロード")
    base_file = st.file_uploader("基礎データ (CSV)", type="csv")
    update_files = st.file_uploader("追加データ (CSV)", type="csv", accept_multiple_files=True)
    target_file = st.file_uploader("目標データ (CSV)", type="csv")
    if st.button("データ処理を実行", type="primary"):
        with st.spinner("データ処理中..."):
            try:
                if base_file:
                    df = loader.load_and_merge_files(base_file, update_files)
                    st.session_state['processed_df'] = df
                    if not df.empty: st.session_state['latest_date'] = df['手術実施日_dt'].max()
                    st.success(f"データ処理完了。{len(df)}件のレコードが読み込まれました。")
                else: st.warning("基礎データファイルをアップロードしてください。")
                if target_file:
                    st.session_state['target_dict'] = target_loader.load_target_file(target_file)
                    st.success(f"目標データを読み込みました。{len(st.session_state['target_dict'])}件の診療科目標を設定。")
            except Exception as e: st.error(f"エラー: {e}"); st.code(traceback.format_exc())

def render_dashboard_page(df, target_dict, latest_date):
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
    else: st.info("目標データをアップロードするとランキングが表示されます。")


def render_hospital_page(df, target_dict, latest_date):
    st.title("🏥 病院全体分析 (完全週データ)")
    
    analysis_end_sunday = weekly.get_analysis_end_date(latest_date)
    if analysis_end_sunday is None:
        st.warning("分析可能な日付データがありません。"); return
        
    excluded_days = (latest_date - analysis_end_sunday).days
    df_complete_weeks = df[df['手術実施日_dt'] <= analysis_end_sunday]
    total_records = len(df_complete_weeks)
    
    # ...(ヘッダーのメトリック表示は変更なし)...
    
    st.markdown("---")
    
    st.subheader("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
    # ...(分析期間の表示は変更なし)...

    perf_summary = ranking.get_department_performance_summary(df, target_dict, latest_date)

    if not perf_summary.empty:
        rate_col_name = '達成率(%)' if '達成率(%)' in perf_summary.columns else '達成率'

        if rate_col_name in perf_summary.columns:
            sorted_perf = perf_summary.sort_values(rate_col_name, ascending=False)
            
            def get_color_for_rate(rate):
                if rate >= 100: return "#28a745"
                if rate >= 80: return "#ffc107"
                return "#dc3545"

            cols = st.columns(3)
            # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
            # ★ ここが修正された箇所です ★
            # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
            for i, row_tuple in enumerate(sorted_perf.itertuples(index=False)):
                with cols[i % 3]:
                    # itertuplesの行を辞書に変換して、元の列名（文字列）で安全に値を取得
                    row = row_tuple._asdict()

                    rate = row.get(rate_col_name, 0)
                    color = get_color_for_rate(rate)
                    bar_width = min(rate, 100)
                    
                    # .get()メソッドで安全に値を取得
                    dept_name = row.get("診療科", "N/A")
                    avg_4_weeks = row.get("4週平均", 0)
                    latest_cases = row.get("直近週実績", 0)
                    target_val = row.get("週次目標", 0)

                    html = f"""
                    <div style="background-color: {color}1A; border-left: 5px solid {color}; padding: 12px; border-radius: 5px; margin-bottom: 12px; height: 165px;">
                        <h5 style="margin: 0 0 10px 0; font-weight: bold; color: #333;">{dept_name}</h5>
                        <div style="display: flex; justify-content: space-between; font-size: 0.9em;"><span>4週平均:</span><span style="font-weight: bold;">{avg_4_weeks:.1f} 件</span></div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.9em;"><span>直近週実績:</span><span style="font-weight: bold;">{latest_cases:.0f} 件</span></div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #666;"><span>目標:</span><span>{target_val:.1f} 件</span></div>
                        <div style="display: flex; justify-content: space-between; font-size: 1.1em; color: {color}; margin-top: 5px;">
                            <span style="font-weight: bold;">達成率:</span><span style="font-weight: bold;">{rate:.1f}%</span>
                        </div>
                        <div style="background-color: #e9ecef; border-radius: 5px; height: 6px; margin-top: 5px;">
                            <div style="width: {bar_width}%; background-color: {color}; height: 6px; border-radius: 5px;"></div>
                        </div>
                    </div>
                    """
                    st.markdown(html, unsafe_allow_html=True)
            
            with st.expander("詳細データテーブル"): st.dataframe(sorted_perf)
        else:
            st.warning("パフォーマンスデータに達成率の列が見つかりません。")
    else:
        st.info("診療科別パフォーマンスを計算する十分なデータがありません。")
        
    st.markdown("---")
    st.subheader("📈 全身麻酔手術件数 週次推移（完全週データ）")
    summary = weekly.get_summary(df, use_complete_weeks=True)
    if not summary.empty:
        fig = trend_plots.create_weekly_summary_chart(summary, "", target_dict)
        st.plotly_chart(fig, use_container_width=True)


def render_department_page(df, target_dict, latest_date):
    st.title("🩺 診療科別分析")
    departments = sorted(df["実施診療科"].dropna().unique())
    if not departments: st.warning("データに診療科情報がありません。"); return
    selected_dept = st.selectbox("分析する診療科を選択", departments)
    dept_df = df[df['実施診療科'] == selected_dept]
    kpi_summary = ranking.get_kpi_summary(dept_df, latest_date)
    generic_plots.display_kpi_metrics(kpi_summary)
    st.markdown("---")
    summary = weekly.get_summary(df, department=selected_dept, use_complete_weeks=st.toggle("完全週データ", True))
    fig = trend_plots.create_weekly_dept_chart(summary, selected_dept, target_dict)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")
    st.header("🔍 詳細分析")
    tab1, tab2, tab3, tab4 = st.tabs(["術者分析", "時間分析", "統計情報", "累積実績"])
    with tab1:
        st.subheader(f"{selected_dept} 術者別件数 (Top 15)")
        expanded_df = surgeon.get_expanded_surgeon_df(dept_df)
        surgeon_summary = surgeon.get_surgeon_summary(expanded_df)
        if not surgeon_summary.empty: st.plotly_chart(generic_plots.plot_surgeon_ranking(surgeon_summary, 15, selected_dept), use_container_width=True)
    with tab2:
        st.subheader("曜日・月別 分布")
        gas_df = dept_df[dept_df['is_gas_20min']]
        if not gas_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                weekday_dist = gas_df['手術実施日_dt'].dt.day_name().value_counts()
                st.plotly_chart(px.pie(values=weekday_dist.values, names=weekday_dist.index, title="曜日別分布"), use_container_width=True)
            with col2:
                month_dist = gas_df['手術実施日_dt'].dt.month_name().value_counts()
                st.plotly_chart(px.bar(x=month_dist.index, y=month_dist.values, title="月別分布", labels={'x':'月', 'y':'件数'}), use_container_width=True)
    with tab3:
        st.dataframe(dept_df[dept_df['is_gas_20min']].describe(include='all').transpose())
    with tab4:
        st.subheader(f"{selected_dept} 今年度 累積実績")
        weekly_target = target_dict.get(selected_dept)
        if weekly_target:
            cum_data = ranking.calculate_cumulative_cases(dept_df, weekly_target)
            if not cum_data.empty: st.plotly_chart(generic_plots.plot_cumulative_cases_chart(cum_data, f"{selected_dept} 累積実績"), use_container_width=True)
        else: st.info("この診療科の目標値が設定されていないため、累積目標は表示できません。")

def render_surgeon_page(df, target_dict, latest_date):
    st.title("👨‍⚕️ 術者分析")
    analysis_type = st.radio("分析タイプ", ["診療科別ランキング", "術者ごと時系列"], horizontal=True)
    with st.spinner("術者データを準備中..."):
        expanded_df = surgeon.get_expanded_surgeon_df(df)
    if expanded_df.empty:
        st.warning("分析可能な術者データがありません。"); return
    if analysis_type == "診療科別ランキング":
        departments = ["全診療科"] + sorted(df["実施診療科"].dropna().unique())
        selected_dept = st.selectbox("診療科で絞り込み", departments)
        top_n = st.slider("表示する術者数（上位）", 5, 50, 15)
        target_df = expanded_df
        if selected_dept != "全診療科": target_df = expanded_df[expanded_df['実施診療科'] == selected_dept]
        summary_df = surgeon.get_surgeon_summary(target_df)
        if not summary_df.empty: st.plotly_chart(generic_plots.plot_surgeon_ranking(summary_df, top_n, selected_dept), use_container_width=True)
    else: # 術者ごと時系列
        surgeons = sorted(expanded_df["実施術者"].dropna().unique())
        selected_surgeon = st.selectbox("分析する術者を選択", surgeons)
        surgeon_df = expanded_df[expanded_df['実施術者'] == selected_surgeon]
        st.header(f"{selected_surgeon} の週次実績")
        summary = weekly.get_summary(surgeon_df, use_complete_weeks=False)
        if not summary.empty:
            fig = trend_plots.create_weekly_dept_chart(summary, selected_surgeon, {})
            st.plotly_chart(fig, use_container_width=True)

def render_prediction_page(df, target_dict, latest_date):
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
        if st.button("予測を実行", type="primary", key="run_prediction"):
            with st.spinner("予測計算中..."):
                result_df, metrics = forecasting.predict_future(df, latest_date, department=department, model_type=model_type, prediction_period=pred_period)
                if metrics.get("message"): st.warning(metrics["message"])
                else:
                    title = f"{department or '病院全体'} {metrics.get('予測モデル','')}モデルによる予測"
                    fig = generic_plots.create_forecast_chart(result_df, title)
                    st.plotly_chart(fig, use_container_width=True); st.write(metrics)
    with tab2:
        st.header("予測モデルの精度検証")
        val_target = st.radio("検証対象", ["病院全体", "診療科別"], horizontal=True, key="val_target")
        val_dept = None
        if val_target == "診療科別": val_dept = st.selectbox("診療科を選択", sorted(df["実施診療科"].dropna().unique()), key="val_dept")
        val_period = st.slider("検証期間（月数）", 3, 12, 6)
        if st.button("検証実行", key="run_validation"):
            with st.spinner("モデル検証中..."):
                metrics_df, train, test, preds, rec = forecasting.validate_model(df, department=val_dept, validation_period=val_period)
                if not metrics_df.empty:
                    st.success(rec); st.dataframe(metrics_df)
                    st.plotly_chart(generic_plots.create_validation_chart(train, test, preds), use_container_width=True)
                else: st.error("モデル検証に失敗しました。")
    with tab3:
        st.header("パラメータ最適化 (Holt-Winters)")
        opt_target = st.radio("最適化対象", ["病院全体", "診療科別"], horizontal=True, key="opt_target")
        opt_dept = None
        if opt_target == "診療科別": opt_dept = st.selectbox("診療科を選択", sorted(df["実施診療科"].dropna().unique()), key="opt_dept")
        if st.button("最適化実行", key="run_opt"):
            with st.spinner("最適化計算中..."):
                params, desc = forecasting.optimize_hwes_params(df, department=opt_dept)
                if params: st.success(f"最適モデル: {desc}"); st.write(params)
                else: st.error(desc)

# --- メイン実行部 ---
def main():
    initialize_session_state()
    render_sidebar()
    render_page_content()

if __name__ == "__main__":
    main()