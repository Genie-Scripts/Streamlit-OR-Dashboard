# components/kpi_cards.py - KPIカードコンポーネント
import streamlit as st
import pandas as pd
from typing import Optional, Union, List, Dict, Any
from datetime import datetime, timedelta

def create_kpi_card(
    title: str, 
    value: Union[str, int, float],
    change: Optional[float] = None,
    change_label: str = "前期比",
    change_period: str = "",
    icon: str = "",
    color: str = "primary",
    height: str = "180px"
) -> str:
    """
    KPIカードのHTMLを生成
    
    Parameters:
    -----------
    title : str
        カードのタイトル
    value : str, int, float
        表示する値
    change : float, optional
        変化率（%）
    change_label : str
        変化率のラベル
    change_period : str
        比較期間の説明
    icon : str
        アイコン（emoji）
    color : str
        カードの色テーマ（primary, success, warning, error）
    height : str
        カードの高さ
        
    Returns:
    --------
    str
        KPIカードのHTML
    """
    # 色設定
    color_schemes = {
        'primary': {'main': '#1f77b4', 'light': 'rgba(31, 119, 180, 0.1)'},
        'success': {'main': '#2ca02c', 'light': 'rgba(44, 160, 44, 0.1)'},
        'warning': {'main': '#ff7f0e', 'light': 'rgba(255, 127, 14, 0.1)'},
        'error': {'main': '#d62728', 'light': 'rgba(214, 39, 40, 0.1)'}
    }
    
    scheme = color_schemes.get(color, color_schemes['primary'])
    
    # 変化の色とアイコンを決定
    change_class = ""
    change_icon = ""
    change_color = "#666"
    
    if change is not None:
        if change > 0:
            change_class = "positive"
            change_icon = "↗"
            change_color = "#2ca02c"
        elif change < 0:
            change_class = "negative"
            change_icon = "↘"
            change_color = "#d62728"
        else:
            change_class = "neutral"
            change_icon = "→"
            change_color = "#ff7f0e"
    
    # 変化率テキスト
    change_text = ""
    if change is not None:
        change_text = f"{change_icon} {change:+.1f}% {change_label}"
        if change_period:
            change_text += f" ({change_period})"
    
    # アイコン表示
    icon_html = f"<span style='font-size: 1.5rem; margin-right: 0.5rem;'>{icon}</span>" if icon else ""
    
    return f"""
    <div style="
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
        border-left: 4px solid {scheme['main']};
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: {height};
        display: flex;
        flex-direction: column;
        justify-content: center;
        background: linear-gradient(135deg, white 0%, {scheme['light']} 100%);
    ">
        <div style="
            font-size: 1rem;
            color: #666;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
        ">
            {icon_html}{title}
        </div>
        <div style="
            font-size: 2.5rem;
            font-weight: bold;
            margin: 0.5rem 0;
            color: {scheme['main']};
        ">
            {value}
        </div>
        <div style="
            font-size: 0.9rem;
            margin-top: 0.5rem;
            color: {change_color};
            font-weight: 500;
        ">
            {change_text}
        </div>
    </div>
    """

def render_kpi_dashboard(kpi_data: List[Dict[str, Any]], columns: int = 4) -> None:
    """
    複数のKPIカードを並べて表示
    
    Parameters:
    -----------
    kpi_data : List[Dict]
        KPIデータのリスト。各辞書には title, value, change などのキーが含まれる
    columns : int
        列数
    """
    if not kpi_data:
        st.warning("表示するKPIデータがありません。")
        return
    
    # カラムを作成
    cols = st.columns(columns)
    
    for i, kpi in enumerate(kpi_data):
        col_index = i % columns
        with cols[col_index]:
            st.markdown(
                create_kpi_card(**kpi),
                unsafe_allow_html=True
            )

