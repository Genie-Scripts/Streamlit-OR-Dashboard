# ui/pages/data_management_page.py
"""
データ管理ページモジュール（CSV出力機能統合版）
データの読み込み、保存、バックアップ管理、メトリクス出力を行う
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_file_operation
from data_persistence import (
    get_data_info, get_file_sizes, get_backup_info, restore_from_backup,
    export_data_package, import_data_package, create_backup,
    load_data_from_file, save_data_to_file, delete_saved_data
)

# メトリクス出力機能をインポート
try:
    from reporting.surgery_metrics_exporter import create_surgery_metrics_export_interface
    METRICS_EXPORT_AVAILABLE = True
except ImportError:
    METRICS_EXPORT_AVAILABLE = False
    logger.warning("メトリクス出力機能が利用できません")

logger = logging.getLogger(__name__)


class DataManagementPage:
    """データ管理ページクラス（CSV出力機能統合版）"""
    
    @staticmethod
    @safe_streamlit_operation("データ管理ページ描画")
    def render() -> None:
        """データ管理ページを描画"""
        st.header("💾 データ管理")
        
        # データ状態の表示
        data_info = get_data_info()
        file_sizes = get_file_sizes()
        
        # タブで機能を分割（メトリクス出力タブを追加）
        if METRICS_EXPORT_AVAILABLE:
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 データ状態", 
                "💾 バックアップ管理", 
                "📁 エクスポート/インポート",
                "📋 メトリクス出力",  # 新規追加
                "⚙️ 詳細設定"
            ])
        else:
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 データ状態", 
                "💾 バックアップ管理", 
                "📁 エクスポート/インポート", 
                "⚙️ 詳細設定"
            ])
        
        with tab1:
            DataManagementPage._render_data_status_tab(data_info, file_sizes)
        
        with tab2:
            DataManagementPage._render_backup_management_tab()
        
        with tab3:
            DataManagementPage._render_export_import_tab()
        
        if METRICS_EXPORT_AVAILABLE:
            with tab4:
                DataManagementPage._render_metrics_export_tab()
            
            with tab5:
                DataManagementPage._render_settings_tab()
        else:
            with tab4:
                DataManagementPage._render_settings_tab()
    
    @staticmethod
    def _render_data_status_tab(data_info: dict, file_sizes: dict) -> None:
        """データ状態タブを描画"""
        st.subheader("📊 現在のデータ状態")
        
        col1, col2 = st.columns(2)
        
        with col1:
            DataManagementPage._render_saved_data_section(data_info)
        
        with col2:
            DataManagementPage._render_session_data_section(file_sizes)
    
    @staticmethod
    @safe_file_operation("保存データ表示")
    def _render_saved_data_section(data_info: dict) -> None:
        """保存データセクションを描画"""
        if data_info:
            st.success("💾 保存データあり")
            
            # データ情報を表示
            with st.expander("📋 保存データ詳細", expanded=True):
                st.json(data_info)
            
            # データ読み込みボタン
            if st.button("💾 保存データを読み込み", type="primary"):
                with st.spinner("データ読み込み中..."):
                    try:
                        df, target_data, metadata = load_data_from_file()
                        
                        if df is not None:
                            # セッションに保存
                            SessionManager.set_processed_df(df)
                            if target_data:
                                SessionManager.set_target_dict(target_data)
                            
                            st.success(f"✅ データを読み込みました: {len(df)}件")
                            st.rerun()
                        else:
                            st.error("❌ データ読み込みに失敗しました")
                    except Exception as e:
                        st.error(f"❌ 読み込みエラー: {e}")
            
            # データ削除ボタン
            if st.button("🗑️ 保存データを削除", type="secondary"):
                if st.checkbox("確認: 保存データを削除します"):
                    try:
                        delete_success = delete_saved_data()
                        if delete_success:
                            st.success("✅ 保存データを削除しました")
                            st.rerun()
                        else:
                            st.error("❌ データ削除に失敗しました")
                    except Exception as e:
                        st.error(f"❌ 削除エラー: {e}")
        else:
            st.info("💾 保存データなし")
            st.caption("データアップロードページでデータを読み込んでください")
    
    @staticmethod
    def _render_session_data_section(file_sizes: dict) -> None:
        """セッションデータセクションを描画"""
        st.write("**📱 セッションデータ**")
        
        if SessionManager.is_data_loaded():
            df = SessionManager.get_processed_df()
            target_dict = SessionManager.get_target_dict()
            
            st.success("✅ セッションにデータあり")
            
            # データ統計
            col1, col2 = st.columns(2)
            with col1:
                st.metric("手術件数", f"{len(df):,}件")
                if '実施診療科' in df.columns:
                    st.metric("診療科数", f"{df['実施診療科'].nunique()}科")
            
            with col2:
                st.metric("目標設定", f"{len(target_dict)}科" if target_dict else "未設定")
                if '手術実施日_dt' in df.columns and not df.empty:
                    date_range = (df['手術実施日_dt'].max() - df['手術実施日_dt'].min()).days + 1
                    st.metric("データ期間", f"{date_range}日間")
            
            # セッションデータ保存
            if st.button("💾 セッションデータを保存"):
                with st.spinner("データ保存中..."):
                    try:
                        metadata = {
                            "save_source": "session",
                            "user_action": "manual_save",
                            "data_version": "2.0"
                        }
                        
                        save_success = save_data_to_file(df, target_dict, metadata)
                        if save_success:
                            st.success("✅ セッションデータを保存しました")
                        else:
                            st.error("❌ データ保存に失敗しました")
                    except Exception as e:
                        st.error(f"❌ 保存エラー: {e}")
        else:
            st.warning("⚠️ セッションにデータなし")
            st.caption("データアップロードページでデータを読み込んでください")
        
        # ファイルサイズ情報
        if file_sizes:
            with st.expander("📁 ファイルサイズ情報"):
                for file_type, size in file_sizes.items():
                    st.write(f"• {file_type}: {size}")
    
    @staticmethod
    def _render_backup_management_tab() -> None:
        """バックアップ管理タブを描画"""
        st.subheader("💾 バックアップ管理")
        
        col1, col2 = st.columns(2)
        
        with col1:
            DataManagementPage._render_backup_list_section()
        
        with col2:
            DataManagementPage._render_manual_backup_section()
    
    @staticmethod
    @safe_file_operation("バックアップ一覧表示")
    def _render_backup_list_section() -> None:
        """バックアップ一覧セクションを描画"""
        st.write("**📋 バックアップ一覧**")
        
        backup_info = get_backup_info()
        
        if backup_info:
            for backup in backup_info:
                with st.container():
                    # 修正箇所1: .get()を使用して安全にキーにアクセス
                    st.write(f"**{backup.get('filename', '不明なファイル')}**")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # 修正箇所2: 'created_at'キーが存在しない場合、「不明」と表示
                        st.caption(f"作成日時: {backup.get('created_at', '不明')}")
                    
                    with col2:
                        # 修正箇所3: 'size'キーも同様に安全にアクセス
                        st.caption(f"サイズ: {backup.get('size', '不明')}")
                    
                    with col3:
                        # 復元ボタンのキーも安全な値を使用
                        filename = backup.get('filename')
                        if filename and st.button("🔄 復元", key=f"restore_{filename}"):
                            DataManagementPage._restore_backup(backup)
                    
                    # ダウンロードボタン
                    if backup.get('filename'):
                        DataManagementPage._download_backup(backup)
                    
                    st.markdown("---")
        else:
            st.info("📝 バックアップファイルがありません")
    
    @staticmethod
    @safe_file_operation("バックアップ復元")
    def _restore_backup(backup: dict) -> None:
        """バックアップを復元"""
        try:
            with st.spinner(f"{backup['filename']} を復元中..."):
                success, message = restore_from_backup(backup['filename'])
                
                if success:
                    st.success(f"✅ {message}")
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
                    
        except Exception as e:
            st.error(f"❌ 復元エラー: {e}")
            logger.error(f"バックアップ復元エラー: {e}")
    
    @staticmethod
    def _download_backup(backup: dict) -> None:
        """バックアップファイルをダウンロード"""
        try:
            with open(backup['path'], 'rb') as f:
                st.download_button(
                    label="💾 ダウンロード開始",
                    data=f.read(),
                    file_name=backup['filename'],
                    mime="application/octet-stream",
                    key=f"download_btn_{backup['filename']}"
                )
        except Exception as e:
            st.error(f"❌ ダウンロードエラー: {e}")
    
    @staticmethod
    def _render_manual_backup_section() -> None:
        """手動バックアップセクションを描画"""
        st.write("**📦 手動バックアップ作成**")
        
        st.info("現在のデータをバックアップファイルとして保存します。")
        
        if st.button("🔄 現在のデータをバックアップ"):
            DataManagementPage._create_manual_backup()
    
    @staticmethod
    @safe_file_operation("手動バックアップ作成")
    def _create_manual_backup() -> None:
        """手動バックアップを作成"""
        try:
            with st.spinner("バックアップ作成中..."):
                backup_success = create_backup(force_create=True)
                
                if backup_success:
                    st.success("✅ バックアップを作成しました")
                    logger.info("手動バックアップ作成完了")
                else:
                    st.error("❌ バックアップ作成に失敗しました")
                    
        except Exception as e:
            st.error(f"❌ バックアップ作成エラー: {e}")
            logger.error(f"バックアップ作成エラー: {e}")
    
    @staticmethod
    def _render_export_import_tab() -> None:
        """エクスポート/インポートタブを描画"""
        col1, col2 = st.columns(2)
        
        with col1:
            DataManagementPage._render_export_section()
        
        with col2:
            DataManagementPage._render_import_section()
    
    @staticmethod
    @safe_file_operation("データエクスポート")
    def _render_export_section() -> None:
        """エクスポートセクションを描画"""
        st.subheader("📤 データエクスポート")
        
        st.info("全てのデータをZIPファイルとしてエクスポートします。")
        
        if st.button("📦 データパッケージをエクスポート"):
            with st.spinner("エクスポート中..."):
                try:
                    success, result = export_data_package()
                    
                    if success:
                        st.success("✅ エクスポート完了")
                        
                        # ダウンロードボタン
                        with open(result, 'rb') as f:
                            st.download_button(
                                label="💾 エクスポートファイルをダウンロード",
                                data=f.read(),
                                file_name=result.split('/')[-1],
                                mime="application/zip"
                            )
                    else:
                        st.error(f"❌ エクスポート失敗: {result}")
                        
                except Exception as e:
                    st.error(f"❌ エクスポートエラー: {e}")
    
    @staticmethod
    @safe_file_operation("データインポート")
    def _render_import_section() -> None:
        """インポートセクションを描画"""
        st.subheader("📥 データインポート")
        
        st.info("エクスポートしたZIPファイルからデータを復元します。")
        
        uploaded_file = st.file_uploader(
            "インポートファイル選択",
            type=['zip'],
            help="エクスポートしたZIPファイルを選択してください"
        )
        
        if uploaded_file is not None:
            if st.button("📥 データをインポート"):
                with st.spinner("インポート中..."):
                    try:
                        # 一時ファイルに保存
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                            tmp_file.write(uploaded_file.read())
                            tmp_path = tmp_file.name
                        
                        success, message = import_data_package(tmp_path)
                        
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                            
                    except Exception as e:
                        st.error(f"❌ インポートエラー: {e}")
    
    @staticmethod
    def _render_metrics_export_tab() -> None:
        """メトリクス出力タブを描画（新規追加）"""
        if METRICS_EXPORT_AVAILABLE:
            create_surgery_metrics_export_interface()
        else:
            st.error("❌ メトリクス出力機能が利用できません")
            st.info("📝 reporting/surgery_metrics_exporter.py モジュールを確認してください")
    
    @staticmethod
    def _render_settings_tab() -> None:
        """詳細設定タブを描画"""
        st.subheader("⚙️ 詳細設定")
        
        # 自動バックアップ設定
        st.write("**🔄 自動バックアップ設定**")
        
        auto_backup = st.checkbox(
            "自動バックアップを有効にする",
            value=st.session_state.get('auto_backup_enabled', True),
            help="データ更新時に自動的にバックアップを作成します"
        )
        
        if auto_backup:
            backup_interval = st.selectbox(
                "バックアップ間隔",
                ["毎回", "1日1回", "週1回"],
                index=0,
                help="バックアップを作成する頻度を選択してください"
            )
            
            max_backups = st.number_input(
                "最大保持バックアップ数",
                min_value=1,
                max_value=50,
                value=st.session_state.get('max_backups', 10),
                help="保持するバックアップファイルの最大数"
            )
            
            # 設定保存
            if st.button("💾 設定を保存"):
                st.session_state['auto_backup_enabled'] = auto_backup
                st.session_state['backup_interval'] = backup_interval
                st.session_state['max_backups'] = max_backups
                st.success("✅ 設定を保存しました")
        
        st.markdown("---")
        
        # データクリア設定
        st.write("**🗑️ データクリア**")
        
        st.warning("⚠️ 以下の操作は元に戻せません。十分ご注意ください。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ セッションデータをクリア", type="secondary"):
                if st.checkbox("確認: セッションデータをクリアします", key="clear_session"):
                    try:
                        SessionManager.clear_session_data()
                        st.success("✅ セッションデータをクリアしました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ クリアエラー: {e}")
        
        with col2:
            if st.button("🗑️ 全データを削除", type="secondary"):
                if st.checkbox("確認: 全てのデータを削除します", key="delete_all"):
                    try:
                        # セッションクリア
                        SessionManager.clear_session_data()
                        
                        # 保存データ削除
                        delete_saved_data()
                        
                        st.success("✅ 全データを削除しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 削除エラー: {e}")
        
        st.markdown("---")
        
        # システム情報
        st.write("**ℹ️ システム情報**")
        
        with st.expander("🔍 システム詳細"):
            system_info = {
                "アプリ名": "手術分析ダッシュボード",
                "バージョン": "2.0",
                "メトリクス出力": "有効" if METRICS_EXPORT_AVAILABLE else "無効",
                "セッション状態": "データあり" if SessionManager.is_data_loaded() else "データなし",
                "現在時刻": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            for key, value in system_info.items():
                st.write(f"• **{key}**: {value}")
        
        # ログ表示
        with st.expander("📋 ログ表示"):
            st.info("開発者向け: アプリケーションログをここに表示")
            st.code("2024-08-05 10:00:00 - INFO - データ管理ページ描画完了")