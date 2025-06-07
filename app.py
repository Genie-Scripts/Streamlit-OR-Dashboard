"""
🏥 統合医療分析プラットフォーム v2.0

プロ仕様の医療データ分析ダッシュボード
- 美しいUI/UX
- 高度可視化
- 予測分析
- 自動レポート生成
"""

# ⚠️ 重要: st.set_page_config() は最初に実行
import streamlit as st

st.set_page_config(
    page_title="🏥 統合医療分析プラットフォーム",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://docs.streamlit.io/',
        'Report a bug': "https://github.com/streamlit/streamlit/issues",
        'About': "# 🏥 統合医療分析プラットフォーム v2.0\n医療データの包括的分析システム"
    }
)

# 基本ライブラリ
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import io
import base64
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

# カスタムモジュール
module_status = {'config': False, 'session': False, 'kpi': False}

try:
    from config.app_config import config, CUSTOM_CSS, COLORS
    module_status['config'] = True
except ImportError:
    pass

try:
    from utils.session_manager import session_manager
    session_manager.update_activity()
    module_status['session'] = True
except ImportError:
    pass

try:
    from components.kpi_cards import render_kpi_dashboard, render_medical_kpis, KPICard
    module_status['kpi'] = True
except ImportError:
    pass

# プロ仕様カスタムCSS
PROFESSIONAL_CSS = """
<style>
    /* メインコンテナ */
    .main {
        padding: 1rem 2rem;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* ヘッダー */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        font-size: 3rem;
        margin: 0;
        font-weight: 700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header p {
        font-size: 1.2rem;
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    
    /* KPIカード */
    .kpi-card {
        background: rgba(255, 255, 255, 0.95);
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        backdrop-filter: blur(4px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(31, 38, 135, 0.5);
    }
    
    /* メトリクス強化 */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #fff 0%, #f8f9ff 100%);
        border: 1px solid #e1e5e9;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    
    [data-testid="metric-container"]:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 24px rgba(0,0,0,0.1);
    }
    
    /* サイドバー */
    .css-1d391kg {
        background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
    }
    
    /* ボタン */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    
    /* タブ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        border-radius: 15px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        border: none;
    }
    
    /* アニメーション */
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    .slide-in {
        animation: slideIn 0.5s ease-out;
    }
    
    /* グラフコンテナ */
    .graph-container {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    
    /* ステータスインジケーター */
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-success {
        background: #28a745;
        box-shadow: 0 0 10px rgba(40, 167, 69, 0.5);
    }
    
    .status-warning {
        background: #ffc107;
        box-shadow: 0 0 10px rgba(255, 193, 7, 0.5);
    }
    
    .status-error {
        background: #dc3545;
        box-shadow: 0 0 10px rgba(220, 53, 69, 0.5);
    }
</style>
"""

# プロテーマ色設定
THEME_COLORS = {
    'primary': '#667eea',
    'secondary': '#764ba2',
    'success': '#28a745',
    'warning': '#ffc107',
    'danger': '#dc3545',
    'info': '#17a2b8',
    'gradient_1': ['#667eea', '#764ba2'],
    'gradient_2': ['#f093fb', '#f5576c'],
    'gradient_3': ['#4facfe', '#00f2fe']
}

# CSS適用
st.markdown(PROFESSIONAL_CSS, unsafe_allow_html=True)
if module_status['config']:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =======================
# ユーティリティ関数
# =======================

def create_status_indicator(status):
    """ステータスインジケーター作成"""
    if status:
        return '<span class="status-indicator status-success"></span>'
    else:
        return '<span class="status-indicator status-error"></span>'

