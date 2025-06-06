# app_enhanced_with_prediction.py (予測指標表示修正)
import streamlit as st

# 最初に set_page_config を呼び出す
st.set_page_config(page_title="手術件数分析アプリ", layout="wide")

# 他の標準ライブラリと外部ライブラリをインポート
import pandas as pd
# import plotly.graph_objects as go # plotter モジュールでインポートされるため不要な可能性
import pytz
from datetime import datetime
import numpy as np
import io # ZIP出力用に io をインポート
import zipfile # ZIP出力用に zipfile をインポート

# スタイル定義をインポート (stコマンドを含まないことを確認)
try:
    import style_config as sc
except ImportError:
    print("ERROR: style_config.pyが見つかりません。デフォルトスタイルで続行します。")
    class StyleConfigFallback: # fallback class
        def __getattr__(self, name):
            print(f"Warning: style_config attribute '{name}' not found, using default.")
            if name.endswith('_STYLE'): return {}
            if name.endswith('_FONT'): return {}
            if name.endswith('_COLOR'): return 'grey'
            if name == 'LAYOUT_DEFAULTS': return {}
            if name == 'TABLE_STYLE_PROPS': return []
            if name == 'TABLE_COMMON_FORMAT_DICT': return {}
            return None
    sc = StyleConfigFallback()

# PDF出力機能をインポート
try:
    # 個別PDF出力ボタンと、一括出力で使用するレポート生成関数をインポート
    from pdf_exporter import (
        add_pdf_report_button,
        generate_department_report,
        generate_hospital_weekly_report, # 病院週次レポート用
        generate_hospital_monthly_report # 病院月次・四半期レポート用
    )
except ImportError:
    print("WARNING: pdf_exporter.pyが見つかりません。PDF出力機能は無効です。")
    def add_pdf_report_button(*args, **kwargs):
        st.warning("PDF出力機能は利用できません。pdf_exporter.pyをインストールしてください。")
    # generate_* 関数もダミー関数として定義
    def generate_department_report(*args, **kwargs): st.error("PDFレポート生成機能が利用できません。"); return None
    def generate_hospital_weekly_report(*args, **kwargs): st.error("PDFレポート生成機能が利用できません。"); return None
    def generate_hospital_monthly_report(*args, **kwargs): st.error("PDFレポート生成機能が利用できません。"); return None

# 術者分析モジュールをインポート
try:
    from surgeon_analyzer import create_surgeon_analysis
except ImportError:
    print("WARNING: surgeon_analyzer.py が見つかりません。術者分析機能は無効です。")
    def create_surgeon_analysis(*args, **kwargs): 
        st.warning("術者分析機能は利用できません。surgeon_analyzer.py をインストールしてください。")

# --- アプリタイトルと最終更新日時 ---
# set_page_config の後に Streamlit コマンドを配置
st.title("🏥 全身麻酔手術件数分析アプリ")
jst = pytz.timezone('Asia/Tokyo')
st.caption(f"最終アクセス日時: {datetime.now(jst).strftime('%Y年%m月%d日 %H:%M:%S')} (JST)")

# --- ローカルモジュールのインポートとエラーハンドリング ---
import_error_occurred = False
error_message = ""

try:
    from loader import load_single_file, merge_base_and_updates
    # analyzer から calculate_pace_projection を削除
    from analyzer import analyze_hospital_summary, analyze_department_summary, calculate_recent_averages, filter_data_by_period
    # hospital_prediction から get_multi_model_forecast_summary を削除 (不要になったため)
    # from hospital_prediction import get_multi_model_forecast_summary
    from monthly_quarterly_analyzer import analyze_monthly_summary, analyze_quarterly_summary, analyze_monthly_department_summary, analyze_quarterly_department_summary
    from target_loader import load_target_file
    from plotter import plot_summary_graph, plot_department_graph
    from monthly_quarterly_plotter import plot_monthly_department_graph, plot_quarterly_department_graph
    from hospital_monthly_quarterly_plotter import plot_monthly_hospital_graph, plot_quarterly_hospital_graph
    from department_ranking import (
        calculate_department_achievement_rates, plot_achievement_ranking,
        calculate_cumulative_cases, plot_cumulative_cases # 累積計算・描画関数もインポート
    )
    from export_handler import render_download_button
    # --- prediction_tab_enhanced のインポート方式 (from ... import ... ) ---
    from prediction_tab_enhanced import create_prediction_tab, get_multi_model_forecast_parallel
    # ---------------------------------------------------------------------
    
    # --- 術者分析モジュールをインポート (追加) ---
    from surgeon_analyzer import create_surgeon_analysis
    # --------------------------------------
    
except ImportError as e:
    import_error_occurred = True
    # エラーメッセージにどのモジュールで失敗したか表示
    error_message = f"必要な分析モジュールの読み込みに失敗しました: {e}\nファイル名: {e.name}\nファイル構成を確認してください。"

# --- インポートエラーがあればメッセージを表示して停止 ---
if import_error_occurred:
    st.error(error_message)
    st.warning("アプリの実行に必要なファイルが不足しているため、処理を続行できません。")
    st.stop()
else:
    # インポートが成功した場合でも術者分析モジュールがなければダミー関数を定義
    if 'create_surgeon_analysis' not in locals():
        def create_surgeon_analysis(*args, **kwargs): 
            st.warning("術者分析機能は利用できません。surgeon_analyzer.py をインストールしてください。")

# --- セッション状態初期化 (モジュールインポート成功後) ---
if 'df_gas' not in st.session_state: st.session_state['df_gas'] = None
if 'target_dict' not in st.session_state: st.session_state['target_dict'] = {}
if 'latest_date' not in st.session_state: st.session_state['latest_date'] = None
if 'base_df' not in st.session_state: st.session_state['base_df'] = None
# --- 予測結果保存用セッションステート初期化 ---
if 'hospital_forecast_metrics' not in st.session_state:
    st.session_state['hospital_forecast_metrics'] = None # これは将来予測タブ用
# --- 初期化ここまで ---

