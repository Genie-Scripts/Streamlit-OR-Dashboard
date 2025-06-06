# prediction_tab_enhanced.py (予測結果保存追加)
import streamlit as st
import pandas as pd
import numpy as np 
import plotly.graph_objects as go
from datetime import datetime, timedelta
import calendar
import style_config as sc # スタイル定義をインポート
import concurrent.futures
from functools import partial

# prediction_validation と hospital_prediction をインポート
try:
    from hospital_prediction import predict_hospital_future, predict_department_future
    from prediction_validation import validate_prediction_model, optimize_seasonal_model_params
except ImportError as e:
    st.error(f"予測関連モジュールの読み込みエラー: {e}")
    # 実行継続は難しいので停止する
    st.stop()


# --- 単一モデルの予測を行う関数（並列処理用） ---
def predict_model_parallel(df_gas, model_type, prediction_period_type, custom_params=None, department=None):
    """単一モデルの予測を行う関数（並列処理用）"""
    try:
        if department is None:
            # 病院全体の予測
            _, _, metrics = predict_hospital_future(
                df_gas,
                prediction_period=prediction_period_type,
                model_type=model_type,
                custom_params=custom_params
            )
        else:
            # 診療科別の予測
            _, _, metrics = predict_department_future(
                df_gas,
                department=department,
                prediction_period=prediction_period_type,
                model_type=model_type,
                custom_params=custom_params
            )
        return model_type, metrics
    except Exception as e:
        print(f"モデル {model_type} の予測でエラーが発生: {e}")
        return model_type, {"error": str(e)}

# --- 複数モデルの予測を並列実行する関数 ---
def get_multi_model_forecast_parallel(df_gas, prediction_period_type, model_types, custom_params=None, department=None):
    """複数モデルの予測を並列実行し、結果を集約する関数"""
    
    # partial関数で引数を事前に設定（df_gasは含めない）
    predict_func = partial(
        predict_model_parallel, 
        prediction_period_type=prediction_period_type,
        custom_params=custom_params,
        department=department
    )
    
    all_metrics = {}
    
    # ThreadPoolExecutorを使用して並列処理
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(model_types), 3)) as executor:
        # df_gasはここで各呼び出しに渡す
        future_to_model = {executor.submit(predict_func, df_gas=df_gas, model_type=model_type): model_type for model_type in model_types}
        
        for future in concurrent.futures.as_completed(future_to_model):
            model_type, metrics = future.result()
            all_metrics[model_type] = metrics
    
    return all_metrics

