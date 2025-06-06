import pandas as pd
import streamlit as st

def preprocess_dataset(df):
    """
    アプリケーション全体で使用するために必要なすべての前処理をデータロード時に一度だけ実行
    
    Parameters:
    -----------
    df : pandas.DataFrame
        元の生データフレーム
        
    Returns:
    --------
    pandas.DataFrame
        前処理済みデータフレーム
    """
    try:
        # 日付変換（一度だけ実行）
        if '手術実施日_dt' not in df.columns and '手術実施日' in df.columns:
            df['手術実施日_dt'] = pd.to_datetime(df['手術実施日'], errors='coerce')
            
        # 日付列があるがNoneやNaNの行を削除
        df = df.dropna(subset=['手術実施日_dt'])
        
        # 重複レコードの識別と削除
        if all(col in df.columns for col in ["手術実施日", "実施診療科", "実施手術室", "入室時刻"]):
            df['unique_op_id'] = (
                df['手術実施日'].astype(str) + '_' +
                df['実施診療科'].astype(str) + '_' +
                df['実施手術室'].astype(str) + '_' +
                df['入室時刻'].astype(str)
            )
            records_before = len(df)
            df = df.drop_duplicates(subset='unique_op_id', keep='last')
            records_after = len(df)
            print(f"前処理で {records_before - records_after} 件の重複レコードを削除しました。")
        elif all(col in df.columns for col in ["手術実施日", "実施診療科"]):
            df['unique_op_id'] = df['手術実施日'].astype(str) + '_' + df['実施診療科'].astype(str)
            records_before = len(df)
            df = df.drop_duplicates(subset='unique_op_id', keep='last')
            records_after = len(df)
            print(f"最低限のチェックで {records_before - records_after} 件の重複を削除しました。")
        
        # 全身麻酔判定フラグを事前に準備（頻繁に使用されるため）
        if '麻酔種別' in df.columns:
            df['is_gas_20min'] = (
                df['麻酔種別'].str.contains("全身麻酔", na=False) &
                df['麻酔種別'].str.contains("20分以上", na=False)
            )
        
        # 平日判定も事前に計算（頻繁に使用されるため）
        if '手術実施日_dt' in df.columns:
            from holiday_handler import is_weekday
            df['is_weekday'] = df['手術実施日_dt'].apply(is_weekday)
        
        # 年度・月・週の情報も事前に計算
        if '手術実施日_dt' in df.columns:
            # 年度
            df['fiscal_year'] = df['手術実施日_dt'].apply(
                lambda d: d.year if d.month >= 4 else d.year - 1
            )
            
            # 月（月初日）
            df['month_start'] = df['手術実施日_dt'].dt.to_period('M').apply(lambda r: r.start_time)
            
            # 週（月曜始まり）
            df['week_start'] = df['手術実施日_dt'] - pd.to_timedelta(df['手術実施日_dt'].dt.dayofweek, unit='d')
            df['week_start'] = df['week_start'].dt.normalize()  # 時間部分を削除
        
        return df
        
    except Exception as e:
        print(f"データ前処理中にエラーが発生しました: {e}")
        # 処理できなかった場合は元のデータフレームを返す
        return df
        
def load_single_file(uploaded_file):
    """
    CSVファイルを読み込む関数
    複数のエンコーディングを試行する
    """
    encodings = ['cp932', 'utf-8-sig', 'utf-8', 'shift-jis', 'euc-jp']
    last_exception = None

    for encoding in encodings:
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding=encoding)
            
            # 列名とデータの空白を削除
            df.columns = df.columns.map(lambda x: x.strip() if isinstance(x, str) else x)
            df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

            # ここから変更: 前処理を適用
            df = preprocess_dataset(df)
            
            # 以下は残すが、多くの処理はpreprocess_dataset()に移動したため不要になる可能性がある
            if '手術実施日_dt' not in df.columns and '手術実施日' in df.columns:
                df["手術実施日_dt"] = pd.to_datetime(df["手術実施日"], errors="coerce")
                invalid_dates = df[df['手術実施日_dt'].isna()]['手術実施日'].unique()
                if len(invalid_dates) > 0:
                    st.warning(f"ファイル '{uploaded_file.name}': 次の日付形式が認識できませんでした: {list(invalid_dates)}")
            return df
        except Exception as e:
            last_exception = e
            continue

    error_msg = f"ファイル '{uploaded_file.name}' の読み込みに失敗しました。試行したエンコーディング: {', '.join(encodings)}. 最後のエラー: {last_exception}"
    st.error(error_msg)
    raise ValueError(error_msg)

def create_unique_id(df):
    """
    レコードの重複チェック用の一意のIDを作成
    必要なカラムが不足している場合は警告を表示
    """
    required_cols = ["手術実施日", "実施診療科", "実施手術室", "入室時刻"]
    
    # 必要なカラムがすべて存在するか確認
    if all(col in df.columns for col in required_cols):
        # データの前処理（None、NaN対策）
        processed_df = df.copy()
        for col in required_cols:
            processed_df[col] = processed_df[col].fillna('').astype(str).str.strip()
        
        # 一意のIDを作成
        processed_df['unique_id'] = (
            processed_df['手術実施日'] + '_' +
            processed_df['実施診療科'] + '_' +
            processed_df['実施手術室'] + '_' +
            processed_df['入室時刻']
        )
        
        # 元のデータフレームにIDをセット
        df['unique_id'] = processed_df['unique_id']
        
        # 空のIDを持つレコードがあるか確認
        empty_ids = df[df['unique_id'] == '___'].index
        if len(empty_ids) > 0:
            st.warning(f"{len(empty_ids)}件のレコードに必要なデータが不足しています。重複チェックから除外されます。")
    else:
        # 不足しているカラムを特定
        missing_cols = [col for col in required_cols if col not in df.columns]
        st.warning(f"ID作成用のカラムが不足しています: {missing_cols}。重複チェックができません。")
        
        # 代替IDを作成（可能であれば）
        alt_cols = [col for col in required_cols if col in df.columns]
        if alt_cols:
            # 利用可能なカラムだけでIDを作成
            df['unique_id'] = df[alt_cols].astype(str).agg('_'.join, axis=1)
            st.info(f"代替カラム {alt_cols} を使用して暫定的なIDを作成しました。")
        else:
            # カラムが全くない場合はダミーIDを作成
            df['unique_id'] = range(len(df))
            st.error("適切なIDが作成できません。行番号をIDとして使用します。")
    
    return df