# 診療科別パフォーマンステーブルを表示する関数 (ここに移動)
def render_department_performance_table(df_gas, target_dict, latest_date):
    """診療科ごとの様々な期間での目標達成率テーブルを作成して表示する"""
    
    st.subheader("📋 診療科別目標達成状況")
    
    # 表示する診療科（固定）- 目標が設定されている診療科のみ
    target_departments = [
        "皮膚科", "整形外科", "産婦人科", "歯科口腔外科", "耳鼻咽喉科", 
        "泌尿器科", "一般消化器外科", "呼吸器外科", "心臓血管外科", 
        "乳腺外科", "形成外科", "脳神経外科"
    ]
    
    # 存在確認（目標値が設定されている診療科のみ表示）
    display_departments = [dept for dept in target_departments if dept in target_dict]
    
    if not display_departments:
        st.warning("目標が設定されている診療科がありません。目標データをアップロードしてください。")
        return pd.DataFrame()  # 空のデータフレームを返す
    
    # 期間の設定
    periods = {
        "直近7日": 7,
        "直近14日": 14,
        "直近30日": 30,
        "直近60日": 60,
        "直近90日": 90,
        "2024年度平均": None,  # 特殊処理
        "2024年度（同期間）": None,  # 特殊処理
        "2025年度平均": None,  # 特殊処理
    }
    
    # 結果を格納するデータフレーム
    result_df = pd.DataFrame(index=display_departments)
    
    # 各期間での平均値と達成率を計算
    for period_name, days in periods.items():
        # 期間の実績データ取得
        if period_name == "2024年度平均":
            # 2024年度全体 (4/1/2024-3/31/2025)
            period_start = pd.Timestamp(2024, 4, 1)
            period_end = pd.Timestamp(2025, 3, 31)
        elif period_name == "2024年度（同期間）":
            # 2024年度の同じ期間 (4/1/2024-現在)
            period_start = pd.Timestamp(2024, 4, 1)
            period_end = latest_date
        elif period_name == "2025年度平均":
            # 2025年度 (4/1/2025-現在、または将来の場合は空)
            period_start = pd.Timestamp(2025, 4, 1)
            period_end = latest_date
            if period_start > latest_date:
                # 2025年度未到達の場合はスキップ
                continue
        else:
            # 直近X日
            period_end = latest_date
            period_start = latest_date - pd.Timedelta(days=days-1)
        
        # 期間内のデータを取得
        period_df = df_gas[(df_gas['手術実施日_dt'] >= period_start) & (df_gas['手術実施日_dt'] <= period_end)]
        
        # 期間内の週数を計算
        weeks_in_period = (period_end - period_start).days / 7.0
        if weeks_in_period <= 0:
            continue  # データがない期間はスキップ
        
        # 各診療科の平均値と達成率を計算
        avg_values = {}
        achievement_rates = {}
        
        for dept in display_departments:
            # 診療科データの取得
            dept_df = period_df[period_df['実施診療科'] == dept]
            dept_df = dept_df[
                dept_df['麻酔種別'].str.contains("全身麻酔", na=False) &
                dept_df['麻酔種別'].str.contains("20分以上", na=False)
            ]
            
            # 週単位で集計
            if not dept_df.empty:
                # 週ごとにグループ化してカウント
                dept_df['週'] = dept_df['手術実施日_dt'] - pd.to_timedelta(dept_df['手術実施日_dt'].dt.dayofweek, unit='d')
                dept_df['週'] = dept_df['週'].dt.normalize()
                weekly_counts = dept_df.groupby('週').size().reset_index(name='件数')
                
                # 週平均値（実績値）
                avg_weekly_count = weekly_counts['件数'].mean()
            else:
                avg_weekly_count = 0
            
            # 目標値と達成率
            target_value = target_dict.get(dept, 0)
            achievement_rate = (avg_weekly_count / target_value * 100) if target_value > 0 else 0
            
            # 結果を保存
            avg_values[dept] = avg_weekly_count
            achievement_rates[dept] = achievement_rate
        
        # 期間ごとの平均値と達成率を結果DFに追加
        if period_name.endswith("達成率 (%)"):
            # 達成率のみの列
            for dept in display_departments:
                result_df.loc[dept, period_name] = achievement_rates[dept]
        else:
            # 平均値の列
            for dept in display_departments:
                result_df.loc[dept, period_name] = avg_values[dept]
    
    # 目標列と達成率列を追加
    result_df["目標 (週合計)"] = [target_dict.get(dept, 0) for dept in display_departments]
    
    # 直近7日、直近30日、年度の達成率列を追加
    if "直近7日" in result_df.columns:
        result_df["直近7日達成率 (%)"] = [
            (result_df.loc[dept, "直近7日"] / target_dict.get(dept, 1) * 100) if target_dict.get(dept, 0) > 0 else 0 
            for dept in display_departments
        ]
    
    if "直近30日" in result_df.columns:
        result_df["直近30日達成率 (%)"] = [
            (result_df.loc[dept, "直近30日"] / target_dict.get(dept, 1) * 100) if target_dict.get(dept, 0) > 0 else 0 
            for dept in display_departments
        ]
    
    if "2025年度平均" in result_df.columns:
        result_df["2025年度達成率 (%)"] = [
            (result_df.loc[dept, "2025年度平均"] / target_dict.get(dept, 1) * 100) if target_dict.get(dept, 0) > 0 else 0 
            for dept in display_departments
        ]
    
    # スタイル設定（条件付き書式）
    def highlight_achievement(s):
        """達成率に応じた背景色を設定 (series対応)"""
        # 列名に '達成率' が含まれているかチェック
        is_rate_column = False
        if isinstance(s, pd.Series):
            is_rate_column = "達成率" in str(s.name) if hasattr(s, 'name') else False
    
        # 達成率列の場合は条件付き書式を適用
        if is_rate_column or (isinstance(s, pd.Series) and "%" in str(s.name)):
            return [
                'background-color: rgba(76, 175, 80, 0.2)' if isinstance(v, (int, float)) and v >= 100 else  # 緑 (100%以上)
                'background-color: rgba(255, 235, 59, 0.2)' if isinstance(v, (int, float)) and v >= 90 else  # 黄色 (90-99%)
                'background-color: rgba(255, 152, 0, 0.2)' if isinstance(v, (int, float)) and v >= 80 else   # オレンジ (80-89%)
                'background-color: rgba(244, 67, 54, 0.2)' if isinstance(v, (int, float)) else ''             # 赤 (80%未満)
                for v in s
            ]
        # それ以外の列には書式を適用しない
        return [''] * len(s) if isinstance(s, pd.Series) else ''
    
    # 列の順序を調整
    # 基本情報、直近の実績、年度実績、達成率の順
    desired_columns = [
        "目標 (週合計)", 
        "直近7日", "直近14日", "直近30日", "直近60日", "直近90日",
        "2024年度平均", "2024年度（同期間）", "2025年度平均",
        "直近7日達成率 (%)", "直近30日達成率 (%)", "2025年度達成率 (%)"
    ]
    final_columns = [col for col in desired_columns if col in result_df.columns]
    result_df = result_df[final_columns]
    
    # 整数と小数点のフォーマット設定
    format_dict = {
        "目標 (週合計)": "{:.1f}",
        "直近7日": "{:.1f}",
        "直近14日": "{:.1f}",
        "直近30日": "{:.1f}",
        "直近60日": "{:.1f}",
        "直近90日": "{:.1f}",
        "2024年度平均": "{:.1f}",
        "2024年度（同期間）": "{:.1f}",
        "2025年度平均": "{:.1f}",
        "直近7日達成率 (%)": "{:.1f}",
        "直近30日達成率 (%)": "{:.1f}",
        "2025年度達成率 (%)": "{:.1f}"
    }
    
    # データフレームとして表示
    st.dataframe(
        result_df.style
            .format(format_dict)
            .apply(highlight_achievement)  # .map ではなく .apply を使用
            .set_table_styles(sc.TABLE_STYLE_PROPS),
        use_container_width=True
    )
    
    # CSVダウンロードボタンを追加
    from export_handler import render_download_button
    render_download_button(result_df, "department", "performance_table")

    # ここから新しいコードを追加 ------------------------------
    # 横向きPDF出力ボタンを追加 (新しい関数を呼び出す)
    try:
        from pdf_exporter import add_landscape_performance_button
        
        # 診療科名をインデックスから列に移動した新しいDataFrameを作成
        pdf_display_df = result_df.reset_index()
        pdf_display_df = pdf_display_df.rename(columns={'index': '診療科'})
        
        # 表示する列を指定された項目に限定
        desired_columns = [
            '診療科',
            '目標 (週合計)',
            '直近7日',
            '直近30日',
            '2024年度平均',
            '2024年度（同期間）',
            '2025年度平均',
            '直近7日達成率 (%)',
            '直近30日達成率 (%)',
            '2025年度達成率 (%)'
        ]
        
        # 存在する列のみをフィルタリング
        available_columns = [col for col in desired_columns if col in pdf_display_df.columns]
        pdf_display_df = pdf_display_df[available_columns]
        
        # 修正したデータフレームを使用して横向きPDFボタンを追加
        add_landscape_performance_button(pdf_display_df)
    except ImportError:
        st.warning("横向きPDF出力機能を利用するには、pdf_exporter.py に新しい関数を追加してください。")
    except Exception as e:
        st.error(f"横向きPDF出力エラー: {e}")
        
    # 結果のデータフレームを返す (ここが追加)
    return result_df

# --- サイドバー (モジュールインポート成功後) ---
st.sidebar.title("分析メニュー")
sidebar_tab = st.sidebar.radio(
    "メニューを選択", ["データアップロード", "病院全体分析", "診療科別分析", "診療科ランキング", "術者分析", "将来予測"],
    captions=["CSV読込", "病院全体", "診療科別", "達成度比較", "術者別", "件数予測"], key="sidebar_menu"
)


# --- 一括出力ボタンセクションに修正を加える (st.sidebar.markdown("---") の後) ---
st.sidebar.markdown("---") # 区切り線
st.sidebar.subheader("レポート出力")

