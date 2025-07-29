# analysis/weekly_surgery_ranking.py
"""
週報用診療科ランキング計算エンジン (競争力強化型)
Option B: 対目標55% + 改善25% + 競争力20%
達成率計算修正版
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def calculate_weekly_surgery_ranking(df: pd.DataFrame, target_dict: Dict[str, float], 
                                   period: str = "直近12週") -> List[Dict[str, Any]]:
    """
    週報用診療科ランキングを計算 (競争力強化型)
    
    Args:
        df: 手術データ
        target_dict: 診療科別目標値（週次目標）
        period: 評価期間
    
    Returns:
        診療科別スコアのリスト（スコア順）
    """
    try:
        logger.info(f"🏆 週報ランキング計算開始: {period}")
        
        if df.empty or not target_dict:
            logger.warning("データまたは目標値が不足")
            return []
        
        # 期間設定
        start_date, end_date = _get_period_dates(df, period)
        if not start_date or not end_date:
            return []
        
        # 週次データ準備
        weekly_df = _prepare_weekly_data(df, start_date, end_date)
        if weekly_df.empty:
            return []
        
        # 各診療科のスコア計算
        dept_scores = []
        for dept_name, target_value in target_dict.items():
            dept_data = weekly_df[weekly_df['実施診療科'] == dept_name]
            
            if dept_data.empty:
                continue
            
            dept_score = _calculate_department_weekly_score(
                dept_data, dept_name, target_value, weekly_df
            )
            
            if dept_score:
                dept_scores.append(dept_score)
        
        # スコア順でソート
        dept_scores.sort(key=lambda x: x['total_score'], reverse=True)
        
        # 順位とランキングスコアを更新
        dept_scores = _update_ranking_scores(dept_scores)
        
        logger.info(f"✅ 週報ランキング計算完了: {len(dept_scores)}科")
        return dept_scores
        
    except Exception as e:
        logger.error(f"週報ランキング計算エラー: {e}")
        return []


def _calculate_department_weekly_score(dept_data: pd.DataFrame, dept_name: str, 
                                     target_value: float, all_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """診療科別週報スコアを計算"""
    try:
        # 週次統計
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
        
        # 基本統計
        latest_week = weekly_stats.index.max()
        latest_gas_cases = weekly_stats.loc[latest_week, 'weekly_gas_cases']
        four_week_avg = weekly_stats['weekly_gas_cases'].mean()
        
        # 週目標値（target_dictの値は既に週次目標）
        weekly_target = target_value if target_value > 0 else 0
        
        # === 1. 対目標パフォーマンス (55点) ===
        target_performance = _calculate_target_performance_score(
            latest_gas_cases, four_week_avg, weekly_target
        )
        
        # === 2. 改善・継続性 (25点) ===
        improvement_score = _calculate_improvement_score(weekly_stats)
        
        # === 3. 相対競争力 (20点) - 仮計算 ===
        # 実際の順位は後で全診療科計算後に更新
        competitive_score = 10.0  # 仮値
        
        # 総合スコア
        total_score = (target_performance['total'] + 
                      improvement_score['total'] + 
                      competitive_score)
        
        # グレード判定
        grade = _determine_weekly_grade(total_score)
        
        # 結果データ
        result = {
            'dept_name': dept_name,
            'display_name': dept_name,
            'total_score': total_score,
            'grade': grade,
            
            # 詳細スコア
            'target_performance': target_performance,
            'improvement_score': improvement_score,
            'competitive_score': competitive_score,
            
            # 基礎データ
            'latest_gas_cases': latest_gas_cases,
            'four_week_avg': four_week_avg,
            'weekly_target': weekly_target,
            'achievement_rate': (latest_gas_cases / weekly_target * 100) if weekly_target > 0 else 0,
            
            # 改善指標
            'previous_week': _get_previous_week_cases(weekly_stats),
            'improvement_rate': _calculate_week_over_week_improvement(weekly_stats),
            'stability_score': _calculate_stability_metric(weekly_stats),
            
            # 週次データ
            'weekly_stats': weekly_stats
        }
        
        return result
        
    except Exception as e:
        logger.error(f"診療科スコア計算エラー ({dept_name}): {e}")
        return None


def _calculate_target_performance_score(latest_cases: float, four_week_avg: float, 
                                      weekly_target: float) -> Dict[str, float]:
    """対目標パフォーマンススコア (55点満点)"""
    
    # 1.1 直近週目標達成度 (35点)
    if weekly_target > 0:
        latest_achievement_rate = (latest_cases / weekly_target) * 100
        
        # 基本点 (30点)
        if latest_achievement_rate >= 120:
            basic_score = 30.0
        elif latest_achievement_rate >= 100:
            basic_score = 25.0
        elif latest_achievement_rate >= 90:
            basic_score = 20.0
        elif latest_achievement_rate >= 80:
            basic_score = 15.0
        elif latest_achievement_rate >= 70:
            basic_score = 10.0
        else:
            basic_score = max(0, latest_achievement_rate / 70 * 10)
        
        # 達成ボーナス(5点)
        bonus_score = 5.0 if latest_achievement_rate >= 100 else 0
        recent_score = basic_score + bonus_score
    else:
        recent_score = 17.5  # デフォルト値
        latest_achievement_rate = 0
    
    # 1.2 4週平均目標達成度 (20点)
    if weekly_target > 0:
        avg_achievement_rate = (four_week_avg / weekly_target) * 100
        
        # 基本点 (15点)
        if avg_achievement_rate >= 110:
            avg_basic = 15.0
        elif avg_achievement_rate >= 100:
            avg_basic = 12.0
        elif avg_achievement_rate >= 90:
            avg_basic = 10.0
        elif avg_achievement_rate >= 80:
            avg_basic = 8.0
        else:
            avg_basic = max(0, avg_achievement_rate / 80 * 8)
        
        # 達成ボーナス (5点)
        avg_bonus = 5.0 if avg_achievement_rate >= 100 else 0
        avg_score = avg_basic + avg_bonus
    else:
        avg_score = 10.0  # デフォルト値
        avg_achievement_rate = 0
    
    total = recent_score + avg_score
    
    return {
        'recent_week': recent_score,
        'four_week_avg': avg_score,
        'total': total,
        'latest_achievement_rate': latest_achievement_rate,
        'avg_achievement_rate': avg_achievement_rate
    }


def _calculate_improvement_score(weekly_stats: pd.DataFrame) -> Dict[str, float]:
    """改善・継続性スコア (25点満点)"""
    
    # 2.1 週次改善度 (15点)
    improvement_score = 0.0
    
    if len(weekly_stats) >= 2:
        # 前週比改善 (10点)
        latest_cases = weekly_stats['weekly_gas_cases'].iloc[-1]
        previous_cases = weekly_stats['weekly_gas_cases'].iloc[-2]
        
        if previous_cases > 0:
            week_over_week = ((latest_cases - previous_cases) / previous_cases) * 100
            
            if week_over_week >= 15:
                prev_week_score = 10.0
            elif week_over_week >= 10:
                prev_week_score = 8.0
            elif week_over_week >= 5:
                prev_week_score = 6.0
            elif week_over_week >= 0:
                prev_week_score = 4.0
            elif week_over_week >= -5:
                prev_week_score = 2.0
            else:
                prev_week_score = 0.0
        else:
            prev_week_score = 5.0
        
        # 4週平均比 (5点)
        four_week_avg = weekly_stats['weekly_gas_cases'].mean()
        if four_week_avg > 0:
            avg_comparison = ((latest_cases - four_week_avg) / four_week_avg) * 100
            
            if avg_comparison >= 10:
                avg_comp_score = 5.0
            elif avg_comparison >= 5:
                avg_comp_score = 4.0
            elif avg_comparison >= 0:
                avg_comp_score = 3.0
            elif avg_comparison >= -5:
                avg_comp_score = 2.0
            else:
                avg_comp_score = 0.0
        else:
            avg_comp_score = 2.5
            
        improvement_score = prev_week_score + avg_comp_score
    else:
        improvement_score = 7.5  # デフォルト値
    
    # 2.2 安定性 (10点)
    if len(weekly_stats) >= 3:
        cv = _calculate_stability_metric(weekly_stats)
        
        if cv <= 0.1:
            stability_score = 10.0
        elif cv <= 0.2:
            stability_score = 8.0
        elif cv <= 0.3:
            stability_score = 6.0
        elif cv <= 0.4:
            stability_score = 4.0
        else:
            stability_score = 2.0
    else:
        stability_score = 5.0  # デフォルト値
    
    total = improvement_score + stability_score
    
    return {
        'weekly_improvement': improvement_score,
        'stability': stability_score,
        'total': total
    }


def _update_ranking_scores(dept_scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """順位に基づいて相対競争力スコアを更新"""
    
    total_depts = len(dept_scores)
    
    # 改善率でソート
    improvement_sorted = sorted(dept_scores, 
                              key=lambda x: x.get('improvement_rate', 0), 
                              reverse=True)
    
    for i, dept in enumerate(dept_scores):
        # 3.1 病院内順位 (12点)
        rank = i + 1
        if rank == 1:
            rank_score = 12.0
        elif rank == 2:
            rank_score = 10.0
        elif rank == 3:
            rank_score = 8.0
        elif rank <= 5:
            rank_score = 6.0
        elif rank <= total_depts * 0.3:
            rank_score = 4.0
        elif rank <= total_depts * 0.5:
            rank_score = 2.0
        else:
            rank_score = 0.0
        
        # 3.2 改善度ランキング (8点)
        improvement_rank = next((j for j, d in enumerate(improvement_sorted) 
                               if d['dept_name'] == dept['dept_name']), 0) + 1
        
        if improvement_rank == 1:
            improvement_rank_score = 8.0
        elif improvement_rank == 2:
            improvement_rank_score = 6.0
        elif improvement_rank == 3:
            improvement_rank_score = 4.0
        elif improvement_rank <= 5:
            improvement_rank_score = 2.0
        else:
            improvement_rank_score = 0.0
        
        # 相対競争力スコアを更新
        competitive_score = rank_score + improvement_rank_score
        dept['competitive_score'] = competitive_score
        dept['hospital_rank'] = rank
        dept['improvement_rank'] = improvement_rank
        
        # 総合スコアを再計算
        dept['total_score'] = (
            dept['target_performance']['total'] + 
            dept['improvement_score']['total'] + 
            competitive_score
        )
        
        # グレードを再判定
        dept['grade'] = _determine_weekly_grade(dept['total_score'])
    
    return dept_scores


def _determine_weekly_grade(total_score: float) -> str:
    """週報グレード判定"""
    if total_score >= 90:
        return 'S+'
    elif total_score >= 85:
        return 'S'
    elif total_score >= 80:
        return 'A+'
    elif total_score >= 75:
        return 'A'
    elif total_score >= 65:
        return 'B'
    elif total_score >= 50:
        return 'C'
    else:
        return 'D'


def _get_period_dates(df: pd.DataFrame, period: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """期間文字列から開始日と終了日を取得"""
    try:
        if '手術実施日_dt' not in df.columns:
            return None, None
        
        latest_date = df['手術実施日_dt'].max()
        
        if "週" in period:
            weeks = int(period.replace("直近", "").replace("週", ""))
            start_date = latest_date - pd.Timedelta(weeks=weeks) + pd.Timedelta(days=1)
        else:
            # デフォルトは12週
            start_date = latest_date - pd.Timedelta(weeks=12) + pd.Timedelta(days=1)
        
        return start_date, latest_date
        
    except Exception as e:
        logger.error(f"期間設定エラー: {e}")
        return None, None


def _prepare_weekly_data(df: pd.DataFrame, start_date: pd.Timestamp, 
                        end_date: pd.Timestamp) -> pd.DataFrame:
    """週次データを準備"""
    try:
        # 期間でフィルタリング
        period_df = df[
            (df['手術実施日_dt'] >= start_date) & 
            (df['手術実施日_dt'] <= end_date)
        ].copy()
        
        if period_df.empty:
            return pd.DataFrame()
        
        # 週の開始日を計算
        period_df['week_start'] = period_df['手術実施日_dt'].dt.to_period('W-MON').dt.start_time
        
        # 全身麻酔フラグの準備
        if 'is_gas_20min' not in period_df.columns:
            if '麻酔法' in period_df.columns:
                period_df['is_gas_20min'] = period_df['麻酔法'].str.contains(
                    '全身麻酔.*20分以上', na=False, regex=True
                )
            else:
                period_df['is_gas_20min'] = True
        
        # 手術時間の準備
        if '手術時間_時間' not in period_df.columns:
            period_df['手術時間_時間'] = 2.0  # デフォルト値
        
        return period_df
        
    except Exception as e:
        logger.error(f"週次データ準備エラー: {e}")
        return pd.DataFrame()


def _get_previous_week_cases(weekly_stats: pd.DataFrame) -> float:
    """前週症例数を取得"""
    try:
        if len(weekly_stats) >= 2:
            return weekly_stats['weekly_gas_cases'].iloc[-2]
        else:
            return 0.0
    except:
        return 0.0


def _calculate_week_over_week_improvement(weekly_stats: pd.DataFrame) -> float:
    """前週比改善率を計算"""
    try:
        if len(weekly_stats) >= 2:
            latest = weekly_stats['weekly_gas_cases'].iloc[-1]
            previous = weekly_stats['weekly_gas_cases'].iloc[-2]
            
            if previous > 0:
                return ((latest - previous) / previous) * 100
        return 0.0
    except:
        return 0.0


def _calculate_stability_metric(weekly_stats: pd.DataFrame) -> float:
    """安定性指標を計算（変動係数）"""
    try:
        if len(weekly_stats) >= 3:
            cases = weekly_stats['weekly_gas_cases']
            if cases.mean() > 0:
                return cases.std() / cases.mean()
        return 0.3  # デフォルト値
    except:
        return 0.3


def generate_weekly_ranking_summary(dept_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """週報ランキングサマリーを生成"""
    try:
        if not dept_scores:
            return {}
        
        total_depts = len(dept_scores)
        avg_score = sum(d['total_score'] for d in dept_scores) / total_depts
        high_achievers = len([d for d in dept_scores if d['achievement_rate'] >= 100])
        s_grade_count = len([d for d in dept_scores if d['grade'].startswith('S')])
        
        # TOP3とワースト3
        top3 = dept_scores[:3]
        worst3 = dept_scores[-3:] if total_depts >= 3 else []
        
        return {
            'total_departments': total_depts,
            'average_score': round(avg_score, 1),
            'high_achievers_count': high_achievers,
            's_grade_count': s_grade_count,
            'top3_departments': top3,
            'bottom3_departments': worst3,
            'evaluation_date': datetime.now().strftime('%Y年第%U週'),
            'scoring_method': 'Option B: 競争力強化型'
        }
        
    except Exception as e:
        logger.error(f"サマリー生成エラー: {e}")
        return {}


# 統合用関数
def calculate_surgery_high_scores_weekly(df: pd.DataFrame, target_dict: Dict[str, float], 
                                       period: str = "直近12週") -> List[Dict[str, Any]]:
    """
    既存ハイスコア機能との互換性を保つ統合関数
    """
    return calculate_weekly_surgery_ranking(df, target_dict, period)