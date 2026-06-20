# components/su_dashboard_logs.py
from nicegui import ui
from components.su_dashboard_logic import fetch_access_logs, format_datetime_string

def build_logs_ui(log_state, refresh_logs_cb, open_log_detail_dialog_cb):
    """
    アクセスログのカードUIを生成する外部コンポーネント
    """
    with ui.card().classes('w-full h-[440px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-emerald-500 flex flex-col overflow-hidden'):
        with ui.row().classes('w-full justify-between items-center mb-2 shrink-0'):
            ui.label('📋 アクセスログ').classes('font-bold text-emerald-400')
            
            def do_refresh():
                log_state['limit'] = 15
                refresh_logs_cb() # 親のリフレッシュ関数を実行
                
            ui.button(icon='refresh', on_click=do_refresh).props('flat round dense color=emerald-400 size=sm')
        
        try:
            logs = fetch_access_logs(log_state['limit'])
        except Exception as e:
            print(f"💡 アクセスログ取得エラー: {e}")
            ui.label('通信が混み合っています...').classes('text-white/50 text-xs p-2')
            return

        with ui.column().classes('w-full gap-2 h-[300px] overflow-y-auto clean-scroll shrink-0'):
            for log in logs:
                raw_date = log.get('created_at', '')
                try:
                    formatted = format_datetime_string(raw_date)
                    parts = formatted.split(' ')
                    date_parts = parts[0].split('-')
                    short_date = f"{date_parts[1]}-{date_parts[2]}"
                    display_time = f"{short_date} {parts[1]}"
                except Exception:
                    display_time = format_datetime_string(raw_date)
                
                loc = log.get('location') or 'ローカル'
                loc = loc.replace('Japan ', '') if 'Japan' in loc else loc

                with ui.row().classes('w-full items-center p-2 bg-black/30 hover:bg-white/10 cursor-pointer rounded-lg border border-white/5 text-[10px] no-wrap gap-2').on('click', lambda _, l=log: open_log_detail_dialog_cb(l)):
                    ui.label(display_time).classes('text-white/40 font-mono shrink-0')
                    ui.label(log.get('user_name', 'ゲスト')).classes('font-bold text-cyan-300 shrink-0 truncate w-14')
                    ui.label(log.get('action', '操作')).classes('text-slate-200 truncate flex-grow')
            
            if len(logs) >= log_state['limit']:
                def load_more():
                    log_state['limit'] += 15
                    refresh_logs_cb() # 親のリフレッシュ関数を実行
                    
                ui.button('もっと見る', on_click=load_more).classes('w-full bg-emerald-900/40 text-emerald-300 text-[10px] py-1 mt-1 shrink-0 rounded-lg')