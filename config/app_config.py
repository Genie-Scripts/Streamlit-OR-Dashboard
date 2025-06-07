"""
🏥 手術分析ダッシュボード - アプリケーション設定

このモジュールには、アプリケーション全体の設定とスタイル定義が含まれています。
"""

import streamlit as st

# ページ設定
PAGE_CONFIG = {
    "page_title": "🏥 手術分析ダッシュボード",
    "page_icon": "🏥",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# アプリケーション設定
config = {
    "app_title": "🏥 手術分析ダッシュボード",
    "app_description": "入院患者データの包括的分析システム",
    "version": "2.0.0",
    "author": "Healthcare Analytics Team",
    
    # データ設定
    "max_upload_size": 200,  # MB
    "supported_formats": [".csv", ".xlsx", ".xls"],
    
    # セッション設定
    "session_timeout": 3600,  # 秒
    "auto_refresh": True,
    
    # 表示設定
    "default_page_size": 100,
    "chart_height": 400,
    "chart_width": 600,
    
    # KPI設定
    "kpi_refresh_interval": 30,  # 秒
    "show_trends": True,
    
    # エクスポート設定
    "export_formats": ["CSV", "Excel", "PDF"],
    "include_charts": True
}

# カスタムCSS
CUSTOM_CSS = """
<style>
    /* メインコンテナ */
    .main-container {
        padding: 1rem;
        background-color: #f8f9fa;
    }
    
    /* ヘッダー */
    .header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: bold;
    }
    
    .header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* KPIカード */
    .kpi-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #1f77b4;
        transition: transform 0.2s ease;
    }
    
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    }
    
    .kpi-title {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 0.5rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    
    .kpi-change {
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .kpi-positive {
        color: #28a745;
    }
    
    .kpi-negative {
        color: #dc3545;
    }
    
    .kpi-neutral {
        color: #6c757d;
    }
    
    /* データテーブル */
    .dataframe {
        border: none !important;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .dataframe thead tr {
        background-color: #1f77b4 !important;
        color: white !important;
    }
    
    .dataframe tbody tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    
    .dataframe tbody tr:hover {
        background-color: #e3f2fd;
    }
    
    /* サイドバー */
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    
    /* メトリクス */
    [data-testid="metric-container"] {
        background: white;
        border: 1px solid #e0e0e0;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    /* アラート */
    .alert {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        border-left: 4px solid;
    }
    
    .alert-success {
        background-color: #d4edda;
        border-color: #28a745;
        color: #155724;
    }
    
    .alert-warning {
        background-color: #fff3cd;
        border-color: #ffc107;
        color: #856404;
    }
    
    .alert-error {
        background-color: #f8d7da;
        border-color: #dc3545;
        color: #721c24;
    }
    
    .alert-info {
        background-color: #d1ecf1;
        border-color: #17a2b8;
        color: #0c5460;
    }
    
    /* ボタン */
    .stButton > button {
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    }
    
    /* ダウンロードボタン */
    .stDownloadButton > button {
        background-color: #28a745;
        color: white;
        border-radius: 8px;
    }
    
    /* フッター */
    .footer {
        margin-top: 3rem;
        padding: 2rem;
        background-color: #f8f9fa;
        border-top: 1px solid #e0e0e0;
        text-align: center;
        color: #666;
    }
    
    /* レスポンシブデザイン */
    @media (max-width: 768px) {
        .header h1 {
            font-size: 2rem;
        }
        
        .kpi-value {
            font-size: 1.5rem;
        }
        
        .kpi-card {
            margin-bottom: 0.5rem;
        }
    }
    
    /* アニメーション */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* プログレスバー */
    .stProgress > div > div > div {
        background-color: #1f77b4;
    }
    
    /* セレクトボックス */
    .stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* 日付入力 */
    .stDateInput > div > div {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* 数値入力 */
    .stNumberInput > div > div {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
</style>
"""

# JavaScript関数
CUSTOM_JS = """
<script>
    // ページロード時のアニメーション
    function fadeInElements() {
        const elements = document.querySelectorAll('.kpi-card, .dataframe');
        elements.forEach((el, index) => {
            setTimeout(() => {
                el.classList.add('fade-in');
            }, index * 100);
        });
    }
    
    // 自動リフレッシュ機能
    function autoRefresh() {
        if (window.location.search.includes('auto_refresh=true')) {
            setTimeout(() => {
                window.location.reload();
            }, 30000); // 30秒後にリフレッシュ
        }
    }
    
    // ページ読み込み完了時に実行
    document.addEventListener('DOMContentLoaded', function() {
        fadeInElements();
        autoRefresh();
    });
    
    // KPIカードのホバーエフェクト
    function addKPIHoverEffects() {
        const kpiCards = document.querySelectorAll('.kpi-card');
        kpiCards.forEach(card => {
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-2px)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }
    
    // エラーハンドリング
    window.addEventListener('error', function(e) {
        console.error('アプリケーションエラー:', e.error);
    });
</script>
"""

# 色設定
COLORS = {
    "primary": "#1f77b4",
    "secondary": "#ff7f0e",
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "info": "#17a2b8",
    "light": "#f8f9fa",
    "dark": "#343a40",
    "background": "#ffffff",
    "border": "#e0e0e0"
}

# チャート設定
CHART_CONFIG = {
    "plotly_config": {
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "pan2d", "lasso2d", "autoScale2d", "resetScale2d"
        ]
    },
    "layout": {
        "font": {"family": "Arial, sans-serif", "size": 12},
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 40, "r": 40, "t": 40, "b": 40}
    }
}

# エラーメッセージ
ERROR_MESSAGES = {
    "file_not_found": "ファイルが見つかりません。正しいファイルを選択してください。",
    "invalid_format": "サポートされていないファイル形式です。CSV、Excel形式のファイルを選択してください。",
    "upload_failed": "ファイルのアップロードに失敗しました。もう一度お試しください。",
    "data_processing_error": "データの処理中にエラーが発生しました。",
    "memory_error": "メモリ不足です。より小さいファイルを使用してください。",
    "connection_error": "接続エラーが発生しました。ネットワーク接続を確認してください。"
}

# 成功メッセージ
SUCCESS_MESSAGES = {
    "file_uploaded": "ファイルが正常にアップロードされました。",
    "data_processed": "データの処理が完了しました。",
    "export_completed": "エクスポートが完了しました。",
    "analysis_completed": "分析が完了しました。"
}

def get_config(key: str = None):
    """設定値を取得する関数"""
    if key is None:
        return config
    return config.get(key)

def get_color(color_name: str) -> str:
    """色設定を取得する関数"""
    return COLORS.get(color_name, COLORS["primary"])

def get_error_message(error_type: str) -> str:
    """エラーメッセージを取得する関数"""
    return ERROR_MESSAGES.get(error_type, "予期しないエラーが発生しました。")

def get_success_message(message_type: str) -> str:
    """成功メッセージを取得する関数"""
    return SUCCESS_MESSAGES.get(message_type, "操作が完了しました。")