# utils/session_manager.py - セッション管理モジュール
import streamlit as st
import pandas as pd
from typing import Any, Dict, Optional, List
from datetime import datetime

class SessionManager:
    """Streamlitセッション状態の統一管理クラス"""
    
    # セッション状態のキー定義
    SESSION_KEYS = {
        'df_gas': None,
        'base_df': None,
        'target_dict': {},
        'latest_date': None,
        'current_view': 'dashboard',
        'data_processed': False,
        'uploaded_files_info': [],
        'current_filters': {},
        'selected_department': None,
        'date_range': None,
        'analysis_cache': {},
        'user_preferences': {
            'auto_refresh': False,
            'show_incomplete_warning': True,
            'default_period': '直近4週',
            'default_analysis_type': '全身麻酔手術'
        }
    }
    
    @staticmethod
    def init_session_state():
        """セッション状態を初期化"""
        for key, default_value in SessionManager.SESSION_KEYS.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
        
        # 初期化完了フラグ
        if 'session_initialized' not in st.session_state:
            st.session_state['session_initialized'] = True
            print("セッション状態が初期化されました")
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """セッション状態の値を取得"""
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key: str, value: Any) -> None:
        """セッション状態の値を設定"""
        st.session_state[key] = value
    
    @staticmethod
    def update(updates: Dict[str, Any]) -> None:
        """複数の値を一括更新"""
        for key, value in updates.items():
            st.session_state[key] = value
    
    @staticmethod
    def clear_data():
        """データ関連セッションのクリア"""
        data_keys = [
            'df_gas', 'base_df', 'target_dict', 'latest_date', 
            'data_processed', 'uploaded_files_info', 'analysis_cache'
        ]
        for key in data_keys:
            if key in st.session_state:
                if key == 'target_dict':
                    st.session_state[key] = {}
                elif key in ['uploaded_files_info', 'analysis_cache']:
                    st.session_state[key] = {}
                else:
                    st.session_state[key] = None
        
        # データ処理フラグをリセット
        st.session_state['data_processed'] = False
        print("データ関連セッション状態がクリアされました")
    
    @staticmethod
    def clear_filters():
        """フィルター関連セッションのクリア"""
        filter_keys = ['current_filters', 'selected_department', 'date_range']
        for key in filter_keys:
            if key in st.session_state:
                if key == 'current_filters':
                    st.session_state[key] = {}
                else:
                    st.session_state[key] = None
    
    @staticmethod
    def is_data_loaded() -> bool:
        """データがロードされているかチェック"""
        df_gas = SessionManager.get('df_gas')
        return df_gas is not None and not df_gas.empty
    
    @staticmethod
    def is_target_loaded() -> bool:
        """目標データがロードされているかチェック"""
        target_dict = SessionManager.get('target_dict', {})
        return bool(target_dict)
    
    @staticmethod
    def get_data_info() -> Dict[str, Any]:
        """データの基本情報を取得"""
        if not SessionManager.is_data_loaded():
            return {
                'loaded': False,
                'record_count': 0,
                'date_range': None,
                'departments': [],
                'latest_date': None
            }
        
        df_gas = SessionManager.get('df_gas')
        latest_date = SessionManager.get('latest_date')
        
        return {
            'loaded': True,
            'record_count': len(df_gas),
            'date_range': {
                'start': df_gas['手術実施日_dt'].min().strftime('%Y/%m/%d'),
                'end': df_gas['手術実施日_dt'].max().strftime('%Y/%m/%d')
            },
            'departments': sorted(df_gas['実施診療科'].dropna().unique().tolist()),
            'latest_date': latest_date.strftime('%Y/%m/%d') if latest_date else None,
            'department_count': df_gas['実施診療科'].nunique()
        }
    
    @staticmethod
    def get_target_info() -> Dict[str, Any]:
        """目標データの基本情報を取得"""
        target_dict = SessionManager.get('target_dict', {})
        
        if not target_dict:
            return {
                'loaded': False,
                'department_count': 0,
                'departments': [],
                'total_target': 0
            }
        
        return {
            'loaded': True,
            'department_count': len(target_dict),
            'departments': list(target_dict.keys()),
            'total_target': sum(target_dict.values()),
            'targets': target_dict
        }
    
    @staticmethod
    def set_user_preference(key: str, value: Any) -> None:
        """ユーザー設定を保存"""
        preferences = SessionManager.get('user_preferences', {})
        preferences[key] = value
        SessionManager.set('user_preferences', preferences)
    
    @staticmethod
    def get_user_preference(key: str, default: Any = None) -> Any:
        """ユーザー設定を取得"""
        preferences = SessionManager.get('user_preferences', {})
        return preferences.get(key, default)
    
    @staticmethod
    def cache_analysis_result(cache_key: str, result: Any) -> None:
        """分析結果をキャッシュ"""
        cache = SessionManager.get('analysis_cache', {})
        cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now(),
            'data_hash': SessionManager._get_data_hash()
        }
        SessionManager.set('analysis_cache', cache)
    
    @staticmethod
    def get_cached_analysis(cache_key: str) -> Optional[Any]:
        """キャッシュされた分析結果を取得"""
        cache = SessionManager.get('analysis_cache', {})
        if cache_key not in cache:
            return None
        
        cached_item = cache[cache_key]
        current_hash = SessionManager._get_data_hash()
        
        # データハッシュが変わっている場合はキャッシュ無効
        if cached_item['data_hash'] != current_hash:
            del cache[cache_key]
            SessionManager.set('analysis_cache', cache)
            return None
        
        return cached_item['result']
    
    @staticmethod
    def _get_data_hash() -> str:
        """データのハッシュ値を計算（キャッシュ有効性チェック用）"""
        df_gas = SessionManager.get('df_gas')
        if df_gas is None or df_gas.empty:
            return "no_data"
        
        # データの基本情報からハッシュを生成
        data_info = f"{len(df_gas)}_{df_gas['手術実施日_dt'].min()}_{df_gas['手術実施日_dt'].max()}"
        return str(hash(data_info))
    
    @staticmethod
    def debug_session_state() -> Dict[str, Any]:
        """デバッグ用：セッション状態の概要を取得"""
        debug_info = {}
        
        for key in SessionManager.SESSION_KEYS.keys():
            value = SessionManager.get(key)
            if isinstance(value, pd.DataFrame):
                debug_info[key] = f"DataFrame({len(value)} rows)" if not value.empty else "Empty DataFrame"
            elif isinstance(value, dict):
                debug_info[key] = f"Dict({len(value)} items)"
            elif isinstance(value, list):
                debug_info[key] = f"List({len(value)} items)"
            else:
                debug_info[key] = str(type(value).__name__)
        
        return debug_info
    
    @staticmethod
    def export_session_summary() -> Dict[str, Any]:
        """セッション状態のサマリーを出力"""
        return {
            'data_info': SessionManager.get_data_info(),
            'target_info': SessionManager.get_target_info(),
            'current_view': SessionManager.get('current_view'),
            'user_preferences': SessionManager.get('user_preferences'),
            'session_debug': SessionManager.debug_session_state()
        }
