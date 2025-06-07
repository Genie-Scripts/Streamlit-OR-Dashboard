"""
🏥 手術分析ダッシュボード - メインアプリケーション

修正版: インポートエラーと設定エラーを解決
"""

# ⚠️ 重要: st.set_page_config() は必ず最初に実行
import streamlit as st

# 最初にページ設定（他のstreamlitコマンドより前に実行）
st.set_page_config(
    page_title="🏥 手術分析ダッシュボード",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# その他のインポート
import pandas as pd
import numpy as np
import traceback
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

# カスタムモジュールのインポート（段階的に）
CONFIG_LOADED = False
SESSION_LOADED = False
KPI_LOADED = False

# 設定モジュール
try:
    from config.app_config import config, CUSTOM_CSS, COLORS, ERROR_MESSAGES, SUCCESS_MESSAGES
    CONFIG_LOADED = True
except ImportError as e:
    st.error(f"⚠️ 設定モジュール読み込みエラー: {e}")
    # フォールバック設定
    config = {
        "app_title": "🏥 手術分析ダッシュボード",
        "max_upload_size": 200,
        "supported_formats": [".csv", ".xlsx", ".xls"]
    }
    CUSTOM_CSS = ""
    COLORS = {"primary": "#1f77b4"}
    ERROR_MESSAGES = {"file_not_found": "ファイルが見つかりません"}
    SUCCESS_MESSAGES = {"file_uploaded": "ファイルが正常にアップロードされました"}

# セッション管理モジュール
try:
    from utils.session_manager import session_manager, init_session, save_preference, get_preference
    session_manager.update_activity()
    SESSION_LOADED = True
except ImportError as e:
    st.error(f"⚠️ セッション管理モジュール読み込みエラー: {e}")

# KPIカードモジュール
try:
    from components.kpi_cards import (
        KPICard, 
        create_kpi_card, 
        render_kpi_dashboard, 
        render_basic_kpis, 
        render_summary_kpis,
        render_medical_kpis
    )
    KPI_LOADED = True
except ImportError as e:
    st.error(f"⚠️ KPIカードモジュール読み込みエラー: {e}")

# CSSスタイルの適用
if CONFIG_LOADED and CUSTOM_CSS:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def show_module_status():
    """モジュール読み込み状況を表示"""
    st.sidebar.markdown("### 🔧 システム状況")
    status_data = [
        {"モジュール": "設定", "状況": "✅ OK" if CONFIG_LOADED else "❌ エラー"},
        {"モジュール": "セッション", "状況": "✅ OK" if SESSION_LOADED else "❌ エラー"},
        {"モジュール": "KPI", "状況": "✅ OK" if KPI_LOADED else "❌ エラー"}
    ]
    st.sidebar.table(pd.DataFrame(status_data))

def load_sample_data():
    """サンプルデータを生成"""
    np.random.seed(42)
    
    # 手術データのサンプル
    n_records = 1000
    
    data = {
        'Patient_ID': [f'P{i:04d}' for i in range(1, n_records + 1)],
        'Age': np.random.normal(55, 15, n_records).astype(int).clip(18, 90),
        'Gender': np.random.choice(['M', 'F'], n_records),
        'Surgery_Type': np.random.choice([
            '心臓外科', '整形外科', '脳外科', '消化器外科', '呼吸器外科'
        ], n_records),
        'Length_of_Stay': np.random.exponential(5, n_records).astype(int).clip(1, 30),
        'Surgery_Cost': np.random.normal(500000, 200000, n_records).clip(100000, 2000000),
        'Surgery_Date': pd.date_range('2023-01-01', periods=n_records, freq='D')[:n_records],
        'Outcome': np.random.choice(['Success', 'Complications', 'Readmission'], 
                                   n_records, p=[0.8, 0.15, 0.05]),
        'Department': np.random.choice([
            '循環器内科', '整形外科', '脳神経外科', '消化器内科', '呼吸器内科'
        ], n_records)
    }
    
    df = pd.DataFrame(data)
    return df

def upload_file():
    """ファイルアップロード機能"""
    st.sidebar.markdown("### 📁 データアップロード")
    
    uploaded_file = st.sidebar.file_uploader(
        "CSVまたはExcelファイルを選択",
        type=['csv', 'xlsx', 'xls'],
        help="手術データファイルをアップロードしてください"
    )
    
    if uploaded_file is not None:
        try:
            # ファイル読み込み
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            if SESSION_LOADED:
                session_manager.set_current_dataset(df, uploaded_file.name)
                session_manager.add_notification(SUCCESS_MESSAGES["file_uploaded"], "success")
            
            st.sidebar.success(f"✅ {uploaded_file.name} を読み込みました")
            st.sidebar.write(f"データ形状: {df.shape}")
            
            return df
            
        except Exception as e:
            error_msg = f"ファイル読み込みエラー: {str(e)}"
            st.sidebar.error(error_msg)
            if SESSION_LOADED:
                session_manager.log_error(error_msg)
            return None
    
    return None

def show_data_overview(data):
    """データ概要を表示"""
    if data is None or data.empty:
        st.warning("表示するデータがありません")
        return
    
    st.markdown("## 📊 データ概要")
    
    # 基本情報
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("総レコード数", f"{len(data):,}")
    
    with col2:
        st.metric("列数", len(data.columns))
    
    with col3:
        st.metric("欠損値", data.isnull().sum().sum())
    
    with col4:
        st.metric("重複行", data.duplicated().sum())
    
    # データ型情報
    st.markdown("### データ型")
    dtype_info = pd.DataFrame({
        '列名': data.columns,
        'データ型': data.dtypes.astype(str),
        '非null値数': data.count(),
        '欠損値数': data.isnull().sum(),
        '欠損率(%)': (data.isnull().sum() / len(data) * 100).round(2)
    })
    st.dataframe(dtype_info, use_container_width=True)
    
    # データプレビュー
    st.markdown("### データプレビュー")
    st.dataframe(data.head(10), use_container_width=True)

def show_kpi_analysis(data):
    """KPI分析を表示"""
    if data is None or data.empty:
        st.warning("分析するデータがありません")
        return
    
    st.markdown("## 📈 KPI分析")
    
    if KPI_LOADED:
        # 医療データ専用KPI
        render_medical_kpis(data)
        
        st.markdown("---")
        
        # 一般的なKPIダッシュボード
        render_kpi_dashboard(data)
        
    else:
        # フォールバック: 基本的な統計表示
        st.markdown("### 基本統計")
        numeric_data = data.select_dtypes(include=[np.number])
        if not numeric_data.empty:
            st.dataframe(numeric_data.describe(), use_container_width=True)

def show_visualizations(data):
    """可視化を表示"""
    if data is None or data.empty:
        st.warning("可視化するデータがありません")
        return
    
    st.markdown("## 📊 データ可視化")
    
    numeric_columns = data.select_dtypes(include=[np.number]).columns.tolist()
    categorical_columns = data.select_dtypes(include=['object']).columns.tolist()
    
    # 可視化タイプ選択
    viz_type = st.selectbox(
        "可視化タイプを選択",
        ["分布", "散布図", "時系列", "カテゴリ別分析"]
    )
    
    if viz_type == "分布" and numeric_columns:
        selected_column = st.selectbox("分析する列を選択", numeric_columns)
        fig = px.histogram(data, x=selected_column, title=f"{selected_column} の分布")
        st.plotly_chart(fig, use_container_width=True)
        
    elif viz_type == "散布図" and len(numeric_columns) >= 2:
        col1, col2 = st.columns(2)
        with col1:
            x_column = st.selectbox("X軸", numeric_columns)
        with col2:
            y_column = st.selectbox("Y軸", [col for col in numeric_columns if col != x_column])
        
        color_column = st.selectbox("色分け（オプション）", ["なし"] + categorical_columns)
        
        fig = px.scatter(
            data, 
            x=x_column, 
            y=y_column,
            color=color_column if color_column != "なし" else None,
            title=f"{x_column} vs {y_column}"
        )
        st.plotly_chart(fig, use_container_width=True)
        
    elif viz_type == "時系列":
        date_columns = [col for col in data.columns if 'date' in col.lower() or 'time' in col.lower()]
        if date_columns and numeric_columns:
            date_col = st.selectbox("日付列", date_columns)
            value_col = st.selectbox("値列", numeric_columns)
            
            # 日付型に変換
            data_copy = data.copy()
            data_copy[date_col] = pd.to_datetime(data_copy[date_col])
            
            # 日別集計
            daily_data = data_copy.groupby(data_copy[date_col].dt.date)[value_col].sum().reset_index()
            
            fig = px.line(daily_data, x=date_col, y=value_col, title=f"{value_col} の時系列推移")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("時系列分析には日付列と数値列が必要です")
            
    elif viz_type == "カテゴリ別分析" and categorical_columns and numeric_columns:
        cat_col = st.selectbox("カテゴリ列", categorical_columns)
        val_col = st.selectbox("値列", numeric_columns)
        
        category_summary = data.groupby(cat_col)[val_col].agg(['sum', 'mean', 'count']).reset_index()
        
        # 棒グラフ
        fig = px.bar(category_summary, x=cat_col, y='sum', title=f"{cat_col}別 {val_col} 合計")
        st.plotly_chart(fig, use_container_width=True)

def export_data(data):
    """データエクスポート機能"""
    if data is None or data.empty:
        return
    
    st.sidebar.markdown("### 💾 データエクスポート")
    
    export_format = st.sidebar.selectbox(
        "エクスポート形式",
        ["CSV", "Excel"]
    )
    
    if st.sidebar.button("エクスポート"):
        try:
            if export_format == "CSV":
                csv = data.to_csv(index=False)
                st.sidebar.download_button(
                    label="CSVダウンロード",
                    data=csv,
                    file_name=f"surgery_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                buffer = io.BytesIO()
                data.to_excel(buffer, index=False)
                buffer.seek(0)
                
                st.sidebar.download_button(
                    label="Excelダウンロード",
                    data=buffer.getvalue(),
                    file_name=f"surgery_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            st.sidebar.success("エクスポート準備完了!")
            
        except Exception as e:
            st.sidebar.error(f"エクスポートエラー: {str(e)}")

def main():
    """メイン関数"""
    
    # ヘッダー
    st.markdown("""
    <div class="header">
        <h1>🏥 手術分析ダッシュボード</h1>
        <p>入院患者データの包括的分析システム</p>
    </div>
    """, unsafe_allow_html=True)
    
    # モジュール状況表示
    show_module_status()
    
    # データ読み込み
    uploaded_data = upload_file()
    
    # サンプルデータ使用オプション
    if uploaded_data is None:
        if st.sidebar.button("📊 サンプルデータを使用"):
            uploaded_data = load_sample_data()
            st.sidebar.success("サンプルデータを読み込みました")
    
    # メイン分析
    if uploaded_data is not None:
        # タブ作成
        tab1, tab2, tab3 = st.tabs(["📊 データ概要", "📈 KPI分析", "📉 可視化"])
        
        with tab1:
            show_data_overview(uploaded_data)
        
        with tab2:
            show_kpi_analysis(uploaded_data)
        
        with tab3:
            show_visualizations(uploaded_data)
        
        # エクスポート機能
        export_data(uploaded_data)
        
    else:
        # 初期画面
        st.markdown("""
        ### 🚀 使用方法
        
        1. **サイドバーからファイルをアップロード** または **サンプルデータを使用**
        2. **データ概要タブ** でデータの基本情報を確認
        3. **KPI分析タブ** で重要指標を分析
        4. **可視化タブ** でグラフやチャートを作成
        5. **結果をエクスポート** して保存
        
        ### 📋 対応データ形式
        - CSV (.csv)
        - Excel (.xlsx, .xls)
        
        ### 🏥 医療データの例
        - 患者ID, 年齢, 性別
        - 手術タイプ, 入院日数
        - 費用, 手術日, 診療科
        - 結果, 合併症データ
        """)
    
    # フッター
    st.markdown("---")
    st.markdown("""
    <div class="footer">
        <p>🏥 手術分析ダッシュボード v2.0 | Healthcare Analytics Team</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("アプリケーションエラーが発生しました")
        st.exception(e)
        
        if SESSION_LOADED:
            session_manager.log_error(str(e), {"traceback": traceback.format_exc()})