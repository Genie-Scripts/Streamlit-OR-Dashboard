# config/app_config.py - 設定管理モジュール
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class AppConfig:
    """アプリケーション設定クラス"""
    
    # ページ設定
    PAGE_TITLE: str = "🏥 手術分析ダッシュボード"
    PAGE_ICON: str = "🏥"
    LAYOUT: str = "wide"
    INITIAL_SIDEBAR_STATE: str = "expanded"

# シングルトンインスタンス
config = AppConfig()

# ページ設定辞書
PAGE_CONFIG = {
    "page_title": config.PAGE_TITLE,
    "page_icon": config.PAGE_ICON,
    "layout": config.LAYOUT,
    "initial_sidebar_state": config.INITIAL_SIDEBAR_STATE
}

# カスタムCSS（既存のCSSをそのまま）
CUSTOM_CSS = """
<style>
    /* メインコンテナ */
    .main-header {
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        padding: 2rem 0;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        border-radius: 10px;
    }
    
    /* KPIカード */
    .kpi-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
    }
    
    .kpi-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
        color: #1f77b4;
    }
    
    .kpi-label {
        font-size: 1rem;
        color: #666;
        margin-bottom: 0.5rem;
    }
    
    .kpi-change {
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }
    
    .positive { color: #2ca02c; }
    .negative { color: #d62728; }
    .neutral { color: #ff7f0e; }
    
    /* フィルタセクション */
    .filter-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        border: 1px solid #e9ecef;
    }
    
    /* チャートコンテナ */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
        margin-bottom: 1.5rem;
    }
    
    /* ダッシュボード タイトル */
    .dashboard-title {
        font-size: 2.5rem;
        color: white;
        font-weight: bold;
        margin: 0;
    }
    
    .dashboard-subtitle {
        font-size: 1.2rem;
        color: rgba(255, 255, 255, 0.8);
        margin-top: 0.5rem;
    }
</style>
"""