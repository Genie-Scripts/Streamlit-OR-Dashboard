# hospital_monthly_quarterly_plotter.py (凡例修正)
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import style_config as sc # スタイル定義をインポート

def plot_monthly_hospital_graph(summary_df, target_dict):
    """病院全体の月単位データをグラフで表示 (スタイル適用・凡例修正)"""
    fig = go.Figure()

    if summary_df.empty or '平日1日平均件数' not in summary_df.columns or summary_df['平日1日平均件数'].isnull().all():
        fig.update_layout(title="月次データがありません", xaxis_title="月", yaxis_title="平日1日平均件数", **sc.LAYOUT_DEFAULTS)
        return fig

    target_per_day = 21
    period_avg = summary_df['平日1日平均件数'].mean()
    warning_threshold = target_per_day * 0.95

    # 注意ゾーン
    fig.add_trace(go.Scatter(x=summary_df['月'], y=[target_per_day] * len(summary_df), mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=summary_df['月'], y=[warning_threshold] * len(summary_df), mode='lines', line=dict(width=0), fill='tonexty', fillcolor=sc.WARNING_ZONE_FILL, name='注意ゾーン背景', showlegend=False))

    # 実データ
    fig.add_trace(go.Scatter(x=summary_df['月'], y=summary_df['平日1日平均件数'], mode='lines+markers', name='平日1日平均件数', line=dict(color=sc.PRIMARY_COLOR, width=1.5), marker=sc.PRIMARY_MARKER))

    # 移動平均
    ma_6m_col = None; ma_3m_col = None
    if len(summary_df) >= 6:
        ma_6m_col = '6ヶ月移動平均'; summary_df[ma_6m_col] = summary_df['平日1日平均件数'].rolling(window=6, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=summary_df['月'], y=summary_df[ma_6m_col], mode='lines', name=ma_6m_col, line=sc.MOVING_AVERAGE_LINE_STYLE))
    if len(summary_df) >= 3:
        ma_3m_col = '3ヶ月移動平均'; summary_df[ma_3m_col] = summary_df['平日1日平均件数'].rolling(window=3, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=summary_df['月'], y=summary_df[ma_3m_col], mode='lines', name=ma_3m_col, line=dict(color='purple', width=2.0)))

    # 期間平均
    fig.add_trace(go.Scatter(x=summary_df['月'], y=[period_avg] * len(summary_df), mode='lines', name=f'期間平均 ({period_avg:.1f}件/日)', line=sc.AVERAGE_LINE_STYLE))

    # 目標ライン
    fig.add_trace(go.Scatter(x=summary_df['月'], y=[target_per_day] * len(summary_df), mode='lines', name=f"目標 ({target_per_day}件/日)", line=sc.TARGET_LINE_STYLE))

    # アノテーション
    if len(summary_df) > 0:
        # アノテーションの位置を調整 (凡例が右側に来るため)
        fig.add_annotation(x=summary_df['月'].iloc[0], y=(target_per_day + warning_threshold) / 2, text="注意ゾーン", showarrow=False, font=sc.ANNOTATION_FONT, xshift=-50, align="left")

    # Y軸範囲計算
    all_y_values = summary_df['平日1日平均件数'].dropna().tolist()
    if ma_6m_col and ma_6m_col in summary_df: all_y_values.extend(summary_df[ma_6m_col].dropna().tolist())
    if ma_3m_col and ma_3m_col in summary_df: all_y_values.extend(summary_df[ma_3m_col].dropna().tolist())
    all_y_values.extend([target_per_day, warning_threshold, period_avg])
    y_min = np.nanmin(all_y_values) if all_y_values else 0; y_max = np.nanmax(all_y_values) if all_y_values else target_per_day * 1.1
    y_range_margin = (y_max - y_min) * 0.05; y_axis_range = [max(0, y_min - y_range_margin), y_max + y_range_margin]

    # レイアウト
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title="月次全身麻酔手術件数推移 - 病院全体", xaxis_title="月", yaxis_title="平日1日平均件数",
        xaxis=dict(tickformat="%Y-%m", tickangle=-45),
        yaxis=dict(range=y_axis_range),
        # --- 凡例の位置と向きを変更 ---
        legend=dict(
            orientation="v", # 縦並び
            yanchor="top",   # 上端を基準に
            y=1,             # 上端に配置
            xanchor="left",  # 左端を基準に
            x=1.02,          # プロットエリアの右外側に配置
            font=dict(size=sc.LEGEND_FONT_SIZE)
        )
        # --- 凡例修正ここまで ---
    )
    return fig


