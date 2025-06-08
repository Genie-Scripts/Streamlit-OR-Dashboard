# plotting/generic_plots.py (修正版)
import streamlit as st
import pandas as pd  # 追加：pandasのインポート
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

def display_kpi_metrics(kpi_summary):
    """
    KPIサマリーをStreamlitで表示する
    """
    if not kpi_summary:
        st.warning("KPIデータがありません")
        return
    
    # カード形式でKPIを表示
    cols = st.columns(len(kpi_summary))
    
    for i, (key, value) in enumerate(kpi_summary.items()):
        with cols[i]:
            st.metric(
                label=key,
                value=value
            )

def plot_achievement_ranking(ranking_data):
    """
    診療科別達成率ランキングのグラフを作成
    """
    if ranking_data.empty:
        return go.Figure()
    
    # 達成率でソート
    sorted_data = ranking_data.sort_values('達成率(%)', ascending=True)
    
    # 色の設定
    colors = ['#dc3545' if x < 80 else '#ffc107' if x < 100 else '#28a745' 
              for x in sorted_data['達成率(%)']]
    
    fig = go.Figure(data=go.Bar(
        x=sorted_data['達成率(%)'],
        y=sorted_data['診療科'],
        orientation='h',
        marker_color=colors,
        text=[f"{x:.1f}%" for x in sorted_data['達成率(%)']],
        textposition='outside'
    ))
    
    fig.update_layout(
        title="診療科別 目標達成率ランキング",
        xaxis_title="達成率 (%)",
        yaxis_title="診療科",
        height=max(400, len(sorted_data) * 30),
        showlegend=False
    )
    
    # 達成率100%のライン
    fig.add_vline(x=100, line_dash="dash", line_color="green", 
                  annotation_text="目標達成ライン")
    
    return fig

def plot_surgeon_ranking(surgeon_summary, top_n, department_name):
    """
    術者別件数ランキングのグラフを作成
    """
    if surgeon_summary.empty:
        return go.Figure()
    
    # 上位N人を選択
    top_surgeons = surgeon_summary.head(top_n)
    
    fig = go.Figure(data=go.Bar(
        x=top_surgeons['件数'],
        y=top_surgeons['術者名'],
        orientation='h',
        marker_color='lightblue',
        text=top_surgeons['件数'],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=f"{department_name} 術者別件数ランキング (Top {top_n})",
        xaxis_title="手術件数",
        yaxis_title="術者名",
        height=max(400, len(top_surgeons) * 25),
        yaxis={'categoryorder':'total ascending'}
    )
    
    return fig

def create_forecast_chart(result_df, title):
    """
    予測結果のグラフを作成
    """
    if result_df.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    # データ構造を確認
    if '種別' in result_df.columns:
        # 種別列を使って実績・予測を分離
        actual_df = result_df[result_df['種別'] == '実績'].copy()
        forecast_df = result_df[result_df['種別'] == '予測'].copy()
        
        # 日付列と値列を特定
        date_col = 'month_start'
        value_col = '値'
        
        # 実績と予測の間に連続性を保つため、実績の最終点を予測の先頭に追加
        if not actual_df.empty and not forecast_df.empty:
            connector = actual_df.tail(1).copy()
            connector['種別'] = '予測'  # 種別を予測に変更
            forecast_df = pd.concat([connector, forecast_df], ignore_index=True)
        
    elif 'タイプ' in result_df.columns:
        # タイプ列がある場合の処理（従来の処理）
        actual_df = result_df[result_df['タイプ'] == '実績'].copy()
        forecast_df = result_df[result_df['タイプ'] == '予測'].copy()
        
        # 列名を推定
        date_col = '月' if '月' in result_df.columns else result_df.columns[0]
        value_col = '値' if '値' in result_df.columns else result_df.columns[1]
        
    else:
        # 種別列がない場合は、全データを予測として扱う
        actual_df = pd.DataFrame()
        forecast_df = result_df.copy()
        
        # 列名を推定
        date_col = result_df.columns[0]
        value_col = '値' if '値' in result_df.columns else result_df.columns[1]
    
    # 実績データのプロット
    if not actual_df.empty:
        fig.add_trace(go.Scatter(
            x=actual_df[date_col], 
            y=actual_df[value_col], 
            name='実績',
            mode='lines+markers',
            line=dict(color='blue', width=2),
            marker=dict(size=6)
        ))
    
    # 予測データのプロット
    if not forecast_df.empty:
        fig.add_trace(go.Scatter(
            x=forecast_df[date_col], 
            y=forecast_df[value_col], 
            name='予測',
            mode='lines+markers',
            line=dict(color='red', width=2, dash='dash'),
            marker=dict(size=6)
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="期間",
        yaxis_title="手術件数",
        height=500,
        showlegend=True,
        legend=dict(x=0.02, y=0.98)
    )
    
    return fig

def create_validation_chart(train_data, test_data, predictions):
    """
    モデル検証結果のグラフを作成
    """
    fig = go.Figure()
    
    # 訓練データ
    if not train_data.empty:
        fig.add_trace(go.Scatter(
            x=train_data.index,
            y=train_data.values,
            name='訓練データ',
            mode='lines+markers',
            line=dict(color='blue', width=2)
        ))
    
    # テストデータ（実績）
    if not test_data.empty:
        fig.add_trace(go.Scatter(
            x=test_data.index,
            y=test_data.values,
            name='テストデータ（実績）',
            mode='lines+markers',
            line=dict(color='green', width=2)
        ))
    
    # 予測データ
    for model_name, pred_data in predictions.items():
        if not pred_data.empty:
            fig.add_trace(go.Scatter(
                x=pred_data.index,
                y=pred_data.values,
                name=f'予測（{model_name}）',
                mode='lines+markers',
                line=dict(width=2, dash='dash')
            ))
    
    fig.update_layout(
        title="モデル検証結果",
        xaxis_title="期間",
        yaxis_title="手術件数",
        height=500,
        showlegend=True
    )
    
    return fig

def plot_cumulative_cases_chart(cumulative_data, title):
    """
    累積実績のグラフを作成
    """
    if cumulative_data.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    # 累積実績
    fig.add_trace(go.Scatter(
        x=cumulative_data['週'],
        y=cumulative_data['累積実績'],
        name='累積実績',
        mode='lines+markers',
        line=dict(color='blue', width=3),
        marker=dict(size=6)
    ))
    
    # 累積目標
    fig.add_trace(go.Scatter(
        x=cumulative_data['週'],
        y=cumulative_data['累積目標'],
        name='累積目標',
        mode='lines',
        line=dict(color='red', width=2, dash='dash')
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="週",
        yaxis_title="累積手術件数",
        height=500,
        showlegend=True,
        legend=dict(x=0.02, y=0.98)
    )
    
    return fig