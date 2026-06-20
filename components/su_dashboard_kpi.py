# components/su_dashboard_kpi.py （全コード）
from nicegui import ui, app
from config.supabase_config import get_supabase
from components.su_dashboard_logic import fetch_page_pv_data
from themes import THEMES

def build_kpi_ui(is_pc_mode: bool = False):
    """
    KPI・アナリティクス領域を生成する外部コンポーネント（ライト・ダーク対応 ＆ ローディングスピナー付）
    """
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)
    
    try:
        sb = get_supabase()
        total_t_res = sb.table("support_tickets").select("id").eq("status", "unread").execute()
        total_t = len(total_t_res.data or [])
        
        total_n_res = sb.table("timeline_posts").select("id").eq("status", "pending").is_("deleted_at", "null").execute()
        total_n = len(total_n_res.data or [])
        
    except Exception as e:
        print(f"KPI取得エラー: {e}")
        total_t, total_n = "-", "-"

    pv_data = fetch_page_pv_data()
    layout_cls = 'w-full gap-4 items-stretch no-wrap flex-row' if is_pc_mode else 'w-full gap-4 items-stretch flex-col'
    
    with ui.row().classes(layout_cls):
        kpi_container_cls = 'shrink-0 w-full lg:w-[220px] gap-3 justify-between flex-col' if is_pc_mode else 'w-full gap-3 flex-row'
        
        alert_num = 0
        if isinstance(total_t, int) and isinstance(total_n, int):
            alert_num = total_t + total_n
            
        if alert_num > 0:
            alert_card_cls = 'bg-red-50 border-l-4 border-red-500 text-red-800 shadow-md' if is_light else 'bg-red-950/40 border-l-4 border-red-500 text-white shadow-lg'
            alert_label_color = 'text-red-700' if is_light else 'text-red-300'
        else:
            alert_card_cls = 'bg-slate-100 border-l-4 border-slate-300 text-slate-800 shadow-sm' if is_light else 'bg-slate-950/40 border-l-4 border-slate-500 text-white shadow-lg'
            alert_label_color = 'text-slate-600' if is_light else 'text-slate-300'
        
        with ui.column().classes(kpi_container_cls) if is_pc_mode else ui.row().classes(kpi_container_cls):
            with ui.card().classes(f'{alert_card_cls} p-4 rounded-xl flex-grow items-center justify-center h-full'):
                ui.label('要対応アラート').classes(f'text-[10px] {alert_label_color} font-bold tracking-widest mb-1.5')
                ui.label(str(alert_num)).classes('text-3xl font-black')

        chart_width_cls = 'flex-grow' if is_pc_mode else 'w-full'
        axis_color = '#475569' if is_light else '#94a3b8'
        split_line_color = '#e2e8f0' if is_light else '#334155'
        
        # 📊 1. アクティブ推移グラフ
        # ★ 変更: bg-slate-900/50 などの色の分岐を完全に撤廃し、一括で「hibi-glass」に指定します。
        # (これで、テーマ切り替えの瞬間にコンテナ背景だけは0秒で美しくライトカラーに切り替わります)
        with ui.card().classes(f'{chart_width_cls} hibi-glass p-3.5 rounded-xl shadow-lg relative overflow-hidden'):
            
            # (★スピナーやz-indexなどの余計なタグはすべて不要になったため削除して元通りにスッキリさせます)
            with ui.row().classes('w-full justify-between items-center mb-1'):
                with ui.row().classes('items-center gap-1'):
                    ui.icon('trending_up', size='xs', color='cyan-500' if is_light else 'cyan-400')
                    ui.label('アクティブ推移 (過去7日間)').classes('text-[11px] font-bold')
                ui.icon('info', size='xs', color='slate-400' if is_light else 'slate-500').classes('cursor-pointer').tooltip('※アクセス数は各ページのページビュー (PV) の合計値です')
            ui.label('※アクセス数は各ページのページビュー (PV) の合計値です').classes('text-[9px] opacity-60 -mt-2 mb-1.5')
            
            ui.echart({
                'backgroundColor': 'transparent', # ★ 変更: 背景は透明にして、hibi-glassの背景色をそのまま綺麗に透過させます
                'tooltip': {'trigger': 'axis'},
                'grid': {'left': '4%', 'right': '4%', 'bottom': '4%', 'top': '15%', 'containLabel': True},
                'xAxis': {'type': 'category', 'data': ['6日前', '5日前', '4日前', '3日前', '一昨日', '昨日', '今日'], 'axisLabel': {'color': axis_color, 'fontSize': 9}},
                'yAxis': {'type': 'value', 'axisLabel': {'color': axis_color, 'fontSize': 9}, 'splitLine': {'lineStyle': {'color': split_line_color}}},
                'series': [
                    {
                        'name': 'アクセス数', 'type': 'line', 'smooth': True, 'data': [145, 152, 148, 170, 165, 188, 202], 
                        'itemStyle': {'color': '#06b6d4'}, 'areaStyle': {'color': 'rgba(6, 182, 212, 0.2)'}, 'symbolSize': 6
                    }
                ]
            }).classes('w-full h-28') # ★ 変更: 独自クラス（kpi-chart）も不要なため削除

        # 📊 2. ページ別アクセス内訳
        # ★ 変更: こちらも「hibi-glass」に指定
        with ui.card().classes(f'{chart_width_cls} hibi-glass p-3.5 rounded-xl shadow-lg relative overflow-hidden'):
            
            with ui.row().classes('items-center gap-1 mb-2'):
                ui.icon('bar_chart', size='xs', color='blue-500' if is_light else 'blue-400')
                ui.label('ページ別アクセス内訳 (本日分)').classes('text-[11px] font-bold')
            
            ui.echart({
                'backgroundColor': 'transparent', # ★ 透明に
                'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
                'grid': {'left': '4%', 'right': '4%', 'bottom': '4%', 'top': '15%', 'containLabel': True},
                'xAxis': {'type': 'category', 'data': pv_data['labels'], 'axisLabel': {'color': axis_color, 'fontSize': 8}},
                'yAxis': {'type': 'value', 'axisLabel': {'color': axis_color, 'fontSize': 9}, 'splitLine': {'lineStyle': {'color': split_line_color}}},
                'series': [
                    {
                        'name': 'PV', 'type': 'bar', 'data': pv_data['values'], 
                        'itemStyle': {'color': '#3b82f6'}, 'barWidth': '55%'
                    }
                ]
            }).classes('w-full h-28')