# --- Helper Functions ---
def hospital_prediction_ui(df_gas, target_dict, latest_date):
    """
    病院全体の予測分析UI（将来予測タブ内で使用）
    """
    # 予測設定セクション
    st.subheader("予測設定")

    col1, col2 = st.columns(2)

    with col1:
        # 予測期間の選択
        prediction_period_options = ["年度末まで", "暦年末まで", "6ヶ月後まで"]
        selected_prediction_period = st.radio("予測期間", prediction_period_options, horizontal=True, key="pred_term_hosp")

        # 選択に応じた予測期間タイプの設定
        if selected_prediction_period == "年度末まで":
            prediction_period_type = "fiscal_year"
        elif selected_prediction_period == "暦年末まで":
            prediction_period_type = "calendar_year"
        else:
            prediction_period_type = "six_months"

    with col2:
        # 予測モデルの選択
        model_options = {
            "hwes": "季節性Holt-Winters（推奨）",
            "arima": "ARIMA",
            "moving_avg": "単純移動平均"
        }
        selected_model = st.selectbox("予測モデル", list(model_options.keys()), format_func=lambda x: model_options[x], key="pred_model_hosp")

    # カスタムパラメータのオプション
    use_custom_params = st.checkbox("カスタムパラメータを使用", value=False, key="pred_custom_cb_hosp")

    custom_params = None # 初期化
    if use_custom_params:
        st.info("モデル検証タブまたはパラメータ最適化タブで得られた最適パラメータを入力してください。")
        custom_params_col1, custom_params_col2 = st.columns(2)
        with custom_params_col1:
            seasonal_periods = st.number_input("季節周期（月数）", min_value=3, max_value=24, value=12, step=1, key="pred_custom_sp_hosp")
            trend_type = st.selectbox("トレンド成分", ["add", "mul"], format_func=lambda x: "加法" if x == "add" else "乗法", key="pred_custom_trend_hosp")
        with custom_params_col2:
            seasonal_type = st.selectbox("季節成分", ["add", "mul"], format_func=lambda x: "加法" if x == "add" else "乗法", key="pred_custom_season_hosp")
            use_boxcox = st.checkbox("Box-Cox変換を使用", value=True, key="pred_custom_boxcox_hosp")
        custom_params = {"seasonal_periods": seasonal_periods, "trend": trend_type, "seasonal": seasonal_type, "use_boxcox": use_boxcox}

    # 複数モデルによる予測を同時に行うオプション
    run_all_models = st.checkbox("すべてのモデルで比較する", value=False, key="run_all_models_hosp")

    # 予測の実行
    if st.button("予測を実行", type="primary", key="pred_run_hosp"):
        with st.spinner("予測計算中..."):
            # 実行するモデルタイプを設定
            model_types_to_run = ['hwes', 'arima', 'moving_avg'] if run_all_models else [selected_model]
            
            # 初期化
            result_df = None
            fig = None
            metrics = {}
            all_model_metrics = {}
            
            try:
                if run_all_models:
                    # 並列処理で複数モデルを実行
                    all_model_metrics = get_multi_model_forecast_parallel(
                        df_gas, 
                        prediction_period_type, 
                        model_types_to_run, 
                        custom_params
                    )
                    
                    # 選択したモデルだけフルに取得（グラフ用）
                    result_df, fig, metrics = predict_hospital_future(
                        df_gas,
                        prediction_period=prediction_period_type,
                        model_type=selected_model,
                        custom_params=custom_params
                    )
                else:
                    # 単一モデルを実行
                    result_df, fig, metrics = predict_hospital_future(
                        df_gas,
                        prediction_period=prediction_period_type,
                        model_type=selected_model,
                        custom_params=custom_params
                    )
                    all_model_metrics = {selected_model: metrics}
                    
            except Exception as pred_e:
                st.error(f"予測計算中にエラーが発生しました: {pred_e}")

            if fig is None:
                st.warning(metrics.get("message", "予測に必要なデータが不足しているか、計算エラーが発生しました。"))
                # エラー時はセッションステートをクリア
                if 'hospital_forecast_metrics' in st.session_state:
                    del st.session_state['hospital_forecast_metrics']
            else:
                # 予測グラフの表示
                st.subheader("予測グラフ")
                st.plotly_chart(fig, use_container_width=True)

                # 予測メトリクスの表示
                st.subheader("予測指標")
                col1_met, col2_met = st.columns(2)
                with col1_met:
                    metrics_list1 = [
                        ("実績平均", f"{metrics.get('実績平均', 0):.1f} 件/日"),
                        ("予測平均", f"{metrics.get('予測平均', 0):.1f} 件/日"),
                        ("変化率(%)", f"{metrics.get('変化率(%)', 0):.1f} %"),
                    ]
                    metrics_df1 = pd.DataFrame(metrics_list1, columns=["指標", "値"])
                    st.dataframe(metrics_df1.style.set_table_styles(sc.TABLE_STYLE_PROPS), hide_index=True)
                with col2_met:
                    metrics_list2 = [
                        ("年度内平日数", f"{metrics.get('年度内平日数', 0)} 日"),
                        ("年度実績件数", f"{metrics.get('年度実績件数', 0)} 件"),
                        ("年度予測件数", f"{metrics.get('年度予測件数', 0)} 件"),
                        ("年度合計予測", f"{metrics.get('年度合計予測', 0)} 件"),
                        ("目標達成率予測", f"{metrics.get('目標達成率予測', 0):.1f} %")
                    ]
                    metrics_df2 = pd.DataFrame(metrics_list2, columns=["指標", "値"])
                    st.dataframe(metrics_df2.style.set_table_styles(sc.TABLE_STYLE_PROPS), hide_index=True)

                # 使用したモデル情報
                model_name_used = model_options.get(metrics.get('予測使用モデル', selected_model), selected_model)
                model_info = f"予測モデル：{model_name_used}"
                if custom_params: model_info += f"（カスタムパラメータ使用：季節周期={custom_params['seasonal_periods']}ヶ月）"
                st.info(model_info)

                # --- 予測結果をセッションステートに保存 ---
                st.session_state['hospital_forecast_metrics'] = {
                    'total_cases': metrics.get('年度合計予測', 'N/A'),
                    'achievement_rate': metrics.get('目標達成率予測', 'N/A'),
                    'model_used': model_name_used
                }
                # --- 保存ここまで ---

                # すべてのモデルを実行した場合は比較表を表示
                if run_all_models and len(all_model_metrics) > 1:
                    st.subheader("モデル比較")
                    comparison_data = []
                    for model_type, model_metrics in all_model_metrics.items():
                        if "error" not in model_metrics:
                            model_name = model_options.get(model_type, model_type)
                            comparison_data.append({
                                "モデル": model_name,
                                "予測平均": f"{model_metrics.get('予測平均', 0):.1f} 件/日",
                                "年度合計予測": f"{model_metrics.get('年度合計予測', 0):,} 件",
                                "目標達成率予測": f"{model_metrics.get('目標達成率予測', 0):.1f} %"
                            })
                    
                    if comparison_data:
                        comparison_df = pd.DataFrame(comparison_data)
                        st.dataframe(comparison_df.style.set_table_styles(sc.TABLE_STYLE_PROPS), hide_index=True)

                # 予測データテーブル
                st.subheader("予測データテーブル")
                if not result_df.empty and '月' in result_df.columns:
                    # データ種別フラグ追加
                    actual_cutoff = latest_date.replace(day=1) + pd.DateOffset(months=1)
                    result_df['データ種別'] = np.where(result_df['月'] < actual_cutoff, '実績', '予測')
                    st.dataframe(
                        result_df[['月', 'データ種別', '平日日数', '平日件数', '平日1日平均件数']].style
                            .format(sc.TABLE_COMMON_FORMAT_DICT)
                            .set_table_styles(sc.TABLE_STYLE_PROPS)
                    )
                else:
                    st.warning("予測結果データフレームが空です。")