def plot_quarterly_hospital_graph(summary_df, target_dict):
    """病院全体の四半期単位データをグラフで表示 (スタイル適用)"""
    fig = go.Figure()

    if summary_df.empty or '四半期ラベル' not in summary_df.columns or '平日1日平均件数' not in summary_df.columns or summary_df['平日1日平均件数'].isnull().all():
        fig.update_layout(title="四半期データがありません", xaxis_title="四半期", yaxis_title="平日1日平均件数", **sc.LAYOUT_DEFAULTS)
        return fig

    target_per_day = 21
    period_avg = summary_df['平日1日平均件数'].mean()
    warning_threshold = target_per_day * 0.95

    # 注意ゾーン
    fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[target_per_day] * len(summary_df), mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[warning_threshold] * len(summary_df), mode='lines', line=dict(width=0), fill='tonexty', fillcolor=sc.WARNING_ZONE_FILL, name='注意ゾーン背景', showlegend=False))

    # 実データ (Bar)
    fig.add_trace(go.Bar(x=summary_df['四半期ラベル'], y=summary_df['平日1日平均件数'], name='平日1日平均件数', marker_color=sc.PRIMARY_COLOR, opacity=0.8))

    # 目標ライン
    fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[target_per_day] * len(summary_df), mode='lines', name=f"目標 ({target_per_day}件/日)", line=sc.TARGET_LINE_STYLE))

    # 期間平均
    fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[period_avg] * len(summary_df), mode='lines', name=f'期間平均 ({period_avg:.1f}件/日)', line=sc.AVERAGE_LINE_STYLE))

    # 前年同期比較
    yoy_col = None
    if len(summary_df) >= 5:
        yoy_col = '前年同期平均'; summary_df[yoy_col] = summary_df['平日1日平均件数'].shift(4)
        yoy_data = summary_df.dropna(subset=[yoy_col])
        if not yoy_data.empty:
            fig.add_trace(go.Scatter(x=yoy_data['四半期ラベル'], y=yoy_data[yoy_col], mode='lines+markers', name=yoy_col, line=sc.YOY_LINE_STYLE, marker=sc.YOY_MARKER))

    # アノテーション
    if len(summary_df) > 0:
        fig.add_annotation(x=summary_df['四半期ラベル'].iloc[-1], y=(target_per_day + warning_threshold) / 2, text="注意ゾーン", showarrow=False, font=sc.ANNOTATION_FONT, xshift=50)

    # Y軸範囲計算
    all_y_values_q = summary_df['平日1日平均件数'].dropna().tolist()
    if yoy_col and yoy_col in summary_df.columns: all_y_values_q.extend(summary_df[yoy_col].dropna().tolist())
    all_y_values_q.extend([target_per_day, warning_threshold, period_avg])
    y_min_q = np.nanmin(all_y_values_q) if all_y_values_q else 0; y_max_q = np.nanmax(all_y_values_q) if all_y_values_q else target_per_day * 1.1
    y_range_margin_q = (y_max_q - y_min_q) * 0.05; y_axis_range_q = [max(0, y_min_q - y_range_margin_q), y_max_q + y_range_margin_q]

    # レイアウト
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title="四半期全身麻酔手術件数推移 - 病院全体", xaxis_title="四半期", yaxis_title="平日1日平均件数",
        xaxis=dict(tickangle=-45),
        yaxis=dict(range=y_axis_range_q),
        barmode='overlay',
        # --- 四半期グラフも凡例位置を調整 ---
        legend=dict(
            orientation="v", # 縦並び
            yanchor="top",   # 上端を基準に
            y=1,             # 上端に配置
            xanchor="left",  # 左端を基準に
            x=1.02,          # プロットエリアの右外側に配置
            font=dict(size=sc.LEGEND_FONT_SIZE)
        )
        # --- 凡例修正ここまで ---
    )
    return fig
