# analysis/surgery_high_score.py
"""
手術ダッシュボード用ハイスコア計算エンジン
診療科別の週次パフォーマンス評価とランキング生成

評価指標:
- 週の全身麻酔手術件数 (70点): 達成度25点 + 貢献度20点 + 改善度10点 + 安定性10点 + 持続性5点
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
    """
    try:
        if df.empty:
            logger.warning("手術データが空です")
            return []
        
        logger.info(f"ハイスコア計算開始: データ{len(df)}件, 期間{period}")
        
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
        
        weekly_df = _prepare_weekly_data(period_df)
        if weekly_df.empty:
            logger.warning("週次データの準備に失敗しました")
            return []
        
        dept_scores = []
        departments = weekly_df['実施診療科'].dropna().unique()
        
        logger.info(f"対象診療科: {len(departments)}科")
        
        for dept in departments:
            dept_data = weekly_df[weekly_df['実施診療科'] == dept]
            if len(dept_data) < 3:
                logger.debug(f"診療科 {dept}: データ不足 ({len(dept_data)}件)")
                continue
            
            score_data = _calculate_department_score(
                dept_data, dept, target_dict, start_date, end_date, weekly_df
            )
            
            if score_data:
                dept_scores.append(score_data)
                logger.debug(f"診療科 {dept}: スコア {score_data['total_score']:.1f}点")
        
        dept_scores_sorted = sorted(dept_scores, key=lambda x: x['total_score'], reverse=True)
        
        logger.info(f"ハイスコア計算完了: {len(dept_scores_sorted)}診療科")
        return dept_scores_sorted
        
    except Exception as e:
        logger.error(f"ハイスコア計算エラー: {e}", exc_info=True)
        return []


def _prepare_weekly_data(df: pd.DataFrame) -> pd.DataFrame:
    """週次データを準備（月曜始まり）"""
    try:
        weekly_df = df.copy()
        weekly_df['week_start'] = weekly_df['手術実施日_dt'].dt.to_period('W-MON').dt.start_time
        
        if '手術時間_時間' not in weekly_df.columns:
            if '入室時刻' in weekly_df.columns and '退室時刻' in weekly_df.columns:
                weekly_df['手術時間_時間'] = _calculate_surgery_hours(
                    weekly_df['入室時刻'], 
                    weekly_df['退室時刻'], 
                    weekly_df['手術実施日_dt']
                )
            else:
                logger.warning("入退室時刻列が見つかりません。デフォルト値を使用します")
                weekly_df['手術時間_時間'] = 2.0
        
        if 'is_gas_20min' not in weekly_df.columns:
            if '麻酔種別' in weekly_df.columns:
                weekly_df['is_gas_20min'] = weekly_df['麻酔種別'].str.contains(
                    '全身麻酔.*20分以上', na=False, regex=True
                )
            else:
                weekly_df['is_gas_20min'] = True
        
        if 'is_weekday' not in weekly_df.columns:
            weekly_df['is_weekday'] = weekly_df['手術実施日_dt'].dt.weekday < 5
        
        return weekly_df
        
    except Exception as e:
        logger.error(f"週次データ準備エラー: {e}")
        return pd.DataFrame()


def _calculate_surgery_hours(entry_times: pd.Series, exit_times: pd.Series, 
                           surgery_dates: pd.Series) -> pd.Series:
    """入退室時刻から手術時間を計算（深夜跨ぎ対応）"""
    try:
        hours = pd.Series(0.0, index=entry_times.index)
        for idx in entry_times.index:
            try:
                entry_dt = _parse_time_to_datetime(str(entry_times[idx]).strip(), surgery_dates[idx])
                exit_dt = _parse_time_to_datetime(str(exit_times[idx]).strip(), surgery_dates[idx])
                
                if not entry_dt or not exit_dt:
                    hours[idx] = 2.0
                    continue
                
                if exit_dt < entry_dt:
                    exit_dt += timedelta(days=1)
                
                duration = (exit_dt - entry_dt).total_seconds() / 3600
                hours[idx] = duration if 0.25 <= duration <= 24 else 2.0
            except Exception:
                hours[idx] = 2.0
        return hours
    except Exception as e:
        logger.error(f"手術時間計算エラー: {e}")
        return pd.Series(2.0, index=entry_times.index)


