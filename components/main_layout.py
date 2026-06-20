# components/main_layout.py
from nicegui import app, ui
import themes
import time

# --- コンポーネント群 ---
from components.chat_view import draw_chat_view
from components.comp_profile import show_profile_dialog 
from components.feed_item import render_timeline
#from components.event_card import render_events
from components.calendar_view import render_events
from components.flat_chat import render_flat_chat
from components.members_view import render_members
from components.su_dashboard import render_su_dashboard
from components.support_dialog import open_support_ticket_dialog
from gemini_chat import render_gemini_chat
from components.help_view import render_help
from components.split_calc import render_split_calc
from components.avatar import draw_user_avatar
# ★ 追加: お店ポータルのインポート
from components.shop_portal_ui import draw_shop_portal
from database.profile_db import get_or_create_invite_code
from database.su_db import get_su_pending_count

# ★ 追加: 自動ルーティング判別用
from database.flat_db import get_flat_by_id

def draw_main_layout(current_user_id, current_user_name, avatar_url, is_su):
    saved_menu = app.storage.user.get('current_menu', 'home')
    saved_room_id = app.storage.user.get('current_room_id', None)
    page_state = {'current_menu': saved_menu, 'current_room_id': saved_room_id}
    nav_btns_pc = {}
    nav_btns_sp = {}

    def change_theme(name):
        app.storage.user['theme_name'] = name
        from main import apply_theme 
        apply_theme() 
                
        ui.notify(f'テーマを {name} に変更しました', position='top')
        draw_theme_selector.refresh()

    @ui.refreshable
    def draw_theme_selector():
        with ui.column().classes('w-full bg-white/5 border border-white/10 rounded-2xl p-3 gap-1.5'):
            ui.label('🎨 テーマを選択').classes('text-[10px] text-white/50 font-bold tracking-widest pl-1')
            with ui.row().classes('w-full gap-3 justify-start items-center flex-wrap px-1 pt-1'):
                for name, t_data in themes.THEMES.items():
                    is_current = (app.storage.user.get('theme_name', 'Moonlight') == name)
                    bg_classes = t_data.get('bg', 'bg-gray-800')
                    
                    element = ui.element('div').classes(
                        f"w-6 h-6 rounded-full cursor-pointer transition-all shrink-0 {bg_classes}"
                    ).tooltip(name).on('click', lambda n=name: (change_theme(n), menu.close()))
                    
                    if is_current:
                        element.classes('border-[3px] scale-110')
                        element.style('border-color: var(--q-primary); box-shadow: 0 0 10px var(--q-primary);')
                    else:
                        element.classes('border border-white/20 hover:scale-105')

    def change_menu(menu_name: str, room_id: str = None):
        page_state['current_menu'] = menu_name
        page_state['current_room_id'] = room_id
        app.storage.user['current_menu'] = menu_name
        app.storage.user['current_room_id'] = room_id
        for name, btn in nav_btns_pc.items():
            btn.props(f'color={"primary" if name == menu_name else "white/50"}')
        for name, btn in nav_btns_sp.items():
            btn.props(f'color={"primary" if name == menu_name else "white/50"}')
        center_content.refresh()
        right_sidebar.refresh() 

    # ★ 追加: 'shop_portal' (お店ポータル) をメニューの3番目に追加
    menus = [
        ('home', 'home', 'タイムライン'),
        ('event', 'event', 'イベントカレンダー'),
        ('shop_portal', 'storefront', 'お店ポータル'),
        ('chat', 'chat', 'チャット一覧'),
        ('members', 'people', 'メンバー一覧'),
        ('ai_chat', 'nightlife', 'スナックHIBI'),
        ('calc', 'calculate', '割り勘計算')
    ]

    # ==========================================
    # 右サイドバー（進行中のチャット、最大3名重ね表示）
    # ==========================================
    @ui.refreshable
    def right_sidebar():
        with ui.column().classes('pc-chat flex-col shrink-0 w-[260px] h-full m-0 p-5 gap-4 hibi-panel-glass border-l border-white/10'):
            ui.label('進行中のチャット').classes('text-xs font-bold text-white/40 uppercase tracking-wider')
            
            from database.chat_db import fetch_active_chat_rooms, get_room_last_message_time, GLOBAL_CHAT_VIEWERS
            from dateutil import parser as date_parser
            from datetime import datetime, timezone

            rooms = fetch_active_chat_rooms()
            real_rooms = [r for r in rooms if not r.get('title', '').startswith('[FLAT砂場]')]
            recent_rooms = real_rooms[-6:] 
            
            if not recent_rooms:
                ui.label('現在アクティブなチャットはありません').classes('text-[10px] text-white/30')
            else:
                for room in reversed(recent_rooms):
                    r_id = room['id']
                    title = room.get('title', '無題ルーム')
                    
                    participants = []
                    room_id_str = str(r_id)
                    viewers = GLOBAL_CHAT_VIEWERS.get(room_id_str, {})
                    for uid, info in list(viewers.items()):
                        if info.get('expire', 0) > time.time():
                            avatar_url = info.get('avatar_url')
                            if avatar_url and avatar_url not in participants:
                                participants.append(avatar_url)

                    last_time_str = get_room_last_message_time(r_id)
                    is_live = False
                    if last_time_str:
                        try:
                            last_dt = date_parser.parse(last_time_str)
                            if last_dt.tzinfo is not None:
                                now_time = datetime.now(timezone.utc)
                            else:
                                now_time = datetime.now()
                            diff = now_time - last_dt
                            if diff.total_seconds() < 600:
                                is_live = True
                        except Exception:
                            pass

                    with ui.card().classes('w-full bg-cyan-500/10 border border-cyan-500/30 p-3 rounded-xl cursor-pointer hover:bg-cyan-500/20 transition').on('click', lambda e, r=r_id: change_menu('chat', r)):
                        with ui.row().classes('w-full justify-between items-center no-wrap'):
                            ui.label(title).classes('text-xs font-bold text-cyan-300 truncate w-24')
                            
                            with ui.row().classes('items-center gap-1.5 shrink-0 no-wrap'):
                                if participants:
                                    display_avatars = participants[:3]
                                    has_more = len(participants) > 3
                                    
                                    with ui.row().classes('flex overflow-hidden items-center').style('gap: 0;'):
                                        for idx, avatar in enumerate(display_avatars):
                                            margin_class = '' if idx == 0 else '-ml-2.5'
                                            ui.element('img').props(f'src="{avatar}"')\
                                                .classes(f'inline-block h-5 w-5 rounded-full border-2 border-white/20 dark:border-white/10 object-cover {margin_class}')\
                                                .style(f'z-index: {10 - idx};')
                                        
                                        if has_more:
                                            with ui.element('div').classes('flex items-center justify-center h-5 w-5 rounded-full border-2 border-white/20 dark:border-white/10 bg-slate-800 text-[9px] text-white/50 font-bold shrink-0 -ml-2.5')\
                                                    .style(f'z-index: {10 - len(display_avatars)};'):
                                                ui.label('⋯').classes('leading-none mt-[-2px]')
                                
                                if is_live:
                                    ui.badge('LIVE', color='cyan-500').classes('text-[9px] px-1 animate-pulse')

    @ui.refreshable
    def center_content():
        current_menu = page_state['current_menu']
        
        # 廃止された旧FLAT画面のメモリが残っていたユーザーを、自動的に統合先のイベント画面へ誘導
        if current_menu == 'flat':
            ui.timer(0.1, lambda: change_menu('event'), once=True)
            return

        try:
            from components.su_dashboard import insert_access_log
            client_ip = ui.context.client.ip or "0.0.0.0"
            room_id = page_state.get("current_room_id")
            user_agent_raw = ui.context.client.request.headers.get('user-agent', '不明')
            
            menu_names_jp = {
                'home': 'タイムライン（ホーム）を表示',
                'event': '公式イベント一覧を表示',
                'shop_portal': 'お店ポータルを表示',  # ★ 追加
                'members': 'メンバー一覧を表示',
                'ai_chat': 'Gemini AI Chat を表示',
                'su_dash': 'SUダッシュボード（管理画面）を表示'
            }
            
            if current_menu == 'chat':
                if room_id:
                    action_text = f'チャットルームを閲覧 (ID: {room_id})'
                else:
                    action_text = 'チャットルーム一覧を表示'
            elif current_menu == 'flat_chat':
                if room_id:
                    action_text = f'ふらっと作戦会議（匿名砂場）を閲覧 (ID: {room_id})'
                else:
                    action_text = 'ふらっと作戦会議（匿名砂場）を表示'
            else:
                action_text = menu_names_jp.get(current_menu, f'メニュー「{current_menu}」を表示')
            
            insert_access_log(current_user_name, action_text, client_ip, user_agent_raw)
        except Exception as e:
            print(f"Global Logging Error: {e}")

        if current_menu == 'chat':
            with ui.column().classes('w-full h-full p-0 m-0'):
                draw_chat_view(current_user_id, page_state.get('current_room_id'))

        elif current_menu == 'ai_chat':
            with ui.column().classes('w-full h-full p-0 m-0'):
                render_gemini_chat(current_user_id, current_user_name, avatar_url)
        
        elif current_menu == 'calc': 
            with ui.column().classes('w-full max-w-2xl mx-auto gap-6 px-4 md:px-8 py-8 m-0'):
                render_split_calc()

        elif current_menu == 'help': 
            with ui.column().classes('w-full max-w-2xl mx-auto gap-6 px-4 md:px-8 py-8 m-0'):
                render_help()

        # ★ 追加: お店ポータルのルーティング（3カラムのワイド表示を維持するため、個別にフル幅で囲む）
        elif current_menu == 'shop_portal':
            with ui.column().classes('w-full h-full p-0 m-0'):
                draw_shop_portal(current_user_id)

        else:
            max_width_class = 'max-w-none px-4 md:px-10' if current_menu == 'su_dash' else 'max-w-2xl mx-auto px-4 md:px-8'
            with ui.column().classes(f'w-full {max_width_class} gap-6 py-8 m-0'):
                if current_menu == 'home':
                    render_timeline(
                        current_user_id=current_user_id,
                        current_user_name=current_user_name,
                        avatar_url=avatar_url,
                        is_su=is_su,
                        refresh_cb=center_content.refresh,
                        change_menu_cb=change_menu
                    )
                elif current_menu == 'event':
                    def smart_route_chat(r_id):
                        if r_id and get_flat_by_id(r_id):
                            change_menu('flat_chat', r_id)
                        else:
                            change_menu('chat', r_id)

                    render_events(
                        current_user_id=current_user_id,
                        is_su=is_su,  
                        enter_chat_cb=smart_route_chat
                    )
                elif current_menu == 'flat_chat':
                    with ui.column().classes('w-full h-full p-0 m-0'):
                        render_flat_chat(
                            current_user_id=current_user_id,
                            flat_id=page_state.get('current_room_id'),
                            exit_cb=lambda: change_menu('event'), 
                            enter_real_chat_cb=lambda room_id: change_menu('chat', room_id)
                        )
                elif current_menu == 'members':
                    render_members(current_user_id=current_user_id)
                elif current_menu == 'su_dash' and is_su:
                    render_su_dashboard(current_user_id)

    def show_notifications():
        notifs = []
        alive_ids = set()
        try:
            from config.supabase_config import get_supabase
            sb = get_supabase()
            
            res = sb.table("notifications")\
                .select("*")\
                .eq("user_id", current_user_id)\
                .order("created_at", desc=True)\
                .limit(30)\
                .execute()
            notifs = res.data or []
            
            target_ids = []
            for msg_data in notifs:
                raw_content = msg_data.get('content', '')
                if "|[post_id:" in raw_content:
                    pid = raw_content.split("|[post_id:")[1].split("|")[0].replace("]", "").strip()
                    target_ids.append(pid)
                if "|[reply_id:" in raw_content:
                    rid = raw_content.split("|[reply_id:")[1].replace("]", "").strip()
                    target_ids.append(rid)
                    
            if target_ids:
                alive_res = sb.table("timeline_posts")\
                    .select("id")\
                    .in_("id", target_ids)\
                    .is_("deleted_at", "null")\
                    .execute()
                if alive_res.data:
                    alive_ids = {str(item['id']) for item in alive_res.data}

        except Exception as e:
            print(f"💡 [通知履歴取得] クエリでエラーが発生しました: {e}")
            try:
                res = sb.table("notifications").select("*").eq("user_id", current_user_id).limit(30).execute()
                notifs = res.data or []
            except Exception as ex:
                print(f"💡 [通知履歴取得フォールバック] 取得に失敗しました: {ex}")
                notifs = []
            
        with ui.dialog() as notif_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-[380px] max-w-full p-6 shadow-2xl rounded-3xl'):
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('お知らせ履歴').classes('text-lg font-bold text-white')
                ui.button(icon='close', on_click=notif_dialog.close).props('flat round size=sm color=white')
                
            with ui.column().classes('w-full max-h-80 overflow-y-auto hide-scrollbar gap-3'):
                if notifs:
                    for msg_data in notifs:
                        raw_content = msg_data.get('content', '')
                        is_unread = not msg_data.get('is_read', False)
                        
                        post_id = None
                        reply_id = None
                        display_text = raw_content
                        
                        if "|[post_id:" in raw_content:
                            parts = raw_content.split("|[post_id:")
                            display_text = parts[0]
                            post_id = parts[1].split("|")[0].replace("]", "").strip()
                        if "|[reply_id:" in raw_content:
                            reply_id = raw_content.split("|[reply_id:")[1].replace("]", "").strip()

                        is_parent_alive = (not post_id) or (post_id in alive_ids)
                        is_reply_alive = (not reply_id) or (reply_id in alive_ids)
                        is_deleted = not (is_parent_alive and is_reply_alive)

                        if is_unread:
                            card_style_classes = 'w-full items-center justify-between gap-2 p-3 rounded-lg border-l-4 select-none transition-all duration-200'
                            row = ui.row().classes(card_style_classes).style('border-color: var(--q-primary); background-color: rgba(255,255,255,0.05);')
                        else:
                            card_style_classes = 'w-full items-center justify-between gap-2 p-3 rounded-lg border-l-2 border-white/10 opacity-60 hover:opacity-100 select-none transition-all duration-200'
                            row = ui.row().classes(card_style_classes)
                        
                        if post_id and not is_deleted:
                            row.classes('cursor-pointer hover:bg-black/50 hover:scale-[1.01]')
                        elif is_deleted:
                            row.classes('opacity-35 bg-black/10')
                            
                        with row:
                            with ui.row().classes('items-start gap-2 flex-grow min-w-0'):
                                if is_deleted:
                                    icon_name = 'delete_outline'
                                    icon_color = 'red-400/60'
                                else:
                                    icon_name = 'info' if is_unread else 'check_circle'
                                    icon_color = 'primary' if is_unread else 'white/40'
                                    
                                ui.icon(icon_name, size='sm').props(f'color="{icon_color}"').classes('mt-0.5 shrink-0')
                                
                                text_class = 'text-sm text-white/80 leading-tight break-all'
                                if is_deleted:
                                    text_class += ' line-through text-white/45'
                                ui.label(display_text).classes(text_class)
                            
                            if post_id:
                                if is_deleted:
                                    with ui.row().classes('items-center gap-1 shrink-0 bg-red-500/5 border border-red-500/10 px-2 py-1 rounded-full'):
                                        ui.label('削除済').classes('text-[10px] font-extrabold text-red-400/50 uppercase tracking-wider')
                                else:
                                    badge_color = 'primary' if is_unread else 'white/40'
                                    with ui.row().classes('items-center gap-1 shrink-0 px-2 py-1 rounded-full transition-colors').style(f'background-color: color-mix(in srgb, var(--q-{badge_color}) 10%, transparent); border: 1px solid color-mix(in srgb, var(--q-{badge_color}) 30%, transparent);'):
                                        ui.label('投稿へ').classes('text-[10px] font-extrabold uppercase tracking-wider').props(f'color="{badge_color}"').style(f'color: var(--q-{badge_color});')
                                        ui.icon('chevron_right', size='xs').props(f'color="{badge_color}"')
                                    
                                    def make_click_handler(pid=post_id):
                                        def handle_click():
                                            app.storage.user['auto_open_post_id'] = pid
                                            clear_and_close()
                                            change_menu('home')
                                        return handle_click
                                        
                                    row.on('click', make_click_handler())
                else:
                    with ui.column().classes('w-full items-center justify-center py-8 gap-2'):
                        ui.icon('notifications_off', size='40px').classes('text-white/20 animate-pulse')
                        ui.label('現在、新しいお知らせや履歴はありません。').classes('text-xs text-white/40 text-center')
                    
            def clear_and_close():
                from database.su_db import mark_notifications_as_read
                try:
                    mark_notifications_as_read(current_user_id)
                except Exception as e:
                    print(f"通知の既読化エラー: {e}")
                
                check_notifications() 
                notif_dialog.close()
                
            with ui.row().classes('w-full justify-end mt-4'):
                has_any_unread = any(not m.get('is_read', False) for m in notifs) if notifs else False
                if has_any_unread:
                    ui.button('すべて既読にする', on_click=clear_and_close).props('outline="true" rounded="true" color="primary"').classes('font-bold px-6 text-xs hover:bg-white/10 transition-colors')
                else:
                    ui.button('閉じる', on_click=notif_dialog.close).props('outline="true" rounded="true" color="white"').classes('font-bold px-6 text-xs hover:bg-white/10 transition-colors')
                
        notif_dialog.open()

    def handle_bell_click():
        show_notifications()   

    with ui.column().classes('absolute inset-0 m-0 p-0 gap-0 no-wrap overflow-hidden'):
        with ui.row().classes('w-full h-14 shrink-0 m-0 px-6 items-center justify-between hibi-panel-glass border-b border-white/10'):
            
            with ui.column().classes('gap-0 cursor-pointer overflow-hidden select-none').on('click', lambda: change_menu('home')):
                ui.label('日々、彩り。').classes(
                    'text-base font-extralight text-white tracking-[0.3em] pl-[0.3em] '
                    'drop-shadow-[0_0_8px_rgba(255,255,255,0.2)] leading-none'
                )
                ui.label('何気ない日常に、大切な仲間と、小さな彩りを。').classes(
                    'text-[7.5px] sm:text-[9px] text-white/30 '
                    'tracking-normal sm:tracking-[0.1em] pl-[0.1em] mt-1.5 leading-none '
                    'truncate max-w-[220px] sm:max-w-none'
                )
            with ui.row().classes('items-center shrink-0 gap-5'):              
                
                if is_su:
                    with ui.element('div').classes('relative cursor-pointer mt-1').on('click', lambda: change_menu('su_dash')):
                        su_icon = ui.icon('security', size='sm', color='white').classes('opacity-70 hover:opacity-100 transition').tooltip('管理者ダッシュボード')
                        su_badge = ui.badge('', color='red').classes('absolute -top-1.5 -right-1.5 text-[9px] px-1.5 py-0.5 font-bold shadow-md')
                        su_badge.set_visibility(False)
                else:
                    with ui.element('div').classes('cursor-pointer mt-1').on('click', lambda: change_menu('help')):
                        ui.icon('help_outline', size='sm', color='white').classes('opacity-70 hover:opacity-100 transition').tooltip('ヘルプ（使い方）')           
                
                with ui.element('div').classes('relative cursor-pointer mt-1').on('click', handle_bell_click):
                    bell_icon = ui.icon('notifications', size='sm', color='white').classes('opacity-70 hover:opacity-100 transition')
                    bell_badge = ui.badge('', color='red').classes('absolute -top-1.5 -right-1.5 text-[9px] px-1 shadow-md')
                    bell_badge.set_visibility(False)

                with ui.row().classes('items-center shrink-0 cursor-pointer') as header_avatar_btn:
                    draw_user_avatar(
                        avatar_url=avatar_url,
                        name=current_user_name,
                        user_id=current_user_id,
                        role='superuser' if is_su else 'member',
                        size_class='w-8 h-8',
                        show_online_badge=True,
                        border_class='border-white/20'
                    )
                    
                    with ui.menu().props('anchor="bottom right" self="top right" :offset="[0, 12]" transition-show="jump-down" transition-hide="jump-up"')\
                            .classes('w-80 max-h-[80vh] overflow-y-auto clean-scroll bg-slate-900/95 backdrop-blur-xl border border-white/10 text-white rounded-[28px] p-0 shadow-2xl mt-1') as menu:
                        
                        def handle_logout():
                            try:
                                fresh_id = app.storage.user.get('user_id')
                                if fresh_id:
                                    from database.profile_db import remove_user_active
                                    remove_user_active(fresh_id)
                            except Exception as e:
                                print(f"Error clearing active user status on logout: {e}")
                            
                            saved_theme = app.storage.user.get('theme_name', 'Moonlight')
                            app.storage.user.clear() 
                            app.storage.user['theme_name'] = saved_theme 
                            ui.navigate.to('/login')

                        with ui.column().classes('w-full items-center px-4 pt-6 pb-4 gap-2 relative border-b border-white/5 m-0'):
                            ui.button(icon='close', on_click=menu.close)\
                                .props('flat round size=xs color=white')\
                                .classes('absolute top-3 right-3 opacity-60 hover:opacity-100')
                            
                            with ui.element('div').classes('w-20 h-20 rounded-full overflow-hidden border-2 border-white/20 shadow-lg flex items-center justify-center bg-white/5 relative'):
                                draw_user_avatar(
                                    avatar_url=avatar_url,
                                    name=current_user_name,
                                    user_id=current_user_id,
                                    role='superuser' if is_su else 'member',
                                    size_class='w-20 h-20',
                                    show_online_badge=True,
                                    border_0='border-0'
                                )
                            
                            ui.label(f'こんにちは、{current_user_name} さん！').classes('text-base font-semibold text-white text-center mt-2 leading-tight')
                            if is_su:
                                ui.label("SUPERUSER").classes('text-[9px] text-cyan-400 font-extrabold tracking-wider uppercase leading-none mt-1')
                            
                            ui.button('マイプロフィールを編集', on_click=lambda: (show_profile_dialog(current_user_id, current_user_id), menu.close()))\
                                .props('outline="true" rounded="true" size="sm" color="primary"')\
                                .classes('px-5 py-1 text-xs font-bold hover:bg-white/10 transition mt-2')

                        with ui.column().classes('w-full px-4 py-3 gap-2 border-b border-white/5 m-0'):
                            with ui.column().classes('w-full bg-white/5 border border-white/10 rounded-2xl p-3 gap-1.5 shadow-inner'):
                                with ui.row().classes('items-center gap-2 no-wrap'):
                                    ui.icon('share', size='xs', color='cyan-400')
                                    ui.label('✉️ メンバー招待').classes('text-[10px] text-cyan-400 font-extrabold tracking-wider uppercase')
                                
                                ui.label('ログイン可能なSNSアカウントをお持ちでない方には、下記の招待コードを共有すれば招待できます。').classes('text-[10px] text-white/60 leading-relaxed')
                                
                                raw_invite_code = get_or_create_invite_code(current_user_id)
                                invite_code = "取得失敗" if str(raw_invite_code).startswith("ERR:") else raw_invite_code
                                
                                with ui.row().classes('w-full items-center justify-between bg-black/20 p-2 rounded-xl border border-white/5 mt-1 no-wrap'):
                                    ui.label(invite_code).classes('text-xs font-mono text-cyan-300 font-bold pl-1')
                                    ui.button('コピー', on_click=lambda e, code=invite_code: (
                                        ui.run_javascript(f'navigator.clipboard.writeText("{code}")'),
                                        ui.notify('招待コードをコピーしました！', color='positive', position='top')
                                    )).props('flat dense size=xs color=cyan-400').classes('text-[10px] font-bold')

                        with ui.column().classes('w-full px-4 py-2 gap-1.5 m-0'):
                            if not is_su:
                                with ui.row().classes('w-full items-center justify-between bg-white/5 hover:bg-white/10 border border-white/5 rounded-2xl p-3 cursor-pointer transition no-wrap')\
                                        .on('click', lambda: (open_support_ticket_dialog(current_user_id), menu.close())):
                                    with ui.row().classes('items-center gap-3 no-wrap'):
                                        ui.icon('support_agent', size='sm', color='white').classes('opacity-70')
                                        ui.label('お問い合わせ / 通報').classes('text-xs font-bold text-white')
                                    ui.icon('chevron_right', size='sm', color='white').classes('opacity-40')

                        with ui.column().classes('w-full px-4 py-2 gap-1 m-0'):
                            draw_theme_selector()

                        with ui.row().classes('w-full px-4 pt-3 pb-5 justify-center m-0'):
                            ui.button('ログアウト', on_click=handle_logout)\
                                .props('unelevated rounded size=sm color=red-500')\
                                .classes('w-full text-xs font-bold py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all')

        with ui.row().classes('w-full flex-grow m-0 p-0 gap-0 no-wrap overflow-hidden'):
            with ui.column().classes('pc-menu flex-col shrink-0 w-20 h-full m-0 py-6 gap-6 items-center hibi-panel-glass border-r border-white/10'):
                for m_id, icon, tooltip in menus:
                    color = "primary" if page_state['current_menu'] == m_id else "white/50"
                    btn = ui.button(on_click=lambda m=m_id: change_menu(m)).props(f'flat round icon={icon} size=md color={color}').tooltip(tooltip)
                    nav_btns_pc[m_id] = btn

            with ui.column().classes('flex-grow h-full clean-scroll m-0 p-0 gap-0 relative'):
                center_content()

            right_sidebar()

        with ui.element('div').classes('sp-menu w-full h-16 shrink-0 m-0 p-0 relative border-t border-white/10 overflow-hidden'):
            with ui.row().classes('w-full h-full px-4 items-center overflow-x-auto no-wrap gap-3').style('scrollbar-width: none; -ms-overflow-style: none;').props('id="sp_scroll_area"') as sp_scroll:
                for m_id, icon, tooltip in menus:
                    color = "primary" if page_state['current_menu'] == m_id else "white/50"
                    btn = ui.button(on_click=lambda m=m_id: change_menu(m)).props(f'flat round icon={icon} size=md color={color}').classes('shrink-0')
                    nav_btns_sp[m_id] = btn
            
            with ui.element('div').classes('absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-slate-950/90 to-transparent pointer-events-none z-20 transition-opacity duration-300 opacity-0').props('id="left_cue"') as left_cue:
                ui.icon('chevron_left', size='22px', color='white/30').classes('absolute left-1.5 top-1/2 -translate-y-1/2 animate-pulse')

            with ui.element('div').classes('absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-slate-950/90 to-transparent pointer-events-none z-20 transition-opacity duration-300 opacity-100').props('id="right_cue"') as right_cue:
                ui.icon('chevron_right', size='22px', color='white/30').classes('absolute right-1.5 top-1/2 -translate-y-1/2 animate-pulse')

    def check_notifications():
        if not app.storage.user.get('is_authenticated'):
            return

        if ui.context.client and not ui.context.client.has_socket_connection:
            return

        try:
            fresh_user_id = app.storage.user.get('user_id')
            if fresh_user_id:
                from database.profile_db import mark_user_active
                mark_user_active(str(fresh_user_id))
        except Exception as e:
            if "10035" in str(e) or "WSAEWOULDBLOCK" in str(e): pass
            else: print(f"Heartbeat update error: {e}")
            
        try:
            right_sidebar.refresh()
        except Exception:
            pass
            
        try:
            from config.supabase_config import get_supabase
            sb = get_supabase()
            
            if is_su:
                total_su_pending = get_su_pending_count()
                if total_su_pending > 0:
                    su_icon.classes(add='animate-swing opacity-100', remove='opacity-70 text-white').props('color=primary')
                    su_badge.set_text(str(total_su_pending))
                    su_badge.props('color=primary')
                    su_badge.set_visibility(True)
                else:
                    su_icon.classes(remove='animate-swing opacity-100', add='opacity-70 text-white').props('color=white')
                    su_badge.set_visibility(False)
            
            from database.su_db import fetch_unread_notifications
            notifs = fetch_unread_notifications(current_user_id)
            
            if notifs:
                bell_icon.classes(add='animate-swing opacity-100', remove='opacity-70 text-white').props('color=primary')
                bell_badge.set_text(str(len(notifs)))
                bell_badge.props('color=primary')
                bell_badge.set_visibility(True)
                app.storage.user['db_notifications'] = notifs
            else:
                bell_icon.classes(remove='animate-swing opacity-100', add='opacity-70 text-white').props('color=white')
                bell_badge.set_visibility(False)
                app.storage.user['db_notifications'] = []
                    
        except Exception as e:
            if "10035" in str(e) or "WSAEWOULDBLOCK" in str(e):
                pass
            else:
                print(f"💡 [通知・管理バッジ更新エラー] {e}")

    check_notifications()
    
    ui.timer(20.0, check_notifications)

    js_scroll_spy = """
    setTimeout(() => {
        const scroll = document.getElementById('sp_scroll_area');
        const left = document.getElementById('left_cue');
        const right = document.getElementById('right_cue');
        
        if (scroll && left && right) {
            function updateScrollIndicators() {
                const scrollLeft = scroll.scrollLeft;
                const maxScrollLeft = scroll.scrollWidth - scroll.clientWidth;
                
                if (scrollLeft > 5) {
                    left.classList.remove('opacity-0');
                    left.classList.add('opacity-100');
                } else {
                    left.classList.remove('opacity-100');
                    left.classList.add('opacity-0');
                }
                
                if (scrollLeft < maxScrollLeft - 5) {
                    right.classList.remove('opacity-0');
                    right.classList.add('opacity-100');
                } else {
                    right.classList.remove('opacity-100');
                    right.classList.add('opacity-0');
                }
            }
            
            scroll.addEventListener('scroll', updateScrollIndicators);
            window.addEventListener('resize', updateScrollIndicators);
            updateScrollIndicators();
        }
    }, 500);
    """
    ui.run_javascript(js_scroll_spy)