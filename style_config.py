# style_config.py
"""
アプリケーション全体のスタイル定義ファイル
グラフやテーブルの見た目を一元管理します。
"""
import pandas as pd # テーブルフォーマットで使用するためインポート
# style_config.py に追加
import plotly.io as pio

# Plotlyグラフのテンプレート設定
PLOT_TEMPLATE = "plotly_white"  # または "plotly", "plotly_dark", "ggplot2", "seaborn" などから選択

# Plotlyグラフの追加設定
PLOT_CONFIG = {
    "margin": dict(l=50, r=50, t=80, b=50),
    "hovermode": "closest",
    "showlegend": True
}
# --- 色定義 ---
PRIMARY_COLOR = 'royalblue'
SECONDARY_COLOR = 'green'
TARGET_COLOR = 'red'
AVERAGE_LINE_COLOR = 'darkred'
WARNING_ZONE_FILL = 'rgba(255, 165, 0, 0.15)'
ANNOTATION_COLOR = 'black'
PREDICTION_COLOR = 'orange'
PREDICTION_ACTUAL_COLOR = PRIMARY_COLOR
VALIDATION_ACTUAL_COLOR = SECONDARY_COLOR # 検証グラフの実績値
VALIDATION_PRED1_COLOR = PREDICTION_COLOR
VALIDATION_PRED2_COLOR = 'firebrick'
VALIDATION_PRED3_COLOR = 'darkorchid'
YOY_COLOR = 'mediumseagreen'
RANKING_BAR_GREEN = 'rgba(76, 175, 80, 0.8)'
RANKING_BAR_ORANGE = 'rgba(255, 152, 0, 0.8)'
RANKING_BAR_RED = 'rgba(244, 67, 54, 0.8)'
GRID_COLOR = 'rgba(230, 230, 230, 0.7)'
TABLE_HEADER_BG = '#f0f2f6'

# --- 線スタイル定義 (Plotly Go用辞書) ---
TARGET_LINE_STYLE = dict(color=TARGET_COLOR, dash='dot', width=2)
AVERAGE_LINE_STYLE = dict(color=AVERAGE_LINE_COLOR, dash='dashdot', width=1.5)
MOVING_AVERAGE_LINE_STYLE = dict(color=SECONDARY_COLOR, width=2.5)
YOY_LINE_STYLE = dict(color=YOY_COLOR, dash='dot', width=2)
PREDICTION_LINE_STYLE = dict(color=PREDICTION_COLOR, dash='dash', width=2)
PREDICTION_ACTUAL_LINE_STYLE = dict(color=PREDICTION_ACTUAL_COLOR, width=2)
VALIDATION_ACTUAL_LINE_STYLE = dict(color=VALIDATION_ACTUAL_COLOR, width=2.5)
VALIDATION_PRED_LINE_STYLE = dict(dash='dash', width=1.5) # 予測線は共通スタイル

# --- マーカー定義 (Plotly Go用辞書) ---
PRIMARY_MARKER = dict(size=6, color=PRIMARY_COLOR)
YOY_MARKER = dict(size=7, symbol='diamond', color=YOY_COLOR)
PREDICTION_MARKER = dict(size=6, color=PREDICTION_COLOR)
PREDICTION_ACTUAL_MARKER = dict(size=6, color=PREDICTION_ACTUAL_COLOR)
VALIDATION_ACTUAL_MARKER = dict(size=7, color=VALIDATION_ACTUAL_COLOR)
VALIDATION_PRED_MARKER = dict(size=6) # 予測マーカーは色を線に合わせる

# --- フォント定義 ---
ANNOTATION_FONT = dict(color=ANNOTATION_COLOR, size=12)
TITLE_FONT_SIZE = 16
AXIS_LABEL_FONT_SIZE = 12
TICK_FONT_SIZE = 11
LEGEND_FONT_SIZE = 11
TABLE_FONT_SIZE = "12px"