# 病院全体週次レポートのみを出力するボタンを追加
if st.sidebar.button("病院全体週次レポート出力", key="hospital_weekly_report_button", help="病院全体の週次レポートのみを出力します"):
    # データ存在チェック
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.sidebar.warning("データがロードされていません。")
    else:
        df_gas = st.session_state['df_gas']
        target_dict = st.session_state.get('target_dict', {})
        latest_date = st.session_state.get('latest_date')

        if latest_date is None:
            st.sidebar.warning("日付情報が取得できません。")
        else:
            with st.spinner("病院全体週次レポートを生成中..."):
                # 病院全体 - 週次の分析
                hospital_summary_w = analyze_hospital_summary(df_gas)
                fig_hospital_w_pdf = None # PDF用グラフ初期化
                recent_averages_w = None
                if not hospital_summary_w.empty:
                    # PDF用グラフ（4週移動平均強制）
                    fig_hospital_w_pdf = plot_summary_graph(hospital_summary_w, "全科", target_dict, 4)
                    recent_averages_w = calculate_recent_averages(df_gas)

                # 予測モデル比較データの取得
                model_comparison_data = None
                model_options = {
                    "hwes": "季節性Holt-Winters",
                    "arima": "ARIMA",
                    "moving_avg": "単純移動平均"
                }
                
                try:
                    # 並列処理で複数モデルの予測を実行
                    model_types_to_run = ['hwes', 'arima', 'moving_avg']
                    all_model_metrics = get_multi_model_forecast_parallel(
                        df_gas, 
                        "fiscal_year", # 年度末までの予測を使用
                        model_types_to_run
                    )
                    
                    # モデル比較データ作成
                    if all_model_metrics:
                        comparison_data = []
                        for model_type, metrics in all_model_metrics.items():
                            if "error" not in metrics:
                                model_name = model_options.get(model_type, model_type)
                                comparison_data.append({
                                    "モデル": model_name,
                                    "予測平均": f"{metrics.get('予測平均', 0):.1f} 件/日",
                                    "年度合計予測": f"{metrics.get('年度合計予測', 0):,} 件",
                                    "目標達成率予測": f"{metrics.get('目標達成率予測', 0):.1f} %"
                                })
                        
                        if comparison_data:
                            model_comparison_data = pd.DataFrame(comparison_data)
                except Exception as pred_e:
                    print(f"予測モデル比較の生成中にエラー発生: {pred_e}")
                    model_comparison_data = None

                # 診療科別目標達成状況の生成 (限定列で)
                dept_performance_data = render_department_performance_table(df_gas, target_dict, latest_date)
                
                # PDFレポート用に表示列を絞り込む
                if not dept_performance_data.empty:
                    # 診療科名をインデックスから列に移動
                    dept_performance_data = dept_performance_data.reset_index()
                    dept_performance_data = dept_performance_data.rename(columns={'index': '診療科'})
                    
                    # 表示する列を指定された項目に限定
                    desired_columns = [
                        '診療科',
                        '目標 (週合計)',
                        '直近7日',
                        '直近30日',
                        '2024年度平均',
                        '2024年度（同期間）',
                        '2025年度平均',
                        '直近7日達成率 (%)',
                        '直近30日達成率 (%)',
                        '2025年度達成率 (%)'
                    ]
                    
                    # 存在する列のみをフィルタリング
                    available_columns = [col for col in desired_columns if col in dept_performance_data.columns]
                    dept_performance_data = dept_performance_data[available_columns]

                # 病院全体累積データ計算
                current_year = latest_date.year
                fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
                hospital_cum_start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')
                hospital_cum_end_date = latest_date
                hospital_cum_data = None
                hospital_cum_fig = None
                hospital_weekly_target = 95 # 仮の目標値

                if hospital_cum_start_date <= hospital_cum_end_date:
                    df_hospital_period_for_cum = df_gas[
                        (df_gas["手術実施日_dt"] >= hospital_cum_start_date) &
                        (df_gas["手術実施日_dt"] <= hospital_cum_end_date)
                    ].copy()
                    if not df_hospital_period_for_cum.empty:
                        hospital_cum_data = calculate_cumulative_cases(df_hospital_period_for_cum, "全診療科", hospital_weekly_target)
                        if not hospital_cum_data.empty:
                            hospital_cum_fig = plot_cumulative_cases(hospital_cum_data, "全診療科")

                # PDF生成関数呼び出し（extrasに累積データとグラフを追加）
                pdf_extras_hosp_w = {
                    'averages_data': recent_averages_w,
                    'cumulative_data': hospital_cum_data, # 病院全体の累積データ
                    'cumulative_fig': hospital_cum_fig # 病院全体の累積グラフ
                }
                
                # 単一PDF生成
                pdf_buffer_hosp_w = generate_hospital_weekly_report(
                    hospital_summary_w, fig_hospital_w_pdf, target_dict, 
                    pdf_extras_hosp_w,
                    model_comparison=model_comparison_data,  # モデル比較データを追加
                    dept_performance=dept_performance_data   # 診療科別目標達成状況テーブルを追加
                )
                
                if pdf_buffer_hosp_w:
                    current_date_str = datetime.now().strftime("%Y%m%d")
                    pdf_filename_hosp_w = f"{current_date_str}_病院全体_週次レポート.pdf"
                    st.sidebar.download_button(
                        label=f"📥 {pdf_filename_hosp_w} をダウンロード",
                        data=pdf_buffer_hosp_w,
                        file_name=pdf_filename_hosp_w,
                        mime="application/pdf",
                        key="download_hospital_weekly_pdf"
                    )
                    st.sidebar.success("病院全体週次レポートの生成が完了しました")
                else:
                    st.sidebar.error("レポート生成中にエラーが発生しました")

