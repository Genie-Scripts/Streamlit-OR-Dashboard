# surgeon_analyzer.py
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from holiday_handler import is_weekday
import style_config as sc  # スタイル定義をインポート
from export_handler import render_download_button
import concurrent.futures
from functools import partial

# キャッシュつきの手術時間計算関数（高速化）
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def calculate_surgery_duration_optimized(df):
    """
    入室時刻と退室時刻から手術時間（時間単位）を計算する関数（最適化版）
    
    Parameters:
    -----------
    df : pandas.DataFrame
        分析対象の手術データフレーム。必須列: ['入室時刻', '退室時刻']
        
    Returns:
    --------
    pandas.DataFrame
        手術時間列が追加されたデータフレーム
    """
    df_copy = df.copy()
    
    # 必要な列の特定（高速化）
    entry_col = None
    exit_col = None
    
    # 標準列名をチェック
    if '入室時刻' in df_copy.columns and '退室時刻' in df_copy.columns:
        entry_col = '入室時刻'
        exit_col = '退室時刻'
    else:
        # 文字化けした列名を探す
        for col in df_copy.columns:
            if 'üº' in col:  # 入室に相当する可能性
                entry_col = col
            elif 'Þº' in col:  # 退室に相当する可能性
                exit_col = col
    
    if not entry_col or not exit_col:
        print("入室時刻または退室時刻の列が見つかりません")
        return df_copy
    
    # 列名を正規化
    if entry_col != '入室時刻':
        df_copy['入室時刻'] = df_copy[entry_col]
    if exit_col != '退室時刻':
        df_copy['退室時刻'] = df_copy[exit_col]
    
    # 手術時間列を初期化
    df_copy['手術時間(時間)'] = pd.NA
    
    # データが空でないか確認
    if df_copy.empty:
        return df_copy
    
    # 数値型変換を試みる（Excel時間形式の場合）
    try:
        # 数値型変換を一括処理
        df_copy['入室時刻_num'] = pd.to_numeric(df_copy['入室時刻'], errors='coerce')
        df_copy['退室時刻_num'] = pd.to_numeric(df_copy['退室時刻'], errors='coerce')
        
        # Excel時間形式の判定
        if not df_copy['入室時刻_num'].isna().all() and not df_copy['退室時刻_num'].isna().all():
            # ベクトル化計算
            df_copy['手術時間(時間)'] = np.where(
                df_copy['退室時刻_num'] < df_copy['入室時刻_num'],
                (df_copy['退室時刻_num'] + 1 - df_copy['入室時刻_num']) * 24,  # 翌日の場合
                (df_copy['退室時刻_num'] - df_copy['入室時刻_num']) * 24  # 同日の場合
            )
            
            # 不正な値を除外
            mask = (df_copy['手術時間(時間)'] < 0) | (df_copy['手術時間(時間)'] > 24)
            df_copy.loc[mask, '手術時間(時間)'] = pd.NA
            
            # 一時列の削除
            df_copy.drop(columns=['入室時刻_num', '退室時刻_num'], inplace=True)
            
            # 有効なデータがあれば返す
            if not df_copy['手術時間(時間)'].isna().all():
                return df_copy
    except Exception as e:
        print(f"数値変換でエラー: {e}")
    
    # 時刻文字列の処理（様々な形式に対応）
    try:
        # 時刻文字列のパターン検出（最適化）
        sample_entry = str(df_copy['入室時刻'].iloc[0]) if not df_copy.empty else ""
        sample_exit = str(df_copy['退室時刻'].iloc[0]) if not df_copy.empty else ""
        
        if not sample_entry or not sample_exit:
            return df_copy
        
        # 時刻形式を推測
        time_format = '%H:%M'  # デフォルト
        
        if ':' in sample_entry:
            if 'AM' in sample_entry.upper() or 'PM' in sample_entry.upper():
                time_format = '%I:%M %p'
            elif sample_entry.count(':') == 2:
                time_format = '%H:%M:%S'
        
        # 基準日を設定
        base_date = pd.Timestamp('2000-01-01')
        
        # ベクトル化処理で時刻変換（高速化）
        try:
            # 文字列に変換してから日時に変換
            str_entry = df_copy['入室時刻'].astype(str)
            str_exit = df_copy['退室時刻'].astype(str)
            
            # 日時変換
            df_copy['入室日時'] = pd.to_datetime(
                base_date.strftime('%Y-%m-%d') + ' ' + str_entry,
                format='%Y-%m-%d ' + time_format,
                errors='coerce'
            )
            
            df_copy['退室日時'] = pd.to_datetime(
                base_date.strftime('%Y-%m-%d') + ' ' + str_exit,
                format='%Y-%m-%d ' + time_format,
                errors='coerce'
            )
            
            # 翌日判定（ベクトル化）
            mask = df_copy['退室日時'] < df_copy['入室日時']
            df_copy.loc[mask, '退室日時'] = df_copy.loc[mask, '退室日時'] + pd.Timedelta(days=1)
            
            # 時間差を計算（時間単位）
            df_copy['手術時間(時間)'] = (df_copy['退室日時'] - df_copy['入室日時']).dt.total_seconds() / 3600
            
            # 不正な値を除外
            mask = (df_copy['手術時間(時間)'] < 0) | (df_copy['手術時間(時間)'] > 24)
            df_copy.loc[mask, '手術時間(時間)'] = pd.NA
            
            # 一時列の削除
            df_copy.drop(columns=['入室日時', '退室日時'], errors='ignore', inplace=True)
            
            # 有効なデータがあれば返す
            if not df_copy['手術時間(時間)'].isna().all():
                return df_copy
                
        except Exception as e:
            print(f"時刻変換エラー ({time_format}): {e}")
    
    except Exception as e:
        print(f"時刻形式の変換でエラーが発生しました: {e}")
    
    return df_copy

