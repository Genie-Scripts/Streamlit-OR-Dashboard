import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Optional

# 既存モジュールのインポート
from analysis import forecasting
from plotting import generic_plots
from ..components import chart_container
from ..error_handler import with_error_handling, ErrorHandler

@with_error_handling("将来予測ページ描画")
def render(df: pd.DataFrame, target_dict: Dict, latest_date: Optional[datetime]) -> None:
    """将来予測ページを描画"""
    
    st.title("🔮 将来予測")
    
    # データ検証
    if not _validate_prediction_data(df, latest_date):
        return
    
    # 予測データの説明
    _render_prediction_explanation()
    
    # タブ構成
    tab1, tab2, tab3 = st.tabs([
        "将来予測", 
        "モデル検証", 
        "パラメータ最適化"
    ])
    
    with tab1:
        _render_prediction_tab(df, target_dict, latest_date)
    
    with tab2:
        _render_validation_tab(df)
    
    with tab3:
        _render_optimization_tab(df)

def _validate_prediction_data(df: pd.DataFrame, latest_date: Optional[datetime]) -> bool:
    """予測データの検証"""
    if df.empty:
        ErrorHandler.display_warning("表示するデータがありません", "将来予測")
        return False
    
    if latest_date is None:
        ErrorHandler.display_warning("日付データが見つかりません", "将来予測")
        return False
    
    required_columns = ['手術実施日_dt', 'is_gas_20min']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        ErrorHandler.display_error(
            ValueError(f"予測に必要な列が不足しています: {missing_columns}"),
            "将来予測"
        )
        return False
    
    return True

def _render_prediction_explanation() -> None:
    """予測データの説明を表示"""
    with st.expander("📊 予測データの詳細説明", expanded=False):
        st.markdown("""
        **予測対象データ**: 全身麻酔手術（20分以上）
        
        **重要**: 休日データの扱いについては実装により異なります
        - 平日のみ対象の場合: 土日祝日、年末年始は除外
        - 全日対象の場合: 休日の緊急手術も含む
        
        **フィルタ条件**:
        - `is_gas_20min = True` （全身麻酔20分以上）
        - `is_weekday` の使用有無は実装依存
        """)

def _render_prediction_tab(df: pd.DataFrame, target_dict: Dict, latest_date: datetime) -> None:
    """将来予測タブを描画"""
    st.header("🔮 将来予測")
    
    # 予測設定
    pred_target, department = _render_prediction_settings(df)
    model_type, pred_period = _render_model_settings()
    
    # 予測実行ボタン
    if st.button("🚀 予測を実行", type="primary", key="run_prediction"):
        _execute_prediction(df, target_dict, latest_date, department, model_type, pred_period)

def _render_prediction_settings(df: pd.DataFrame) -> tuple:
    """予測設定セクションを描画"""
    col1, col2 = st.columns(2)
    
    with col1:
        pred_target = st.radio(
            "🎯 予測対象",
            ["病院全体", "診療科別"],
            horizontal=True,
            key="pred_target",
            help="予測する対象を選択してください"
        )
    
    with col2:
        department = None
        if pred_target == "診療科別":
            departments = sorted(df["実施診療科"].dropna().unique())
            if departments:
                department = st.selectbox(
                    "🏥 診療科を選択",
                    departments,
                    key="pred_dept_select",
                    help="予測を行う診療科を選択してください"
                )
            else:
                st.warning("利用可能な診療科がありません")
    
    return pred_target, department

def _render_model_settings() -> tuple:
    """モデル設定セクションを描画"""
    col1, col2 = st.columns(2)
    
    with col1:
        model_type = st.selectbox(
            "🤖 予測モデル",
            ["hwes", "arima", "moving_avg"],
            format_func=lambda x: {
                "hwes": "Holt-Winters指数平滑法",
                "arima": "ARIMA モデル",
                "moving_avg": "移動平均法"
            }[x],
            help="使用する予測アルゴリズムを選択してください"
        )
    
    with col2:
        pred_period = st.selectbox(
            "📅 予測期間",
            ["fiscal_year", "calendar_year", "six_months"],
            format_func=lambda x: {
                "fiscal_year": "年度末まで",
                "calendar_year": "年末まで",
                "six_months": "6ヶ月先まで"
            }[x],
            help="予測する期間を選択してください"
        )
    
    return model_type, pred_period

@with_error_handling("予測実行", show_spinner=True, spinner_text="予測計算中...")
def _execute_prediction(
    df: pd.DataFrame,
    target_dict: Dict,
    latest_date: datetime,
    department: Optional[str],
    model_type: str,
    pred_period: str
) -> None:
    """予測を実行"""
    try:
        result_df, metrics = forecasting.predict_future(
            df, 
            latest_date, 
            department=department, 
            model_type=model_type, 
            prediction_period=pred_period
        )
        
        if metrics.get("message"):
            st.warning(metrics["message"])
            return
        
        # 予測結果の表示
        _display_prediction_results(result_df, metrics, target_dict, department, df)
        
    except Exception as e:
        ErrorHandler.display_error(e, "予測計算")

