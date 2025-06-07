"""
🔧 セッション管理ユーティリティ

Streamlitセッション状態の管理、データのキャッシュ、
ユーザー設定の保存・復元機能を提供します。
"""

import streamlit as st
import pandas as pd
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionManager:
    """セッション状態を管理するクラス"""
    
    def __init__(self):
        self.session_id = self._generate_session_id()
        self._initialize_session()
    
    def _generate_session_id(self) -> str:
        """ユニークなセッションIDを生成"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]
    
    def _initialize_session(self):
        """セッション状態を初期化"""
        default_state = {
            'session_id': self.session_id,
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'user_preferences': {},
            'data_cache': {},
            'analysis_history': [],
            'current_dataset': None,
            'filtered_data': None,
            'selected_columns': [],
            'chart_settings': {},
            'export_settings': {},
            'page_state': 'home',
            'sidebar_collapsed': False,
            'theme': 'light',
            'language': 'ja',
            'notifications': [],
            'error_log': [],
            'performance_metrics': {}
        }
        
        for key, value in default_state.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def update_activity(self):
        """最終活動時間を更新"""
        st.session_state.last_activity = datetime.now()
    
    def is_session_expired(self, timeout_minutes: int = 60) -> bool:
        """セッションの有効期限をチェック"""
        if 'last_activity' not in st.session_state:
            return True
        
        last_activity = st.session_state.last_activity
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.now() - last_activity > timeout
    
    def clear_session(self):
        """セッションをクリア"""
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        self._initialize_session()
        logger.info("セッションがクリアされました")
    
    def save_user_preference(self, key: str, value: Any):
        """ユーザー設定を保存"""
        if 'user_preferences' not in st.session_state:
            st.session_state.user_preferences = {}
        
        st.session_state.user_preferences[key] = value
        self.update_activity()
        logger.info(f"ユーザー設定を保存: {key}")
    
    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """ユーザー設定を取得"""
        if 'user_preferences' not in st.session_state:
            return default
        
        return st.session_state.user_preferences.get(key, default)
    
    def cache_data(self, key: str, data: Any, ttl_minutes: int = 30):
        """データをキャッシュ"""
        if 'data_cache' not in st.session_state:
            st.session_state.data_cache = {}
        
        cache_entry = {
            'data': data,
            'timestamp': datetime.now(),
            'ttl': ttl_minutes
        }
        
        st.session_state.data_cache[key] = cache_entry
        logger.info(f"データをキャッシュ: {key}")
    
    def get_cached_data(self, key: str) -> Optional[Any]:
        """キャッシュからデータを取得"""
        if 'data_cache' not in st.session_state:
            return None
        
        if key not in st.session_state.data_cache:
            return None
        
        cache_entry = st.session_state.data_cache[key]
        timestamp = cache_entry['timestamp']
        ttl = cache_entry['ttl']
        
        # TTLチェック
        if datetime.now() - timestamp > timedelta(minutes=ttl):
            del st.session_state.data_cache[key]
            return None
        
        return cache_entry['data']
    
    def clear_cache(self, key: str = None):
        """キャッシュをクリア"""
        if key is None:
            st.session_state.data_cache = {}
            logger.info("全キャッシュをクリア")
        else:
            if key in st.session_state.data_cache:
                del st.session_state.data_cache[key]
                logger.info(f"キャッシュをクリア: {key}")
    
    def add_to_history(self, action: str, details: Dict[str, Any] = None):
        """分析履歴に追加"""
        if 'analysis_history' not in st.session_state:
            st.session_state.analysis_history = []
        
        history_entry = {
            'timestamp': datetime.now(),
            'action': action,
            'details': details or {},
            'session_id': self.session_id
        }
        
        st.session_state.analysis_history.append(history_entry)
        
        # 履歴を最新100件に制限
        if len(st.session_state.analysis_history) > 100:
            st.session_state.analysis_history = st.session_state.analysis_history[-100:]
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """分析履歴を取得"""
        if 'analysis_history' not in st.session_state:
            return []
        
        return st.session_state.analysis_history[-limit:]
    
    def set_current_dataset(self, df: pd.DataFrame, name: str = "current"):
        """現在のデータセットを設定"""
        st.session_state.current_dataset = {
            'data': df,
            'name': name,
            'timestamp': datetime.now(),
            'shape': df.shape,
            'columns': list(df.columns),
            'memory_usage': df.memory_usage(deep=True).sum()
        }
        
        self.add_to_history("dataset_loaded", {
            'name': name,
            'shape': df.shape,
            'columns': len(df.columns)
        })
        
        logger.info(f"データセットを設定: {name}, Shape: {df.shape}")
    
    def get_current_dataset(self) -> Optional[pd.DataFrame]:
        """現在のデータセットを取得"""
        if 'current_dataset' not in st.session_state or st.session_state.current_dataset is None:
            return None
        
        return st.session_state.current_dataset['data']
    
    def set_filtered_data(self, df: pd.DataFrame):
        """フィルター適用後のデータを設定"""
        st.session_state.filtered_data = df
        self.add_to_history("data_filtered", {'shape': df.shape})
    
    def get_filtered_data(self) -> Optional[pd.DataFrame]:
        """フィルター適用後のデータを取得"""
        return st.session_state.get('filtered_data')
    
    def save_chart_settings(self, chart_type: str, settings: Dict[str, Any]):
        """チャート設定を保存"""
        if 'chart_settings' not in st.session_state:
            st.session_state.chart_settings = {}
        
        st.session_state.chart_settings[chart_type] = settings
        logger.info(f"チャート設定を保存: {chart_type}")
    
    def get_chart_settings(self, chart_type: str) -> Dict[str, Any]:
        """チャート設定を取得"""
        if 'chart_settings' not in st.session_state:
            return {}
        
        return st.session_state.chart_settings.get(chart_type, {})
    
    def add_notification(self, message: str, type: str = "info", duration: int = 5):
        """通知を追加"""
        if 'notifications' not in st.session_state:
            st.session_state.notifications = []
        
        notification = {
            'id': hashlib.md5(f"{message}{datetime.now()}".encode()).hexdigest()[:8],
            'message': message,
            'type': type,
            'timestamp': datetime.now(),
            'duration': duration,
            'read': False
        }
        
        st.session_state.notifications.append(notification)
        
        # 古い通知を削除（最新50件を保持）
        if len(st.session_state.notifications) > 50:
            st.session_state.notifications = st.session_state.notifications[-50:]
    
    def get_notifications(self, unread_only: bool = False) -> List[Dict[str, Any]]:
        """通知を取得"""
        if 'notifications' not in st.session_state:
            return []
        
        notifications = st.session_state.notifications
        
        if unread_only:
            notifications = [n for n in notifications if not n['read']]
        
        return notifications
    
    def mark_notification_read(self, notification_id: str):
        """通知を既読にする"""
        if 'notifications' not in st.session_state:
            return
        
        for notification in st.session_state.notifications:
            if notification['id'] == notification_id:
                notification['read'] = True
                break
    
    def log_error(self, error: str, details: Dict[str, Any] = None):
        """エラーをログに記録"""
        if 'error_log' not in st.session_state:
            st.session_state.error_log = []
        
        error_entry = {
            'timestamp': datetime.now(),
            'error': error,
            'details': details or {},
            'session_id': self.session_id
        }
        
        st.session_state.error_log.append(error_entry)
        
        # エラーログを最新50件に制限
        if len(st.session_state.error_log) > 50:
            st.session_state.error_log = st.session_state.error_log[-50:]
        
        logger.error(f"エラーをログに記録: {error}")
    
    def get_error_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """エラーログを取得"""
        if 'error_log' not in st.session_state:
            return []
        
        return st.session_state.error_log[-limit:]
    
    def record_performance_metric(self, operation: str, duration: float, details: Dict[str, Any] = None):
        """パフォーマンスメトリクスを記録"""
        if 'performance_metrics' not in st.session_state:
            st.session_state.performance_metrics = {}
        
        if operation not in st.session_state.performance_metrics:
            st.session_state.performance_metrics[operation] = []
        
        metric = {
            'timestamp': datetime.now(),
            'duration': duration,
            'details': details or {}
        }
        
        st.session_state.performance_metrics[operation].append(metric)
        
        # メトリクスを最新100件に制限
        if len(st.session_state.performance_metrics[operation]) > 100:
            st.session_state.performance_metrics[operation] = st.session_state.performance_metrics[operation][-100:]
    
    def get_performance_metrics(self, operation: str = None) -> Union[Dict[str, List], List[Dict]]:
        """パフォーマンスメトリクスを取得"""
        if 'performance_metrics' not in st.session_state:
            return {} if operation is None else []
        
        if operation is None:
            return st.session_state.performance_metrics
        
        return st.session_state.performance_metrics.get(operation, [])
    
    def export_session_data(self) -> Dict[str, Any]:
        """セッションデータをエクスポート"""
        export_data = {
            'session_id': self.session_id,
            'created_at': st.session_state.get('created_at', datetime.now()).isoformat(),
            'user_preferences': st.session_state.get('user_preferences', {}),
            'analysis_history': [
                {
                    'timestamp': h['timestamp'].isoformat(),
                    'action': h['action'],
                    'details': h['details']
                }
                for h in st.session_state.get('analysis_history', [])
            ],
            'chart_settings': st.session_state.get('chart_settings', {}),
            'notifications': [
                {
                    'message': n['message'],
                    'type': n['type'],
                    'timestamp': n['timestamp'].isoformat()
                }
                for n in st.session_state.get('notifications', [])
            ]
        }
        
        return export_data
    
    def get_session_summary(self) -> Dict[str, Any]:
        """セッション概要を取得"""
        current_dataset = st.session_state.get('current_dataset')
        
        summary = {
            'session_id': self.session_id,
            'created_at': st.session_state.get('created_at'),
            'last_activity': st.session_state.get('last_activity'),
            'dataset_loaded': current_dataset is not None,
            'dataset_name': current_dataset['name'] if current_dataset else None,
            'dataset_shape': current_dataset['shape'] if current_dataset else None,
            'history_count': len(st.session_state.get('analysis_history', [])),
            'cache_size': len(st.session_state.get('data_cache', {})),
            'notifications_count': len(st.session_state.get('notifications', [])),
            'unread_notifications': len([n for n in st.session_state.get('notifications', []) if not n['read']]),
            'error_count': len(st.session_state.get('error_log', []))
        }
        
        return summary

# グローバルインスタンス
session_manager = SessionManager()

# 便利関数
def init_session():
    """セッションを初期化"""
    return session_manager

def save_preference(key: str, value: Any):
    """ユーザー設定を保存"""
    session_manager.save_user_preference(key, value)

def get_preference(key: str, default: Any = None):
    """ユーザー設定を取得"""
    return session_manager.get_user_preference(key, default)

def cache_dataframe(key: str, df: pd.DataFrame, ttl_minutes: int = 30):
    """DataFrameをキャッシュ"""
    session_manager.cache_data(key, df, ttl_minutes)

def get_cached_dataframe(key: str) -> Optional[pd.DataFrame]:
    """キャッシュからDataFrameを取得"""
    return session_manager.get_cached_data(key)

def add_notification(message: str, type: str = "info"):
    """通知を追加"""
    session_manager.add_notification(message, type)

def log_action(action: str, details: Dict[str, Any] = None):
    """アクションをログに記録"""
    session_manager.add_to_history(action, details)

def set_dataset(df: pd.DataFrame, name: str = "current"):
    """データセットを設定"""
    session_manager.set_current_dataset(df, name)

def get_dataset() -> Optional[pd.DataFrame]:
    """現在のデータセットを取得"""
    return session_manager.get_current_dataset()

def update_activity():
    """活動時間を更新"""
    session_manager.update_activity()