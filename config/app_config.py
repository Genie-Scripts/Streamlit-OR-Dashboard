# config/app_config.py - 設定管理モジュール
# 既存のapp.pyから設定を外部化
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
    
    # データ設定
    MAX_FILE_SIZE_MB: int = 200
    SUPPORTED_FILE_TYPES: List[str] = [".csv", ".xlsx", ".xls"]
    
    # UI設定
    CHART_HEIGHT: int = 500
    KPI_CARD_HEIGHT: int = 180
    
    # 色設定
    PRIMARY_COLOR: str = "#1f77b4"
    SUCCESS_COLOR: str = "#2ca02c"
    WARNING_COLOR: str = "#ff7f0e"
    ERROR_COLOR: str = "#d62728"
    
    # 目標設定
    DEFAULT_HOSPITAL_TARGET: int = 21  # 病院全体の平日1日平均目標

# シングルトンインスタンス
config = AppConfig()

# ページ設定辞書
PAGE_CONFIG = {
    "page_title": config.PAGE_TITLE,
    "page_icon": config.PAGE_ICON,
    "layout": config.LAYOUT,
    "initial_sidebar_state": config.INITIAL_SIDEBAR_STATE
}

# カスタムCSS
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
    
    /* ナビゲーション */
    .nav-pill {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.5rem 1rem;
        border-radius: 25px;
        margin: 0.25rem;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .nav-pill:hover {
        background: #1976d2;
        color: white;
    }
    
    .nav-pill.active {
        background: #1976d2;
        color: white;
    }
    
    /* メトリクスカード（診療科パフォーマンス用） */
    .metrics-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid;
    }
    
    .metrics-card.success {
        background-color: rgba(76, 175, 80, 0.1);
        border-left-color: #4CAF50;
    }
    
    .metrics-card.warning {
        background-color: rgba(255, 152, 0, 0.1);
        border-left-color: #FF9800;
    }
    
    .metrics-card.error {
        background-color: rgba(244, 67, 54, 0.1);
        border-left-color: #F44336;
    }
</style>
"""

# ターゲット診療科リスト
TARGET_DEPARTMENTS = [
    "皮膚科", "整形外科", "産婦人科", "歯科口腔外科", "耳鼻咽喉科", 
    "泌尿器科", "一般消化器外科", "呼吸器外科", "心臓血管外科", 
    "乳腺外科", "形成外科", "脳神経外科"
]

# ナビゲーションメニュー
NAVIGATION_MENU = [
    "🏠 ダッシュボード",
    "📤 データアップロード", 
    "🏥 病院全体分析",
    "🩺 診療科別分析",
    "🏆 診療科ランキング",
    "👨‍⚕️ 術者分析",
    "🔮 将来予測"
]

# ビューマッピング
VIEW_MAPPING = {
    "🏠 ダッシュボード": "dashboard",
    "📤 データアップロード": "upload",
    "🏥 病院全体分析": "hospital",
    "🩺 診療科別分析": "department", 
    "🏆 診療科ランキング": "ranking",
    "👨‍⚕️ 術者分析": "surgeon",
    "🔮 将来予測": "prediction"
}

# 期間フィルターオプション
PERIOD_FILTER_OPTIONS = [
    "直近30日", "直近90日", "直近180日", "今年度", "全期間"
]

# 週次期間オプション（完全週データ用）
WEEKLY_PERIOD_OPTIONS = [
    "直近1週", "直近4週", "直近12週", "直近26週", "直近52週", "今年度", "全期間"
]

# 分析タイプオプション
ANALYSIS_TYPE_OPTIONS = ["全身麻酔手術", "全手術"]

# 表示形式オプション
VIEW_TYPE_OPTIONS = ["週次", "月次", "四半期"]