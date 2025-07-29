# reporting/surgery_high_score_html.py (統一版 - 週報ランキング方式 + 病院全体サマリ追加)
"""
手術評価レポートHTML出力 - 週報ランキング方式（100点満点）に統一 + 病院全体サマリ追加
"""

import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_unified_surgery_report_html(df: pd.DataFrame, target_dict: Dict[str, float], 
                                        period: str = "直近12週", 
                                        report_type: str = "weekly_ranking") -> str:
    """
    統合された手術レポートHTML生成（週報ランキング方式に統一）
    
    Args:
        df: 手術データ
        target_dict: 目標値辞書
        period: 評価期間
        report_type: "weekly_ranking" または "high_score"（互換性のため残す）
    """
    try:
        logger.info(f"🎨 統合レポート生成開始: {report_type}, {period}")
        
        # 常に週報ランキング方式を使用（統一のため）
        return generate_weekly_ranking_html(df, target_dict, period)
        
    except Exception as e:
        logger.error(f"統合レポート生成エラー: {e}")
        return _generate_error_html(str(e))


# === 🆕 病院全体サマリHTML生成機能 ===

def generate_hospital_surgery_summary_html(df: pd.DataFrame, latest_date: pd.Timestamp) -> str:
    """
    病院全体手術サマリHTML生成（年度比較機能付き）
    
    Args:
        df: 手術データ
        latest_date: 最新日付
        
    Returns:
        str: 病院全体サマリHTML
    """
    try:
        # 拡張KPIデータを取得（年度比較含む）
        from analysis.ranking import get_enhanced_kpi_summary
        enhanced_kpi = get_enhanced_kpi_summary(df, latest_date)
        
        yearly_data = enhanced_kpi.get('yearly_comparison', {})
        monthly_trend = enhanced_kpi.get('monthly_trend', [])
        basic_kpi = {k: v for k, v in enhanced_kpi.items() if k not in ['yearly_comparison', 'monthly_trend', 'enhanced']}
        
        return f"""
        <div id="surgery-summary" class="view-content active">
            {generate_yearly_comparison_card_html(yearly_data)}
            {generate_current_performance_cards_html(basic_kpi)}
            {generate_monthly_trend_chart_html(monthly_trend)}
            {generate_analysis_insights_html(yearly_data, basic_kpi)}
        </div>
        """
        
    except Exception as e:
        logger.error(f"病院サマリHTML生成エラー: {e}")
        return f'<div class="error">病院サマリ生成でエラーが発生しました: {e}</div>'


def generate_yearly_comparison_card_html(yearly_data: Dict[str, Any]) -> str:
    """年度比較カードHTML生成"""
    if not yearly_data or yearly_data.get('current_fiscal_total', 0) == 0:
        return '<div class="yearly-comparison-card-placeholder">年度比較データを準備中...</div>'
    
    # 増減に応じた色とアイコン
    growth_rate = yearly_data.get('growth_rate', 0)
    difference = yearly_data.get('difference', 0)
    
    if growth_rate > 5:
        trend_color = "#4CAF50"
        trend_icon = "📈"
        trend_text = "順調な増加"
        trend_status = "🎯 目標達成ペース"
    elif growth_rate > 0:
        trend_color = "#FF9800" 
        trend_icon = "➡️"
        trend_text = "微増"
        trend_status = "📊 推移を注視"
    else:
        trend_color = "#F44336"
        trend_icon = "📉"
        trend_text = "要改善"
        trend_status = "⚠️ 対策が必要"
    
    return f"""
    <div class="yearly-comparison-card">
        <div class="yearly-card-header">
            <div class="yearly-card-icon">📊</div>
            <div>
                <div class="yearly-card-title">全身麻酔手術件数 年度比較</div>
                <div class="yearly-card-subtitle">病院目標：全身麻酔手術件数増加</div>
            </div>
        </div>
        
        <div class="yearly-comparison-grid">
            <div class="yearly-metric">
                <div class="yearly-metric-label">今年度累計</div>
                <div class="yearly-metric-value">{yearly_data['current_fiscal_total']:,}</div>
                <div class="yearly-metric-period">{yearly_data['comparison_period']}</div>
            </div>
            
            <div class="yearly-metric">
                <div class="yearly-metric-label">昨年度同期</div>
                <div class="yearly-metric-value">{yearly_data['prev_fiscal_total']:,}</div>
                <div class="yearly-metric-period">前年同期間</div>
            </div>
            
            <div class="yearly-metric">
                <div class="yearly-metric-label">今年度予測</div>
                <div class="yearly-metric-value">{yearly_data['projected_annual']:,}</div>
                <div class="yearly-metric-period">年度末予測値</div>
            </div>
        </div>
        
        <div class="yearly-comparison-result">
            <div class="yearly-change-value" style="color: {trend_color};">
                {difference:+,}件 ({growth_rate:+.1f}%)
            </div>
            <div class="yearly-change-label">
                {trend_icon} 前年度同期比で{trend_text} {trend_status}
            </div>
        </div>
    </div>
    """


