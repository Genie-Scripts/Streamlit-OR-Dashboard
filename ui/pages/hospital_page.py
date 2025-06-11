# ui/pages/hospital_page.py
"""
病院全体分析ページモジュール
病院全体のパフォーマンス分析を表示
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
import logging

from ui.session_manager import SessionManager
from ui.error_handler import safe_streamlit_operation, safe_data_operation

# 既存の分析モジュールをインポート
from analysis import weekly, ranking
from plotting import trend_plots, generic_plots

# 追加の統計分析用ライブラリ（オプション）
try:
    from sklearn.linear_model import LinearRegression
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class HospitalPage:
    """病院全体分析ページクラス"""
    
    @staticmethod
    @safe_streamlit_operation("病院全体分析ページ描画")
    def render() -> None:
        """病院全体分析ページを描画"""
        st.title("🏥 病院全体分析 - 詳細分析")
        
        # データ取得
        df = SessionManager.get_processed_df()
        target_dict = SessionManager.get_target_dict()
        latest_date = SessionManager.get_latest_date()
        
        # 分析期間情報の表示
        HospitalPage._render_analysis_period_info(df, latest_date)
        
        # 週次推移グラフ（複数パターン）
        HospitalPage._render_multiple_trend_patterns(df, target_dict)
        
        # 統計分析セクション
        HospitalPage._render_statistical_analysis(df, latest_date)
        
        # 期間別比較セクション
        HospitalPage._render_period_comparison(df, target_dict, latest_date)
        
        # トレンド分析セクション
        HospitalPage._render_trend_analysis(df, latest_date)
    
    @staticmethod
    @safe_data_operation("分析期間情報表示")
    def _render_analysis_period_info(df: pd.DataFrame, latest_date: Optional[pd.Timestamp]) -> None:
        """分析期間情報を表示"""
        if latest_date is None:
            st.warning("分析可能な日付データがありません。")
            return
        
        analysis_end_sunday = weekly.get_analysis_end_date(latest_date)
        if analysis_end_sunday is None:
            st.warning("分析可能な日付データがありません。")
            return
        
        excluded_days = (latest_date - analysis_end_sunday).days
        df_complete_weeks = df[df['手術実施日_dt'] <= analysis_end_sunday]
        total_records = len(df_complete_weeks)
        
        # メトリクス表示
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 総レコード数", f"{total_records:,}件")
        with col2:
            st.metric("📅 最新データ日", latest_date.strftime('%Y/%m/%d'))
        with col3:
            st.metric("🎯 分析終了日", analysis_end_sunday.strftime('%Y/%m/%d'))
        with col4:
            st.metric("⚠️ 除外日数", f"{excluded_days}日")
        
        st.caption(
            f"💡 最新データが{latest_date.strftime('%A')}のため、"
            f"分析精度向上のため前の日曜日({analysis_end_sunday.strftime('%Y/%m/%d')})までを分析対象としています。"
        )
        st.markdown("---")
    
    @staticmethod
    @safe_data_operation("複数トレンドパターン表示")
    def _render_multiple_trend_patterns(df: pd.DataFrame, target_dict: Dict[str, Any]) -> None:
        """複数の週次推移パターンを表示"""
        st.subheader("📈 週次推移分析（複数パターン）")
        
        try:
            # 完全週データ取得
            summary = weekly.get_summary(df, use_complete_weeks=True)
            
            if summary.empty:
                st.warning("週次推移データがありません。")
                return
            
            # タブで複数パターンを表示
            tab1, tab2, tab3 = st.tabs(["📊 標準推移", "📈 移動平均", "🎯 目標比較"])
            
            with tab1:
                st.markdown("**標準的な週次推移（平日1日平均）**")
                fig1 = trend_plots.create_weekly_summary_chart(summary, "病院全体 週次推移", target_dict)
                st.plotly_chart(fig1, use_container_width=True)
            
            with tab2:
                st.markdown("**移動平均トレンド（4週移動平均）**")
                if len(summary) >= 4:
                    summary_ma = summary.copy()
                    summary_ma['4週移動平均'] = summary_ma['平日1日平均件数'].rolling(window=4).mean()
                    
                    # 移動平均チャートを既存関数で作成
                    fig2 = trend_plots.create_weekly_summary_chart(
                        summary_ma, "移動平均トレンド（4週移動平均）", target_dict
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    # 移動平均の数値テーブル
                    with st.expander("移動平均データ"):
                        ma_display = summary_ma[['週開始日', '平日1日平均件数', '4週移動平均']].dropna()
                        st.dataframe(ma_display.round(1), use_container_width=True)
                else:
                    st.info("移動平均計算には最低4週間のデータが必要です。")
            
            with tab3:
                st.markdown("**目標達成率推移**")
                if target_dict:
                    from config.hospital_targets import HospitalTargets
                    hospital_target = HospitalTargets.get_daily_target()
                    
                    summary_target = summary.copy()
                    summary_target['達成率(%)'] = (summary_target['平日1日平均件数'] / hospital_target * 100)
                    
                    # 達成率チャートを既存関数で作成
                    fig3 = trend_plots.create_weekly_summary_chart(
                        summary_target, "目標達成率推移", target_dict
                    )
                    st.plotly_chart(fig3, use_container_width=True)
                    
                    # 達成率統計
                    avg_achievement = summary_target['達成率(%)'].mean()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("平均達成率", f"{avg_achievement:.1f}%")
                    with col2:
                        above_target = len(summary_target[summary_target['達成率(%)'] >= 100])
                        st.metric("目標達成週数", f"{above_target}/{len(summary_target)}週")
                    with col3:
                        max_achievement = summary_target['達成率(%)'].max()
                        st.metric("最高達成率", f"{max_achievement:.1f}%")
                else:
                    st.info("目標データが設定されていません。")
            
            # 統計サマリー
            with st.expander("📊 統計サマリー"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("🗓️ 分析週数", f"{len(summary)}週")
                    st.metric("📈 最大値", f"{summary['平日1日平均件数'].max():.1f}件/日")
                
                with col2:
                    st.metric("📉 最小値", f"{summary['平日1日平均件数'].min():.1f}件/日") 
                    st.metric("📊 平均値", f"{summary['平日1日平均件数'].mean():.1f}件/日")
                
                with col3:
                    if len(summary) >= 2:
                        recent_avg = summary.tail(4)['平日1日平均件数'].mean()
                        earlier_avg = summary.head(4)['平日1日平均件数'].mean()
                        trend_change = ((recent_avg/earlier_avg - 1)*100) if earlier_avg > 0 else 0
                        st.metric("📈 トレンド変化", f"{trend_change:+.1f}%")
                        st.metric("🔄 標準偏差", f"{summary['平日1日平均件数'].std():.1f}")
                
        except Exception as e:
            st.error(f"週次推移分析エラー: {e}")
            logger.error(f"週次推移分析エラー: {e}")
    
    @staticmethod
    @safe_data_operation("統計分析表示")
    def _render_statistical_analysis(df: pd.DataFrame, latest_date: Optional[pd.Timestamp]) -> None:
        """統計分析セクションを表示"""
        st.markdown("---")
        st.subheader("📊 統計分析・パフォーマンス指標")
        
        try:
            if latest_date is None:
                st.warning("統計分析に必要な日付データがありません。")
                return
            
            # 直近4週間のデータでKPI計算
            analysis_end_date = weekly.get_analysis_end_date(latest_date)
            if analysis_end_date:
                four_weeks_ago = analysis_end_date - pd.Timedelta(days=27)
                recent_df = df[
                    (df['手術実施日_dt'] >= four_weeks_ago) & 
                    (df['手術実施日_dt'] <= analysis_end_date) &
                    (df['is_gas_20min'] == True)
                ]
                
                if recent_df.empty:
                    st.warning("統計分析対象データがありません。")
                    return
                
                # KPI計算
                kpi_summary = ranking.get_kpi_summary(df, latest_date)
                
                # KPI表示
                st.markdown("**📈 主要業績指標 (KPI)**")
                generic_plots.display_kpi_metrics(kpi_summary)
                
                # 診療科別統計
                st.markdown("**🏥 診療科別統計分析**")
                dept_stats = HospitalPage._calculate_department_statistics(recent_df)
                
                if not dept_stats.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**上位5診療科 (件数)**")
                        top5 = dept_stats.head().round(1)
                        st.dataframe(top5, use_container_width=True)
                    
                    with col2:
                        st.markdown("**統計サマリー**")
                        st.write(f"• 診療科数: {len(dept_stats)}科")
                        st.write(f"• 平均件数: {dept_stats['合計件数'].mean():.1f}件")
                        st.write(f"• 最大差: {dept_stats['合計件数'].max() - dept_stats['合計件数'].min():.1f}件")
                        st.write(f"• 標準偏差: {dept_stats['合計件数'].std():.1f}")
                
                # 時系列統計（機械学習が利用可能な場合）
                if SKLEARN_AVAILABLE:
                    HospitalPage._render_advanced_statistics(recent_df)
                
            else:
                st.warning("分析期間を設定できませんでした。")
                
        except Exception as e:
            st.error(f"統計分析エラー: {e}")
            logger.error(f"統計分析エラー: {e}")
    
    @staticmethod
    def _calculate_department_statistics(df: pd.DataFrame) -> pd.DataFrame:
        """診療科別統計を計算"""
        try:
            dept_stats = df.groupby('実施診療科').agg({
                '手術実施日_dt': 'count',
                'is_weekday': 'sum'
            }).rename(columns={
                '手術実施日_dt': '合計件数',
                'is_weekday': '平日件数'
            })
            
            dept_stats['平日割合(%)'] = (dept_stats['平日件数'] / dept_stats['合計件数'] * 100).round(1)
            dept_stats = dept_stats.sort_values('合計件数', ascending=False)
            
            return dept_stats
            
        except Exception as e:
            logger.error(f"診療科別統計計算エラー: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def _render_advanced_statistics(df: pd.DataFrame) -> None:
        """高度統計分析（機械学習を使用）"""
        try:
            st.markdown("**🔬 高度統計分析**")
            
            # 日次件数の時系列データ準備
            daily_counts = df.groupby('手術実施日_dt').size().reset_index(name='件数')
            daily_counts = daily_counts.sort_values('手術実施日_dt')
            
            if len(daily_counts) >= 7:
                # 線形回帰でトレンド分析
                X = np.arange(len(daily_counts)).reshape(-1, 1)
                y = daily_counts['件数'].values
                
                model = LinearRegression()
                model.fit(X, y)
                
                trend_slope = model.coef_[0]
                r_squared = model.score(X, y)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    trend_direction = "上昇" if trend_slope > 0 else "下降"
                    st.metric("📈 トレンド傾向", trend_direction)
                
                with col2:
                    st.metric("📊 回帰係数", f"{trend_slope:.3f}")
                
                with col3:
                    st.metric("🎯 決定係数 (R²)", f"{r_squared:.3f}")
                
                st.caption("💡 決定係数が高いほど、トレンドの予測精度が高くなります")
            else:
                st.info("高度統計分析には最低7日分のデータが必要です。")
                
        except Exception as e:
            logger.error(f"高度統計分析エラー: {e}")
            st.warning("高度統計分析でエラーが発生しました。")
    
    @staticmethod
    @safe_data_operation("期間比較表示")
    def _render_period_comparison(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                 latest_date: Optional[pd.Timestamp]) -> None:
        """期間別比較セクションを表示"""
        st.markdown("---")
        st.subheader("📅 期間別比較分析")
        
        try:
            if latest_date is None:
                st.warning("期間比較に必要な日付データがありません。")
                return
            
            analysis_end_date = weekly.get_analysis_end_date(latest_date)
            if not analysis_end_date:
                st.warning("分析期間を設定できませんでした。")
                return
            
            # 期間設定
            periods = {
                "直近4週": 28,
                "直近8週": 56,
                "直近12週": 84
            }
            
            comparison_data = []
            
            for period_name, days in periods.items():
                start_date = analysis_end_date - pd.Timedelta(days=days-1)
                period_df = df[
                    (df['手術実施日_dt'] >= start_date) & 
                    (df['手術実施日_dt'] <= analysis_end_date) &
                    (df['is_gas_20min'] == True)
                ]
                
                if not period_df.empty:
                    # 平日のみの件数
                    weekday_df = period_df[period_df['is_weekday']]
                    total_days = days
                    weekdays = sum(1 for i in range(total_days) 
                                 if (start_date + pd.Timedelta(days=i)).weekday() < 5)
                    
                    daily_avg = len(weekday_df) / weekdays if weekdays > 0 else 0
                    total_cases = len(period_df)
                    
                    comparison_data.append({
                        "期間": period_name,
                        "総件数": total_cases,
                        "平日平均/日": round(daily_avg, 1),
                        "期間": f"{start_date.strftime('%m/%d')} - {analysis_end_date.strftime('%m/%d')}"
                    })
            
            if comparison_data:
                # 比較テーブル表示
                comparison_df = pd.DataFrame(comparison_data)
                st.dataframe(comparison_df, use_container_width=True)
                
                # 目標達成状況比較
                if target_dict:
                    from config.hospital_targets import HospitalTargets
                    hospital_target = HospitalTargets.get_daily_target()
                    
                    st.markdown("**🎯 目標達成状況比較**")
                    
                    for data in comparison_data:
                        achievement_rate = (data["平日平均/日"] / hospital_target * 100) if hospital_target > 0 else 0
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.write(f"**{data['期間']}**")
                        with col2:
                            st.write(f"{data['平日平均/日']:.1f} 件/日")
                        with col3:
                            color = "🟢" if achievement_rate >= 100 else "🟡" if achievement_rate >= 80 else "🔴"
                            st.write(f"{color} {achievement_rate:.1f}%")
                
                # トレンド方向の分析
                if len(comparison_data) >= 2:
                    recent_avg = comparison_data[0]["平日平均/日"]  # 直近4週
                    longer_avg = comparison_data[-1]["平日平均/日"]  # 直近12週
                    
                    trend_change = ((recent_avg / longer_avg - 1) * 100) if longer_avg > 0 else 0
                    
                    st.markdown("**📈 トレンド分析**")
                    if trend_change > 5:
                        st.success(f"🔺 上昇トレンド: {trend_change:+.1f}%")
                    elif trend_change < -5:
                        st.error(f"🔻 下降トレンド: {trend_change:+.1f}%")
                    else:
                        st.info(f"➡️ 安定トレンド: {trend_change:+.1f}%")
            else:
                st.warning("期間比較データがありません。")
                
        except Exception as e:
            st.error(f"期間比較分析エラー: {e}")
            logger.error(f"期間比較分析エラー: {e}")
    
    @staticmethod
    @safe_data_operation("トレンド分析表示")
    def _render_trend_analysis(df: pd.DataFrame, latest_date: Optional[pd.Timestamp]) -> None:
        """トレンド分析セクションを表示"""
        st.markdown("---")
        st.subheader("🔮 詳細トレンド分析・予測")
        
        try:
            if latest_date is None:
                st.warning("トレンド分析に必要な日付データがありません。")
                return
            
            # 週次データでトレンド分析
            summary = weekly.get_summary(df, use_complete_weeks=True)
            
            if summary.empty:
                st.warning("トレンド分析用データがありません。")
                return
            
            tab1, tab2, tab3 = st.tabs(["📈 基本トレンド", "📊 季節性分析", "🔮 短期予測"])
            
            with tab1:
                HospitalPage._render_basic_trend_analysis(summary)
            
            with tab2:
                HospitalPage._render_seasonality_analysis(summary, df)
            
            with tab3:
                HospitalPage._render_short_term_prediction(summary)
                
        except Exception as e:
            st.error(f"トレンド分析エラー: {e}")
            logger.error(f"トレンド分析エラー: {e}")
    
    @staticmethod
    def _render_basic_trend_analysis(summary: pd.DataFrame) -> None:
        """基本トレンド分析"""
        st.markdown("**📈 基本トレンド指標**")
        
        if len(summary) < 4:
            st.info("基本トレンド分析には最低4週間のデータが必要です。")
            return
        
        # 最近4週 vs 前4週の比較
        recent_4weeks = summary.tail(4)['平日1日平均件数'].mean()
        previous_4weeks = summary.iloc[-8:-4]['平日1日平均件数'].mean() if len(summary) >= 8 else None
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 直近4週平均", f"{recent_4weeks:.1f}件/日")
        
        with col2:
            if previous_4weeks:
                change = recent_4weeks - previous_4weeks
                change_pct = (change / previous_4weeks * 100) if previous_4weeks > 0 else 0
                st.metric("📈 前4週比較", f"{previous_4weeks:.1f}件/日", 
                         delta=f"{change:+.1f} ({change_pct:+.1f}%)")
            else:
                st.metric("📈 前4週比較", "データ不足")
        
        with col3:
            volatility = summary['平日1日平均件数'].std()
            st.metric("📊 変動度", f"{volatility:.1f}")
        
        with col4:
            max_week = summary['平日1日平均件数'].max()
            min_week = summary['平日1日平均件数'].min()
            range_val = max_week - min_week
            st.metric("📏 最大幅", f"{range_val:.1f}")
        
        # トレンド方向
        if len(summary) >= 6:
            recent_trend = summary.tail(6)['平日1日平均件数'].mean()
            earlier_trend = summary.head(6)['平日1日平均件数'].mean()
            
            if recent_trend > earlier_trend * 1.05:
                st.success("🔺 **明確な上昇トレンド** を検出")
            elif recent_trend < earlier_trend * 0.95:
                st.error("🔻 **明確な下降トレンド** を検出")
            else:
                st.info("➡️ **安定的なトレンド** を維持")
    
    @staticmethod
    def _render_seasonality_analysis(summary: pd.DataFrame, df: pd.DataFrame) -> None:
        """季節性分析"""
        st.markdown("**🗓️ 季節性・周期性分析**")
        
        try:
            # 曜日別分析
            if '手術実施日_dt' in df.columns:
                df_copy = df.copy()
                df_copy['曜日'] = df_copy['手術実施日_dt'].dt.day_name()
                df_copy['曜日番号'] = df_copy['手術実施日_dt'].dt.dayofweek
                
                # 平日のみで曜日別件数
                weekday_df = df_copy[df_copy['is_weekday'] == True]
                
                if not weekday_df.empty:
                    dow_analysis = weekday_df.groupby(['曜日', '曜日番号']).size().reset_index(name='件数')
                    dow_analysis = dow_analysis.sort_values('曜日番号')
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**曜日別傾向**")
                        for _, row in dow_analysis.iterrows():
                            st.write(f"• {row['曜日']}: {row['件数']}件")
                    
                    with col2:
                        if len(dow_analysis) > 1:
                            max_dow = dow_analysis.loc[dow_analysis['件数'].idxmax(), '曜日']
                            min_dow = dow_analysis.loc[dow_analysis['件数'].idxmin(), '曜日']
                            st.markdown("**パターン分析**")
                            st.write(f"• 最多曜日: {max_dow}")
                            st.write(f"• 最少曜日: {min_dow}")
                            
                            variance = dow_analysis['件数'].var()
                            if variance > dow_analysis['件数'].mean() * 0.1:
                                st.write("• 曜日による変動が大きい")
                            else:
                                st.write("• 曜日による変動は小さい")
            
            # 月別傾向（データが複数月にわたる場合）
            if len(summary) >= 8:  # 約2ヶ月分
                st.markdown("**📅 月次傾向分析**")
                df_monthly = df.copy()
                df_monthly['年月'] = df_monthly['手術実施日_dt'].dt.to_period('M')
                monthly_counts = df_monthly.groupby('年月').size()
                
                if len(monthly_counts) >= 2:
                    st.write("月別推移:")
                    for period, count in monthly_counts.items():
                        st.write(f"• {period}: {count}件")
                else:
                    st.info("月次傾向分析には複数月のデータが必要です。")
            else:
                st.info("季節性分析には8週間以上のデータが推奨されます。")
                
        except Exception as e:
            logger.error(f"季節性分析エラー: {e}")
            st.warning("季節性分析でエラーが発生しました。")
    
    @staticmethod
    def _render_short_term_prediction(summary: pd.DataFrame) -> None:
        """短期予測"""
        st.markdown("**🔮 短期予測（次週・次月）**")
        
        if len(summary) < 4:
            st.info("予測には最低4週間のデータが必要です。")
            return
        
        try:
            # 単純移動平均による予測
            recent_4weeks_avg = summary.tail(4)['平日1日平均件数'].mean()
            recent_2weeks_avg = summary.tail(2)['平日1日平均件数'].mean()
            
            # トレンド調整
            if len(summary) >= 6:
                trend_factor = recent_2weeks_avg / recent_4weeks_avg if recent_4weeks_avg > 0 else 1
            else:
                trend_factor = 1
            
            # 予測値計算
            next_week_prediction = recent_4weeks_avg * trend_factor
            confidence_range = summary['平日1日平均件数'].std() * 0.5
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🔮 次週予測", f"{next_week_prediction:.1f}件/日")
            
            with col2:
                st.metric("📊 予測範囲", 
                         f"{next_week_prediction-confidence_range:.1f} - {next_week_prediction+confidence_range:.1f}")
            
            with col3:
                # 目標との比較
                from config.hospital_targets import HospitalTargets
                hospital_target = HospitalTargets.get_daily_target()
                predicted_achievement = (next_week_prediction / hospital_target * 100) if hospital_target > 0 else 0
                st.metric("🎯 予測達成率", f"{predicted_achievement:.1f}%")
            
            # 予測の信頼性
            data_points = len(summary)
            variability = summary['平日1日平均件数'].std() / summary['平日1日平均件数'].mean()
            
            st.markdown("**📊 予測の信頼性**")
            
            if data_points >= 8 and variability < 0.2:
                st.success("🟢 高い信頼性: 十分なデータと安定した傾向")
            elif data_points >= 6 and variability < 0.3:
                st.warning("🟡 中程度の信頼性: データまたは安定性に課題")
            else:
                st.error("🔴 低い信頼性: データ不足または高い変動性")
            
            st.caption(f"💡 データ期間: {data_points}週, 変動係数: {variability:.2f}")
            
        except Exception as e:
            logger.error(f"短期予測エラー: {e}")
            st.warning("短期予測でエラーが発生しました。")
    
    @staticmethod
    @safe_data_operation("パフォーマンスダッシュボード表示")
    def _render_performance_dashboard(df: pd.DataFrame, target_dict: Dict[str, Any], 
                                    latest_date: Optional[pd.Timestamp]) -> None:
        """診療科別パフォーマンスダッシュボードを表示"""
        st.subheader("📊 診療科別パフォーマンスダッシュボード（直近4週データ分析）")
        
        if latest_date:
            analysis_end_sunday = weekly.get_analysis_end_date(latest_date)
            if analysis_end_sunday:
                four_weeks_ago = analysis_end_sunday - pd.Timedelta(days=27)
                st.caption(f"🗓️ 分析対象期間: {four_weeks_ago.strftime('%Y/%m/%d')} ~ {analysis_end_sunday.strftime('%Y/%m/%d')}")
        
        # パフォーマンスサマリーを取得
        try:
            perf_summary = ranking.get_department_performance_summary(df, target_dict, latest_date)
            
            if not perf_summary.empty:
                if '達成率(%)' not in perf_summary.columns:
                    st.warning("パフォーマンスデータに達成率の列が見つかりません。")
                    return
                
                # 達成率順にソート
                sorted_perf = perf_summary.sort_values("達成率(%)", ascending=False)
                
                # パフォーマンスカードの表示
                HospitalPage._render_performance_cards(sorted_perf)
                
                # 詳細データテーブル
                with st.expander("詳細データテーブル"):
                    st.dataframe(sorted_perf, use_container_width=True)
            else:
                st.info("診療科別パフォーマンスを計算する十分なデータがありません。")
                
        except Exception as e:
            st.error(f"パフォーマンス計算エラー: {e}")
            logger.error(f"パフォーマンス計算エラー: {e}")
    
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
                        <span>4週平均:</span>
                        <span style="font-weight: bold;">{row["4週平均"]:.1f} 件</span>
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
    @safe_data_operation("週次推移表示")
    def _render_weekly_trend_section(df: pd.DataFrame, target_dict: Dict[str, Any]) -> None:
        """週次推移セクションを表示"""
        st.markdown("---")
        st.subheader("📈 全身麻酔手術件数 週次推移（完全週データ）")
        
        try:
            summary = weekly.get_summary(df, use_complete_weeks=True)
            
            if not summary.empty:
                fig = trend_plots.create_weekly_summary_chart(summary, "", target_dict)
                st.plotly_chart(fig, use_container_width=True)
                
                # 統計情報
                with st.expander("📊 統計情報"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**基本統計:**")
                        st.write(f"• 週数: {len(summary)}週")
                        st.write(f"• 最大値: {summary['平日1日平均件数'].max():.1f}件/日")
                        st.write(f"• 最小値: {summary['平日1日平均件数'].min():.1f}件/日")
                        st.write(f"• 平均値: {summary['平日1日平均件数'].mean():.1f}件/日")
                    
                    with col2:
                        st.write("**トレンド分析:**")
                        if len(summary) >= 2:
                            recent_avg = summary.tail(4)['平日1日平均件数'].mean()
                            earlier_avg = summary.head(4)['平日1日平均件数'].mean()
                            trend = "上昇" if recent_avg > earlier_avg else "下降"
                            st.write(f"• 直近トレンド: {trend}")
                            st.write(f"• 変化率: {((recent_avg/earlier_avg - 1)*100):+.1f}%")
            else:
                st.warning("週次トレンドデータがありません")
                
        except Exception as e:
            st.error(f"週次推移分析エラー: {e}")
            logger.error(f"週次推移分析エラー: {e}")


# ページルーター用の関数
def render():
    """ページルーター用のレンダー関数"""
    HospitalPage.render()