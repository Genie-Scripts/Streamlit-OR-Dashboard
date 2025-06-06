# pdf_exporter.py (set_page_config 削除 - 再々確認)
"""
手術件数分析アプリ用のPDFレポート生成モジュール
週報・月報のPDF出力機能を提供する
"""
import pandas as pd
import numpy as np
import io
import base64
from datetime import datetime
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st # Streamlit 自体のインポートは必要
import calendar
import pytz
# A4 を直接インポートし、landscape は削除
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 累積計算・描画関数をインポート
try:
    from department_ranking import calculate_cumulative_cases, plot_cumulative_cases
except ImportError:
    print("WARNING: department_ranking.pyが見つかりません。累積グラフは生成されません。")
    # ダミー関数を定義
    def calculate_cumulative_cases(*args, **kwargs): return pd.DataFrame()
    def plot_cumulative_cases(*args, **kwargs): return None


# --- st.set_page_config() の呼び出しは app_enhanced_with_prediction.py で行う ---
# st.set_page_config(page_title="手術件数分析アプリ", layout="wide") # この行が削除またはコメントアウトされていることを確認

# --- 日本語フォント設定 (変更なし) ---
def setup_japanese_font():
    """日本語フォントの設定（ローカルの fonts フォルダ優先）"""
    # カスタムフォントフォルダを優先チェック
    custom_font_paths = [
        # カレントディレクトリに対する相対パス
        os.path.join('fonts', 'NotoSansJP-Regular.ttf'),
        os.path.join('fonts', 'NotoSans-Regular.ttf'),
        # アプリケーションディレクトリを基準とした絶対パス
        os.path.abspath(os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSansJP-Regular.ttf')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSans-Regular.ttf')),
    ]

    # システム標準フォントのパス（OS別）
    system_font_paths = []

    # 1. カスタムフォントの検索
    for font_path in custom_font_paths:
        if os.path.exists(font_path):
            try:
                font_name = 'NotoSansJP'
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                # Streamlit環境外での実行も考慮し、printに変更
                print(f"日本語フォント(Noto Sans JP)を登録しました: {font_path}")
                return font_name
            except Exception as e:
                print(f"カスタムフォント登録エラー: {e}")

    # 2. システムフォントの検索
    try:
        # Windows環境
        system_font_paths.append(('MSGothic', 'msgothic.ttc'))
        # Mac環境
        system_font_paths.append(('Hiragino', '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'))
        system_font_paths.append(('Hiragino', '/System/Library/Fonts/HiraginoSans-W3.ttc'))
        system_font_paths.append(('AppleGothic', '/System/Library/Fonts/AppleGothic.ttf'))
        # Linux環境
        system_font_paths.append(('IPAGothic', '/usr/share/fonts/truetype/ipafont-gothic/ipag.ttf'))
        system_font_paths.append(('IPAGothic', '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf'))

        for font_name, font_path in system_font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    print(f"システムフォント({font_name})を登録しました: {font_path}")
                    return font_name
                except Exception as e:
                    continue
    except Exception as e:
        print(f"システムフォント検索エラー: {e}")

    # 3. 最後の手段としてデフォルトフォント（Helvetica）を使用
    print("警告: 日本語フォントが見つからないため、一部のテキストが正しく表示されない可能性があります。")
    return 'Helvetica'

# --- プロットをPNG画像に変換する関数 (変更なし) ---
def fig_to_image(fig, width=800, height=400, scale=1.0):
    """Plotlyグラフを画像データに変換"""
    if fig is None:
        return None

    # 画像としてエクスポート
    img_bytes = pio.to_image(fig, format='png', width=width, height=height, scale=scale)
    return img_bytes