# --- レイアウト共通設定 (Plotly Go用辞書) ---
LAYOUT_DEFAULTS = dict(
    margin=dict(l=50, r=30, t=70, b=50),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=LEGEND_FONT_SIZE)
    ),
    title_font=dict(size=TITLE_FONT_SIZE),
    xaxis=dict(
        title_font=dict(size=AXIS_LABEL_FONT_SIZE),
        tickfont=dict(size=TICK_FONT_SIZE),
        showgrid=True,
        gridcolor=GRID_COLOR
        ),
    yaxis=dict(
        title_font=dict(size=AXIS_LABEL_FONT_SIZE),
        tickfont=dict(size=TICK_FONT_SIZE),
        showgrid=True,
        gridcolor=GRID_COLOR
        )
)

# --- ランキンググラフ用 (Plotly Express用) ---
RANKING_COLOR_MAP = {
    'green': RANKING_BAR_GREEN,
    'orange': RANKING_BAR_ORANGE,
    'red': RANKING_BAR_RED
}

# --- テーブルスタイル (Streamlit DataFrame Styler用) ---
TABLE_STYLE_PROPS = [
    {'selector': 'th', 'props': [
        ('background-color', TABLE_HEADER_BG),
        ('font-weight', 'bold'),
        ('text-align', 'center'),
        ('font-size', TABLE_FONT_SIZE)
        ]},
    {'selector': 'td', 'props': [
        ('text-align', 'right'),
        ('font-size', TABLE_FONT_SIZE)
        ]},
    # 左端の列（診療科など）だけ左揃えにする場合 (オプション)
    # {'selector': 'td:first-child, th:first-child', 'props': [('text-align', 'left')]}
]

# --- テーブル数値フォーマット (共通) ---
TABLE_COMMON_FORMAT_DICT = {
    # 日付・期間
    "週": lambda t: t.strftime("%Y-%m-%d") if pd.notna(t) else "",
    "月": lambda t: t.strftime("%Y年%m月") if pd.notna(t) else "",
    "四半期": lambda t: t.strftime("%Y-%m-%d") if pd.notna(t) else "",
    "四半期ラベル": "{:}".format,
    "期間": "{:}".format,
    # 件数・日数
    "全日件数": "{:,.0f}", # カンマ区切り追加
    "平日件数": "{:,.0f}",
    "平日日数": "{:,.0f}",
    "週合計件数": "{:,.0f}",
    "月合計件数": "{:,.0f}",
    "四半期合計件数": "{:,.0f}",
    "実績件数": "{:,.0f}",
    "年度実績件数": "{:,.0f}",
    "年度予測件数": "{:,.0f}",
    "年度合計予測": "{:,.0f}",
    "診療科数": "{:,.0f}",
    # 平均・目標
    "平日1日平均件数": "{:.1f}",
    "期間内目標件数": "{:.1f}",
    "目標件数/週": "{:.1f}",
    "実績平均": "{:.1f}",
    "予測平均": "{:.1f}",
    "実績月平均": "{:.1f}",
    "予測月平均": "{:.1f}",
    "前年同期平均": "{:.1f}",
    "前年同期件数": "{:,.0f}",
    # 率・誤差
    "達成率(%)": "{:.1f}%",
    "目標達成率予測": "{:.1f}%",
    "変化率(%)": "{:.1f}%",
    "割合(%)": "{:.1f}%",
    "MAE": "{:.2f}",
    "RMSE": "{:.2f}",
    "MAPE(%)": "{:.1f}%",
    # 移動平均 (共通プレフィックスで対応)
    "移動平均_2週": "{:.1f}", "移動平均_3ヶ月": "{:.1f}",
    "移動平均_4週": "{:.1f}", "6ヶ月移動平均": "{:.1f}",
    "移動平均_8週": "{:.1f}",
    "移動平均_12週": "{:.1f}",
    # その他
    "値": "{:}".format, # 指標表示用
}