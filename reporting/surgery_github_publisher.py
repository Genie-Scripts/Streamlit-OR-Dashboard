# reporting/surgery_github_publisher.py (評価ロジック参照先・説明パネル・GA対応修正版)

import pandas as pd
import logging
import streamlit as st
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import base64
import requests
import json
import os

from ui.session_manager import SessionManager

logger = logging.getLogger(__name__)


class SurgeryGitHubPublisher:
    """手術分析ダッシュボード GitHub公開クラス（4タブ統合ダッシュボード版）"""
    
    def __init__(self, github_token: str, repo_owner: str, repo_name: str, branch: str = "main"):
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.base_url = "https://api.github.com"

    # ▼▼▼【修正箇所】google_analytics_id を引数に追加 ▼▼▼
    def generate_dashboard_html_content(self, df: pd.DataFrame, target_dict: Dict[str, float], 
                                        period: str, analysis_base_date: pd.Timestamp,
                                        google_analytics_id: Optional[str] = None) -> Optional[str]:
        """ダッシュボードのHTMLコンテンツを生成する"""
        try:
            logger.info("HTMLコンテンツの生成を開始")
            self.df = df
            # ▼▼▼【修正箇所】google_analytics_id を渡す ▼▼▼
            html_content = self._generate_integrated_html_content(df, target_dict, period, analysis_base_date, google_analytics_id)
            if html_content:
                logger.info("HTMLコンテンツの生成が完了")
            else:
                logger.warning("HTMLコンテンツの生成に失敗")
            return html_content
        except Exception as e:
            logger.error(f"HTMLコンテンツの生成エラー: {e}", exc_info=True)
            return None

    def save_html_locally(self, html_content: str, folder: str = "docs") -> Tuple[bool, str]:
        """HTMLコンテンツをローカルファイルに保存する"""
        try:
            if not os.path.exists(folder):
                os.makedirs(folder)
                logger.info(f"フォルダを作成しました: {folder}")

            filepath = os.path.join(folder, "index.html")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)

            absolute_path = os.path.abspath(filepath)
            logger.info(f"HTMLをローカルに保存しました: {absolute_path}")
            return True, f"docs/index.html に保存しました"
        except Exception as e:
            logger.error(f"HTMLのローカル保存エラー: {e}", exc_info=True)
            return False, f"ローカルへの保存に失敗しました: {e}"

    # ▼▼▼【修正箇所】google_analytics_id を引数に追加 ▼▼▼
    def publish_surgery_dashboard(self, df: pd.DataFrame, target_dict: Dict[str, float], 
                                  analysis_base_date: pd.Timestamp,
                                  period: str = "直近12週", 
                                  report_type: str = "integrated_dashboard",
                                  google_analytics_id: Optional[str] = None) -> Tuple[bool, str]:
        """手術分析ダッシュボードを公開（4タブ統合版）"""
        try:
            logger.info(f"🚀 統合手術分析ダッシュボード公開開始: 4タブ構成")
            self.df = df
            # ▼▼▼【修正箇所】google_analytics_id を渡す ▼▼▼
            html_content = self._generate_integrated_html_content(df, target_dict, period, analysis_base_date, google_analytics_id)
            
            if not html_content:
                return False, "HTMLコンテンツの生成に失敗しました"
            
            success, message = self._upload_to_github(html_content)
            
            if success:
                public_url = self.get_public_url()
                return True, f"統合ダッシュボードの公開が完了しました\n📍 URL: {public_url}"
            else:
                return False, f"公開に失敗しました: {message}"
                
        except Exception as e:
            logger.error(f"公開エラー: {e}")
            return False, str(e)
    
    def _get_recent_week_kpi_data(self, df: pd.DataFrame, analysis_base_date: pd.Timestamp) -> Dict[str, Any]:
        """直近週のKPIデータを計算"""
        try:
            from analysis.weekly import get_analysis_end_date

            analysis_end_date = get_analysis_end_date(analysis_base_date)
            if not analysis_end_date: return {}
            
            one_week_ago = analysis_end_date - pd.Timedelta(days=6)
            recent_week_df = df[(df['手術実施日_dt'] >= one_week_ago) & (df['手術実施日_dt'] <= analysis_end_date)]

            if recent_week_df.empty:
                return {}

            gas_df = recent_week_df[recent_week_df['is_gas_20min']]
            gas_weekday_df = gas_df[gas_df['is_weekday']]
            
            num_weekdays = len(pd.bdate_range(start=one_week_ago, end=analysis_end_date))
            daily_avg = len(gas_weekday_df) / num_weekdays if num_weekdays > 0 else 0.0

            return {
                "全身麻酔手術件数 (直近週)": len(gas_df),
                "全手術件数 (直近週)": len(recent_week_df),
                "平日1日あたり全身麻酔手術件数 (直近週)": f"{daily_avg:.1f}",
            }
        except Exception as e:
            logger.error(f"直近週KPI取得エラー: {e}")
            return {}

    # ▼▼▼【修正箇所】google_analytics_id を引数に追加 ▼▼▼
    def _generate_integrated_html_content(self, df: pd.DataFrame, target_dict: Dict[str, float], 
                                          period: str, analysis_base_date: pd.Timestamp,
                                          google_analytics_id: Optional[str] = None) -> Optional[str]:
        """統合HTMLコンテンツを生成（4タブ構成）"""
        try:
            basic_kpi = self._get_basic_kpi_data(df, analysis_base_date)
            yearly_data = self._get_yearly_comparison_data(df, analysis_base_date)
            high_score_data = self._get_high_score_data(df, target_dict, period)
            dept_performance = self._get_department_performance_data(df, target_dict, analysis_base_date)
            recent_week_kpi = self._get_recent_week_kpi_data(df, analysis_base_date)
            
            # ▼▼▼【修正箇所】google_analytics_id を渡す ▼▼▼
            return self._generate_4tab_dashboard_html(
                yearly_data=yearly_data, basic_kpi=basic_kpi, high_score_data=high_score_data,
                dept_performance=dept_performance, period=period, recent_week_kpi=recent_week_kpi,
                analysis_base_date=analysis_base_date,
                google_analytics_id=google_analytics_id
            )
        except Exception as e:
            logger.error(f"統合HTMLコンテンツ生成エラー: {e}")
            return self._generate_error_html(str(e))
    
    def _get_basic_kpi_data(self, df: pd.DataFrame, analysis_base_date: pd.Timestamp) -> Dict[str, Any]:
        """基本KPIデータ取得"""
        try:
            from analysis.ranking import get_kpi_summary
            return get_kpi_summary(df, analysis_base_date)
        except Exception as e:
            logger.error(f"基本KPI取得エラー: {e}")
            return {}
    
    def _get_yearly_comparison_data(self, df: pd.DataFrame, analysis_base_date: pd.Timestamp) -> Dict[str, Any]:
        """年度比較データ取得"""
        try:
            from analysis.ranking import calculate_yearly_surgery_comparison
            return calculate_yearly_surgery_comparison(df, analysis_base_date)
        except Exception as e:
            logger.error(f"年度比較データ取得エラー: {e}")
            return {}
    
    def _get_high_score_data(self, df: pd.DataFrame, target_dict: Dict[str, float], period: str) -> list:
        """ハイスコアデータ取得"""
        try:
            from analysis.surgery_high_score import calculate_surgery_high_scores
            return calculate_surgery_high_scores(df, target_dict, period)
        except Exception as e:
            logger.error(f"ハイスコアデータ取得エラー: {e}")
            return []
    
    def _get_department_performance_data(self, df: pd.DataFrame, target_dict: Dict[str, float], 
                                         analysis_base_date: pd.Timestamp) -> pd.DataFrame:
        """診療科別パフォーマンスデータ取得"""
        try:
            from analysis.ranking import get_department_performance_summary
            return get_department_performance_summary(df, target_dict, analysis_base_date)
        except Exception as e:
            logger.error(f"診療科別パフォーマンスデータ取得エラー: {e}")
            return pd.DataFrame()
    
    # ▼▼▼【修正箇所】google_analytics_id を引数に追加し、HTMLに埋め込む ▼▼▼
    def _generate_4tab_dashboard_html(self, yearly_data: Dict[str, Any], basic_kpi: Dict[str, Any],
                                    high_score_data: list, dept_performance: pd.DataFrame,
                                    period: str, recent_week_kpi: Dict[str, Any],
                                    analysis_base_date: pd.Timestamp,
                                    google_analytics_id: Optional[str] = None) -> str:
        """4タブダッシュボードHTML生成"""
        try:
            current_date = datetime.now().strftime('%Y年%m月%d日')
            
            # Google Analytics トラッキングコードの生成
            ga_script_html = ""
            if google_analytics_id:
                ga_script_html = f"""
    <script async src="https://www.googletagmanager.com/gtag/js?id={google_analytics_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{{{dataLayer.push(arguments);}}}}
      gtag('js', new Date());
      gtag('config', '{google_analytics_id}');
    </script>"""

            return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏥 手術分析ダッシュボード</title>
    {ga_script_html}
    <style>{self._get_integrated_dashboard_css()}</style>
</head>
<body>
    {self._generate_header_html()}
    
    <div class="container">
        {self._generate_tab_navigation_html()}
        
        {self._generate_hospital_summary_tab(yearly_data, basic_kpi, recent_week_kpi, analysis_base_date)}
        
        {self._generate_high_score_tab(high_score_data, period)}
        
        {self._generate_department_performance_tab(dept_performance)}
        
        {self._generate_analysis_tab(yearly_data, basic_kpi)}
    </div>
    
    {self._generate_javascript_functions()}
    {self._generate_footer_html(current_date)}
