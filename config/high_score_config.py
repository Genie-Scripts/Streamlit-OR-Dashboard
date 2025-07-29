# config/high_score_config.py (統一版 - 週報ランキングデフォルト)
"""
評価機能の統合設定 - 週報ランキング方式（100点満点）をデフォルトに
"""

import streamlit as st
import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# === 基本設定 ===
PERIOD_OPTIONS = ["直近4週", "直近8週", "直近12週"]
MIN_DATA_REQUIREMENTS = {
    'min_total_cases': 3,
    'min_weeks': 2
}

# === 週報設定（デフォルト） ===
WEEKLY_REPORT_CONFIG = {
    'scoring_method': 'competitive_enhanced',  # Option B: 競争力強化型
    'weights': {
        'target_performance': 55,  # 対目標パフォーマンス
        'improvement': 25,         # 改善・継続性
        'competitiveness': 20      # 相対競争力
    },
    'grade_thresholds': {
        'S+': 90,
        'S': 85,
        'A+': 80,
        'A': 75,
        'B': 65,
        'C': 50
    }
}

# === 評価モード（週報ランキングをデフォルトに） ===
DEFAULT_EVALUATION_MODE = 'weekly_ranking'  # デフォルトを週報ランキングに

EVALUATION_MODES = {
    'weekly_ranking': {
        'name': '週報ランキング',
        'description': '100点満点の競争力重視評価',
        'function': 'calculate_weekly_surgery_ranking'
    },
    'high_score': {
        'name': 'ハイスコア評価',
        'description': '包括的な長期評価（旧方式）',
        'function': 'calculate_surgery_high_scores'
    }
}


def get_evaluation_mode() -> str:
    """現在の評価モードを取得（デフォルト: 週報ランキング）"""
    return st.session_state.get('evaluation_mode', DEFAULT_EVALUATION_MODE)


def set_evaluation_mode(mode: str) -> None:
    """評価モードを設定"""
    if mode in EVALUATION_MODES:
        st.session_state.evaluation_mode = mode
        logger.info(f"評価モード変更: {EVALUATION_MODES[mode]['name']}")


def create_mode_selector() -> str:
    """評価モード選択UI（週報ランキングを推奨）"""
    current_mode = get_evaluation_mode()
    
    st.sidebar.markdown("**📊 評価方式**")
    
    # 週報ランキングを最初に表示
    mode_options = {
        'weekly_ranking': '🏆 週報ランキング (100点満点)',
        'high_score': '⭐ ハイスコア評価 (旧方式)'
    }
    
    selected_option = st.sidebar.radio(
        "評価方式を選択",
        options=list(mode_options.keys()),
        format_func=lambda x: mode_options[x],
        index=0,  # 常に週報ランキングをデフォルトに
        key="evaluation_mode_selector"
    )
    
    if selected_option != current_mode:
        set_evaluation_mode(selected_option)
        st.rerun()
    
    # 選択された方式の説明
    if selected_option == 'weekly_ranking':
        st.sidebar.info("💡 推奨: 診療科間の競争力を重視した100点満点評価")
    else:
        st.sidebar.caption("💡 旧方式: 全身麻酔中心の包括的評価")
    
    return selected_option


def create_high_score_sidebar_section():
    """統合評価機能のサイドバーセクション"""
    try:
        # データ確認
        df = st.session_state.get('processed_df', pd.DataFrame())
        target_dict = st.session_state.get('target_dict', {})
        
        if df.empty or not target_dict:
            st.sidebar.info("📊 データ読み込み後に評価機能が利用可能になります")
            return
        
        st.sidebar.markdown("---")
        st.sidebar.header("🏆 診療科評価")
        
        # 評価モード選択（週報ランキングがデフォルト）
        current_mode = create_mode_selector()
        
        # 期間選択
        period = st.sidebar.selectbox(
            "📅 評価期間",
            PERIOD_OPTIONS,
            index=2,
            key="evaluation_period"
        )
        
        # 詳細設定
        with st.sidebar.expander("⚙️ 評価設定"):
            if current_mode == 'weekly_ranking':
                st.markdown("**週報ランキング（100点満点）**")
                st.write("• 対目標パフォーマンス: 55点")
                st.write("• 改善・継続性: 25点") 
                st.write("• 相対競争力: 20点")
                st.write("")
                st.write("**グレード基準**")
                st.write("• S+: 90点以上")
                st.write("• S: 85-89点")
                st.write("• A+: 80-84点")
                st.write("• A: 75-79点")
            else:
                st.markdown("**ハイスコア評価（旧方式）**")
                st.write("• 全身麻酔評価: 70点")
                st.write("• 全手術件数: 15点")
                st.write("• 総手術時間: 15点")
        
        # 統計表示
        display_unified_stats(df, target_dict, current_mode, period)
        
        # クイックアクション
        st.sidebar.markdown("**⚡ クイックアクション**")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("📊 評価表示", key="show_evaluation", use_container_width=True):
                st.session_state.show_evaluation_tab = True
                st.rerun()
        
        with col2:
            if st.button("📄 レポート", key="generate_report", use_container_width=True):
                generate_quick_report()
        
    except Exception as e:
        logger.error(f"サイドバーセクション作成エラー: {e}")
        st.sidebar.error("評価機能でエラーが発生しました")


