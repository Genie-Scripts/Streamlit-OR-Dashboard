# ui/session_manager.py (期間選択機能追加版)
"""
セッション状態管理モジュール
アプリケーションのセッション状態を一元管理（期間選択機能追加）
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
        'auto_load_attempted': 'auto_load_attempted',
        'analysis_base_date': 'analysis_base_date', # <--- 修正
        # 期間選択関連
        'period_selections': 'period_selections',
        'period_cache': 'period_cache'
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

            # === ▼▼▼ 修正箇所 ▼▼▼ ===
            if SessionManager.SESSION_KEYS['analysis_base_date'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['analysis_base_date']] = None
            # === ▲▲▲ 修正箇所 ▲▲▲ ===
            
            # 期間選択関連の初期化
            if SessionManager.SESSION_KEYS['period_selections'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['period_selections']] = {}
            
            if SessionManager.SESSION_KEYS['period_cache'] not in st.session_state:
                st.session_state[SessionManager.SESSION_KEYS['period_cache']] = {}
            
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
        return st.session_state.get(SessionManager.SESSION_KEYS['processed_df'], pd.DataFrame())
    
    @staticmethod
    def set_processed_df(df: pd.DataFrame) -> None:
        st.session_state[SessionManager.SESSION_KEYS['processed_df']] = df
        if not df.empty and '手術実施日_dt' in df.columns:
            st.session_state[SessionManager.SESSION_KEYS['latest_date']] = df['手術実施日_dt'].max()
        SessionManager.clear_period_cache()

    @staticmethod
    def get_target_dict() -> Dict[str, Any]:
        return st.session_state.get(SessionManager.SESSION_KEYS['target_dict'], {})
    
    @staticmethod
    def set_target_dict(target_dict: Dict[str, Any]) -> None:
        st.session_state[SessionManager.SESSION_KEYS['target_dict']] = target_dict

    @staticmethod
    def get_latest_date() -> Optional[datetime]:
        return st.session_state.get(SessionManager.SESSION_KEYS['latest_date'])
    
    @staticmethod
    def set_latest_date(date: datetime) -> None:
        st.session_state[SessionManager.SESSION_KEYS['latest_date']] = date

    @staticmethod
    def get_current_view() -> str:
        return st.session_state.get(SessionManager.SESSION_KEYS['current_view'], 'ダッシュボード')
    
    @staticmethod
    def set_current_view(view: str) -> None:
        st.session_state[SessionManager.SESSION_KEYS['current_view']] = view

    @staticmethod
    def get_data_source() -> str:
        return st.session_state.get(SessionManager.SESSION_KEYS['data_source'], 'unknown')
    
    @staticmethod
    def set_data_source(source: str) -> None:
        st.session_state[SessionManager.SESSION_KEYS['data_source']] = source

    # === ▼▼▼ 修正箇所 ▼▼▼ ===
    @staticmethod
    def get_analysis_base_date() -> Optional[datetime]:
        """分析基準日を取得"""
        return st.session_state.get(SessionManager.SESSION_KEYS['analysis_base_date'])

    @staticmethod
    def set_analysis_base_date(date: datetime) -> None:
        """分析基準日を設定"""
        st.session_state[SessionManager.SESSION_KEYS['analysis_base_date']] = date
    # === ▲▲▲ 修正箇所 ▲▲▲ ===

    @staticmethod
    def get_period_selection(page_name: str) -> str:
        period_selections = st.session_state.get(SessionManager.SESSION_KEYS['period_selections'], {})
        return period_selections.get(page_name, "直近4週")
    
    @staticmethod
    def set_period_selection(page_name: str, period: str) -> None:
        period_selections = st.session_state.get(SessionManager.SESSION_KEYS['period_selections'], {})
        period_selections[page_name] = period
        st.session_state[SessionManager.SESSION_KEYS['period_selections']] = period_selections
        SessionManager.clear_period_cache(page_name)
    
    @staticmethod
    def get_filtered_data(page_name: str, 
                         start_date: Optional[pd.Timestamp], 
                         end_date: Optional[pd.Timestamp]) -> pd.DataFrame:
        try:
            cache_key = f"{page_name}_{start_date}_{end_date}"
            period_cache = st.session_state.get(SessionManager.SESSION_KEYS['period_cache'], {})
            
            if cache_key in period_cache:
                return period_cache[cache_key]
            
            df = SessionManager.get_processed_df()
            
            if df.empty or start_date is None or end_date is None:
                filtered_df = df
            else:
                filtered_df = df[
                    (df['手術実施日_dt'] >= start_date) & 
                    (df['手術実施日_dt'] <= end_date)
                ]
            
            period_cache[cache_key] = filtered_df
            st.session_state[SessionManager.SESSION_KEYS['period_cache']] = period_cache
            return filtered_df
            
        except Exception as e:
            logger.error(f"フィルタデータ取得エラー: {e}")
            return SessionManager.get_processed_df()
    
    @staticmethod
    def clear_period_cache(page_name: Optional[str] = None) -> None:
        """期間キャッシュをクリア"""
        try:
            period_cache = st.session_state.get(SessionManager.SESSION_KEYS['period_cache'], {})
            
            if page_name:
                # 特定ページのキャッシュのみクリア
                keys_to_remove = [key for key in period_cache.keys() if key.startswith(page_name)]
                for key in keys_to_remove:
                    del period_cache[key]
                logger.debug(f"ページ {page_name} のキャッシュをクリア")
            else:
                # 全キャッシュクリア
                period_cache = {}
                logger.debug("全期間キャッシュをクリア")
            
            st.session_state[SessionManager.SESSION_KEYS['period_cache']] = period_cache
            
        except Exception as e:
            logger.error(f"期間キャッシュクリアエラー: {e}")
    
    @staticmethod
    def get_period_stats(page_name: str, 
                        start_date: Optional[pd.Timestamp], 
                        end_date: Optional[pd.Timestamp]) -> Dict[str, Any]:
        """期間統計情報を取得"""
        try:
            filtered_df = SessionManager.get_filtered_data(page_name, start_date, end_date)
            
            if filtered_df.empty or not start_date or not end_date:
                return {
                    'total_cases': 0,
                    'gas_cases': 0,
                    'weekday_cases': 0,
                    'period_days': 0,
                    'weekdays': 0,
                    'daily_avg': 0.0
                }
            
            # 統計計算
            total_cases = len(filtered_df)
            gas_cases = len(filtered_df[filtered_df['is_gas_20min']]) if 'is_gas_20min' in filtered_df.columns else 0
            weekday_cases = len(filtered_df[filtered_df['is_weekday']]) if 'is_weekday' in filtered_df.columns else total_cases
            
            period_days = (end_date - start_date).days + 1
            weekdays = sum(1 for i in range(period_days) 
                          if (start_date + pd.Timedelta(days=i)).weekday() < 5)
            
            daily_avg = weekday_cases / weekdays if weekdays > 0 else 0.0
            
            return {
                'total_cases': total_cases,
                'gas_cases': gas_cases,
                'weekday_cases': weekday_cases,
                'period_days': period_days,
                'weekdays': weekdays,
                'daily_avg': daily_avg
            }
            
        except Exception as e:
            logger.error(f"期間統計計算エラー: {e}")
            return {}

    # === 基本機能メソッド ===
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
                    elif key == SessionManager.SESSION_KEYS['period_selections']:
                        st.session_state[key] = {}
                    elif key == SessionManager.SESSION_KEYS['period_cache']:
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
    
    @staticmethod
    def get_cache_info() -> Dict[str, Any]:
        """キャッシュ情報を取得（デバッグ用）"""
        try:
            period_cache = st.session_state.get(SessionManager.SESSION_KEYS['period_cache'], {})
            period_selections = st.session_state.get(SessionManager.SESSION_KEYS['period_selections'], {})
            
            return {
                'cache_count': len(period_cache),
                'cache_keys': list(period_cache.keys()),
                'period_selections': period_selections,
                'total_cached_records': sum(len(df) for df in period_cache.values() if isinstance(df, pd.DataFrame))
            }
        except Exception as e:
            logger.error(f"キャッシュ情報取得エラー: {e}")
            return {}