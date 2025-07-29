# analysis/surgery_high_score.py
"""
手術ダッシュボード用ハイスコア計算エンジン
診療科別の週次パフォーマンス評価とランキング生成

評価指標:
- 週の全身麻酔手術件数 (70点): 直近週達成度30点 + 改善度20点 + 安定性15点 + 持続性5点
- 週の全手術件数 (15点): ランキング10点 + 改善度5点
- 週の総手術時間 (15点): ランキング10点 + 改善度5点
総合100点満点でS/A/B/C/Dグレード判定
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger(__name__)


def calculate_surgery_high_scores(df: pd.DataFrame, target_dict: Dict[str, float], 
                                period: str = "直近12週") -> List[Dict[str, Any]]:
    """
    手術データから診療科別ハイスコアを計算
    
    Args:
        df: 手術データフレーム（必須列: 手術実施日_dt, 実施診療科, 入室時刻, 退室時刻）
        target_dict: 診療科別目標値辞書 {診療科名: 週次目標件数}
        period: 分析期間 ("直近4週", "直近8週", "直近12週")
    
    Returns:
        診療科スコアリスト（スコア順ソート済み）
        
    Example:
        dept_scores = calculate_surgery_high_scores(df, target_dict, "直近12週")
        for dept in dept_scores[:3]:  # TOP3
            print(f"{dept['display_name']}: {dept['total_score']:.1f}点 ({dept['grade']})")
    """
    try:
        if df.empty:
            logger.warning("手術データが空です")
            return []
        
        logger.info(f"ハイスコア計算開始: データ{len(df)}件, 期間{period}")
        
        # 期間フィルタリング
        start_date, end_date = _get_period_dates(df, period)
        if not start_date or not end_date:
            logger.error("期間計算に失敗しました")
            return []
        
        period_df = df[
            (df['手術実施日_dt'] >= start_date) & 
            (df['手術実施日_dt'] <= end_date)
        ].copy()
        
        if period_df.empty:
            logger.warning(f"期間 {period} にデータがありません")
            return []
        
        logger.info(f"期間フィルタ後: {len(period_df)}件 ({start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')})")
        
        # 週次データ準備
        weekly_df = _prepare_weekly_data(period_df)
        if weekly_df.empty:
            logger.warning("週次データの準備に失敗しました")
            return []
        
        # 診療科別スコア計算
        dept_scores = []
        departments = weekly_df['実施診療科'].dropna().unique()
        
        logger.info(f"対象診療科: {len(departments)}科")
        
        for dept in departments:
            dept_data = weekly_df[weekly_df['実施診療科'] == dept]
            if len(dept_data) < 3:  # 最小データ数チェック
                logger.debug(f"診療科 {dept}: データ不足 ({len(dept_data)}件)")
                continue
            
            score_data = _calculate_department_score(
                dept_data, dept, target_dict, start_date, end_date, weekly_df
            )
            
            if score_data:
                dept_scores.append(score_data)
                logger.debug(f"診療科 {dept}: スコア {score_data['total_score']:.1f}点")
        
        # スコア順でソート
        dept_scores_sorted = sorted(dept_scores, key=lambda x: x['total_score'], reverse=True)
        
        logger.info(f"ハイスコア計算完了: {len(dept_scores_sorted)}診療科")
        return dept_scores_sorted
        
    except Exception as e:
        logger.error(f"ハイスコア計算エラー: {e}", exc_info=True)
        return []


def _prepare_weekly_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    週次データを準備（月曜始まり）
    
    手術時間計算、全身麻酔判定、平日判定を含む
    """
    try:
        weekly_df = df.copy()
        
        # 週開始日を計算（月曜始まり）
        weekly_df['week_start'] = weekly_df['手術実施日_dt'].dt.to_period('W-MON').dt.start_time
        
        # 手術時間計算（入退室時刻から）
        if '入室時刻' in weekly_df.columns and '退室時刻' in weekly_df.columns:
            weekly_df['手術時間_時間'] = _calculate_surgery_hours(
                weekly_df['入室時刻'], 
                weekly_df['退室時刻'], 
                weekly_df['手術実施日_dt']
            )
        else:
            logger.warning("入退室時刻列が見つかりません。デフォルト値を使用します")
            weekly_df['手術時間_時間'] = 2.0  # デフォルト2時間
        
        # 全身麻酔フラグの確認・作成
        if 'is_gas_20min' not in weekly_df.columns:
            if '麻酔種別' in weekly_df.columns:
                weekly_df['is_gas_20min'] = weekly_df['麻酔種別'].str.contains(
                    '全身麻酔.*20分以上', na=False, regex=True
                )
                logger.info(f"全身麻酔判定: {weekly_df['is_gas_20min'].sum()}件")
            else:
                logger.warning("麻酔種別列が見つかりません。全て対象とします")
                weekly_df['is_gas_20min'] = True
        
        # 平日フラグの確認・作成
        if 'is_weekday' not in weekly_df.columns:
            weekly_df['is_weekday'] = weekly_df['手術実施日_dt'].dt.weekday < 5
        
        # データ品質チェック
        total_weeks = weekly_df['week_start'].nunique()
        logger.info(f"週次データ準備完了: {len(weekly_df)}件, {total_weeks}週間")
        
        return weekly_df
        
    except Exception as e:
        logger.error(f"週次データ準備エラー: {e}")
        return pd.DataFrame()