# --- 表を作成する関数 (変更なし) ---
# pdf_exporter.py 内の既存の関数を以下のコードで置き換えます
# def create_table_for_pdf(df, title, japanese_font):  # 修正前 (colWidths がない)
def create_table_for_pdf(df, title, japanese_font, colWidths=None): # ★修正後: colWidths=None を追加
    """データフレームからPDF用のテーブルを作成（達成率による色分け機能追加）"""
    if df is None or df.empty:
        return None

    # カスタムスタイルの定義
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName=japanese_font,
        fontSize=10,
        alignment=1  # 中央揃え
    )

    # ヘッダー行のセル内容をParagraphオブジェクトに変換
    header_cells = [Paragraph(str(col), header_style) for col in df.columns]

    # データ行の変換（数値フォーマット適用）
    table_data = [header_cells]
    for _, row in df.iterrows():
        row_data = []
        for i, val in enumerate(row):
            # ... (既存のデータフォーマット処理) ...
            if isinstance(val, (int, float, np.number)): # np.number を追加
                if np.isnan(val): # NaN チェック
                    text = ""
                elif isinstance(val, (int, np.integer)): # 整数型チェック強化
                    text = f"{val:,}"
                else:
                    col_name = df.columns[i]
                    if "率" in col_name or "%" in col_name:
                        text = f"{val:.1f}%"
                    else:
                        text = f"{val:.1f}"
            elif isinstance(val, (datetime, pd.Timestamp)):
                if pd.isna(val):
                    text = ""
                elif val.hour == 0 and val.minute == 0:
                    text = val.strftime('%Y/%m/%d')
                else:
                    text = val.strftime('%Y/%m/%d %H:%M')
            else:
                text = str(val) if pd.notna(val) else ""
            row_data.append(text)
        table_data.append(row_data)

    # テーブル作成
    if colWidths: # colWidths が渡された場合のみ使用
        table = Table(table_data, colWidths=colWidths)
    else:
        table = Table(table_data) # 渡されない場合は従来の動作

    # テーブルスタイル設定
    # ... (既存のスタイル設定) ...
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), japanese_font),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        # ('FONTSIZE', (0, 1), (0, -1), 8), # ← 診療科列のフォントサイズ調整（必要に応じて）
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('FONTNAME', (0, 1), (-1, -1), japanese_font),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])

    # ... (既存の奇数行・偶数行の背景色、達成率の色分け処理) ...
    for i in range(1, len(table_data), 2):
        style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)

    achievement_cols = []
    for i, col in enumerate(df.columns):
        if '達成率' in str(col) or '%' in str(col):
            achievement_cols.append(i)
    
    if achievement_cols:
        for row_idx in range(1, len(table_data)):
            for col_idx in achievement_cols:
                try:
                    cell_value = table_data[row_idx][col_idx]
                    if '%' in cell_value:
                        rate = float(cell_value.replace('%', '').strip())
                        if rate >= 100:
                            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(0.3, 0.7, 0.3, 0.2))
                        elif rate >= 90:
                            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(1.0, 0.9, 0.2, 0.2))
                        elif rate >= 80:
                            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(1.0, 0.6, 0.0, 0.2))
                        else:
                            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.Color(1.0, 0.3, 0.3, 0.2))
                except (ValueError, TypeError):
                    pass

    table.setStyle(style)
    return table
    
# --- レポートのセクションを作成する関数 (変更なし) ---
def create_report_section(title, description, japanese_font, chart=None, table_df=None, colWidths=None): # colWidths を追加
    """レポートのセクション（タイトル、説明、グラフ、表）を作成"""
    styles = getSampleStyleSheet()

    # カスタムスタイルの定義
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading1'],
        fontName=japanese_font,
        fontSize=16,
        spaceAfter=10
    )

    description_style = ParagraphStyle(
        'Description',
        parent=styles['Normal'],
        fontName=japanese_font,
        fontSize=10,
        spaceAfter=15,
        leading=14 # 行間調整
    )

    content = []

    # セクションタイトル
    content.append(Paragraph(title, section_title_style))

    # 説明テキスト (改行を <br/> に変換)
    if description:
        desc_html = description.replace('\n', '<br/>')
        content.append(Paragraph(desc_html, description_style))

    # チャート（グラフ）
    if chart is not None:
        try:
            # 画像生成 (解像度はそのまま)
            img_data = fig_to_image(chart, width=700, height=350)
            if img_data:
                # PDF内の画像幅を縦向き用に調整 (16cm -> 15cm)
                img = Image(io.BytesIO(img_data), width=15*cm, height=7.5*cm) # 高さは幅に合わせて調整
                img.hAlign = 'CENTER'
                content.append(img)
                content.append(Spacer(1, 10))
        except Exception as e:
            print(f"グラフ画像生成エラー: {e}")
            content.append(Paragraph(f"グラフ描画エラー: {e}", styles['Normal']))


    # データテーブル
    if table_df is not None and not table_df.empty:
        table = create_table_for_pdf(table_df, title, japanese_font, colWidths=colWidths) # colWidths を渡す
        if table:
            content.append(table)
            content.append(Spacer(1, 15))
    return content

# --- フッター描画関数 (変更なし) ---
def add_footer(canvas, doc, footer_text):
    """PDFの各ページにフッターを追加する (作成日を含む)"""
    japanese_font = setup_japanese_font() # フッターでもフォント設定を確認
    canvas.saveState()
    canvas.setFont(japanese_font, 9)

    # 作成日を取得
    creation_date_str = datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y/%m/%d')

    # フッターテキスト (中央揃え)
    center_text = f"{footer_text} | 作成日: {creation_date_str}"
    canvas.drawCentredString(doc.width/2.0 + doc.leftMargin, doc.bottomMargin - 10, center_text)

    # ページ番号 (右揃え)
    page_num = f"- {canvas.getPageNumber()} -"
    canvas.drawRightString(doc.width + doc.leftMargin - 1*cm, doc.bottomMargin - 10, page_num)

    canvas.restoreState()

