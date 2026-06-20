# components/su_dashboard_events.py
from nicegui import ui, app
from database.event_db import fetch_active_events
from database.scoring_db import record_event_attendance, remove_event_attendance
from config.supabase_config import get_supabase

def fetch_actual_attendees(event_id: str):
    """実際にスコア付与済みのユーザーを取得"""
    sb = get_supabase()
    try:
        res = sb.table("event_attendance").select("user_id").eq("event_id", event_id).execute()
        return [item['user_id'] for item in (res.data or [])]
    except Exception as e:
        print(f"❌ [fetch_actual_attendees エラー]: {e}")
        return []

def build_events_ui(refresh_users_cb, refresh_kpi_cb):
    # テーマ設定の取得
    from themes import THEMES
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)

    try:
        events = fetch_active_events()
    except Exception as e:
        print(f"イベント取得エラー: {e}")
        with ui.card().classes('w-full h-[430px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-indigo-500/50 flex flex-col overflow-hidden'):
            ui.label('📅 イベント出席管理').classes('font-bold text-indigo-400 mb-2 shrink-0')
            ui.label('通信が混み合っています...').classes('text-white/50 text-xs p-2')
        return

    # ★ テーマに合わせた外枠の色設定
    outer_border = 'border-indigo-300' if is_light else 'border-indigo-500/50'
    header_text = 'text-indigo-700' if is_light else 'text-indigo-400'
    no_event_text = 'text-slate-500' if is_light else 'text-white/50'
    inner_border = 'border-slate-200' if is_light else 'border-white/5'

    # NG審議・チケットと高さを合わせたフレックスコンテナ
    with ui.card().classes(f'w-full h-[430px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 {outer_border} flex flex-col overflow-hidden'):
        ui.label('📅 イベント出席管理').classes(f'font-bold {header_text} mb-2 shrink-0')

        # 削除済みのイベントを除外
        active_events = [e for e in events if not e.get('deleted_at')]

        if not active_events:
            with ui.column().classes('w-full flex-grow justify-center items-center'):
                ui.label('現在、有効なイベントはありません。').classes(f'{no_event_text} text-xs text-center w-full')
        else:
            with ui.scroll_area().classes(f'w-full flex-grow border {inner_border} rounded-lg'):
                with ui.column().classes('w-full gap-3 pb-4'):
                    for event in active_events:
                        # ★ 個別カードのテーマ別カラー設定
                        card_bg = 'bg-white border-indigo-200 shadow-sm' if is_light else 'bg-slate-900/40 border-indigo-500/40'
                        title_text = 'text-slate-800' if is_light else 'text-slate-100'
                        date_text = 'text-indigo-600' if is_light else 'text-indigo-300/80'
                        icon_color = 'indigo-500' if is_light else 'indigo-400/80'
                        btn_bg = 'bg-indigo-500 hover:bg-indigo-400' if is_light else 'bg-indigo-600/80 hover:bg-indigo-500'
                        
                        with ui.column().classes(f"w-full rounded-xl p-3 border-l-2 {card_bg} border-y border-r {inner_border} shrink-0 min-h-[90px]"):
                            
                            with ui.row().classes(f'w-full items-center gap-1.5 m-0 pb-1 border-b {inner_border} no-wrap'):
                                ui.icon('event', size='xs', color=icon_color)
                                ui.label(event.get('title', '無題')).classes(f'font-bold {title_text} text-xs truncate flex-grow')
                            
                            ui.label(f"開催日時: {event.get('event_date', '未定')}").classes(f'text-[9px] {date_text} mb-0.5 mt-1 pl-0.5')
                            
                            with ui.row().classes('w-full justify-end mt-1 m-0'):
                                def make_open_cb(e_data=event):
                                    return lambda: open_attendance_dialog(e_data, refresh_users_cb, refresh_kpi_cb, is_light)
                                    
                                ui.button('参加者リストを開く', icon='group', on_click=make_open_cb()).classes(f'{btn_bg} text-white font-bold py-1 px-3 text-[10px] rounded-lg shadow')

