# ui/pages/dashboard_page.py
"""
ダッシュボードページモジュール
メインダッシュボードの表示を管理
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation

# 既存の分析モジュールをインポート
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots
from utils import date_helpers

logger = logging.getLogger(__name__)


class DashboardPage:
    """ダッシュボードページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("ダッシュボードページ描画")
    def render() -> None:
        """ダッシュボードページを描画"""
        st.title("📱 ダッシュボード - 管理者向けサマリー")
        
        # データ取得
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        latest_date = SessionManager.get_latest_date()
        
        if df.empty:
            DashboardPage._render_no_data_dashboard()
            return
        
        # 期間選択セクション
        analysis_period, start_date, end_date = DashboardPage._render_period_selector(latest_date)
        
        # 分析期間情報
        DashboardPage._render_analysis_period_info(latest_date, analysis_period, start_date, end_date)
        
        # 主要指標セクション
        DashboardPage._render_kpi_section(df, latest_date, start_date, end_date)
        
        # 診療科別パフォーマンスダッシュボード
        DashboardPage._render_performance_dashboard(df, target_dict, latest_date, start_date, end_date)
        
        # 目標達成状況サマリー  
        DashboardPage._render_achievement_summary(df, target_dict, latest_date, start_date, end_date)
    
    @staticmethod
    def _render_period_selector(latest_date: Optional[pd.Timestamp]) -> Tuple[str, pd.Timestamp, pd.Timestamp]:
        """期間選択セクションを表示"""
        st.subheader("📅 分析期間選択")
        
        period_options = [
            "直近4週",
            "直近8週", 
            "直近12週",
            "今年度",
            "昨年度"
        ]
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            selected_period = st.selectbox(
                "分析期間",
                period_options,
                index=0,
                help="分析に使用する期間を選択してください"
            )
        
        # 選択された期間に基づいて開始日・終了日を計算
        start_date, end_date = DashboardPage._calculate_period_dates(selected_period, latest_date)
        
        with col2:
            if start_date and end_date:
                st.info(
                    f"📊 **選択期間**: {selected_period}  \n"
                    f"📅 **分析範囲**: {start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')}  \n"
                    f"📈 **期間長**: {(end_date - start_date).days + 1}日間"
                )
            else:
                st.warning("期間計算でエラーが発生しました")
        
        return selected_period, start_date, end_date
    
    @staticmethod
    def _calculate_period_dates(period: str, latest_date: Optional[pd.Timestamp]) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
        """選択された期間に基づいて開始日・終了日を計算"""
        if not latest_date:
            return None, None
        
        try:
            # 週単位分析の場合は分析終了日（日曜日）を使用
            if "週" in period:
                analysis_end_date = weekly.get_analysis_end_date(latest_date)
                if not analysis_end_date:
                    return None, None
                end_date = analysis_end_date
            else:
                end_date = latest_date
            
            if period == "直近4週":
                start_date = end_date - pd.Timedelta(days=27)
            elif period == "直近8週":
                start_date = end_date - pd.Timedelta(days=55)
            elif period == "直近12週":
                start_date = end_date - pd.Timedelta(days=83)
            elif period == "今年度":
                current_year = latest_date.year
                if latest_date.month >= 4:
                    start_date = pd.Timestamp(current_year, 4, 1)
                else:
                    start_date = pd.Timestamp(current_year - 1, 4, 1)
                end_date = latest_date
            elif period == "昨年度":
                current_year = latest_date.year
                if latest_date.month >= 4:
                    start_date = pd.Timestamp(current_year - 1, 4, 1)
                    end_date = pd.Timestamp(current_year, 3, 31)
                else:
                    start_date = pd.Timestamp(current_year - 2, 4, 1)
                    end_date = pd.Timestamp(current_year - 1, 3, 31)
            else:
                return None, None
            
            return start_date, end_date
            
        except Exception as e:
            logger.error(f"期間計算エラー: {e}")
            return None, None
    
    @staticmethod
    def _render_no_data_dashboard() -> None:
        """データなし時のダッシュボード"""
        st.info("📊 ダッシュボードを表示するにはデータが必要です")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🚀 はじめに
            
            手術分析ダッシュボードへようこそ！
            
            **主な機能:**
            - 📈 リアルタイム手術実績分析
            - 🏆 診療科別ランキング
            - 👨‍⚕️ 術者別パフォーマンス分析
            - 🔮 将来予測とトレンド分析
            """)
        
        with col2:
            st.markdown("""
            ### 📋 次のステップ
            
            1. **データアップロード**で手術データを読み込み
            2. **目標データ**を設定（オプション）
            3. **分析開始** - 各種レポートを確認
            
            **対応形式:** CSV形式の手術データ
            """)
        
        # クイックアクション
        st.markdown("---")
        st.subheader("⚡ クイックアクション")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📤 データアップロード", type="primary", use_container_width=True):
                SessionManager.set_current_view("データアップロード")
                st.rerun()
        
        with col2:
            if st.button("💾 データ管理", use_container_width=True):
                SessionManager.set_current_view("データ管理")
                st.rerun()
        
        with col3:
            if st.button("📖 ヘルプ", use_container_width=True):
                DashboardPage._show_help_dialog()
    
    @staticmethod
    @safe_data_operation("KPI計算")
    def _render_kpi_section(df: pd.DataFrame, latest_date: Optional[pd.Timestamp], 
                          start_date: Optional[pd.Timestamp], end_date: Optional[pd.Timestamp]) -> None:
        """KPIセクションを描画"""
        st.header("📊 主要指標 (選択期間)")
        
        try:
            # 選択された期間でデータをフィルタリング
            if start_date and end_date:
                period_df = df[
                    (df['手術実施日_dt'] >= start_date) & 
                    (df['手術実施日_dt'] <= end_date)
                ]
            else:
                # フォールバック: 元の関数を使用
                kpi_summary = ranking.get_kpi_summary(df, latest_date)
                generic_plots.display_kpi_metrics(kpi_summary)
                return
            
            # KPIサマリーを計算（選択期間用）
            kpi_data = DashboardPage._calculate_period_kpi(period_df, start_date, end_date)
            
            # KPI表示（直接メトリクス表示）
            DashboardPage._display_period_kpi_metrics(kpi_data, start_date, end_date)
            
        except Exception as e:
            logger.error(f"KPI計算エラー: {e}")
            st.error("KPI計算中にエラーが発生しました")
    
    @staticmethod
    def _calculate_period_kpi(df: pd.DataFrame, start_date: Optional[pd.Timestamp], 
                             end_date: Optional[pd.Timestamp]) -> Dict[str, Any]:
        """選択期間のKPIを計算"""
        try:
            if df.empty:
                return {}
            
            # 期間の日数計算
            if start_date and end_date:
                total_days = (end_date - start_date).days + 1
                weekdays = sum(1 for i in range(total_days) 
                             if (start_date + pd.Timedelta(days=i)).weekday() < 5)
            else:
                total_days = 28
                weekdays = 20
            
            # 1. 全身麻酔手術件数
            gas_df = df[df['is_gas_20min'] == True] if 'is_gas_20min' in df.columns else pd.DataFrame()
            gas_cases = len(gas_df)
            
            # 2. 全手術件数
            total_cases = len(df)
            
            # 3. 平日1日あたり全身麻酔手術件数
            if not gas_df.empty and 'is_weekday' in gas_df.columns:
                weekday_gas_df = gas_df[gas_df['is_weekday'] == True]
                weekday_gas_cases = len(weekday_gas_df)
            else:
                weekday_gas_cases = gas_cases
            
            daily_avg_gas = weekday_gas_cases / weekdays if weekdays > 0 else 0
            
            # 4. 手術室稼働率：時間ベースの正確な計算
            utilization_rate, actual_minutes, max_minutes = DashboardPage._calculate_or_utilization(
                df, start_date, end_date, weekdays
            )
            
            return {
                'gas_cases': gas_cases,
                'total_cases': total_cases,
                'daily_avg_gas': daily_avg_gas,
                'utilization_rate': utilization_rate,
                'actual_minutes': actual_minutes,
                'max_minutes': max_minutes,
                'period_days': total_days,
                'weekdays': weekdays
            }
            
        except Exception as e:
            logger.error(f"期間KPI計算エラー: {e}")
            return {}
    
    @staticmethod
    def _calculate_or_utilization(df: pd.DataFrame, start_date: Optional[pd.Timestamp], 
                                 end_date: Optional[pd.Timestamp], weekdays: int) -> Tuple[float, int, int]:
        """手術室稼働率を時間ベースで計算"""
        try:
            # 平日のデータのみ
            if 'is_weekday' in df.columns:
                weekday_df = df[df['is_weekday'] == True].copy()
            else:
                weekday_df = df.copy()
            
            if weekday_df.empty:
                return 0.0, 0, 0
            
            # 手術室フィルタリング（簡易版）
            or_columns = ['手術室', 'OR', 'OP室', '実施手術室']
            or_column = None
            
            for col in or_columns:
                if col in weekday_df.columns:
                    or_column = col
                    break
            
            if or_column:
                # OP-1からOP-12を含む手術室を抽出（簡易版）
                weekday_df['or_str'] = weekday_df[or_column].astype(str)
                or_filtered_df = weekday_df[
                    weekday_df['or_str'].str.contains('OP-', na=False) &
                    ~weekday_df['or_str'].str.contains('OP-11A', na=False) &
                    ~weekday_df['or_str'].str.contains('OP-11B', na=False)
                ]
            else:
                logger.warning("手術室列が見つからないため、全データを使用")
                or_filtered_df = weekday_df
            
            # 時刻フィルタリング：9:00〜17:15
            time_filtered_df = DashboardPage._filter_operating_hours(or_filtered_df)
            
            # 手術時間の計算
            actual_minutes = DashboardPage._calculate_surgery_minutes(time_filtered_df)
            
            # 分母：理論上の最大稼働時間
            max_minutes = 495 * 11 * weekdays
            
            # 稼働率計算
            utilization_rate = (actual_minutes / max_minutes * 100) if max_minutes > 0 else 0.0
            
            return utilization_rate, actual_minutes, max_minutes
            
        except Exception as e:
            logger.error(f"手術室稼働率計算エラー: {e}")
            return 0.0, 0, 0
    
    @staticmethod
    def _filter_operating_hours(df: pd.DataFrame) -> pd.DataFrame:
        """9:00〜17:15の手術をフィルタリング"""
        try:
            if df.empty:
                return df
            
            # 手術開始時刻の列を探す
            time_columns = ['手術開始時刻', '開始時刻', '手術開始時間', 'start_time']
            time_column = None
            
            for col in time_columns:
                if col in df.columns:
                    time_column = col
                    break
            
            if not time_column:
                logger.warning("手術開始時刻列が見つからないため、時刻フィルタリングをスキップ")
                return df
            
            def parse_time_to_minutes(time_str):
                """時刻文字列を分単位に変換"""
                if pd.isna(time_str) or time_str == '':
                    return None
                try:
                    time_str = str(time_str).strip()
                    if ':' in time_str:
                        hour, minute = time_str.split(':')
                        return int(hour) * 60 + int(minute)
                    else:
                        time_num = int(float(time_str))
                        hour = time_num // 100
                        minute = time_num % 100
                        return hour * 60 + minute
                except:
                    return None
            
            df_filtered = df.copy()
            df_filtered['start_minutes'] = df_filtered[time_column].apply(parse_time_to_minutes)
            
            # 9:00（540分）〜17:15（1035分）でフィルタリング
            filtered_df = df_filtered[
                (df_filtered['start_minutes'] >= 540) & 
                (df_filtered['start_minutes'] <= 1035) &
                (df_filtered['start_minutes'].notna())
            ]
            
            return filtered_df
            
        except Exception as e:
            logger.error(f"時刻フィルタリングエラー: {e}")
            return df
    
    @staticmethod
    def _calculate_surgery_minutes(df: pd.DataFrame) -> int:
        """手術時間の合計を分単位で計算"""
        try:
            if df.empty:
                return 0
            
            # 手術時間の列を探す
            duration_columns = ['手術時間', '所要時間', '手術時間（分）', 'duration', 'surgery_time']
            duration_column = None
            
            for col in duration_columns:
                if col in df.columns:
                    duration_column = col
                    break
            
            if duration_column:
                try:
                    total_minutes = df[duration_column].fillna(0).sum()
                    return int(total_minutes)
                except:
                    logger.warning(f"手術時間列 {duration_column} の計算でエラー")
            
            # 手術時間列がない場合、開始時刻と終了時刻から計算
            start_columns = ['手術開始時刻', '開始時刻', '手術開始時間']
            end_columns = ['手術終了時刻', '終了時刻', '手術終了時間']
            
            start_col = None
            end_col = None
            
            for col in start_columns:
                if col in df.columns:
                    start_col = col
                    break
            
            for col in end_columns:
                if col in df.columns:
                    end_col = col
                    break
            
            if start_col and end_col:
                def time_to_minutes(time_str):
                    if pd.isna(time_str) or time_str == '':
                        return None
                    try:
                        time_str = str(time_str).strip()
                        if ':' in time_str:
                            hour, minute = time_str.split(':')
                            return int(hour) * 60 + int(minute)
                    except:
                        return None
                
                df_calc = df.copy()
                df_calc['start_min'] = df_calc[start_col].apply(time_to_minutes)
                df_calc['end_min'] = df_calc[end_col].apply(time_to_minutes)
                
                # 終了時刻が開始時刻より小さい場合は翌日とみなす
                df_calc.loc[df_calc['end_min'] < df_calc['start_min'], 'end_min'] += 24 * 60
                
                df_calc['duration'] = df_calc['end_min'] - df_calc['start_min']
                
                # 妥当性チェック（0分〜12時間以内）
                valid_durations = df_calc[
                    (df_calc['duration'] >= 0) & 
                    (df_calc['duration'] <= 720) & 
                    (df_calc['duration'].notna())
                ]['duration']
                
                return int(valid_durations.sum())
            
            # フォールバック：件数ベースで推定（平均60分/件と仮定）
            logger.warning("手術時間を計算できないため、件数ベースで推定（60分/件）")
            return len(df) * 60
            
        except Exception as e:
            logger.error(f"手術時間計算エラー: {e}")
            return len(df) * 60
    
    @staticmethod
    def _display_period_kpi_metrics(kpi_data: Dict[str, Any], 
                                   start_date: Optional[pd.Timestamp], 
                                   end_date: Optional[pd.Timestamp]) -> None:
        """選択期間のKPI指標を表示"""
        if not kpi_data:
            st.warning("KPIデータが計算できませんでした")
            return
        
        # メトリクス表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            gas_cases = kpi_data.get('gas_cases', 0)
            st.metric(
                "🔴 全身麻酔手術件数",
                f"{gas_cases:,}件",
                help="選択期間内の全身麻酔手術（20分以上）総件数"
            )
        
        with col2:
            total_cases = kpi_data.get('total_cases', 0)
            st.metric(
                "📊 全手術件数",
                f"{total_cases:,}件",
                help="選択期間内の全手術総件数"
            )
        
        with col3:
            daily_avg_gas = kpi_data.get('daily_avg_gas', 0)
            # 目標との比較
            from config.hospital_targets import HospitalTargets
            hospital_target = HospitalTargets.get_daily_target()
            delta_gas = daily_avg_gas - hospital_target if hospital_target > 0 else 0
            
            st.metric(
                "📈 平日1日あたり全身麻酔手術件数",
                f"{daily_avg_gas:.1f}件/日",
                delta=f"{delta_gas:+.1f}件" if hospital_target > 0 else None,
                help="平日（月〜金）の1日あたり全身麻酔手術件数"
            )
        
        with col4:
            utilization = kpi_data.get('utilization_rate', 0)
            actual_minutes = kpi_data.get('actual_minutes', 0)
            max_minutes = kpi_data.get('max_minutes', 0)
            
            # 時間を見やすい形式に変換
            actual_hours = actual_minutes / 60
            max_hours = max_minutes / 60
            
            st.metric(
                "🏥 手術室稼働率",
                f"{utilization:.1f}%",
                delta=f"{actual_hours:.1f}h / {max_hours:.1f}h",
                help="OP-1〜12（11A,11Bを除く）11室の平日9:00〜17:15稼働率"
            )
        
        # 補足情報
        if start_date and end_date:
            period_days = kpi_data.get('period_days', 0)
            weekdays = kpi_data.get('weekdays', 0)
            actual_minutes = kpi_data.get('actual_minutes', 0)
            max_minutes = kpi_data.get('max_minutes', 0)
            
            st.caption(
                f"📅 分析期間: {start_date.strftime('%Y/%m/%d')} ～ {end_date.strftime('%Y/%m/%d')} "
                f"({period_days}日間, 平日{weekdays}日) | "
                f"実際稼働: {actual_minutes:,}分, 最大稼働: {max_minutes:,}分"
            )
    
    @staticmethod
    def _render_analysis_period_info(latest_date: Optional[pd.Timestamp], 
                                   period: str, start_date: Optional[pd.Timestamp], 
                                   end_date: Optional[pd.Timestamp]) -> None:
        """分析期間情報を表示"""
        if not latest_date or not start_date or not end_date:
            return
        
        st.markdown("---")
    
    @staticmethod
    @safe_data_operation("パフォーマンスダッシュボード表示")
    def _render_performance_dashboard(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                    latest_date: Optional[pd.Timestamp],
                                    start_date: Optional[pd.Timestamp], 
                                    end_date: Optional[pd.Timestamp]) -> None:
        """診療科別パフォーマンスダッシュボードを表示"""
        st.markdown("---")
        st.header("📊 診療科別パフォーマンスダッシュボード")
        
        if start_date and end_date:
            st.caption(f"🗓️ 分析対象期間: {start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}")
        
        # パフォーマンスサマリーを取得
        try:
            # 選択期間でデータをフィルタリング
            if start_date and end_date:
                period_df = df[
                    (df['手術実施日_dt'] >= start_date) & 
                    (df['手術実施日_dt'] <= end_date)
                ]
            else:
                period_df = df
            
            perf_summary = DashboardPage._calculate_period_performance(period_df, target_dict, start_date, end_date)
            
            if not perf_summary.empty:
                if '達成率(%)' not in perf_summary.columns:
                    st.warning("パフォーマンスデータに達成率の列が見つかりません。")
                    return
                
                # 達成率順にソート
                sorted_perf = perf_summary.sort_values("達成率(%)", ascending=False)
                
                # パフォーマンスカードの表示
                DashboardPage._render_performance_cards(sorted_perf)
                
                # 詳細データテーブル
                with st.expander("📋 詳細データテーブル"):
                    st.dataframe(sorted_perf, use_container_width=True)
            else:
                st.info("診療科別パフォーマンスを計算する十分なデータがありません。")
                
        except Exception as e:
            st.error(f"パフォーマンス計算エラー: {e}")
            logger.error(f"パフォーマンス計算エラー: {e}")
    
    @staticmethod
    def _calculate_period_performance(df: pd.DataFrame, target_dict: Dict[str, Any],
                                    start_date: Optional[pd.Timestamp], 
                                    end_date: Optional[pd.Timestamp]) -> pd.DataFrame:
        """選択期間の診療科別パフォーマンスを計算"""
        try:
            if df.empty or not target_dict:
                return pd.DataFrame()
            
            # 全身麻酔手術のみ
            gas_df = df[df['is_gas_20min'] == True] if 'is_gas_20min' in df.columns else df
            
            if gas_df.empty:
                return pd.DataFrame()
            
            # 診療科別集計
            dept_summary = []
            
            for dept, target_weekly in target_dict.items():
                if target_weekly <= 0:
                    continue
                
                dept_df = gas_df[gas_df['実施診療科'] == dept]
                
                if dept_df.empty:
                    continue
                
                # 期間の週数計算
                if start_date and end_date:
                    period_days = (end_date - start_date).days + 1
                    period_weeks = period_days / 7
                else:
                    period_weeks = 4
                
                # 実績計算
                total_cases = len(dept_df)
                weekly_avg = total_cases / period_weeks if period_weeks > 0 else 0
                
                # 最近の週の実績（最後の7日間）
                if end_date:
                    recent_week_start = end_date - pd.Timedelta(days=6)
                    recent_week_df = dept_df[dept_df['手術実施日_dt'] >= recent_week_start]
                    recent_week_cases = len(recent_week_df)
                else:
                    recent_week_cases = 0
                
                # 達成率計算
                achievement_rate = (weekly_avg / target_weekly * 100) if target_weekly > 0 else 0
                
                dept_summary.append({
                    '診療科': dept,
                    '期間平均': weekly_avg,
                    '直近週実績': recent_week_cases,
                    '週次目標': target_weekly,
                    '達成率(%)': achievement_rate
                })
            
            return pd.DataFrame(dept_summary)
            
        except Exception as e:
            logger.error(f"期間パフォーマンス計算エラー: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def _render_performance_cards(sorted_perf: pd.DataFrame) -> None:
        """パフォーマンスカードを表示"""
        def get_color_for_rate(rate):
            if rate >= 100:
                return "#28a745"
            if rate >= 80:
                return "#ffc107"
            return "#dc3545"
        
        cols = st.columns(3)
        for i, (idx, row) in enumerate(sorted_perf.iterrows()):
            with cols[i % 3]:
                rate = row["達成率(%)"]
                color = get_color_for_rate(rate)
                bar_width = min(rate, 100)
                
                # 期間平均の表示名を動的に決定
                period_label = "期間平均" if "期間平均" in row.index else "4週平均"
                period_value = row.get("期間平均", row.get("4週平均", 0))
                
                html = f"""
                <div style="
                    background-color: {color}1A; 
                    border-left: 5px solid {color}; 
                    padding: 12px; 
                    border-radius: 5px; 
                    margin-bottom: 12px; 
                    height: 165px;
                ">
                    <h5 style="margin: 0 0 10px 0; font-weight: bold; color: #333;">{row["診療科"]}</h5>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <span>{period_label}:</span>
                        <span style="font-weight: bold;">{period_value:.1f} 件</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em;">
                        <span>直近週実績:</span>
                        <span style="font-weight: bold;">{row["直近週実績"]:.0f} 件</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #666;">
                        <span>目標:</span>
                        <span>{row["週次目標"]:.1f} 件</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 1.1em; color: {color}; margin-top: 5px;">
                        <span style="font-weight: bold;">達成率:</span>
                        <span style="font-weight: bold;">{rate:.1f}%</span>
                    </div>
                    <div style="background-color: #e9ecef; border-radius: 5px; height: 6px; margin-top: 5px;">
                        <div style="width: {bar_width}%; background-color: {color}; height: 6px; border-radius: 5px;"></div>
                    </div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)
    
    @staticmethod
    @safe_data_operation("目標達成状況サマリー")
    def _render_achievement_summary(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                  latest_date: Optional[pd.Timestamp],
                                  start_date: Optional[pd.Timestamp], 
                                  end_date: Optional[pd.Timestamp]) -> None:
        """目標達成状況サマリーを表示"""
        st.markdown("---")
        st.header("🎯 目標達成状況サマリー")
        
        try:
            # 病院全体の目標達成状況
            from config.hospital_targets import HospitalTargets
            
            # 選択期間のデータを計算
            if start_date and end_date:
                period_df = df[
                    (df['手術実施日_dt'] >= start_date) & 
                    (df['手術実施日_dt'] <= end_date) &
                    (df['is_gas_20min'] == True)
                ]
                
                if not period_df.empty:
                    # 平日のみの日次平均を計算
                    weekday_df = period_df[period_df['is_weekday']]
                    if not weekday_df.empty:
                        total_days = (end_date - start_date).days + 1
                        weekdays = sum(1 for i in range(total_days) 
                                     if (start_date + pd.Timedelta(days=i)).weekday() < 5)
                        daily_avg = len(weekday_df) / weekdays if weekdays > 0 else 0
                        
                        hospital_target = HospitalTargets.get_daily_target()
                        achievement_rate = (daily_avg / hospital_target * 100) if hospital_target > 0 else 0
                        
                        # サマリーカード表示
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric(
                                "🏥 病院全体達成率", 
                                f"{achievement_rate:.1f}%",
                                delta=f"{achievement_rate - 100:.1f}%" if achievement_rate != 100 else "目標達成"
                            )
                        
                        with col2:
                            st.metric(
                                "📊 実績 (平日平均)", 
                                f"{daily_avg:.1f}件/日",
                                delta=f"{daily_avg - hospital_target:+.1f}件"
                            )
                        
                        with col3:
                            st.metric("🎯 目標", f"{hospital_target}件/日")
                        
                        with col4:
                            dept_count = len([k for k, v in target_dict.items() if v > 0]) if target_dict else 0
                            st.metric("📋 目標設定診療科", f"{dept_count}科")
                        
                        # 診療科別達成状況サマリー
                        if target_dict:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.subheader("📈 診療科別達成状況")
                                ranking_data = ranking.calculate_achievement_rates(period_df, target_dict)
                                
                                if not ranking_data.empty:
                                    # TOP3とWORST3を表示
                                    top3 = ranking_data.head(3)
                                    st.write("**🏆 TOP 3:**")
                                    for idx, row in top3.iterrows():
                                        st.write(f"• {row['診療科']}: {row['達成率(%)']:.1f}%")
                            
                            with col2:
                                if len(ranking_data) >= 3:
                                    st.subheader("📉 要注意診療科")
                                    bottom3 = ranking_data.tail(3)
                                    st.write("**⚠️ 達成率が低い科:**")
                                    for idx, row in bottom3.iterrows():
                                        if row['達成率(%)'] < 80:
                                            st.write(f"• {row['診療科']}: {row['達成率(%)']:.1f}%")
                                    
                                    # 改善アクション提案
                                    low_performers = ranking_data[ranking_data['達成率(%)'] < 80]
                                    if not low_performers.empty:
                                        st.write("**💡 推奨アクション:**")
                                        st.write("• 個別面談実施")
                                        st.write("• リソース配分見直し")
                                        st.write("• 詳細分析実施")
                    else:
                        st.info("平日データが不足しています")
                else:
                    st.info("選択期間のデータがありません")
            else:
                st.info("期間設定エラー")
                
        except Exception as e:
            st.error(f"目標達成状況計算エラー: {e}")
            logger.error(f"目標達成状況計算エラー: {e}")
    
    @staticmethod
    def _show_help_dialog() -> None:
        """ヘルプダイアログを表示"""
        with st.expander("📖 ダッシュボードの使い方", expanded=True):
            st.markdown("""
            ### 🏠 ダッシュボード概要
            
            ダッシュボードは手術分析の中心となるページです。
            
            #### 📅 期間選択機能
            - **直近4週・8週・12週**: 最新データから指定週数分を分析
            - **今年度・昨年度**: 日本の年度（4月〜3月）での分析
            - 期間に応じて自動的にKPIや達成率を再計算
            
            #### 📊 主要指標 (KPI)
            - **全身麻酔手術件数**: 選択期間の全身麻酔手術の総件数
            - **全手術件数**: 選択期間の全手術総件数
            - **平日1日あたり全身麻酔手術件数**: 平日あたりの平均手術件数
            - **手術室稼働率**: OP-1〜12の時間ベース稼働率
            
            #### 🏆 診療科別パフォーマンス
            - 選択期間でのパフォーマンス評価
            - 達成率順のランキング表示
            - 診療科間の比較分析
            
            #### 🎯 目標達成状況
            - 病院全体の達成状況
            - TOP3とワースト3の診療科
            - 改善アクション提案
            """)


# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    DashboardPage.render()