# --- PDF全体を生成する関数 (病院全体 - 週次) (累積実績セクション追加) ---
# --- PDF全体を生成する関数 (病院全体 - 週次) (診療科目標達成状況セクション追加) ---
def generate_hospital_weekly_report(weekly_data, fig_weekly, target_dict=None, extras=None, model_comparison=None, dept_performance=None):
    """病院全体の週次レポートPDFを生成 (2025年度達成率で降順ソート対応)"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2.5*cm, # フッター領域確保
        leftMargin=2*cm,
        rightMargin=2*cm
    )

    # 日本語フォント設定
    japanese_font = setup_japanese_font()

    # コンテンツリスト
    content = []

    # extrasから必要なデータを取得
    averages_data = extras.get('averages_data') if extras else None
    cumulative_data = extras.get('cumulative_data') if extras else None
    cumulative_fig = extras.get('cumulative_fig') if extras else None

    # 週次推移セクション
    if weekly_data is not None and not weekly_data.empty:
        latest_week = weekly_data['週'].max()
        latest_week_data = weekly_data[weekly_data['週'] == latest_week].iloc[0]
        latest_week_str = latest_week.strftime('%Y年%m月%d日') + " 週"
        latest_avg = latest_week_data['平日1日平均件数'] if '平日1日平均件数' in latest_week_data else 'N/A'
        period_avg = weekly_data['平日1日平均件数'].mean() if '平日1日平均件数' in weekly_data.columns else 'N/A'
        target_val = 21.0

        description = f"""
        最新データ（{latest_week_str}）: 平日1日平均 {latest_avg:.1f} 件/日
        全期間平均: {period_avg:.1f} 件/日
        目標値: {target_val:.1f} 件/日
        """

        weekly_section = create_report_section(
            "全身麻酔手術件数 週次推移（病院全体）",
            description,
            japanese_font,
            chart=fig_weekly, # 4週MA付きグラフを使用
            table_df=weekly_data.tail(10)
        )
        content.extend(weekly_section)
        content.append(PageBreak())

    # 期間別平均セクション
    if averages_data is not None and not averages_data.empty:
        avg_section = create_report_section(
            "期間別平均分析",
            "様々な期間での全身麻酔手術の平均件数",
            japanese_font,
            chart=None,
            table_df=averages_data
        )
        content.extend(avg_section)
        
        # 診療科別目標達成状況テーブルをここに追加（新規）
        if dept_performance is not None and not dept_performance.empty:
            content.append(Spacer(1, 20))  # 期間別平均との間に少し余白を追加
            
            # ここで2025年度達成率で降順ソート
            sorted_dept_performance = dept_performance.copy()
            
            # 2025年度達成率の列が存在するか確認
            sort_column = None
            for col in sorted_dept_performance.columns:
                if '2025年度達成率' in col:
                    sort_column = col
                    break
            
            # ソート列が見つかった場合はソートを適用
            if sort_column:
                sorted_dept_performance = sorted_dept_performance.sort_values(by=sort_column, ascending=False)
                sort_description = "診療科別の2025年度目標達成率ランキング（降順）。達成率: 緑=100%以上、黄=90-99%、橙=80-89%、赤=80%未満"
            else:
                sort_description = "各診療科の週次目標と様々な期間での実績および達成率。達成率: 緑=100%以上、黄=90-99%、橙=80-89%、赤=80%未満"
            
            # 診療科別目標達成状況テーブルの列幅を定義
            # A4縦（約170mm利用可能と仮定 = 210mm - 左右マージン各20mm）
            num_cols = len(dept_performance.columns)
            if num_cols > 0:
                department_col_width = 35 * mm  # 「診療科」列の幅を広めに設定 (例: 45mm)
                # 残りの列で利用可能な幅を計算
                remaining_width = (170 * mm) - department_col_width
                other_col_width = remaining_width / (num_cols - 1) if num_cols > 1 else remaining_width
                performance_col_widths = [department_col_width] + [other_col_width] * (num_cols - 1)
            else:
                performance_col_widths = None

            dept_perf_section = create_report_section(
                "診療科別目標達成状況",
                sort_description, # sort_description は既存のコードで定義されている想定
                japanese_font,
                chart=None,
                table_df=sorted_dept_performance, # sorted_dept_performance は既存のコードで定義されている想定
                colWidths=performance_col_widths # 設定した列幅を渡す
            )
            content.extend(dept_perf_section)
        
    content.append(PageBreak()) # 期間別平均の後にも改ページ

    # 累積実績セクション (病院全体)
    if cumulative_data is not None and not cumulative_data.empty:
        try:
            latest_cum_week = cumulative_data['週'].max()
            latest_cum_data = cumulative_data[cumulative_data['週'] == latest_cum_week].iloc[0]
            latest_cum_str = latest_cum_week.strftime('%Y年%m月%d日') + " 週"
            latest_actual = latest_cum_data.get('累積実績件数', 0)
            latest_target = latest_cum_data.get('累積目標件数', 0)
            achievement_rate = (latest_actual / latest_target * 100) if latest_target > 0 else 0

            description_cum = f"""
            最新データ（{latest_cum_str}現在）:
            累積実績: {latest_actual:,.0f} 件
            累積目標: {latest_target:,.0f} 件 (仮目標 95件/週)
            達成率: {achievement_rate:.1f}%
            """

            cumulative_section_hosp = create_report_section(
                "累積実績 vs 目標 (今年度) - 病院全体",
                description_cum,
                japanese_font,
                chart=cumulative_fig,
                table_df=cumulative_data.tail(15)
            )
            content.extend(cumulative_section_hosp)
            
            # 最後のセクションの後には改ページ不要
            # モデル比較セクションがある場合は改ページを追加
            if model_comparison is not None:
                content.append(PageBreak())
                
        except Exception as e:
            print(f"病院全体レポート 累積データ分析エラー: {e}")
            content.append(Paragraph(f"累積データ分析エラー: {str(e)}", ParagraphStyle(
                'Error', parent=getSampleStyleSheet()['Normal'], fontName=japanese_font, fontSize=12, textColor=colors.red
            )))

    # モデル比較セクション
    if model_comparison is not None and not model_comparison.empty:
        try:
            model_comp_description = """
            複数の予測モデルによる手術件数の予測結果比較です。
            各モデルの特性により予測値に差が生じますが、実績データとの乖離が少ない
            モデルがより信頼性が高いと考えられます。
            """
            
            model_comp_section = create_report_section(
                "予測モデル比較（年度末着地予測）",
                model_comp_description,
                japanese_font,
                chart=None,
                table_df=model_comparison
            )
            content.extend(model_comp_section)
        except Exception as e:
            print(f"モデル比較セクション生成エラー: {e}")
            content.append(Paragraph(f"モデル比較セクション生成エラー: {str(e)}", ParagraphStyle(
                'Error', parent=getSampleStyleSheet()['Normal'], fontName=japanese_font, fontSize=12, textColor=colors.red
            )))


    # フッター関数を定義 (lambdaでラップして引数を渡す)
    footer_text = "手術件数分析アプリ (c) 医療情報管理部" # フッター中央のテキスト
    footer_func = lambda canvas, doc: add_footer(canvas, doc, footer_text)

    # PDFを生成
    try:
        doc.build(content, onFirstPage=footer_func, onLaterPages=footer_func)
    except Exception as e:
        print(f"PDF生成エラー (病院全体 週次): {e}")
        # エラーページを追加するなどフォールバック処理
        content.append(Paragraph(f"PDF生成中にエラーが発生しました: {e}", getSampleStyleSheet()['Normal']))
        doc.build(content) # エラー情報付きでビルド試行

    # バッファの内容を取得
    buffer.seek(0)
    return buffer

# --- PDF全体を生成する関数 (病院全体 - 月次/四半期) (変更なし) ---
def generate_hospital_monthly_report(monthly_data, fig, target_dict=None, period_label="月次", filename="hospital_report.pdf"):
    """病院全体の月次または四半期レポートPDFを生成 (縦向き、表紙なし、改ページあり)"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2.5*cm,
        leftMargin=2*cm,
        rightMargin=2*cm
    )

    japanese_font = setup_japanese_font()
    content = []

    if monthly_data is not None and not monthly_data.empty:
        date_col = '月' if period_label == "月次" else '四半期ラベル'
        avg_col = '平日1日平均件数'
        count_col = '平日件数' if period_label == "月次" else '全日件数'

        if date_col not in monthly_data.columns or avg_col not in monthly_data.columns:
             print(f"必要な列が見つかりません: {date_col}, {avg_col}")
        else:
            latest_period = monthly_data[date_col].iloc[-1]
            latest_data = monthly_data.iloc[-1]
            latest_period_str = latest_period.strftime('%Y年%m月') if period_label == "月次" else str(latest_period)
            latest_avg = latest_data.get(avg_col, 'N/A')
            latest_total = latest_data.get(count_col, 'N/A')
            period_avg = monthly_data[avg_col].mean()
            target_val = 21.0

            description = f"""
            最新データ（{latest_period_str}）: 平日1日平均 {latest_avg:.1f} 件/日, {period_label}合計 {latest_total:,.0f} 件
            全期間平均: {period_avg:.1f} 件/日
            目標値: {target_val:.1f} 件/日
            """

            section = create_report_section(
                f"全身麻酔手術件数 {period_label}推移（病院全体）",
                description,
                japanese_font,
                chart=fig,
                table_df=monthly_data.tail(12)
            )
            content.extend(section)

    footer_text = f"手術件数分析アプリ ({period_label}) (c) 医療情報管理部"
    footer_func = lambda canvas, doc: add_footer(canvas, doc, footer_text)

    try:
        doc.build(content, onFirstPage=footer_func, onLaterPages=footer_func)
    except Exception as e:
        print(f"PDF生成エラー ({period_label}): {e}")
        content.append(Paragraph(f"PDF生成中にエラーが発生しました: {e}", getSampleStyleSheet()['Normal']))
        doc.build(content)

    buffer.seek(0)
    return buffer