# 一括出力ボタン（既存コードを修正）
if st.sidebar.button("全レポート一括出力 (ZIP)", key="bulk_export_button", help="病院全体(週/月/四半期)と全診療科のレポートを出力します"):
    # データ存在チェック
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty:
        st.sidebar.warning("データがロードされていません。")
    else:
        df_gas = st.session_state['df_gas']
        target_dict = st.session_state.get('target_dict', {})
        latest_date = st.session_state.get('latest_date')

        if latest_date is None:
             st.sidebar.warning("日付情報が取得できません。")
        else:
            all_departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
            if not all_departments:
                st.sidebar.warning("データ内に診療科情報が見つかりません。")
            else:
                zip_buffer = io.BytesIO()
                # 病院全体(3種類) + 診療科数
                total_reports = 3 + len(all_departments)
                progress_bar = st.sidebar.progress(0)
                status_text = st.sidebar.empty()
                generated_count = 0
                error_count = 0
                current_report_index = 0 # 進捗表示用

                # 年度開始年をここで計算（ループの外で一度だけ計算すれば良い）
                current_year = latest_date.year
                fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
                cum_end_date = latest_date # 累積計算の終了日は最新日付

                with st.spinner(f"全 {total_reports} 件のレポートを生成中..."):
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:

                        # --- 病院全体レポート生成 ---
                        current_date_str = datetime.now().strftime("%Y%m%d")

                        # 1. 病院全体 - 週次
                        current_report_index += 1
                        status_text.text(f"処理中: 病院全体 週次 ({current_report_index}/{total_reports})")
                        try:
                            hospital_summary_w = analyze_hospital_summary(df_gas)
                            fig_hospital_w_pdf = None # PDF用グラフ初期化
                            recent_averages_w = None
                            if not hospital_summary_w.empty:
                                # PDF用グラフ（4週移動平均強制）
                                fig_hospital_w_pdf = plot_summary_graph(hospital_summary_w, "全科", target_dict, 4)
                                recent_averages_w = calculate_recent_averages(df_gas)

                            # 予測モデル比較データの取得（一括出力時でも常に最新計算）
                            model_comparison_data = None
                            model_options = {
                                "hwes": "季節性Holt-Winters",
                                "arima": "ARIMA",
                                "moving_avg": "単純移動平均"
                            }
                            
                            try:
                                # 並列処理で複数モデルの予測を実行
                                model_types_to_run = ['hwes', 'arima', 'moving_avg']
                                all_model_metrics = get_multi_model_forecast_parallel(
                                    df_gas, 
                                    "fiscal_year", # 年度末までの予測を使用
                                    model_types_to_run
                                )
                                
                                # モデル比較データ作成
                                if all_model_metrics:
                                    comparison_data = []
                                    for model_type, metrics in all_model_metrics.items():
                                        if "error" not in metrics:
                                            model_name = model_options.get(model_type, model_type)
                                            comparison_data.append({
                                                "モデル": model_name,
                                                "予測平均": f"{metrics.get('予測平均', 0):.1f} 件/日",
                                                "年度合計予測": f"{metrics.get('年度合計予測', 0):,} 件",
                                                "目標達成率予測": f"{metrics.get('目標達成率予測', 0):.1f} %"
                                            })
                                    
                                    if comparison_data:
                                        model_comparison_data = pd.DataFrame(comparison_data)
                            except Exception as pred_e:
                                print(f"予測モデル比較の生成中にエラー発生: {pred_e}")
                                model_comparison_data = None

                            # 診療科別目標達成状況の生成 (限定列で)
                            dept_performance_data = render_department_performance_table(df_gas, target_dict, latest_date)
                            
                            # PDFレポート用に表示列を絞り込む
                            if not dept_performance_data.empty:
                                # 診療科名をインデックスから列に移動
                                dept_performance_data = dept_performance_data.reset_index()
                                dept_performance_data = dept_performance_data.rename(columns={'index': '診療科'})
                                
                                # 表示する列を指定された項目に限定
                                desired_columns = [
                                    '診療科',
                                    '目標 (週合計)',
                                    '直近7日',
                                    '直近30日',
                                    '2024年度平均',
                                    '2024年度（同期間）',
                                    '2025年度平均',
                                    '直近7日達成率 (%)',
                                    '直近30日達成率 (%)',
                                    '2025年度達成率 (%)'
                                ]
                                
                                # 存在する列のみをフィルタリング
                                available_columns = [col for col in desired_columns if col in dept_performance_data.columns]
                                dept_performance_data = dept_performance_data[available_columns]

                            # 病院全体累積データ計算
                            hospital_cum_start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')
                            hospital_cum_data = None
                            hospital_cum_fig = None
                            hospital_weekly_target = 95 # 仮の目標値

                            if hospital_cum_start_date <= cum_end_date:
                                df_hospital_period_for_cum = df_gas[
                                    (df_gas["手術実施日_dt"] >= hospital_cum_start_date) &
                                    (df_gas["手術実施日_dt"] <= cum_end_date)
                                ].copy()
                                if not df_hospital_period_for_cum.empty:
                                    hospital_cum_data = calculate_cumulative_cases(df_hospital_period_for_cum, "全診療科", hospital_weekly_target)
                                    if not hospital_cum_data.empty:
                                        hospital_cum_fig = plot_cumulative_cases(hospital_cum_data, "全診療科")

                            # PDF生成関数呼び出し（extrasに累積データとグラフを追加）
                            pdf_extras_hosp_w = {
                                'averages_data': recent_averages_w,
                                'cumulative_data': hospital_cum_data, # 病院全体の累積データ
                                'cumulative_fig': hospital_cum_fig # 病院全体の累積グラフ
                            }
                            pdf_buffer_hosp_w = generate_hospital_weekly_report(
                                hospital_summary_w, fig_hospital_w_pdf, target_dict, 
                                pdf_extras_hosp_w,
                                model_comparison=model_comparison_data,  # モデル比較データを追加
                                dept_performance=dept_performance_data   # 診療科別目標達成状況テーブルを追加
                            )
                            if pdf_buffer_hosp_w:
                                pdf_filename_hosp_w = f"{current_date_str}_病院全体_週次レポート.pdf"
                                zipf.writestr(pdf_filename_hosp_w, pdf_buffer_hosp_w.getvalue())
                                generated_count += 1
                            else: error_count += 1
                        except Exception as e:
                            print(f"レポート生成中にエラー発生 (病院全体 週次): {e}")
                            error_count += 1
                        progress_bar.progress(current_report_index / total_reports)
                        
                        # 2. 病院全体 - 月次
                        current_report_index += 1
                        status_text.text(f"処理中: 病院全体 月次 ({current_report_index}/{total_reports})")
                        try:
                            hospital_summary_m = analyze_monthly_summary(df_gas)
                            fig_hospital_m = None
                            if not hospital_summary_m.empty:
                                fig_hospital_m = plot_monthly_hospital_graph(hospital_summary_m, target_dict)

                            pdf_buffer_hosp_m = generate_hospital_monthly_report(
                                hospital_summary_m, fig_hospital_m, target_dict, period_label="月次"
                            )
                            if pdf_buffer_hosp_m:
                                pdf_filename_hosp_m = f"{current_date_str}_病院全体_月次レポート.pdf"
                                zipf.writestr(pdf_filename_hosp_m, pdf_buffer_hosp_m.getvalue())
                                generated_count += 1
                            else: error_count += 1
                        except Exception as e:
                            print(f"レポート生成中にエラー発生 (病院全体 月次): {e}")
                            error_count += 1
                        progress_bar.progress(current_report_index / total_reports)

                        # 3. 病院全体 - 四半期
                        current_report_index += 1
                        status_text.text(f"処理中: 病院全体 四半期 ({current_report_index}/{total_reports})")
                        try:
                            hospital_summary_q = analyze_quarterly_summary(df_gas)
                            fig_hospital_q = None
                            if not hospital_summary_q.empty:
                                fig_hospital_q = plot_quarterly_hospital_graph(hospital_summary_q, target_dict)

                            pdf_buffer_hosp_q = generate_hospital_monthly_report( # 月次用関数を流用
                                hospital_summary_q, fig_hospital_q, target_dict, period_label="四半期"
                            )
                            if pdf_buffer_hosp_q:
                                pdf_filename_hosp_q = f"{current_date_str}_病院全体_四半期レポート.pdf"
                                zipf.writestr(pdf_filename_hosp_q, pdf_buffer_hosp_q.getvalue())
                                generated_count += 1
                            else: error_count += 1
                        except Exception as e:
                            print(f"レポート生成中にエラー発生 (病院全体 四半期): {e}")
                            error_count += 1
                        progress_bar.progress(current_report_index / total_reports)

                        # --- 診療科別レポート生成ループ ---
                        for dept in all_departments:
                            current_report_index += 1
                            status_text.text(f"処理中: {dept} ({current_report_index}/{total_reports})")
                            try:
                                # 1. 週次データの生成とグラフ描画 (PDF用 - 4週MA強制)
                                weekly_data = analyze_department_summary(df_gas, dept)
                                weekly_fig_pdf = None # PDF用グラフ初期化
                                if not weekly_data.empty:
                                    weekly_fig_pdf = plot_department_graph(weekly_data, dept, target_dict, 4) # 4週MA強制

                                # 2. 月次データの生成とグラフ描画
                                monthly_data = analyze_monthly_department_summary(df_gas, dept)
                                monthly_fig = None
                                if not monthly_data.empty:
                                    monthly_fig = plot_monthly_department_graph(monthly_data, dept, target_dict)

                                # 3. 累積データの準備とグラフ描画
                                # fiscal_year_start_year はループの外で計算済み
                                cum_start_date_dept = pd.Timestamp(f'{fiscal_year_start_year}-04-01') # <= ここで参照
                                cumulative_data = None
                                cumulative_fig = None
                                current_weekly_target = target_dict.get(dept, 0) if target_dict else 0

                                if cum_start_date_dept <= cum_end_date:
                                    df_dept_period_for_cum = df_gas[
                                        (df_gas["実施診療科"] == dept) &
                                        (df_gas["手術実施日_dt"] >= cum_start_date_dept) &
                                        (df_gas["手術実施日_dt"] <= cum_end_date)
                                    ].copy()

                                    if not df_dept_period_for_cum.empty:
                                        cumulative_data = calculate_cumulative_cases(df_dept_period_for_cum, dept, current_weekly_target)
                                        if not cumulative_data.empty:
                                            cumulative_fig = plot_cumulative_cases(cumulative_data, dept)

                                # 4. PDFレポート生成 (PDF用週次グラフを渡す)
                                pdf_filename = f"{current_date_str}_{dept}_分析レポート.pdf"
                                pdf_buffer_dept = generate_department_report(
                                    dept,
                                    weekly_data=weekly_data, fig=weekly_fig_pdf, # PDF用グラフを使用
                                    monthly_data=monthly_data, monthly_fig=monthly_fig,
                                    cumulative_data=cumulative_data, cumulative_fig=cumulative_fig,
                                    filename=pdf_filename
                                )

                                # 5. ZIPファイルに追加
                                if pdf_buffer_dept:
                                    zipf.writestr(pdf_filename, pdf_buffer_dept.getvalue())
                                    generated_count += 1
                                else:
                                    print(f"レポート生成失敗（BufferがNone）: {dept}")
                                    error_count += 1

                            except Exception as e:
                                print(f"レポート生成中にエラー発生 ({dept}): {e}")
                                error_count += 1

                            # プログレスバー更新
                            progress_bar.progress(current_report_index / total_reports)

                # ZIPファイルの準備
                zip_buffer.seek(0)
                status_text.success(f"完了: {generated_count}件生成、{error_count}件エラー")
                progress_bar.empty() # プログレスバーを消す

                # ダウンロードボタン
                zip_filename = f"{datetime.now().strftime('%Y%m%d')}_全レポート.zip" # ファイル名変更
                st.sidebar.download_button(
                    label=f"📥 {zip_filename} をダウンロード",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip",
                    key="download_zip_button"
                )

# PDF依存関係の確認関数 (変更なし)
def check_pdf_dependencies():
    """PDFレポート出力に必要なライブラリが利用可能か確認"""

    # 関数の本体は省略...

# アプリ起動時にチェック実行
check_pdf_dependencies()


