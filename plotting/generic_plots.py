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
    
    # 列名を柔軟に対応
    surgeon_col = None
    count_col = None
    
    # 術者名の列を特定
    for col in surgeon_summary.columns:
        if any(keyword in col for keyword in ['術者', 'surgeon', '医師', 'doctor', '実施術者']):
            surgeon_col = col
            break
    
    # 件数の列を特定
    for col in surgeon_summary.columns:
        if any(keyword in col for keyword in ['件数', 'count', '数', 'num']):
            count_col = col
            break
    
    # フォールバック：インデックスまたは最初の列を術者、2番目の列を件数として使用
    if not surgeon_col:
        if surgeon_summary.index.name:
            # インデックスが術者名の場合
            surgeon_col = surgeon_summary.index.name
            top_surgeons = top_surgeons.reset_index()
        elif len(surgeon_summary.columns) > 0:
            surgeon_col = surgeon_summary.columns[0]
    
    if not count_col and len(surgeon_summary.columns) > 1:
        count_col = surgeon_summary.columns[1]
    elif not count_col and len(surgeon_summary.columns) > 0:
        count_col = surgeon_summary.columns[0]
    
    if not surgeon_col or not count_col:
        return go.Figure()
    
    fig = go.Figure(data=go.Bar(
        x=top_surgeons[count_col],
        y=top_surgeons[surgeon_col],
        orientation='h',
        marker_color='lightblue',
        text=top_surgeons[count_col],
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
    
    # データ構造を確認して実績・予測を分離
    if '種別' in result_df.columns:
        # '種別'列で実績・予測を分離
        actual_df = result_df[result_df['種別'] == '実績'].copy()
        forecast_df = result_df[result_df['種別'] == '予測'].copy()
        
        # 日付列を適切に選択（予測データでは'月'列を優先）
        value_col = '値'
        
        # 実績データ用の日付列
        actual_date_col = 'month_start'
        
        # 予測データ用の日付列（'月'列を優先、なければ'month_start'）
        if '月' in forecast_df.columns and forecast_df['月'].notna().any():
            forecast_date_col = '月'
        else:
            forecast_date_col = 'month_start'
        
        # 実績と予測の間に連続性を保つため、実績の最終点を予測の先頭に追加
        if not actual_df.empty and not forecast_df.empty:
            connector = actual_df.tail(1).copy()
            connector['種別'] = '予測'
            
            # 予測データで'月'列を使用する場合、connectorの'月'列も設定
            if forecast_date_col == '月':
                connector['月'] = connector['month_start']
            
            forecast_df = pd.concat([connector, forecast_df], ignore_index=True)
            
    elif 'タイプ' in result_df.columns:
        # 'タイプ'列がある場合の処理（レガシー対応）
        actual_df = result_df[result_df['タイプ'] == '実績'].copy()
        forecast_df = result_df[result_df['タイプ'] == '予測'].copy()
        
        actual_date_col = '月' if '月' in actual_df.columns else 'month_start'
        forecast_date_col = '月' if '月' in forecast_df.columns else 'month_start'
        value_col = '値'
        
    else:
        # 種別列がない場合は、全データを予測として扱う
        actual_df = pd.DataFrame()
        forecast_df = result_df.copy()
        
        actual_date_col = 'month_start'
        forecast_date_col = '月' if '月' in forecast_df.columns else 'month_start'
        value_col = '値' if '値' in result_df.columns else result_df.columns[1]
    
    # 実績データのプロット
    if not actual_df.empty:
        fig.add_trace(go.Scatter(
            x=actual_df[actual_date_col], 
            y=actual_df[value_col], 
            name='実績',
            mode='lines+markers',
            line=dict(color='blue', width=2),
            marker=dict(size=6)
        ))
    
    # 予測データのプロット
    if not forecast_df.empty:
        fig.add_trace(go.Scatter(
            x=forecast_df[forecast_date_col], 
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

def create_forecast_summary_table(result_df, target_dict=None, department=None):
    """
    予測結果のサマリーテーブルを作成
    """
    if result_df.empty or '種別' not in result_df.columns:
        return pd.DataFrame(), pd.DataFrame()
    
    # 実績と予測を分離
    actual_df = result_df[result_df['種別'] == '実績'].copy()
    forecast_df = result_df[result_df['種別'] == '予測'].copy()
    
    # 予測データのみを使用（実績は除外）
    pure_forecast_df = forecast_df[forecast_df.index > 0] if len(forecast_df) > 1 else forecast_df
    
    if actual_df.empty and pure_forecast_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # 年度内の実績累計を計算（月次データを年度で集計）
    actual_total = actual_df['値'].sum() if not actual_df.empty else 0
    
    # 予測値の適切な計算
    # 注意: forecasting.pyから返される値が月平均なのか月総数なのかを確認する必要がある
    forecast_monthly_details = []
    forecast_total = 0
    
    if not pure_forecast_df.empty:
        for _, row in pure_forecast_df.iterrows():
            monthly_value = row['値']
            
            # 月の日付を取得
            if '月' in row and pd.notna(row['月']):
                month_date = pd.to_datetime(row['月'])
                date_str = month_date.strftime('%Y年%m月')
                
                # その月の平日数を計算（手術は通常平日のみ）
                year, month = month_date.year, month_date.month
                # その月の平日数を計算
                month_start = pd.Timestamp(year, month, 1)
                if month == 12:
                    month_end = pd.Timestamp(year + 1, 1, 1) - pd.Timedelta(days=1)
                else:
                    month_end = pd.Timestamp(year, month + 1, 1) - pd.Timedelta(days=1)
                
                # 平日数を計算（pandas.bdate_rangeを使用）
                weekdays_in_month = len(pd.bdate_range(start=month_start, end=month_end))
                
                # 予測値が月平均件数の場合、月総数に変換
                # ここは forecasting.py の実装により調整が必要
                # 仮に月平均と仮定して、平日数を掛ける
                estimated_monthly_total = monthly_value * weekdays_in_month
                
                forecast_monthly_details.append({
                    '予測期間': date_str,
                    '平日数': f"{weekdays_in_month}日",
                    '月平均予測': f"{monthly_value:.1f}件/日", 
                    '月総数予測': f"{estimated_monthly_total:.0f}件"
                })
                
                forecast_total += estimated_monthly_total
            else:
                forecast_monthly_details.append({
                    '予測期間': "不明",
                    '平日数': "不明",
                    '月平均予測': f"{monthly_value:.1f}件/日",
                    '月総数予測': "算出不可"
                })
    
    # 年度合計予測
    year_total_forecast = actual_total + forecast_total
    
    # 目標との比較（年度目標を週次目標から算出）
    annual_target = None
    target_achievement_rate = None
    
    if target_dict and department and department in target_dict:
        weekly_target = target_dict[department]
        annual_target = weekly_target * 52  # 年間52週
        target_achievement_rate = (year_total_forecast / annual_target) * 100 if annual_target > 0 else 0
    
    # サマリーテーブル作成
    summary_data = {
        '項目': [
            '年度内実績累計 (平日)',
            '年度内予測累計 (平日)', 
            '年度合計予測 (平日)',
            '年度目標 (平日ベース)',
            '目標達成率予測'
        ],
        '値': [
            f"{actual_total:.0f}件",
            f"{forecast_total:.0f}件",
            f"{year_total_forecast:.0f}件",
            f"{annual_target:.0f}件" if annual_target else "未設定",
            f"{target_achievement_rate:.1f}%" if target_achievement_rate else "算出不可"
        ],
        '備考': [
            "実績データの月次合計",
            "予測データの月次合計",
            "実績 + 予測の年度合計",
            "週次目標 × 52週",
            "年度合計予測 ÷ 年度目標"
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    monthly_df = pd.DataFrame(forecast_monthly_details)
    
    return summary_df, monthly_df

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