# --- 累積データ専用のレポート生成関数 (変更なし) ---
def generate_cumulative_report(department, cumulative_data, fig, target_dict=None, filename=None):
    """累積データ専用のPDFレポートを生成 (縦向き、表紙なし)"""
    if filename is None:
        filename = f"department_{department}_cumulative_report.pdf"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2.5*cm,
        leftMargin=2*cm,
        rightMargin=2*cm
    )

    japanese_font = setup_japanese_font()
    content = []

    if cumulative_data is not None and not cumulative_data.empty:
        try:
            latest_cum_week = cumulative_data['週'].max()
            latest_cum_data = cumulative_data[cumulative_data['週'] == latest_cum_week].iloc[0]
            latest_cum_str = latest_cum_week.strftime('%Y年%m月%d日') + " 週"
            latest_actual = latest_cum_data.get('累積実績件数', 0)
            latest_target = latest_cum_data.get('累積目標件数', 0)
            achievement_rate = (latest_actual / latest_target * 100) if latest_target > 0 else 0

            description = f"""
            最新データ（{latest_cum_str}現在）:
            累積実績: {latest_actual:,.0f} 件
            累積目標: {latest_target:,.0f} 件
            達成率: {achievement_rate:.1f}%
            """

            cumulative_section = create_report_section(
                f"{department} 累積実績 vs 目標 (今年度)",
                description,
                japanese_font,
                chart=fig,
                table_df=cumulative_data.tail(15)
            )
            content.extend(cumulative_section)
        except Exception as e:
            print(f"累積データレポート作成エラー: {e}")
            content.append(Paragraph(f"データ分析エラー: {str(e)}", ParagraphStyle(
                'Error', parent=getSampleStyleSheet()['Normal'], fontName=japanese_font, fontSize=12, textColor=colors.red
            )))

    footer_text = f"{department} 累積実績分析レポート (c) 医療情報管理部"
    footer_func = lambda canvas, doc: add_footer(canvas, doc, footer_text)

    try:
        doc.build(content, onFirstPage=footer_func, onLaterPages=footer_func)
    except Exception as e:
        print(f"PDF生成エラー (累積): {e}")
        content.append(Paragraph(f"PDF生成中にエラーが発生しました: {e}", getSampleStyleSheet()['Normal']))
        doc.build(content)

    buffer.seek(0)
    return buffer

