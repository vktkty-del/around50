# components/su_dashboard_requests.py
from nicegui import ui
from database.event_db import fetch_pending_requests_for_su, update_request_status
from components.event_dialogs import open_create_event_dialog
from components.avatar import draw_user_avatar

@ui.refreshable
def build_requests_ui(current_user_id: str, refresh_all_cb):
    # ★ 修正: bg-slate-900/50 から、テーマ自動追従の hibi-panel-glass に変更
    with ui.column().classes('w-full hibi-panel-glass border border-white/10 rounded-2xl p-4 gap-3 mb-4'):
        with ui.row().classes('items-center justify-between w-full'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('how_to_vote', size='sm', color='indigo-400')
                ui.label('新着の開催リクエスト').classes('text-sm font-bold text-white')
            ui.button(icon='refresh', on_click=lambda: build_requests_ui.refresh()).props('flat round size=xs color=white').classes('opacity-50 hover:opacity-100')
        
        requests = fetch_pending_requests_for_su()
        
        if not requests:
            ui.label('現在、承認待ちのリクエストはありません。').classes('text-xs text-white/50 py-4 text-center w-full')
            return
            
        with ui.column().classes('w-full gap-2 max-h-[400px] overflow-y-auto clean-scroll'):
            for req in requests:
                shop = req.get('shops', {})
                prof = req.get('profiles', {})
                
                # ★ 修正: bg-slate-800/80 から、ライトテーマ時に綺麗に白反転する bg-white/5 に変更
                with ui.card().classes('w-full bg-white/5 border border-white/10 p-3 gap-2 shadow-md'):
                    with ui.row().classes('w-full items-center justify-between no-wrap'):
                        with ui.row().classes('items-center gap-2 flex-grow overflow-hidden'):
                            draw_user_avatar(
                                avatar_url=prof.get('avatar_url'),
                                name=prof.get('name', '名無し'),
                                user_id=req.get('requested_by'),
                                role='member',
                                size_class='w-6 h-6',
                                show_online_badge=False,
                                border_class='border-slate-700'
                            )
                            ui.label(f"{prof.get('name', '名無し')} さんからのリクエスト").classes('text-xs font-bold text-indigo-300 truncate')
                        
                        ui.label(req.get('created_at', '')[:10]).classes('text-[10px] text-white/40 shrink-0')
                    
                    with ui.column().classes('gap-1 mt-1'):
                        ui.badge(shop.get('name', '不明な店舗'), color='indigo-600').classes('text-xs px-2')
                        if req.get('comment'):
                            ui.label(f"「{req.get('comment')}」").classes('text-xs text-white/80 bg-black/20 p-2 rounded border border-white/5 w-full whitespace-pre-wrap')
                    
                    with ui.row().classes('w-full justify-end gap-2 mt-2'):
                        def handle_reject(r_id=req['id']):
                            update_request_status(r_id, 'rejected')
                            ui.notify('リクエストを見送りました', color='warning')
                            build_requests_ui.refresh()
                            
                        def handle_create(r=req, s=shop):
                            prefill = {
                                'request_id': r['id'],
                                'requested_by': r['requested_by'],
                                'shop_id': s['id'],
                                'shop_name': s.get('name', ''),
                                'url': s.get('url', ''),
                                'image_url': s.get('image_url', '')
                            }
                            open_create_event_dialog(current_user_id, refresh_all_cb, prefill_data=prefill)
                            
                        ui.button('見送り', on_click=handle_reject).props('flat size=xs color=grey').classes('font-bold')
                        ui.button('このお店でイベントを作成', on_click=handle_create, icon='add').classes('bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold px-3 py-1 rounded shadow-lg')