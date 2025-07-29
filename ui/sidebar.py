# ui/sidebar.py

import streamlit as st
import pytz
from datetime import datetime
import pandas as pd  # <--- 修正

from ui.session_manager import SessionManager

try:
    from config.high_score_config import create_high_score_sidebar_section
    EVALUATION_AVAILABLE = True
except ImportError:
    EVALUATION_AVAILABLE = False
    def create_high_score_sidebar_section():
        st.sidebar.header("🏆 診療科評価")
        st.sidebar.info("評価機能は準備中です")

try:
    from reporting.surgery_github_publisher import create_surgery_github_publisher_interface
    GITHUB_PUBLISHER_AVAILABLE = True
except ImportError:
    GITHUB_PUBLISHER_AVAILABLE = False
    def create_surgery_github_publisher_interface():
        st.sidebar.header("🌐 GitHub公開")
        st.sidebar.info("公開機能は準備中です")


class SidebarManager:
    """サイドバーを管理するクラス"""
    
    NAVIGATION_VIEWS = [
        "ダッシュボード", "診療科別分析", "術者別分析",
        "病院全体分析", "将来予測", "データ管理", "データアップロード"
    ]
    
    @staticmethod
    def render() -> None:
        """サイドバー全体を描画"""
        with st.sidebar:
            SidebarManager._render_header()
            SidebarManager._render_data_status()
            SidebarManager._render_analysis_settings() # <--- 修正
            SidebarManager._render_navigation()
            create_high_score_sidebar_section()
            create_surgery_github_publisher_interface()
            SidebarManager._render_footer()

    @staticmethod
    def _render_header() -> None:
        st.title("🏥 手術ダッシュボード")
        st.caption("評価方式: 週報ランキング (100点満点)")
        st.markdown("---")

    @staticmethod
    def _render_data_status() -> None:
        st.subheader("📊 データ状況")
        if SessionManager.is_data_loaded():
            df = SessionManager.get_processed_df()
            target_dict = SessionManager.get_target_dict()

            st.success("✅ データ読み込み済み")
            st.metric("手術件数", f"{len(df):,}件")
            if '手術実施日_dt' in df.columns and not df.empty:
                min_date = df['手術実施日_dt'].min().strftime('%Y/%m/%d')
                max_date = df['手術実施日_dt'].max().strftime('%Y/%m/%d')
                st.caption(f"期間: {min_date} - {max_date}")

            if target_dict:
                st.success("✅ 目標値設定済み")
                st.metric("設定診療科数", f"{len(target_dict)}科")
            else:
                st.info("🎯 目標値未設定")
        else:
            st.warning("⚠️ データ未読み込み")
        
        st.markdown("---")
        
    # === ▼▼▼ 修正箇所 ▼▼▼ ===
    @staticmethod
    def _render_analysis_settings() -> None:
        """分析設定セクションを描画"""
        st.subheader("⚙️ 分析設定")
    
        # セッションから現在の日付を取得、なければ今日の日付
        base_date_val = SessionManager.get_analysis_base_date()
        if base_date_val is None:
            base_date_val = datetime.now().date()
    
        # 日付入力ウィジェットを配置
        selected_date = st.date_input(
            "分析基準日",
            value=base_date_val,
            help="分析期間を計算する際の基準日。データがない日も考慮して、分析したい時点の日付を選択してください。"
        )
    
        # 選択された日付をセッションに保存
        if selected_date:
            SessionManager.set_analysis_base_date(pd.to_datetime(selected_date))
    
        st.markdown("---")
    # === ▲▲▲ 修正箇所 ▲▲▲ ===

    @staticmethod
    def _render_navigation() -> None:
        st.subheader("📍 ナビゲーション")
        current_view = SessionManager.get_current_view()
        
        try:
            current_index = SidebarManager.NAVIGATION_VIEWS.index(current_view)
        except ValueError:
            current_index = 0
        
        selected_view = st.radio(
            "ページ選択",
            SidebarManager.NAVIGATION_VIEWS,
            index=current_index,
            key="navigation_radio"
        )
        
        if selected_view != current_view:
            SessionManager.set_current_view(selected_view)
            st.rerun()

    @staticmethod
    def _render_footer() -> None:
        st.markdown("---")
        jst = pytz.timezone('Asia/Tokyo')
        current_time = datetime.now(jst).strftime('%Y-%m-%d %H:%M')
        st.caption(f"© 2025 Surgery Analytics v2.2 | {current_time}")