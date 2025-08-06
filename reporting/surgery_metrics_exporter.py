# reporting/surgery_metrics_exporter.py
"""
手術分析メトリクスCSV出力モジュール
ポータル統合用の標準化されたCSVデータを出力
"""

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging
from pathlib import Path
import io

logger = logging.getLogger(__name__)

class SurgeryMetricsExporter:
    """手術分析メトリクス出力クラス"""
    
    def __init__(self):
        self.app_name = "手術分析"
        self.version = "2.0"
        
    def export_metrics_csv(
        self,
        df: pd.DataFrame,
        target_dict: Dict[str, float] = None,
        analysis_date: datetime = None,
        period_type: str = "週次"
    ) -> Tuple[pd.DataFrame, str]:
        """
        メトリクスデータをCSV形式で出力
        
        Returns:
            Tuple[pd.DataFrame, str]: (メトリクスデータフレーム, ファイル名)
        """
        try:
            if analysis_date is None:
                analysis_date = datetime.now()
            
            # 期間設定
            period_info = self._calculate_period(analysis_date, period_type)
            
            # メトリクス計算
            metrics_data = []
            
            # 1. 全体メトリクス
            overall_metrics = self._calculate_overall_metrics(
                df, target_dict, period_info
            )
            metrics_data.extend(overall_metrics)
            
            # 2. 診療科別メトリクス
            dept_metrics = self._calculate_department_metrics(
                df, target_dict, period_info
            )
            metrics_data.extend(dept_metrics)
            
            # 3. 術者別メトリクス
            surgeon_metrics = self._calculate_surgeon_metrics(
                df, period_info
            )
            metrics_data.extend(surgeon_metrics)
            
            # 4. 時間別メトリクス
            time_metrics = self._calculate_time_metrics(
                df, period_info
            )
            metrics_data.extend(time_metrics)
            
            # データフレーム作成
            metrics_df = pd.DataFrame(metrics_data)
            
            # ファイル名生成
            filename = self._generate_filename(analysis_date, period_type)
            
            return metrics_df, filename
            
        except Exception as e:
            logger.error(f"メトリクス出力エラー: {e}")
            raise
    
    def _calculate_period(self, analysis_date: datetime, period_type: str) -> Dict:
        """期間情報を計算"""
        if period_type == "週次":
            # 月曜日開始の週
            days_since_monday = analysis_date.weekday()
            week_start = analysis_date - timedelta(days=days_since_monday)
            week_end = week_start + timedelta(days=6)
            
            return {
                "type": "週次",
                "start_date": week_start,
                "end_date": week_end,
                "label": f"{week_start.strftime('%Y年%m月%d日')}〜{week_end.strftime('%m月%d日')}週"
            }
        elif period_type == "月次":
            month_start = analysis_date.replace(day=1)
            next_month = month_start.replace(month=month_start.month + 1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1)
            month_end = next_month - timedelta(days=1)
            
            return {
                "type": "月次",
                "start_date": month_start,
                "end_date": month_end,
                "label": f"{month_start.strftime('%Y年%m月')}"
            }
        else:
            return {
                "type": "全期間",
                "start_date": df['手術実施日_dt'].min() if '手術実施日_dt' in df.columns else analysis_date,
                "end_date": df['手術実施日_dt'].max() if '手術実施日_dt' in df.columns else analysis_date,
                "label": "全期間"
            }
    
    def _calculate_overall_metrics(
        self, 
        df: pd.DataFrame, 
        target_dict: Dict[str, float],
        period_info: Dict
    ) -> List[Dict]:
        """全体メトリクス計算"""
        metrics = []
        
        # 期間内データフィルタリング
        period_df = self._filter_by_period(df, period_info)
        
        if period_df.empty:
            return metrics
        
        # 総手術件数
        total_count = len(period_df)
        metrics.append({
            "診療科名": "全体",
            "メトリクス名": "総手術件数",
            "値": total_count,
            "単位": "件",
            "期間": period_info["label"],
            "期間タイプ": period_info["type"],
            "カテゴリ": "全体指標",
            "データ種別": "実績",
            "計算日時": datetime.now().isoformat(),
            "アプリ名": self.app_name
        })
        
        # 平均手術件数（日別）
        if '手術実施日_dt' in period_df.columns:
            daily_counts = period_df.groupby('手術実施日_dt').size()
            avg_daily = daily_counts.mean()
            
            metrics.append({
                "診療科名": "全体",
                "メトリクス名": "日平均手術件数",
                "値": round(avg_daily, 2),
                "単位": "件/日",
                "期間": period_info["label"],
                "期間タイプ": period_info["type"],
                "カテゴリ": "全体指標",
                "データ種別": "実績",
                "計算日時": datetime.now().isoformat(),
                "アプリ名": self.app_name
            })
        
        # 目標達成率（全体）
        if target_dict:
            total_target = sum(target_dict.values())
            achievement_rate = (total_count / total_target * 100) if total_target > 0 else 0
            
            metrics.append({
                "診療科名": "全体",
                "メトリクス名": "目標達成率",
                "値": round(achievement_rate, 1),
                "単位": "%",
                "期間": period_info["label"],
                "期間タイプ": period_info["type"],
                "カテゴリ": "目標管理",
                "データ種別": "実績",
                "計算日時": datetime.now().isoformat(),
                "アプリ名": self.app_name
            })
        
        return metrics
    
    def _calculate_department_metrics(
        self,
        df: pd.DataFrame,
        target_dict: Dict[str, float],
        period_info: Dict
    ) -> List[Dict]:
        """診療科別メトリクス計算"""
        metrics = []
        
        # 期間内データフィルタリング
        period_df = self._filter_by_period(df, period_info)
        
        if period_df.empty or '実施診療科' not in period_df.columns:
            return metrics
        
        # 診療科別集計
        dept_counts = period_df['実施診療科'].value_counts()
        
        for dept, count in dept_counts.items():
            # 手術件数
            metrics.append({
                "診療科名": dept,
                "メトリクス名": "手術件数",
                "値": count,
                "単位": "件",
                "期間": period_info["label"],
                "期間タイプ": period_info["type"],
                "カテゴリ": "診療科別実績",
                "データ種別": "実績",
                "計算日時": datetime.now().isoformat(),
                "アプリ名": self.app_name
            })
            
            # 目標値と達成率
            if target_dict and dept in target_dict:
                target_value = target_dict[dept]
                achievement_rate = (count / target_value * 100) if target_value > 0 else 0
                
                # 目標値
                metrics.append({
                    "診療科名": dept,
                    "メトリクス名": "目標件数",
                    "値": target_value,
                    "単位": "件",
                    "期間": period_info["label"],
                    "期間タイプ": period_info["type"],
                    "カテゴリ": "診療科別目標",
                    "データ種別": "目標",
                    "計算日時": datetime.now().isoformat(),
                    "アプリ名": self.app_name
                })
                
                # 達成率
                metrics.append({
                    "診療科名": dept,
                    "メトリクス名": "目標達成率",
                    "値": round(achievement_rate, 1),
                    "単位": "%",
                    "期間": period_info["label"],
                    "期間タイプ": period_info["type"],
                    "カテゴリ": "診療科別目標",
                    "データ種別": "実績",
                    "計算日時": datetime.now().isoformat(),
                    "アプリ名": self.app_name
                })
                
                # 目標差分
                diff = count - target_value
                metrics.append({
                    "診療科名": dept,
                    "メトリクス名": "目標差分",
                    "値": diff,
                    "単位": "件",
                    "期間": period_info["label"],
                    "期間タイプ": period_info["type"],
                    "カテゴリ": "診療科別目標",
                    "データ種別": "実績",
                    "計算日時": datetime.now().isoformat(),
                    "アプリ名": self.app_name
                })
        
        return metrics
    
    def _calculate_surgeon_metrics(
        self,
        df: pd.DataFrame,
        period_info: Dict
    ) -> List[Dict]:
        """術者別メトリクス計算"""
        metrics = []
        
        # 期間内データフィルタリング
        period_df = self._filter_by_period(df, period_info)
        
        if period_df.empty or '実施術者' not in period_df.columns:
            return metrics
        
        # 術者別集計
        surgeon_counts = period_df['実施術者'].value_counts()
        
        # トップ10術者のみ出力
        top_surgeons = surgeon_counts.head(10)
        
        for surgeon, count in top_surgeons.items():
            metrics.append({
                "診療科名": "術者別",
                "メトリクス名": f"手術件数_{surgeon}",
                "値": count,
                "単位": "件",
                "期間": period_info["label"],
                "期間タイプ": period_info["type"],
                "カテゴリ": "術者別実績",
                "データ種別": "実績",
                "計算日時": datetime.now().isoformat(),
                "アプリ名": self.app_name
            })
        
        return metrics
    
    def _calculate_time_metrics(
        self,
        df: pd.DataFrame,
        period_info: Dict
    ) -> List[Dict]:
        """時間関連メトリクス計算"""
        metrics = []
        
        # 期間内データフィルタリング
        period_df = self._filter_by_period(df, period_info)
        
        if period_df.empty:
            return metrics
        
        # 手術時間分析（入室・退室時刻がある場合）
        if '入室時刻' in period_df.columns and '退室時刻' in period_df.columns:
            try:
                # 手術時間計算
                time_data = self._calculate_surgery_duration(period_df)
                
                if not time_data.empty:
                    avg_duration = time_data['手術時間_分'].mean()
                    
                    metrics.append({
                        "診療科名": "全体",
                        "メトリクス名": "平均手術時間",
                        "値": round(avg_duration, 1),
                        "単位": "分",
                        "期間": period_info["label"],
                        "期間タイプ": period_info["type"],
                        "カテゴリ": "時間分析",
                        "データ種別": "実績",
                        "計算日時": datetime.now().isoformat(),
                        "アプリ名": self.app_name
                    })
            except Exception as e:
                logger.warning(f"手術時間計算エラー: {e}")
        
        # 時間帯別分析
        if '入室時刻' in period_df.columns:
            try:
                time_slot_analysis = self._analyze_time_slots(period_df)
                
                for time_slot, count in time_slot_analysis.items():
                    metrics.append({
                        "診療科名": "全体",
                        "メトリクス名": f"手術件数_{time_slot}",
                        "値": count,
                        "単位": "件",
                        "期間": period_info["label"],
                        "期間タイプ": period_info["type"],
                        "カテゴリ": "時間帯分析",
                        "データ種別": "実績",
                        "計算日時": datetime.now().isoformat(),
                        "アプリ名": self.app_name
                    })
            except Exception as e:
                logger.warning(f"時間帯分析エラー: {e}")
        
        return metrics
    
    def _filter_by_period(self, df: pd.DataFrame, period_info: Dict) -> pd.DataFrame:
        """期間でデータをフィルタリング"""
        if '手術実施日_dt' not in df.columns:
            return df
        
        if period_info["type"] == "全期間":
            return df
        
        start_date = period_info["start_date"]
        end_date = period_info["end_date"]
        
        return df[
            (df['手術実施日_dt'] >= start_date) & 
            (df['手術実施日_dt'] <= end_date)
        ]
    
    def _calculate_surgery_duration(self, df: pd.DataFrame) -> pd.DataFrame:
        """手術時間を計算"""
        try:
            # 時刻文字列をdatetimeに変換
            df_copy = df.copy()
            df_copy['入室時刻_dt'] = pd.to_datetime(df_copy['入室時刻'], format='%H:%M', errors='coerce')
            df_copy['退室時刻_dt'] = pd.to_datetime(df_copy['退室時刻'], format='%H:%M', errors='coerce')
            
            # 深夜跨ぎの処理
            mask = df_copy['退室時刻_dt'] < df_copy['入室時刻_dt']
            df_copy.loc[mask, '退室時刻_dt'] += pd.Timedelta(days=1)
            
            # 手術時間（分）計算
            df_copy['手術時間_分'] = (df_copy['退室時刻_dt'] - df_copy['入室時刻_dt']).dt.total_seconds() / 60
            
            # 異常値除外（0分未満、24時間以上）
            df_copy = df_copy[
                (df_copy['手術時間_分'] >= 0) & 
                (df_copy['手術時間_分'] <= 1440)
            ]
            
            return df_copy
        except Exception as e:
            logger.error(f"手術時間計算エラー: {e}")
            return pd.DataFrame()
    
    def _analyze_time_slots(self, df: pd.DataFrame) -> Dict[str, int]:
        """時間帯別分析"""
        try:
            df_copy = df.copy()
            df_copy['入室時刻_dt'] = pd.to_datetime(df_copy['入室時刻'], format='%H:%M', errors='coerce')
            df_copy = df_copy.dropna(subset=['入室時刻_dt'])
            
            df_copy['時間帯'] = df_copy['入室時刻_dt'].dt.hour.map(
                lambda x: '午前' if 6 <= x < 12 else '午後' if 12 <= x < 18 else '夜間'
            )
            
            time_slot_counts = df_copy['時間帯'].value_counts()
            return time_slot_counts.to_dict()
        except Exception as e:
            logger.error(f"時間帯分析エラー: {e}")
            return {}
    
    def _generate_filename(self, analysis_date: datetime, period_type: str) -> str:
        """ファイル名生成"""
        date_str = analysis_date.strftime("%Y%m%d")
        return f"{date_str}_{self.app_name}_メトリクス_{period_type}.csv"
    
    def create_downloadable_csv(self, metrics_df: pd.DataFrame) -> io.BytesIO:
        """ダウンロード可能なCSVファイルを作成"""
        output = io.BytesIO()
        metrics_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        return output