# 最適化された術者データ前処理関数
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def preprocess_surgeon_data_optimized(df):
    """
    術者データを前処理し、複数術者の場合は行を展開する関数（最適化版）
    
    Parameters:
    -----------
    df : pandas.DataFrame
        分析対象の手術データフレーム。必須列: ['実施術者']
        
    Returns:
    --------
    pandas.DataFrame
        前処理済みのデータフレーム（複数術者の場合は行が増える）
    """
    # データのコピー
    df_copy = df.copy()
    
    # 術者列がない場合はそのまま返す
    if '実施術者' not in df_copy.columns:
        return df_copy
    
    # 入室時刻と退室時刻から手術時間を計算
    df_copy = calculate_surgery_duration_optimized(df_copy)
    
    # 術者列のデータ型をチェック（文字列に変換）
    df_copy['実施術者'] = df_copy['実施術者'].astype(str)
    
    # 複数術者を含む行があるか確認
    has_multiple_surgeons = df_copy['実施術者'].str.contains('\n|\r').any()
    
    if not has_multiple_surgeons:
        # 複数術者がなければそのまま返す
        return df_copy
        
    # 最適化: pandasのexplode機能を使用
    # 術者列を分割（改行文字の統一と分割）
    df_copy['術者リスト'] = df_copy['実施術者'].str.replace('\r', '\n').str.split('\n')
    
    # 分割後のリストから空白要素を削除
    df_copy['術者リスト'] = df_copy['術者リスト'].apply(
        lambda x: [s.strip() for s in x if s.strip()] if isinstance(x, list) else ['不明']
    )
    
    # 空のリストを「不明」で置き換え
    mask = df_copy['術者リスト'].apply(lambda x: len(x) == 0)
    df_copy.loc[mask, '術者リスト'] = [['不明']]
    
    # explode関数で行を展開
    expanded_df = df_copy.explode('術者リスト')
    
    # 展開した列を実施術者列に戻す
    expanded_df['実施術者'] = expanded_df['術者リスト']
    expanded_df = expanded_df.drop(columns=['術者リスト'])
    
    # 統計情報をログ出力
    unique_surgeons_before = df_copy['実施術者'].nunique()
    unique_surgeons_after = expanded_df['実施術者'].nunique()
    rows_before = len(df_copy)
    rows_after = len(expanded_df)
    
    print(f"術者データ前処理: {rows_before}行→{rows_after}行 ({rows_after-rows_before}行増加)")
    print(f"ユニーク術者数: {unique_surgeons_before}→{unique_surgeons_after} ({unique_surgeons_after-unique_surgeons_before}増加)")
    
    return expanded_df

