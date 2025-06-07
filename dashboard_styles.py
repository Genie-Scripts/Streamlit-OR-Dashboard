# dashboard_styles.py - ダッシュボード用スタイル設定
import streamlit as st

def load_dashboard_css():
    """ダッシュボード用のカスタムCSSを読み込み"""
    st.markdown("""
    <style>
    /* ベースリセット */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* メインコンテナ */
    .main .block-container {
        padding: 1rem 2rem;
        max-width: 100%;
    }
    
    /* ヘッダーセクション */
    .dashboard-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        text-align: center;
    }
    
    .dashboard-title {
        font-size: 3rem;
        font-weight: bold;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .dashboard-subtitle {
        font-size: 1.3rem;
        margin-top: 0.5rem;
        opacity: 0.9;
    }
    
    .dashboard-stats {
        display: flex;
        justify-content: space-around;
        margin-top: 1.5rem;
    }
    
    .stat-item {
        text-align: center;
    }
    
    .stat-value {
        font-size: 1.8rem;
        font-weight: bold;
        display: block;
    }
    
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.8;
        display: block;
        margin-top: 0.2rem;
    }
    
    /* KPIカード */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .kpi-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    .kpi-card:hover {
        transform: translateY(-10px) scale(1.02);
        box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    }
    
    .kpi-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        color: #667eea;
    }
    
    .kpi-value {
        font-size: 2.8rem;
        font-weight: bold;
        color: #2c3e50;
        margin: 0.5rem 0;
        line-height: 1;
    }
    
    .kpi-label {
        font-size: 1.1rem;
        color: #7f8c8d;
        margin-bottom: 1rem;
        font-weight: 500;
    }
    
    .kpi-change {
        font-size: 1rem;
        font-weight: bold;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: inline-block;
    }
    
    .kpi-change.positive {
        background: rgba(46, 160, 67, 0.1);
        color: #2ea043;
    }
    
    .kpi-change.negative {
        background: rgba(214, 39, 40, 0.1);
        color: #d62728;
    }
    
    .kpi-change.neutral {
        background: rgba(255, 127, 14, 0.1);
        color: #ff7f0e;
    }
    
    /* フィルターセクション */
    .filter-container {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.3);
    }
    
    /* チャートコンテナ */
    .chart-section {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.3);
    }
    
    .chart-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    
    /* サイドバー */
    .css-1d391kg {
        background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
    }
    
    .css-1d391kg .stRadio > label {
        color: white;
        font-weight: 500;
    }
    
    .css-1d391kg .stSelectbox > label {
        color: white;
        font-weight: 500;
    }
    
    /* ナビゲーションボタン */
    .nav-button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.8rem 1.5rem;
        border-radius: 25px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
        margin: 0.3rem;
        display: inline-block;
        text-decoration: none;
    }
    
    .nav-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    
    .nav-button.active {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        box-shadow: 0 5px 15px rgba(44, 62, 80, 0.4);
    }
    
    /* タブスタイル */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px;
        padding: 0.8rem 1.5rem;
        font-weight: bold;
        border: 1px solid #dee2e6;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    /* メトリクスカード */
    .metric-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.3);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.15);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #2c3e50;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #7f8c8d;
        margin-top: 0.5rem;
    }
    
    /* データテーブル */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    
    /* アニメーション */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .fade-in {
        animation: fadeInUp 0.6s ease-out;
    }
    
    /* レスポンシブデザイン */
    @media (max-width: 768px) {
        .dashboard-title {
            font-size: 2rem;
        }
        
        .kpi-container {
            grid-template-columns: 1fr;
        }
        
        .main .block-container {
            padding: 1rem;
        }
    }
    
    /* スクロールバー */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
    }
    
    /* ローディングスピナー */
    .loading-spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* 成功・警告・エラーメッセージ */
    .stAlert > div {
        border-radius: 10px;
        border: none;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    
    /* プログレスバー */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def create_dashboard_header(title, subtitle, stats=None):
    """ダッシュボードヘッダーを作成"""
    stats_html = ""
    if stats:
        stats_items = []
        for stat in stats:
            stats_items.append(f"""
                <div class="stat-item">
                    <span class="stat-value">{stat['value']}</span>
                    <span class="stat-label">{stat['label']}</span>
                </div>
            """)
        stats_html = f'<div class="dashboard-stats">{"".join(stats_items)}</div>'
    
    return f"""
    <div class="dashboard-header fade-in">
        <h1 class="dashboard-title">{title}</h1>
        <p class="dashboard-subtitle">{subtitle}</p>
        {stats_html}
    </div>
    """

def create_kpi_card(icon, title, value, change=None, change_label="前期比"):
    """改良版KPIカードを作成"""
    change_class = ""
    change_icon = ""
    change_text = ""
    
    if change is not None:
        if change > 0:
            change_class = "positive"
            change_icon = "📈"
        elif change < 0:
            change_class = "negative"
            change_icon = "📉"
        else:
            change_class = "neutral"
            change_icon = "➡️"
        
        change_text = f"""
        <div class="kpi-change {change_class}">
            {change_icon} {change:+.1f}% {change_label}
        </div>
        """
    
    return f"""
    <div class="kpi-card fade-in">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-label">{title}</div>
        <div class="kpi-value">{value}</div>
        {change_text}
    </div>
    """

def create_metric_card(label, value, delta=None):
    """シンプルなメトリクスカードを作成"""
    delta_html = ""
    if delta is not None:
        delta_color = "#2ea043" if delta >= 0 else "#d62728"
        delta_icon = "▲" if delta >= 0 else "▼"
        delta_html = f'<div style="color: {delta_color}; font-size: 0.8rem; margin-top: 0.5rem;">{delta_icon} {delta:+.1f}%</div>'
    
    return f"""
    <div class="metric-card">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """

def create_filter_section(title="フィルター設定"):
    """フィルターセクションのコンテナを作成"""
    return f"""
    <div class="filter-container">
        <h3 style="margin: 0 0 1rem 0; color: #2c3e50;">{title}</h3>
    """

def close_filter_section():
    """フィルターセクションを閉じる"""
    return "</div>"

def create_chart_section(title):
    """チャートセクションのコンテナを作成"""
    return f"""
    <div class="chart-section">
        <h3 class="chart-title">{title}</h3>
    """

def close_chart_section():
    """チャートセクションを閉じる"""
    return "</div>"

def show_loading_spinner():
    """ローディングスピナーを表示"""
    return '<div class="loading-spinner"></div>'

# カラーパレット定義
DASHBOARD_COLORS = {
    'primary': '#667eea',
    'secondary': '#764ba2', 
    'success': '#2ea043',
    'warning': '#ff7f0e',
    'danger': '#d62728',
    'info': '#17a2b8',
    'light': '#f8f9fa',
    'dark': '#2c3e50'
}

def get_color_gradient(color1, color2):
    """グラデーションカラーを生成"""
    return f"linear-gradient(135deg, {color1} 0%, {color2} 100%)"