# --- PDF全体を生成する関数 (診療科別レポート用) (変更なし) ---
def generate_department_report(department, weekly_data, fig, monthly_data=None, monthly_fig=None,
                              cumulative_data=None, cumulative_fig=None, filename=None):
    """診療科別レポートPDFを生成 (縦向き、表紙なし、改ページあり)"""
    if filename is None:
        filename = f"department_{department}_report.pdf"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2.5*cm,
        leftMargin=2*cm,
        rightMargin=2*cm
    )

    japanese_font = setup_japanese_font()
    content = []
    has_previous_section = False

    if weekly_data is not None and not weekly_data.empty and '週' in weekly_data.columns and '週合計件数' in weekly_data.columns:
        latest_week = weekly_data['週'].max()
        latest_week_data = weekly_data[weekly_data['週'] == latest_week].iloc[0]
        latest_week_str = latest_week.strftime('%Y年%m月%d日') + " 週"
        latest_count = latest_week_data.get('週合計件数', 'N/A')
        period_avg = weekly_data['週合計件数'].mean() if '週合計件数' in weekly_data.columns else 'N/A'

        description = f"""
        最新データ（{latest_week_str}）: 週合計 {latest_count:,.0f} 件
        全期間平均: {period_avg:.1f} 件/週
        """

        weekly_section = create_report_section(
            f"{department} 週次手術件数推移", description, japanese_font, chart=fig, table_df=weekly_data.tail(10)
        )
        content.extend(weekly_section)
        has_previous_section = True

    if monthly_data is not None and not monthly_data.empty and monthly_fig is not None and '月' in monthly_data.columns:
        if has_previous_section: content.append(PageBreak())
        latest_month = monthly_data['月'].max()
        latest_month_data = monthly_data[monthly_data['月'] == latest_month].iloc[0]
        latest_month_str = latest_month.strftime('%Y年%m月')
        latest_count = latest_month_data.get('月合計件数', 'N/A')
        period_avg = monthly_data['月合計件数'].mean() if '月合計件数' in monthly_data.columns else 'N/A'

        description = f"""
        最新データ（{latest_month_str}）: 月合計 {latest_count:,.0f} 件
        全期間平均: {period_avg:.1f} 件/月
        """

        monthly_section = create_report_section(
            f"{department} 月次手術件数推移", description, japanese_font, chart=monthly_fig, table_df=monthly_data.tail(12)
        )
        content.extend(monthly_section)
        has_previous_section = True

    if cumulative_data is not None and not cumulative_data.empty and cumulative_fig is not None and '週' in cumulative_data.columns:
        if has_previous_section: content.append(PageBreak())
        try:
            latest_cum_week = cumulative_data['週'].max()
            latest_cum_data = cumulative_data[cumulative_data['週'] == latest_cum_week].iloc[0]
            latest_cum_str = latest_cum_week.strftime('%Y年%m月%d日') + " 週"
            latest_actual = latest_cum_data.get('累積実績件数', 0)
            latest_target = latest_cum_data.get('累積目標件数', 0)
            achievement_rate = (latest_actual / latest_target * 100) if latest_target > 0 else 0

            description = f"""
            最新データ（{latest_cum_str}現在）:
            累積実績: {latest_actual:,.0f} 件
            累積目標: {latest_target:,.0f} 件
            達成率: {achievement_rate:.1f}%
            """

            cumulative_section = create_report_section(
                f"{department} 累積実績 vs 目標 (今年度)", description, japanese_font, chart=cumulative_fig, table_df=cumulative_data.tail(15)
            )
            content.extend(cumulative_section)
        except Exception as e:
            print(f"診療科別レポート 累積データ分析エラー: {e}")
            content.append(Paragraph(f"累積データ分析エラー: {str(e)}", ParagraphStyle(
                'Error', parent=getSampleStyleSheet()['Normal'], fontName=japanese_font, fontSize=12, textColor=colors.red
            )))

    footer_text = f"{department} 手術件数分析レポート (c) 医療情報管理部"
    footer_func = lambda canvas, doc: add_footer(canvas, doc, footer_text)

    try:
        doc.build(content, onFirstPage=footer_func, onLaterPages=footer_func)
    except Exception as e:
        print(f"PDF生成エラー (診療科別): {e}")
        content.append(Paragraph(f"PDF生成中にエラーが発生しました: {e}", getSampleStyleSheet()['Normal']))
        doc.build(content)

    buffer.seek(0)
    return buffer