def department_prediction_ui(df_gas, target_dict, latest_date):
    """
    診療科別の予測分析UI（将来予測タブ内で使用）
    """
    departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
    if not departments:
        st.warning("データに診療科情報が見つかりません。")
        return
    selected_department = st.selectbox("診療科を選択", departments, key="pred_dept_select")

    st.subheader(f"予測設定 ({selected_department})")
    col1, col2 = st.columns(2)
    with col1:
        prediction_period_options = ["年度末まで", "暦年末まで", "6ヶ月後まで"]
        selected_prediction_period = st.radio("予測期間", prediction_period_options, horizontal=True, key="pred_term_dept")
        if selected_prediction_period == "年度末まで": prediction_period_type = "fiscal_year"
        elif selected_prediction_period == "暦年末まで": prediction_period_type = "calendar_year"
        else: prediction_period_type = "six_months"
    with col2:
        model_options = {"hwes": "季節性Holt-Winters（推奨）", "arima": "ARIMA", "moving_avg": "単純移動平均"}
        selected_model = st.selectbox("予測モデル", list(model_options.keys()), format_func=lambda x: model_options[x], key="pred_model_dept")

    use_custom_params = st.checkbox("カスタムパラメータを使用", value=False, key="pred_custom_cb_dept")
    custom_params = None
    if use_custom_params:
        st.info("モデル検証タブまたはパラメータ最適化タブで得られた最適パラメータを入力してください。")
        cp_col1, cp_col2 = st.columns(2)
        with cp_col1:
            sp = st.number_input("季節周期（月数）", min_value=3, max_value=24, value=12, step=1, key="pred_custom_sp_dept")
            tr = st.selectbox("トレンド成分", ["add", "mul"], format_func=lambda x: "加法" if x == "add" else "乗法", key="pred_custom_trend_dept")
        with cp_col2:
            se = st.selectbox("季節成分", ["add", "mul"], format_func=lambda x: "加法" if x == "add" else "乗法", key="pred_custom_season_dept")
            ub = st.checkbox("Box-Cox変換を使用", value=True, key="pred_custom_boxcox_dept")
        custom_params = {"seasonal_periods": sp, "trend": tr, "seasonal": se, "use_boxcox": ub}

    # 複数モデルによる予測を同時に行うオプション
    run_all_models_dept = st.checkbox("すべてのモデルで比較する", value=False, key="run_all_models_dept")

    if st.button(f"{selected_department} の予測を実行", type="primary", key="pred_run_dept"):
        with st.spinner(f"{selected_department} の予測計算中..."):
            # 実行するモデルタイプを設定
            model_types_to_run = ['hwes', 'arima', 'moving_avg'] if run_all_models_dept else [selected_model]
            
            # 初期化
            result_df_dept = None
            fig_dept = None
            metrics_dept = {}
            all_model_metrics_dept = {}
            
            try:
                if run_all_models_dept:
                    # 並列処理で複数モデルを実行
                    all_model_metrics_dept = get_multi_model_forecast_parallel(
                        df_gas, 
                        prediction_period_type, 
                        model_types_to_run, 
                        custom_params,
                        department=selected_department
                    )
                    
                    # 選択したモデルだけフルに取得（グラフ用）
                    result_df_dept, fig_dept, metrics_dept = predict_department_future(
                        df_gas,
                        department=selected_department,
                        prediction_period=prediction_period_type,
                        model_type=selected_model,
                        custom_params=custom_params
                    )
                else:
                    # 単一モデルを実行
                    result_df_dept, fig_dept, metrics_dept = predict_department_future(
                        df_gas,
                        department=selected_department,
                        prediction_period=prediction_period_type,
                        model_type=selected_model,
                        custom_params=custom_params
                    )
                    all_model_metrics_dept = {selected_model: metrics_dept}
                    
            except Exception as pred_e:
                st.error(f"予測計算中にエラーが発生しました: {pred_e}")

            if fig_dept is None:
                st.warning(metrics_dept.get("message", "予測に必要なデータが不足しています。"))
            else:
                st.subheader(f"{selected_department} 予測グラフ")
                st.plotly_chart(fig_dept, use_container_width=True)
                st.subheader(f"{selected_department} 予測指標")
                metrics_list_dept = [
                    ("実績月平均", f"{metrics_dept.get('実績月平均', 0):.1f} 件/月"),
                    ("予測月平均", f"{metrics_dept.get('予測月平均', 0):.1f} 件/月"),
                    ("変化率(%)", f"{metrics_dept.get('変化率(%)', 0):.1f} %"),
                ]
                metrics_df_dept = pd.DataFrame(metrics_list_dept, columns=["指標", "値"])
                st.dataframe(metrics_df_dept.style.set_table_styles(sc.TABLE_STYLE_PROPS), hide_index=True)

                model_info_dept = f"予測モデル：{model_options.get(metrics_dept.get('使用モデル', selected_model), selected_model)}"
                if custom_params: model_info_dept += f"（カスタムパラメータ使用：季節周期={custom_params['seasonal_periods']}ヶ月）"
                st.info(model_info_dept)

                # すべてのモデルを実行した場合は比較表を表示
                if run_all_models_dept and len(all_model_metrics_dept) > 1:
                    st.subheader(f"{selected_department} モデル比較")
                    comparison_data_dept = []
                    for model_type, model_metrics in all_model_metrics_dept.items():
                        if "error" not in model_metrics:
                            model_name = model_options.get(model_type, model_type)
                            comparison_data_dept.append({
                                "モデル": model_name,
                                "予測月平均": f"{model_metrics.get('予測月平均', 0):.1f} 件/月",
                                "変化率(%)": f"{model_metrics.get('変化率(%)', 0):.1f} %"
                            })
                    
                    if comparison_data_dept:
                        comparison_df_dept = pd.DataFrame(comparison_data_dept)
                        st.dataframe(comparison_df_dept.style.set_table_styles(sc.TABLE_STYLE_PROPS), hide_index=True)

                st.subheader(f"{selected_department} 予測データテーブル")
                if not result_df_dept.empty and '月' in result_df_dept.columns:
                    actual_cutoff = latest_date.replace(day=1) + pd.DateOffset(months=1)
                    result_df_dept['データ種別'] = np.where(result_df_dept['月'] < actual_cutoff, '実績', '予測')
                    st.dataframe(
                        result_df_dept[['月', 'データ種別', '月合計件数']].style
                            .format(sc.TABLE_COMMON_FORMAT_DICT)
                            .set_table_styles(sc.TABLE_STYLE_PROPS)
                    )
                else:
                     st.warning("予測結果データフレームが空です。")


