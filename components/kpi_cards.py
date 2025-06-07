"""
📊 KPIカードコンポーネント

ダッシュボード用のKPI表示カードを生成するモジュール。
メトリクス、トレンド、比較データを視覚的に表示します。
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Union, Optional, Dict, List, Any
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px

class KPICard:
    """KPIカードクラス"""
    
    def __init__(self):
        pass
    
    def render_metric_card(
        self,
        title: str,
        value: Union[int, float, str],
        delta: Optional[Union[int, float]] = None,
        delta_color: str = "normal",
        help_text: Optional[str] = None,
        prefix: str = "",
        suffix: str = "",
        format_value: bool = True
    ):
        """
        基本的なメトリクスカードを表示
        
        Args:
            title: カードのタイトル
            value: 表示する値
            delta: 変化量
            delta_color: 変化量の色 ("normal", "inverse")
            help_text: ヘルプテキスト
            prefix: 値の前に付ける文字
            suffix: 値の後に付ける文字
            format_value: 値をフォーマットするかどうか
        """
        
        # 値のフォーマット
        if format_value and isinstance(value, (int, float)):
            if value >= 1000000:
                formatted_value = f"{value/1000000:.1f}M"
            elif value >= 1000:
                formatted_value = f"{value/1000:.1f}K"
            else:
                formatted_value = f"{value:,.0f}" if isinstance(value, int) else f"{value:,.2f}"
        else:
            formatted_value = str(value)
        
        # メトリクス表示
        st.metric(
            label=title,
            value=f"{prefix}{formatted_value}{suffix}",
            delta=delta,
            delta_color=delta_color,
            help=help_text
        )
    
    def render_kpi_grid(self, kpis: List[Dict[str, Any]], columns: int = 4):
        """
        KPIのグリッド表示
        
        Args:
            kpis: KPIデータのリスト
            columns: 列数
        """
        
        # グリッドレイアウト
        cols = st.columns(columns)
        
        for i, kpi in enumerate(kpis):
            col_index = i % columns
            with cols[col_index]:
                self.render_metric_card(**kpi)
    
    def render_trend_card(
        self,
        title: str,
        data: pd.Series,
        trend_period: int = 7,
        show_sparkline: bool = True,
        height: int = 150
    ):
        """
        トレンド付きKPIカードを表示
        
        Args:
            title: カードのタイトル
            data: 時系列データ
            trend_period: トレンド計算期間
            show_sparkline: スパークラインを表示するかどうか
            height: カードの高さ
        """
        
        if len(data) == 0:
            st.warning(f"{title}: データがありません")
            return
        
        # 現在値と変化量を計算
        current_value = data.iloc[-1]
        
        if len(data) >= trend_period:
            previous_value = data.iloc[-trend_period]
            delta = current_value - previous_value
            delta_percent = (delta / previous_value * 100) if previous_value != 0 else 0
        else:
            delta = None
            delta_percent = 0
        
        # コンテナ作成
        with st.container():
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # メトリクス表示
                delta_text = f"{delta:+.0f} ({delta_percent:+.1f}%)" if delta is not None else None
                self.render_metric_card(
                    title=title,
                    value=current_value,
                    delta=delta_text,
                    format_value=True
                )
            
            with col2:
                if show_sparkline and len(data) > 1:
                    # スパークライン作成
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            y=data.values,
                            mode='lines',
                            line=dict(color='#1f77b4', width=2),
                            fill='tonexty',
                            fillcolor='rgba(31, 119, 180, 0.1)'
                        )
                    )
                    
                    # レイアウト調整
                    fig.update_layout(
                        height=height,
                        margin=dict(l=0, r=0, t=0, b=0),
                        showlegend=False,
                        xaxis=dict(visible=False),
                        yaxis=dict(visible=False),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    def render_comparison_card(
        self,
        title: str,
        current_value: Union[int, float],
        target_value: Union[int, float],
        benchmark_value: Optional[Union[int, float]] = None,
        show_progress: bool = True
    ):
        """
        比較データ付きKPIカードを表示
        
        Args:
            title: カードのタイトル
            current_value: 現在値
            target_value: 目標値
            benchmark_value: ベンチマーク値
            show_progress: プログレスバーを表示するかどうか
        """
        
        with st.container():
            # タイトル
            st.markdown(f"**{title}**")
            
            # 現在値表示
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("現在値", f"{current_value:,.0f}")
            
            with col2:
                st.metric("目標値", f"{target_value:,.0f}")
                
            with col3:
                if benchmark_value is not None:
                    st.metric("ベンチマーク", f"{benchmark_value:,.0f}")
            
            # 達成率計算
            achievement_rate = (current_value / target_value) if target_value != 0 else 0
            
            # プログレスバー
            if show_progress:
                progress_color = "green" if achievement_rate >= 1.0 else "orange" if achievement_rate >= 0.8 else "red"
                st.progress(min(achievement_rate, 1.0))
                st.caption(f"達成率: {achievement_rate:.1%}")
            
            # ベンチマーク比較
            if benchmark_value is not None:
                benchmark_ratio = (current_value / benchmark_value) if benchmark_value != 0 else 0
                benchmark_text = "上回る" if benchmark_ratio > 1.0 else "下回る"
                st.caption(f"ベンチマーク比: {benchmark_ratio:.1%} ({benchmark_text})")
    
    def render_category_kpi_grid(
        self,
        data: pd.DataFrame,
        category_col: str,
        value_col: str,
        title: str = "カテゴリ別KPI",
        max_categories: int = 8
    ):
        """
        カテゴリ別KPIグリッドを表示
        
        Args:
            data: データフレーム
            category_col: カテゴリ列名
            value_col: 値列名
            title: タイトル
            max_categories: 最大表示カテゴリ数
        """
        
        st.markdown(f"### {title}")
        
        # カテゴリ別集計
        category_stats = data.groupby(category_col)[value_col].agg(['sum', 'mean', 'count']).reset_index()
        category_stats = category_stats.sort_values('sum', ascending=False).head(max_categories)
        
        # グリッド表示
        cols = st.columns(min(4, len(category_stats)))
        
        for i, row in category_stats.iterrows():
            col_index = i % len(cols)
            with cols[col_index]:
                category = row[category_col]
                total = row['sum']
                avg = row['mean']
                count = row['count']
                
                st.markdown(f"**{category}**")
                st.metric("合計", f"{total:,.0f}")
                st.metric("平均", f"{avg:,.1f}")
                st.metric("件数", f"{count:,.0f}")
    
    def render_time_series_kpi(
        self,
        data: pd.DataFrame,
        date_col: str,
        value_col: str,
        title: str = "時系列KPI",
        period: str = "daily",
        show_forecast: bool = False
    ):
        """
        時系列KPIカードを表示
        
        Args:
            data: データフレーム
            date_col: 日付列名
            value_col: 値列名
            title: タイトル
            period: 集計期間 ("daily", "weekly", "monthly")
            show_forecast: 予測表示フラグ
        """
        
        st.markdown(f"### {title}")
        
        # 日付列の型変換
        data = data.copy()
        data[date_col] = pd.to_datetime(data[date_col])
        
        # 期間別集計
        if period == "daily":
            time_series = data.groupby(data[date_col].dt.date)[value_col].sum()
        elif period == "weekly":
            time_series = data.groupby(data[date_col].dt.to_period('W'))[value_col].sum()
        elif period == "monthly":
            time_series = data.groupby(data[date_col].dt.to_period('M'))[value_col].sum()
        
        # KPIメトリクス計算
        total = time_series.sum()
        mean = time_series.mean()
        trend = "上昇" if len(time_series) > 1 and time_series.iloc[-1] > time_series.iloc[-2] else "下降"
        
        # メトリクス表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("総計", f"{total:,.0f}")
        
        with col2:
            st.metric("平均", f"{mean:,.1f}")
        
        with col3:
            if len(time_series) > 1:
                latest_change = time_series.iloc[-1] - time_series.iloc[-2]
                st.metric("前期比", f"{latest_change:+.0f}")
        
        with col4:
            st.metric("トレンド", trend)
        
        # チャート表示
        fig = px.line(
            x=time_series.index,
            y=time_series.values,
            title=f"{title} - {period.title()} Trend"
        )
        
        fig.update_layout(
            height=300,
            xaxis_title="期間",
            yaxis_title=value_col
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_distribution_kpi(
        self,
        data: pd.Series,
        title: str = "分布KPI",
        show_percentiles: bool = True
    ):
        """
        分布統計KPIカードを表示
        
        Args:
            data: データシリーズ
            title: タイトル
            show_percentiles: パーセンタイル表示フラグ
        """
        
        st.markdown(f"### {title}")
        
        # 基本統計量
        stats = data.describe()
        
        # メトリクス表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("平均", f"{stats['mean']:,.2f}")
        
        with col2:
            st.metric("中央値", f"{stats['50%']:,.2f}")
        
        with col3:
            st.metric("標準偏差", f"{stats['std']:,.2f}")
        
        with col4:
            st.metric("件数", f"{stats['count']:,.0f}")
        
        if show_percentiles:
            # パーセンタイル表示
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("25%", f"{stats['25%']:,.2f}")
            
            with col2:
                st.metric("75%", f"{stats['75%']:,.2f}")
            
            with col3:
                st.metric("最小値", f"{stats['min']:,.2f}")
            
            with col4:
                st.metric("最大値", f"{stats['max']:,.2f}")
        
        # ヒストグラム
        fig = px.histogram(data, nbins=30, title="分布")
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

# 便利関数
def create_kpi_card():
    """KPIカードインスタンスを作成"""
    return KPICard()

def render_basic_kpis(data: pd.DataFrame, numeric_columns: List[str]):
    """基本的なKPI表示"""
    kpi = KPICard()
    
    # 基本統計KPI
    kpis = []
    for col in numeric_columns:
        if col in data.columns:
            total = data[col].sum()
            mean = data[col].mean()
            kpis.extend([
                {
                    "title": f"{col} 合計",
                    "value": total,
                    "format_value": True
                },
                {
                    "title": f"{col} 平均",
                    "value": mean,
                    "format_value": True
                }
            ])
    
    if kpis:
        kpi.render_kpi_grid(kpis, columns=4)

def render_summary_kpis(data: pd.DataFrame):
    """サマリーKPI表示"""
    kpi = KPICard()
    
    summary_kpis = [
        {
            "title": "総レコード数",
            "value": len(data),
            "suffix": " 件"
        },
        {
            "title": "列数",
            "value": len(data.columns),
            "suffix": " 列"
        },
        {
            "title": "欠損値",
            "value": data.isnull().sum().sum(),
            "suffix": " 個"
        },
        {
            "title": "重複行",
            "value": data.duplicated().sum(),
            "suffix": " 行"
        }
    ]
    
    kpi.render_kpi_grid(summary_kpis, columns=4)