# --- StreamlitからPDFをダウンロードする関数 (変更なし) ---
def render_pdf_download_button(pdf_buffer, button_text, file_name):
    """PDFダウンロードボタンを表示"""
    if pdf_buffer is None:
        # st.error は Streamlit コマンドなのでここでは print に変更
        print("PDF生成に失敗しました。ダウンロードできません。")
        return

    try:
        pdf_buffer.seek(0) # バッファの先頭に戻す
        b64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')
        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{file_name}">📥 {button_text}</a>'
        st.markdown(href, unsafe_allow_html=True) # Streamlit コマンドはここだけ
    except Exception as e:
        # st.error は Streamlit コマンドなのでここでは print に変更
        print(f"PDFダウンロードリンク作成中にエラーが発生しました: {e}")


# --- PDFダウンロードボタンを表示 (Streamlit専用) (変更なし) ---
def add_pdf_report_button(data_type, period_type, df, fig, department=None, target_dict=None, extras=None):
    """データタイプと期間タイプに応じたPDFレポートのダウンロードボタンを表示"""
    # df が None または空の場合のチェックを強化
    if df is None or df.empty:
        # extras にデータがあるか確認 (診療科別レポートなど)
        if data_type == 'department' and extras:
            # extras 内のデータが None または空でないかチェック
            has_extra_data = False
            for key in ['monthly_data', 'cumulative_data']:
                if extras.get(key) is not None and not extras[key].empty:
                    has_extra_data = True
                    break
            if not has_extra_data and fig is None: # fig もない場合は警告
                st.warning("レポート出力用のデータがありません。")
                return
        elif data_type == 'hospital' and period_type == 'weekly' and extras: # 病院週次特有のチェック
             has_extra_data = False
             for key in ['averages_data', 'cumulative_data']:
                 if extras.get(key) is not None and not extras[key].empty:
                     has_extra_data = True
                     break
             if not has_extra_data and fig is None:
                 st.warning("レポート出力用のデータがありません。")
                 return
        elif data_type not in ['department', 'hospital']: # それ以外で df が空なら警告
             st.warning("レポート出力用のデータがありません。")
             return
        # 上記以外（データがある場合）は処理続行

    current_date = datetime.now().strftime("%Y%m%d")
    pdf_buffer = None # 初期化
    button_text = "レポートPDF" # デフォルト
    file_name = f"{current_date}_report.pdf" # デフォルト

    try:
        if data_type == 'hospital':
            if period_type == 'weekly':
                file_name = f"{current_date}_病院全体_週次レポート.pdf"
                button_text = "週次レポートPDFをダウンロード"
                # generate_hospital_weekly_report は extras を受け取るように修正済み
                pdf_buffer = generate_hospital_weekly_report(df, fig, target_dict, extras)
            elif period_type == 'monthly':
                file_name = f"{current_date}_病院全体_月次レポート.pdf"
                button_text = "月次レポートPDFをダウンロード"
                pdf_buffer = generate_hospital_monthly_report(df, fig, target_dict, period_label="月次")
            else:  # quarterly
                file_name = f"{current_date}_病院全体_四半期レポート.pdf"
                button_text = "四半期レポートPDFをダウンロード"
                # 四半期データの場合、period_label を変更
                pdf_buffer = generate_hospital_monthly_report(df, fig, target_dict, period_label="四半期")

        elif data_type == 'department':
            dept_name = department if department else "全診療科"
            if period_type == 'weekly':
                file_name = f"{current_date}_{dept_name}_週次レポート.pdf"
                button_text = f"{dept_name} 週次レポートPDF"
                monthly_data = extras.get('monthly_data') if extras else None
                monthly_fig = extras.get('monthly_fig') if extras else None
                cumulative_data = extras.get('cumulative_data') if extras else None
                cumulative_fig = extras.get('cumulative_fig') if extras else None
                pdf_buffer = generate_department_report(
                    dept_name, df, fig, # fig はPDF用グラフ(4週MA付き)
                    monthly_data=monthly_data,
                    monthly_fig=monthly_fig,
                    cumulative_data=cumulative_data,
                    cumulative_fig=cumulative_fig,
                    filename=file_name
                )
            elif period_type == 'monthly':
                file_name = f"{current_date}_{dept_name}_月次レポート.pdf"
                button_text = f"{dept_name} 月次レポートPDF"
                # 月次レポートの場合、df が月次データ、fig が月次グラフ
                pdf_buffer = generate_department_report(dept_name, None, None, monthly_data=df, monthly_fig=fig, filename=file_name)
            elif period_type == 'quarterly':
                file_name = f"{current_date}_{dept_name}_四半期レポート.pdf"
                button_text = f"{dept_name} 四半期レポートPDF"
                # 四半期レポートの場合、df が四半期データ、fig が四半期グラフ
                pdf_buffer = generate_department_report(dept_name, None, None, monthly_data=df, monthly_fig=fig, filename=file_name)
            elif period_type == 'cumulative':
                file_name = f"{current_date}_{dept_name}_累積実績レポート.pdf"
                button_text = f"{dept_name} 累積実績レポートPDF"
                # 累積レポートの場合、df が累積データ、fig が累積グラフ
                pdf_buffer = generate_cumulative_report(dept_name, df, fig, target_dict, filename=file_name)

        elif data_type == 'ranking':
            file_name = f"{current_date}_診療科ランキングレポート.pdf"
            button_text = "ランキングレポートPDF"
            # ランキング用のカスタムレポート生成関数は未実装のため暫定対応
            # generate_ranking_report(df, fig, extras) のような関数を別途作成する必要あり
            st.warning("ランキングレポートのPDF生成は現在実装中です。") # 未実装のため警告
            pdf_buffer = None # 未実装なので None

        else:
            # その他のレポートタイプ (デフォルト処理)
            file_name = f"{current_date}_分析レポート.pdf"
            button_text = "分析レポートPDF"
            # デフォルトとして週次レポート関数を使用（要件に応じて変更）
            pdf_buffer = generate_hospital_weekly_report(df, fig, target_dict, extras)

        # ダウンロードボタンを表示 (pdf_buffer が None でない場合のみ)
        if pdf_buffer:
            render_pdf_download_button(pdf_buffer, button_text, file_name)

    except Exception as e:
        st.error(f"PDFレポート生成またはダウンロードボタン表示中にエラーが発生しました: {e}")
        print(f"PDFレポートエラー詳細: {e}") # ログにも出力
        
