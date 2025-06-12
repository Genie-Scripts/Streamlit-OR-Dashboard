# utils/pdf_generator.py
"""
PDF レポート生成モジュール
ダッシュボードの内容をPDF形式で出力
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import base64
from io import BytesIO
import os

# PDF生成ライブラリ
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfutils
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    
    # 日本語フォント設定（fontsフォルダーのNotoSansJPを使用）
    try:
        # プロジェクトルートのfontsフォルダーから読み込み
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
        
        # 利用可能なNotoSansJPフォントファイル
        font_files = {
            'NotoSansJP-Regular': 'NotoSansJP-Regular.ttf',
            'NotoSansJP-Bold': 'NotoSansJP-Bold.ttf',
            'NotoSansJP-Light': 'NotoSansJP-Light.ttf',
            'NotoSansJP-Medium': 'NotoSansJP-Medium.ttf'
        }
        
        # ロガー設定（フォント登録前に必要）
        logger = logging.getLogger(__name__)
        
        # フォント登録
        registered_fonts = {}
        for font_name, font_file in font_files.items():
            font_path = os.path.join(font_dir, font_file)
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    registered_fonts[font_name] = font_path
                    logger.info(f"日本語フォント登録成功: {font_name}")
                except Exception as e:
                    logger.warning(f"フォント登録失敗 {font_name}: {e}")
        
        # 登録されたフォントから使用フォントを決定
        if 'NotoSansJP-Regular' in registered_fonts:
            JAPANESE_FONT = 'NotoSansJP-Regular'
            JAPANESE_FONT_BOLD = 'NotoSansJP-Bold' if 'NotoSansJP-Bold' in registered_fonts else 'NotoSansJP-Regular'
            JAPANESE_FONT_LIGHT = 'NotoSansJP-Light' if 'NotoSansJP-Light' in registered_fonts else 'NotoSansJP-Regular'
            logger.info(f"NotoSansJPフォント使用: {len(registered_fonts)}個のフォントを登録")
        else:
            # フォールバック: reportlab内蔵のCIDフォント
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
            JAPANESE_FONT = 'HeiseiMin-W3'
            JAPANESE_FONT_BOLD = 'HeiseiKakuGo-W5'
            JAPANESE_FONT_LIGHT = 'HeiseiMin-W3'
            logger.warning("NotoSansJPが見つからないため、内蔵フォントを使用")
            
    except Exception as e:
        # 最終フォールバック
        logger = logging.getLogger(__name__)
        logger.error(f"日本語フォント設定エラー: {e}")
        JAPANESE_FONT = 'Helvetica'
        JAPANESE_FONT_BOLD = 'Helvetica-Bold'
        JAPANESE_FONT_LIGHT = 'Helvetica'
        logger.warning("日本語フォントを設定できませんでした。英数字のみ表示されます。")
    
    REPORTLAB_AVAILABLE = True
    
except ImportError:
    REPORTLAB_AVAILABLE = False
    # フォールバック変数
    JAPANESE_FONT = 'Helvetica'
    JAPANESE_FONT_BOLD = 'Helvetica-Bold'
    JAPANESE_FONT_LIGHT = 'Helvetica'

# ロガー設定（ImportError時にも必要）
logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """PDF レポート生成クラス"""
    
    def __init__(self):
        self.styles = None
        self.setup_styles()
    
    def setup_styles(self):
        """PDFスタイルを設定"""
        if not REPORTLAB_AVAILABLE:
            return
        
        self.styles = getSampleStyleSheet()
        
        # カスタムスタイル（日本語フォント対応 + エンコーディング対応）
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontName=JAPANESE_FONT_BOLD,
            fontSize=18,
            spaceAfter=20,
            textColor=colors.darkblue,
            alignment=TA_CENTER,
            wordWrap='CJK'  # 日本語の改行処理
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontName=JAPANESE_FONT_BOLD,
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.darkblue,
            wordWrap='CJK'
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=self.styles['Normal'],
            fontName=JAPANESE_FONT,
            fontSize=10,
            spaceAfter=6,
            wordWrap='CJK'
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomSmall',
            parent=self.styles['Normal'],
            fontName=JAPANESE_FONT,
            fontSize=8,
            spaceAfter=2,
            spaceBefore=2,
            wordWrap='CJK',
            alignment=TA_CENTER  # テーブル用に中央揃え
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomSmallBold',
            parent=self.styles['Normal'],
            fontName=JAPANESE_FONT_BOLD,
            fontSize=8,
            spaceAfter=2,
            spaceBefore=2,
            wordWrap='CJK',
            alignment=TA_CENTER,  # テーブル用に中央揃え
            textColor=colors.whitesmoke  # ヘッダー用の白文字
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomSubHeading',
            parent=self.styles['Heading3'],
            fontName=JAPANESE_FONT_BOLD,
            fontSize=12,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.darkblue,
            wordWrap='CJK'
        ))
    
    def generate_dashboard_report(self, 
                                kpi_data: Dict[str, Any],
                                performance_data: pd.DataFrame,
                                period_info: Dict[str, Any],
                                charts: Dict[str, go.Figure] = None) -> BytesIO:
        """ダッシュボードレポートPDFを生成"""
        
        if not REPORTLAB_AVAILABLE:
            st.error("PDF生成にはreportlabライブラリが必要です")
            return None
        
        # 文字列のサニタイズ処理（改良版・テーブル用）
        def sanitize_text(text):
            """絵文字や特殊文字を除去（改良版）"""
            return self._sanitize_text_for_table(text)
        
        # period_infoの文字列をサニタイズ
        sanitized_period_info = {}
        for key, value in period_info.items():
            sanitized_period_info[key] = sanitize_text(value) if isinstance(value, str) else value
        
        # performance_dataの文字列をサニタイズ
        if not performance_data.empty:
            performance_data_clean = performance_data.copy()
            for col in performance_data_clean.select_dtypes(include=['object']).columns:
                performance_data_clean[col] = performance_data_clean[col].apply(lambda x: sanitize_text(x) if isinstance(x, str) else x)
        else:
            performance_data_clean = performance_data
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # タイトルページ
        story.extend(self._create_title_page(sanitized_period_info))
        
        # ページブレイク
        story.append(PageBreak())
        
        # 概要セクション
        story.extend(self._create_summary_section(kpi_data, sanitized_period_info))
        
        # KPI セクション
        story.extend(self._create_kpi_section(kpi_data))
        
        # パフォーマンスセクション
        if not performance_data_clean.empty:
            story.extend(self._create_performance_section(performance_data_clean))
        
        # グラフセクション
        if charts:
            story.extend(self._create_charts_section(charts))
        
        # フッター情報
        story.extend(self._create_footer_section())
        
        # フォント情報（デバッグ用）
        story.extend(self._create_font_info_section())
        
        # PDF生成
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    def _create_font_info_section(self) -> List:
        """フォント情報セクション（デバッグ用）"""
        story = []
        
        try:
            font_info_text = f"""
            <b>使用フォント情報:</b><br/>
            ・ 通常フォント: {JAPANESE_FONT}<br/>
            ・ 太字フォント: {JAPANESE_FONT_BOLD}<br/>
            ・ 軽量フォント: {JAPANESE_FONT_LIGHT}<br/>
            """
            
            font_info_para = Paragraph(font_info_text, self.styles['CustomSmall'])
            story.append(font_info_para)
        except Exception as e:
            logger.error(f"フォント情報作成エラー: {e}")
        
        return story
    
    def _create_title_page(self, period_info: Dict[str, Any]) -> List:
        """タイトルページを作成"""
        story = []
        
        # メインタイトル（絵文字を除去）
        title = Paragraph("手術分析ダッシュボード", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.8*inch))
        
        # サブタイトル
        subtitle = Paragraph("管理者向けサマリーレポート", self.styles['CustomHeading'])
        story.append(subtitle)
        story.append(Spacer(1, 0.5*inch))
        
        # 期間情報（改行と書式を調整）
        period_text = f"""
        <b>分析期間:</b> {period_info.get('period_name', 'N/A')}<br/><br/>
        <b>対象日:</b> {period_info.get('start_date', 'N/A')} ～ {period_info.get('end_date', 'N/A')}<br/><br/>
        <b>分析日数:</b> {period_info.get('total_days', 'N/A')}日間 (平日: {period_info.get('weekdays', 'N/A')}日)<br/>
        """
        period_para = Paragraph(period_text, self.styles['CustomNormal'])
        story.append(period_para)
        story.append(Spacer(1, 1*inch))
        
        # 生成情報
        generated_text = f"""
        <b>レポート生成日時:</b> {datetime.now().strftime('%Y年%m月%d日 %H:%M')}<br/><br/>
        <b>生成システム:</b> 手術分析ダッシュボード v1.0
        """
        generated_para = Paragraph(generated_text, self.styles['CustomNormal'])
        story.append(generated_para)
        
        return story
    
    def _create_summary_section(self, kpi_data: Dict[str, Any], period_info: Dict[str, Any]) -> List:
        """概要セクションを作成"""
        story = []
        
        # セクションタイトル（絵文字を除去）
        story.append(Paragraph("エグゼクティブサマリー", self.styles['CustomHeading']))
        
        # 主要指標サマリー
        gas_cases = kpi_data.get('gas_cases', 0)
        total_cases = kpi_data.get('total_cases', 0)
        daily_avg = kpi_data.get('daily_avg_gas', 0)
        utilization = kpi_data.get('utilization_rate', 0)
        
        summary_text = f"""
        選択期間（{period_info.get('period_name', 'N/A')}）における手術実績の概要：<br/><br/>
        
        ・ <b>全身麻酔手術件数:</b> {gas_cases:,}件<br/>
        ・ <b>全手術件数:</b> {total_cases:,}件<br/>
        ・ <b>平日1日あたり全身麻酔手術:</b> {daily_avg:.1f}件/日<br/>
        ・ <b>手術室稼働率:</b> {utilization:.1f}%<br/><br/>
        
        手術室稼働率は OP-1〜OP-12（OP-11A, OP-11B除く）11室の平日9:00〜17:15における
        実際の稼働時間を基準として算出されています。
        """
        
        summary_para = Paragraph(summary_text, self.styles['CustomNormal'])
        story.append(summary_para)
        story.append(Spacer(1, 0.3*inch))
        
        return story
    
    def _create_kpi_section(self, kpi_data: Dict[str, Any]) -> List:
        """KPI セクションを作成"""
        story = []
        
        # セクションタイトル（絵文字を除去）
        story.append(Paragraph("主要業績指標 (KPI)", self.styles['CustomHeading']))
        
        # KPI テーブルデータ（Paragraphオブジェクトとして改行を処理）
        kpi_table_data = [
            [
                Paragraph('指標', self.styles['CustomSmallBold']),
                Paragraph('値', self.styles['CustomSmallBold']),
                Paragraph('単位', self.styles['CustomSmallBold']),
                Paragraph('備考', self.styles['CustomSmallBold'])
            ],
            [
                Paragraph('全身麻酔手術件数', self.styles['CustomSmall']),
                Paragraph(f"{kpi_data.get('gas_cases', 0):,}", self.styles['CustomSmall']),
                Paragraph('件', self.styles['CustomSmall']),
                Paragraph('20分以上の<br/>全身麻酔手術', self.styles['CustomSmall'])
            ],
            [
                Paragraph('全手術件数', self.styles['CustomSmall']),
                Paragraph(f"{kpi_data.get('total_cases', 0):,}", self.styles['CustomSmall']),
                Paragraph('件', self.styles['CustomSmall']),
                Paragraph('全ての手術<br/>(局麻等含む)', self.styles['CustomSmall'])
            ],
            [
                Paragraph('平日1日あたり<br/>全身麻酔手術', self.styles['CustomSmall']),
                Paragraph(f"{kpi_data.get('daily_avg_gas', 0):.1f}", self.styles['CustomSmall']),
                Paragraph('件/日', self.styles['CustomSmall']),
                Paragraph('平日(月〜金)<br/>の平均', self.styles['CustomSmall'])
            ],
            [
                Paragraph('手術室稼働率', self.styles['CustomSmall']),
                Paragraph(f"{kpi_data.get('utilization_rate', 0):.1f}", self.styles['CustomSmall']),
                Paragraph('%', self.styles['CustomSmall']),
                Paragraph('OP-1〜12の<br/>実稼働時間ベース', self.styles['CustomSmall'])
            ]
        ]
        
        # テーブル作成（幅を調整）
        kpi_table = Table(kpi_table_data, colWidths=[3.5*cm, 2*cm, 1.5*cm, 3.5*cm])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # 縦方向中央揃え
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(kpi_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 稼働時間詳細
        actual_minutes = kpi_data.get('actual_minutes', 0)
        max_minutes = kpi_data.get('max_minutes', 0)
        
        detail_text = f"""
        <b>手術室稼働詳細:</b><br/>
        ・ 実際稼働時間: {actual_minutes:,}分 ({actual_minutes/60:.1f}時間)<br/>
        ・ 最大稼働時間: {max_minutes:,}分 ({max_minutes/60:.1f}時間)<br/>
        ・ 平日数: {kpi_data.get('weekdays', 0)}日<br/>
        """
        
        detail_para = Paragraph(detail_text, self.styles['CustomNormal'])
        story.append(detail_para)
        story.append(Spacer(1, 0.3*inch))
        
        return story
    
    def _create_performance_section(self, performance_data: pd.DataFrame) -> List:
        """パフォーマンスセクションを作成"""
        story = []
        
        # 改ページを追加
        story.append(PageBreak())
        
        # セクションタイトル（絵文字を除去）
        story.append(Paragraph("診療科別パフォーマンス", self.styles['CustomHeading']))
        
        # パフォーマンステーブル（Paragraphオブジェクトとして改行を処理）
        perf_table_data = [
            [
                Paragraph('診療科', self.styles['CustomSmallBold']),
                Paragraph('期間<br/>平均', self.styles['CustomSmallBold']),
                Paragraph('直近週<br/>実績', self.styles['CustomSmallBold']),
                Paragraph('週次<br/>目標', self.styles['CustomSmallBold']),
                Paragraph('達成率<br/>(%)', self.styles['CustomSmallBold'])
            ]
        ]
        
        for _, row in performance_data.iterrows():
            dept_name = self._sanitize_text_for_table(str(row['診療科']))
            # 長い診療科名の場合は改行
            if len(dept_name) > 6:
                # 適切な位置で改行を挿入
                if '外科' in dept_name:
                    dept_name = dept_name.replace('外科', '<br/>外科')
                elif '科' in dept_name and len(dept_name) > 8:
                    parts = dept_name.split('科')
                    if len(parts) > 1:
                        dept_name = parts[0] + '科<br/>' + '科'.join(parts[1:])
            
            perf_table_data.append([
                Paragraph(dept_name, self.styles['CustomSmall']),
                Paragraph(f"{row['期間平均']:.1f}", self.styles['CustomSmall']),
                Paragraph(f"{row['直近週実績']:.0f}", self.styles['CustomSmall']),
                Paragraph(f"{row['週次目標']:.1f}", self.styles['CustomSmall']),
                Paragraph(f"{row['達成率(%)']:.1f}", self.styles['CustomSmall'])
            ])
        
        # テーブル作成（幅を調整）
        perf_table = Table(perf_table_data, colWidths=[3*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm])
        perf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # 縦方向中央揃え
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(perf_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 達成率分析
        high_performers = performance_data[performance_data['達成率(%)'] >= 100]
        low_performers = performance_data[performance_data['達成率(%)'] < 80]
        
        analysis_text = f"""
        <b>達成率分析:</b><br/>
        ・ 目標達成科数: {len(high_performers)}科 / {len(performance_data)}科<br/>
        ・ 要注意科数: {len(low_performers)}科 (達成率80%未満)<br/>
        """
        
        if len(high_performers) > 0:
            top_dept = high_performers.iloc[0]
            top_dept_name = self._sanitize_text_for_table(str(top_dept['診療科']))
            analysis_text += f"・ 最高達成率: {top_dept_name} ({top_dept['達成率(%)']:.1f}%)<br/>"
        
        analysis_para = Paragraph(analysis_text, self.styles['CustomNormal'])
        story.append(analysis_para)
        story.append(Spacer(1, 0.3*inch))
        
        return story
    
    def _create_charts_section(self, charts: Dict[str, go.Figure]) -> List:
        """グラフセクションを作成"""
        story = []
        
        # 改ページを追加
        story.append(PageBreak())
        
        # セクションタイトル（絵文字を除去）
        story.append(Paragraph("グラフ・チャート", self.styles['CustomHeading']))
        
        for chart_name, fig in charts.items():
            try:
                # グラフの日本語対応
                fig_clean = self._sanitize_plotly_figure(fig)
                
                # Plotlyグラフを画像に変換（設定最適化）
                img_bytes = pio.to_image(
                    fig_clean, 
                    format="png", 
                    width=800, 
                    height=400,
                    engine="kaleido",
                    validate=False  # 検証を無効化してエラーを回避
                )
                img_buffer = BytesIO(img_bytes)
                
                # レポートラブImage作成
                img = Image(img_buffer, width=6*inch, height=3*inch)
                story.append(img)
                
                # キャプション（日本語保持）
                clean_chart_name = self._sanitize_text_for_chart(chart_name)
                if not clean_chart_name or clean_chart_name == "Chart Data":
                    clean_chart_name = "手術分析グラフ"
                caption = Paragraph(f"図: {clean_chart_name}", self.styles['CustomNormal'])
                story.append(caption)
                story.append(Spacer(1, 0.2*inch))
                
            except Exception as e:
                logger.error(f"グラフ変換エラー ({chart_name}): {e}")
                try:
                    # フォールバック: シンプルなプレースホルダーグラフを作成
                    fallback_fig = go.Figure()
                    fallback_fig.add_annotation(
                        text=f"Chart: {self._sanitize_text_safe(chart_name)}",
                        xref="paper", yref="paper",
                        x=0.5, y=0.5, showarrow=False,
                        font=dict(family="Arial", size=14, color="black")
                    )
                    fallback_fig.update_layout(
                        title=dict(
                            text="Surgery Analysis Chart",
                            font=dict(family="Arial", size=16, color="black")
                        ),
                        xaxis=dict(showgrid=False, showticklabels=False),
                        yaxis=dict(showgrid=False, showticklabels=False),
                        font=dict(family="Arial", size=10, color="black"),
                        plot_bgcolor='white',
                        paper_bgcolor='white'
                    )
                    
                    # フォールバックグラフを画像に変換
                    fallback_bytes = pio.to_image(
                        fallback_fig, 
                        format="png", 
                        width=800, 
                        height=400,
                        engine="kaleido",
                        validate=False
                    )
                    fallback_buffer = BytesIO(fallback_bytes)
                    
                    img = Image(fallback_buffer, width=6*inch, height=3*inch)
                    story.append(img)
                    
                    # キャプション（日本語保持）
                    clean_chart_name = self._sanitize_text_for_chart(chart_name)
                    if not clean_chart_name or clean_chart_name == "Chart Data":
                        clean_chart_name = "手術分析グラフ"
                    caption = Paragraph(f"図: {clean_chart_name} (簡易版)", self.styles['CustomNormal'])
                    story.append(caption)
                    story.append(Spacer(1, 0.2*inch))
                    
                except Exception as e2:
                    logger.error(f"フォールバックグラフ作成エラー: {e2}")
                    # 最終フォールバック: テキストのみ（日本語保持）
                    clean_name = self._sanitize_text_for_chart(chart_name)
                    if not clean_name or clean_name == "Chart Data":
                        clean_name = "手術グラフ"
                    error_text = Paragraph(
                        f"グラフ '{clean_name}' - データは正常ですが、PDF変換時にエラーが発生しました", 
                        self.styles['CustomNormal']
                    )
                    story.append(error_text)
                    story.append(Spacer(1, 0.2*inch))
        
        return story
    
    def _sanitize_plotly_figure(self, fig: go.Figure) -> go.Figure:
        """Plotlyグラフの文字化け対策（日本語保持版）"""
        try:
            # figureのコピーを作成
            fig_copy = go.Figure(fig)
            
            # レイアウトのテキストを安全化（日本語保持）
            if fig_copy.layout.title and fig_copy.layout.title.text:
                original_title = fig_copy.layout.title.text
                clean_title = self._sanitize_text_for_chart(original_title)
                fig_copy.layout.title.text = clean_title
                logger.info(f"グラフタイトル処理: {original_title} -> {clean_title}")
            
            if fig_copy.layout.xaxis and fig_copy.layout.xaxis.title and fig_copy.layout.xaxis.title.text:
                fig_copy.layout.xaxis.title.text = self._sanitize_text_for_chart(fig_copy.layout.xaxis.title.text)
            
            if fig_copy.layout.yaxis and fig_copy.layout.yaxis.title and fig_copy.layout.yaxis.title.text:
                fig_copy.layout.yaxis.title.text = self._sanitize_text_for_chart(fig_copy.layout.yaxis.title.text)
            
            # X軸の目盛りラベルを処理
            if hasattr(fig_copy.layout.xaxis, 'ticktext') and fig_copy.layout.xaxis.ticktext:
                fig_copy.layout.xaxis.ticktext = [self._sanitize_text_for_chart(str(tick)) for tick in fig_copy.layout.xaxis.ticktext]
            
            # 凡例とデータ系列の文字列を処理
            for trace in fig_copy.data:
                if hasattr(trace, 'name') and trace.name:
                    original_name = trace.name
                    clean_name = self._sanitize_text_for_chart(trace.name)
                    trace.name = clean_name
                    logger.info(f"凡例処理: {original_name} -> {clean_name}")
                    
                if hasattr(trace, 'text') and trace.text:
                    if isinstance(trace.text, (list, tuple)):
                        trace.text = [self._sanitize_text_for_chart(str(t)) for t in trace.text]
                    else:
                        trace.text = self._sanitize_text_for_chart(str(trace.text))
                        
                # ホバーテキストも処理
                if hasattr(trace, 'hovertext') and trace.hovertext:
                    if isinstance(trace.hovertext, (list, tuple)):
                        trace.hovertext = [self._sanitize_text_for_chart(str(t)) for t in trace.hovertext]
                    else:
                        trace.hovertext = self._sanitize_text_for_chart(str(trace.hovertext))
            
            # --- ▼ここからが修正箇所▼ ---

            # クロスプラットフォームで日本語表示の可能性を高めるフォントファミリーリスト
            # Noto Sans JPを最優先にしつつ、各OSの標準的な日本語フォントをフォールバックとして指定
            font_family_list = [
                "Noto Sans JP",                 # プロジェクト推奨フォント
                "Meiryo",                       # Windows (メイリオ)
                "Yu Gothic",                    # Windows (游ゴシック)
                "Hiragino Sans",                # macOS (ヒラギノ角ゴシック)
                "Hiragino Kaku Gothic ProN",    # macOS
                "IPAexGothic",                  # Linux (要インストール)
                "Arial Unicode MS",             # 多くの文字をカバー
                "sans-serif"                    # 最終フォールバック
            ]
            font_family_str = ", ".join(f'"{name}"' for name in font_family_list)

            # 日本語対応フォント設定の強化
            fig_copy.update_layout(
                font=dict(
                    family=font_family_str,
                    size=10,
                    color="black"
                ),
                title=dict(
                    font=dict(family=font_family_str, size=14, color="black")
                ),
                xaxis=dict(
                    title=dict(font=dict(family=font_family_str, size=10)),
                    tickfont=dict(family=font_family_str, size=8)
                ),
                yaxis=dict(
                    title=dict(font=dict(family=font_family_str, size=10)),
                    tickfont=dict(family=font_family_str, size=8)
                ),
                legend=dict(
                    font=dict(family=font_family_str, size=8)
                )
            )
            
            logger.info(f"Plotlyグラフのフォントファミリーを '{font_family_str}' に設定しました。")
            
            # --- ▲ここまでが修正箇所▲ ---
            
            return fig_copy
            
        except Exception as e:
            logger.error(f"Plotlyグラフ処理エラー: {e}")
            # エラー時はシンプルなグラフを返す
            try:
                fig_simple = go.Figure()
                fig_simple.add_annotation(
                    text="手術データグラフ",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(family="Noto Sans JP, Arial, sans-serif", size=12)
                )
                fig_simple.update_layout(
                    title="手術分析グラフ",
                    font=dict(family="Noto Sans JP, Arial, sans-serif", size=10)
                )
                return fig_simple
            except:
                return fig
    
    def _sanitize_text_for_table(self, text: str) -> str:
        """テーブル用文字列処理（日本語保持）"""
        if not isinstance(text, str):
            text = str(text)
        
        # テーブルでは日本語をそのまま保持
        # ただし、問題のある文字のみ除去
        import re
        
        # 絵文字や制御文字のみ除去、日本語は保持
        cleaned = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]', '', text)
        
        return cleaned.strip() if cleaned.strip() else text
    
    def _sanitize_text_for_chart(self, text: str) -> str:
        """グラフ用文字列処理（文字化け対策）"""
        if not isinstance(text, str):
            text = str(text)
        
        # 空文字チェック
        if not text.strip():
            return "Data"
        
        # 日本語を保持しつつ、問題のある文字のみ除去
        import re
        
        # 絵文字や特殊記号のみ除去
        cleaned = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]', '', text)
        
        # 制御文字を除去
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        
        return cleaned.strip() if cleaned.strip() else "Chart Data"
    
    def _create_footer_section(self) -> List:
        """フッターセクションを作成"""
        story = []
        
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("ーーーーーーーーーーーーーーーーーーーーーーーーーーーー", self.styles['CustomNormal']))
        
        footer_text = f"""
        <b>レポート生成情報:</b><br/>
        ・ システム: 手術分析ダッシュボード v1.0<br/>
        ・ 生成日時: {datetime.now().strftime('%Y年%m月%d日 %H時%M分')}<br/>
        ・ 注意事項: このレポートに含まれる情報は分析対象期間のデータに基づいています<br/>
        """
        
        footer_para = Paragraph(footer_text, self.styles['CustomNormal'])
        story.append(footer_para)
        
        return story


# Streamlit用のPDF出力インターフェース
class StreamlitPDFExporter:
    """Streamlit用PDF出力インターフェース"""
    
    @staticmethod
    def add_pdf_download_button(kpi_data: Dict[str, Any],
                               performance_data: pd.DataFrame,
                               period_info: Dict[str, Any],
                               charts: Dict[str, go.Figure] = None,
                               button_label: str = "📄 PDFレポートをダウンロード"):
        """PDFダウンロードボタンを追加"""
        
        if not REPORTLAB_AVAILABLE:
            st.error("📋 PDF出力機能を使用するには以下のライブラリのインストールが必要です:")
            st.code("pip install reportlab")
            return
        
        # フォント情報の表示
        try:
            if 'JAPANESE_FONT' in globals():
                if JAPANESE_FONT.startswith('NotoSansJP'):
                    st.success(f"✅ 日本語フォント: {JAPANESE_FONT} が使用されます")
                else:
                    st.warning(f"⚠️ フォールバックフォント: {JAPANESE_FONT} が使用されます")
                    st.info("💡 最適な表示にはfonts/フォルダーにNotoSansJP-Regular.ttfを配置してください")
        except:
            pass
        
        try:
            # PDF生成
            generator = PDFReportGenerator()
            pdf_buffer = generator.generate_dashboard_report(
                kpi_data, performance_data, period_info, charts
            )
            
            if pdf_buffer:
                # ファイル名生成
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"手術分析レポート_{period_info.get('period_name', 'report')}_{timestamp}.pdf"
                
                # ダウンロードボタン
                st.download_button(
                    label=button_label,
                    data=pdf_buffer.getvalue(),
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
                
                st.success(f"✅ PDFレポートの準備が完了しました。ボタンをクリックしてダウンロードしてください。")
                
            else:
                st.error("PDFの生成に失敗しました")
                
        except Exception as e:
            st.error(f"PDF生成エラー: {e}")
            logger.error(f"PDF生成エラー: {e}")
    
    @staticmethod
    def create_period_info(period_name: str, start_date, end_date, total_days: int, weekdays: int) -> Dict[str, Any]:
        """期間情報辞書を作成"""
        return {
            'period_name': period_name,
            'start_date': start_date.strftime('%Y/%m/%d') if start_date else 'N/A',
            'end_date': end_date.strftime('%Y/%m/%d') if end_date else 'N/A',
            'total_days': total_days,
            'weekdays': weekdays
        }
    
    @staticmethod
    def check_font_availability() -> Dict[str, Any]:
        """フォントの利用可能性をチェック"""
        result = {
            'fonts_folder_exists': False,
            'available_fonts': [],
            'missing_fonts': [],
            'status': 'error'
        }
        
        try:
            # fontsフォルダーの存在確認
            font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
            result['fonts_folder_exists'] = os.path.exists(font_dir)
            
            if not result['fonts_folder_exists']:
                result['status'] = 'no_fonts_folder'
                return result
            
            # 推奨フォントファイルの確認
            recommended_fonts = [
                'NotoSansJP-Regular.ttf',
                'NotoSansJP-Bold.ttf',
                'NotoSansJP-Light.ttf',
                'NotoSansJP-Medium.ttf'
            ]
            
            for font_file in recommended_fonts:
                font_path = os.path.join(font_dir, font_file)
                if os.path.exists(font_path):
                    result['available_fonts'].append(font_file)
                else:
                    result['missing_fonts'].append(font_file)
            
            # ステータス判定
            if 'NotoSansJP-Regular.ttf' in result['available_fonts']:
                result['status'] = 'excellent' if len(result['available_fonts']) >= 3 else 'good'
            elif len(result['available_fonts']) > 0:
                result['status'] = 'partial'
            else:
                result['status'] = 'no_fonts'
                
        except Exception as e:
            result['error'] = str(e)
            result['status'] = 'error'
        
        return result
    
    @staticmethod  
    def display_font_status():
        """Streamlit上でフォント状況を表示"""
        font_status = StreamlitPDFExporter.check_font_availability()
        
        if font_status['status'] == 'excellent':
            st.success("✅ **フォント設定**: 完璧です！全ての推奨フォントが利用可能")
            st.write(f"利用可能: {', '.join(font_status['available_fonts'])}")
            
        elif font_status['status'] == 'good':
            st.success("✅ **フォント設定**: 良好です")
            st.write(f"利用可能: {', '.join(font_status['available_fonts'])}")
            if font_status['missing_fonts']:
                st.info(f"オプション: {', '.join(font_status['missing_fonts'])}")
                
        elif font_status['status'] == 'partial':
            st.warning("⚠️ **フォント設定**: 一部のフォントが不足")
            st.write(f"利用可能: {', '.join(font_status['available_fonts'])}")
            st.write(f"不足: {', '.join(font_status['missing_fonts'])}")
            st.info("NotoSansJP-Regular.ttf が推奨されます")
            
        elif font_status['status'] == 'no_fonts_folder':
            st.error("❌ **フォント設定**: fonts/フォルダーが見つかりません")
            st.info("プロジェクトルートに fonts/ フォルダーを作成してください")
            
        elif font_status['status'] == 'no_fonts':
            st.error("❌ **フォント設定**: NotoSansJPフォントが見つかりません")
            st.info("fonts/フォルダーにNotoSansJP-Regular.ttfを配置してください")
            
        else:
            st.error("❌ **フォント設定**: チェック中にエラーが発生")
            if 'error' in font_status:
                st.write(f"エラー: {font_status['error']}")
        
        # ダウンロードリンク
        with st.expander("📥 NotoSansJPフォントのダウンロード"):
            st.markdown("""
            **Google Fonts から取得:**
            1. [Google Fonts - Noto Sans Japanese](https://fonts.google.com/noto/specimen/Noto+Sans+JP)
            2. 「Download family」をクリック
            3. ZIPファイルを展開して .ttf ファイルを fonts/ フォルダーに配置
            
            **必須ファイル:**
            - NotoSansJP-Regular.ttf（通常フォント）
            
            **推奨ファイル:**
            - NotoSansJP-Bold.ttf（太字フォント）
            """)
        
        return font_status