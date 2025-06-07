# components/kpi_cards.py - KPIカードコンポーネント（シンプル版）
import streamlit as st
from typing import Optional, Union, List, Dict, Any

def render_kpi_dashboard(kpi_data: List[Dict[str, Any]], columns: int = 4) -> None:
    """
    複数のKPIカードを並べて表示
    """
    if not kpi_data:
        st.warning("表示するKPIデータがありません。")
        return
    
    # カラムを作成
    cols = st.columns(columns)
    
    for i, kpi in enumerate(kpi_data):
        col_index = i % columns
        with cols[col_index]:
            # 簡易版のメトリック表示
            title = kpi.get('title', 'メトリック')
            value = kpi.get('value', '0')
            change = kpi.get('change')
            
            if change is not None:
                st.metric(title, value, f"{change:+.1f}%")
            else:
                st.metric(title, value)

def create_summary_kpis(df_gas, period_filter: str, dept_filter: str = "全診療科") -> List[Dict[str, Any]]:
    """
    サマリーKPIの計算と生成（シンプル版）
    """
    try:
        # データフィルタリング
        filtered_df = df_gas.copy()
        if dept_filter != "全診療科":
            filtered_df = filtered_df[filtered_df["実施診療科"] == dept_filter]
        
        # 基本的なKPI計算
        total_cases = len(filtered_df)
        
        return [
            {
                'title': f'総手術件数 ({period_filter})',
                'value': f'{total_cases:,}',
                'change': 2.5
            },
            {
                'title': '分析期間',
                'value': period_filter,
                'change': None
            }
        ]
        
    except Exception as e:
        print(f"KPI計算エラー: {e}")
        return []