def create_department_dashboard(df_gas, target_dict, latest_date):
    """診療科ごとのパフォーマンスダッシュボードを作成"""
    
    st.subheader("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
    
    # ターゲット診療科（固定）
    target_departments = [
        "皮膚科", "整形外科", "産婦人科", "歯科口腔外科", "耳鼻咽喉科", 
        "泌尿器科", "一般消化器外科", "呼吸器外科", "心臓血管外科", 
        "乳腺外科", "形成外科", "脳神経外科"
    ]
    
    # 存在確認（データと目標値が設定されている診療科のみ表示）
    available_departments = []
    for dept in target_departments:
        if dept in target_dict and dept in df_gas['実施診療科'].unique():
            available_departments.append(dept)
    
    if not available_departments:
        st.warning("表示可能な診療科データがありません。")
        return
    
    # メトリクスの準備
    metrics_data = []
    
    for dept in available_departments:
        # 直近30日のデータを抽出
        period_end = latest_date
        period_start = period_end - pd.Timedelta(days=30)
        
        dept_recent_df = df_gas[
            (df_gas['実施診療科'] == dept) &
            (df_gas['手術実施日_dt'] >= period_start) &
            (df_gas['手術実施日_dt'] <= period_end) &
            (df_gas['麻酔種別'].str.contains("全身麻酔", na=False)) &
            (df_gas['麻酔種別'].str.contains("20分以上", na=False))
        ]
        
        # 週あたりの件数を集計
        weekly_count = len(dept_recent_df) / 4.3  # 約4.3週間分
        
        # 目標値と達成率
        target = target_dict.get(dept, 0)
        achievement_rate = (weekly_count / target * 100) if target > 0 else 0
        
        metrics_data.append({
            "診療科": dept,
            "直近4週平均": weekly_count,
            "週間目標": target,
            "達成率": achievement_rate,
            "状態": "達成" if achievement_rate >= 100 else 
                   "注意" if achievement_rate >= 80 else "未達成"
        })
    
    # データフレーム作成と降順ソート
    metrics_df = pd.DataFrame(metrics_data)
    metrics_df = metrics_df.sort_values("達成率", ascending=False)
    
    # ダッシュボード表示（3列レイアウト）
    cols = st.columns(3)
    
    for i, (_, row) in enumerate(metrics_df.iterrows()):
        col_index = i % 3
        with cols[col_index]:
            # メトリクスカードの背景色を達成状況に応じて設定
            if row["状態"] == "達成":
                card_color = "rgba(76, 175, 80, 0.1)"  # 緑 (薄く)
                text_color = "#4CAF50"  # 緑
            elif row["状態"] == "注意":
                card_color = "rgba(255, 152, 0, 0.1)"  # オレンジ (薄く)
                text_color = "#FF9800"  # オレンジ
            else:
                card_color = "rgba(244, 67, 54, 0.1)"  # 赤 (薄く)
                text_color = "#F44336"  # 赤
            
            # カスタムHTMLを使用してメトリクスカードを作成
            html = f"""
            <div style="background-color: {card_color}; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <h4 style="margin-top: 0; color: {text_color};">{row["診療科"]}</h4>
                <div style="display: flex; justify-content: space-between;">
                    <span>週平均:</span>
                    <span style="font-weight: bold;">{row["直近4週平均"]:.1f} 件</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>目標:</span>
                    <span>{row["週間目標"]} 件</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>達成率:</span>
                    <span style="font-weight: bold; color: {text_color};">{row["達成率"]:.1f}%</span>
                </div>
                <div style="background-color: #e0e0e0; height: 4px; border-radius: 2px; margin-top: 0.5rem;">
                    <div style="background-color: {text_color}; width: {min(row["達成率"], 100)}%; height: 100%; border-radius: 2px;"></div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
    
    # 詳細テーブルを折りたたみセクションで表示
    with st.expander("詳細データテーブル", expanded=False):
        st.dataframe(
            metrics_df.style
                .format({"直近4週平均": "{:.1f}", "達成率": "{:.1f}%"})
                .set_table_styles(sc.TABLE_STYLE_PROPS)
                .apply(lambda x: [
                    f"background-color: rgba(76, 175, 80, 0.2)" if x["達成率"] >= 100 else
                    f"background-color: rgba(255, 152, 0, 0.2)" if x["達成率"] >= 80 else
                    f"background-color: rgba(244, 67, 54, 0.2)"
                    for _ in range(len(x))
                ], axis=1),
            hide_index=True,
            use_container_width=True
        )

# =======================
# データアップロードタブ
# =======================
if sidebar_tab == "データアップロード":
    st.header("📊 データファイルアップロード")
    st.markdown("### ステップ1: 基礎データと目標データのアップロード")
    st.info("手術実績データ(CSV)と、任意で目標データ(CSV)をアップロードしてください。")
    col1, col2 = st.columns(2)
    with col1: uploaded_base_file = st.file_uploader("基礎データCSV", type="csv", key="base_uploader", help="必須。手術実績データ全体。")
    with col2: uploaded_target_file = st.file_uploader("目標データCSV", type="csv", key="target_uploader", help="任意。列名例: '診療科', '目標'")
    st.markdown("### ステップ2: 追加データ（任意）のアップロード")
    st.info("基礎データ以降の最新データがあればアップロードします。")
    uploaded_update_files = st.file_uploader("追加データCSV", type="csv", accept_multiple_files=True, key="update_uploader", help="基礎データと同じ形式のCSV。")
    if uploaded_base_file:
        try:
            st.session_state['base_df'] = load_single_file(uploaded_base_file)
            st.success("基礎データを読み込みました。")
            with st.expander("基礎データ概要", expanded=False):
                st.write(f"レコード数: {len(st.session_state['base_df'])}件")
                if '手術実施日_dt' in st.session_state['base_df'].columns and not st.session_state['base_df']['手術実施日_dt'].isnull().all():
                     st.write(f"期間: {st.session_state['base_df']['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {st.session_state['base_df']['手術実施日_dt'].max().strftime('%Y/%m/%d')}")
                     st.dataframe(st.session_state['base_df'].head().style.format(precision=0).set_table_styles(sc.TABLE_STYLE_PROPS))
                     # 読み込み時に latest_date も更新しておく
                     st.session_state['latest_date'] = st.session_state['base_df']['手術実施日_dt'].max()
                else: st.warning("有効な'手術実施日'が見つかりません。")
        except Exception as e: st.error(f"基礎データ読込エラー: {e}"); st.session_state['base_df'] = None
    if uploaded_target_file:
        try:
            st.session_state['target_dict'] = load_target_file(uploaded_target_file)
            st.success("目標データを読み込みました。")
            with st.expander("目標データ概要", expanded=False):
                 if st.session_state['target_dict']:
                     target_df = pd.DataFrame({'診療科': list(st.session_state['target_dict'].keys()), '目標件数/週': list(st.session_state['target_dict'].values())})
                     st.dataframe(target_df.style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                 else: st.write("目標データは空か読込不可でした。")
        except Exception as e: st.error(f"目標データ読込エラー: {e}"); st.session_state['target_dict'] = {}
    if st.session_state.get('base_df') is not None:
        base_to_merge = st.session_state['base_df'].copy()
        try:
            if uploaded_update_files: st.session_state['df_gas'] = merge_base_and_updates(base_to_merge, uploaded_update_files)
            else: st.session_state['df_gas'] = base_to_merge
            st.success("データ準備完了。")
        except Exception as e: st.error(f"データ統合エラー: {e}"); st.session_state['df_gas'] = base_to_merge
        if st.session_state.get('df_gas') is not None and not st.session_state['df_gas'].empty:
             final_df = st.session_state['df_gas']
             if '手術実施日_dt' in final_df.columns and not final_df['手術実施日_dt'].isnull().all():
                 # 統合後のデータで latest_date を最終更新
                 st.session_state['latest_date'] = final_df['手術実施日_dt'].max()
                 col_m1, col_m2 = st.columns(2)
                 with col_m1: st.metric("全データ期間", f"{final_df['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {st.session_state['latest_date'].strftime('%Y/%m/%d')}")
                 with col_m2: st.metric("総レコード数", f"{len(final_df)} 件")
             else: st.warning("日付情報がないため分析できません。"); st.session_state['latest_date'] = None
        else: st.warning("有効なデータがありません。")

# ============================
# 病院全体分析タブ
# ============================

elif sidebar_tab == "病院全体分析":
    st.header("🏥 病院全体分析")
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty or st.session_state.get('latest_date') is None:
        st.warning("データ未準備または日付情報がありません。データアップロードタブを確認してください。")
    else:
        try:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            latest_date = st.session_state['latest_date']
            st.info(f"分析対象期間: {df_gas['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {latest_date.strftime('%Y/%m/%d')}")
            # ここに新しいダッシュボード機能を追加 (分析単位の前に配置)
            create_department_dashboard(df_gas, target_dict, latest_date)
            analysis_period = st.radio("分析単位", ["週単位", "月単位", "四半期単位"], horizontal=True, key="hosp_period")

            # 週単位分析の実装
            if analysis_period == "週単位":
                st.subheader("📈 週単位推移")
                with st.expander("表示オプション"):
                    period_options = ["全期間", "昨年度以降", "直近180日", "直近90日"]
                    selected_period = st.radio("表示期間", period_options, index=1, horizontal=True, key="hosp_period_sel")
                    ma_options = [0, 2, 4, 8, 12]
                    selected_ma = st.select_slider("移動平均(週)", options=ma_options, value=4, key="hosp_ma", help="0で非表示")

                filtered_df = filter_data_by_period(df_gas, selected_period)
                hospital_summary = analyze_hospital_summary(filtered_df)

                if not hospital_summary.empty:
                    st.metric(f"直近週 ({hospital_summary['週'].iloc[-1].strftime('%Y/%m/%d')}週) 平日1日平均",
                             f"{hospital_summary['平日1日平均件数'].iloc[-1]:.1f} 件/日")

                    # UI用グラフ
                    fig_weekly_ui = plot_summary_graph(hospital_summary, "全科", target_dict, selected_ma)
                    st.plotly_chart(fig_weekly_ui, use_container_width=True)

                    # --- 年度末 着地予測ブロックを削除 ---

                    # --- モデル予測に基づく年度末見通しブロックも削除 ---

                    # PDF出力ボタンを追加 (表示位置は変更なし)
                    col_pdf, col_exp = st.columns([1, 3])
                    with col_pdf:
                        # PDF用グラフ（4週移動平均強制）
                        fig_weekly_pdf = plot_summary_graph(hospital_summary, "全科", target_dict, 4)
                        # 週次レポートの追加情報
                        recent_averages = calculate_recent_averages(df_gas)
                        # 病院全体累積データ計算
                        current_year_pdf = latest_date.year
                        fiscal_year_start_year_pdf = current_year_pdf if latest_date.month >= 4 else current_year_pdf - 1
                        hospital_cum_start_date_pdf = pd.Timestamp(f'{fiscal_year_start_year_pdf}-04-01')
                        hospital_cum_data_pdf = None
                        hospital_cum_fig_pdf = None
                        hospital_weekly_target_pdf = 95 # 仮

                        if hospital_cum_start_date_pdf <= latest_date:
                             df_hospital_period_for_cum_pdf = df_gas[
                                 (df_gas["手術実施日_dt"] >= hospital_cum_start_date_pdf) &
                                 (df_gas["手術実施日_dt"] <= latest_date)
                             ].copy()
                             if not df_hospital_period_for_cum_pdf.empty:
                                 hospital_cum_data_pdf = calculate_cumulative_cases(df_hospital_period_for_cum_pdf, "全診療科", hospital_weekly_target_pdf)
                                 if not hospital_cum_data_pdf.empty:
                                     hospital_cum_fig_pdf = plot_cumulative_cases(hospital_cum_data_pdf, "全診療科")

                        pdf_extras_hosp_w = {
                            'averages_data': recent_averages,
                            'cumulative_data': hospital_cum_data_pdf,
                            'cumulative_fig': hospital_cum_fig_pdf
                        }
                        add_pdf_report_button('hospital', 'weekly', hospital_summary, fig_weekly_pdf,
                                         target_dict=target_dict, extras=pdf_extras_hosp_w)

                    with col_exp:
                        with st.expander("集計テーブル"):
                            display_cols = ['週', '全日件数', '平日件数', '平日日数', '平日1日平均件数']
                            ma_col_name = f'移動平均_{selected_ma}週'
                            if selected_ma > 0 and ma_col_name in hospital_summary.columns:
                                display_cols.append(ma_col_name)
                            st.dataframe(hospital_summary[display_cols].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                            render_download_button(hospital_summary[display_cols], "hospital", "weekly")
                else:
                    st.warning(f"期間「{selected_period}」にデータがありません。")

                # --- 期間別平均と予測指標のサマリーテーブル ---
                st.markdown("---")
                st.subheader("📊 期間別平均と予測指標")

                col_avg, col_forecast = st.columns(2) # 2列レイアウト

                with col_avg:
                    st.markdown("**期間別平均**")
                    # 期間別平均の計算 (全科、申込区分なし)
                    recent_averages_summary = calculate_recent_averages(df_gas, None)
                    if recent_averages_summary is not None and not recent_averages_summary.empty:
                        # 表示する列を絞り込む
                        avg_display_cols = ["期間", "平日1日平均件数"]
                        st.dataframe(
                            recent_averages_summary[avg_display_cols].style
                            .format({"平日1日平均件数": "{:.1f}"}) # 数値フォーマット適用
                            .set_table_styles(sc.TABLE_STYLE_PROPS)
                            .hide(axis="index") # インデックス非表示
                        )
                    else:
                        st.warning("期間別平均データ無し")

                # フォーマット用の関数を定義 (with col_forecast: の前に配置)
                def format_forecast_value(x, df_display, format_dict):
                    """予測指標の値に応じたフォーマットを適用する関数"""
                    if pd.isna(x):
                        return 'N/A'
                    try:
                        # 値 x に対応する指標名を df_display から検索
                        # 注意: 同じ値が複数の指標に含まれる場合、最初のものだけが使われる
                        metric_series = df_display.loc[df_display['値'] == x, '指標']
                        if not metric_series.empty:
                            metric = metric_series.iloc[0]
                            fmt = format_dict.get(metric, '{:}') # format_dict を参照
                            return fmt.format(x)
                        else:
                            # 値でメトリックが見つからない場合はデフォルトフォーマット
                            return '{:}'.format(x)
                    except (ValueError, TypeError, IndexError):
                        return 'N/A' # エラー時は N/A
                        
                with col_forecast:
                    st.markdown("**予測指標**", help="『将来予測』タブで最後に実行されたモデルの予測結果です。")
                    # --- 予測指標の表示 (セッションステートから取得) ---
                    forecast_metrics = st.session_state.get('hospital_forecast_metrics')

                    if forecast_metrics:
                        model_used = forecast_metrics.get('model_used', 'N/A')
                        total_cases_pred = forecast_metrics.get('total_cases', 'N/A')
                        achieve_rate_pred = forecast_metrics.get('achievement_rate', 'N/A')

                        # 表示用データリスト作成
                        display_data = [
                            {"指標": "年度合計予測", "値": total_cases_pred},
                            {"指標": "目標達成率予測", "値": achieve_rate_pred},
                        ]
                        forecast_df_display = pd.DataFrame(display_data)

                        # フォーマット定義
                        formatters = {
                            '年度合計予測': '{:,.0f} 件',
                            '目標達成率予測': '{:.1f}%'
                        }

                        # スタイラーでフォーマット適用
                        styler = forecast_df_display.style
                        styler = styler.format(lambda val: format_forecast_value(val, forecast_df_display, formatters), subset=['値'])
                        st.dataframe(
                            styler
                            .hide(axis="index") # インデックス非表示
                            .set_table_styles(sc.TABLE_STYLE_PROPS),
                            use_container_width=True
                        )
                        st.caption(f"(使用モデル: {model_used})")

                    else:
                        st.info("将来予測タブで予測を実行すると、モデルベースの予測指標が表示されます。")
                # --- サマリーテーブルここまで ---


            # 月単位分析の実装
            elif analysis_period == "月単位":
                st.subheader("📅 月単位推移")
                hospital_monthly = analyze_monthly_summary(df_gas)

                if not hospital_monthly.empty:
                    st.metric(f"直近月 ({hospital_monthly['月'].iloc[-1].strftime('%Y年%m月')}) 平日1日平均",
                             f"{hospital_monthly['平日1日平均件数'].iloc[-1]:.1f} 件/日")

                    fig_monthly = plot_monthly_hospital_graph(hospital_monthly, target_dict)
                    st.plotly_chart(fig_monthly, use_container_width=True)

                    # PDF出力ボタンを追加
                    col_pdf, col_exp = st.columns([1, 3]) # レイアウト調整
                    with col_pdf:
                        add_pdf_report_button('hospital', 'monthly', hospital_monthly, fig_monthly, target_dict=target_dict)

                    with col_exp:
                        with st.expander("集計テーブル"):
                            display_cols_m = ['月', '全日件数', '平日件数', '平日日数', '平日1日平均件数']
                            if '6ヶ月移動平均' in hospital_monthly.columns:
                                display_cols_m.append('6ヶ月移動平均')
                            if '3ヶ月移動平均' in hospital_monthly.columns:
                                display_cols_m.append('3ヶ月移動平均')
                            st.dataframe(hospital_monthly[display_cols_m].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                            render_download_button(hospital_monthly[display_cols_m], "hospital", "monthly")
                else:
                    st.warning("月単位データ無し")

            # 四半期単位分析の実装
            elif analysis_period == "四半期単位":
                st.subheader("🗓️ 四半期単位推移")
                hospital_quarterly = analyze_quarterly_summary(df_gas)

                if not hospital_quarterly.empty:
                    st.metric(f"直近四半期 ({hospital_quarterly['四半期ラベル'].iloc[-1]}) 平日1日平均",
                             f"{hospital_quarterly['平日1日平均件数'].iloc[-1]:.1f} 件/日")

                    fig_quarterly = plot_quarterly_hospital_graph(hospital_quarterly, target_dict)
                    st.plotly_chart(fig_quarterly, use_container_width=True)

                    # PDF出力ボタンを追加
                    col_pdf, col_exp = st.columns([1, 3])
                    with col_pdf:
                        add_pdf_report_button('hospital', 'quarterly', hospital_quarterly, fig_quarterly, target_dict=target_dict)

                    with col_exp:
                        with st.expander("集計テーブル"):
                            display_cols_q = ['四半期ラベル', '全日件数', '平日件数', '平日日数', '平日1日平均件数']
                            if '前年同期平均' in hospital_quarterly.columns:
                                display_cols_q.append('前年同期平均')
                            st.dataframe(hospital_quarterly[display_cols_q].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                            render_download_button(hospital_quarterly[display_cols_q], "hospital", "quarterly")
                else:
                    st.warning("四半期データ無し")
                    
            # --- 診療科別目標達成率テーブルを追加 ---
            st.markdown("---")
            render_department_performance_table(df_gas, target_dict, latest_date)
                    
        except Exception as e:
            st.error(f"病院全体分析エラー: {e}")
            st.exception(e)

# ============================
# 診療科別分析タブ (変更なし)
# ============================
elif sidebar_tab == "診療科別分析":
    st.header("🩺 診療科別分析")
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty or st.session_state.get('latest_date') is None:
        st.warning("データ未準備または日付情報がありません。")
    else:
        try:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            latest_date = st.session_state['latest_date']
            all_departments_list = sorted(df_gas["実施診療科"].dropna().unique().tolist())
            dept_options = ["全診療科"] + all_departments_list

            if not dept_options:
                st.warning("データ内に診療科情報が見つかりません。")
            else:
                selected_entity = st.selectbox("分析対象を選択", dept_options, key="dept_entity_select")
                st.info(f"対象期間: {df_gas['手術実施日_dt'].min().strftime('%Y/%m/%d')}～{latest_date.strftime('%Y/%m/%d')} | 分析対象: **{selected_entity}**")

                if selected_entity != "全診療科":
                    st.subheader(f"📈 {selected_entity}：期間別 推移")
                    analysis_period_dept = st.radio("分析単位", ["週単位", "月単位", "四半期単位"], horizontal=True, key="dept_period")

                    # 週単位分析
                    if analysis_period_dept == "週単位":
                        with st.expander("表示オプション"):
                            period_options_d = ["全期間", "昨年度以降", "直近180日", "直近90日"]
                            selected_period_d = st.radio("表示期間", period_options_d, index=1, horizontal=True, key="dept_period_sel")
                            ma_options_d = [0, 2, 4, 8, 12]
                            selected_ma_d = st.select_slider("移動平均(週)", options=ma_options_d, value=4, key="dept_ma")

                        filtered_df_d = filter_data_by_period(df_gas, selected_period_d)
                        department_summary = analyze_department_summary(filtered_df_d, selected_entity)

                        if not department_summary.empty:
                            st.metric(f"直近週 ({department_summary['週'].iloc[-1].strftime('%Y/%m/%d')}週) 合計",
                                     f"{department_summary['週合計件数'].iloc[-1]} 件")

                            # UI用グラフ
                            fig_dept_weekly_ui = plot_department_graph(department_summary, selected_entity, target_dict, selected_ma_d)
                            st.plotly_chart(fig_dept_weekly_ui, use_container_width=True)

                            # --- 年度末 着地予測 (診療科別) ---
                            # st.markdown("---")
                            # st.subheader(f"🎯 {selected_entity} 年度末 着地予測")
                            # df_dept = df_gas[df_gas["実施診療科"] == selected_entity] # calculate_pace_projection削除に伴い不要
                            # current_weekly_target = target_dict.get(selected_entity, 0) if target_dict else 0 # 同上
                            # calculate_pace_projection は削除されたため、このブロックはコメントアウトまたは削除
                            # projection_results_dept = calculate_pace_projection(df_dept, latest_date, pace_period_days=28, entity_name=selected_entity, weekly_target=current_weekly_target)
                            # if 'error' in projection_results_dept:
                            #     st.warning(projection_results_dept['error'])
                            # else:
                            #     cols_dept = st.columns(3)
                            #     ... (表示部分) ...
                            # st.info("診療科別の着地予測表示は現在削除されています。") # 代替メッセージ
                            # --- 予測ここまで ---


                            # PDF出力ボタンを追加
                            col_pdf, col_exp = st.columns([1, 3])
                            with col_pdf:
                                # PDF用グラフ（4週移動平均強制）
                                fig_dept_weekly_pdf = plot_department_graph(department_summary, selected_entity, target_dict, 4)
                                # 診療科別レポートには月次データと累積データも含める
                                monthly_dept_data = analyze_monthly_department_summary(df_gas, selected_entity)
                                monthly_dept_fig = None
                                if not monthly_dept_data.empty:
                                    monthly_dept_fig = plot_monthly_department_graph(monthly_dept_data, selected_entity, target_dict)

                                # 累積データの準備
                                current_year = latest_date.year
                                fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
                                cum_start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')
                                cum_end_date = latest_date

                                cumulative_data = None
                                cumulative_fig = None
                                current_weekly_target = target_dict.get(selected_entity, 0) if target_dict else 0 # 再計算

                                if cum_start_date <= cum_end_date:
                                    df_dept_period_for_cum = df_gas[
                                        (df_gas["実施診療科"] == selected_entity) &
                                        (df_gas["手術実施日_dt"] >= cum_start_date) &
                                        (df_gas["手術実施日_dt"] <= cum_end_date)
                                    ].copy()

                                    if not df_dept_period_for_cum.empty:
                                        cumulative_data = calculate_cumulative_cases(df_dept_period_for_cum, selected_entity, current_weekly_target)
                                        if not cumulative_data.empty:
                                            cumulative_fig = plot_cumulative_cases(cumulative_data, selected_entity)

                                extras = {
                                    'monthly_data': monthly_dept_data,
                                    'monthly_fig': monthly_dept_fig,
                                    'cumulative_data': cumulative_data,
                                    'cumulative_fig': cumulative_fig
                                }

                                add_pdf_report_button('department', 'weekly', department_summary, fig_dept_weekly_pdf, # PDF用グラフを渡す
                                                 department=selected_entity, target_dict=target_dict, extras=extras)

                            with col_exp:
                                with st.expander("集計テーブル (週次)"):
                                    display_cols_dw = ['週', '週合計件数']
                                    moving_avg_col_dw = f'移動平均_{selected_ma_d}週'
                                    if selected_ma_d > 0 and moving_avg_col_dw in department_summary.columns:
                                        display_cols_dw.append(moving_avg_col_dw)
                                    st.dataframe(department_summary[display_cols_dw].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                                    render_download_button(department_summary[display_cols_dw], "department", "weekly", selected_entity)
                        else:
                            st.warning(f"期間「{selected_period_d}」に {selected_entity} のデータがありません。")

                    # 月単位分析
                    elif analysis_period_dept == "月単位":
                        department_monthly = analyze_monthly_department_summary(df_gas, selected_entity)
                        if not department_monthly.empty:
                            st.metric(f"直近月 ({department_monthly['月'].iloc[-1].strftime('%Y年%m月')}) 合計",
                                    f"{department_monthly['月合計件数'].iloc[-1]} 件")

                            fig_dept_monthly = plot_monthly_department_graph(department_monthly, selected_entity, target_dict)
                            st.plotly_chart(fig_dept_monthly, use_container_width=True)

                            # PDF出力ボタンを追加
                            col_pdf, col_exp = st.columns([1, 3])
                            with col_pdf:
                                add_pdf_report_button('department', 'monthly', department_monthly, fig_dept_monthly,
                                                  department=selected_entity, target_dict=target_dict)

                            with col_exp:
                                with st.expander("集計テーブル (月次)"):
                                    display_cols_dm = ['月', '月合計件数']
                                    if '6ヶ月移動平均' in department_monthly.columns:
                                        display_cols_dm.append('6ヶ月移動平均')
                                    if '3ヶ月移動平均' in department_monthly.columns:
                                        display_cols_dm.append('3ヶ月移動平均')
                                    st.dataframe(department_monthly[display_cols_dm].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                                    render_download_button(department_monthly[display_cols_dm], "department", "monthly", selected_entity)
                        else:
                            st.warning(f"月単位で {selected_entity} のデータ無し")

                    # 四半期単位分析
                    elif analysis_period_dept == "四半期単位":
                        department_quarterly = analyze_quarterly_department_summary(df_gas, selected_entity)
                        if not department_quarterly.empty:
                            st.metric(f"直近四半期 ({department_quarterly['四半期ラベル'].iloc[-1]}) 合計",
                                    f"{department_quarterly['四半期合計件数'].iloc[-1]} 件")

                            fig_dept_quarterly = plot_quarterly_department_graph(department_quarterly, selected_entity, target_dict)
                            st.plotly_chart(fig_dept_quarterly, use_container_width=True)

                            # PDF出力ボタンを追加
                            col_pdf, col_exp = st.columns([1, 3])
                            with col_pdf:
                                add_pdf_report_button('department', 'quarterly', department_quarterly, fig_dept_quarterly,
                                                  department=selected_entity, target_dict=target_dict)

                            with col_exp:
                                with st.expander("集計テーブル (四半期)"):
                                    display_cols_dq = ['四半期ラベル', '四半期合計件数']
                                    if '前年同期件数' in department_quarterly.columns:
                                        display_cols_dq.append('前年同期件数')
                                    st.dataframe(department_quarterly[display_cols_dq].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                                    render_download_button(department_quarterly[display_cols_dq], "department", "quarterly", selected_entity)
                        else:
                            st.warning(f"四半期単位で {selected_entity} のデータ無し")

                # --- 累積実績 vs 目標グラフ ---
                st.markdown("---")
                st.subheader(f"📊 {selected_entity}：累積実績 vs 目標 推移 (今年度週次)")
                cum_start_date = None
                cum_end_date = latest_date
                current_year = latest_date.year
                fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
                cum_start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')

                if cum_start_date > latest_date:
                    cum_start_date = pd.Timestamp(f'{fiscal_year_start_year-1}-04-01')

                st.caption(f"集計期間: {cum_start_date.strftime('%Y/%m/%d')} ～ {cum_end_date.strftime('%Y/%m/%d')}")
                current_weekly_target = 0

                if selected_entity == "全診療科":
                    # 全診療科の目標値は別途定義するか、合計値を計算する必要がある
                    # ここでは仮に 95 とする
                    current_weekly_target = 95 # 仮の値
                    st.info("全診療科の目標値は仮に95件/週として表示しています。")
                elif target_dict:
                    current_weekly_target = target_dict.get(selected_entity, 0)

                if current_weekly_target <= 0 and selected_entity != "全診療科":
                    st.warning(f"{selected_entity} の週次目標値が0または未設定のため、目標ラインは表示されません。")

                if cum_start_date is not None and cum_start_date <= cum_end_date:
                    # フィルタリング条件を修正
                    df_dept_period_for_cum = df_gas[
                        (df_gas["実施診療科"] == selected_entity if selected_entity != "全診療科" else True) & # 全診療科の場合フィルタしない
                        (df_gas["手術実施日_dt"] >= cum_start_date) &
                        (df_gas["手術実施日_dt"] <= cum_end_date)
                    ].copy()

                    if not df_dept_period_for_cum.empty:
                        cumulative_data = calculate_cumulative_cases(df_dept_period_for_cum, selected_entity, current_weekly_target)

                        if not cumulative_data.empty:
                            fig_cumulative = plot_cumulative_cases(cumulative_data, selected_entity)
                            st.plotly_chart(fig_cumulative, use_container_width=True)

                            # PDF出力ボタンを追加（累積データ用）
                            col_pdf_cum, col_exp_cum = st.columns([1, 3])
                            with col_pdf_cum:
                                add_pdf_report_button('department', 'cumulative', cumulative_data, fig_cumulative,
                                                 department=selected_entity, target_dict=target_dict)

                            with col_exp_cum:
                                with st.expander("累積データテーブル (今年度週次)"):
                                    display_cols_cum = ['週','週次実績','累積実績件数', '累積目標件数']
                                    valid_display_cols = [col for col in display_cols_cum if col in cumulative_data.columns]
                                    if valid_display_cols:
                                        st.dataframe(cumulative_data[valid_display_cols].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                                        render_download_button(cumulative_data[valid_display_cols], "cumulative_cases", "fiscal_year", selected_entity)
                                    else:
                                        st.warning("表示する累積データ列が見つかりません。")
                        else:
                            st.info(f"今年度の {selected_entity} の累積データがありません。(計算結果が空)")
                    else:
                        st.info(f"今年度に {selected_entity} のデータがありません。(フィルタ後が空)")
                else:
                    st.warning("有効な今年度の期間が設定できません。")
        except Exception as e:
            st.error(f"診療科別分析でエラーが発生しました: {e}")
            st.exception(e)


# ============================
# 診療科ランキングタブ (変更なし)
# ============================
elif sidebar_tab == "診療科ランキング":
    st.header("🏆 診療科ランキング")
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty or st.session_state.get('latest_date') is None:
        st.warning("データ未準備または日付情報がありません。")
    elif not st.session_state.get('target_dict'):
        st.warning("ランキング表示には目標データが必要です。")
    else:
        try:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            latest_date = st.session_state['latest_date']

            st.info(f"ランキング集計基準日: **{latest_date.strftime('%Y年%m月%d日')}**")

            col1_rank, col2_rank = st.columns(2)
            with col1_rank:
                ranking_period_options = ["今年度", "直近30日", "直近60日", "直近90日", "直近180日", "直近365日"]
                selected_ranking_period_label = st.selectbox("集計期間", ranking_period_options, index=0, key="ranking_period", help="この期間の実績と目標を比較します")

            with col2_rank:
                avail_depts = df_gas['実施診療科'].nunique()
                max_slider = max(3, avail_depts)
                default_n = min(10, max_slider)
                top_n = st.slider("表示診療科数 (達成率TopN)", min_value=3, max_value=max_slider, value=default_n, key="top_n_slider")

            # 期間の開始日と終了日を設定
            start_date = None
            end_date = latest_date

            # 今年度の処理を修正
            if selected_ranking_period_label == "今年度":
                # 現在の日付から年度を正確に判断
                current_year = latest_date.year
                # 4月1日より前なら前年度、4月1日以降なら当年度
                fiscal_year_start_year = current_year if latest_date.month >= 4 else current_year - 1
                # 年度開始日を設定
                start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')

                # 年度の開始日は必ず4月1日に設定（None対策）
                if start_date is None:
                    start_date = pd.Timestamp(f'{fiscal_year_start_year}-04-01')

                # 開始日が最終日より後になることはない（論理エラー防止）
                if start_date > latest_date:  # このチェックは念のため残す
                    # 前年度の4月1日に設定
                    start_date = pd.Timestamp(f'{fiscal_year_start_year-1}-04-01')

                st.caption(f"集計期間: {start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}")
            else:
                # 直近X日の処理
                days_map = {"直近30日": 30, "直近60日": 60, "直近90日": 90, "直近180日": 180, "直近365日": 365}
                days = days_map.get(selected_ranking_period_label, 90)
                start_date = latest_date - pd.Timedelta(days=days - 1)
                st.caption(f"集計期間: {start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}")

            # start_dateがNoneでないことを確認
            if start_date is None:
                st.error("集計開始日が設定できませんでした。")
                filtered_df_rank = pd.DataFrame()
            # 正常な期間でデータをフィルタリング
            elif start_date <= end_date:
                filtered_df_rank = df_gas[(df_gas["手術実施日_dt"] >= start_date) & (df_gas["手術実施日_dt"] <= end_date)].copy()
            else:
                st.error("集計期間の設定に問題があります。開始日が終了日より後になっています。")
                filtered_df_rank = pd.DataFrame()

            if not filtered_df_rank.empty:
                achievement_rates, achievement_summary = calculate_department_achievement_rates(filtered_df_rank, target_dict)
            else:
                achievement_rates, achievement_summary = pd.DataFrame(), pd.DataFrame()

            if achievement_rates is not None and not achievement_rates.empty:
                st.subheader(f"{selected_ranking_period_label} 目標達成率ランキング")
                col_chart, col_summary = st.columns([3, 1])

                with col_chart:
                    fig_rank = plot_achievement_ranking(achievement_rates, top_n)
                    st.plotly_chart(fig_rank, use_container_width=True)

                with col_summary:
                    if achievement_summary is not None and not achievement_summary.empty:
                        st.subheader("達成状況サマリー")
                        st.dataframe(achievement_summary.style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                    else:
                        st.write("サマリー情報無し")

                # PDF出力ボタンを追加（ランキング用）
                col_pdf_rank, col_exp_rank = st.columns([1, 3])
                with col_pdf_rank:
                    # ランキングレポート用のPDF出力ボタン
                    add_pdf_report_button('ranking', 'summary', achievement_rates, fig_rank,
                                     target_dict=target_dict, extras=achievement_summary)

                with col_exp_rank:
                    with st.expander("ランキング詳細テーブル"):
                        display_cols_rank = ['診療科', '実績件数', '期間内目標件数', '達成率(%)']
                        valid_cols = [col for col in display_cols_rank if col in achievement_rates.columns]
                        st.dataframe(achievement_rates[valid_cols].style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                        render_download_button(achievement_rates[valid_cols], "department", "ranking", f"period_{selected_ranking_period_label}")
            else:
                st.warning(f"選択した期間「{selected_ranking_period_label}」のランキングデータがありません。")
        except Exception as e:
            st.error(f"診療科ランキングエラー: {e}")
            st.exception(e)

# ============================
# 術者分析タブ (新規追加)
# ============================
elif sidebar_tab == "術者分析":
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty or st.session_state.get('latest_date') is None:
        st.warning("データ未準備または日付情報がありません。データアップロードタブを確認してください。")
    else:
        try:
            df_gas = st.session_state['df_gas']
            target_dict = st.session_state.get('target_dict', {})
            latest_date = st.session_state['latest_date']
            st.info(f"分析対象期間: {df_gas['手術実施日_dt'].min().strftime('%Y/%m/%d')} ～ {latest_date.strftime('%Y/%m/%d')}")
            
            # 術者分析の実行（target_dictを渡す）
            create_surgeon_analysis(df_gas, target_dict)
            
        except Exception as e:
            st.error(f"術者分析でエラーが発生しました: {e}")
            st.exception(e)

# ============================
# 将来予測タブ (変更なし)
# ============================
elif sidebar_tab == "将来予測":
    # st.header("🔮 将来予測") # ヘッダーは prediction_tab_enhanced 内
    if st.session_state.get('df_gas') is None or st.session_state['df_gas'].empty or st.session_state.get('latest_date') is None:
        st.warning("データ未準備または日付情報がありません。")
    else:
        df_gas = st.session_state['df_gas']
        target_dict = st.session_state.get('target_dict', {})
        latest_date = st.session_state['latest_date']
        try:
            create_prediction_tab(df_gas, target_dict, latest_date) # from ... import ... 形式
        except NameError:
            st.error(f"エラー: 'create_prediction_tab' 関数が見つかりません。\n`prediction_tab_enhanced.py` ファイルを確認してください。")
        except Exception as e:
            st.error(f"将来予測タブで予期せぬエラーが発生しました: {e}")
            st.exception(e)