def _display_prediction_results(
    result_df: pd.DataFrame,
    metrics: Dict,
    target_dict: Dict,
    department: Optional[str],
    source_df: pd.DataFrame
) -> None:
    """予測結果を表示"""
    target_name = department or '病院全体'
    model_name = metrics.get('予測モデル', '')
    title = f"{target_name} {model_name}モデルによる予測"
    
    # 予測グラフ表示
    with chart_container.create_chart_container():
        fig = generic_plots.create_forecast_chart(result_df, title)
        st.plotly_chart(fig, use_container_width=True)
    
    # 詳細分析
    _render_prediction_analysis(result_df, source_df, department)
    
    # 予測サマリー
    _render_prediction_summary(result_df, target_dict, department, source_df)
    
    # モデル評価指標
    with st.expander("📊 モデル評価指標詳細"):
        st.write(metrics)

def _render_prediction_analysis(
    result_df: pd.DataFrame,
    source_df: pd.DataFrame,
    department: Optional[str]
) -> None:
    """予測入力データの詳細分析"""
    st.header("🔍 予測入力データの詳細分析")
    
    # データフィルタリング結果の分析
    if department:
        base_data = source_df[source_df['実施診療科'] == department]
    else:
        base_data = source_df
    
    # 各段階でのデータ件数
    total_data = len(base_data)
    gas_data = base_data[base_data['is_gas_20min']]
    gas_count = len(gas_data)
    
    # 平日・休日の内訳
    if 'is_weekday' in gas_data.columns:
        weekday_data = gas_data[gas_data['is_weekday']]
        weekend_data = gas_data[~gas_data['is_weekday']]
        weekday_count = len(weekday_data)
        weekend_count = len(weekend_data)
    else:
        weekday_count = gas_count
        weekend_count = 0
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        _display_filtering_summary(total_data, gas_count, weekday_count, weekend_count)
    
    with col2:
        _display_day_analysis(gas_data)
    
    # 重要な確認メッセージ
    _display_data_usage_warning(weekend_count, weekday_count, gas_count)

def _display_filtering_summary(
    total_data: int,
    gas_count: int,
    weekday_count: int,
    weekend_count: int
) -> None:
    """データフィルタリング結果サマリー"""
    st.subheader("📊 データフィルタリング結果")
    
    filter_summary = pd.DataFrame({
        'フィルタ段階': [
            '1. 全データ',
            '2. 全身麻酔(20分以上)',
            '3. うち平日のみ',
            '4. うち休日のみ'
        ],
        '件数': [
            f"{total_data:,}件",
            f"{gas_count:,}件", 
            f"{weekday_count:,}件",
            f"{weekend_count:,}件"
        ],
        '割合': [
            "100%",
            f"{gas_count/total_data*100:.1f}%" if total_data > 0 else "0%",
            f"{weekday_count/gas_count*100:.1f}%" if gas_count > 0 else "0%",
            f"{weekend_count/gas_count*100:.1f}%" if gas_count > 0 else "0%"
        ]
    })
    
    st.dataframe(filter_summary, hide_index=True, use_container_width=True)

def _display_day_analysis(gas_data: pd.DataFrame) -> None:
    """曜日別分析"""
    st.subheader("📅 曜日別内訳")
    
    if gas_data.empty or '手術実施日_dt' not in gas_data.columns:
        st.info("曜日別データがありません")
        return
    
    try:
        day_analysis = gas_data.groupby(gas_data['手術実施日_dt'].dt.day_name()).size()
        
        if not day_analysis.empty:
            day_df = pd.DataFrame({
                '曜日': day_analysis.index,
                '件数': day_analysis.values
            })
            
            # 曜日順にソート
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_df['曜日順'] = day_df['曜日'].map({day: i for i, day in enumerate(day_order)})
            day_df = day_df.sort_values('曜日順').drop('曜日順', axis=1)
            
            st.dataframe(day_df, hide_index=True, use_container_width=True)
        else:
            st.info("曜日別データがありません")
            
    except Exception as e:
        st.warning(f"曜日別分析でエラーが発生しました: {str(e)}")

def _display_data_usage_warning(weekend_count: int, weekday_count: int, gas_count: int) -> None:
    """データ使用に関する警告表示"""
    if weekend_count > 0:
        st.warning(f"""
        ⚠️ **重要確認**: 休日にも{weekend_count}件の全身麻酔手術があります。
        
        **予測モデルがどちらを使用しているかは `forecasting.py` の実装によります：**
        - 平日のみ使用: {weekday_count}件のデータで予測
        - 全日使用: {gas_count}件のデータで予測
        
        実際に使用されているデータは、予測結果の実績部分の件数と比較して確認できます。
        """)
    else:
        st.info(f"✅ 対象期間中の休日手術は0件のため、平日・全日どちらでも同じ結果になります。")

