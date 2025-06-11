# app.py (新版) - リファクタリング後のメインエントリーポイント
"""
手術分析ダッシュボード - メインアプリケーション
リファクタリング版: UI層を完全分離した保守性の高いアーキテクチャ
"""

import streamlit as st
from config import style_config
from ui.session_manager import SessionManager
from ui.sidebar import SidebarManager
from ui.page_router import render_current_page
from ui.error_handler import ErrorHandler, setup_global_exception_handler

# ページ設定 (必ず最初に実行)
st.set_page_config(
    page_title="手術分析ダッシュボード", 
    page_icon="🏥", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

def main():
    """メインアプリケーション"""
    try:
        # グローバル例外ハンドラー設定
        setup_global_exception_handler()
        
        # スタイル読み込み
        style_config.load_dashboard_css()
        
        # セッション状態初期化
        SessionManager.initialize_session_state()
        
        # サイドバー描画
        SidebarManager.render()
        
        # 現在のページを描画
        render_current_page()
        
    except Exception as e:
        ErrorHandler.handle_error(e, "メインアプリケーション", show_details=True)

if __name__ == "__main__":  # ← ここを修正
    main()