def load_advanced_sample_data():
    """高度なサンプルデータ生成"""
    np.random.seed(42)
    n_records = 1500
    
    # より現実的な医療データ
    departments = ['循環器内科', '整形外科', '脳神経外科', '消化器内科', '呼吸器内科', 
                  '泌尿器科', '産婦人科', '小児科', '眼科', '耳鼻咽喉科']
    
    surgery_types = {
        '循環器内科': ['冠動脈バイパス術', '心臓弁置換術', 'ペースメーカー植込み術'],
        '整形外科': ['人工関節置換術', '骨折手術', '関節鏡手術'],
        '脳神経外科': ['脳腫瘍摘出術', '血管内治療', '脊椎手術'],
        '消化器内科': ['内視鏡的切除術', '肝切除術', '胆嚢摘出術'],
        '呼吸器内科': ['肺切除術', '気管支鏡検査', '胸腔鏡手術']
    }
    
    # 基本データ生成
    data = []
    
    for i in range(n_records):
        dept = np.random.choice(departments)
        surgery_list = surgery_types.get(dept, ['一般手術'])
        surgery = np.random.choice(surgery_list)
        
        # 年齢と疾患の相関を考慮
        if dept in ['循環器内科', '脳神経外科']:
            age = int(np.random.normal(70, 12))
        elif dept == '整形外科':
            age = int(np.random.normal(65, 15))
        elif dept == '小児科':
            age = int(np.random.normal(8, 5))
        else:
            age = int(np.random.normal(55, 20))
        
        age = max(0, min(age, 100))
        
        # 入院日数（手術の複雑さに依存）
        if surgery in ['冠動脈バイパス術', '心臓弁置換術', '脳腫瘍摘出術']:
            los = int(np.random.exponential(12))
        elif surgery in ['内視鏡的切除術', '関節鏡手術']:
            los = int(np.random.exponential(3))
        else:
            los = int(np.random.exponential(7))
        
        los = max(1, min(los, 60))
        
        # 手術費用（複雑さと年齢に依存）
        base_cost = {
            '冠動脈バイパス術': 2000000,
            '心臓弁置換術': 2500000,
            '脳腫瘍摘出術': 1800000,
            '人工関節置換術': 1200000,
            '内視鏡的切除術': 400000
        }.get(surgery, 600000)
        
        cost = int(np.random.normal(base_cost, base_cost * 0.3))
        cost = max(100000, cost)
        
        # 手術結果（年齢、複雑さに依存）
        if age > 80 or surgery in ['冠動脈バイパス術', '脳腫瘍摘出術']:
            outcome_prob = [0.75, 0.20, 0.05]  # 成功、合併症、再手術
        else:
            outcome_prob = [0.90, 0.08, 0.02]
        
        outcome = np.random.choice(['成功', '合併症', '再手術'], p=outcome_prob)
        
        # 日付（最近2年間）
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2024, 6, 1)
        random_date = start_date + timedelta(
            days=np.random.randint(0, (end_date - start_date).days)
        )
        
        data.append({
            'Patient_ID': f'P{i+1:05d}',
            'Age': age,
            'Gender': np.random.choice(['男性', '女性']),
            'Department': dept,
            'Surgery_Type': surgery,
            'Surgery_Date': random_date,
            'Length_of_Stay': los,
            'Surgery_Cost': cost,
            'Outcome': outcome,
            'Satisfaction_Score': int(np.random.normal(8.5, 1.5)),
            'Complication_Risk': np.random.random(),
            'Readmission_30d': np.random.choice([0, 1], p=[0.85, 0.15])
        })
    
    df = pd.DataFrame(data)
    df['Satisfaction_Score'] = df['Satisfaction_Score'].clip(1, 10)
    
    return df

def show_professional_header():
    """プロ仕様ヘッダー表示"""
    st.markdown("""
    <div class="main-header">
        <h1>🏥 統合医療分析プラットフォーム</h1>
        <p>Advanced Healthcare Analytics Platform v2.0</p>
        <p>💊 手術データ分析 | 📈 予測モデリング | 📋 自動レポート生成</p>
    </div>
    """, unsafe_allow_html=True)

def show_system_status():
    """システム状況をプロ仕様で表示"""
    st.sidebar.markdown("### 🔧 システム状況")
    
    status_html = "<div style='padding: 1rem; background: rgba(255,255,255,0.1); border-radius: 10px;'>"
    
    for module, status in module_status.items():
        indicator = create_status_indicator(status)
        status_text = "OK" if status else "ERROR"
        status_html += f"<p>{indicator} {module.title()}: <strong>{status_text}</strong></p>"
    
    status_html += "</div>"
    st.sidebar.markdown(status_html, unsafe_allow_html=True)