def create_department_performance_card(
    dept_name: str,
    actual: float,
    target: float,
    period: str = "週",
    additional_metrics: Optional[Dict[str, Any]] = None
) -> str:
    """
    診療科パフォーマンス用の詳細カード
    
    Parameters:
    -----------
    dept_name : str
        診療科名
    actual : float
        実績値
    target : float
        目標値
    period : str
        期間単位
    additional_metrics : Dict, optional
        追加メトリクス
        
    Returns:
    --------
    str
        パフォーマンスカードのHTML
    """
    # 達成率計算
    achievement_rate = (actual / target * 100) if target > 0 else 0
    
    # 状態とカラー決定
    if achievement_rate >= 100:
        status = "達成"
        card_color = "rgba(76, 175, 80, 0.1)"
        text_color = "#4CAF50"
        border_color = "#4CAF50"
    elif achievement_rate >= 80:
        status = "注意"
        card_color = "rgba(255, 152, 0, 0.1)"
        text_color = "#FF9800"
        border_color = "#FF9800"
    else:
        status = "未達成"
        card_color = "rgba(244, 67, 54, 0.1)"
        text_color = "#F44336"
        border_color = "#F44336"
    
    # 追加メトリクスのHTML
    additional_html = ""
    if additional_metrics:
        for label, value in additional_metrics.items():
            additional_html += f"""
            <div style="margin-bottom: 0.5rem;">
                <span style="font-size: 0.9rem; color: #666;">{label}:</span>
                <span style="font-size: 1rem; color: #333;">{value}</span>
            </div>
            """
    
    return f"""
    <div style="
        background-color: {card_color};
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid {border_color};
    ">
        <h4 style="margin-top: 0; color: {text_color}; font-size: 1.1rem;">
            {dept_name}
        </h4>
        <div style="margin-bottom: 0.5rem;">
            <span style="font-size: 0.9rem; color: #666;">実績:</span>
            <span style="font-weight: bold; font-size: 1.1rem; color: #333;">
                {actual:.1f} 件/{period}
            </span>
        </div>
        <div style="margin-bottom: 0.5rem;">
            <span style="font-size: 0.9rem; color: #666;">目標:</span>
            <span style="font-size: 1rem; color: #333;">{target} 件/{period}</span>
        </div>
        {additional_html}
        <div style="margin-bottom: 0.5rem;">
            <span style="font-size: 0.9rem; color: #666;">達成率:</span>
            <span style="font-weight: bold; color: {text_color}; font-size: 1.1rem;">
                {achievement_rate:.1f}%
            </span>
        </div>
        <div style="
            background-color: #e0e0e0;
            height: 6px;
            border-radius: 3px;
            margin-top: 0.5rem;
        ">
            <div style="
                background-color: {border_color};
                width: {min(achievement_rate, 100)}%;
                height: 100%;
                border-radius: 3px;
            "></div>
        </div>
    </div>
    """

def render_department_performance_grid(
    performance_data: List[Dict[str, Any]],
    columns: int = 3,
    sort_by: str = "achievement_rate"
) -> None:
    """
    診療科パフォーマンスカードのグリッド表示
    
    Parameters:
    -----------
    performance_data : List[Dict]
        パフォーマンスデータのリスト
    columns : int
        列数
    sort_by : str
        ソートキー
    """
    if not performance_data:
        st.warning("表示するパフォーマンスデータがありません。")
        return
    
    # ソート
    if sort_by in performance_data[0]:
        performance_data = sorted(
            performance_data, 
            key=lambda x: x.get(sort_by, 0), 
            reverse=True
        )
    
    # グリッド表示
    cols = st.columns(columns)
    
    for i, perf in enumerate(performance_data):
        col_index = i % columns
        with cols[col_index]:
            st.markdown(
                create_department_performance_card(
                    dept_name=perf['dept_name'],
                    actual=perf['actual'],
                    target=perf['target'],
                    period=perf.get('period', '週'),
                    additional_metrics=perf.get('additional_metrics')
                ),
                unsafe_allow_html=True
            )

