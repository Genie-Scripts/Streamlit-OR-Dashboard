# utils/session_manager.py - セッション管理モジュール（シンプル版）
import streamlit as st
from typing import Any, Dict

class SessionManager:
    """Streamlitセッション状態の統一管理クラス"""
    
    # セッション状態のキー定義
    SESSION_KEYS = {
        'df_gas': None,
        'base_df': None,
        'target_dict': {},
        'latest_date': None,
        'current_view': 'dashboard',
        'data_processed': False
    }
    
    @staticmethod
    def init_session_state():
        """セッション状態を初期化"""
        for key, default_value in SessionManager.SESSION_KEYS.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """セッション状態の値を取得"""
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key: str, value: Any) -> None:
        """セッション状態の値を設定"""
        st.session_state[key] = value