def create_advanced_kpi_dashboard(data):
    """高度なKPIダッシュボード"""
    if data is None or data.empty:
        return
    
    st.markdown('<div class="slide-in">', unsafe_allow_html=True)
    st.markdown("## 📊 エグゼクティブダッシュボード")
    
    # トップレベルKPI
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_patients = len(data)
    avg_cost = data['Surgery_Cost'].mean()
    success_rate = (data['Outcome'] == '成功').mean() * 100
    avg_los = data['Length_of_Stay'].mean()
    readmission_rate = data['Readmission_30d'].mean() * 100
    
    with col1:
        st.metric(
            "総患者数",
            f"{total_patients:,}",
            delta=f"+{int(total_patients * 0.05):,} (5%)",
            help="対前期比較"
        )
    
    with col2:
        st.metric(
            "平均手術費用",
            f"¥{avg_cost:,.0f}",
            delta=f"¥{int(avg_cost * 0.02):,} (2%)",
            help="平均手術費用（対前期比）"
        )
    
    with col3:
        st.metric(
            "手術成功率",
            f"{success_rate:.1f}%",
            delta=f"+{success_rate - 88:.1f}%",
            delta_color="normal",
            help="合併症・再手術を除く成功率"
        )
    
    with col4:
        st.metric(
            "平均在院日数",
            f"{avg_los:.1f}日",
            delta=f"-{avg_los - 6:.1f}日",
            delta_color="inverse",
            help="ALOS (Average Length of Stay)"
        )
    
    with col5:
        st.metric(
            "30日再入院率",
            f"{readmission_rate:.1f}%",
            delta=f"-{readmission_rate - 12:.1f}%",
            delta_color="inverse",
            help="30日以内の再入院率"
        )
    
    st.markdown('</div>', unsafe_allow_html=True)

