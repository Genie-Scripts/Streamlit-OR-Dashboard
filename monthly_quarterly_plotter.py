# monthly_quarterly_plotter.py
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import style_config as sc # スタイル定義をインポート

def plot_monthly_department_graph(summary_df, selected_department, target_dict):
    """診療科の月単位データをグラフで表示 (スタイル適用)"""
    fig = go.Figure()

    if summary_df.empty or '月合計件数' not in summary_df.columns or summary_df['月合計件数'].isnull().all():
        fig.update_layout(title=f"{selected_department} - 月次データがありません", xaxis_title="月", yaxis_title="月合計件数", **sc.LAYOUT_DEFAULTS)
        return fig

    target_value = None; warning_threshold = None
    if selected_department in target_dict:
        weekly_target = target_dict[selected_department]; target_value = weekly_target * 4.3; warning_threshold = target_value * 0.95
        # 注意ゾーン
        fig.add_trace(go.Scatter(x=summary_df['月'], y=[target_value] * len(summary_df), mode='lines', line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=summary_df['月'], y=[warning_threshold] * len(summary_df), mode='lines', line=dict(width=0), fill='tonexty', fillcolor=sc.WARNING_ZONE_FILL, name='注意ゾーン背景', showlegend=False))
        if len(summary_df) > 0:
            fig.add_annotation(x=summary_df['月'].iloc[-1], y=(target_value + warning_threshold) / 2, text="注意ゾーン", showarrow=False, font=sc.ANNOTATION_FONT, xshift=50)

    # 実データ
    fig.add_trace(go.Scatter(x=summary_df['月'], y=summary_df['月合計件数'], mode='lines+markers', name='月合計件数', line=dict(color=sc.PRIMARY_COLOR, width=1.5), marker=sc.PRIMARY_MARKER))

    # 移動平均
    ma_6m_col = None; ma_3m_col = None
    if len(summary_df) >= 6:
        ma_6m_col = '6ヶ月移動平均'; summary_df[ma_6m_col] = summary_df['月合計件数'].rolling(window=6, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=summary_df['月'], y=summary_df[ma_6m_col], mode='lines', name=ma_6m_col, line=sc.MOVING_AVERAGE_LINE_STYLE))
    if len(summary_df) >= 3:
        ma_3m_col = '3ヶ月移動平均'; summary_df[ma_3m_col] = summary_df['月合計件数'].rolling(window=3, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=summary_df['月'], y=summary_df[ma_3m_col], mode='lines', name=ma_3m_col, line=dict(color='purple', width=2.0)))

    # 期間平均
    period_avg = summary_df['月合計件数'].mean()
    fig.add_trace(go.Scatter(x=summary_df['月'], y=[period_avg] * len(summary_df), mode='lines', name=f'期間平均 ({period_avg:.1f}件/月)', line=sc.AVERAGE_LINE_STYLE))

    # 目標ライン
    if target_value is not None:
        fig.add_trace(go.Scatter(x=summary_df['月'], y=[target_value] * len(summary_df), mode='lines', name=f"目標 ({target_value:.1f}件/月)", line=sc.TARGET_LINE_STYLE))

    # Y軸範囲計算
    all_y_values = summary_df['月合計件数'].dropna().tolist()
    if ma_6m_col and ma_6m_col in summary_df: all_y_values.extend(summary_df[ma_6m_col].dropna().tolist())
    if ma_3m_col and ma_3m_col in summary_df: all_y_values.extend(summary_df[ma_3m_col].dropna().tolist())
    if target_value is not None: all_y_values.extend([target_value, warning_threshold])
    all_y_values.append(period_avg)
    y_min = np.nanmin(all_y_values) if all_y_values else 0; y_max = np.nanmax(all_y_values) if all_y_values else (target_value * 1.1 if target_value is not None else 10)
    y_range_margin = (y_max - y_min) * 0.05; y_axis_range = [max(0, y_min - y_range_margin), y_max + y_range_margin]

    # レイアウト
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title=f"月次全身麻酔手術件数推移 - {selected_department}", xaxis_title="月", yaxis_title="月合計件数",
        xaxis=dict(tickformat="%Y-%m", tickangle=-45),
        yaxis=dict(range=y_axis_range)
    )
    return fig