def create_future_prediction_tab(df_gas, target_dict, latest_date):
    """将来予測サブタブのUI"""
    st.subheader(f"将来予測（{latest_date.strftime('%Y年%m月%d日')}現在）")
    prediction_target = st.radio("分析対象", ["病院全体", "診療科別"], horizontal=True, key="pred_target_radio")
    if prediction_target == "病院全体":
        hospital_prediction_ui(df_gas, target_dict, latest_date)
    else:
        department_prediction_ui(df_gas, target_dict, latest_date)


def create_model_validation_tab(df_gas, target_dict, latest_date):
    """モデル検証サブタブのUI"""
    st.subheader(f"予測モデル検証（{latest_date.strftime('%Y年%m月%d日')}現在）")
    validation_target = st.radio("検証対象", ["病院全体", "診療科別"], horizontal=True, key="validation_target_radio")

    department = None
    if validation_target == "診療科別":
        departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
        if not departments: st.warning("データに診療科情報がないため、病院全体で検証します。")
        else: department = st.selectbox("診療科を選択", departments, key="validation_dept_select")

    col1, col2 = st.columns(2)
    with col1: validation_period_options = [3, 6, 9, 12]; validation_period = st.select_slider("検証期間（月数）", options=validation_period_options, value=6, key="validation_period_slider")
    with col2:
        model_options = {"hwes": "季節性Holt-Winters", "arima": "ARIMA", "moving_avg": "単純移動平均"}
        selected_models = st.multiselect("検証モデル", options=list(model_options.keys()), default=list(model_options.keys()), format_func=lambda x: model_options[x], key="validation_models_multi")

    if st.button("モデル検証を実行", type="primary", key="run_validation_button"):
        if not selected_models:
             st.warning("検証するモデルを1つ以上選択してください。")
        else:
            with st.spinner("モデル検証中..."):
                metrics_df, fig, recommendation = validate_prediction_model(
                    df_gas, department=department, model_types=selected_models, validation_period=validation_period
                )
                if fig is None: st.warning(recommendation)
                else:
                    st.success(recommendation)
                    st.subheader("モデル精度比較")
                    st.dataframe(metrics_df.style.format(sc.TABLE_COMMON_FORMAT_DICT).set_table_styles(sc.TABLE_STYLE_PROPS))
                    st.subheader("検証グラフ")
                    st.plotly_chart(fig, use_container_width=True)
                    with st.expander("精度指標の説明"):
                        st.markdown("""**MAE (平均絶対誤差)**: 誤差の絶対値の平均。小さいほど良い。\n
**RMSE (平方根平均二乗誤差)**: 誤差の二乗平均の平方根。MAEより外れ値の影響を受けやすい。小さいほど良い。\n
**MAPE (平均絶対パーセント誤差)**: 誤差の絶対値を実測値で割った割合の平均(%)。スケールの異なるデータ比較に有用。小さいほど良い。""")