</body>
</html>"""
            
        except Exception as e:
            logger.error(f"4タブHTML生成エラー: {e}")
            return self._generate_error_html(str(e))

    def _generate_header_html(self) -> str:
        """ヘッダーHTML生成（ポータルボタン追加版）"""
        return """
        <div class="header">
            <a href="../index.html" class="portal-home-button">🏠 ポータルTOPへ</a>
            <h1>🏥 手術分析ダッシュボード</h1>
            <div class="header-subtitle">診療科別パフォーマンス分析システム</div>
            <button class="info-button" onclick="toggleInfoPanel()" title="評価基準・用語説明">
                ℹ️ 説明
            </button>
        </div>

        <div id="info-overlay" class="info-overlay" onclick="closeInfoPanel()"></div>
        
        <div id="info-panel" class="info-panel">
            <div class="info-panel-header">
                <h2>📚 評価基準・用語説明</h2>
                <button class="close-button" onclick="closeInfoPanel()">✕</button>
            </div>
            <div class="info-panel-content">
                <div class="info-section">
                    <h3>🏥 病院全体サマリ評価基準</h3>
                    <p>「病院全体手術サマリ」タブの各カードの評価（優秀・良好・注意・要改善）は、以下の全身麻酔手術件数に基づいて決定されます。</p>
                    
                    <h4 style="margin-top: 16px; margin-bottom: 8px;">📅 直近週パフォーマンス</h4>
                    <table class="score-table" style="width:100%;">
                        <tbody>
                            <tr><td style="width: 30%;">優秀 (Success)</td><td>100件以上</td></tr>
                            <tr><td>良好 (Info)</td><td>80件以上 - 100件未満</td></tr>
                            <tr><td>注意 (Warning)</td><td>70件以上 - 80件未満</td></tr>
                            <tr><td>要改善 (Danger)</td><td>70件未満</td></tr>
                        </tbody>
                    </table>

                    <h4 style="margin-top: 20px; margin-bottom: 8px;">📊 直近4週間パフォーマンス</h4>
                    <table class="score-table" style="width:100%;">
                        <tbody>
                            <tr><td style="width: 30%;">優秀 (Success)</td><td>400件以上</td></tr>
                            <tr><td>良好 (Info)</td><td>350件以上 - 400件未満</td></tr>
                            <tr><td>注意 (Warning)</td><td>280件以上 - 350件未満</td></tr>
                            <tr><td>要改善 (Danger)</td><td>280件未満</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="info-section">
                    <h3>🎯 評価基準</h3>
                </div>
                
                <div class="info-section score-calculation-section">
                    <h3>🏆 ハイスコア計算方法（100点満点）</h3>
                    <div class="score-explanation">
                        <p class="score-intro">診療科ランキングの総合スコアは、以下の3つの指標から構成されています：</p>
                        <div class="score-component">
                            <h4>1. 🎯 全身麻酔手術件数（70点満点）- 最重要指標</h4>
                            <div class="score-detail">
                                <p>週単位の全身麻酔手術件数（麻酔時間20分以上）を多角的に評価します。</p>
                                <div class="score-breakdown">
                                    <h5>配点内訳：</h5>
                                    <ul>
                                        <li><strong>直近週達成度（25点）</strong>
                                            <ul>
                                                <li>CSV目標値に対する達成率で評価</li>
                                                <li>達成率100%以上：25点</li>
                                                <li>達成率90-99%：20点</li>
                                                <li>達成率80-89%：15点</li>
                                                <li>達成率70-79%：10点</li>
                                                <li>達成率70%未満：0-5点</li>
                                            </ul>
                                        </li>
                                        <li><strong>貢献度（20点）</strong>
                                            <ul>
                                                <li>病院全体の全身麻酔手術合計件数に占める診療科の割合</li>
                                                <li>30%以上：20点</li>
                                                <li>20%～30%未満：15点</li>
                                                <li>15%～20%未満：10点</li>
                                                <li>10%～15%未満：5点</li>
                                                <li>10%未満：0点</li>
                                            </ul>
                                        </li>
                                        <li><strong>改善度（10点）</strong>
                                            <ul>
                                                <li>評価期間の平均と過去期間の平均を比較</li>
                                                <li>改善率+20%以上：10点</li>
                                                <li>改善率+10-19%：8点</li>
                                                <li>改善率+5-9%：6点</li>
                                                <li>改善率0-4%：4点</li>
                                                <li>マイナス成長：0点</li>
                                            </ul>
                                        </li>
                                        <li><strong>安定性（10点）</strong>
                                            <ul>
                                                <li>週次実績の変動係数で評価</li>
                                                <li>変動係数10%未満：10点</li>
                                                <li>変動係数10-20%：8点</li>
                                                <li>変動係数20-30%：6点</li>
                                                <li>変動係数30-40%：4点</li>
                                                <li>変動係数40%以上：0点</li>
                                            </ul>
                                        </li>
                                        <li><strong>持続性（5点）</strong>
                                            <ul>
                                                <li>週次トレンドの傾きで評価</li>
                                                <li>上昇トレンド：5点</li>
                                                <li>横ばいトレンド：3点</li>
                                                <li>下降トレンド：0点</li>
                                            </ul>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <div class="score-component">
                            <h4>2.  全手術件数（15点満点）</h4>
                            <div class="score-detail">
                                <p>診療科の全体的な手術活動量を評価します。</p>
                                
                                <div class="score-breakdown">
                                    <h5>配点内訳：</h5>
                                    <ul>
                                        <li><strong>診療科間ランキング（10点）</strong>
                                            <ul>
                                                <li>1位：10点</li>
                                                <li>2位：8点</li>
                                                <li>3位：6点</li>
                                                <li>4位：4点</li>
                                                <li>5位：2点</li>
                                                <li>6位以下：0点</li>
                                            </ul>
                                        </li>
                                        <li><strong>改善度（5点）</strong>
                                            <ul>
                                                <li>前期比+10%以上：5点</li>
                                                <li>前期比+5-9%：3点</li>
                                                <li>前期比0-4%：1点</li>
                                                <li>前期比マイナス：0点</li>
                                            </ul>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <div class="score-component">
                            <h4>3. ⏱️ 総手術時間（15点満点）</h4>
                            <div class="score-detail">
                                <p>手術室の稼働効率と貢献度を評価します。</p>
                                
                                <div class="score-breakdown">
                                    <h5>配点内訳：</h5>
                                    <ul>
                                        <li><strong>診療科間ランキング（10点）</strong>
                                            <ul>
                                                <li>1位：10点</li>
                                                <li>2位：8点</li>
                                                <li>3位：6点</li>
                                                <li>4位：4点</li>
                                                <li>5位：2点</li>
                                                <li>6位以下：0点</li>
                                            </ul>
                                        </li>
                                        <li><strong>改善度（5点）</strong>
                                            <ul>
                                                <li>前期比+10%以上：5点</li>
                                                <li>前期比+5-9%：3点</li>
                                                <li>前期比0-4%：1点</li>
                                                <li>前期比マイナス：0点</li>
                                            </ul>
                                        </li>
                                    </ul>
                                </div>
                                
                                <div class="calculation-note">
                                    <p><strong>⚠️ 手術時間の計算方法：</strong></p>
                                    <ul>
                                        <li>入室時刻から退室時刻までの経過時間</li>
                                        <li>深夜跨ぎ対応（23:30入室→1:15退室 = 1時間45分）</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <div class="total-score-summary">
                            <h4>📊 総合スコア = 全身麻酔(70点) + 全手術(15点) + 手術時間(15点)</h4>
                            <p class="score-note">※ 最高100点満点で評価</p>
                            
                            <div class="grade-system">
                                <h5>グレード判定：</h5>
                                <ul class="grade-list">
                                    <li><span class="grade-badge grade-s">S</span> 90点以上（卓越したパフォーマンス）</li>
                                    <li><span class="grade-badge grade-a">A</span> 80-89点（優秀なパフォーマンス）</li>
                                    <li><span class="grade-badge grade-b">B</span> 70-79点（良好なパフォーマンス）</li>
                                    <li><span class="grade-badge grade-c">C</span> 60-69点（標準的なパフォーマンス）</li>
                                    <li><span class="grade-badge grade-d">D</span> 60点未満（改善が必要）</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

            <div class="info-section">
                <h3>📖 用語説明</h3>
                <dl class="term-list">
                    <dt>全身麻酔手術</dt>
                    <dd>麻酔時間が20分以上の手術。病院の手術活動の主要指標として重要視されます。</dd>
                    
                    <dt>変動係数（CV）</dt>
                    <dd>標準偏差を平均値で割った値。データのばらつきの程度を示し、値が小さいほど安定していることを意味します。</dd>
                    
                    <dt>週次トレンド</dt>
                    <dd>週ごとの手術件数の推移を線形回帰で分析した傾向。正の傾きは成長、負の傾きは減少を示します。</dd>
                    
                    <dt>達成率</dt>
                    <dd>実績値を目標値で割った百分率。100%以上が目標達成を意味します。</dd>
                    
                    <dt>改善度</dt>
                    <dd>現在の期間の平均値と過去の期間の平均値を比較した成長率。プラスの値は改善を示します。</dd>
                </dl>
            </div>
            
            <div class="info-section">
                <h3>🧮 計算方法</h3>
                <div class="formula-list">
                    <div class="formula-item">
                        <strong>達成率の計算</strong>
                        <code>達成率 = (実績値 ÷ 目標値) × 100</code>
                    </div>
                    
                    <div class="formula-item">
                        <strong>改善度の計算</strong>
                        <code>改善度 = ((現在期間平均 - 過去期間平均) ÷ 過去期間平均) × 100</code>
                    </div>
                    
                    <div class="formula-item">
                        <strong>変動係数の計算</strong>
                        <code>変動係数 = (標準偏差 ÷ 平均値) × 100</code>
                    </div>
                    
                    <div class="formula-item">
                        <strong>手術時間の計算</strong>
                        <code>手術時間 = 退室時刻 - 入室時刻（深夜跨ぎ対応）</code>
                    </div>
                </div>
            </div>
            
            <div class="info-section">
                <h3>💡 活用のヒント</h3>
                <ul class="tips-list">
                    <li><strong>目標設定の重要性：</strong>適切な目標値設定が正確な評価の基礎となります。過去実績と将来計画を考慮して設定しましょう。</li>
                    
                    <li><strong>トレンド分析：</strong>単発の数値だけでなく、時系列での推移を見ることで、改善傾向や問題の早期発見が可能です。</li>
                    
                    <li><strong>診療科間比較：</strong>他診療科との比較により、自科の相対的な位置づけを把握し、ベストプラクティスを学ぶ機会となります。</li>
                    
                    <li><strong>安定性の重視：</strong>高い実績も重要ですが、安定した手術実施は病院運営の観点から極めて重要です。</li>
                    
                    <li><strong>定期的な確認：</strong>週次でダッシュボードを確認し、早期の問題発見と対策立案を心がけましょう。</li>
                </ul>
            </div>
        </div>
    </div>
    """

    def _generate_tab_navigation_html(self) -> str:
        """タブナビゲーションHTML生成（統一デザイン版）"""
        return """
        <div class="view-selector">
            <div class="view-tabs">
                <div class="view-tab active" onclick="showView('surgery-summary')">
                    🏥 病院全体手術サマリ
                </div>
                <div class="view-tab" onclick="showView('high-score')">
                    🏆 ハイスコア TOP3
                </div>
                <div class="view-tab" onclick="showView('performance')">
                    📊 診療科別パフォーマンス
                </div>
                <div class="view-tab" onclick="showView('analysis')">
                    📈 詳細分析
                </div>
            </div>
        </div>
        """

    def _generate_unified_hospital_summary_html(self, yearly_data: Dict[str, Any], basic_kpi: Dict[str, Any], recent_week_kpi: Dict[str, Any]) -> str:
        """統一デザインの病院全体サマリHTMLを生成"""
        if not yearly_data and not basic_kpi:
            return "<div><p>病院サマリーデータを準備中です...</p></div>"
        
        # --- 1. 直近週パフォーマンスカード ---
        recent_week_gas = recent_week_kpi.get("全身麻酔手術件数 (直近週)", 0)
        recent_week_total = recent_week_kpi.get("全手術件数 (直近週)", 0)
        recent_week_daily_avg = recent_week_kpi.get("平日1日あたり全身麻酔手術件数 (直近週)", "0.0")
    
        # 直近週の状態判定
        # 評価クラスを決定
        if recent_week_gas >= 100:
            recent_week_class = "success"
        elif recent_week_gas >= 80:
            recent_week_class = "info"
        elif recent_week_gas >= 70:
            recent_week_class = "warning"
        else:
            recent_week_class = "danger"

        recent_week_card = f"""
        <div class="metric-card {recent_week_class}">
            <div class="metric-title">📅 直近週パフォーマンス</div>
            <div class="metric-row">
                <span>全身麻酔手術件数</span>
                <span class="metric-value-row">{recent_week_gas:,} 件</span>
            </div>
            <div class="metric-row">
                <span>全手術件数</span>
                <span class="metric-value-row">{recent_week_total:,} 件</span>
            </div>
            <div class="metric-row">
                <span>平日1日あたり全身麻酔手術</span>
                <span class="metric-value-row">{recent_week_daily_avg} 件</span>
            </div>
            <div class="achievement-row">
                <span>評価</span>
                <span>{'優秀' if recent_week_class == 'success' else '良好' if recent_week_class == 'info' else '注意' if recent_week_class == 'warning' else '要改善'}</span>
            </div>
        </div>
        """
    
        # --- 2. 直近4週間パフォーマンスカード ---
        gas_cases_4w = basic_kpi.get("全身麻酔手術件数 (直近4週)", 0)
        total_cases_4w = basic_kpi.get("全手術件数 (直近4週)", 0)
        daily_avg_str_4w = basic_kpi.get("平日1日あたり全身麻酔手術件数", "0.0")
    
        # 4週間の状態判定
        if gas_cases_4w >= 400:
            four_week_class = "success"
        elif gas_cases_4w >= 350:
            four_week_class = "info"
        elif gas_cases_4w >= 280:
            four_week_class = "warning"
        else:
            four_week_class = "danger"
    
        four_weeks_card = f"""
        <div class="metric-card {four_week_class}">
            <div class="metric-title">📊 直近4週間パフォーマンス</div>
            <div class="metric-row">
                <span>全身麻酔手術件数</span>
                <span class="metric-value-row">{gas_cases_4w:,} 件</span>
            </div>
            <div class="metric-row">
                <span>全手術件数</span>
                <span class="metric-value-row">{total_cases_4w:,} 件</span>
            </div>
            <div class="metric-row">
                <span>平日1日あたり全身麻酔手術</span>
                <span class="metric-value-row">{daily_avg_str_4w} 件</span>
            </div>
            <div class="achievement-row">
                <span>評価</span>
                <span>{'優秀' if four_week_class == 'success' else '良好' if four_week_class == 'info' else '注意' if four_week_class == 'warning' else '要改善'}</span>
            </div>
        </div>
        """
        
        # --- 3. 年度比較カード ---
        growth_rate = yearly_data.get('growth_rate', 0)
        yearly_class = "info"
        if growth_rate > 5:
            yearly_class = "success"
        elif growth_rate >= 0:
            yearly_class = "warning"
        else:
            yearly_class = "danger"
    
        yearly_card = f"""
        <div class="metric-card {yearly_class}">
            <div class="metric-title">📈 全身麻酔手術件数 年度比較</div>
            <div class="metric-row">
                <span>今年度累計 ({yearly_data.get('comparison_period', 'N/A')})</span>
                <span class="metric-value-row">{yearly_data.get('current_fiscal_total', 0):,} 件</span>
            </div>
            <div class="metric-row">
                <span>昨年度同期</span>
                <span class="metric-value-row">{yearly_data.get('prev_fiscal_total', 0):,} 件</span>
            </div>
            <div class="metric-row">
                <span>年度末予測</span>
                <span class="metric-value-row">{yearly_data.get('projected_annual', 0):,} 件</span>
            </div>
            <div class="achievement-row">
                <span>前年度同期比</span>
                <span>{yearly_data.get('difference', 0):+,} 件 ({growth_rate:+.1f}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {min(abs(growth_rate) * 10, 100)}%;"></div>
            </div>
        </div>
        """
        
        # --- 4. 稼働率カード ---
        utilization_str = basic_kpi.get("手術室稼働率 (全手術、平日のみ)", "0.0%")
        prev_year_utilization = yearly_data.get('prev_year_utilization_rate', 'N/A')
        
        try:
            utilization_val = float(utilization_str.replace('%',''))
            if utilization_val >= 85:
                util_class = "success"
            elif utilization_val >= 80:
                util_class = "warning"
            elif utilization_val >= 75:
                util_class = "info"
            else:
                util_class = "danger"
        except ValueError:
            util_class = "danger"
            utilization_val = 0
        
        prev_year_html = ""
        if prev_year_utilization != 'N/A':
            prev_year_html = f"""
            <div class="metric-row">
                <span>前年度同期稼働率</span>
                <span class="metric-value-row">{prev_year_utilization}</span>
            </div>
            """
        
        utilization_card = f"""
        <div class="metric-card {util_class}">
            <div class="metric-title">🏥 手術室稼働率 (直近4週)</div>
            <div class="metric-row">
                <span>現在の稼働率</span>
                <span class="metric-value-row">{utilization_str}</span>
            </div>
            {prev_year_html}
            <div class="achievement-row">
                <span>評価</span>
                <span>{'優秀' if util_class == 'success' else '良好' if util_class == 'info' else '注意' if util_class == 'warning' else '改善余地あり'}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {min(utilization_val, 100)}%;"></div>
            </div>
        </div>
        """
    
        # --- カードを統一レイアウトで結合 ---
        return f"""
        <div class="summary">
            <h2>🏥 病院全体サマリー</h2>
        </div>
        <div class="grid-container">
            {recent_week_card}
            {four_weeks_card}
            {yearly_card}
            {utilization_card}
        </div>
    """

    def _generate_hospital_summary_tab(self, yearly_data: Dict[str, Any], basic_kpi: Dict[str, Any], 
                                     recent_week_kpi: Dict[str, Any], analysis_base_date: pd.Timestamp) -> str:
        """病院全体手術サマリタブ生成（デザイン統一版 + 週別推移チャート追加）"""
        try:
            summary_html = self._generate_unified_hospital_summary_html(yearly_data, basic_kpi, recent_week_kpi)
            monthly_trend_chart = self._generate_monthly_trend_section(yearly_data)
            
            if hasattr(self, 'df'):
                # <<< 修正点: ここで analysis_base_date を使う >>>
                weekly_trend_data = self._get_weekly_trend_data(self.df, analysis_base_date)
                weekly_trend_chart = self._generate_weekly_trend_section(weekly_trend_data)
            else:
                weekly_trend_chart = self._generate_fallback_weekly_chart()
            
            return f"""
            <div id="surgery-summary" class="view-content active">
                {summary_html}
                {monthly_trend_chart}
                {weekly_trend_chart}
            </div>
            """
            
        except Exception as e:
            logger.error(f"病院サマリタブ生成エラー: {e}")
            return '<div id="surgery-summary" class="view-content active"><p>病院サマリデータを読み込み中...</p></div>'

    def _generate_high_score_tab(self, high_score_data: list, period: str) -> str:
        """ハイスコア TOP3タブ生成（統一デザイン版）"""
        try:
            if not high_score_data:
                return '<div id="high-score" class="view-content"><p>ハイスコアデータがありません</p></div>'
            
            # TOP3を取得
            top3 = high_score_data[:3]
            
            ranking_html = ""
            for i, dept in enumerate(top3):
                rank_emoji = ["🥇", "🥈", "🥉"][i]
                achievement_pct = dept.get('achievement_rate', 0)
                
                # 統一されたランキングカード
                ranking_html += f"""
                <div class="ranking-card rank-{i+1}">
                    <div class="rank-header">
                        <span class="medal">{rank_emoji}</span>
                        <span class="rank-label">診療科{i+1}位</span>
                    </div>
                    <div class="dept-name">{dept['display_name']}</div>
                    <div class="score-info">
                        <div class="achievement">達成率 {achievement_pct:.1f}%</div>
                        <div class="score-value">{dept['total_score']:.0f}点</div>
                    </div>
                </div>
                """
            
            # 1位の詳細スコア（統一デザイン）
            score_breakdown = ""
            if top3:
                top_dept = top3[0]
                target_perf = top_dept.get('target_performance', {})
                improvement_score = top_dept.get('improvement_score', {})
                
                score_breakdown = f"""
                <div class="summary">
                    <h2>👑 診療科1位：{top_dept['display_name']}</h2>
                    <div class="summary-stats">
                        <div class="stat-item">
                            <div class="stat-value">{top_dept['total_score']:.0f}点</div>
                            <div class="stat-label">総合スコア</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{top_dept.get('achievement_rate', 0):.1f}%</div>
                            <div class="stat-label">達成率</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{top_dept.get('hospital_rank', 0)}位</div>
                            <div class="stat-label">病院内順位</div>
                        </div>
                    </div>
                </div>
                
                <div class="grid-container">
                    <div class="metric-card success">
                        <div class="metric-title">📊 対目標パフォーマンス</div>
                        <div class="metric-row">
                            <span>スコア</span>
                            <span class="metric-value-row">{target_perf.get('total', 0):.0f}点</span>
                        </div>
                        <div class="achievement-row">
                            <span>達成率</span>
                            <span>{top_dept.get('achievement_rate', 0):.1f}%</span>
                        </div>
                    </div>
                    
                    <div class="metric-card info">
                        <div class="metric-title">📈 改善・継続性</div>
                        <div class="metric-row">
                            <span>スコア</span>
                            <span class="metric-value-row">{improvement_score.get('total', 0):.0f}点</span>
                        </div>
                        <div class="achievement-row">
                            <span>安定性</span>
                            <span>{improvement_score.get('stability', 0):.0f}点</span>
                        </div>
                    </div>
                    
                    <div class="metric-card warning">
                        <div class="metric-title">🎯 相対競争力</div>
                        <div class="metric-row">
                            <span>スコア</span>
                            <span class="metric-value-row">{top_dept.get('competitive_score', 0):.0f}点</span>
                        </div>
                        <div class="achievement-row">
                            <span>改善度</span>
                            <span>{top_dept.get('improvement_rate', 0):+.1f}%</span>
                        </div>
                    </div>
                </div>
                """
            
            return f"""
            <div id="high-score" class="view-content">
                <div class="stats-highlight">
                    <h2>🏆 診療科ランキング TOP3</h2>
                    <p>評価期間: {period}</p>
                </div>
                
                <div class="ranking-section">
                    {ranking_html}
                </div>
                
                {score_breakdown}
            </div>
            """
            
        except Exception as e:
            logger.error(f"ハイスコアタブ生成エラー: {e}")
            return '<div id="high-score" class="view-content"><p>ハイスコアデータの読み込みでエラーが発生しました</p></div>'


    def _generate_department_performance_tab(self, dept_performance: pd.DataFrame) -> str:
        """診療科別パフォーマンスタブ生成（統一デザイン版）"""
        try:
            if dept_performance.empty:
                return '<div id="performance" class="view-content"><p>診療科別パフォーマンスデータがありません</p></div>'
            
            # サマリー統計
            total_depts = len(dept_performance)
            achieving_depts = len(dept_performance[dept_performance['達成率(%)'] >= 100])
            avg_achievement = dept_performance['達成率(%)'].mean()
            
            summary_html = f"""
            <div class="summary">
                <h2>📊 診療科別パフォーマンス概要</h2>
                <div class="summary-stats">
                    <div class="stat-item">
                        <div class="stat-value">{total_depts}</div>
                        <div class="stat-label">診療科数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{achieving_depts}</div>
                        <div class="stat-label">目標達成科数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{avg_achievement:.1f}%</div>
                        <div class="stat-label">平均達成率</div>
                    </div>
                </div>
            </div>
            """
            
            # 診療科カード生成（統一デザイン）
            cards_html = ""
            for _, row in dept_performance.iterrows():
                achievement_rate = row['達成率(%)']
                
                # 達成率に応じた統一クラス
                if achievement_rate >= 100:
                    card_class = "success"
                elif achievement_rate >= 90:
                    card_class = "info"
                elif achievement_rate >= 80:
                    card_class = "warning"
                else:
                    card_class = "danger"
                
                cards_html += f"""
                <div class="metric-card {card_class}">
                    <div class="metric-title">{row['診療科']}</div>
                    <div class="metric-row">
                        <span>4週平均</span>
                        <span class="metric-value-row">{row['4週平均']:.1f} 件</span>
                    </div>
                    <div class="metric-row">
                        <span>直近週実績</span>
                        <span class="metric-value-row">{row['直近週実績']} 件</span>
                    </div>
                    <div class="metric-row">
                        <span>週次目標</span>
                        <span class="metric-value-row">{row['週次目標']:.1f} 件</span>
                    </div>
                    <div class="achievement-row">
                        <span>達成率</span>
                        <span>{achievement_rate:.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {min(achievement_rate, 100)}%;"></div>
                    </div>
                </div>
                """
            
            return f"""
            <div id="performance" class="view-content">
                {summary_html}
                <div class="grid-container">
                    {cards_html}
                </div>
            </div>
            """
        except Exception as e:
            logger.error(f"診療科別パフォーマンスタブ生成エラー: {e}")
            return '<div id="performance" class="view-content"><p>診療科別パフォーマンスデータの読み込みでエラーが発生しました</p></div>'

    def _generate_analysis_tab(self, yearly_data: Dict[str, Any], basic_kpi: Dict[str, Any]) -> str:
        """詳細分析タブ生成（統一デザイン版）"""
        try:
            growth_rate = yearly_data.get('growth_rate', 0) if yearly_data else 0
            utilization_str = basic_kpi.get("手術室稼働率 (全手術、平日のみ)", "0%") if basic_kpi else "0%"
            
            try:
                utilization = float(utilization_str.replace("%", ""))
            except ValueError:
                utilization = 0
            
            # 分析結果の判定
            improvement_class = "success" if growth_rate > 0 else "warning" if growth_rate >= -2 else "danger"
            action_class = "info"
            
            improvement_analysis = f"""
            <div class="analysis-card {improvement_class}">
                <h3>{'✅ 年度目標達成状況' if growth_rate > 0 else '⚠️ 注意ポイント' if growth_rate >= -2 else '🚨 緊急対応事項'}</h3>
                <ul>
                    <li>前年度同期比{growth_rate:+.1f}%{'の順調な増加' if growth_rate > 0 else 'で要改善'}</li>
                    <li>手術室稼働率{utilization:.1f}%は{'適正水準' if utilization >= 80 else '改善余地あり'}</li>
                    <li>年度末予測{yearly_data.get('projected_annual', 0):,}件{'は過去最高水準' if growth_rate > 10 else 'の実現を目指す'}</li>
                    <li>{'継続的な成長基調を維持' if growth_rate > 5 else '更なる取り組み強化が必要'}</li>
                </ul>
            </div>
            """
            
            action_plan = f"""
            <div class="analysis-card {action_class}">
                <h3>🎯 目標達成施策</h3>
                <ul>
                    <li>手術室稼働率を{max(85, utilization + 5):.0f}%以上に向上させる</li>
                    <li>診療科間の手術枠最適化を実施する</li>
                    <li>緊急手術体制の強化を検討する</li>
                    <li>年度末目標：{int(yearly_data.get('projected_annual', 0) * 1.03):,}件を目指す</li>
                    <li>{'現在の成長ペースを維持する' if growth_rate > 5 else 'パフォーマンス向上策を強化する'}</li>
                </ul>
            </div>
            """
            
            # KPI要約カード
            kpi_summary = f"""
            <div class="metric-card {'success' if growth_rate > 5 and utilization >= 85 else 'warning' if growth_rate >= 0 or utilization >= 80 else 'danger'}">
                <div class="metric-title">📊 統合パフォーマンス指標</div>
                <div class="metric-row">
                    <span>年度成長率</span>
                    <span class="metric-value-row">{growth_rate:+.1f}%</span>
                </div>
                <div class="metric-row">
                    <span>手術室稼働率</span>
                    <span class="metric-value-row">{utilization:.1f}%</span>
                </div>
                <div class="metric-row">
                    <span>年度末予測</span>
                    <span class="metric-value-row">{yearly_data.get('projected_annual', 0):,}件</span>
                </div>
                <div class="achievement-row">
                    <span>総合評価</span>
                    <span>{'優秀' if growth_rate > 5 and utilization >= 85 else '良好' if growth_rate >= 0 or utilization >= 80 else '要改善'}</span>
                </div>
            </div>
            """
            
            return f"""
            <div id="analysis" class="view-content">
                <div class="summary">
                    <h2>📈 詳細分析・改善提案</h2>
                </div>
                
                <div class="grid-container" style="grid-template-columns: 1fr;">
                    {kpi_summary}
                </div>
                
                <div class="analysis-section">
                    <h2>📊 年度目標達成分析</h2>
                    <div class="analysis-grid">
                        {improvement_analysis}
                        {action_plan}
                    </div>
                </div>
            </div>
            """
            
        except Exception as e:
            logger.error(f"詳細分析タブ生成エラー: {e}")
            return '<div id="analysis" class="view-content"><p>詳細分析データの読み込みでエラーが発生しました</p></div>'

    def _get_monthly_trend_data(self, df: pd.DataFrame, yearly_data: Dict[str, Any]) -> list:
        """実データに基づく月別トレンドデータ取得（月末までデータが揃っている直近12ヶ月分）"""
        try:
            if df.empty:
                return []
    
            # 日付列をdatetime型に変換
            # ▼▼▼【修正箇所】'pd.to_to_datetime' から 'pd.to_datetime' に修正 ▼▼▼
            df['手術実施日_dt'] = pd.to_datetime(df['手術実施日_dt'], errors='coerce')
            df.dropna(subset=['手術実施日_dt'], inplace=True)
    
            # データ内の最新の日付を取得
            analysis_base_date = df['手術実施日_dt'].max()
    
            # データが揃っている最後の月（分析基準日の前月）の最終日を計算
            start_of_current_month = analysis_base_date.replace(day=1)
            end_of_last_full_month = start_of_current_month - pd.Timedelta(days=1)
            
            result = []
            
            # 直近12ヶ月分のデータを遡って取得
            for i in range(12):
                # 基準となる月を計算
                target_month_date = end_of_last_full_month - pd.DateOffset(months=i)
                current_year = target_month_date.year
                current_month = target_month_date.month
    
                # is_gas_20min列がTrueのデータのみをフィルタリング
                gas_df = df[df['is_gas_20min'] == True]
    
                # 今年度データの取得 (該当年・月のデータを全て取得)
                current_month_df = gas_df[
                    (gas_df['手術実施日_dt'].dt.year == current_year) &
                    (gas_df['手術実施日_dt'].dt.month == current_month)
                ]
    
                # 前年度データの取得 (該当年・月のデータを全て取得)
                last_year_month_df = gas_df[
                    (gas_df['手術実施日_dt'].dt.year == current_year - 1) &
                    (gas_df['手術実施日_dt'].dt.month == current_month)
                ]
                
                month_name = f"{current_year % 100}年{current_month}月"
                current_count = len(current_month_df)
                last_year_count = len(last_year_month_df)
    
                result.append({
                    'month': f"{current_year}-{current_month:02d}",
                    'month_name': month_name,
                    'count': int(current_count),
                    'last_year_count': int(last_year_count) if last_year_count > 0 else None,
                    'is_partial': False  # 全て完了した月なので常にFalse
                })
            
            # 月の昇順に並び替え
            result.reverse()
            return result
            
        except Exception as e:
            logger.error(f"月別トレンドデータ取得エラー: {e}")
            return []

    def _generate_monthly_trend_section(self, yearly_data: Dict[str, Any]) -> str:
        """月別トレンドセクション生成（折れ線グラフ版、Y軸可変、過去6ヶ月表示）"""
        try:
            if not yearly_data:
                return ""
            
            if hasattr(self, 'df'):
                monthly_data = self._get_monthly_trend_data(self.df, yearly_data)
            else:
                logger.warning("dfが見つかりません。月別トレンドデータをスキップします。")
                return self._generate_fallback_trend_chart(yearly_data)
            
            if not monthly_data:
                return self._generate_fallback_trend_chart(yearly_data)
            
            import json
            
            labels = [item['month_name'] for item in monthly_data]
            values = [int(item['count']) for item in monthly_data]
            
            target_value = int(yearly_data.get('monthly_target', 420))
            target_line = [target_value] * len(labels)
            
            last_year_values = [int(item['last_year_count']) if item.get('last_year_count') is not None else 0 for item in monthly_data]
            # Noneをグラフにプロットしないようにnullに変換
            last_year_values_for_plot = [val if val > 0 else None for val in last_year_values]

            # Y軸の最大値・最小値をデータに合わせて動的に設定
            all_plot_values = [v for v in values if v is not None] + \
                              [v for v in last_year_values if v is not None and v > 0]
            if target_value:
                 all_plot_values.append(target_value)
            
            if not all_plot_values:
                min_value, max_value = 0, 500 # デフォルト値
            else:
                data_min = min(all_plot_values)
                data_max = max(all_plot_values)
                padding = (data_max - data_min) * 0.15 if (data_max - data_min) > 0 else 20
                min_value = int(max(0, data_min - padding))
                max_value = int(data_max + padding)

            html_content = f'''
            <div class="trend-chart">
                <h3>📈 月別推移（全身麻酔手術件数 - 直近12ヶ月）</h3>
                <div style="position: relative; height: 300px; margin: 20px 0;">
                    <canvas id="monthlyTrendChart"></canvas>
                </div>
                <p style="text-align: center; color: #666; font-size: 12px;">
                    実線：当月実績 | 点線：前年同月実績 | 破線：目標ライン（月{target_value}件）
                </p>
            </div>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
            <script>
            (function() {{
                function initChart() {{
                    const ctx = document.getElementById('monthlyTrendChart');
                    if (!ctx) {{
                        setTimeout(initChart, 100);
                        return;
                    }}
                    
                    const chartData = {{
                        labels: {json.dumps(labels, ensure_ascii=False)},
                        datasets: [
                            {{
                                label: '当月実績',
                                data: {json.dumps(values)},
                                borderColor: 'rgb(102, 126, 234)',
                                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                borderWidth: 3,
                                tension: 0.1,
                                pointRadius: 5,
                            }},
                            {{
                                label: '前年同月実績',
                                data: {json.dumps(last_year_values_for_plot)},
                                borderColor: 'rgb(156, 163, 175)',
                                backgroundColor: 'rgba(156, 163, 175, 0.1)',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                tension: 0.1,
                                pointRadius: 4,
                                spanGaps: true, // null値を線で繋がない
                            }},
                            {{
                                label: '目標ライン',
                                data: {json.dumps(target_line)},
                                borderColor: 'rgb(255, 152, 0)',
                                borderWidth: 2,
                                borderDash: [10, 5],
                                pointRadius: 0,
                                fill: false
                            }}
                        ]
                    }};
                    
                    const chartOptions = {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'top',
                            }},
                            tooltip: {{
                                mode: 'index',
                                intersect: false,
                                callbacks: {{
                                    label: function(context) {{
                                        let label = context.dataset.label || '';
                                        if (label) {{
                                            label += ': ';
                                        }}
                                        if (context.parsed.y !== null) {{
                                            label += context.parsed.y + '件';
                                        }}
                                        return label;
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                display: true,
                                suggestedMin: {min_value},
                                suggestedMax: {max_value},
                                grid: {{
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }},
                                ticks: {{
                                    callback: function(value) {{
                                        return Math.round(value) + '件';
                                    }}
                                }}
                            }}
                        }},
                        interaction: {{
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }}
                    }};
                    
                    new Chart(ctx, {{
                        type: 'line',
                        data: chartData,
                        options: chartOptions
                    }});
                }}
                
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initChart);
                }} else {{
                    setTimeout(initChart, 100);
                }}
            }})();
            </script>
            '''
            
            return html_content
            
        except Exception as e:
            logger.error(f"月別トレンドセクション生成エラー: {e}")
            return self._generate_fallback_trend_chart(yearly_data)
            

    def _generate_fallback_trend_chart(self, yearly_data: Dict[str, Any]) -> str:
        """フォールバック用の棒グラフ表示"""
        try:
            # yearly_dataから直接月別データを取得できる場合
            monthly_trend = yearly_data.get('monthly_trend', [])
            
            if not monthly_trend:
                return """
                <div class="trend-chart">
                    <h3>📈 月別推移（全身麻酔手術件数）</h3>
                    <p style="text-align: center; padding: 40px; color: #666;">
                        月別トレンドデータを準備中...
                    </p>
                </div>
                """
            
            # 最大値を取得してバーの高さを正規化
            max_count = max(int(item.get('count', 0)) for item in monthly_trend)
            if max_count == 0:
                max_count = 100
            
            bars_html = ""
            for item in monthly_trend[-4:]:  # 直近4ヶ月分を表示
                count = int(item.get('count', 0))
                height_percent = (count / max_count * 100) if max_count > 0 else 0
                month_name = item.get('month_name', item.get('month', ''))
                
                bars_html += f'''
                <div class="trend-bar" style="height: {height_percent}%;">
                    <div class="trend-bar-value">{count}</div>
                    <div class="trend-bar-label">{month_name}</div>
                </div>
                '''
            
            return f'''
            <div class="trend-chart">
                <h3>📈 月別推移（全身麻酔手術件数）</h3>
                <div class="trend-bars">
                    {bars_html}
                </div>
                <p style="text-align: center; color: #666; font-size: 12px;">
                    青：今年度実績 | 目標ペース：月平均{yearly_data.get('monthly_target', 420)}件
                </p>
            </div>
            '''
            
        except Exception as e:
            logger.error(f"フォールバックチャート生成エラー: {e}")
            return ""
            
    def _get_weekly_trend_data(self, df: pd.DataFrame, analysis_base_date: pd.Timestamp) -> list:
        """週別トレンドデータを取得"""
        try:
            from analysis.weekly import get_weekly_trend_data
            return get_weekly_trend_data(df, analysis_base_date, weeks=8)
        except Exception as e:
            logger.error(f"週別トレンドデータ取得エラー: {e}")
            return []
    
    def _generate_weekly_trend_section(self, weekly_data: list) -> str:
        """週別トレンドセクション生成（折れ線グラフ版、過去8週間表示）"""
        try:
            if not weekly_data:
                return self._generate_fallback_weekly_chart()
            
            import json
            from analysis.weekly import get_weekly_target_value
            
            labels = [item['week_name'] for item in weekly_data]
            values = [int(item['count']) for item in weekly_data]
            
            target_value = get_weekly_target_value()  # 95件
            target_line = [target_value] * len(labels)
            
            # Y軸の最大値・最小値をデータに合わせて動的に設定
            all_plot_values = [v for v in values if v is not None] + [target_value]
            
            if not all_plot_values:
                min_value, max_value = 0, 120
            else:
                data_min = min(all_plot_values)
                data_max = max(all_plot_values)
                padding = (data_max - data_min) * 0.15 if (data_max - data_min) > 0 else 10
                min_value = int(max(0, data_min - padding))
                max_value = int(data_max + padding)
    
            html_content = f'''
            <div class="trend-chart">
                <h3>📊 週別推移（全身麻酔手術件数 - 過去8週間）</h3>
                <div style="position: relative; height: 300px; margin: 20px 0;">
                    <canvas id="weeklyTrendChart"></canvas>
                </div>
                <p style="text-align: center; color: #666; font-size: 12px;">
                    実線：当週実績 | 破線：目標ライン（週{target_value}件）
                </p>
            </div>
            
            <script>
            (function() {{
                function initWeeklyChart() {{
                    const ctx = document.getElementById('weeklyTrendChart');
                    if (!ctx) {{
                        setTimeout(initWeeklyChart, 100);
                        return;
                    }}
                    
                    const chartData = {{
                        labels: {json.dumps(labels, ensure_ascii=False)},
                        datasets: [
                            {{
                                label: '当週実績',
                                data: {json.dumps(values)},
                                borderColor: 'rgb(34, 197, 94)',
                                backgroundColor: 'rgba(34, 197, 94, 0.1)',
                                borderWidth: 3,
                                tension: 0.1,
                                pointRadius: 5,
                                pointBackgroundColor: 'rgb(34, 197, 94)',
                            }},
                            {{
                                label: '目標ライン',
                                data: {json.dumps(target_line)},
                                borderColor: 'rgb(239, 68, 68)',
                                borderWidth: 2,
                                borderDash: [10, 5],
                                pointRadius: 0,
                                fill: false
                            }}
                        ]
                    }};
                    
                    const chartOptions = {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'top',
                            }},
                            tooltip: {{
                                mode: 'index',
                                intersect: false,
                                callbacks: {{
                                    label: function(context) {{
                                        let label = context.dataset.label || '';
                                        if (label) {{
                                            label += ': ';
                                        }}
                                        if (context.parsed.y !== null) {{
                                            label += context.parsed.y + '件';
                                        }}
                                        return label;
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                display: true,
                                suggestedMin: {min_value},
                                suggestedMax: {max_value},
                                grid: {{
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }},
                                ticks: {{
                                    callback: function(value) {{
                                        return Math.round(value) + '件';
                                    }}
                                }}
                            }}
                        }},
                        interaction: {{
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }}
                    }};
                    
                    new Chart(ctx, {{
                        type: 'line',
                        data: chartData,
                        options: chartOptions
                    }});
                }}
                
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initWeeklyChart);
                }} else {{
                    setTimeout(initWeeklyChart, 100);
                }}
            }})();
            </script>
            '''
            
            return html_content
            
        except Exception as e:
            logger.error(f"週別トレンドセクション生成エラー: {e}")
            return self._generate_fallback_weekly_chart()
    
    
    def _generate_fallback_weekly_chart(self) -> str:
        """フォールバック用の週別チャート表示"""
        return """
        <div class="trend-chart">
            <h3>📊 週別推移（全身麻酔手術件数 - 過去8週間）</h3>
            <p style="text-align: center; padding: 40px; color: #666;">
                週別トレンドデータを準備中...
            </p>
        </div>
        """

    def _generate_javascript_functions(self) -> str:
        """JavaScript関数生成（情報パネル機能追加版）"""
        return """
        <script>
            function showView(viewId) {
                // すべてのタブとコンテンツを非アクティブ化
                document.querySelectorAll('.view-tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                document.querySelectorAll('.view-content').forEach(content => {
                    content.classList.remove('active');
                });
                
                // 選択されたタブとコンテンツをアクティブ化
                event.target.classList.add('active');
                document.getElementById(viewId).classList.add('active');
            }
            
            // 情報パネルの表示/非表示
            function toggleInfoPanel() {
                const panel = document.getElementById('info-panel');
                const overlay = document.getElementById('info-overlay');
                
                if (panel.style.display === 'block') {
                    panel.style.display = 'none';
                    overlay.style.display = 'none';
                } else {
                    panel.style.display = 'block';
                    overlay.style.display = 'block';
                }
            }
            
            // オーバーレイクリックで閉じる
            function closeInfoPanel() {
                document.getElementById('info-panel').style.display = 'none';
                document.getElementById('info-overlay').style.display = 'none';
            }
            
            // ページ読み込み時の初期化
            document.addEventListener('DOMContentLoaded', function() {
                // デフォルトで病院全体手術サマリを表示
                document.getElementById('surgery-summary').classList.add('active');
            });
        </script>
        """

    def _generate_footer_html(self, current_date: str) -> str:
        """フッターHTML生成（統一デザイン版）"""
        return f"""
        <div class="footer">
            <div>生成日時: {current_date}</div>
            <div>手術分析ダッシュボード v2.0</div>
        </div>
        """
    
    def _generate_fallback_html(self, df: pd.DataFrame, target_dict: Dict[str, float], period: str) -> str:
        """フォールバック用HTML（既存TOP3表示）"""
        try:
            from reporting.surgery_high_score_html import generate_unified_surgery_report_html
            return generate_unified_surgery_report_html(df, target_dict, period, "weekly_ranking")
        except Exception as e:
            logger.error(f"フォールバックHTML生成エラー: {e}")
            return self._generate_error_html("データの読み込みに失敗しました")
    
    def _generate_error_html(self, error_message: str) -> str:
        """エラーHTML生成"""
        return f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>エラー - 手術分析ダッシュボード</title>
        </head>
        <body style="font-family: sans-serif; padding: 20px; text-align: center;">
            <h1>❌ ダッシュボード生成エラー</h1>
            <p>統合ダッシュボードの生成中にエラーが発生しました。</p>
            <p>エラー詳細: {error_message}</p>
            <p>データと設定を確認してから再度お試しください。</p>
        </body>
        </html>
        """
    
    def _get_integrated_dashboard_css(self) -> str:
        """手術分析ダッシュボード用CSS（情報パネル追加版）"""
        # 既存のCSSはそのまま残す
        base_css = """
            :root {
                /* === 統一カラーパレット === */
                --primary-color: #667eea;
                --primary-dark: #5a67d8;
                --success-color: #10B981;
                --info-color: #3B82F6;
                --warning-color: #F59E0B;
                --danger-color: #EF4444;
                
                /* === 統一テキストカラー === */
                --text-primary: #1F2937;
                --text-secondary: #6B7280;
                --text-muted: #9CA3AF;
                --text-light: #F3F4F6;
                
                /* === 統一スペーシング === */
                --card-padding: 20px;
                --card-gap: 16px;
                --border-radius: 12px;
                --transition: all 0.3s ease;
                
                /* === 統一シャドウ === */
                --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
                --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
                --shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.12);
            }
        
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                margin: 0;
                padding: 0;
                background: #f5f5f5;
                color: var(--text-primary);
                line-height: 1.6;
            }
            
            .header {
                text-align: center;
                padding: 24px 20px;
                background: white;
                box-shadow: var(--shadow-md);
                margin-bottom: 20px;
                position: relative;
            }

            /* === ポータルへ戻るボタン === */
            .portal-home-button {
                position: absolute;
                top: 20px;
                left: 20px;
                background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
                color: white;
                padding: 10px 20px;
                border-radius: 25px;
                text-decoration: none;
                font-weight: 600;
                font-size: 14px;
                transition: var(--transition);
                border: 2px solid rgba(255, 255, 255, 0.2);
                display: inline-flex;
                align-items: center;
                gap: 6px;
                box-shadow: var(--shadow-sm);
                z-index: 10;
            }
            
            .portal-home-button:hover {
                background: linear-gradient(135deg, var(--primary-dark), var(--primary-color));
                transform: translateY(-2px);
                box-shadow: var(--shadow-lg);
                border-color: rgba(255, 255, 255, 0.4);
            }

            .header h1 {
                font-size: 2.2em;
                margin: 0 0 10px 0;
                color: var(--text-primary);
                font-weight: 700;
            }
            
            .header-subtitle {
                color: var(--text-secondary);
                font-size: 1.1em;
                font-weight: 500;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 0 20px;
            }
            
            /* === タブナビゲーション === */
            .view-selector {
                background: white;
                border-radius: var(--border-radius);
                padding: 20px;
                margin-bottom: 24px;
                box-shadow: var(--shadow-sm);
            }
            
            .view-tabs {
                display: flex;
                gap: 8px;
                justify-content: center;
                flex-wrap: wrap;
            }
            
            .view-tab {
                background: var(--text-light);
                border: 2px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px 20px;
                cursor: pointer;
                transition: var(--transition);
                font-weight: 600;
                font-size: 14px;
                color: var(--text-secondary);
                user-select: none;
            }
            
            .view-tab:hover {
                background: #E5E7EB;
                transform: translateY(-1px);
                box-shadow: var(--shadow-sm);
            }
            
            .view-tab.active {
                background: var(--primary-color);
                color: white;
                border-color: var(--primary-color);
                box-shadow: var(--shadow-md);
            }
            
            /* === コンテンツエリア === */
            .view-content {
                display: none;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            .view-content.active {
                display: block;
                opacity: 1;
                animation: fadeIn 0.3s ease;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            /* === 統一メトリクスカードシステム === */
            .grid-container {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: var(--card-gap);
                margin: 24px 0;
            }
            
            .metric-card {
                background: white;
                border-radius: var(--border-radius);
                padding: var(--card-padding);
                box-shadow: var(--shadow-sm);
                border: 1px solid #E5E7EB;
                transition: var(--transition);
                position: relative;
                overflow: hidden;
                min-height: 140px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            
            .metric-card:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-lg);
            }
            
            /* === 統一カラーインジケーター === */
            .metric-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: #E5E7EB;
            }
            
            .metric-card.success::before { background: var(--success-color); }
            .metric-card.warning::before { background: var(--warning-color); }
            .metric-card.danger::before { background: var(--danger-color); }
            .metric-card.info::before { background: var(--info-color); }
            
            /* === 統一テキストスタイル === */
            .metric-title {
                font-size: 1.0em;
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: 16px;
                line-height: 1.3;
            }
            
            .metric-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 14px;
                margin-bottom: 8px;
                line-height: 1.4;
            }
            
            .metric-row span:first-child {
                color: var(--text-secondary);
                font-weight: 500;
            }
            
            .metric-value-row {
                font-weight: 700;
                color: var(--text-primary);
                font-size: 15px;
            }
            
            .achievement-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 16px;
                font-weight: 700;
                margin-top: 12px;
                padding-top: 8px;
                border-top: 1px solid #F3F4F6;
            }
            
            .achievement-row span:first-child {
                color: var(--text-secondary);
                font-size: 14px;
            }
            
            /* === パフォーマンス別カラー === */
            .metric-card.success .achievement-row span:last-child {
                color: var(--success-color);
            }
            
            .metric-card.warning .achievement-row span:last-child {
                color: var(--warning-color);
            }
            
            .metric-card.danger .achievement-row span:last-child {
                color: var(--danger-color);
            }
            
            .metric-card.info .achievement-row span:last-child {
                color: var(--info-color);
            }
            
            /* === プログレスバー === */
            .progress-bar {
                background-color: #F3F4F6;
                border-radius: 4px;
                height: 6px;
                margin-top: 8px;
                overflow: hidden;
            }
            
            .progress-fill {
                height: 100%;
                border-radius: 4px;
                transition: width 0.3s ease;
            }
            
            .metric-card.success .progress-fill { background: var(--success-color); }
            .metric-card.warning .progress-fill { background: var(--warning-color); }
            .metric-card.danger .progress-fill { background: var(--danger-color); }
            .metric-card.info .progress-fill { background: var(--info-color); }
            
            /* === サマリー統計 === */
            .summary {
                background: white;
                padding: 24px;
                border-radius: var(--border-radius);
                margin-bottom: 24px;
                box-shadow: var(--shadow-sm);
                text-align: center;
            }
            
            .summary h2 {
                color: var(--text-primary);
                margin-bottom: 20px;
                font-size: 1.4em;
                font-weight: 700;
            }
            
            .summary-stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            
            .stat-item {
                padding: 16px;
                background: #F9FAFB;
                border-radius: 8px;
                border: 1px solid #F3F4F6;
            }
            
            .stat-value {
                font-size: 24px;
                font-weight: 700;
                color: var(--primary-color);
                margin-bottom: 4px;
            }
            
            .stat-label {
                font-size: 14px;
                color: var(--text-secondary);
                font-weight: 500;
            }
            
            /* === 年度比較カード === */
            .yearly-comparison-card {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                color: white;
                border-radius: 16px;
                padding: 32px;
                margin-bottom: 32px;
                box-shadow: var(--shadow-lg);
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
                margin-bottom: 24px;
                position: relative;
                z-index: 1;
            }
            
            .yearly-card-icon {
                font-size: 32px;
                margin-right: 16px;
            }
            
            .yearly-card-title {
                font-size: 20px;
                font-weight: 700;
            }
            
            .yearly-card-subtitle {
                font-size: 14px;
                opacity: 0.9;
                margin-top: 4px;
            }
            
            .yearly-comparison-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 24px;
                position: relative;
                z-index: 1;
            }
            
            .yearly-metric {
                text-align: center;
                padding: 20px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: var(--border-radius);
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
                font-weight: 700;
                margin-bottom: 4px;
            }
            
            .yearly-metric-period {
                font-size: 11px;
                opacity: 0.8;
            }
            
            .yearly-comparison-result {
                background: rgba(255, 255, 255, 0.2);
                border-radius: var(--border-radius);
                padding: 20px;
                text-align: center;
                position: relative;
                z-index: 1;
            }
            
            .yearly-change-value {
                font-size: 36px;
                font-weight: 700;
                margin-bottom: 8px;
            }
            
            .yearly-change-label {
                font-size: 14px;
                opacity: 0.9;
            }
            
            /* === ハイスコアランキング === */
            .stats-highlight {
                background: #F9FAFB;
                padding: 24px;
                border-radius: var(--border-radius);
                margin-bottom: 32px;
                text-align: center;
                border: 1px solid #F3F4F6;
            }
            
            .stats-highlight h2 {
                margin: 0 0 8px 0;
                color: var(--text-primary);
                font-size: 1.5em;
                font-weight: 700;
            }
            
            .ranking-section {
                margin-bottom: 32px;
            }
            
            .ranking-card {
                background: white;
                border: 2px solid #E5E7EB;
                border-radius: var(--border-radius);
                padding: 24px;
                margin-bottom: 16px;
                box-shadow: var(--shadow-sm);
                transition: var(--transition);
            }
            
            .ranking-card:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-md);
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
                gap: 12px;
                margin-bottom: 12px;
            }
            
            .medal {
                font-size: 2em;
            }
            
            .rank-label {
                font-weight: 600;
                color: var(--text-secondary);
                font-size: 14px;
            }
            
            .dept-name {
                font-size: 1.4em;
                font-weight: 700;
                margin-bottom: 12px;
                color: var(--text-primary);
            }
            
            .score-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            
            .achievement {
                color: var(--text-secondary);
                font-size: 1.0em;
                font-weight: 500;
            }
            
            .score-value {
                font-size: 2.2em;
                font-weight: 700;
                color: var(--danger-color);
                text-align: right;
            }
            
            /* === 月別トレンドチャート === */
            .trend-chart {
                background: white;
                border-radius: var(--border-radius);
                padding: 32px;
                margin: 32px 0;
                box-shadow: var(--shadow-sm);
                border: 1px solid #F3F4F6;
            }
            
            .trend-chart h3 {
                margin: 0 0 24px 0;
                color: var(--text-primary);
                font-size: 1.2em;
                font-weight: 600;
            }
            
            #monthlyTrendChart {
                max-width: 100%;
                height: 100%;
            }
            
            /* === 分析セクション === */
            .analysis-section {
                background: white;
                border-radius: var(--border-radius);
                padding: 32px;
                box-shadow: var(--shadow-sm);
                margin-bottom: 32px;
                border: 1px solid #F3F4F6;
            }
            
            .analysis-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 24px;
            }
            
            .analysis-card {
                background: #F9FAFB;
                border-left: 4px solid var(--primary-color);
                border-radius: var(--border-radius);
                padding: 20px;
                border: 1px solid #F3F4F6;
            }
            
            .analysis-card.improvement {
                border-left-color: var(--success-color);
                background: rgba(16, 185, 129, 0.05);
            }
            
            .analysis-card.concern {
                border-left-color: var(--warning-color);
                background: rgba(245, 158, 11, 0.05);
            }
            
            .analysis-card.action {
                border-left-color: var(--info-color);
                background: rgba(59, 130, 246, 0.05);
            }
            
            .analysis-card h3 {
                margin-top: 0;
                margin-bottom: 16px;
                font-size: 1.1em;
                font-weight: 600;
            }
            
            .analysis-card ul {
                margin: 0;
                padding-left: 20px;
                line-height: 1.6;
            }
            
            .analysis-card li {
                margin-bottom: 8px;
                font-size: 14px;
            }
            
            /* === フッター === */
            .footer {
                text-align: center;
                margin-top: 48px;
                color: var(--text-muted);
                font-size: 12px;
                padding: 24px;
                background: white;
                border-radius: var(--border-radius);
                box-shadow: var(--shadow-sm);
            }
            
            /* === レスポンシブ対応 === */
            @media (max-width: 768px) {
                .container {
                    padding: 0 12px;
                }
                
                .header {
                    padding: 60px 16px 20px 16px;
                }
                
                .portal-home-button {
                    top: 15px;
                    left: 15px;
                    padding: 8px 16px;
                    font-size: 12px;
                }
                
                .info-button {
                    top: 15px;
                    right: 15px;
                }
                
                .header h1 {
                    font-size: 1.8em;
                }
                
                .view-tabs {
                    flex-direction: column;
                    gap: 8px;
                }
                
                .view-tab {
                    padding: 12px 16px;
                    font-size: 13px;
                }
                
                .grid-container {
                    grid-template-columns: 1fr;
                    gap: 12px;
                }
                
                .metric-card {
                    padding: 16px;
                    min-height: 120px;
                }
                
                .yearly-comparison-card {
                    padding: 24px;
                }
                
                .yearly-comparison-grid {
                    grid-template-columns: 1fr;
                    gap: 16px;
                }
                
                .summary-stats {
                    grid-template-columns: 1fr;
                    gap: 12px;
                }
                
                .analysis-grid {
                    grid-template-columns: 1fr;
                }
                
                .trend-chart {
                    padding: 20px;
                }
                
                .ranking-card {
                    padding: 20px;
                }
            }

            @media (max-width: 480px) {
                .header {
                    padding-top: 70px;
                }
                
                .portal-home-button {
                    top: 10px;
                    left: 10px;
                    padding: 6px 12px;
                    font-size: 11px;
                }

                .header h1 {
                    font-size: 1.5em;
                }
                
                .metric-card {
                    padding: 14px;
                }
                
                .yearly-comparison-card {
                    padding: 20px;
                }
                
                .yearly-metric {
                    padding: 16px;
                }
                
                .yearly-metric-value {
                    font-size: 24px;
                }
                
                .score-value {
                    font-size: 1.8em;
                }
                
                .dept-name {
                    font-size: 1.2em;
                }
            }
            """
        
        # 情報パネル用の追加CSS
        info_panel_css = """
            /* === 情報ボタン === */
            .info-button {
                position: absolute;
                top: 20px;
                right: 20px;
                background: var(--primary-color);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: var(--transition);
                box-shadow: var(--shadow-sm);
            }
            
            .info-button:hover {
                background: var(--primary-dark);
                transform: translateY(-2px);
                box-shadow: var(--shadow-md);
            }
            
            /* === 情報パネルオーバーレイ === */
            .info-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                z-index: 999;
                animation: fadeIn 0.3s ease;
            }
            
            /* === 情報パネル === */
            .info-panel {
                display: none;
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 90%;
                max-width: 800px;
                max-height: 80vh;
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
                z-index: 1000;
                overflow: hidden;
                animation: slideIn 0.3s ease;
            }
            
            @keyframes slideIn {
                from {
                    transform: translate(-50%, -45%);
                    opacity: 0;
                }
                to {
                    transform: translate(-50%, -50%);
                    opacity: 1;
                }
            }
            
            .info-panel-header {
                background: var(--primary-color);
                color: white;
                padding: 20px 24px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .info-panel-header h2 {
                margin: 0;
                font-size: 1.4em;
                font-weight: 700;
            }
            
            .close-button {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                transition: background 0.2s;
            }
            
            .close-button:hover {
                background: rgba(255, 255, 255, 0.2);
            }
            
            .info-panel-content {
                padding: 24px;
                overflow-y: auto;
                max-height: calc(80vh - 80px);
            }
            
            .info-section {
                margin-bottom: 32px;
            }
            
            .info-section h3 {
                color: var(--text-primary);
                margin-bottom: 16px;
                font-size: 1.2em;
                font-weight: 600;
                border-bottom: 2px solid #E5E7EB;
                padding-bottom: 8px;
            }
            
            /* === 評価基準グリッド === */
            .criteria-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 16px;
            }
            
            .criteria-card {
                background: #F9FAFB;
                border-radius: 8px;
                padding: 16px;
                border: 1px solid #E5E7EB;
            }
            
            .criteria-card h4 {
                margin: 0 0 12px 0;
                color: var(--text-primary);
                font-size: 1em;
                font-weight: 600;
            }
            
            .criteria-card ul {
                margin: 0;
                padding-left: 0;
                list-style: none;
            }
            
            .criteria-card li {
                margin-bottom: 8px;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            /* === バッジ === */
            .badge {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                color: white;
                min-width: 60px;
                text-align: center;
            }
            
            .badge.success { background: var(--success-color); }
            .badge.info { background: var(--info-color); }
            .badge.warning { background: var(--warning-color); }
            .badge.danger { background: var(--danger-color); }
            
            /* === スコア計算説明セクション === */
            .score-calculation-section {
                background: #FEF3C7;
                border-radius: 12px;
                padding: 24px;
                border: 1px solid #FCD34D;
                margin-bottom: 32px;
            }
            
            .score-explanation {
                margin-top: 16px;
            }
            
            .score-intro {
                font-size: 15px;
                color: var(--text-primary);
                margin-bottom: 24px;
                font-weight: 500;
            }
            
            .score-component {
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 16px;
                border: 1px solid #E5E7EB;
                box-shadow: var(--shadow-sm);
            }
            
            .score-component h4 {
                margin: 0 0 16px 0;
                color: var(--primary-color);
                font-size: 1.1em;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .score-detail {
                margin-left: 16px;
            }
            
            .score-detail p {
                margin: 8px 0;
                font-size: 14px;
                color: var(--text-secondary);
            }
            
            .score-detail code {
                display: inline-block;
                background: #F3F4F6;
                padding: 4px 12px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                color: #374151;
                border: 1px solid #E5E7EB;
                margin: 8px 0;
            }
            
            .score-breakdown {
                margin-top: 16px;
                background: #F9FAFB;
                border-radius: 6px;
                padding: 16px;
            }
            
            .score-breakdown h5 {
                margin: 0 0 12px 0;
                font-size: 14px;
                font-weight: 600;
                color: var(--text-primary);
            }
            
            .score-breakdown ul {
                margin: 0;
                padding-left: 20px;
            }
            
            .score-breakdown > ul > li {
                margin-bottom: 12px;
                font-size: 14px;
                color: var(--text-primary);
            }
            
            .score-breakdown ul ul {
                margin-top: 4px;
                margin-bottom: 0;
            }
            
            .score-breakdown ul ul li {
                margin-bottom: 4px;
                font-size: 13px;
                color: var(--text-secondary);
            }
            
            .total-score-summary {
                background: var(--primary-color);
                color: white;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                margin-top: 24px;
            }
            
            .total-score-summary h4 {
                margin: 0 0 8px 0;
                color: white;
                font-size: 1.1em;
                font-weight: 700;
            }
            
            .score-note {
                margin: 0;
                font-size: 14px;
                opacity: 0.9;
            }
            
            /* === グレードシステム === */
            .grade-system {
                background: #F9FAFB;
                border-radius: 8px;
                padding: 16px;
                margin-top: 16px;
            }
            
            .grade-system h5 {
                margin: 0 0 12px 0;
                font-size: 14px;
                font-weight: 600;
                color: var(--text-primary);
            }
            
            .grade-list {
                margin: 0;
                padding: 0;
                list-style: none;
            }
            
            .grade-list li {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 8px;
                font-size: 14px
            }
        
            .grade-badge {
                display: inline-block;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                text-align: center;
                line-height: 24px;
                font-weight: 700;
                font-size: 14px;
                color: white;
            }
            
            .grade-badge.grade-s {
                background: linear-gradient(135deg, #FFD700, #FFA500);
                box-shadow: 0 2px 4px rgba(255, 215, 0, 0.4);
            }
            
            .grade-badge.grade-a {
                background: #DC143C;
            }
            
            .grade-badge.grade-b {
                background: #4169E1;
            }
            
            .grade-badge.grade-c {
                background: #32CD32;
            }
            
            .grade-badge.grade-d {
                background: #708090;
            }
            
            .calculation-note {
                background: #FEF3C7;
                border-radius: 6px;
                padding: 12px;
                margin-top: 12px;
                border: 1px solid #FCD34D;
            }
            
            .calculation-note p {
                margin: 0 0 8px 0;
                font-weight: 600;
                color: #92400E;
            }
            
            .calculation-note ul {
                margin: 0;
                padding-left: 20px;
            }
            
            .calculation-note li {
                font-size: 13px;
                color: #78350F;
            }
            
            /* === 用語リスト === */
            .term-list {
                background: #F9FAFB;
                border-radius: 8px;
                padding: 20px;
                margin: 0;
            }
            
            .term-list dt {
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: 4px;
                font-size: 15px;
            }
            
            .term-list dd {
                color: var(--text-secondary);
                margin: 0 0 16px 0;
                padding-left: 16px;
                font-size: 14px;
                line-height: 1.6;
            }
            
            /* === 計算式リスト === */
            .formula-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            
            .formula-item {
                background: #F9FAFB;
                border-radius: 8px;
                padding: 12px 16px;
                border: 1px solid #E5E7EB;
            }
            
            .formula-item strong {
                display: block;
                color: var(--text-primary);
                margin-bottom: 4px;
                font-size: 14px;
            }
            
            .formula-item code {
                display: block;
                background: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                color: #374151;
                border: 1px solid #E5E7EB;
            }
            
            /* === ヒントリスト === */
            .tips-list {
                background: #F0F9FF;
                border-radius: 8px;
                padding: 20px;
                margin: 0;
                border: 1px solid #BFDBFE;
            }
            
            .tips-list li {
                color: #1E40AF;
                margin-bottom: 12px;
                padding-left: 8px;
                font-size: 14px;
                line-height: 1.6;
            }
            
            /* === レスポンシブ対応（情報パネル） === */
            @media (max-width: 768px) {
                .info-button {
                    top: 60px;
                    right: 16px;
                    padding: 6px 12px;
                    font-size: 13px;
                }
                
                .info-panel {
                    width: 95%;
                    max-height: 90vh;
                }
                
                .info-panel-content {
                    padding: 16px;
                    max-height: calc(90vh - 70px);
                }
                
                .criteria-grid {
                    grid-template-columns: 1fr;
                }
                
                .formula-item code {
                    font-size: 11px;
                    padding: 6px 8px;
                    word-break: break-all;
                }
                
                .score-component {
                    padding: 16px;
                }
                
                .score-breakdown {
                    padding: 12px;
                }
            }
            """
        
        # 既存のCSSと情報パネル用CSSを結合して返す
        return base_css + info_panel_css

    def _upload_to_github(self, html_content: str) -> Tuple[bool, str]:
        """GitHubにHTMLファイルをアップロード"""
        try:
            self._upload_file('docs/index.html', html_content, skip_ci=False)
            return True, "手術分析ダッシュボードの公開が完了しました"
        except Exception as e:
            logger.error(f"GitHubアップロードエラー: {e}")
            return False, str(e)

    def _upload_file(self, filepath: str, content: str, skip_ci: bool = False) -> Tuple[bool, str]:
        """単一ファイルをGitHubにアップロード"""
        try:
            headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github.v3+json"}
            get_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{filepath}"
            get_response = requests.get(get_url, headers=headers)
            sha = get_response.json().get('sha') if get_response.status_code == 200 else None
            
            content_encoded = base64.b64encode(content.encode()).decode()
            
            commit_message = f"Update integrated surgery dashboard - {datetime.now().strftime('%Y/%m/%d %H:%M')}"
            if skip_ci:
                commit_message += " [ci skip]"
                
            data = {"message": commit_message, "content": content_encoded, "branch": self.branch}
            if sha:
                data["sha"] = sha
            
            put_response = requests.put(get_url, json=data, headers=headers)
            
            if put_response.status_code in [200, 201]:
                return True, f"Successfully uploaded: {filepath}"
            else:
                return False, f"Upload failed: {put_response.json().get('message', 'Unknown error')}"
        except Exception as e:
            logger.error(f"ファイルアップロードエラー: {e}")
            return False, str(e)
            
    def _ensure_github_pages_workflow(self, skip_ci: bool = False):
        """GitHub Pagesワークフローを確認・作成"""
        workflow_content = """name: Deploy to GitHub Pages
on:
  push:
    branches: [ main ]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: "pages"
  cancel-in-progress: false
jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Pages
        uses: actions/configure-pages@v5
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          # このリポジトリのルートディレクトリをアップロード対象にする
          path: '.'

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""


        workflow_path = ".github/workflows/pages.yml"
        self._upload_file(workflow_path, workflow_content, skip_ci=skip_ci)
        logger.info("GitHub Pagesワークフロー設定完了")

    def get_public_url(self) -> str:
        """公開URLを取得"""
        return f"https://{self.repo_owner}.github.io/{self.repo_name}/"


def create_surgery_github_publisher_interface():
    """手術分析GitHub公開インターフェース（4タブ手術分析ダッシュボード版）"""
    try:
        df = st.session_state.get('processed_df', pd.DataFrame())
        target_dict = st.session_state.get('target_dict', {})

        if df.empty or not target_dict:
            st.sidebar.info("📊 データ読み込み後に手術分析ダッシュボード公開が利用可能になります")
            return

        st.sidebar.markdown("---")
        st.sidebar.header("🚀 手術分析ダッシュボード公開")

        saved_settings = load_github_settings()

        with st.sidebar.expander("🔧 GitHub設定", expanded=False):
            github_token = st.text_input("GitHub Token", type="password", help="GitHubのPersonal Access Token (repo権限が必要)", key="surgery_github_token")
            repo_owner = st.text_input("リポジトリオーナー", value=saved_settings.get('repo_owner', 'Genie-Scripts'), help="GitHubユーザー名または組織名", key="surgery_repo_owner")
            repo_name = st.text_input("リポジトリ名", value=saved_settings.get('repo_name', 'Streamlit-OR-Dashboard'), help="公開用リポジトリ名", key="surgery_repo_name")
            branch = st.selectbox("ブランチ", ["main", "master", "gh-pages"], index=0, key="surgery_branch")
            if st.button("🔌 接続テスト", key="test_connection"):
                if github_token and repo_owner and repo_name:
                    success, message = test_github_connection(github_token, repo_owner, repo_name)
                    if success:
                        st.success(f"✅ {message}")
                        save_github_settings(repo_owner, repo_name, branch)
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("すべての項目を入力してください")

        st.sidebar.markdown("**⚙️ 公開設定**")
        period = st.sidebar.selectbox("評価期間", ["直近4週", "直近8週", "直近12週"], index=2, key="surgery_publish_period")
        
        # ★★ Google Analytics IDの入力欄を追加 ★★
        google_analytics_id = st.sidebar.text_input(
            "Google Analytics ID (任意)",
            key="surgery_ga_id",
            help="例: G-K6XTL1DM13"
        )

        publisher = SurgeryGitHubPublisher(github_token, repo_owner, repo_name, branch)

        def _generate_html():
            analysis_base_date = SessionManager.get_analysis_base_date()
            if analysis_base_date is None:
                analysis_base_date = df['手術実施日_dt'].max() if '手術実施日_dt' in df.columns and not df.empty else datetime.now()

            # ★★ GA_IDを渡す ★★
            return publisher.generate_dashboard_html_content(df, target_dict, period, analysis_base_date, google_analytics_id)

        st.sidebar.markdown("**📤 公開アクション**")

        if st.sidebar.button("💾 ローカル保存のみ", key="local_save_button"):
            with st.spinner("HTMLを生成して保存中..."):
                html_content = _generate_html()
                if html_content:
                    save_success, save_message = publisher.save_html_locally(html_content)
                    if save_success: st.sidebar.success(f"✅ {save_message}")
                    else: st.sidebar.error(f"❌ {save_message}")
                else:
                    st.sidebar.error("❌ HTMLの生成に失敗しました。")

        save_on_publish = st.sidebar.checkbox("公開時にローカルにも保存する", value=True)

        if st.sidebar.button("🚀 GitHubに公開", type="primary", key="publish_button"):
            if not github_token or not repo_owner or not repo_name:
                st.sidebar.error("GitHub設定の全項目を入力してください。")
            else:
                with st.spinner("ダッシュボードを生成・公開中..."):
                    html_content = _generate_html()
                    if not html_content:
                        st.sidebar.error("❌ HTMLの生成に失敗しました。")
                    else:
                        # ★★ GA_IDを渡す ★★
                        success, message = publisher.publish_surgery_dashboard(df, target_dict, SessionManager.get_analysis_base_date() or datetime.now(), period, google_analytics_id=google_analytics_id)

                        if success:
                            st.sidebar.success(f"✅ {message}")
                            save_github_settings(repo_owner, repo_name, branch)

                            if save_on_publish:
                                save_success, save_message = publisher.save_html_locally(html_content)
                                if save_success: st.sidebar.info(f"ℹ️ {save_message}")
                                else: st.sidebar.warning(f"⚠️ ローカル保存に失敗: {save_message}")
                        else:
                            st.sidebar.error(f"❌ 公開失敗: {message}")

        with st.sidebar.expander("📚 使い方"):
            st.markdown("""
            **💾 ローカル保存のみ:**
            生成された `index.html` をこのアプリの `docs` フォルダに保存します。

            **🚀 GitHubに公開:**
            `index.html` を指定されたGitHubリポジトリにアップロードし、Webページとして公開します。
            - **「公開時にローカルにも保存する」** にチェックを入れると、公開と同時にローカルにもファイルが保存されます。
            """)

    except Exception as e:
        logger.error(f"手術GitHub公開インターフェースエラー: {e}", exc_info=True)
        st.sidebar.error("GitHub公開機能でエラーが発生しました")

# === 既存関数（変更なし） ===

def test_github_connection(github_token: str, repo_owner: str, repo_name: str) -> Tuple[bool, str]:
    """GitHub接続テスト"""
    try:
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # リポジトリの存在確認
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            repo_info = response.json()
            return True, f"接続成功: {repo_info.get('full_name', 'Unknown')}"
        elif response.status_code == 404:
            return False, "リポジトリが見つかりません"
        elif response.status_code == 401:
            return False, "認証に失敗しました。トークンを確認してください"
        else:
            return False, f"接続エラー: {response.status_code}"
            
    except Exception as e:
        return False, f"接続テストエラー: {str(e)}"


def save_github_settings(repo_owner: str, repo_name: str, branch: str):
    """GitHub設定をセッションに保存"""
    try:
        st.session_state.surgery_github_settings = {
            'repo_owner': repo_owner,
            'repo_name': repo_name, 
            'branch': branch,
            'saved_at': datetime.now().isoformat()
        }
        logger.info("GitHub設定を保存しました")
    except Exception as e:
        logger.error(f"GitHub設定保存エラー: {e}")


def load_github_settings() -> Dict[str, str]:
    """保存されたGitHub設定を読み込み"""
    try:
        settings = st.session_state.get('surgery_github_settings', {})
        
        if settings and 'saved_at' in settings:
            # 設定の有効期限チェック（7日間）
            saved_at = datetime.fromisoformat(settings['saved_at'])
            if (datetime.now() - saved_at).days < 7:
                return settings
        
        return {}
        
    except Exception as e:
        logger.error(f"GitHub設定読み込みエラー: {e}")
        return {}