def plot_quarterly_department_graph(summary_df, selected_department, target_dict):
    """診療科の四半期単位データをグラフで表示 (スタイル適用)"""
    fig = go.Figure()

    if summary_df.empty or '四半期ラベル' not in summary_df.columns or '四半期合計件数' not in summary_df.columns or summary_df['四半期合計件数'].isnull().all():
        fig.update_layout(title=f"{selected_department} - 四半期データがありません", xaxis_title="四半期", yaxis_title="四半期合計件数", **sc.LAYOUT_DEFAULTS)
        return fig

    target_value = None; warning_threshold = None
    if selected_department in target_dict:
        weekly_target = target_dict[selected_department]; target_value = weekly_target * 13; warning_threshold = target_value * 0.95
        # 注意ゾーン
        fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[target_value] * len(summary_df), mode='lines', line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[warning_threshold] * len(summary_df), mode='lines', line=dict(width=0), fill='tonexty', fillcolor=sc.WARNING_ZONE_FILL, name='注意ゾーン背景', showlegend=False))
        if len(summary_df) > 0:
            fig.add_annotation(x=summary_df['四半期ラベル'].iloc[-1], y=(target_value + warning_threshold) / 2, text="注意ゾーン", showarrow=False, font=sc.ANNOTATION_FONT, xshift=50)

    # 実データ (Bar)
    fig.add_trace(go.Bar(x=summary_df['四半期ラベル'], y=summary_df['四半期合計件数'], name='四半期合計件数', marker_color=sc.PRIMARY_COLOR, opacity=0.8))

    # 目標ライン
    if target_value is not None:
        fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[target_value] * len(summary_df), mode='lines', name=f"目標 ({target_value:.1f}件/四半期)", line=sc.TARGET_LINE_STYLE))

    # 期間平均
    period_avg = summary_df['四半期合計件数'].mean()
    fig.add_trace(go.Scatter(x=summary_df['四半期ラベル'], y=[period_avg] * len(summary_df), mode='lines', name=f'期間平均 ({period_avg:.1f}件/四半期)', line=sc.AVERAGE_LINE_STYLE))

    # 前年同期比較
    yoy_col = None
    if len(summary_df) >= 5:
        yoy_col = '前年同期件数'; summary_df[yoy_col] = summary_df['四半期合計件数'].shift(4)
        yoy_data = summary_df.dropna(subset=[yoy_col])
        if not yoy_data.empty:
            fig.add_trace(go.Scatter(x=yoy_data['四半期ラベル'], y=yoy_data[yoy_col], mode='lines+markers', name=yoy_col, line=sc.YOY_LINE_STYLE, marker=sc.YOY_MARKER))

    # Y軸範囲計算
    all_y_values_q = summary_df['四半期合計件数'].dropna().tolist()
    if yoy_col and yoy_col in summary_df.columns: all_y_values_q.extend(summary_df[yoy_col].dropna().tolist())
    if target_value is not None: all_y_values_q.extend([target_value, warning_threshold])
    all_y_values_q.append(period_avg)
    y_min_q = np.nanmin(all_y_values_q) if all_y_values_q else 0; y_max_q = np.nanmax(all_y_values_q) if all_y_values_q else (target_value * 1.1 if target_value is not None else 10)
    y_range_margin_q = (y_max_q - y_min_q) * 0.05; y_axis_range_q = [max(0, y_min_q - y_range_margin_q), y_max_q + y_range_margin_q]

    # レイアウト
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title=f"四半期全身麻酔手術件数推移 - {selected_department}", xaxis_title="四半期", yaxis_title="四半期合計件数",
        xaxis=dict(tickangle=-45),
        yaxis=dict(range=y_axis_range_q),
        barmode='overlay'
    )
    return fig