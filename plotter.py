# plotter.py
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import style_config as sc # スタイル定義をインポート

def plot_summary_graph(summary_df, selected_department, target_dict, moving_avg_period=4):
    """病院全体の週単位データをグラフで表示 (スタイル適用)"""
    fig = go.Figure()

    if summary_df.empty or '平日1日平均件数' not in summary_df.columns or summary_df['平日1日平均件数'].isnull().all():
        fig.update_layout(title="週次データがありません", xaxis_title="週", yaxis_title="平日1日平均件数", **sc.LAYOUT_DEFAULTS)
        return fig

    period_avg = summary_df['平日1日平均件数'].mean()
    target_value = 21
    warning_threshold = target_value * 0.95

    # 注意ゾーン
    fig.add_trace(go.Scatter(x=summary_df['週'], y=[target_value] * len(summary_df), mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=summary_df['週'], y=[warning_threshold] * len(summary_df), mode='lines', line=dict(width=0), fill='tonexty', fillcolor=sc.WARNING_ZONE_FILL, name='注意ゾーン背景', showlegend=False))

    # 実データ
    fig.add_trace(go.Scatter(x=summary_df['週'], y=summary_df['平日1日平均件数'], mode='lines+markers', name='平日1日平均件数', line=dict(color=sc.PRIMARY_COLOR, width=1.5), marker=sc.PRIMARY_MARKER))

    # 移動平均
    moving_avg_col = None
    if moving_avg_period > 0 and len(summary_df) >= moving_avg_period:
        moving_avg_col = f'移動平均_{moving_avg_period}週'
        actual_window = min(moving_avg_period, len(summary_df))
        summary_df[moving_avg_col] = summary_df['平日1日平均件数'].rolling(window=actual_window, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=summary_df['週'], y=summary_df[moving_avg_col], mode='lines', name=f'{moving_avg_period}週移動平均', line=sc.MOVING_AVERAGE_LINE_STYLE))

    # 期間平均
    fig.add_trace(go.Scatter(x=summary_df['週'], y=[period_avg] * len(summary_df), mode='lines', name=f'期間平均 ({period_avg:.1f}件/日)', line=sc.AVERAGE_LINE_STYLE))

    # 目標ライン
    fig.add_trace(go.Scatter(x=summary_df['週'], y=[target_value] * len(summary_df), mode='lines', name=f"目標 ({target_value}件/日)", line=sc.TARGET_LINE_STYLE))

    # アノテーション
    if len(summary_df) > 0:
        fig.add_annotation(x=summary_df['週'].iloc[-1], y=(target_value + warning_threshold) / 2, text="注意ゾーン", showarrow=False, font=sc.ANNOTATION_FONT, xshift=50)

    # Y軸範囲計算
    all_y_values = summary_df['平日1日平均件数'].dropna().tolist()
    if moving_avg_col and moving_avg_col in summary_df.columns: all_y_values.extend(summary_df[moving_avg_col].dropna().tolist())
    all_y_values.extend([target_value, warning_threshold, period_avg])
    y_min = np.nanmin(all_y_values) if all_y_values else 0; y_max = np.nanmax(all_y_values) if all_y_values else target_value * 1.1 # nanmin/max使用
    y_range_margin = (y_max - y_min) * 0.05; y_axis_range = [max(0, y_min - y_range_margin), y_max + y_range_margin] # 最小値は0以下にならないように

    # レイアウト
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title=f"全身麻酔手術件数推移 - 病院全体 (週単位)",
        xaxis_title="週 (月曜日開始)", yaxis_title="平日1日平均件数",
        yaxis=dict(range=y_axis_range)
    )
    return fig

def plot_department_graph(summary_df, selected_department, target_dict, moving_avg_period=4):
    """診療科別の週単位データをグラフで表示 (スタイル適用)"""
    fig = go.Figure()

    if summary_df.empty or '週合計件数' not in summary_df.columns or summary_df['週合計件数'].isnull().all():
        fig.update_layout(title=f"{selected_department} - 週次データがありません", xaxis_title="週", yaxis_title="週合計件数", **sc.LAYOUT_DEFAULTS)
        return fig

    target_value = None; warning_threshold = None
    if selected_department in target_dict:
        target_value = target_dict[selected_department]; warning_threshold = target_value * 0.95
        # 注意ゾーン
        fig.add_trace(go.Scatter(x=summary_df['週'], y=[target_value] * len(summary_df), mode='lines', line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=summary_df['週'], y=[warning_threshold] * len(summary_df), mode='lines', line=dict(width=0), fill='tonexty', fillcolor=sc.WARNING_ZONE_FILL, name='注意ゾーン背景', showlegend=False))
        if len(summary_df) > 0:
            fig.add_annotation(x=summary_df['週'].iloc[-1], y=(target_value + warning_threshold) / 2, text="注意ゾーン", showarrow=False, font=sc.ANNOTATION_FONT, xshift=50)

    # 実データ
    fig.add_trace(go.Scatter(x=summary_df['週'], y=summary_df['週合計件数'], mode='lines+markers', name='週合計件数', line=dict(color=sc.PRIMARY_COLOR, width=1.5), marker=sc.PRIMARY_MARKER))

    # 移動平均
    moving_avg_col = None
    if moving_avg_period > 0 and len(summary_df) >= moving_avg_period:
        moving_avg_col = f'移動平均_{moving_avg_period}週'
        actual_window = min(moving_avg_period, len(summary_df))
        summary_df[moving_avg_col] = summary_df['週合計件数'].rolling(window=actual_window, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=summary_df['週'], y=summary_df[moving_avg_col], mode='lines', name=f'{moving_avg_period}週移動平均', line=sc.MOVING_AVERAGE_LINE_STYLE))

    # 期間平均
    period_avg_dept = summary_df['週合計件数'].mean()
    fig.add_trace(go.Scatter(x=summary_df['週'], y=[period_avg_dept] * len(summary_df), mode='lines', name=f'期間平均 ({period_avg_dept:.1f}件/週)', line=sc.AVERAGE_LINE_STYLE))

    # 目標ライン
    if target_value is not None:
        fig.add_trace(go.Scatter(x=summary_df['週'], y=[target_value] * len(summary_df), mode='lines', name=f"目標 ({target_value:.1f}件/週)", line=sc.TARGET_LINE_STYLE))

    # Y軸範囲計算
    all_y_values_d = summary_df['週合計件数'].dropna().tolist()
    if moving_avg_col and moving_avg_col in summary_df.columns: all_y_values_d.extend(summary_df[moving_avg_col].dropna().tolist())
    if target_value is not None: all_y_values_d.extend([target_value, warning_threshold])
    all_y_values_d.append(period_avg_dept)
    y_min_d = np.nanmin(all_y_values_d) if all_y_values_d else 0; y_max_d = np.nanmax(all_y_values_d) if all_y_values_d else (target_value * 1.1 if target_value is not None else 10)
    y_range_margin_d = (y_max_d - y_min_d) * 0.05; y_axis_range_d = [max(0, y_min_d - y_range_margin_d), y_max_d + y_range_margin_d]

    # レイアウト
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        title=f"全身麻酔手術件数推移 - {selected_department} (週単位)",
        xaxis_title="週 (月曜日開始)", yaxis_title="週合計件数",
        yaxis=dict(range=y_axis_range_d)
    )
    return fig