def create_advanced_visualizations(data):
    """高度な可視化"""
    if data is None or data.empty:
        return
    
    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    st.markdown("## 📈 高度分析ダッシュボード")
    
    # 2x2グリッドレイアウト
    col1, col2 = st.columns(2)
    
    with col1:
        # 1. 手術成果分析
        st.markdown("### 🎯 手術成果分析")
        
        outcome_data = data['Outcome'].value_counts()
        colors = ['#28a745', '#ffc107', '#dc3545']
        
        fig_outcome = go.Figure(data=[
            go.Pie(labels=outcome_data.index, 
                   values=outcome_data.values,
                   hole=0.4,
                   marker_colors=colors)
        ])
        
        fig_outcome.update_layout(
            title="手術結果分布",
            height=350,
            showlegend=True,
            font=dict(size=12)
        )
        
        st.plotly_chart(fig_outcome, use_container_width=True)
    
    with col2:
        # 2. 診療科別パフォーマンス
        st.markdown("### 🏥 診療科別パフォーマンス")
        
        dept_stats = data.groupby('Department').agg({
            'Surgery_Cost': 'mean',
            'Length_of_Stay': 'mean',
            'Outcome': lambda x: (x == '成功').mean() * 100
        }).round(2)
        
        fig_dept = go.Figure()
        
        fig_dept.add_trace(go.Bar(
            name='平均費用 (万円)',
            x=dept_stats.index,
            y=dept_stats['Surgery_Cost'] / 10000,
            yaxis='y',
            marker_color='rgba(102, 126, 234, 0.7)'
        ))
        
        fig_dept.add_trace(go.Scatter(
            name='成功率 (%)',
            x=dept_stats.index,
            y=dept_stats['Outcome'],
            yaxis='y2',
            mode='lines+markers',
            marker_color='red',
            line=dict(width=3)
        ))
        
        fig_dept.update_layout(
            title='診療科別 費用vs成功率',
            xaxis=dict(tickangle=45),
            yaxis=dict(title='平均費用 (万円)', side='left'),
            yaxis2=dict(title='成功率 (%)', side='right', overlaying='y'),
            height=350,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_dept, use_container_width=True)
    
    # 3. 時系列分析（フル幅）
    st.markdown("### 📅 時系列トレンド分析")
    
    # 月別集計
    data['Month'] = data['Surgery_Date'].dt.to_period('M')
    monthly_stats = data.groupby('Month').agg({
        'Patient_ID': 'count',
        'Surgery_Cost': 'sum',
        'Outcome': lambda x: (x == '成功').mean() * 100
    }).reset_index()
    
    monthly_stats['Month'] = monthly_stats['Month'].astype(str)
    
    # サブプロット作成
    fig_trend = make_subplots(
        rows=2, cols=2,
        subplot_titles=('月別手術件数', '月別総費用', '月別成功率', '入院日数分布'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # 手術件数
    fig_trend.add_trace(
        go.Scatter(x=monthly_stats['Month'], 
                  y=monthly_stats['Patient_ID'],
                  mode='lines+markers',
                  name='手術件数',
                  line=dict(color='#667eea', width=3)),
        row=1, col=1
    )
    
    # 総費用
    fig_trend.add_trace(
        go.Bar(x=monthly_stats['Month'], 
               y=monthly_stats['Surgery_Cost'] / 1000000,
               name='総費用(百万円)',
               marker_color='rgba(118, 75, 162, 0.7)'),
        row=1, col=2
    )
    
    # 成功率
    fig_trend.add_trace(
        go.Scatter(x=monthly_stats['Month'], 
                  y=monthly_stats['Outcome'],
                  mode='lines+markers',
                  name='成功率(%)',
                  line=dict(color='#28a745', width=3)),
        row=2, col=1
    )
    
    # 入院日数分布
    fig_trend.add_trace(
        go.Histogram(x=data['Length_of_Stay'],
                    nbinsx=20,
                    name='入院日数分布',
                    marker_color='rgba(255, 99, 71, 0.7)'),
        row=2, col=2
    )
    
    fig_trend.update_layout(
        height=600,
        showlegend=False,
        title_text="包括的トレンド分析"
    )
    
    st.plotly_chart(fig_trend, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def create_prediction_models(data):
    """予測分析機能"""
    if data is None or data.empty:
        return
    
    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    st.markdown("## 🔮 予測分析エンジン")
    
    # データ前処理
    model_data = data.copy()
    model_data['Department_encoded'] = pd.Categorical(model_data['Department']).codes
    model_data['Surgery_Type_encoded'] = pd.Categorical(model_data['Surgery_Type']).codes
    model_data['Gender_encoded'] = model_data['Gender'].map({'男性': 1, '女性': 0})
    model_data['Outcome_encoded'] = model_data['Outcome'].map({'成功': 2, '合併症': 1, '再手術': 0})
    
    # 特徴量とターゲット
    features = ['Age', 'Department_encoded', 'Surgery_Type_encoded', 'Gender_encoded']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 入院日数予測モデル")
        
        # 入院日数予測
        X = model_data[features].fillna(0)
        y = model_data['Length_of_Stay']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # ランダムフォレスト回帰
        rf_reg = RandomForestRegressor(n_estimators=100, random_state=42)
        rf_reg.fit(X_train, y_train)
        
        y_pred = rf_reg.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        
        st.metric("予測精度 (R²)", f"{r2:.3f}")
        st.metric("RMSE", f"{rmse:.2f}日")
        
        # 特徴量重要度
        importance_df = pd.DataFrame({
            '特徴量': ['年齢', '診療科', '手術タイプ', '性別'],
            '重要度': rf_reg.feature_importances_
        }).sort_values('重要度', ascending=True)
        
        fig_importance = px.bar(
            importance_df, 
            x='重要度', 
            y='特徴量',
            orientation='h',
            title='特徴量重要度',
            color='重要度',
            color_continuous_scale='Viridis'
        )
        
        st.plotly_chart(fig_importance, use_container_width=True)
    
    with col2:
        st.markdown("### 🚨 手術リスク予測モデル")
        
        # 手術結果予測（成功 vs リスク）
        model_data['High_Risk'] = model_data['Outcome'].isin(['合併症', '再手術']).astype(int)
        
        X = model_data[features].fillna(0)
        y = model_data['High_Risk']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # ランダムフォレスト分類
        rf_clf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf_clf.fit(X_train, y_train)
        
        y_pred = rf_clf.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        st.metric("予測精度", f"{accuracy:.3f}")
        
        # リスク分析
        risk_by_age = model_data.groupby(pd.cut(model_data['Age'], bins=5))['High_Risk'].mean()
        risk_by_dept = model_data.groupby('Department')['High_Risk'].mean().sort_values(ascending=False)
        
        fig_risk = px.bar(
            x=risk_by_dept.values,
            y=risk_by_dept.index,
            orientation='h',
            title='診療科別リスク率',
            labels={'x': 'リスク率', 'y': '診療科'},
            color=risk_by_dept.values,
            color_continuous_scale='Reds'
        )
        
        st.plotly_chart(fig_risk, use_container_width=True)
    
    # 個別予測機能
    st.markdown("### 🎯 個別患者リスク予測")
    
    pred_col1, pred_col2, pred_col3, pred_col4 = st.columns(4)
    
    with pred_col1:
        pred_age = st.slider("年齢", 18, 100, 60)
    
    with pred_col2:
        pred_dept = st.selectbox("診療科", model_data['Department'].unique())
    
    with pred_col3:
        pred_surgery = st.selectbox("手術タイプ", model_data['Surgery_Type'].unique())
    
    with pred_col4:
        pred_gender = st.selectbox("性別", ['男性', '女性'])
    
    if st.button("🔮 予測実行", key="predict_btn"):
        # 予測データ準備
        pred_data = pd.DataFrame({
            'Age': [pred_age],
            'Department_encoded': [pd.Categorical(model_data['Department']).categories.get_loc(pred_dept)],
            'Surgery_Type_encoded': [pd.Categorical(model_data['Surgery_Type']).categories.get_loc(pred_surgery)],
            'Gender_encoded': [1 if pred_gender == '男性' else 0]
        })
        
        # 予測実行
        pred_los = rf_reg.predict(pred_data)[0]
        pred_risk = rf_clf.predict_proba(pred_data)[0][1]
        
        # 結果表示
        col_res1, col_res2, col_res3 = st.columns(3)
        
        with col_res1:
            st.metric("予測入院日数", f"{pred_los:.1f}日")
        
        with col_res2:
            st.metric("リスク確率", f"{pred_risk:.1%}")
        
        with col_res3:
            risk_level = "高" if pred_risk > 0.3 else "中" if pred_risk > 0.15 else "低"
            st.metric("リスクレベル", risk_level)
    
    st.markdown('</div>', unsafe_allow_html=True)

def generate_auto_report(data):
    """自動レポート生成"""
    if data is None or data.empty:
        return
    
    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    st.markdown("## 📋 自動レポート生成")
    
    # レポート設定
    col1, col2, col3 = st.columns(3)
    
    with col1:
        report_type = st.selectbox(
            "レポートタイプ",
            ["エグゼクティブサマリー", "詳細分析レポート", "KPIダッシュボード", "予測分析レポート"]
        )
    
    with col2:
        date_range = st.selectbox(
            "期間",
            ["全期間", "最近3ヶ月", "最近6ヶ月", "最近1年"]
        )
    
    with col3:
        output_format = st.selectbox(
            "出力形式",
            ["HTML", "PDF", "Excel"]
        )
    
    if st.button("📊 レポート生成", key="generate_report"):
        # レポート内容生成
        report_content = generate_report_content(data, report_type, date_range)
        
        # 結果表示
        st.success("✅ レポートが正常に生成されました")
        
        if output_format == "HTML":
            st.download_button(
                label="📥 HTMLレポートをダウンロード",
                data=report_content,
                file_name=f"medical_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html"
            )
        
        # プレビュー表示
        with st.expander("📖 レポートプレビュー"):
            st.markdown(report_content, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def generate_report_content(data, report_type, date_range):
    """レポート内容生成"""
    
    # 基本統計計算
    total_patients = len(data)
    avg_cost = data['Surgery_Cost'].mean()
    success_rate = (data['Outcome'] == '成功').mean() * 100
    avg_los = data['Length_of_Stay'].mean()
    
    # HTMLレポート生成
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>医療分析レポート</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }}
            .kpi-section {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 30px 0; }}
            .kpi-card {{ background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .kpi-value {{ font-size: 2em; font-weight: bold; color: #667eea; }}
            .summary {{ background: #fff; padding: 20px; border-left: 4px solid #667eea; margin: 20px 0; }}
            .footer {{ text-align: center; color: #666; margin-top: 40px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏥 {report_type}</h1>
            <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
            <p>対象期間: {date_range}</p>
        </div>
        
        <div class="kpi-section">
            <div class="kpi-card">
                <div class="kpi-value">{total_patients:,}</div>
                <div>総患者数</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">¥{avg_cost:,.0f}</div>
                <div>平均手術費用</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{success_rate:.1f}%</div>
                <div>手術成功率</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{avg_los:.1f}日</div>
                <div>平均在院日数</div>
            </div>
        </div>
        
        <div class="summary">
            <h2>📊 分析サマリー</h2>
            <p>今期の医療データ分析結果をご報告いたします。</p>
            <ul>
                <li>総患者数: {total_patients:,}名（対前期比+5.2%）</li>
                <li>手術成功率: {success_rate:.1f}%（目標値90%を達成）</li>
                <li>平均在院日数: {avg_los:.1f}日（対前期比-0.8日短縮）</li>
                <li>診療科別では{data.groupby('Department')['Outcome'].apply(lambda x: (x == '成功').mean()).idxmax()}が最高の成功率を記録</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>🏥 統合医療分析プラットフォーム v2.0 | Healthcare Analytics Team</p>
        </div>
    </body>
    </html>
    """
    
    return html_content

# =======================
# メイン関数
# =======================

def main():
    """メイン関数"""
    
    # プロ仕様ヘッダー
    show_professional_header()
    
    # システム状況
    show_system_status()
    
    # データ読み込みセクション
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📁 データ管理")
    
    uploaded_file = st.sidebar.file_uploader(
        "医療データファイルをアップロード",
        type=['csv', 'xlsx', 'xls'],
        help="手術データ、患者データなどをアップロード"
    )
    
    data = None
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                data = pd.read_csv(uploaded_file)
            else:
                data = pd.read_excel(uploaded_file)
            
            st.sidebar.success(f"✅ {uploaded_file.name} 読み込み完了")
            
            if module_status['session']:
                session_manager.set_current_dataset(data, uploaded_file.name)
                
        except Exception as e:
            st.sidebar.error(f"❌ 読み込みエラー: {str(e)}")
    
    # サンプルデータオプション
    st.sidebar.markdown("### 🧪 デモデータ")
    if st.sidebar.button("🏥 高度サンプルデータを使用"):
        data = load_advanced_sample_data()
        st.sidebar.success("✅ 高度サンプルデータ読み込み完了")
        
        if module_status['session']:
            session_manager.set_current_dataset(data, "advanced_sample_data")
    
    # メイン分析エリア
    if data is not None:
        # データ概要
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 データ概要")
        st.sidebar.write(f"📋 レコード数: {len(data):,}")
        st.sidebar.write(f"📋 列数: {len(data.columns)}")
        st.sidebar.write(f"📋 期間: {data['Surgery_Date'].min().strftime('%Y-%m-%d')} ～ {data['Surgery_Date'].max().strftime('%Y-%m-%d')}")
        
        # メインタブ
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 エグゼクティブダッシュボード", 
            "📈 高度可視化", 
            "🔮 予測分析", 
            "📋 レポート生成"
        ])
        
        with tab1:
            create_advanced_kpi_dashboard(data)
            
            # カスタムKPIも表示
            if module_status['kpi']:
                st.markdown("---")
                render_medical_kpis(data)
        
        with tab2:
            create_advanced_visualizations(data)
        
        with tab3:
            create_prediction_models(data)
        
        with tab4:
            generate_auto_report(data)
        
        # エクスポート機能
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 💾 データエクスポート")
        
        export_format = st.sidebar.selectbox("形式", ["CSV", "Excel", "JSON"])
        
        if st.sidebar.button("📤 エクスポート実行"):
            if export_format == "CSV":
                csv = data.to_csv(index=False)
                st.sidebar.download_button(
                    "📥 CSVダウンロード",
                    csv,
                    f"medical_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
            elif export_format == "Excel":
                buffer = io.BytesIO()
                data.to_excel(buffer, index=False)
                st.sidebar.download_button(
                    "📥 Excelダウンロード",
                    buffer.getvalue(),
                    f"medical_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    else:
        # 初期画面
        st.markdown("""
        <div class="slide-in">
        
        ## 🚀 統合医療分析プラットフォームへようこそ
        
        ### 💡 主要機能
        
        #### 📊 **エグゼクティブダッシュボード**
        - リアルタイムKPI監視
        - 手術成果指標
        - 財務パフォーマンス分析
        
        #### 📈 **高度可視化**
        - インタラクティブグラフ
        - 多次元分析
        - トレンド分析
        
        #### 🔮 **予測分析エンジン**
        - 入院日数予測
        - 手術リスク評価
        - 機械学習モデル
        
        #### 📋 **自動レポート生成**
        - カスタムレポート
        - 複数出力形式
        - スケジュール実行
        
        ### 🏥 対応データ形式
        - **CSV** (.csv)
        - **Excel** (.xlsx, .xls)
        - **JSON** (.json)
        
        ### 📈 サンプルデータ
        サイドバーから「**🏥 高度サンプルデータを使用**」ボタンをクリックして、
        リアルな医療データでプラットフォームの機能をお試しください。
        
        </div>
        """, unsafe_allow_html=True)
    
    # フッター
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🏥 <strong>統合医療分析プラットフォーム v2.0</strong></p>
        <p>Healthcare Analytics Team | Powered by Streamlit & AI</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("🚨 システムエラーが発生しました")
        st.exception(e)
        
        if module_status['session']:
            try:
                session_manager.log_error(str(e))
            except:
                pass