def generate_current_performance_cards_html(kpi_data: Dict[str, Any]) -> str:
    """現在の4週間パフォーマンスカードHTML生成"""
    if not kpi_data:
        return '<div class="performance-cards-placeholder">パフォーマンスデータを読み込み中...</div>'
    
    # KPIデータから値を取得
    gas_cases = kpi_data.get("全身麻酔手術件数 (直近4週)", 0)
    total_cases = kpi_data.get("全手術件数 (直近4週)", 0)
    daily_avg = kpi_data.get("平日1日あたり全身麻酔手術件数", "0.0").replace("件", "")
    utilization = kpi_data.get("手術室稼働率 (全手術、平日のみ)", "0.0%").replace("%", "")
    
    try:
        daily_avg_float = float(daily_avg)
        utilization_float = float(utilization)
    except ValueError:
        daily_avg_float = 0.0
        utilization_float = 0.0
    
    # 目標値との比較（config/hospital_targets.pyの値を使用）
    try:
        from config.hospital_targets import HospitalTargets
        daily_target = HospitalTargets.get_daily_target('weekday_gas_surgeries')
        daily_achievement = (daily_avg_float / daily_target * 100) if daily_target > 0 else 0
    except ImportError:
        daily_target = 21.0  # フォールバック値
        daily_achievement = (daily_avg_float / daily_target * 100) if daily_target > 0 else 0
    
    # 稼働率の評価
    if utilization_float >= 85:
        util_status = "excellent"
        util_icon = "🟢"
    elif utilization_float >= 80:
        util_status = "good" 
        util_icon = "🟡"
    else:
        util_status = "needs_improvement"
        util_icon = "🔴"
    
    return f"""
    <div class="hospital-summary">
        <h2>🏥 直近4週間パフォーマンス</h2>
        <p style="color: #666; margin-bottom: 20px;">評価期間: 直近4週間 | 全診療科・全手術室統合データ</p>
        
        <div class="summary-grid">
            <div class="summary-metric primary">
                <div class="metric-icon">🔴</div>
                <div class="metric-value">{gas_cases:,}</div>
                <div class="metric-label">全身麻酔手術件数</div>
                <div class="metric-subtitle">直近4週間合計</div>
            </div>
            
            <div class="summary-metric secondary">
                <div class="metric-icon">⚕️</div>
                <div class="metric-value">{total_cases:,}</div>
                <div class="metric-label">全手術件数</div>
                <div class="metric-subtitle">全身麻酔以外も含む</div>
            </div>
            
            <div class="summary-metric accent">
                <div class="metric-icon">📊</div>
                <div class="metric-value">{daily_avg}</div>
                <div class="metric-label">平日1日あたり全身麻酔</div>
                <div class="metric-subtitle">件/平日 (目標: {daily_target:.1f}件)</div>
                <div class="metric-achievement">達成率: {daily_achievement:.1f}%</div>
            </div>
            
            <div class="summary-metric {util_status}">
                <div class="metric-icon">🏭</div>
                <div class="metric-value">{utilization}%</div>
                <div class="metric-label">手術室稼働率</div>
                <div class="metric-subtitle">平日のみ、11室対象</div>
                <div class="metric-status">{util_icon} {'優秀' if util_status == 'excellent' else '良好' if util_status == 'good' else '改善余地あり'}</div>
            </div>
        </div>
    </div>
    """


