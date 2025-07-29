# app.py
"""
手術ダッシュボード メインアプリケーション
"""

import streamlit as st
import logging
from ui.session_manager import SessionManager
from ui.page_router import PageRouter
from ui.sidebar import SidebarManager  # SidebarManagerをインポート

# 基本設定
st.set_page_config(
    page_title="手術ダッシュボード",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """メインアプリケーション"""
    try:
        # セッション初期化
        SessionManager.initialize_session_state()

        # サイドバーの描画をSidebarManagerに一任する
        SidebarManager.render()
        
        # メインコンテンツ表示
        router = PageRouter()
        router.render_current_page()
        
    except Exception as e:
        logger.error(f"アプリケーション実行エラー: {e}", exc_info=True)
        st.error(f"アプリケーションエラーが発生しました: {e}")
        if st.checkbox("デバッグ情報を表示"):
            st.exception(e)

# アプリケーション実行
if __name__ == "__main__":
    main()