def open_attendance_dialog(event_data, refresh_users_cb, refresh_kpi_cb, is_light=False):
    sb = get_supabase()
    try:
        res = sb.table("profiles").select("id, name, avatar_url").neq("status", "pending").execute()
        all_users = res.data or []
    except Exception as e:
        print(f"ユーザー取得エラー: {e}")
        all_users = []
        
    actual_attendees = fetch_actual_attendees(event_data['id'])
    intended_participants = event_data.get('participant_ids') or []
    
    # ★ ダイアログのテーマ別カラー設定
    dialog_bg = 'bg-slate-50 border-indigo-300' if is_light else 'bg-slate-900 border-indigo-500/30'
    text_main = 'text-slate-800' if is_light else 'text-white'
    text_sub = 'text-slate-500' if is_light else 'text-white/60'
    header_border = 'border-slate-300' if is_light else 'border-white/10'
    scroll_bg = 'bg-slate-200/50 border-slate-300' if is_light else 'bg-black/20 border-white/5'
    
    with ui.dialog() as dialog, ui.card().classes(f'w-[90vw] max-w-md {dialog_bg} {text_main} p-5 shadow-2xl rounded-2xl gap-3'):
        with ui.row().classes(f'w-full justify-between items-center border-b {header_border} pb-2 mb-1'):
            with ui.row().classes('items-center gap-1.5'):
                ui.icon('fact_check', size='sm', color='indigo-500' if is_light else 'indigo-400')
                ui.label(f"『{event_data.get('title')}』出席確認").classes('text-sm font-bold truncate max-w-[200px]')
            ui.button(icon='close', on_click=dialog.close).props(f'flat round size=sm color={"grey-8" if is_light else "white"}')
            
        ui.label('スイッチをONにするとスコアが付与されます。').classes(f'text-[10px] {text_sub} mb-1')
        
        with ui.scroll_area().classes(f'h-[50vh] w-full border rounded-lg p-2 {scroll_bg}'):
            sorted_users = sorted(all_users, key=lambda x: x['id'] not in intended_participants)
            
            for user in sorted_users:
                u_id = user['id']
                is_intended = u_id in intended_participants
                is_attended = u_id in actual_attendees
                
                # ★ ユーザー行のテーマ別カラー設定
                if is_light:
                    row_bg = 'bg-indigo-50 border-indigo-200' if is_intended else 'bg-white border-slate-200'
                    intended_text = 'text-indigo-600'
                else:
                    row_bg = 'bg-indigo-950/40 border-indigo-500/30' if is_intended else 'bg-slate-800/50 border-white/5'
                    intended_text = 'text-indigo-300'
                
                with ui.row().classes(f'w-full items-center justify-between p-2 rounded-lg border {row_bg} mb-2 shadow-sm'):
                    with ui.row().classes('items-center gap-2'):
                        ui.image(user.get('avatar_url')).classes(f'w-8 h-8 rounded-full border {"border-slate-300" if is_light else "border-white/20"}')
                        with ui.column().classes('gap-0'):
                            ui.label(user.get('name', '名無し')).classes('text-xs font-bold')
                            if is_intended:
                                ui.label('参加予定').classes(f'text-[8px] {intended_text} font-bold')
                    
                    def toggle_attendance(e, event_id=event_data['id'], uid=u_id):
                        if e.value:
                            record_event_attendance(event_id, uid)
                        else:
                            remove_event_attendance(event_id, uid)
                        refresh_kpi_cb()
                        refresh_users_cb()
                        
                    ui.switch(value=is_attended, on_change=toggle_attendance).props('color=indigo-500 size=sm')

        btn_close_bg = 'bg-slate-300 hover:bg-slate-400 text-slate-800' if is_light else 'bg-slate-800 hover:bg-slate-700 text-white'
        ui.button('閉じる', on_click=dialog.close).classes(f'w-full mt-2 {btn_close_bg} py-2 rounded-xl text-xs font-bold')
    dialog.open()