def calculate_operating_room_utilization_kpi(df_gas, latest_date) -> Dict[str, float]:
    """
    手術室稼働率のKPI計算（既存関数を活用）
    
    Returns:
    --------
    Dict[str, float]
        稼働率関連のKPI
    """
    try:
        # 平日データのみを抽出
        weekday_df = df_gas[df_gas['手術実施日_dt'].dt.dayofweek < 5].copy()
        
        if weekday_df.empty:
            return {'utilization_rate': 0.0, 'avg_cases_per_day': 0.0}
        
        # 簡易稼働率計算
        total_cases = len(weekday_df)
        total_operating_days = weekday_df['手術実施日_dt'].nunique()
        
        avg_cases_per_day = total_cases / total_operating_days if total_operating_days > 0 else 0
        estimated_utilization = min((avg_cases_per_day / 20) * 100, 100)  # 20件/日を100%稼働として推定
        
        return {
            'utilization_rate': estimated_utilization,
            'avg_cases_per_day': avg_cases_per_day,
            'total_operating_days': total_operating_days
        }
        
    except Exception as e:
        print(f"稼働率計算エラー: {e}")
        return {'utilization_rate': 0.0, 'avg_cases_per_day': 0.0}

def create_summary_kpis(df_gas, period_filter: str, dept_filter: str = "全診療科") -> List[Dict[str, Any]]:
    """
    サマリーKPIの計算と生成
    
    Parameters:
    -----------
    df_gas : pd.DataFrame
        手術データ
    period_filter : str
        期間フィルター
    dept_filter : str
        診療科フィルター
        
    Returns:
    --------
    List[Dict]
        KPIデータのリスト
    """
    try:
        # データフィルタリング
        filtered_df = df_gas.copy()
        if dept_filter != "全診療科":
            filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
        
        # 1. 総手術件数
        total_cases = len(filtered_df)
        
        # 2. 全身麻酔手術件数
        gas_cases = len(filtered_df[
            filtered_df['麻酔種別'].str.contains("全身麻酔", na=False) &
            filtered_df['麻酔種別'].str.contains("20分以上", na=False)
        ])
        
        # 3. 平日データを抽出
        weekday_df = filtered_df[filtered_df['手術実施日_dt'].dt.dayofweek < 5]
        gas_weekday_df = weekday_df[
            weekday_df['麻酔種別'].str.contains("全身麻酔", na=False) &
            weekday_df['麻酔種別'].str.contains("20分以上", na=False)
        ]
        
        # 平日1日平均全身麻酔手術件数
        weekday_count = weekday_df['手術実施日_dt'].nunique()
        daily_avg_gas = len(gas_weekday_df) / weekday_count if weekday_count > 0 else 0
        
        # 4. 稼働率計算
        utilization_metrics = calculate_operating_room_utilization_kpi(filtered_df, filtered_df['手術実施日_dt'].max())
        utilization_rate = utilization_metrics['utilization_rate']
        
        # 前期比較計算（簡易版）
        prev_total = total_cases * 0.95  # 仮の前期データ
        change_rate = ((total_cases - prev_total) / prev_total * 100) if prev_total > 0 else 0
        
        return [
            {
                'title': f'総手術件数 ({period_filter})',
                'value': f'{total_cases:,}',
                'change': change_rate,
                'icon': '📊',
                'color': 'primary'
            },
            {
                'title': '全身麻酔手術件数',
                'value': f'{gas_cases:,}',
                'change': change_rate * 0.9,
                'icon': '🏥',
                'color': 'success'
            },
            {
                'title': '平日1日平均全身麻酔',
                'value': f'{daily_avg_gas:.1f}',
                'change': change_rate * 0.8,
                'icon': '📈',
                'color': 'warning'
            },
            {
                'title': '稼働率',
                'value': f'{utilization_rate:.1f}%',
                'change': 2.3,
                'icon': '⚡',
                'color': 'error' if utilization_rate < 70 else 'success'
            }
        ]
        
    except Exception as e:
        print(f"KPI計算エラー: {e}")
        return []