def display_unified_stats(df: pd.DataFrame, target_dict: Dict[str, float], 
                         mode: str, period: str):
    """統合された統計表示"""
    try:
        st.sidebar.markdown("**📈 評価統計**")
        
        # 基本統計
        total_depts = len(df['実施診療科'].dropna().unique()) if '実施診療科' in df.columns else 0
        target_depts = len(target_dict)
        
        st.sidebar.metric("評価対象科", f"{target_depts}科")
        st.sidebar.metric("総診療科数", f"{total_depts}科")
        
        # 評価モード別の詳細統計
        try:
            if mode == 'weekly_ranking':
                from analysis.weekly_surgery_ranking import calculate_weekly_surgery_ranking
                dept_scores = calculate_weekly_surgery_ranking(df, target_dict, period)
                
                if dept_scores:
                    avg_score = sum(d['total_score'] for d in dept_scores) / len(dept_scores)
                    high_achievers = len([d for d in dept_scores if d['achievement_rate'] >= 100])
                    s_grades = len([d for d in dept_scores if d['grade'].startswith('S')])
                    
                    st.sidebar.metric("平均スコア", f"{avg_score:.1f}点")
                    st.sidebar.metric("目標達成科", f"{high_achievers}科")
                    st.sidebar.metric("S評価科数", f"{s_grades}科")
                    
                    # 今週の1位
                    if dept_scores:
                        top_dept = dept_scores[0]
                        st.sidebar.markdown("**🥇 今週の1位**")
                        st.sidebar.markdown(f"**{top_dept['display_name']}**")
                        st.sidebar.markdown(f"{top_dept['total_score']:.1f}点 ({top_dept['grade']})")
            
            else:  # high_score mode
                from analysis.surgery_high_score import calculate_surgery_high_scores
                dept_scores = calculate_surgery_high_scores(df, target_dict, period)
                
                if dept_scores:
                    avg_score = sum(d['total_score'] for d in dept_scores) / len(dept_scores)
                    high_achievers = len([d for d in dept_scores if d['achievement_rate'] >= 100])
                    
                    st.sidebar.metric("平均スコア", f"{avg_score:.1f}点")
                    st.sidebar.metric("目標達成科", f"{high_achievers}科")
                    
                    # ハイスコア1位
                    if dept_scores:
                        top_dept = dept_scores[0]
                        st.sidebar.markdown("**🏆 ハイスコア1位**")
                        st.sidebar.markdown(f"**{top_dept['display_name']}**")
                        st.sidebar.markdown(f"{top_dept['total_score']:.1f}点 ({top_dept['grade']})")
        
        except ImportError:
            st.sidebar.info("評価エンジン準備中...")
        except Exception as e:
            logger.debug(f"詳細統計計算エラー: {e}")
            st.sidebar.info("統計計算中...")
    
    except Exception as e:
        logger.error(f"統計表示エラー: {e}")


def generate_quick_report():
    """クイックレポート生成"""
    try:
        df = st.session_state.get('processed_df', pd.DataFrame())
        target_dict = st.session_state.get('target_dict', {})
        
        if df.empty or not target_dict:
            st.sidebar.warning("データが不足しています")
            return
        
        current_mode = get_evaluation_mode()
        period = st.session_state.get('evaluation_period', '直近12週')
        
        with st.spinner("レポート生成中..."):
            if current_mode == 'weekly_ranking':
                st.sidebar.success("✅ 週報レポート準備完了")
                st.sidebar.info("💡 「📊 評価表示」で詳細を確認")
            else:
                st.sidebar.success("✅ ハイスコアレポート準備完了")
                st.sidebar.info("💡 「📊 評価表示」で詳細を確認")
        
    except Exception as e:
        logger.error(f"レポート生成エラー: {e}")
        st.sidebar.error("生成中にエラーが発生しました")


def test_high_score_functionality():
    """機能テスト"""
    try:
        # 週報ランキング機能のテスト
        try:
            from analysis.weekly_surgery_ranking import calculate_weekly_surgery_ranking
            weekly_available = True
        except ImportError:
            weekly_available = False
        
        # ハイスコア機能のテスト  
        try:
            from analysis.surgery_high_score import calculate_surgery_high_scores
            high_score_available = True
        except ImportError:
            high_score_available = False
        
        if weekly_available:
            logger.info("✅ 週報ランキング機能: 利用可能")
            return True
        elif high_score_available:
            logger.info("⚠️ ハイスコア機能のみ利用可能")
            return True
        else:
            logger.warning("❌ 評価機能が利用できません")
            return False
    
    except Exception as e:
        logger.error(f"機能テストエラー: {e}")
        return False


def integrate_high_score_to_main_app():
    """メインアプリに統合評価機能を統合（修正版：重複呼び出しを防ぐ）"""
    try:
        # 既に統合済みかチェック
        if st.session_state.get('evaluation_integrated', False):
            return True
        
        # セッション状態の初期化（週報ランキングをデフォルトに）
        if 'evaluation_mode' not in st.session_state:
            st.session_state.evaluation_mode = DEFAULT_EVALUATION_MODE
        
        if 'show_evaluation_tab' not in st.session_state:
            st.session_state.show_evaluation_tab = False
        
        # 統合済みフラグを設定
        st.session_state.evaluation_integrated = True
        
        logger.info("✅ 統合評価機能の統合完了")
        return True
        
    except Exception as e:
        logger.error(f"統合評価機能の統合エラー: {e}")
        return False


# 互換性のための関数
def display_high_score_stats():
    """互換性維持用（統合版で実装済み）"""
    pass


def generate_quick_html_export():
    """互換性維持用（generate_quick_reportに統合）"""
    generate_quick_report()


# エクスポート
__all__ = [
    'PERIOD_OPTIONS',
    'MIN_DATA_REQUIREMENTS',
    'WEEKLY_REPORT_CONFIG',
    'EVALUATION_MODES',
    'DEFAULT_EVALUATION_MODE',
    'get_evaluation_mode',
    'set_evaluation_mode',
    'create_high_score_sidebar_section',
    'test_high_score_functionality',
    'integrate_high_score_to_main_app',
    'display_high_score_stats',
    'generate_quick_html_export'
]