def merge_base_and_updates(base_df, update_files):
    """
    基礎データと更新データをマージする関数
    重複レコードを確実に削除する
    """
    total_duplicates_removed = 0
    
    # 基礎データの処理
    if base_df is not None and not base_df.empty:
        base_df = create_unique_id(base_df)
        count_before_base = len(base_df)
        base_df = base_df.drop_duplicates(subset='unique_id', keep='last')
        count_after_base = len(base_df)
        duplicates_in_base = count_before_base - count_after_base
        total_duplicates_removed += duplicates_in_base
        
        if duplicates_in_base > 0:
            st.info(f"基礎データ内の重複 {duplicates_in_base} 件を削除しました。")
    else:
        st.warning("基礎データが空または存在しません。")
        base_df = pd.DataFrame()

    # 更新ファイルの処理
    update_dfs = []
    
    if update_files:
        st.info(f"{len(update_files)}件の更新ファイルを処理します...")
        
        for i, f in enumerate(update_files):
            try:
                st.text(f"更新ファイル {i+1}/{len(update_files)}: {f.name} を処理中...")
                update_df = load_single_file(f)
                
                # 空のデータフレームをスキップ
                if update_df.empty:
                    st.warning(f"更新ファイル '{f.name}' は空でした。スキップします。")
                    continue
                    
                # 一意のID作成と重複排除
                update_df = create_unique_id(update_df)
                count_before_update = len(update_df)
                update_df = update_df.drop_duplicates(subset='unique_id', keep='last')
                count_after_update = len(update_df)
                duplicates_in_update = count_before_update - count_after_update
                total_duplicates_removed += duplicates_in_update
                
                if duplicates_in_update > 0:
                    st.info(f"更新ファイル '{f.name}' 内の重複 {duplicates_in_update} 件を削除しました。")
                    
                if not update_df.empty:
                    update_dfs.append(update_df)
                    st.success(f"更新ファイル '{f.name}' ({len(update_df)}件) を読み込みました。")
                    
            except Exception as e:
                st.error(f"更新ファイル '{f.name}' の処理中にエラーが発生しました: {e}")
                continue

    # 更新データの結合と重複排除
    if update_dfs:
        # 更新データファイル間の重複を排除
        st.text("更新データ間の重複をチェック中...")
        df_updates = pd.concat(update_dfs, ignore_index=True)
        count_before_concat = len(df_updates)
        df_updates = df_updates.drop_duplicates(subset='unique_id', keep='last')
        count_after_concat = len(df_updates)
        duplicates_between_updates = count_before_concat - count_after_concat
        total_duplicates_removed += duplicates_between_updates
        
        if duplicates_between_updates > 0:
            st.info(f"更新ファイル間の重複 {duplicates_between_updates} 件を削除しました。")
            
        # 基礎データと更新データの結合
        st.text("基礎データと更新データを結合中...")
        combined = pd.concat([base_df, df_updates], ignore_index=True)
    else:
        st.info("有効な更新データがないため、基礎データのみを使用します。")
        combined = base_df

    # 最終的な重複排除
    if combined is not None and not combined.empty:
        count_before_final = len(combined)
        combined = combined.drop_duplicates(subset='unique_id', keep='last')
        count_after_final = len(combined)
        duplicates_in_final = count_before_final - count_after_final
        total_duplicates_removed += duplicates_in_final
        
        if duplicates_in_final > 0:
            st.info(f"基礎データと更新データ間の重複 {duplicates_in_final} 件を削除しました。")
            
        # 不要な列を削除
        if 'unique_id' in combined.columns:
            combined = combined.drop(columns=['unique_id'])

        # 日付変換と並び替え
        if '手術実施日' in combined.columns and '手術実施日_dt' not in combined.columns:
            combined["手術実施日_dt"] = pd.to_datetime(combined["手術実施日"], errors="coerce")
            invalid_dates = combined[combined['手術実施日_dt'].isna()]['手術実施日'].unique()
            if len(invalid_dates) > 0:
                st.warning(f"次の日付形式が認識できませんでした: {list(invalid_dates)}")

        if '手術実施日_dt' in combined.columns:
            sort_columns = ["手術実施日_dt"]
            if '実施診療科' in combined.columns:
                sort_columns.append("実施診療科")
            combined = combined.sort_values(by=sort_columns).reset_index(drop=True)

        st.success(f"データ処理完了: 合計 {len(combined)} 件のレコード、{total_duplicates_removed} 件の重複を排除しました。")
    elif combined is None or combined.empty:
        st.warning("有効なデータがありません。処理を終了します。")
        return pd.DataFrame()

    if combined is not None and not combined.empty:
        # 最終的な前処理を適用
        combined = preprocess_dataset(combined)

    return combined