def create_parameter_optimization_tab(df_gas, target_dict, latest_date):
    """パラメータ最適化サブタブのUI"""
    st.subheader(f"季節性モデルのパラメータ最適化（{latest_date.strftime('%Y年%m月%d日')}現在）")
    st.info("季節性Holt-Winters法のパラメータ（季節周期、トレンド、季節成分、Box-Cox変換）を最適化し、最も精度の高い組み合わせを見つけます。")

    optimization_target = st.radio("最適化対象", ["病院全体", "診療科別"], horizontal=True, key="optimization_target_radio")
    department = None
    if optimization_target == "診療科別":
        departments = sorted(df_gas["実施診療科"].dropna().unique().tolist())
        if not departments: st.warning("データに診療科情報がないため、病院全体で最適化します。")
        else: department = st.selectbox("診療科を選択", departments, key="optimization_dept_select")

    validation_period_options = [3, 6, 9, 12]; validation_period = st.select_slider("検証期間（月数）", options=validation_period_options, value=6, key="opt_validation_period_slider")

    if st.button("パラメータ最適化を実行", type="primary", key="run_optimization_button"):
        with st.spinner("パラメータ最適化中...（計算に時間がかかる場合があります）"):
            best_params, model_description = optimize_seasonal_model_params(
                df_gas, department=department, validation_period=validation_period
            )
            if not best_params: st.warning(model_description)
            else:
                st.subheader("最適パラメータ (Holt-Winters)")
                params_list = [
                    ('季節周期', f"{best_params.get('seasonal_periods','N/A')}ヶ月"),
                    ('トレンド成分', best_params.get('trend','N/A')),
                    ('季節成分', best_params.get('seasonal','N/A')),
                    ('Box-Cox変換', "あり" if best_params.get('use_boxcox',False) else "なし"),
                    ('検証RMSE', f"{best_params.get('rmse',0):.2f}")
                ]
                params_df = pd.DataFrame(params_list, columns=['パラメータ','値'])
                st.dataframe(params_df.style.set_table_styles(sc.TABLE_STYLE_PROPS), hide_index=True)
                st.success(f"最適モデル: {model_description}")
                with st.expander("パラメータの説明"):
                    st.markdown("""**季節周期**: データの周期性(月数)。12は年周期。\n
**トレンド成分**: `add`(加法) or `mul`(乗法)。データの傾向変化の仕方。\n
**季節成分**: `add`(加法) or `mul`(乗法)。季節変動の仕方。\n
**Box-Cox変換**: データ分散を安定させる変換の有無。\n
**検証RMSE**: このパラメータでの検証誤差。小さいほど精度が高い。""")
                st.info("これらの最適パラメータを「将来予測」タブのカスタムパラメータで使用できます。")