def generate_monthly_trend_chart_html(monthly_trend: List[Dict[str, Any]]) -> str:
    """月別トレンドチャートHTML生成"""
    if not monthly_trend or len(monthly_trend) == 0:
        return '<div class="trend-chart-placeholder">月別トレンドデータを準備中...</div>'
    
    # 最大値を取得してバーの高さを正規化
    max_count = max(trend['count'] for trend in monthly_trend if trend['count'] > 0)
    if max_count == 0:
        return '<div class="trend-chart-placeholder">トレンドデータが不足しています</div>'
    
    # バーHTML生成
    bars_html = ""
    for trend in monthly_trend[:8]:  # 最新8ヶ月分を表示
        count = trend['count']
        height_percent = (count / max_count * 100) if max_count > 0 else 0
        
        bars_html += f"""
        <div class="trend-bar" style="height: {height_percent}%;">
            <div class="trend-bar-value">{count}</div>
            <div class="trend-bar-label">{trend['month']}</div>
        </div>
        """
    
    return f"""
    <div class="trend-chart">
        <h3>📈 月別推移（全身麻酔手術件数）</h3>
        <div class="trend-bars">
            {bars_html}
        </div>
        <p style="text-align: center; color: #666; font-size: 12px;">
            青：今年度実績 | 目標ペース：月平均460件
        </p>
    </div>
    """


def generate_analysis_insights_html(yearly_data: Dict[str, Any], kpi_data: Dict[str, Any]) -> str:
    """分析インサイトHTML生成"""
    growth_rate = yearly_data.get('growth_rate', 0)
    utilization = float(kpi_data.get("手術室稼働率 (全手術、平日のみ)", "0").replace("%", ""))
    
    return f"""
    <div class="analysis-section">
        <h2>📈 年度目標達成分析</h2>
        
        <div class="analysis-grid">
            <div class="analysis-card {'improvement' if growth_rate > 0 else 'concern'}">
                <h3 style="color: {'#4CAF50' if growth_rate > 0 else '#FF9800'}; margin-top: 0;">
                    {'✅ 年度目標達成状況' if growth_rate > 0 else '⚠️ 注意ポイント'}
                </h3>
                <ul style="margin: 0; padding-left: 20px;">
                    {'<li>前年度同期比+' + f'{growth_rate:.1f}%の順調な増加</li>' if growth_rate > 0 else '<li>前年度同期比' + f'{growth_rate:.1f}%で要改善</li>'}
                    <li>手術室稼働率{utilization:.1f}%は{'適正水準' if utilization >= 80 else '改善余地'}</li>
                    <li>年度末予測{yearly_data.get('projected_annual', 0):,}件{'は過去最高' if growth_rate > 10 else 'の実現を目指す'}</li>
                    <li>{'継続的な成長基調' if growth_rate > 5 else '更なる取り組み強化が必要'}</li>
                </ul>
            </div>
            
            <div class="analysis-card action">
                <h3 style="color: #2196F3; margin-top: 0;">🎯 目標達成施策</h3>
                <ul style="margin: 0; padding-left: 20px;">
                    <li>手術室稼働率を{max(85, utilization + 5):.0f}%以上に向上</li>
                    <li>診療科間の手術枠最適化</li>
                    <li>緊急手術体制の強化検討</li>
                    <li>年度末目標：{int(yearly_data.get('projected_annual', 0) * 1.03):,}件を目指す</li>
                </ul>
            </div>
        </div>
    </div>
    """


# === 既存の週報ランキング機能（変更なし） ===