def _calculate_surgery_hours(entry_times: pd.Series, exit_times: pd.Series, 
                           surgery_dates: pd.Series) -> pd.Series:
    """
    入退室時刻から手術時間を計算（深夜跨ぎ対応）
    
    Examples:
        入室: "9:30", 退室: "11:15" → 1.75時間
        入室: "23:30", 退室: "1:15" → 1.75時間（深夜跨ぎ）
    """
    try:
        hours = pd.Series(0.0, index=entry_times.index)
        error_count = 0
        
        for idx in entry_times.index:
            try:
                entry_time = entry_times[idx]
                exit_time = exit_times[idx]
                surgery_date = surgery_dates[idx]
                
                if pd.isna(entry_time) or pd.isna(exit_time) or pd.isna(surgery_date):
                    hours[idx] = 2.0  # デフォルト値
                    error_count += 1
                    continue
                
                # 時刻をdatetimeに変換
                entry_dt = _parse_time_to_datetime(str(entry_time).strip(), surgery_date)
                exit_dt = _parse_time_to_datetime(str(exit_time).strip(), surgery_date)
                
                if not entry_dt or not exit_dt:
                    hours[idx] = 2.0
                    error_count += 1
                    continue
                
                # 深夜跨ぎの処理
                if exit_dt < entry_dt:
                    exit_dt += timedelta(days=1)
                
                # 手術時間を時間単位で計算
                duration = exit_dt - entry_dt
                hours[idx] = duration.total_seconds() / 3600
                
                # 妥当性チェック（0.25時間〜24時間）
                if not (0.25 <= hours[idx] <= 24):
                    hours[idx] = 2.0
                    error_count += 1
                    
            except Exception:
                hours[idx] = 2.0
                error_count += 1
        
        if error_count > 0:
            logger.warning(f"手術時間計算: {error_count}件でエラー（デフォルト値2.0時間を使用）")
        
        logger.info(f"手術時間計算完了: 平均{hours.mean():.1f}時間, 最大{hours.max():.1f}時間")
        return hours
        
    except Exception as e:
        logger.error(f"手術時間計算エラー: {e}")
        return pd.Series(2.0, index=entry_times.index)