def generate_department_performance_report(dept_performance_df, filename=None):
    """診療科別目標達成状況テーブルのみを横向きPDFで出力する関数 (達成率降順ソート対応)"""
    import io
    import os
    import pandas as pd
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.units import mm, cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    # 日本語フォントの登録
    font_path = os.path.join('fonts', 'NotoSansJP-Regular.ttf')
    font_bold_path = os.path.join('fonts', 'NotoSansJP-Bold.ttf')
    
    # フォントが存在するか確認してから登録
    font_name = 'NotoSansJP'
    font_bold_name = 'NotoSansJP-Bold'
    
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        if os.path.exists(font_bold_path):
            pdfmetrics.registerFont(TTFont(font_bold_name, font_bold_path))
        
        # フォールバックフォントとして登録
        import reportlab.rl_config
        reportlab.rl_config.canvas_basefontname = font_name
    else:
        print(f"警告: 日本語フォントファイルが見つかりません: {font_path}")
        font_name = 'Helvetica'
        font_bold_name = 'Helvetica-Bold'
    
    # バッファ作成
    buffer = io.BytesIO()
    
    # A4横向きで設定
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.0*cm,  # 左マージンを小さく
        rightMargin=1.0*cm, # 右マージンを小さく
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    # スタイル定義
    styles = getSampleStyleSheet()
    
    # タイトルスタイル
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Heading1'],
        fontName=font_bold_name,
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    # サブタイトルスタイル
    subtitle_style = ParagraphStyle(
        name='SubTitleStyle',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=12,
        alignment=TA_LEFT,
        spaceAfter=8
    )
    
    # 注釈スタイル
    note_style = ParagraphStyle(
        name='NoteStyle',
        parent=styles['BodyText'],
        fontName=font_name,
        fontSize=9,
        alignment=TA_LEFT
    )
    
    # セル内のテキストスタイル - ヘッダー用
    header_style = ParagraphStyle(
        name='HeaderStyle',
        parent=styles['Normal'],
        fontName=font_bold_name,
        fontSize=10,
        alignment=TA_CENTER,
        leading=11  # 行間
    )
    
    # ドキュメント要素のリスト
    elements = []
    
    # タイトルと日付
    import datetime
    current_date = datetime.datetime.now().strftime("%Y年%m月%d日")
    elements.append(Paragraph(f"診療科別目標達成状況一覧 (直近7日達成率 降順)", title_style))
    elements.append(Paragraph(f"出力日: {current_date}", subtitle_style))
    elements.append(Spacer(1, 8*mm))
    
    # テーブルデータの処理
    if dept_performance_df is not None and not dept_performance_df.empty:
        # データを直近7日達成率で降順ソート (DataFrame のソート)
        sort_column = '直近7日達成率 (%)' if '直近7日達成率 (%)' in dept_performance_df.columns else None
        
        if sort_column:
            # ソート前にデータフレームをコピーしてソート
            sorted_df = dept_performance_df.copy()
            sorted_df = sorted_df.sort_values(by=sort_column, ascending=False)
        else:
            # ソート列がない場合はそのまま使用
            sorted_df = dept_performance_df
        
        # 列見出しを2段に分割する関数
        def split_header(header):
            # 長い列見出しを適切な位置で分割
            if "達成率" in header and "%" in header:
                parts = header.split("達成率")
                if len(parts) > 1:
                    return f"{parts[0]}<br/>達成率{parts[1]}"
            elif len(header) > 8:  # 8文字以上なら分割を検討
                # スペースがあればそこで分割
                if " " in header:
                    return header.replace(" ", "<br/>")
                # 括弧があればその前で分割
                elif "（" in header:
                    return header.replace("（", "<br/>（")
                elif "(" in header:
                    return header.replace("(", "<br/>(")
                # 数字の前で分割
                elif any(c.isdigit() for c in header):
                    for i, c in enumerate(header):
                        if c.isdigit() and i > 0:
                            return header[:i] + "<br/>" + header[i:]
            return header
        
        # 列見出しをParagraph化して2段表示対応
        header_row = []
        for col in sorted_df.columns:
            split_text = split_header(str(col))
            header_row.append(Paragraph(split_text, header_style))
        
        # テーブルデータ作成 - ヘッダー行を修正済みのものに
        table_data = [header_row]
        
        # データ行 (ソートされたデータフレームを使用)
        for _, row in sorted_df.iterrows():
            # 数値フォーマット
            formatted_row = []
            for col in sorted_df.columns:
                val = row[col]
                if col == '診療科':
                    formatted_row.append(val)  # 診療科名はそのまま
                elif '達成率' in col:
                    formatted_row.append(f"{val:.1f}" if isinstance(val, (int, float)) else val)  # 達成率は小数点以下1桁
                else:
                    formatted_row.append(f"{val:.1f}" if isinstance(val, (int, float)) else val)  # その他の数値も小数点以下1桁
            table_data.append(formatted_row)
        
        # テーブルの列幅設定
        # 元の列幅設定を維持
        colWidths = [30*mm]  # 診療科列
        colWidths.extend([25*mm] * (len(sorted_df.columns) - 1))  # その他の列
        
        # テーブル作成
        data_table = Table(table_data, colWidths=colWidths)
        
        # テーブルスタイル設定
        style = TableStyle([
            # ヘッダー行の設定 - 高さを調整して2段表示に対応
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),  # 垂直中央揃え
            ('FONTNAME', (0, 0), (-1, 0), font_bold_name),
            # パディングを増やして2行分の余裕を持たせる
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # データ行の設定
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            
            # 数値列の右揃え (1列目以外)
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            # 診療科列は左揃え
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            
            # 枠線設定
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.black),  # ヘッダー行の下線を太く
        ])
        
        # 条件付き書式（達成率に応じた背景色）を優先する
        for i, row in enumerate(table_data[1:], 1):  # ヘッダー行をスキップ
            for j, col in enumerate(sorted_df.columns):
                if '達成率' in str(col):
                    try:
                        cell = row[j]
                        val = float(cell.replace('%', '').strip()) if isinstance(cell, str) else float(cell)
                        if val >= 100:
                            # 緑 (100%以上) - 不透明度を上げて濃くする
                            style.add('BACKGROUND', (j, i), (j, i), colors.Color(0.3, 0.7, 0.3, 0.5))
                        elif val >= 90:
                            # 黄色 (90-99%) - 不透明度を上げて濃くする
                            style.add('BACKGROUND', (j, i), (j, i), colors.Color(1.0, 0.92, 0.23, 0.5))
                        elif val >= 80:
                            # オレンジ (80-89%) - 不透明度を上げて濃くする
                            style.add('BACKGROUND', (j, i), (j, i), colors.Color(1.0, 0.6, 0.0, 0.5))
                        else:
                            # 赤 (80%未満) - 不透明度を上げて濃くする
                            style.add('BACKGROUND', (j, i), (j, i), colors.Color(0.96, 0.26, 0.21, 0.5))
                    except (ValueError, TypeError):
                        pass  # 数値変換できない場合はスキップ
        
        data_table.setStyle(style)
        elements.append(data_table)
        
        # 注釈を追加
        elements.append(Spacer(1, 8*mm))
        
        # 凡例をより見やすく
        legend_text = "※ 色分け凡例:  "
        legend_text += "<font color='#4CAF50'>■</font> 緑=100%以上達成,  "
        legend_text += "<font color='#FFEB3B'>■</font> 黄=90-99%,  "
        legend_text += "<font color='#FF9800'>■</font> オレンジ=80-89%,  "
        legend_text += "<font color='#F44336'>■</font> 赤=80%未満"
        
        legend_style = ParagraphStyle(
            name='LegendStyle',
            parent=styles['BodyText'],
            fontName=font_name,
            fontSize=10,
            alignment=TA_LEFT
        )
        
        elements.append(Paragraph(legend_text, legend_style))
    else:
        # データなしの場合
        elements.append(Paragraph("データが存在しません。", subtitle_style))
    
    # PDFに書き込み
    doc.build(elements)
    buffer.seek(0)
    return buffer

