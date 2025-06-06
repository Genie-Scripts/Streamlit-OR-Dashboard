# department_ranking.py (X軸範囲を明示的に計算・設定 - 再修正)
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import style_config as sc # スタイル定義をインポート

# --- 累積実績/達成率 計算・描画関数 (変更なし) ---
def calculate_cumulative_cases(df_period, entity_name, weekly_target):
    """累積実績件数を計算する関数 (週単位の表示修正)"""
    df = df_period.copy()
    output_cols = ['週', '週次実績', '累積実績件数', '累積目標件数']
    
    if entity_name != "全診療科":
        df_filtered = df[df['実施診療科'] == entity_name]
    else:
        df_filtered = df
        
    df_gas = df_filtered[
        df_filtered['麻酔種別'].str.contains("全身麻酔", na=False) & 
        df_filtered['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()
    
    if df_gas.empty:
        return pd.DataFrame(columns=output_cols)
    
    df_gas = df_gas.sort_values('手術実施日_dt')
    
    # 修正: 週単位でまとめる（月曜始まり）- 明示的な方法で
    df_gas['週'] = df_gas['手術実施日_dt'] - pd.to_timedelta(df_gas['手術実施日_dt'].dt.dayofweek, unit='d')
    df_gas['週'] = df_gas['週'].dt.normalize()  # 時間部分を削除し、日付だけに
    
    weekly_actual = df_gas.groupby('週', as_index=False).size().rename(columns={'size': '週次実績'})
    
    try:
        min_week = df_gas['週'].min()
        max_week = df_gas['週'].max()
        
        if min_week == max_week and not weekly_actual.empty:
            all_weeks = pd.to_datetime([min_week])
        elif min_week < max_week:
            # 週の範囲を生成 (月曜日始まり)
            all_weeks = pd.date_range(start=min_week, end=max_week, freq='W-MON')
        else:
            return pd.DataFrame(columns=output_cols)
    except Exception as e:
        print(f"Error generating date range in CalcCumCases: {e}")
        return pd.DataFrame(columns=output_cols)
    
    weekly_df = pd.DataFrame({'週': all_weeks})
    weekly_df = pd.merge(weekly_df, weekly_actual, on='週', how='left').fillna(0)
    weekly_df = weekly_df.sort_values('週')
    weekly_df['週次実績'] = weekly_df['週次実績'].astype(int)
    weekly_df['累積実績件数'] = weekly_df['週次実績'].cumsum()
    weekly_df['経過週'] = np.arange(len(weekly_df)) + 1
    weekly_df['累積目標件数'] = weekly_df['経過週'] * weekly_target
    
    return weekly_df[output_cols]

def plot_cumulative_cases(cumulative_df, entity_name):
    # ... (内容は変更なし) ...
    fig = go.Figure(); required_cols = ['週', '累積実績件数', '累積目標件数']
    if not all(col in cumulative_df.columns for col in required_cols) or cumulative_df.empty: fig.update_layout(title=f"{entity_name} - 累積データ不足"); return fig
    fig.add_trace(go.Scatter(x=cumulative_df['週'], y=cumulative_df['累積実績件数'], mode='lines+markers', name='累積実績', line=dict(color=sc.PRIMARY_COLOR, width=2), marker=sc.PRIMARY_MARKER))
    if cumulative_df['累積目標件数'].sum() > 0: fig.add_trace(go.Scatter(x=cumulative_df['週'], y=cumulative_df['累積目標件数'], mode='lines', name='累積目標', line=sc.TARGET_LINE_STYLE)); all_y_values = pd.concat([cumulative_df['累積実績件数'], cumulative_df['累積目標件数']]).dropna()
    else: all_y_values = cumulative_df['累積実績件数'].dropna()
    y_max = all_y_values.max() if not all_y_values.empty else 10; y_max_display = max(y_max * 1.1, 10); y_axis_range = [0, y_max_display]
    fig.update_layout(**sc.LAYOUT_DEFAULTS); fig.update_layout(title=f"{entity_name} - 累積実績 vs 目標 推移 (今年度週次)", xaxis_title="週 (月曜日開始)", yaxis_title="累積件数", yaxis=dict(range=y_axis_range), xaxis=dict(tickformat="%Y-%m-%d")); return fig

# --- 目標達成率 計算関数 (変更なし) ---
def calculate_department_achievement_rates(df_period, target_dict):
    """診療科ごとの目標達成率を計算する関数 (改善版)"""
    if '手術実施日_dt' not in df_period.columns:
        raise ValueError("Input DataFrame must contain '手術実施日_dt' column.")
    
    # 全身麻酔(20分以上)データのみを抽出
    df_gas = df_period[
        df_period['麻酔種別'].str.contains("全身麻酔", na=False) &
        df_period['麻酔種別'].str.contains("20分以上", na=False)
    ].copy()
    
    # データがない場合は空のDataFrameを返す
    if df_gas.empty:
        empty_result = pd.DataFrame(columns=['診療科', '実績件数', '期間内目標件数', '達成率(%)'])
        empty_summary = pd.DataFrame(columns=['サマリー', '診療科数', '割合(%)'])
        return empty_result, empty_summary
    
    # 期間情報の取得（データの最小日、最大日からチェック）
    actual_start_date = df_gas['手術実施日_dt'].min()
    actual_end_date = df_gas['手術実施日_dt'].max()
    
    # 日付型チェック - どちらもNoneでないことを確認
    if actual_start_date is None or actual_end_date is None:
        empty_result = pd.DataFrame(columns=['診療科', '実績件数', '期間内目標件数', '達成率(%)'])
        empty_summary = pd.DataFrame(columns=['サマリー', '診療科数', '割合(%)'])
        return empty_result, empty_summary
    
    # 期間の日数と週数を計算
    period_days = (actual_end_date - actual_start_date).days + 1
    weeks_in_period = period_days / 7.0
    
    # 診療科ごとの件数をカウント
    dept_counts = df_gas.groupby('実施診療科').size().reset_index(name='実績件数')
    
    # 結果格納用リスト
    result = []
    
    # 各診療科の目標と実績を比較
    for _, row in dept_counts.iterrows():
        dept = row['実施診療科']
        actual_count = row['実績件数']
        
        # 目標値の取得と期間中の目標件数計算
        if dept in target_dict and weeks_in_period > 0:
            weekly_target = target_dict[dept]
            target_count_period = weekly_target * weeks_in_period
            
            # 目標件数がゼロ以上なら達成率を計算
            if target_count_period > 0:
                achievement_rate = (actual_count / target_count_period) * 100
            else:
                achievement_rate = 0
                
            result.append({
                '診療科': dept,
                '実績件数': actual_count,
                '期間内目標件数': round(target_count_period, 1),
                '達成率(%)': round(achievement_rate, 1)
            })
        elif dept in target_dict:
            # weeks_in_periodが0以下の場合（異常値）
            result.append({
                '診療科': dept,
                '実績件数': actual_count,
                '期間内目標件数': 0.0,
                '達成率(%)': 0.0
            })
        else:
            # 目標が設定されていない診療科（オプション）
            # 診療科の表示が必要なら以下をコメント解除
            # result.append({
            #     '診療科': dept,
            #     '実績件数': actual_count,
            #     '期間内目標件数': 0.0,
            #     '達成率(%)': 0.0
            # })
            pass
    
    # 結果をDataFrameに変換
    result_df = pd.DataFrame(result)
    
    # サマリー情報（達成状況の総括）
    summary_df = pd.DataFrame(columns=['サマリー', '診療科数', '割合(%)'])
    
    if not result_df.empty:
        # 達成率順にソート
        result_df = result_df.sort_values('達成率(%)', ascending=False).reset_index(drop=True)
        
        # 達成率グループごとのカウント
        achieved = len(result_df[result_df['達成率(%)'] >= 100])
        almost = len(result_df[(result_df['達成率(%)'] >= 80) & (result_df['達成率(%)'] < 100)])
        low = len(result_df[result_df['達成率(%)'] < 80])
        total_depts = len(result_df)
        
        # サマリーデータフレーム作成
        if total_depts > 0:
            summary_data = {
                'サマリー': ['目標達成 (100%以上)', '達成率良好 (80-99%)', '達成率不足 (80%未満)', '合計'],
                '診療科数': [achieved, almost, low, total_depts],
                '割合(%)': [
                    round(achieved/total_depts*100, 1),
                    round(almost/total_depts*100, 1),
                    round(low/total_depts*100, 1),
                    100.0
                ]
            }
            summary_df = pd.DataFrame(summary_data)
    
    return result_df, summary_df

# --- 目標達成率ランキング グラフ描画関数 (X軸範囲計算を修正) ---
def plot_achievement_ranking(achievement_df, top_n=None):
    """診療科の目標達成率ランキングを横棒グラフで表示 (X軸範囲をデータに基づき計算)"""
    if achievement_df.empty:
        fig = go.Figure(); fig.update_layout(title="ランキングデータがありません", xaxis_title="達成率(%)", yaxis_title="診療科"); return fig

    plot_df = achievement_df.copy()
    plot_df['color'] = plot_df['達成率(%)'].apply(lambda x: 'green' if x >= 100 else ('orange' if x >= 80 else 'red'))
    plot_df_sorted_desc = plot_df.sort_values(by="達成率(%)", ascending=False)
    if top_n is not None and top_n > 0 and len(plot_df_sorted_desc) > top_n: plot_df_to_show = plot_df_sorted_desc.head(top_n)
    else: plot_df_to_show = plot_df_sorted_desc
    plot_df_sorted_asc = plot_df_to_show.sort_values(by="達成率(%)", ascending=True)

    fig = px.bar(plot_df_sorted_asc, y='診療科', x='達成率(%)', color='color', color_discrete_map=sc.RANKING_COLOR_MAP, text='達成率(%)', orientation='h', title=f"診療科別目標達成率ランキング (Top {top_n})" if top_n else "診療科別目標達成率ランキング")
    fig.add_shape(type="line", x0=100, y0=-0.5, x1=100, y1=len(plot_df_to_show) - 0.5, line=dict(color="black", width=1, dash="dash"))

    # --- X軸の範囲を計算 (マージン追加方式) ---
    if not plot_df_to_show.empty:
        data_min = plot_df_to_show['達成率(%)'].min()
        data_max = plot_df_to_show['達成率(%)'].max()
        data_range = data_max - data_min
        margin = data_range * 0.05 # 5%のマージン

        # 最小表示位置: データ最小値 - マージン (ただし0未満にはしない)
        x_min_display = max(0, data_min - margin)
        # 最大表示位置: データ最大値 + マージン (ただし最低110は確保)
        x_max_display = max(data_max + margin, 110)

        x_axis_range = [x_min_display, x_max_display]
    else:
        x_axis_range = [0, 110] # データがない場合のデフォルト
    # --- X軸範囲計算ここまで ---

    # レイアウト更新
    fig.update_layout(**sc.LAYOUT_DEFAULTS)
    fig.update_layout(
        xaxis_title="達成率(%)", yaxis_title="診療科",
        yaxis=dict(tickfont=dict(size=sc.TICK_FONT_SIZE)),
        height=max(300, 35 * len(plot_df_to_show)), showlegend=False,
        title_font_size=sc.TITLE_FONT_SIZE, yaxis_title_font_size=sc.AXIS_LABEL_FONT_SIZE,
    )

    # 計算したX軸範囲を適用
    fig.update_xaxes(range=x_axis_range)

    fig.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
    return fig