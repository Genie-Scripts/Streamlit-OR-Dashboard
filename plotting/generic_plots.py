# plotting/generic_plots.py
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config import style_config as sc

def display_kpi_metrics(kpi_summary):
    """ダッシュボードにKPIカードを表示する"""
    if not kpi_summary:
        st.info("KPIを計算するデータがありません。")
        return

    cols = st.columns(len(kpi_summary))
    for i, (label, value) in enumerate(kpi_summary.items()):
        with cols[i]:
            st.metric(label=label, value=value)

def plot_achievement_ranking(ranking_df, top_n=15):
    """診療科の目標達成率ランキングを横棒グラフで表示"""
    if ranking_df.empty:
        fig = go.Figure()
        return fig.update_layout(title="ランキングデータがありません")

    plot_df = ranking_df.copy().head(top_n)
    plot_df['color'] = plot_df['達成率(%)'].apply(
        lambda x: 'green' if x >= 100 else ('orange' if x >= 80 else 'red')
    )
    plot_df = plot_df.sort_values(by="達成率(%)", ascending=True)

    fig = px.bar(
        plot_df,
        y='診療科',
        x='達成率(%)',
        color='color',
        color_discrete_map=sc.RANKING_COLOR_MAP,
        text='達成率(%)',
        orientation='h',
        title=f"診療科別 目標達成率ランキング (Top {top_n})"
    )
    fig.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
    fig.add_vline(x=100, line=sc.TARGET_LINE_STYLE, annotation_text="目標100%")
    fig.update_layout(showlegend=False, height=max(300, 30 * len(plot_df)), **sc.LAYOUT_DEFAULTS)
    
    return fig

def plot_surgeon_ranking(summary_df, top_n, department_name):
    """術者別ランキングの棒グラフを作成"""
    if summary_df.empty:
        fig = go.Figure()
        return fig.update_layout(title="術者データがありません")

    plot_df = summary_df.head(top_n).sort_values("件数", ascending=True)
    title = f"{department_name} 術者別手術件数 (Top {top_n})"

    fig = px.bar(
        plot_df,
        y='実施術者',
        x='件数',
        orientation='h',
        title=title,
        text='件数'
    )
    fig.update_layout(height=max(300, 30 * len(plot_df)), **sc.LAYOUT_DEFAULTS)
    return fig

def create_forecast_chart(df, title):
    """予測結果と実績を比較するグラフを作成"""
    fig = go.Figure()
    if df.empty:
        return fig.update_layout(title="予測データがありません")

    actual_df = df[df['種別'] == '実績']
    forecast_df = df[df['種別'] == '予測']
    
    # 実績と予測の間に切れ目を作るため、実績の最終点を予測の先頭に追加
    if not actual_df.empty and not forecast_df.empty:
        connector = actual_df.tail(1)
        forecast_df = pd.concat([connector, forecast_df], ignore_index=True)

    fig.add_trace(go.Scatter(x=actual_df['月'], y=actual_df['値'], name='実績', mode='lines+markers', line=dict(color=sc.PRIMARY_COLOR)))
    fig.add_trace(go.Scatter(x=forecast_df['月'], y=forecast_df['値'], name='予測', mode='lines+markers', line=dict(color=sc.PREDICTION_COLOR, dash='dash')))

    fig.update_layout(title=title, xaxis_title="月", yaxis_title="値", **sc.LAYOUT_DEFAULTS)
    return fig


def create_validation_chart(train, test, predictions):
    """モデル検証結果のグラフを作成"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=train.index, y=train, name='訓練データ', mode='lines', line=dict(color=sc.PRIMARY_COLOR)))
    fig.add_trace(go.Scatter(x=test.index, y=test, name='実績値 (検証)', mode='lines+markers', line=dict(color=sc.SECONDARY_COLOR, width=2.5)))

    colors = ['orange', 'firebrick', 'darkorchid']
    for i, (name, pred) in enumerate(predictions.items()):
        fig.add_trace(go.Scatter(x=test.index, y=pred, name=f'予測 ({name})', mode='lines', line=dict(color=colors[i % len(colors)], dash='dash')))

    fig.update_layout(title="予測モデル精度検証", xaxis_title="月", yaxis_title="値", **sc.LAYOUT_DEFAULTS)
    return fig

def plot_cumulative_cases_chart(df, title):
    """累積実績と目標のグラフを作成する"""
    if df.empty or '累積実績' not in df.columns:
        return go.Figure().update_layout(title="累積実績データがありません")
        
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['週'], y=df['累積実績'], name='累積実績', mode='lines+markers', line=dict(color=sc.PRIMARY_COLOR)))
    
    if '累積目標' in df.columns and df['累積目標'].sum() > 0:
        fig.add_trace(go.Scatter(x=df['週'], y=df['累積目標'], name='累積目標', mode='lines', line=sc.TARGET_LINE_STYLE))
        
    fig.update_layout(title=title, xaxis_title="週", yaxis_title="累積件数", **sc.LAYOUT_DEFAULTS)
    return fig