# --- Main Function ---

def create_prediction_tab(df_gas, target_dict, latest_date):
    """予測分析タブのUI部分を作成（拡張版）"""
    st.header("🔮 将来予測")

    if df_gas.empty:
        st.warning("データが見つかりません。データアップロードタブでデータをアップロードしてください。")
        return

    # Create subtabs
    tab1, tab2, tab3 = st.tabs(["将来予測", "モデル検証", "パラメータ最適化"])

    with tab1:
        # Call function to generate content for future prediction tab
        create_future_prediction_tab(df_gas, target_dict, latest_date)

    with tab2:
        # Call function to generate content for model validation tab
        create_model_validation_tab(df_gas, target_dict, latest_date)

    with tab3:
        # Call function to generate content for parameter optimization tab
        create_parameter_optimization_tab(df_gas, target_dict, latest_date)
        
def visualize_prediction_comparison(result_df, metrics, selected_model, model_options):
    """異なる予測モデルの結果を比較する可視化グラフを作成"""
    
    fig = go.Figure()
    
    # 実績データと予測データを分割
    cutoff_date = pd.to_datetime(metrics.get('予測開始日', result_df['月'].max()))
    actual_data = result_df[result_df['月'] <= cutoff_date]
    forecast_data = result_df[result_df['月'] >= cutoff_date]
    
    # 実績データプロット
    fig.add_trace(go.Scatter(
        x=actual_data['月'],
        y=actual_data['平日1日平均件数'],
        mode='lines+markers',
        name='実績',
        line=dict(color=sc.PREDICTION_ACTUAL_COLOR, width=2),
        marker=sc.PREDICTION_ACTUAL_MARKER
    ))
    
    # 予測データプロット
    fig.add_trace(go.Scatter(
        x=forecast_data['月'],
        y=forecast_data['平日1日平均件数'],
        mode='lines+markers',
        name=f'予測 ({model_options.get(selected_model, selected_model)})',
        line=dict(color=sc.PREDICTION_COLOR, width=2, dash='dash'),
        marker=sc.PREDICTION_MARKER
    ))
    
    # 予測の信頼区間を追加（オプション）
    if 'confidence_upper' in forecast_data.columns and 'confidence_lower' in forecast_data.columns:
        fig.add_trace(go.Scatter(
            x=forecast_data['月'],
            y=forecast_data['confidence_upper'],
            mode='lines',
            line=dict(width=0),
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=forecast_data['月'],
            y=forecast_data['confidence_lower'],
            mode='lines',
            line=dict(width=0),
            fill='tonexty',
            fillcolor='rgba(255, 165, 0, 0.2)',
            name='95% 信頼区間'
        ))
    
    # レイアウト設定
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title=f"全身麻酔手術件数予測と実績推移",
        xaxis_title="月",
        yaxis_title="平日1日平均件数",
        xaxis=dict(tickformat="%Y-%m"),
        legend=dict(y=1.1, orientation='h')
    )
    
    return fig