def _parse_time_to_datetime(time_str: str, date_obj: pd.Timestamp) -> Optional[datetime]:
    """
    時刻文字列をdatetimeに変換
    
    対応形式: "9:30", "09:30", "930", 9.5（Excel時刻）
    """
    try:
        if ':' in time_str:
            # HH:MM形式
            parts = time_str.split(':')
            if len(parts) >= 2:
                hour = int(parts[0])
                minute = int(parts[1])
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return datetime.combine(date_obj.date(), time(hour, minute))
        
        elif time_str.isdigit() and len(time_str) in [3, 4]:
            # HMM または HHMM形式
            if len(time_str) == 3:  # HMM (例: "930")
                hour = int(time_str[0])
                minute = int(time_str[1:])
            else:  # HHMM (例: "0930")
                hour = int(time_str[:2])
                minute = int(time_str[2:])
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return datetime.combine(date_obj.date(), time(hour, minute))
        
        else:
            # Excel時刻形式（数値）を試行
            try:
                time_float = float(time_str)
                if 0 <= time_float <= 1:
                    # 0.5 = 12:00, 0.25 = 6:00 など
                    total_seconds = time_float * 24 * 3600
                    hour = int(total_seconds // 3600)
                    minute = int((total_seconds % 3600) // 60)
                    
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return datetime.combine(date_obj.date(), time(hour, minute))
            except ValueError:
                pass
        
        return None
        
    except Exception:
        return None


def _calculate_department_score(dept_data: pd.DataFrame, dept_name: str, 
                               target_dict: Dict[str, float], 
                               start_date: pd.Timestamp, end_date: pd.Timestamp,
                               all_weekly_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    診療科別スコアを計算（100点満点）
    
    スコア構成:
    - 全身麻酔手術件数評価 (70点)
    - 全手術件数評価 (15点) 
    - 総手術時間評価 (15点)
    """
    try:
        # 週次集計
        weekly_stats = dept_data.groupby('week_start').agg({
            'is_gas_20min': 'sum',      # 週次全身麻酔件数
            '手術実施日_dt': 'count',    # 週次全手術件数  
            '手術時間_時間': 'sum'       # 週次総手術時間
        }).rename(columns={
            'is_gas_20min': 'weekly_gas_cases',
            '手術実施日_dt': 'weekly_total_cases',
            '手術時間_時間': 'weekly_total_hours'
        })
        
        if weekly_stats.empty:
            return None
        
        # 基本統計
        avg_gas_cases = weekly_stats['weekly_gas_cases'].mean()
        avg_total_cases = weekly_stats['weekly_total_cases'].mean()
        avg_total_hours = weekly_stats['weekly_total_hours'].mean()
        
        # 最新週実績
        latest_week = weekly_stats.index.max()
        latest_gas_cases = weekly_stats.loc[latest_week, 'weekly_gas_cases']
        latest_total_cases = weekly_stats.loc[latest_week, 'weekly_total_cases']
        latest_total_hours = weekly_stats.loc[latest_week, 'weekly_total_hours']
        
        # 目標との比較（全身麻酔手術件数）
        target_gas_cases = target_dict.get(dept_name, 0)
        achievement_rate = (latest_gas_cases / target_gas_cases * 100) if target_gas_cases > 0 else 0
        
        # 他診療科との比較ランキング計算
        dept_rankings = _calculate_department_rankings(all_weekly_df, dept_name)
        
        # スコア計算
        score_components = _calculate_score_components(
            weekly_stats, target_gas_cases, achievement_rate,
            avg_gas_cases, avg_total_cases, avg_total_hours,
            latest_gas_cases, latest_total_cases, latest_total_hours,
            dept_rankings
        )
        
        total_score = sum(score_components.values())
        grade = _determine_grade(total_score)
        
        # 改善度計算
        improvement_rate = _calculate_improvement_rate(weekly_stats['weekly_gas_cases'])
        
        return {
            'entity_name': dept_name,
            'display_name': dept_name,
            'total_score': round(total_score, 1),
            'grade': grade,
            'latest_gas_cases': int(latest_gas_cases),
            'latest_total_cases': int(latest_total_cases),
            'latest_total_hours': round(latest_total_hours, 1),
            'avg_gas_cases': round(avg_gas_cases, 1),
            'avg_total_cases': round(avg_total_cases, 1),
            'avg_total_hours': round(avg_total_hours, 1),
            'target_gas_cases': target_gas_cases,
            'achievement_rate': round(achievement_rate, 1),
            'improvement_rate': round(improvement_rate, 1),
            'score_components': {k: round(v, 1) for k, v in score_components.items()},
            'latest_achievement_rate': round(achievement_rate, 1),
            'weekly_data': weekly_stats.to_dict('index'),
            'rankings': dept_rankings
        }
        
    except Exception as e:
        logger.error(f"診療科 {dept_name} のスコア計算エラー: {e}")
        return None


def _calculate_department_rankings(all_weekly_df: pd.DataFrame, dept_name: str) -> Dict[str, int]:
    """診療科間ランキングを計算"""
    try:
        # 最新週の診療科別実績
        latest_week = all_weekly_df['week_start'].max()
        latest_week_data = all_weekly_df[all_weekly_df['week_start'] == latest_week]
        
        dept_stats = latest_week_data.groupby('実施診療科').agg({
            '手術実施日_dt': 'count',
            '手術時間_時間': 'sum'
        }).rename(columns={
            '手術実施日_dt': 'total_cases',
            '手術時間_時間': 'total_hours'
        })
        
        # === ▼▼▼ 修正箇所 ▼▼▼ ===
        # 診療科が最新週データに存在しない場合の対応
        if dept_name not in dept_stats.index:
            total_depts = len(dept_stats)
            return {
                'total_cases_rank': total_depts + 1,
                'total_hours_rank': total_depts + 1,
                'total_departments': total_depts
            }
        # === ▲▲▲ 修正箇所 ▲▲▲ ===

        # ランキング計算
        total_cases_rank = (dept_stats['total_cases'] > dept_stats.loc[dept_name, 'total_cases']).sum() + 1
        total_hours_rank = (dept_stats['total_hours'] > dept_stats.loc[dept_name, 'total_hours']).sum() + 1
        
        return {
            'total_cases_rank': total_cases_rank,
            'total_hours_rank': total_hours_rank,
            'total_departments': len(dept_stats)
        }
        
    except Exception as e:
        # エラーログに dept_name を含める
        logger.error(f"ランキング計算エラー ({dept_name}): {e}", exc_info=True)
        return {'total_cases_rank': 1, 'total_hours_rank': 1, 'total_departments': 1}


def _calculate_score_components(weekly_stats: pd.DataFrame, target_gas_cases: float,
                               achievement_rate: float, avg_gas_cases: float,
                               avg_total_cases: float, avg_total_hours: float,
                               latest_gas_cases: float, latest_total_cases: float,
                               latest_total_hours: float, rankings: Dict[str, int]) -> Dict[str, float]:
    """スコア構成要素を計算"""
    
    # 1. 全身麻酔手術件数評価 (70点満点)
    gas_score = _calculate_gas_surgery_score(
        weekly_stats['weekly_gas_cases'], target_gas_cases, achievement_rate
    )
    
    # 2. 全手術件数評価 (15点満点)
    total_cases_score = _calculate_total_cases_score(
        latest_total_cases, avg_total_cases, rankings
    )
    
    # 3. 総手術時間評価 (15点満点)
    total_hours_score = _calculate_total_hours_score(
        latest_total_hours, avg_total_hours, rankings
    )
    
    return {
        'gas_surgery_score': gas_score,
        'total_cases_score': total_cases_score,
        'total_hours_score': total_hours_score
    }


def _calculate_gas_surgery_score(weekly_gas_cases: pd.Series, target: float, 
                                achievement_rate: float) -> float:
    """全身麻酔手術件数スコア (70点満点)"""
    
    # 直近週達成度 (30点)
    if achievement_rate >= 110:
        achievement_score = 30
    elif achievement_rate >= 100:
        achievement_score = 25
    elif achievement_rate >= 90:
        achievement_score = 20
    elif achievement_rate >= 80:
        achievement_score = 15
    else:
        achievement_score = max(0, achievement_rate / 80 * 15)
    
    # 改善度 (20点)
    improvement_rate = _calculate_improvement_rate(weekly_gas_cases)
    if improvement_rate >= 15:
        improvement_score = 20
    elif improvement_rate >= 10:
        improvement_score = 15
    elif improvement_rate >= 5:
        improvement_score = 10
    elif improvement_rate >= 0:
        improvement_score = 8
    else:
        improvement_score = max(0, 8 + improvement_rate * 0.4)
    
    # 安定性 (15点) - 変動係数
    variation_coeff = weekly_gas_cases.std() / weekly_gas_cases.mean() if weekly_gas_cases.mean() > 0 else 1
    if variation_coeff <= 0.2:
        stability_score = 15
    elif variation_coeff <= 0.4:
        stability_score = 12
    elif variation_coeff <= 0.6:
        stability_score = 8
    else:
        stability_score = max(0, 15 - variation_coeff * 10)
    
    # 持続性 (5点) - トレンド
    trend_score = _calculate_trend_score(weekly_gas_cases, 5)
    
    return achievement_score + improvement_score + stability_score + trend_score


def _calculate_total_cases_score(latest: float, avg: float, rankings: Dict[str, int]) -> float:
    """全手術件数スコア (15点満点)"""
    # ランキング評価 (10点)
    rank = rankings.get('total_cases_rank', 1)
    total_depts = rankings.get('total_departments', 1)
    
    if rank == 1:
        ranking_score = 10
    elif rank <= total_depts * 0.2:  # TOP 20%
        ranking_score = 8
    elif rank <= total_depts * 0.5:  # TOP 50%
        ranking_score = 6
    else:
        ranking_score = 4
    
    # 改善度評価 (5点)
    improvement_rate = ((latest - avg) / avg * 100) if avg > 0 else 0
    if improvement_rate >= 10:
        improvement_score = 5
    elif improvement_rate >= 5:
        improvement_score = 4
    elif improvement_rate >= 0:
        improvement_score = 3
    else:
        improvement_score = max(0, 3 + improvement_rate * 0.2)
    
    return ranking_score + improvement_score


def _calculate_total_hours_score(latest: float, avg: float, rankings: Dict[str, int]) -> float:
    """総手術時間スコア (15点満点)"""
    # 全手術件数と同じロジック
    rank = rankings.get('total_hours_rank', 1)
    total_depts = rankings.get('total_departments', 1)
    
    if rank == 1:
        ranking_score = 10
    elif rank <= total_depts * 0.2:
        ranking_score = 8
    elif rank <= total_depts * 0.5:
        ranking_score = 6
    else:
        ranking_score = 4
    
    improvement_rate = ((latest - avg) / avg * 100) if avg > 0 else 0
    if improvement_rate >= 10:
        improvement_score = 5
    elif improvement_rate >= 5:
        improvement_score = 4
    elif improvement_rate >= 0:
        improvement_score = 3
    else:
        improvement_score = max(0, 3 + improvement_rate * 0.2)
    
    return ranking_score + improvement_score


def _calculate_improvement_rate(series: pd.Series) -> float:
    """改善率を計算（後半と前半の平均比較）"""
    try:
        if len(series) < 2:
            return 0
        
        # 後半と前半の平均を比較
        mid_point = len(series) // 2
        recent_avg = series.iloc[mid_point:].mean()
        early_avg = series.iloc[:mid_point].mean()
        
        if early_avg > 0:
            return (recent_avg - early_avg) / early_avg * 100
        else:
            return 0
            
    except Exception:
        return 0


def _calculate_trend_score(series: pd.Series, max_score: float) -> float:
    """トレンドスコアを計算（線形回帰の傾き）"""
    try:
        if len(series) < 3:
            return max_score / 2
        
        # 線形回帰の傾き
        x = np.arange(len(series))
        slope, _ = np.polyfit(x, series, 1)
        
        # 正の傾きを評価
        if slope > 0:
            return max_score
        elif slope >= -0.5:
            return max_score * 0.7
        else:
            return max_score * 0.3
            
    except Exception:
        return max_score / 2


def _determine_grade(total_score: float) -> str:
    """総合スコアからグレード判定"""
    if total_score >= 85:
        return 'S'
    elif total_score >= 75:
        return 'A'
    elif total_score >= 65:
        return 'B'
    elif total_score >= 50:
        return 'C'
    else:
        return 'D'


def _get_period_dates(df: pd.DataFrame, period: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """期間文字列から開始・終了日を取得"""
    try:
        if df.empty:
            return None, None
        
        latest_date = df['手術実施日_dt'].max()
        
        if period == "直近4週":
            weeks = 4
        elif period == "直近8週": 
            weeks = 8
        elif period == "直近12週":
            weeks = 12
        else:
            weeks = 12  # デフォルト
        
        # 最新日付から遡って期間を設定
        start_date = latest_date - pd.Timedelta(weeks=weeks) + pd.Timedelta(days=1)
        end_date = latest_date
        
        return start_date, end_date
        
    except Exception as e:
        logger.error(f"期間計算エラー: {e}")
        return None, None


def generate_surgery_high_score_summary(dept_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    ハイスコアサマリーを生成
    
    Returns:
        サマリー辞書（統計情報、TOP3、インサイト等）
    """
    try:
        if not dept_scores:
            return {}
        
        # TOP3抽出
        top3 = dept_scores[:3]
        
        # 統計情報
        total_depts = len(dept_scores)
        avg_score = sum(d['total_score'] for d in dept_scores) / total_depts
        high_achievers = len([d for d in dept_scores if d['achievement_rate'] >= 100])
        
        # グレード分布
        grade_counts = {}
        for grade in ['S', 'A', 'B', 'C', 'D']:
            grade_counts[grade] = len([d for d in dept_scores if d['grade'] == grade])
        
        # インサイト生成
        insights = []
        if dept_scores:
            top_dept = dept_scores[0]
            if top_dept['total_score'] >= 85:
                insights.append(f"🌟 {top_dept['display_name']}が{top_dept['total_score']:.0f}点でSグレードを達成！")
            
            if high_achievers > 0:
                insights.append(f"🎯 {high_achievers}診療科が目標達成率100%以上を記録")
            
            high_improvement = [d for d in dept_scores if d['improvement_rate'] > 15]
            if high_improvement:
                insights.append(f"📈 {len(high_improvement)}診療科で大幅な改善を確認")
        
        return {
            'top3_departments': top3,
            'total_departments': total_depts,
            'average_score': round(avg_score, 1),
            'high_achievers_count': high_achievers,
            'grade_distribution': grade_counts,
            'insights': insights,
            'evaluation_period': "診療科別週次パフォーマンス評価"
        }
        
    except Exception as e:
        logger.error(f"サマリー生成エラー: {e}")
        return {}


# === 使用例 ===
if __name__ == "__main__":
    # テスト用のダミーデータ生成（実際の使用では不要）
    import random
    from datetime import datetime, timedelta
    
    # ダミー手術データ
    dates = [datetime.now() - timedelta(days=i) for i in range(84)]  # 12週間
    depts = ['整形外科', '外科', '産婦人科', '泌尿器科', '呼吸器外科']
    
    dummy_data = []
    for date in dates:
        for _ in range(random.randint(5, 15)):  # 1日5-15件
            dept = random.choice(depts)
            entry_hour = random.randint(8, 16)
            duration = random.uniform(1, 4)
            exit_hour = entry_hour + duration
            
            dummy_data.append({
                '手術実施日_dt': date,
                '実施診療科': dept,
                '入室時刻': f"{entry_hour:02d}:{random.randint(0, 59):02d}",
                '退室時刻': f"{int(exit_hour):02d}:{random.randint(0, 59):02d}",
                '麻酔種別': '全身麻酔(20分以上：吸入もしくは静脈麻酔薬)' if random.random() > 0.3 else 'その他'
            })
    
    df_test = pd.DataFrame(dummy_data)
    
    # ダミー目標データ
    target_dict_test = {
        '整形外科': 25,
        '外科': 20,
        '産婦人科': 15,
        '泌尿器科': 18,
        '呼吸器外科': 12
    }
    
    # テスト実行
    print("=== 手術ハイスコア計算テスト ===")
    dept_scores = calculate_surgery_high_scores(df_test, target_dict_test, "直近12週")
    
    if dept_scores:
        print(f"\n📊 計算結果: {len(dept_scores)}診療科")
        print("\n🏆 TOP3:")
        for i, dept in enumerate(dept_scores[:3]):
            rank_emoji = ["🥇", "🥈", "🥉"][i]
            print(f"{rank_emoji} {dept['display_name']}: {dept['total_score']:.1f}点 ({dept['grade']}グレード)")
            print(f"   達成率: {dept['achievement_rate']:.1f}% | 改善度: {dept['improvement_rate']:+.1f}%")
        
        # サマリー生成テスト
        summary = generate_surgery_high_score_summary(dept_scores)
        if summary:
            print(f"\n📈 統計情報:")
            print(f"   平均スコア: {summary['average_score']}点")
            print(f"   目標達成: {summary['high_achievers_count']}診療科")
            print(f"   グレード分布: {summary['grade_distribution']}")
    else:
        print("❌ スコア計算に失敗しました")