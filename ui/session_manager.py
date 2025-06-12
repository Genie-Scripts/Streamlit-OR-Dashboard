# ui/session_manager.py
"""
セッション状態管理モジュール
アプリケーションのセッション状態を一元管理
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import logging

from data_persistence import auto_load_data

logger = logging.getLogger(__name__)


class SessionManager:
    """セッション状態を管理するクラス"""
    
    # セッションキーの定数定義
    SESSION_KEYS = {
        'processed_df': 'processed_df',
        'target_dict': 'target_dict', 
        'latest_date': 'latest_date',
        'current_view': 'current_view',
        'data_loaded_from_file': 'data_loaded_from_file',
        'data_source': 'data_source',
        'auto_load_attempted': 'auto_load_attempted'
    }
    
    @staticmethod
    def initialize_session_state() -> None:
        """セッション状態を初期化"""
        try:
            # 基本的なセッション変数の初期化
            if SessionManager.SESSION_KEYS['processed_df'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['processed_df']] = pd.DataFrame()
            
            if SessionManager.SESSION_KEYS['target_dict'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['target_dict']] = {}
            
            if SessionManager.SESSION_KEYS['latest_date'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['latest_date']] = None
            
            if SessionManager.SESSION_KEYS['current_view'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['current_view']] = 'ダッシュボード'
            
            if SessionManager.SESSION_KEYS['data_loaded_from_file'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['data_loaded_from_file']] = False
            
            if SessionManager.SESSION_KEYS['data_source'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['data_source']] = 'unknown'
            
            # アプリ起動時の自動データ読み込み
            if not st.session_state.get(SessionManager.SESSION_KEYS['auto_load_attempted'], False):
                SessionManager._attempt_auto_load()
                
        except Exception as e:
            logger.error(f"セッション状態初期化エラー: {e}")
            st.error(f"セッション初期化に失敗しました: {e}")

    @staticmethod
    def _attempt_auto_load() -> None:
        """自動データ読み込みを試行"""
        try:
            st.session_state[SessionManager.SESSION_KEYS['auto_load_attempted']] = True
            
            if auto_load_data():
                st.session_state[SessionManager.SESSION_KEYS['data_loaded_from_file']] = True
                st.session_state[SessionManager.SESSION_KEYS['data_source']] = 'auto_loaded'
                
                # データがロードされた場合、セッション変数を更新
                df = st.session_state.get('df')
                target_data = st.session_state.get('target_data')
                
                if df is not None and not df.empty:
                    st.session_state[SessionManager.SESSION_KEYS['processed_df']] = df
                    st.session_state[SessionManager.SESSION_KEYS['target_dict']] = target_data or {}
                    
                    if '手術実施日_dt' in df.columns:
                        st.session_state[SessionManager.SESSION_KEYS['latest_date']] = df['手術実施日_dt'].max()
                        
                logger.info("自動データ読み込み完了")
            else:
                logger.info("自動データ読み込み: 利用可能なデータなし")
                
        except Exception as e:
            logger.error(f"自動データ読み込みエラー: {e}")

    @staticmethod
    def get_processed_df() -> pd.DataFrame:
        """処理済みデータフレームを取得"""
        return st.session_state.get(SessionManager.SESSION_KEYS['processed_df'], pd.DataFrame())
    
    @staticmethod
    def set_processed_df(df: pd.DataFrame) -> None:
        """処理済みデータフレームを設定"""
        st.session_state[SessionManager.SESSION_KEYS['processed_df']] = df
        
        # 最新日付も更新
        if not df.empty and '手術実施日_dt' in df.columns:
            st.session_state[SessionManager.SESSION_KEYS['latest_date']] = df['手術実施日_dt'].max()

    @staticmethod
    def get_target_dict() -> Dict[str, Any]:
        """目標辞書を取得"""
        return st.session_state.get(SessionManager.SESSION_KEYS['target_dict'], {})
    
    @staticmethod
    def set_target_dict(target_dict: Dict[str, Any]) -> None:
        """目標辞書を設定"""
        st.session_state[SessionManager.SESSION_KEYS['target_dict']] = target_dict

    @staticmethod
    def get_latest_date() -> Optional[datetime]:
        """最新日付を取得"""
        return st.session_state.get(SessionManager.SESSION_KEYS['latest_date'])
    
    @staticmethod
    def set_latest_date(date: datetime) -> None:
        """最新日付を設定"""
        st.session_state[SessionManager.SESSION_KEYS['latest_date']] = date

    @staticmethod
    def get_current_view() -> str:
        """現在のビューを取得"""
        return st.session_state.get(SessionManager.SESSION_KEYS['current_view'], 'ダッシュボード')
    
    @staticmethod
    def set_current_view(view: str) -> None:
        """現在のビューを設定"""
        st.session_state[SessionManager.SESSION_KEYS['current_view']] = view

    @staticmethod
    def get_data_source() -> str:
        """データソースを取得"""
        return st.session_state.get(SessionManager.SESSION_KEYS['data_source'], 'unknown')
    
    @staticmethod
    def set_data_source(source: str) -> None:
        """データソースを設定"""
        st.session_state[SessionManager.SESSION_KEYS['data_source']] = source

    @staticmethod
    def is_data_loaded() -> bool:
        """データが読み込まれているかチェック"""
        df = SessionManager.get_processed_df()
        return df is not None and not df.empty

    @staticmethod
    def get_data_info() -> Dict[str, Any]:
        """データ情報のサマリーを取得"""
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        latest_date = SessionManager.get_latest_date()
        data_source = SessionManager.get_data_source()
        
        return {
            'has_data': SessionManager.is_data_loaded(),
            'record_count': len(df) if df is not None else 0,
            'has_target': bool(target_dict),
            'latest_date': latest_date.strftime('%Y/%m/%d') if latest_date else None,
            'data_source': data_source,
            'columns': list(df.columns) if df is not None and not df.empty else []
        }

    @staticmethod
    def clear_session_data() -> None:
        """セッションデータをクリア"""
        try:
            for key in SessionManager.SESSION_KEYS.values():
                if key in st.session_state:
                    if key == SessionManager.SESSION_KEYS['current_view']:
                        st.session_state[key] = 'ダッシュボード'
                    elif key == SessionManager.SESSION_KEYS['processed_df']:
                        st.session_state[key] = pd.DataFrame()
                    elif key == SessionManager.SESSION_KEYS['target_dict']:
                        st.session_state[key] = {}
                    else:
                        del st.session_state[key]
            
            logger.info("セッションデータをクリアしました")
            
        except Exception as e:
            logger.error(f"セッションデータクリアエラー: {e}")

    @staticmethod
    def validate_session_data() -> Tuple[bool, str]:
        """セッションデータの整合性をチェック"""
        try:
            df = SessionManager.get_processed_df()
            latest_date = SessionManager.get_latest_date()
            
            # データフレームの検証
            if df is not None and not df.empty:
                # 必要な列の存在確認
                required_columns = ['手術実施日_dt', '実施診療科', 'is_gas_20min']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    return False, f"必要な列が不足しています: {missing_columns}"
                
                # 日付の整合性確認
                if latest_date and '手術実施日_dt' in df.columns:
                    actual_latest = df['手術実施日_dt'].max()
                    if actual_latest != latest_date:
                        # 自動修正
                        SessionManager.set_latest_date(actual_latest)
                        logger.warning(f"最新日付を修正: {latest_date} -> {actual_latest}")
            
            return True, "セッションデータは正常です"
            
        except Exception as e:
            logger.error(f"セッションデータ検証エラー: {e}")
            return False, f"検証エラー: {e}"