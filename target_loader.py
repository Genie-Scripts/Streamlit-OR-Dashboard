import pandas as pd

def load_target_file(uploaded_file):
    """
    目標データCSVファイルを読み込み、診療科と目標件数の辞書を返す
    複数のエンコーディングを試行して読み込む
    """
    # エンコーディングのリストを試行順に定義
    encodings = ['cp932', 'utf-8-sig', 'utf-8', 'shift-jis', 'euc-jp']
    
    # 各エンコーディングを試行
    for encoding in encodings:
        try:
            # ファイルポインタをリセット
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding=encoding)
            
            # 列名の空白を削除
            df.columns = df.columns.str.strip()
            
            # カラム名の確認と柔軟な対応
            dept_col = None
            target_col = None
            
            # 診療科カラムの検出
            for col in ["実施診療科", "診療科"]:
                if col in df.columns:
                    dept_col = col
                    break
            
            # 目標値カラムの検出
            for col in ["目標（週合計）", "目標件数", "目標"]:
                if col in df.columns:
                    target_col = col
                    break
            
            if dept_col is None:
                raise ValueError("診療科のカラムが見つかりません")
            
            if target_col is None:
                raise ValueError("目標値のカラムが見つかりません")
            
            df = df[[dept_col, target_col]]
            df = df.rename(columns={dept_col: "診療科", target_col: "目標件数"})
            
            # 非数値データを対処（目標値が数値であることを確認）
            df["目標件数"] = pd.to_numeric(df["目標件数"], errors="coerce")
            df = df.dropna(subset=["目標件数"])
            
            # 正常に読み込めたらその辞書を返す
            return dict(zip(df["診療科"], df["目標件数"]))
        
        except Exception as e:
            # エラーが発生したら次のエンコーディングを試す
            continue
    
    # すべてのエンコーディングで失敗した場合はエラーを発生
    raise ValueError(f"目標データファイルをいずれのエンコーディング({', '.join(encodings)})でも読み込めませんでした。")