# 並列処理用の関数
def process_chunk(chunk_df):
    """各チャンクを処理する関数"""
    # チャンク単位の処理
    return preprocess_surgeon_data_optimized(chunk_df)

# 大きなデータセット用の並列処理関数
def preprocess_data_parallel(df, chunk_size=1000):
    """データを分割して並列処理する"""
    # データが小さい場合は直接処理
    if len(df) <= chunk_size:
        return preprocess_surgeon_data_optimized(df)
    
    # データを分割
    chunks = [df.iloc[i:i+chunk_size] for i in range(0, len(df), chunk_size)]
    
    # 並列処理
    with concurrent.futures.ThreadPoolExecutor() as executor:
        processed_chunks = list(executor.map(process_chunk, chunks))
    
    # 結果を結合
    return pd.concat(processed_chunks, ignore_index=True)

# 最適化された集計関数
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def analyze_surgeon_summary_optimized(df, period_type="weekly"):
    """
    術者別の全身麻酔手術件数と手術時間を集計する関数（最適化版）
    
    Parameters:
    -----------
    df : pandas.DataFrame
        前処理済みのデータフレーム
    period_type : str
        'weekly', 'monthly', 'quarterly'のいずれか
        
    Returns:
    --------
    tuple
        (件数集計結果, 時間集計結果)
    """
    # 既に前処理済みのデータを使用（前処理はこの関数の外で実行）
    df_gas = df.copy()
    
    # 全身麻酔(20分以上)フィルタ
    df_gas = df_gas[
        df_gas['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_gas['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    if df_gas.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 時間列を特定
    time_col = None
    
    # 計算した手術時間を優先
    if '手術時間(時間)' in df_gas.columns:
        time_col = '手術時間(時間)'
    # 他の時間列をチェック
    else:
        for col in ['予定所要時間', '予定所要時間(OR)', '予定使用時間', '実績時間']:
            if col in df_gas.columns:
                time_col = col
                break
        
        # 文字化けした列名もチェック
        if not time_col:
            for col in df_gas.columns:
                if 'pÔ' in col:  # 「時間」を含む可能性がある列
                    time_col = col
                    break
    
    # 時間列がある場合は数値に変換
    if time_col and time_col != '手術時間(時間)':  # 手術時間(時間)は既に変換済み
        # 数値に変換（エラーはNaNに）
        df_gas[time_col] = pd.to_numeric(df_gas[time_col], errors='coerce')
        
        # 時間単位に変換（分単位の場合）
        # 値が300を超える場合は分単位と仮定
        if df_gas[time_col].max() > 300:
            df_gas[time_col] = df_gas[time_col] / 60
    
    # 期間タイプに応じた集計（高速化）
    if period_type == "weekly":
        # 週単位でまとめる (月曜始まり)
        df_gas['週'] = df_gas['手術実施日_dt'] - pd.to_timedelta(df_gas['手術実施日_dt'].dt.dayofweek, unit='d')
        df_gas['週'] = df_gas['週'].dt.normalize()  # 時間部分を削除
        
        # 件数集計
        count_result = df_gas.groupby(['週', '実施術者']).size().reset_index(name='件数')
        count_result = count_result.sort_values(['週', '件数'], ascending=[True, False])
        
        # 時間集計（時間列がある場合のみ）
        time_result = pd.DataFrame()
        if time_col:
            time_result = df_gas.groupby(['週', '実施術者'])[time_col].sum().reset_index(name='時間')
            time_result = time_result.sort_values(['週', '時間'], ascending=[True, False])
        
    elif period_type == "monthly":
        # 月単位でまとめる
        df_gas['月'] = df_gas['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
        
        # 件数集計
        count_result = df_gas.groupby(['月', '実施術者']).size().reset_index(name='件数')
        count_result = count_result.sort_values(['月', '件数'], ascending=[True, False])
        
        # 時間集計（時間列がある場合のみ）
        time_result = pd.DataFrame()
        if time_col:
            time_result = df_gas.groupby(['月', '実施術者'])[time_col].sum().reset_index(name='時間')
            time_result = time_result.sort_values(['月', '時間'], ascending=[True, False])
        
    elif period_type == "quarterly":
        # 四半期単位でまとめる
        df_gas['四半期'] = df_gas['手術実施日_dt'].dt.to_period('Q').apply(lambda r: r.start_time)
        df_gas['四半期ラベル'] = df_gas['四半期'].apply(lambda d: f"{d.year}年Q{(d.month-1)//3+1}")
        
        # 件数集計
        count_result = df_gas.groupby(['四半期', '四半期ラベル', '実施術者']).size().reset_index(name='件数')
        count_result = count_result.sort_values(['四半期', '件数'], ascending=[True, False])
        
        # 時間集計（時間列がある場合のみ）
        time_result = pd.DataFrame()
        if time_col:
            time_result = df_gas.groupby(['四半期', '四半期ラベル', '実施術者'])[time_col].sum().reset_index(name='時間')
            time_result = time_result.sort_values(['四半期', '時間'], ascending=[True, False])
    
    else:
        # デフォルトは週単位
        df_gas['週'] = df_gas['手術実施日_dt'] - pd.to_timedelta(df_gas['手術実施日_dt'].dt.dayofweek, unit='d')
        df_gas['週'] = df_gas['週'].dt.normalize()
        count_result = df_gas.groupby(['週', '実施術者']).size().reset_index(name='件数')
        count_result = count_result.sort_values(['週', '件数'], ascending=[True, False])
        
        # 時間集計（時間列がある場合のみ）
        time_result = pd.DataFrame()
        if time_col:
            time_result = df_gas.groupby(['週', '実施術者'])[time_col].sum().reset_index(name='時間')
            time_result = time_result.sort_values(['週', '時間'], ascending=[True, False])
    
    return count_result, time_result

# 診療科別分析の最適化関数
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def analyze_surgeon_by_department_optimized(df, selected_department=None):
    """
    診療科ごとの術者分布を分析（最適化版）
    
    Parameters:
    -----------
    df : pandas.DataFrame
        前処理済みのデータフレーム
    selected_department : str, optional
        特定の診療科のみを分析する場合に指定
        
    Returns:
    --------
    pandas.DataFrame
        診療科×術者の集計結果
    """
    # コピーは不要（前処理済みデータを使用）
    df_gas = df.copy()
    
    # 全身麻酔(20分以上)フィルタ
    df_gas = df_gas[
        df_gas['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_gas['麻酔種別'].str.contains("20分以上", na=False)
    ]
    
    if df_gas.empty:
        return pd.DataFrame()
    
    # 特定の診療科のみを処理（高速化）
    if selected_department:
        df_gas = df_gas[df_gas['実施診療科'] == selected_department]
        
        if df_gas.empty:
            return pd.DataFrame()
    
    # 診療科と術者による集計
    result = df_gas.groupby(['実施診療科', '実施術者']).size().reset_index(name='件数')
    result = result.sort_values(['実施診療科', '件数'], ascending=[True, False])
    
    return result

# メイン関数
def create_surgeon_analysis(df_gas, target_dict=None):
    """術者分析UI部分の作成（最適化版）"""
    st.header("👨‍⚕️ 術者別分析")
    
    if df_gas is None or df_gas.empty:
        st.warning("データが見つかりません。データアップロードタブでデータをアップロードしてください。")
        return
    
    # 複数術者の説明
    st.info("""
    **複数術者への対応について**: 
    「実施術者」列に複数の名前が改行区切り（\\n または \\r）で記載されている場合、
    それぞれの術者に対して1件ずつカウントします。
    つまり、1つの手術に2人の術者が関わっていた場合、各術者に1件ずつカウントされます。
    """)
    
    # 時間データの説明（入室時刻と退室時刻から計算）
    st.info("""
    **手術時間の計算について**:
    「入室時刻」と「退室時刻」から実際の手術時間を計算します。
    退室時刻が入室時刻より早い場合は、翌日にまたがる手術と判断します。
    「手術時間」列が既に存在する場合はその値を優先し、なければ計算して使用します。
    時間はすべて時間単位で表示されます。
    """)
    
    # 前処理にプログレスバーを追加
    if 'preprocessed_surgeon_data' not in st.session_state:
        with st.spinner("術者データを前処理中..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("データをフィルタリング中...")
            progress_bar.progress(20)
            
            # まず全身麻酔でフィルタリング（処理対象を減らす）
            df_gas_filtered = df_gas[
                df_gas['麻酔種別'].str.contains("全身麻酔", na=False) &
                df_gas['麻酔種別'].str.contains("20分以上", na=False)
            ].copy()
            
            if df_gas_filtered.empty:
                st.warning("全身麻酔(20分以上)のデータが見つかりません。")
                return
                
            status_text.text("手術時間を計算中...")
            progress_bar.progress(40)
            
            # 並列処理を使用して前処理を高速化
            status_text.text("術者データを展開中...")
            progress_bar.progress(60)
            
            # 並列処理で前処理
            st.session_state['preprocessed_surgeon_data'] = preprocess_data_parallel(df_gas_filtered)
            
            status_text.text("前処理完了")
            progress_bar.progress(100)
            st.success("術者データの前処理が完了しました。")
            
    # セッションステートから前処理済みデータを取得
    temp_df = st.session_state['preprocessed_surgeon_data']
    
    # 術者リスト取得
    surgeons = sorted(temp_df["実施術者"].dropna().unique().tolist())
    
    if not surgeons:
        st.warning("データに術者情報が見つかりません。")
        return
    
    # 複数術者の統計情報を表示
    original_count = df_gas["実施術者"].nunique()
    expanded_count = len(surgeons)
    if expanded_count > original_count:
        st.success(f"複数術者の分割により、{original_count}人 → {expanded_count}人 の術者が識別されました。")
        
    # 入室時刻と退室時刻の列が存在するか確認
    has_entry_exit_time = ('入室時刻' in df_gas.columns and '退室時刻' in df_gas.columns) or \
                           any('üº' in col for col in df_gas.columns) and any('Þº' in col for col in df_gas.columns)
    
    if has_entry_exit_time and '手術時間(時間)' in temp_df.columns:
        avg_duration = temp_df['手術時間(時間)'].mean()
        st.success(f"入室時刻と退室時刻から手術時間を計算しました。全体の平均手術時間: {avg_duration:.2f} 時間")
    
    # 分析タイプ選択
    analysis_type = st.radio("分析タイプ", ["時系列分析", "診療科別分析"], horizontal=True)
    
    if analysis_type == "時系列分析":
        # 時系列分析UI
        col1, col2 = st.columns(2)
        
        with col1:
            period_type = st.radio("分析単位", ["週単位", "月単位", "四半期単位"], horizontal=True)
        
        with col2:
            selection_mode = st.radio("術者選択方法", ["上位表示", "個別選択"], horizontal=True)
        
        if selection_mode == "上位表示":
            top_n = st.slider("表示する術者数", min_value=3, max_value=30, value=15)
            selected_surgeons = None
        else:
            selected_surgeons = st.multiselect("術者選択", surgeons, default=surgeons[:5] if len(surgeons) > 5 else surgeons)
            top_n = 10  # ダミー値
            
            if not selected_surgeons:
                st.warning("分析対象の術者を1人以上選択してください。")
                return
        
        # 遅延実行のためのボタン
        execute_button = st.button("集計を実行", key="run_time_analysis")
        
        if execute_button:
            with st.spinner(f"{period_type}での集計を実行中..."):
                # 期間タイプに応じた集計
                period_map = {"週単位": "weekly", "月単位": "monthly", "四半期単位": "quarterly"}
                
                # 件数と時間の集計を取得
                count_data, time_data = analyze_surgeon_summary_optimized(temp_df, period_map[period_type])
                
                if count_data.empty:
                    st.warning(f"{period_type}での集計データがありません。")
                    return
                
                # 集計データテーブル
                st.subheader("術者別手術件数集計")
                
                # ピボットテーブル作成（表示のため）
                time_column_ui = '週' if period_type == "週単位" else ('月' if period_type == "月単位" else '四半期')
                
                if period_type == "四半期単位" and '四半期ラベル' in count_data.columns:
                    pivot_source = count_data[['四半期', '四半期ラベル', '実施術者', '件数']]
                    pivot_column = '四半期ラベル'
                else:
                    pivot_source = count_data
                    pivot_column = time_column_ui
                    
                pivot_table = pivot_source.pivot_table(
                    index='実施術者', 
                    columns=pivot_column, 
                    values='件数', 
                    aggfunc='sum',
                    fill_value=0
                ).reset_index()
                
                # 合計列を追加
                pivot_table['合計'] = pivot_table.iloc[:, 1:].sum(axis=1)
                
                # 合計でソート
                pivot_table = pivot_table.sort_values('合計', ascending=False)
                
                if selection_mode == "上位表示":
                    # 上位N件のみ表示
                    pivot_table = pivot_table.head(top_n)
                elif selected_surgeons:
                    # 選択された術者のみ表示
                    pivot_table = pivot_table[pivot_table['実施術者'].isin(selected_surgeons)]
                
                # テーブル表示
                st.dataframe(
                    pivot_table.style.format({col: "{:.0f}" for col in pivot_table.columns if col != '実施術者'})
                             .set_table_styles(sc.TABLE_STYLE_PROPS),
                    use_container_width=True
                )
                
                # CSVダウンロードボタン
                render_download_button(pivot_table, "surgeon", period_map[period_type])
                
                # 手術時間テーブル（時間データがある場合）
                if not time_data.empty:
                    st.subheader("術者別手術時間集計 (時間単位)")
                    
                    # ピボットテーブル作成
                    if period_type == "四半期単位" and '四半期ラベル' in time_data.columns:
                        time_pivot_source = time_data[['四半期', '四半期ラベル', '実施術者', '時間']]
                        time_pivot_column = '四半期ラベル'
                    else:
                        time_pivot_source = time_data
                        time_pivot_column = time_column_ui
                        
                    time_pivot_table = time_pivot_source.pivot_table(
                        index='実施術者', 
                        columns=time_pivot_column, 
                        values='時間', 
                        aggfunc='sum',
                        fill_value=0
                    ).reset_index()
                    
                    # 合計列を追加
                    time_pivot_table['合計'] = time_pivot_table.iloc[:, 1:].sum(axis=1)
                    
                    # 合計でソート
                    time_pivot_table = time_pivot_table.sort_values('合計', ascending=False)
                    
                    if selection_mode == "上位表示":
                        # 上位N件のみ表示
                        time_pivot_table = time_pivot_table.head(top_n)
                    elif selected_surgeons:
                        # 選択された術者のみ表示
                        time_pivot_table = time_pivot_table[time_pivot_table['実施術者'].isin(selected_surgeons)]
                    
                    # テーブル表示
                    st.dataframe(
                        time_pivot_table.style.format({col: "{:.1f}" for col in time_pivot_table.columns if col != '実施術者'})
                                 .set_table_styles(sc.TABLE_STYLE_PROPS),
                        use_container_width=True
                    )
                    
                    # CSVダウンロードボタン
                    render_download_button(time_pivot_table, "surgeon_time", period_map[period_type])

    else:  # 診療科別分析
        # 診療科リストを取得（データから）
        data_departments = sorted(temp_df["実施診療科"].dropna().unique().tolist())
    
        # 目標データから診療科リストを取得（もし利用可能なら）
        target_departments = []
        if target_dict and 'departments' in target_dict:
            target_departments = target_dict['departments']
    
        # 目標データの診療科のみを使用
        if target_departments:
            departments = sorted([dept for dept in data_departments if dept in target_departments])
            if not departments:
                # 目標データの診療科が実際のデータにない場合、警告を表示してすべての診療科を使用
                st.warning("目標データの診療科がデータ内に見つかりません。すべての診療科を表示します。")
                departments = data_departments
        else:
            # 目標データがない場合はすべての診療科を使用
            departments = data_departments
    
        if not departments:
            st.warning("データに診療科情報が見つかりません。")
            return
    
        # 診療科選択UI
        selected_department = st.selectbox(
            "診療科選択", 
            ["すべての診療科"] + departments,
            index=0
        )
    
        # 上位表示数
        top_surgeons = st.slider("表示する術者数", min_value=5, max_value=50, value=15)
        
        # 実行ボタン
        execute_button = st.button("分析を実行", key="run_dept_analysis")
        
        if execute_button:
            with st.spinner("診療科別分析を実行中..."):
                # 診療科別分析の実行
                dept_param = None if selected_department == "すべての診療科" else selected_department
                result_df = analyze_surgeon_by_department_optimized(temp_df, selected_department=dept_param)
                
                if result_df.empty:
                    st.warning(f"選択された診療科「{selected_department}」のデータが見つかりません。")
                    return
                
                # 結果表示
                st.subheader(f"{'すべての診療科' if dept_param is None else selected_department}の術者別手術件数")
                
                # 診療科ごとに上位表示
                if dept_param is None:  # すべての診療科の場合
                    # 診療科ごとに上位n件を抽出
                    top_result = pd.DataFrame()
                    for dept in departments:
                        dept_data = result_df[result_df['実施診療科'] == dept]
                        top_surgeons_in_dept = min(top_surgeons, len(dept_data))
                        if top_surgeons_in_dept > 0:
                            top_result = pd.concat([
                                top_result, 
                                dept_data.head(top_surgeons_in_dept)
                            ])
                    
                    # 診療科ごとにソート
                    result_display = top_result.sort_values(['実施診療科', '件数'], ascending=[True, False])
                else:
                    # 1つの診療科の場合は件数で降順ソート
                    result_display = result_df.sort_values('件数', ascending=False).head(top_surgeons)
                
                # テーブル表示
                st.dataframe(
                    result_display.style.format({'件数': '{:.0f}'})
                              .set_table_styles(sc.TABLE_STYLE_PROPS),
                    use_container_width=True
                )
                
                # CSVダウンロードボタン
                render_download_button(result_display, 
                                      f"surgeon_by_dept{'_all' if dept_param is None else '_' + dept_param}", 
                                      "dept_analysis")
# 手術時間集計（時間列があるか確認）
                time_col = None
                
                # 計算した手術時間を優先
                if '手術時間(時間)' in temp_df.columns:
                    time_col = '手術時間(時間)'
                # 他の時間列をチェック
                else:
                    for col in ['予定所要時間', '予定所要時間(OR)', '予定使用時間', '実績時間']:
                        if col in temp_df.columns:
                            time_col = col
                            break
                    
                    # 文字化けした列名もチェック
                    if not time_col:
                        for col in temp_df.columns:
                            if 'pÔ' in col:  # 「時間」を含む可能性がある列
                                time_col = col
                                break
                
                # 時間列がある場合は手術時間集計を表示
                if time_col:
                    st.subheader("術者別手術時間集計 (時間単位)")
                    
                    # 全身麻酔(20分以上)フィルタ
                    df_time = temp_df[
                        temp_df['麻酔種別'].str.contains("全身麻酔", na=False) &
                        temp_df['麻酔種別'].str.contains("20分以上", na=False)
                    ].copy()
                    
                    # 選択された診療科でフィルタ
                    if dept_param:
                        df_time = df_time[df_time['実施診療科'] == dept_param]
                    
                    if not df_time.empty:
                        # 診療科と術者による手術時間集計
                        time_result = df_time.groupby(['実施診療科', '実施術者'])[time_col].sum().reset_index(name='時間')
                        time_result = time_result.sort_values(['実施診療科', '時間'], ascending=[True, False])
                        
                        # 診療科ごとに上位表示
                        if dept_param is None:  # すべての診療科の場合
                            # 診療科ごとに上位n件を抽出
                            top_time_result = pd.DataFrame()
                            for dept in departments:
                                dept_data = time_result[time_result['実施診療科'] == dept]
                                top_surgeons_in_dept = min(top_surgeons, len(dept_data))
                                if top_surgeons_in_dept > 0:
                                    top_time_result = pd.concat([
                                        top_time_result, 
                                        dept_data.head(top_surgeons_in_dept)
                                    ])
                            
                            # 診療科ごとにソート
                            time_display = top_time_result.sort_values(['実施診療科', '時間'], ascending=[True, False])
                        else:
                            # 1つの診療科の場合は時間で降順ソート
                            time_display = time_result.sort_values('時間', ascending=False).head(top_surgeons)
                        
                        # テーブル表示
                        st.dataframe(
                            time_display.style.format({'時間': '{:.1f}'})
                                     .set_table_styles(sc.TABLE_STYLE_PROPS),
                            use_container_width=True
                        )
                        
                        # CSVダウンロードボタン
                        render_download_button(time_display, 
                                              f"surgeon_time_by_dept{'_all' if dept_param is None else '_' + dept_param}", 
                                              "dept_time_analysis")
                    else:
                        st.warning("選択した条件での手術時間データが見つかりません。")
                else:
                    st.info("データに手術時間列が見つかりません。")