@with_error_handling("予測サマリー表示")
def _render_prediction_summary(
    result_df: pd.DataFrame,
    target_dict: Dict,
    department: Optional[str],
    source_df: pd.DataFrame
) -> None:
    """予測サマリーを表示"""
    st.header("📋 予測サマリー")
    
    try:
        summary_df, monthly_df = generic_plots.create_forecast_summary_table(
            result_df, target_dict, department, source_df=source_df
        )
        
        if not summary_df.empty:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("年度予測サマリー")
                st.dataframe(summary_df, hide_index=True, use_container_width=True)
                
                # 実績値との整合性チェック
                _display_consistency_check(result_df, source_df, department)
            
            with col2:
                st.subheader("月別予測詳細")
                if not monthly_df.empty:
                    st.dataframe(monthly_df, hide_index=True, use_container_width=True)
                else:
                    st.info("月別予測データがありません")
        else:
            st.info("予測サマリーを生成できませんでした")
            
    except Exception as e:
        ErrorHandler.display_error(e, "予測サマリー生成")

def _display_consistency_check(
    result_df: pd.DataFrame,
    source_df: pd.DataFrame,
    department: Optional[str]
) -> None:
    """整合性チェック表示"""
    if '種別' not in result_df.columns:
        return
    
    actual_from_forecast = result_df[result_df['種別'] == '実績']['値'].sum()
    
    # 生データからの件数計算
    if department:
        base_data = source_df[source_df['実施診療科'] == department]
    else:
        base_data = source_df
    
    gas_data = base_data[base_data['is_gas_20min']]
    weekday_count = len(gas_data[gas_data.get('is_weekday', True)]) if 'is_weekday' in gas_data.columns else len(gas_data)
    gas_count = len(gas_data)
    
    st.caption(f"""
    **整合性チェック**: 
    - 予測結果の実績部分: {actual_from_forecast:.0f}件
    - 平日全身麻酔データ: {weekday_count}件
    - 全日全身麻酔データ: {gas_count}件
    """)

def _render_validation_tab(df: pd.DataFrame) -> None:
    """モデル検証タブを描画"""
    st.header("🔍 予測モデルの精度検証")
    
    # 検証設定
    val_target = st.radio(
        "🎯 検証対象",
        ["病院全体", "診療科別"],
        horizontal=True,
        key="val_target"
    )
    
    val_dept = None
    if val_target == "診療科別":
        departments = sorted(df["実施診療科"].dropna().unique())
        if departments:
            val_dept = st.selectbox(
                "🏥 診療科を選択",
                departments,
                key="val_dept"
            )
    
    val_period = st.slider(
        "📅 検証期間（月数）",
        min_value=3,
        max_value=12,
        value=6,
        help="過去何ヶ月分のデータを検証用に使用するか設定してください"
    )
    
    if st.button("🧪 検証実行", key="run_validation"):
        _execute_validation(df, val_dept, val_period)

@with_error_handling("モデル検証実行", show_spinner=True, spinner_text="モデル検証中...")
def _execute_validation(df: pd.DataFrame, department: Optional[str], validation_period: int) -> None:
    """モデル検証を実行"""
    try:
        metrics_df, train, test, preds, rec = forecasting.validate_model(
            df, 
            department=department, 
            validation_period=validation_period
        )
        
        if not metrics_df.empty:
            st.success(rec)
            
            # メトリクス表示
            st.subheader("📊 検証結果")
            st.dataframe(metrics_df, use_container_width=True)
            
            # 検証グラフ表示
            with chart_container.create_chart_container():
                fig = generic_plots.create_validation_chart(train, test, preds)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("❌ モデル検証に失敗しました。")
            
    except Exception as e:
        ErrorHandler.display_error(e, "モデル検証")

def _render_optimization_tab(df: pd.DataFrame) -> None:
    """パラメータ最適化タブを描画"""
    st.header("⚙️ パラメータ最適化 (Holt-Winters)")
    
    # 最適化設定
    opt_target = st.radio(
        "🎯 最適化対象",
        ["病院全体", "診療科別"],
        horizontal=True,
        key="opt_target"
    )
    
    opt_dept = None
    if opt_target == "診療科別":
        departments = sorted(df["実施診療科"].dropna().unique())
        if departments:
            opt_dept = st.selectbox(
                "🏥 診療科を選択",
                departments,
                key="opt_dept"
            )
    
    if st.button("🚀 最適化実行", key="run_opt"):
        _execute_optimization(df, opt_dept)

@with_error_handling("パラメータ最適化実行", show_spinner=True, spinner_text="最適化計算中...")
def _execute_optimization(df: pd.DataFrame, department: Optional[str]) -> None:
    """パラメータ最適化を実行"""
    try:
        params, desc = forecasting.optimize_hwes_params(df, department=department)
        
        if params:
            st.success(f"✅ 最適モデル: {desc}")
            
            # パラメータ詳細表示
            st.subheader("🔧 最適パラメータ")
            st.json(params)
            
            # 推奨事項
            st.info("""
            💡 **推奨事項**:
            - 最適化されたパラメータを使用することで予測精度が向上します
            - 定期的にパラメータを再最適化することをお勧めします
            - データ量が増えた場合は再度最適化を実行してください
            """)
        else:
            st.error(f"❌ 最適化失敗: {desc}")
            
    except Exception as e:
        ErrorHandler.display_error(e, "パラメータ最適化")