def add_landscape_performance_button(dept_performance_df):
    """診療科別目標達成状況テーブルのみを横向きPDFで出力するボタンを追加"""
    import streamlit as st
    from datetime import datetime
    import uuid  # 一意のキーを生成するためにuuidをインポート
    
    current_date = datetime.now().strftime("%Y%m%d")
    filename = f"{current_date}_診療科別目標達成状況.pdf"
    
    if dept_performance_df is not None and not dept_performance_df.empty:
        try:
            pdf_buffer = generate_department_performance_report(dept_performance_df)
            
            # 一意のキーを生成（タイムスタンプとランダムなUUIDの組み合わせ）
            unique_key = f"download_landscape_performance_{datetime.now().strftime('%H%M%S')}_{str(uuid.uuid4())[:8]}"
            
            st.download_button(
                label="📄 診療科別目標達成状況テーブル (横向きPDF)",
                data=pdf_buffer,
                file_name=filename,
                mime="application/pdf",
                help="診療科別目標達成状況テーブルのみを横向きPDFで出力します",
                key=unique_key  # 一意のキーを使用
            )
        except Exception as e:
            st.error(f"横向きPDF生成エラー: {e}")
            st.exception(e)  # エラーの詳細表示（デバッグ用）
    else:
        st.warning("データが不足しているため、PDFを生成できません。")