def create_surgery_metrics_export_interface():
    """手術メトリクス出力インターフェース"""
    try:
        st.subheader("📊 手術メトリクス出力")
        
        # セッションからデータ取得
        from ui.session_manager import SessionManager
        
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        
        if df.empty:
            st.info("📊 手術データを読み込んでからメトリクス出力をご利用ください。")
            return
        
        # エクスポート設定
        col1, col2 = st.columns(2)
        
        with col1:
            period_type = st.selectbox(
                "分析期間タイプ",
                ["週次", "月次", "全期間"],
                help="メトリクス分析の期間を選択してください"
            )
        
        with col2:
            analysis_date = st.date_input(
                "基準日",
                value=datetime.now().date(),
                help="分析の基準となる日付を選択してください"
            )
        
        # プレビュー表示
        if st.button("📋 メトリクスプレビュー", type="secondary"):
            with st.spinner("メトリクス計算中..."):
                try:
                    exporter = SurgeryMetricsExporter()
                    metrics_df, filename = exporter.export_metrics_csv(
                        df, target_dict, datetime.combine(analysis_date, datetime.min.time()), period_type
                    )
                    
                    st.success(f"✅ メトリクス計算完了: {len(metrics_df)}件のメトリクス")
                    
                    # プレビュー表示
                    with st.expander("📄 メトリクスプレビュー", expanded=True):
                        st.dataframe(metrics_df.head(20), use_container_width=True)
                        if len(metrics_df) > 20:
                            st.caption(f"... 他 {len(metrics_df) - 20} 件のメトリクス")
                    
                    # カテゴリ別サマリー
                    category_summary = metrics_df['カテゴリ'].value_counts()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**カテゴリ別メトリクス数**")
                        for category, count in category_summary.items():
                            st.write(f"• {category}: {count}件")
                    
                    with col2:
                        st.write("**含まれる診療科**")
                        departments = metrics_df[metrics_df['診療科名'] != '全体']['診療科名'].unique()
                        for dept in departments[:10]:
                            st.write(f"• {dept}")
                        if len(departments) > 10:
                            st.write(f"... 他 {len(departments) - 10} 診療科")
                    
                    # セッションに保存
                    st.session_state['preview_metrics_df'] = metrics_df
                    st.session_state['preview_filename'] = filename
                    
                except Exception as e:
                    st.error(f"❌ メトリクス計算エラー: {e}")
                    logger.error(f"メトリクス計算エラー: {e}")
        
        # CSV出力
        st.markdown("---")
        
        if st.button("📥 CSV出力", type="primary"):
            try:
                # 修正箇所: exporterをtryブロックの最初にインスタンス化する
                # これにより、プレビューの有無に関わらず常にexporterが利用可能になる
                exporter = SurgeryMetricsExporter()

                # プレビューデータがあればそれを使用、なければ新規計算
                if 'preview_metrics_df' in st.session_state:
                    metrics_df = st.session_state['preview_metrics_df']
                    filename = st.session_state['preview_filename']
                else:
                    with st.spinner("メトリクス計算中..."):
                        # 事前に作成したexporterを使用
                        metrics_df, filename = exporter.export_metrics_csv(
                            df, target_dict, datetime.combine(analysis_date, datetime.min.time()), period_type
                        )
                
                # CSV出力
                # これで、この行に到達したときには必ずexporterが存在する
                csv_data = exporter.create_downloadable_csv(metrics_df)
                
                st.download_button(
                    label="💾 メトリクスCSVダウンロード",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    help=f"{filename} をダウンロードします。ポータル統合用の標準化されたメトリクスデータです。"
                )
                
                st.success(f"✅ CSV出力準備完了: {len(metrics_df)}件のメトリクス")
                
            except Exception as e:
                st.error(f"❌ CSV出力エラー: {e}")
                logger.error(f"CSV出力エラー: {e}")
        
        # 使用方法説明
        with st.expander("ℹ️ 使用方法とデータ形式"):
            st.markdown("""
            ### 📋 出力されるメトリクス
            
            **全体指標**
            - 総手術件数
            - 日平均手術件数  
            - 目標達成率
            
            **診療科別指標**
            - 診療科別手術件数
            - 診療科別目標達成率
            - 目標差分
            
            **術者別指標**
            - 術者別手術件数（トップ10）
            
            **時間分析**
            - 平均手術時間
            - 時間帯別手術件数
            
            ### 🔧 ポータル統合について
            
            出力されるCSVファイルは以下の標準形式で統一されています：
            - 診療科名、メトリクス名、値、単位、期間などの共通フォーマット
            - ポータルwebページで自動読み込み・表示可能
            - 他のアプリ（入退院分析等）と統合表示
            """)
    
    except Exception as e:
        st.error(f"❌ メトリクス出力インターフェースエラー: {e}")
        logger.error(f"メトリクス出力インターフェースエラー: {e}")


if __name__ == "__main__":
    # テスト用
    st.title("手術メトリクス出力テスト")
    create_surgery_metrics_export_interface()