import pandas as pd
import streamlit as st
import base64
from io import StringIO
import datetime

def convert_df_to_csv_download_link(df, filename="data.csv"):
    """
    データフレームをCSVファイルとしてダウンロードするためのリンクを生成
    
    Parameters:
    -----------
    df : pandas.DataFrame
        ダウンロード対象のデータフレーム
    filename : str
        ダウンロードされるCSVファイルの名前
    
    Returns:
    --------
    str
        ダウンロードリンクHTML
    """
    # データフレームをCSV形式に変換
    csv = df.to_csv(index=False).encode('utf-8-sig')
    
    # Base64エンコード
    b64 = base64.b64encode(csv).decode()
    
    # リンク生成
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 {filename}をダウンロード</a>'
    
    return href

def get_default_filename(data_type, period_type, department=None):
    """
    データタイプと期間タイプに基づいてデフォルトのファイル名を生成
    
    Parameters:
    -----------
    data_type : str
        データタイプ ('hospital', 'department', 'ranking', 'surgeon')
    period_type : str
        期間タイプ ('weekly', 'monthly', 'quarterly', 'performance_table')
    department : str, optional
        診療科名（診療科別データの場合）
    
    Returns:
    --------
    str
        デフォルトのファイル名
    """
    now = datetime.datetime.now().strftime("%Y%m%d")
    
    # 診療科別目標達成状況テーブルの場合の特別処理
    if period_type == "performance_table":
        return f"{now}_診療科別目標達成状況.csv"
    
    if data_type == 'hospital':
        data_label = "病院全体"
    elif data_type == 'department':
        # departmentがNoneの場合は「全診療科」とする
        dept_name = department if department else "全診療科"
        data_label = f"診療科_{dept_name}"
    elif data_type == 'ranking':
        data_label = "診療科ランキング"
    elif data_type == 'cumulative_cases':
        # 累積ケースの場合
        dept_name = department if department else "全診療科"
        data_label = f"累積件数_{dept_name}"
    elif data_type == 'surgeon':
        # 術者分析の場合
        if period_type == 'by_department':
            dept_name = department if department else "全診療科"
            data_label = f"術者分析_{dept_name}"
        else:
            data_label = "術者分析"
    else:
        data_label = "データ"
    
    if period_type == 'weekly':
        period_label = "週次"
    elif period_type == 'monthly':
        period_label = "月次"
    elif period_type == 'quarterly':
        period_label = "四半期"
    elif period_type == 'fiscal_year':
        period_label = "年度"
    elif period_type == 'by_department':
        period_label = "診療科別"
    else:
        period_label = ""
    
    filename = f"{now}_{data_label}_{period_label}.csv"
    return filename

def render_download_button(df, data_type, period_type, department=None):
    """
    StreamlitでCSVダウンロードボタンを表示
    
    Parameters:
    -----------
    df : pandas.DataFrame
        ダウンロード対象のデータフレーム
    data_type : str
        データタイプ ('hospital', 'department', 'ranking', 'surgeon')
    period_type : str
        期間タイプ ('weekly', 'monthly', 'quarterly')
    department : str, optional
        診療科名（診療科別データの場合）
    """
    if df.empty:
        st.warning("ダウンロード可能なデータがありません")
        return
    
    # データフレームをコピーして、インデックスがある場合は列に変換
    # 特に performance_table など、診療科名がインデックスになっている場合
    df_to_export = df.copy()
    if period_type == "performance_table" and not df_to_export.index.name:
        # インデックス名が未設定の場合は診療科と仮定
        df_to_export = df_to_export.reset_index().rename(columns={'index': '診療科'})
    elif df_to_export.index.name:
        # インデックス名が設定されている場合はその名前でリセット
        df_to_export = df_to_export.reset_index()
    
    filename = get_default_filename(data_type, period_type, department)
    
    # ユニークなキーを生成
    button_key = f"download_{data_type}_{period_type}_{department if department else 'all'}_{datetime.datetime.now().strftime('%H%M%S%f')}"
    
    # ダウンロードボタン - ここではリセット済みのデータフレームを使用
    csv = df_to_export.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label=f"📥 CSVダウンロード",
        data=csv,
        file_name=filename,
        mime='text/csv',
        key=button_key
    )