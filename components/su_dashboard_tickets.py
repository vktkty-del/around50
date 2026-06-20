# components/su_dashboard_tickets.py
from nicegui import ui, app
from database.su_db import fetch_support_tickets, update_ticket_status, delete_ticket

# ★修正: NG審議と同じようにモジュールレベルでタブ状態を保持する
ticket_state = {'active': 'active'}

def build_tickets_ui(refresh_tickets_cb, refresh_kpi_cb):
    # ★ 以下のテーマ取得とスタイル定義を追加します
    from themes import THEMES
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)

    tab_bg = 'bg-slate-150 border-slate-200' if is_light else 'bg-slate-900/30 border-white/5'
    inactive_color = 'grey-6' if is_light else 'white/50'
    """
    サポートチケットのUIを生成する外部コンポーネント (NG審議と完全統一版)
    """
    try:
        tickets = fetch_support_tickets()
    except Exception as e:
        print(f"チケット取得エラー: {e}")
        with ui.card().classes('w-full h-[430px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-amber-500/50 flex flex-col overflow-hidden'):
            ui.label('📩 サポートチケット').classes('font-bold text-amber-400 mb-2 shrink-0')
            ui.label('通信が混み合っています...').classes('text-white/50 text-xs p-2')
        return

    # NG審議と同じくフレックスボックスと flex-grow を使ってスクロール潰れを防止
    with ui.card().classes('w-full h-[430px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-amber-500/50 flex flex-col overflow-hidden'):
        ui.label('📩 サポートチケット').classes('font-bold text-amber-400 mb-2 shrink-0')
        
        # ★ bg-slate-900/30 などのクラスを廃止し、カスタムクラス「hibi-tab-row」に差し替え
        with ui.row().classes('w-full hibi-tab-row rounded-lg p-1 mb-2.5 border shrink-0 gap-2 justify-stretch'):
            is_active = (ticket_state['active'] == 'active')
            
            # ★ 非アクティブ時は、固定で "white" ＋ 「hibi-tab-btn-inactive」クラスを適用
            active_color = 'primary' if is_active else 'white'
            ui.button('未対応・対応中', on_click=lambda: (ticket_state.update(active='active'), refresh_tickets_cb())) \
                .props(f'flat color={active_color} size=sm')\
                .classes('flex-grow font-bold text-xs' + ('' if is_active else ' hibi-tab-btn-inactive'))
                
            done_color = 'white' if is_active else 'primary'
            ui.button('完了済アーカイブ', on_click=lambda: (ticket_state.update(active='done'), refresh_tickets_cb())) \
                .props(f'flat color={done_color} size=sm')\
                .classes('flex-grow font-bold text-xs' + ('' if not is_active else ' hibi-tab-btn-inactive'))

        # --- 【未対応・対応中 領域】 ---
        if ticket_state['active'] == 'active':
            active_tickets = [t for t in tickets if t.get('status') in ['unread', 'in_progress']]
            
            if not active_tickets:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('未対応のチケットはありません。').classes('text-white/50 text-xs text-center w-full')
            else:
                with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg'):
                    with ui.column().classes('w-full gap-3 pb-4'):
                        for t in active_tickets:
                            is_high = (t.get('priority') == 'high')
                            card_bg = 'bg-red-950/30 border-red-500/40' if is_high else 'bg-slate-900/40 border-amber-500/40'
                                
                            with ui.column().classes(f"w-full rounded-xl p-3 border-l-2 {card_bg} border-y border-r border-white/5 shrink-0 min-h-[120px]"):
                                profile = t.get('profiles') or {}
                                sender_name = profile.get('name', '名無し')
                                
                                # ヘッダー部分
                                with ui.row().classes('w-full items-center gap-1.5 m-0 pb-1 border-b border-white/5 no-wrap'):
                                    ui.icon('mail', size='xs', color='amber-400/80' if not is_high else 'red-400/80')
                                    ui.label(t.get('title', '無題')).classes('font-bold text-slate-100 text-xs truncate flex-grow')
                                    if is_high:
                                        ui.label('至急').classes('text-[9px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded border border-red-500/30 shrink-0')
                                    elif t.get('status') == 'in_progress':
                                        ui.label('対応中').classes('text-[9px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30 shrink-0')

                                ui.label(f"送信: {sender_name}").classes('text-[9px] text-amber-300/80 mb-0.5 mt-1 pl-0.5')
                                ui.label(t.get('content', '')).classes('text-xs text-slate-300 bg-black/15 p-2.5 rounded-xl w-full whitespace-pre-wrap border border-white/5 leading-relaxed')
                                
                                current_status = t.get('status', 'unread')
                                with ui.row().classes('w-full justify-end mt-1 m-0 gap-2'):
                                    if current_status == 'unread':
                                        def start_progress(tid=t['id']):
                                            update_ticket_status(tid, 'in_progress')
                                            refresh_tickets_cb()
                                            refresh_kpi_cb()
                                        ui.button('対応開始', on_click=start_progress).classes('bg-amber-600/80 hover:bg-amber-500 text-white font-bold py-1 px-3 text-[10px] rounded-lg shadow')
                                    
                                    elif current_status == 'in_progress':
                                        def resolve_ticket(tid=t['id']):
                                            update_ticket_status(tid, 'resolved')
                                            refresh_tickets_cb()
                                            refresh_kpi_cb()
                                        ui.button('解決済みにする', on_click=resolve_ticket).classes('bg-emerald-600/80 hover:bg-emerald-500 text-white font-bold py-1 px-3 text-[10px] rounded-lg shadow')

        # --- 【完了済アーカイブ 領域】 ---
        else:
            done_tickets = [t for t in tickets if t.get('status') == 'resolved']
            
            if not done_tickets:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('解決済みの履歴はありません。').classes('text-white/50 text-xs text-center w-full')
            else:
                with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg'):
                    with ui.column().classes('w-full gap-3 pb-4'):
                        for t in done_tickets:
                            with ui.column().classes("w-full rounded-xl p-3 bg-slate-900/30 border-l-2 border-emerald-500/30 border-y border-r border-white/5 shrink-0 min-h-[100px]"):
                                profile = t.get('profiles') or {}
                                sender_name = profile.get('name', '名無し')
                                
                                with ui.row().classes('w-full items-center gap-1.5 m-0 pb-1 border-b border-white/5 no-wrap'):
                                    ui.icon('check_circle', size='xs', color='emerald-500/60')
                                    ui.label(t.get('title', '無題')).classes('font-bold text-slate-300 text-xs truncate flex-grow')
                                    ui.label('解決済').classes('text-[9px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/20 shrink-0')

                                ui.label(f"送信: {sender_name}").classes('text-[9px] text-emerald-400/80 mb-0.5 mt-1 pl-0.5')
                                ui.label(t.get('content', '')).classes('text-xs text-slate-400 bg-black/10 p-2.5 rounded-xl w-full whitespace-pre-wrap')
                                
                                with ui.row().classes('w-full justify-end mt-1 m-0'):
                                    def delete_t(tid=t['id']):
                                        delete_ticket(tid)
                                        refresh_tickets_cb()
                                    ui.button('レコード削除', icon='delete_forever', on_click=delete_t).classes('bg-slate-800 hover:bg-red-800 text-white font-bold py-1 px-3 text-[10px] rounded-lg shadow')