def _parse_time_to_datetime(time_str: str, date_obj: pd.Timestamp) -> Optional[datetime]:
    """時刻文字列をdatetimeに変換"""
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            hour, minute = int(parts[0]), int(parts[1])
        elif time_str.isdigit() and len(time_str) in [3, 4]:
            hour = int(time_str[:-2])
            minute = int(time_str[-2:])
        else:
            time_float = float(time_str)
            if 0 <= time_float <= 1:
                total_seconds = time_float * 24 * 3600
                hour = int(total_seconds // 3600)
                minute = int((total_seconds % 3600) // 60)
            else:
                return None
        return datetime.combine(date_obj.date(), time(hour, minute))
    except (ValueError, TypeError):
        return None


def _calculate_department_score(dept_data: pd.DataFrame, dept_name: str, 
                               target_dict: Dict[str, float], 
                               start_date: pd.Timestamp, end_date: pd.Timestamp,
                               all_weekly_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """診療科別スコアを計算（100点満点）"""
    try:
        weekly_stats = dept_data.groupby('week_start').agg({
            'is_gas_20min': 'sum',
            '手術実施日_dt': 'count',
            '手術時間_時間': 'sum'
        }).rename(columns={
            'is_gas_20min': 'weekly_gas_cases',
            '手術実施日_dt': 'weekly_total_cases',
            '手術時間_時間': 'weekly_total_hours'
        })
        
        if weekly_stats.empty:
            return None
        
        latest_week = weekly_stats.index.max()
        latest_gas_cases = weekly_stats.loc[latest_week, 'weekly_gas_cases']
        target_gas_cases = target_dict.get(dept_name, 0)
        achievement_rate = (latest_gas_cases / target_gas_cases * 100) if target_gas_cases > 0 else 0
        
        dept_rankings = _calculate_department_rankings(all_weekly_df, dept_name)
        
        score_components = _calculate_score_components(
            weekly_stats, target_gas_cases, achievement_rate, dept_rankings, all_weekly_df
        )
        
        total_score = sum(score_components.values())
        
        # === 修正部分：詳細なスコア内訳を追加 ===
        gas_score_details = _get_gas_surgery_score_details(
            weekly_stats, achievement_rate, all_weekly_df
        )
        
        return {
            'entity_name': dept_name, 
            'display_name': dept_name,
            'total_score': round(total_score, 1),
            'grade': _determine_grade(total_score),
            'achievement_rate': round(achievement_rate, 1),
            'improvement_rate': round(_calculate_improvement_rate(weekly_stats['weekly_gas_cases']), 1),
            'score_components': {k: round(v, 1) for k, v in score_components.items()},
            # === 追加：HTMLで必要な情報 ===
            'hospital_rank': dept_rankings.get('total_cases_rank', 1),  # 病院内順位
            'target_performance': {
                'total': round(gas_score_details['achievement_score'], 1)
            },
            'improvement_score': {
                'total': round(gas_score_details['improvement_score'] + gas_score_details['stability_score'], 1),
                'stability': round(gas_score_details['stability_score'], 1)
            },
            'competitive_score': round(score_components.get('total_cases_score', 0) + score_components.get('total_hours_score', 0), 1)
        }
        
    except Exception as e:
        logger.error(f"診療科 {dept_name} のスコア計算エラー: {e}")
        return None

def _get_gas_surgery_score_details(dept_weekly_stats: pd.DataFrame, achievement_rate: float, 
                                   all_weekly_df: pd.DataFrame) -> Dict[str, float]:
    """全身麻酔手術件数スコアの詳細を取得"""
    weekly_gas_cases = dept_weekly_stats['weekly_gas_cases']
    
    # 1. 直近週達成度 (25点)
    if achievement_rate >= 100: achievement_score = 25.0
    elif achievement_rate >= 90: achievement_score = 20.0
    elif achievement_rate >= 80: achievement_score = 15.0
    elif achievement_rate >= 70: achievement_score = 10.0
    else: achievement_score = max(0, (achievement_rate / 70) * 5)

    # 2. 改善度 (10点)
    improvement_rate = _calculate_improvement_rate(weekly_gas_cases)
    if improvement_rate >= 20: improvement_score = 10.0
    elif improvement_rate >= 10: improvement_score = 8.0
    elif improvement_rate >= 5: improvement_score = 6.0
    elif improvement_rate >= 0: improvement_score = 4.0
    else: improvement_score = 0.0

    # 3. 安定性 (10点)
    variation_coeff = weekly_gas_cases.std() / weekly_gas_cases.mean() if weekly_gas_cases.mean() > 0 else 1
    if variation_coeff < 0.1: stability_score = 10.0
    elif variation_coeff < 0.2: stability_score = 8.0
    elif variation_coeff < 0.3: stability_score = 6.0
    elif variation_coeff < 0.4: stability_score = 4.0
    else: stability_score = 0.0

    # 4. 持続性 (5点)
    trend_score = _calculate_trend_score(weekly_gas_cases, 5)

    # 5. 貢献度 (20点)
    contribution_score = _calculate_contribution_score(dept_weekly_stats, all_weekly_df)
    
    return {
        'achievement_score': achievement_score,
        'improvement_score': improvement_score,
        'stability_score': stability_score,
        'trend_score': trend_score,
        'contribution_score': contribution_score
    }

def _calculate_department_rankings(all_weekly_df: pd.DataFrame, dept_name: str) -> Dict[str, int]:
    """診療科間ランキングを計算"""
    try:
        latest_week = all_weekly_df['week_start'].max()
        latest_week_data = all_weekly_df[all_weekly_df['week_start'] == latest_week]
        
        dept_stats = latest_week_data.groupby('実施診療科').agg({
            '手術実施日_dt': 'count', 
            '手術時間_時間': 'sum'
        }).rename(columns={
            '手術実施日_dt': 'total_cases', 
            '手術時間_時間': 'total_hours'
        })
        
        if dept_name not in dept_stats.index:
            total_depts = len(dept_stats)
            # 0位ではなく最下位を返す
            return {
                'total_cases_rank': total_depts, 
                'total_hours_rank': total_depts, 
                'total_departments': total_depts
            }

        total_cases_rank = (dept_stats['total_cases'] > dept_stats.loc[dept_name, 'total_cases']).sum() + 1
        total_hours_rank = (dept_stats['total_hours'] > dept_stats.loc[dept_name, 'total_hours']).sum() + 1
        
        return {
            'total_cases_rank': int(total_cases_rank),  # intに変換
            'total_hours_rank': int(total_hours_rank),  # intに変換
            'total_departments': len(dept_stats)
        }
    except Exception as e:
        logger.error(f"ランキング計算エラー ({dept_name}): {e}", exc_info=True)
        # エラー時も1位（0位ではない）を返す
        return {
            'total_cases_rank': 1, 
            'total_hours_rank': 1, 
            'total_departments': 1
        }

def _calculate_score_components(weekly_stats: pd.DataFrame, target_gas_cases: float,
                               achievement_rate: float, rankings: Dict[str, int],
                               all_weekly_df: pd.DataFrame) -> Dict[str, float]:
    """スコア構成要素を計算"""
    gas_score = _calculate_gas_surgery_score(
        weekly_stats, achievement_rate, all_weekly_df
    )
    
    latest_total_cases = weekly_stats['weekly_total_cases'].iloc[-1]
    avg_total_cases = weekly_stats['weekly_total_cases'].mean()
    total_cases_score = _calculate_total_cases_score(latest_total_cases, avg_total_cases, rankings)
    
    latest_total_hours = weekly_stats['weekly_total_hours'].iloc[-1]
    avg_total_hours = weekly_stats['weekly_total_hours'].mean()
    total_hours_score = _calculate_total_hours_score(latest_total_hours, avg_total_hours, rankings)
    
    return {
        'gas_surgery_score': gas_score,
        'total_cases_score': total_cases_score,
        'total_hours_score': total_hours_score
    }


def _calculate_gas_surgery_score(dept_weekly_stats: pd.DataFrame, achievement_rate: float, 
                                all_weekly_df: pd.DataFrame) -> float:
    """全身麻酔手術件数スコア (70点満点)"""
    weekly_gas_cases = dept_weekly_stats['weekly_gas_cases']
    
    # 1. 直近週達成度 (25点)
    if achievement_rate >= 100: score = 25.0
    elif achievement_rate >= 90: score = 20.0
    elif achievement_rate >= 80: score = 15.0
    elif achievement_rate >= 70: score = 10.0
    else: score = max(0, (achievement_rate / 70) * 5)
    achievement_score = score

    # 2. 改善度 (10点)
    improvement_rate = _calculate_improvement_rate(weekly_gas_cases)
    if improvement_rate >= 20: score = 10.0
    elif improvement_rate >= 10: score = 8.0
    elif improvement_rate >= 5: score = 6.0
    elif improvement_rate >= 0: score = 4.0
    else: score = 0.0
    improvement_score = score

    # 3. 安定性 (10点)
    variation_coeff = weekly_gas_cases.std() / weekly_gas_cases.mean() if weekly_gas_cases.mean() > 0 else 1
    if variation_coeff < 0.1: score = 10.0
    elif variation_coeff < 0.2: score = 8.0
    elif variation_coeff < 0.3: score = 6.0
    elif variation_coeff < 0.4: score = 4.0
    else: score = 0.0
    stability_score = score

    # 4. 持続性 (5点)
    trend_score = _calculate_trend_score(weekly_gas_cases, 5)

    # 5. 貢献度 (20点)
    contribution_score = _calculate_contribution_score(dept_weekly_stats, all_weekly_df)
    
    return achievement_score + improvement_score + stability_score + trend_score + contribution_score


def _calculate_contribution_score(dept_weekly_stats: pd.DataFrame, all_weekly_df: pd.DataFrame) -> float:
    """貢献度スコア (20点満点)"""
    try:
        dept_total_gas = dept_weekly_stats['weekly_gas_cases'].sum()
        hospital_total_gas = all_weekly_df[all_weekly_df['is_gas_20min'] == True]['is_gas_20min'].sum()
        
        if hospital_total_gas == 0:
            return 0.0
            
        contribution_pct = (dept_total_gas / hospital_total_gas) * 100
        
        if contribution_pct >= 30: return 20.0
        elif contribution_pct >= 20: return 15.0
        elif contribution_pct >= 15: return 10.0
        elif contribution_pct >= 10: return 5.0
        else: return 0.0
            
    except Exception as e:
        logger.error(f"貢献度スコア計算エラー: {e}")
        return 0.0


def _calculate_total_cases_score(latest: float, avg: float, rankings: Dict[str, int]) -> float:
    """全手術件数スコア (15点満点)"""
    rank, total_depts = rankings.get('total_cases_rank', 1), rankings.get('total_departments', 1)
    if rank == 1: score = 10
    elif rank <= total_depts * 0.2: score = 8
    elif rank <= total_depts * 0.5: score = 6
    else: score = 4
    ranking_score = score
    
    improvement_rate = ((latest - avg) / avg * 100) if avg > 0 else 0
    if improvement_rate >= 10: score = 5
    elif improvement_rate >= 5: score = 4
    elif improvement_rate >= 0: score = 3
    else: score = max(0, 3 + improvement_rate * 0.2)
    improvement_score = score
    
    return ranking_score + improvement_score


def _calculate_total_hours_score(latest: float, avg: float, rankings: Dict[str, int]) -> float:
    """総手術時間スコア (15点満点)"""
    rank, total_depts = rankings.get('total_hours_rank', 1), rankings.get('total_departments', 1)
    if rank == 1: score = 10
    elif rank <= total_depts * 0.2: score = 8
    elif rank <= total_depts * 0.5: score = 6
    else: score = 4
    ranking_score = score
    
    improvement_rate = ((latest - avg) / avg * 100) if avg > 0 else 0
    if improvement_rate >= 10: score = 5
    elif improvement_rate >= 5: score = 4
    elif improvement_rate >= 0: score = 3
    else: score = max(0, 3 + improvement_rate * 0.2)
    improvement_score = score
    
    return ranking_score + improvement_score


def _calculate_improvement_rate(series: pd.Series) -> float:
    """改善率を計算（後半と前半の平均比較）"""
    try:
        if len(series) < 2: return 0
        mid_point = len(series) // 2
        recent_avg, early_avg = series.iloc[mid_point:].mean(), series.iloc[:mid_point].mean()
        return (recent_avg - early_avg) / early_avg * 100 if early_avg > 0 else 0
    except Exception: return 0


def _calculate_trend_score(series: pd.Series, max_score: float) -> float:
    """トレンドスコアを計算（線形回帰の傾き）"""
    try:
        if len(series) < 3: return max_score / 2
        slope, _ = np.polyfit(np.arange(len(series)), series, 1)
        if slope > 0: return max_score
        elif slope >= -0.5: return max_score * 0.7
        else: return max_score * 0.3
    except Exception: return max_score / 2


def _determine_grade(total_score: float) -> str:
    """総合スコアからグレード判定"""
    if total_score >= 85: return 'S'
    elif total_score >= 75: return 'A'
    elif total_score >= 65: return 'B'
    elif total_score >= 50: return 'C'
    else: return 'D'


def _get_period_dates(df: pd.DataFrame, period: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """期間文字列から開始・終了日を取得"""
    try:
        if df.empty: return None, None
        latest_date = df['手術実施日_dt'].max()
        weeks = {'直近4週': 4, '直近8週': 8, '直近12週': 12}.get(period, 12)
        start_date = latest_date - pd.Timedelta(weeks=weeks) + pd.Timedelta(days=1)
        return start_date, latest_date
    except Exception as e:
        logger.error(f"期間計算エラー: {e}")
        return None, None


def generate_surgery_high_score_summary(dept_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ハイスコアサマリーを生成"""
    if not dept_scores: return {}
    total_depts = len(dept_scores)
    avg_score = sum(d['total_score'] for d in dept_scores) / total_depts
    high_achievers = len([d for d in dept_scores if d.get('achievement_rate', 0) >= 100])
    grade_counts = {grade: len([d for d in dept_scores if d['grade'] == grade]) for grade in ['S', 'A', 'B', 'C', 'D']}
    return {
        'top3_departments': dept_scores[:3], 'total_departments': total_depts,
        'average_score': round(avg_score, 1), 'high_achievers_count': high_achievers,
        'grade_distribution': grade_counts, 'evaluation_period': "診療科別週次パフォーマンス評価"
    }