def generate_weekly_ranking_html(df: pd.DataFrame, target_dict: Dict[str, float], 
                               period: str = "直近12週") -> str:
    """週報ランキングのHTML生成（100点満点方式）"""
    try:
        from analysis.weekly_surgery_ranking import (
            calculate_weekly_surgery_ranking, 
            generate_weekly_ranking_summary
        )
        
        # 週報ランキング計算（100点満点）
        dept_scores = calculate_weekly_surgery_ranking(df, target_dict, period)
        
        if not dept_scores:
            return _generate_empty_weekly_ranking_html()
        
        summary = generate_weekly_ranking_summary(dept_scores)
        
        # HTML生成
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>🏆 診療科別手術ハイスコア TOP3</title>
            <style>{_get_weekly_ranking_css()}</style>
        </head>
        <body>
            <div class="container">
                {_generate_weekly_header_html(period, summary)}
                {_generate_weekly_highlights_html(summary)}
                {_generate_weekly_ranking_top3_html(dept_scores[:3])}
                {_generate_footer_html("weekly_ranking")}
            </div>
        </body>
        </html>
        """
        
        logger.info(f"✅ 週報ランキングHTML生成完了: {len(dept_scores)}科")
        return html_content
        
    except Exception as e:
        logger.error(f"週報ランキングHTML生成エラー: {e}")
        return _generate_error_html(str(e))


def generate_surgery_high_score_html(df: pd.DataFrame, target_dict: Dict[str, float], 
                                   period: str = "直近12週") -> str:
    """
    従来のハイスコアHTML生成（互換性維持）
    実際は週報ランキング方式を使用
    """
    return generate_weekly_ranking_html(df, target_dict, period)


def _generate_weekly_header_html(period: str, summary: Dict[str, Any]) -> str:
    """週報ヘッダーHTML生成"""
    current_date = datetime.now().strftime('%Y/%m/%d')
    
    return f"""
    <header class="header">
        <h1>🏆 診療科別手術ハイスコア TOP3</h1>
        <div class="header-meta">
            <span class="period">評価期間: {period}</span>
        </div>
    </header>
    """


def _generate_weekly_highlights_html(summary: Dict[str, Any]) -> str:
    """統計ハイライトHTML生成"""
    return f"""
    <div class="stats-highlight">
        <h2>🥇 診療科ランキング</h2>
    </div>
    """

def _generate_weekly_ranking_top3_html(top3: List[Dict[str, Any]]) -> str:
    """TOP3ランキングHTML生成"""
    if not top3:
        return ""
    
    ranking_html = ""
    
    for i, dept in enumerate(top3):
        rank_emoji = ["🥇", "🥈", "🥉"][i]
        achievement_pct = dept.get('achievement_rate', 0)
        
        ranking_html += f"""
        <div class="ranking-card rank-{i+1}">
            <div class="rank-header">
                <span class="medal">{rank_emoji}</span>
                <span class="rank-label">診療科{i+1}位</span>
            </div>
            <div class="dept-name">{dept['display_name']}</div>
            <div class="score-info">
                <div class="achievement">達成率 {achievement_pct:.1f}%</div>
            </div>
            <div class="score-value">{dept['total_score']:.0f}点</div>
        </div>
        """
    
    # 1位の診療科データを動的に反映
    top_dept = top3[0]
    # score_breakdownの取得を修正（weekly_surgery_rankingの構造に合わせる）
    target_perf = top_dept.get('target_performance', {})
    improvement_score_details = top_dept.get('improvement_score', {})
    
    score_details_html = f"""
    <div class="scoring-info">
        <div class="score-icon">👑</div>
        <div class="score-label">診療科1位：{top_dept['display_name']}</div>
        <div class="score-detail">総合スコア：{top_dept['total_score']:.0f}点</div>
    </div>
    
    <div class="score-breakdown">
        <h3>📊 総合スコア：{top_dept['total_score']:.0f}点</h3>
        <table class="score-table">
            <tr>
                <td>対目標パフォーマンス</td>
                <td>{target_perf.get('total', 0):.0f}点</td>
                <td>（達成率{top_dept.get('achievement_rate', 0):.1f}%）</td>
            </tr>
            <tr>
                <td>改善・継続性</td>
                <td>{improvement_score_details.get('total', 0):.0f}点</td>
                <td>（安定性 {improvement_score_details.get('stability', 0):.0f}点）</td>
            </tr>
            <tr>
                <td>相対競争力</td>
                <td>{top_dept.get('competitive_score', 0):.0f}点</td>
                <td>（病院内 {top_dept.get('hospital_rank', 0)}位）</td>
            </tr>
            <tr>
                <td>改善度</td>
                <td>{top_dept.get('improvement_rate', 0):+.1f}%</td>
                <td></td>
            </tr>
        </table>
    </div>
    """

    return f"""
    <div class="ranking-section">
        {ranking_html}
    </div>
    {score_details_html}
    """


def _get_weekly_ranking_css() -> str:
    """週報ランキング用CSS（年度比較カード対応版）"""
    return """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        margin: 0;
        padding: 0;
        background: #f5f5f5;
        color: #333;
    }
    
    .container {
        max-width: 900px;
        margin: 0 auto;
        padding: 20px;
        background: white;
    }
    
    .header {
        text-align: center;
        padding: 20px 0;
        border-bottom: 3px solid #2c3e50;
        margin-bottom: 30px;
    }
    
    .header h1 {
        font-size: 2em;
        margin: 0 0 10px 0;
        color: #2c3e50;
    }
    
    .header-meta {
        color: #666;
        font-size: 0.9em;
    }
    
    /* 年度比較カード専用スタイル */
    .yearly-comparison-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px;
        padding: 30px;
        margin-bottom: 30px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
        position: relative;
        overflow: hidden;
    }
    
    .yearly-comparison-card::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 100%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        pointer-events: none;
    }
    
    .yearly-card-header {
        display: flex;
        align-items: center;
        margin-bottom: 25px;
        position: relative;
        z-index: 1;
    }
    
    .yearly-card-icon {
        font-size: 32px;
        margin-right: 15px;
    }
    
    .yearly-card-title {
        font-size: 20px;
        font-weight: bold;
    }
    
    .yearly-card-subtitle {
        font-size: 14px;
        opacity: 0.9;
        margin-top: 5px;
    }
    
    .yearly-comparison-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 20px;
        margin-bottom: 25px;
        position: relative;
        z-index: 1;
    }
    
    .yearly-metric {
        text-align: center;
        padding: 20px;
        background: rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    
    .yearly-metric-label {
        font-size: 12px;
        opacity: 0.9;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .yearly-metric-value {
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    
    .yearly-metric-period {
        font-size: 11px;
        opacity: 0.8;
    }
    
    .yearly-comparison-result {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        position: relative;
        z-index: 1;
    }
    
    .yearly-change-value {
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    
    .yearly-change-label {
        font-size: 14px;
        opacity: 0.9;
    }
    
    /* 病院サマリスタイル */
    .hospital-summary {
        background: white;
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
    }
    
    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin-top: 20px;
    }
    
    .summary-metric {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 25px;
        border-radius: 12px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    
    .summary-metric.primary {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
    }
    
    .summary-metric.secondary {
        background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
    }
    
    .summary-metric.accent {
        background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
    }
    
    .summary-metric.needs_improvement {
        background: linear-gradient(135deg, #FF5722 0%, #D84315 100%);
    }
    
    .summary-metric.good {
        background: linear-gradient(135deg, #8BC34A 0%, #689F38 100%);
    }
    
    .summary-metric.excellent {
        background: linear-gradient(135deg, #4CAF50 0%, #388E3C 100%);
    }
    
    .metric-icon {
        font-size: 32px;
        margin-bottom: 10px;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
    }
    
    .metric-subtitle {
        font-size: 12px;
        opacity: 0.8;
        margin-top: 5px;
    }
    
    .metric-achievement {
        font-size: 11px;
        opacity: 0.9;
        margin-top: 3px;
        font-weight: bold;
    }
    
    .metric-status {
        font-size: 12px;
        margin-top: 5px;
        font-weight: bold;
    }
    
    /* 月別トレンドチャート */
    .trend-chart {
        background: white;
        border-radius: 8px;
        padding: 20px;
        margin: 20px 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    .trend-bars {
        display: flex;
        align-items: end;
        gap: 8px;
        height: 120px;
        margin: 20px 0;
    }
    
    .trend-bar {
        flex: 1;
        background: linear-gradient(to top, #667eea, #764ba2);
        border-radius: 3px 3px 0 0;
        position: relative;
        min-height: 20px;
    }
    
    .trend-bar-label {
        position: absolute;
        bottom: -25px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 10px;
        color: #666;
        white-space: nowrap;
    }
    
    .trend-bar-value {
        position: absolute;
        top: -20px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 10px;
        font-weight: bold;
        color: #333;
    }
    
    /* 分析セクション */
    .analysis-section {
        background: white;
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
    }
    
    .analysis-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
        margin-top: 20px;
    }
    
    .analysis-card {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        border-radius: 8px;
        padding: 20px;
    }
    
    .analysis-card.improvement {
        border-left-color: #4CAF50;
        background: #e8f5e8;
    }
    
    .analysis-card.concern {
        border-left-color: #FF9800;
        background: #fff3cd;
    }
    
    .analysis-card.action {
        border-left-color: #2196F3;
        background: #e3f2fd;
    }
    
    /* 既存のランキングスタイル */
    .stats-highlight {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 30px;
        text-align: center;
    }
    
    .stats-highlight h2 {
        margin: 0;
        color: #2c3e50;
    }
    
    .ranking-section {
        margin-bottom: 40px;
    }
    
    .ranking-card {
        background: #fff;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .ranking-card.rank-1 {
        border-color: #ffd700;
        background: linear-gradient(135deg, #fffef5 0%, #fffdf0 100%);
    }
    
    .ranking-card.rank-2 {
        border-color: #c0c0c0;
        background: linear-gradient(135deg, #fafafa 0%, #f8f8f8 100%);
    }
    
    .ranking-card.rank-3 {
        border-color: #cd7f32;
        background: linear-gradient(135deg, #fffaf5 0%, #fff8f0 100%);
    }
    
    .rank-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }
    
    .medal {
        font-size: 2em;
    }
    
    .rank-label {
        font-weight: bold;
        color: #666;
    }
    
    .dept-name {
        font-size: 1.5em;
        font-weight: bold;
        margin-bottom: 10px;
        color: #2c3e50;
    }
    
    .score-info {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 10px;
    }
    
    .achievement {
        color: #666;
        font-size: 1.1em;
    }
    
    .score-value {
        font-size: 2em;
        font-weight: bold;
        color: #e74c3c;
        text-align: right;
    }
    
    .scoring-info {
        background: #f8f9fa;
        padding: 15px;
        margin: 20px 0;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
    .score-icon {
        font-size: 2em;
    }
    
    .score-label {
        font-size: 1.2em;
        font-weight: bold;
        color: #2c3e50;
    }
    
    .score-detail {
        margin-left: auto;
        font-size: 1.1em;
        color: #e74c3c;
    }
    
    .score-breakdown {
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 30px;
    }
    
    .score-breakdown h3 {
        margin: 0 0 15px 0;
        color: #2c3e50;
    }
    
    .score-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .score-table td {
        padding: 8px;
        border-bottom: 1px solid #eee;
    }
    
    .score-table td:first-child {
        font-weight: 500;
        color: #666;
    }
    
    .score-table td:nth-child(2) {
        text-align: right;
        font-weight: bold;
        color: #2c3e50;
    }
    
    .score-table td:nth-child(3) {
        text-align: right;
        color: #666;
        font-size: 0.9em;
    }
    
    .footer {
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e0e0e0;
        text-align: center;
        color: #666;
        font-size: 0.9em;
    }
    
    /* レスポンシブ対応 */
    @media (max-width: 768px) {
        .yearly-comparison-grid {
            grid-template-columns: 1fr;
        }
        
        .summary-grid {
            grid-template-columns: 1fr;
        }
        
        .analysis-grid {
            grid-template-columns: 1fr;
        }
        
        .container {
            padding: 10px;
        }
    }
    """


def _generate_footer_html(report_type: str) -> str:
    """フッターHTML生成"""
    return f"""
    <div class="footer">
        <p>評価期間: 直近12週 (07/27まで)</p>
    </div>
    """


def _generate_empty_weekly_ranking_html() -> str:
    """空の週報ランキングHTML"""
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>週報ランキング - データなし</title>
        <style>{_get_weekly_ranking_css()}</style>
    </head>
    <body>
        <div class="container">
            <h1>📊 週報ランキング</h1>
            <div class="empty-message">
                <p>評価対象のデータがありません。</p>
                <p>データと目標設定を確認してください。</p>
            </div>
        </div>
    </body>
    </html>
    """


def _generate_error_html(error_message: str) -> str:
    """エラーHTML生成"""
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>エラー</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }}
            .error-container {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: 0 auto;
            }}
            .error-title {{
                color: #e74c3c;
                margin-bottom: 20px;
            }}
            .error-message {{
                color: #666;
                font-size: 1.1em;
                margin-bottom: 20px;
            }}
            .error-details {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.9em;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="error-container">
            <h1 class="error-title">❌ レポート生成エラー</h1>
            <div class="error-message">
                レポートの生成中にエラーが発生しました。
            </div>
            <div class="error-details">
                エラー詳細: {error_message}
            </div>
            <p>データと設定を確認してから再度お試しください。</p>
        </div>
    </body>
    </html>
    """