# components/flat_dialogs.py
import base64
import uuid
from nicegui import ui
from dateutil import parser as date_parser

from database.flat_db import (
    get_active_flats, create_flat_recruitment, join_flat_recruitment,
    silent_leave_flat, delete_flat_recruitment
)
from database.profile_db import get_safe_profile
from components.comp_profile import show_profile_dialog

def get_anonymous_avatar(pseudo_name: str) -> str:
    """通り名（pseudo_name）をベースにシードを生成し、アバターURLを返す"""
    safe_seed = base64.urlsafe_b64encode(pseudo_name.encode()).decode()[:15]
    return f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}"


def open_flat_detail_dialog(room, current_user_id, is_su, refresh_cb, enter_chat_cb):
    """ふらっと募集の詳細ダイアログを表示する"""
    room_id = room.get('id')
    participants = room.get('participant_ids') or []
    assigned_names = room.get('assigned_names', {})
    current_members = len(participants)
    max_members = room.get('target_count') or 3
    remaining = max_members - current_members
    is_joined = current_user_id in participants
    
    is_host = str(room.get('created_by')) == str(current_user_id)
    host_pseudo_name = room.get('pseudo_name', '名無しのゲスト')
    avatar_url = get_anonymous_avatar(host_pseudo_name)

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-cyan-500/30 text-slate-800 dark:text-white flex flex-col gap-4'):
        with ui.row().classes('w-full items-center justify-between no-wrap'):
            ui.label('ふらっと 詳細').classes('text-base sm:text-lg font-bold text-slate-800 dark:text-white truncate')
            ui.badge(room.get('genre', 'ジャンル未定'), color='cyan-600').classes('text-[10px] px-2 py-0.5 shrink-0')

        with ui.column().classes('w-full gap-1.5'):
            with ui.row().classes('items-center gap-2'):
                ui.image(avatar_url).classes('w-6 h-6 rounded-full bg-slate-800 border border-cyan-500/50')
                ui.label(f"主催者: {host_pseudo_name}").classes('text-xs text-slate-500 dark:text-white/70')
            
            with ui.row().classes('items-center gap-2 text-xs text-slate-700 dark:text-white/90'):
                ui.icon('access_time', size='14px', color='cyan-300')
                ui.label(f"開始目安: {room.get('timing', '時間未定')}")
                
            if room.get('location'):
                with ui.row().classes('items-center gap-2 text-xs text-slate-700 dark:text-white/90'):
                    ui.icon('place', size='14px', color='cyan-300')
                    ui.label(f"場所: {room.get('location')}")

        if room.get('description'):
            ui.label(room.get('description')).classes('text-sm text-slate-700 dark:text-slate-200 bg-black/5 dark:bg-black/30 p-3.5 rounded-lg w-full whitespace-pre-wrap')

        if participants:
            with ui.column().classes('w-full gap-1 mt-1'):
                ui.label('現在のメンバー:').classes('text-[10px] text-slate-500 dark:text-white/50')
                with ui.row().classes('items-center gap-0'):
                    for idx, pid in enumerate(participants):
                        p_name = assigned_names.get(pid, 'ゲスト')
                        av_url = get_anonymous_avatar(p_name)
                        z_index = 100 - idx
                        ml_style = 'margin-left: -14px;' if idx > 0 else 'margin-left: 0px;'
                        ui.image(av_url).style(f'position: relative; z-index: {z_index}; {ml_style}').classes('w-8 h-8 rounded-full bg-slate-800 border-2 border-cyan-500/30 shadow-md').tooltip(p_name)

        with ui.row().classes('w-full justify-end gap-2 mt-2 items-center no-wrap'):
            ui.button('閉じる', on_click=dialog.close).classes('bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')

            if is_host or is_su:
                def handle_delete():
                    with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-80 p-6'):
                        ui.label('この募集を完全に削除しますか？').classes('text-base font-bold text-red-400')
                        ui.label('※この操作は取り消せません。発言ログも消去されます。').classes('text-xs text-white/60')
                        with ui.row().classes('w-full justify-end mt-6 gap-3'):
                            ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                            def execute_delete():
                                delete_flat_recruitment(room_id)
                                ui.notify('募集を完全に消去しました。', type='negative', position='top')
                                confirm_dialog.close()
                                dialog.close()
                                refresh_cb()
                            ui.button('削除する', on_click=execute_delete).classes('bg-red-600 hover:bg-red-500 font-bold')
                    confirm_dialog.open()
                ui.button('募集を削除', icon='delete', on_click=handle_delete).classes('bg-red-800 hover:bg-red-700 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')

            if is_joined:
                if is_host:
                    ui.badge('👑 主催者', color='cyan-600').classes('text-xs px-3 py-2 h-10 flex items-center rounded-lg shrink-0 font-bold')
                else:
                    if remaining > 0:
                        def handle_leave():
                            with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-80 p-6'):
                                ui.label('作戦会議からそっと抜けますか？').classes('text-base font-bold text-red-400')
                                with ui.row().classes('w-full justify-end mt-6 gap-3'):
                                    ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                                    def execute_leave():
                                        silent_leave_flat(room_id, current_user_id)
                                        ui.notify('作戦会議からそっと抜けました。', type='info', position='top')
                                        confirm_dialog.close()
                                        dialog.close()
                                        refresh_cb()
                                    ui.button('抜ける', on_click=execute_leave).classes('bg-red-600 hover:bg-red-500 font-bold')
                            confirm_dialog.open()
                        ui.button('参加済み (タップで辞める)', icon='check_circle', on_click=handle_leave).classes('bg-teal-600 hover:bg-red-700 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0 transition-all duration-200')
                    else:
                        ui.button('会議室へ', icon='meeting_room', on_click=lambda: (dialog.close(), enter_chat_cb(room_id))).classes('bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0 animate-bounce')
            else:
                if remaining > 0:
                    async def handle_join(target_room_id=room_id, current_room=room):
                        profile = get_safe_profile(current_user_id)
                        gender = profile.get('gender', 0)
                        
                        if current_room.get('genre') == '👩 女子会':
                            if gender == 0:
                                ui.notify('女子会に参加するため、プロフィールで「性別」を設定してください！', type='warning', position='top', timeout=5000)
                                dialog.close()
                                show_profile_dialog(current_user_id, current_user_id)
                                return
                            elif gender != 2:
                                ui.notify('申し訳ありません、この募集は女性限定です。', type='negative', position='top')
                                return
                                
                        res = join_flat_recruitment(target_room_id, current_user_id)
                        ui.notify(res['message'], type='positive' if res['status'] == 'success' else 'warning', position='top')
                        if res['status'] == 'success':
                            dialog.close()
                            refresh_cb()
                    ui.button('混ざる', icon='login', on_click=lambda: handle_join()).classes('bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')
                else:
                    ui.button('満員御礼', icon='lock').props('disable').classes('bg-slate-700 text-white/50 text-xs font-bold h-10 px-4 rounded-lg shrink-0')

    dialog.open()


def draw_flat_special_card(room, current_user_id, is_su, refresh_cb, enter_chat_cb):
    """ダッシュボードやカレンダーに配置する、特別急募ふらっとカードの描画"""
    room_id = room.get('id')
    participants = room.get('participant_ids') or []
    assigned_names = room.get('assigned_names', {})
    current_members = len(participants)
    max_members = room.get('target_count') or 3
    remaining = max_members - current_members
    is_joined = current_user_id in participants
    is_host = str(room.get('created_by')) == str(current_user_id)
    
    host_pseudo_name = room.get('pseudo_name', '名無しのゲスト')
    avatar_url = get_anonymous_avatar(host_pseudo_name)
    
    unique_suffix = uuid.uuid4().hex[:8]
    timer_id = f"timer-{room_id}-{unique_suffix}"
    progress_id = f"progress-{room_id}-{unique_suffix}"

    expires_at_str = room.get('expires_at', '')
    try:
        expire_dt = date_parser.parse(expires_at_str)
        expire_ts = int(expire_dt.timestamp() * 1000)
    except Exception:
        expire_ts = 0

    card_styles = 'w-full bg-white/95 dark:bg-slate-900/60 border border-cyan-400/60 dark:border-cyan-500/40 rounded-xl p-4 shadow-[0_0_15px_rgba(6,182,212,0.15)] flex flex-col gap-2 relative overflow-hidden backdrop-blur-sm'
    
    with ui.card().classes(card_styles).style('padding: 14px !important; gap: 8px !important;'):
        with ui.row().classes('w-full justify-between items-start no-wrap'):
            with ui.row().classes('items-center gap-2.5 overflow-hidden'):
                ui.image(avatar_url).classes('w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 border border-cyan-400/60 shrink-0')
                with ui.column().classes('gap-0 overflow-hidden'):
                    ui.label(host_pseudo_name).classes('font-bold text-cyan-700 dark:text-cyan-400 text-xs truncate')
                    with ui.row().classes('gap-1 items-center mt-0.5'):
                        ui.label(room.get('genre', 'ふらっと')).classes('bg-cyan-100 dark:bg-cyan-950 text-cyan-700 dark:text-cyan-400 border border-cyan-300 dark:border-cyan-500/30 text-[9px] px-1.5 py-0.5 rounded font-bold leading-none')
                        ui.label(room.get('timing', '今すぐ')).classes('bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-500/20 text-[9px] px-1.5 py-0.5 rounded font-bold leading-none')
            
            status_bg = 'bg-cyan-500' if remaining > 0 else 'bg-amber-500'
            status_text = f'急募 あと{remaining}人' if remaining > 0 else '作戦会議中'
            ui.label(status_text).classes(f'{status_bg} text-white text-[10px] font-bold px-2 py-1 rounded shadow-md shrink-0 leading-none')

        with ui.column().classes('w-full bg-slate-100/80 dark:bg-black/20 p-2.5 rounded-lg border border-slate-200 dark:border-white/5 gap-1'):
            with ui.row().classes('items-center gap-1'):
                ui.icon('place', size='12px').classes('text-cyan-600 dark:text-cyan-400')
                ui.label(room.get('location', '未定')).classes('text-[11px] font-bold text-cyan-700 dark:text-cyan-300 truncate')
            ui.label(room.get('description', '')).classes('text-xs text-slate-600 dark:text-slate-300 line-clamp-2 leading-relaxed')

        with ui.row().classes('w-full justify-between items-end mt-1'):
            with ui.column().classes('gap-0.5'):
                if is_joined:
                    my_name = assigned_names.get(current_user_id, "あなた")
                    ui.label(f"あなたは「{my_name}」です").classes('text-[9px] text-cyan-600 dark:text-cyan-400 font-black animate-pulse')
                else:
                    ui.label("現在の突発メンバー").classes('text-[9px] text-slate-400 dark:text-white/40')
                
                with ui.row().classes('items-center -space-x-1.5'):
                    for idx, pid in enumerate(participants):
                        p_name = assigned_names.get(pid, 'ゲスト')
                        av_url = get_anonymous_avatar(p_name)
                        z_index = 100 - idx
                        ml_style = 'margin-left: -10px;' if idx > 0 else 'margin-left: 0px;'
                        ui.image(av_url).style(f'position: relative; z-index: {z_index}; {ml_style}').classes('w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 border-2 border-white dark:border-slate-950 shadow-md')

            with ui.row().classes('gap-1.5 items-center shrink-0 no-wrap'):
                if is_host or is_su:
                    def handle_card_delete_direct():
                        with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-80 p-6'):
                            ui.label('この募集を完全に削除しますか？').classes('text-base font-bold text-red-400')
                            with ui.row().classes('w-full justify-end mt-6 gap-3'):
                                ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                                def execute_delete():
                                    delete_flat_recruitment(room_id)
                                    ui.notify('募集を完全に消去しました。', type='negative', position='top')
                                    confirm_dialog.close()
                                    refresh_cb()
                                ui.button('削除する', on_click=execute_delete).classes('bg-red-600 hover:bg-red-500 font-bold')
                        confirm_dialog.open()
                    ui.button(icon='delete', on_click=handle_card_delete_direct).props('flat round size=xs').classes('text-red-500 dark:text-red-400 opacity-40 hover:opacity-100 transition shrink-0')

                ui.button('詳細', on_click=lambda: open_flat_detail_dialog(room, current_user_id, is_su, refresh_cb, enter_chat_cb)).classes('bg-cyan-600 dark:bg-cyan-800 hover:bg-cyan-500 text-white text-[10px] px-2 py-0.5 rounded')
                
                if is_joined:
                    if remaining > 0:
                        ui.label('待機中...').classes('bg-cyan-100 dark:bg-cyan-900 text-cyan-700 dark:text-cyan-300 border border-cyan-300 dark:border-cyan-500/20 text-[10px] px-2 py-1 font-bold rounded')
                    else:
                        ui.button('会議室へ', icon='meeting_room', on_click=lambda: enter_chat_cb(room_id)).classes('bg-amber-500 dark:bg-amber-600 hover:bg-amber-400 text-white text-[10px] px-2 py-0.5 rounded animate-bounce')
                else:
                    if remaining > 0:
                        async def handle_join_direct():
                            profile = get_safe_profile(current_user_id)
                            gender = profile.get('gender', 0)
                            
                            if room.get('genre') == '👩 女子会':
                                if gender == 0:
                                    ui.notify('女子会に参加するため、プロフィールで「性別」を設定してください！', type='warning', position='top', timeout=5000)
                                    show_profile_dialog(current_user_id, current_user_id)
                                    return
                                elif gender != 2:
                                    ui.notify('申し訳ありません、この募集は女性限定です。', type='negative', position='top')
                                    return
                                    
                            res = join_flat_recruitment(room_id, current_user_id)
                            ui.notify(res['message'], type='positive' if res['status'] == 'success' else 'warning', position='top')
                            if res['status'] == 'success':
                                refresh_cb()
                        ui.button('混ざる', icon='login', on_click=handle_join_direct).classes('bg-cyan-500 dark:bg-cyan-600 hover:bg-cyan-400 text-white text-[10px] px-2 py-0.5 rounded')
                    else:
                        ui.button('満員', icon='lock').props('disable').classes('bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-white/30 text-[10px] px-2 py-0.5 rounded')

        with ui.row().classes('w-full items-center justify-between mt-1 pt-1 border-t border-slate-200 dark:border-white/5 no-wrap'):
            with ui.row().classes('items-center gap-1.5 shrink-0 no-wrap'):
                ui.label('本日限り').classes('bg-red-500 dark:bg-red-600 text-white font-black text-[8px] px-1.5 py-0.5 rounded select-none tracking-tighter')
                ui.html(f'<span id="{timer_id}" class="text-[10px] font-mono text-cyan-600 dark:text-cyan-400 font-bold select-none">⏳ 消滅まであと --:--:--</span>')
            
            ui.html(f'<div class="w-24 h-1.5 bg-slate-200 dark:bg-white/10 rounded-full overflow-hidden border border-slate-300 dark:border-white/5"><div id="{progress_id}" class="h-full transition-all duration-1000 ease-linear" style="width: 100%;"></div></div>')

        ui.run_javascript(f"""
        (function() {{
            const targetId = "{timer_id}";
            const progressId = "{progress_id}";
            const expireTime = {expire_ts}; 
            const maxDuration = 3 * 60 * 60 * 1000; 

            function initTimer() {{
                const txtEl = document.getElementById(targetId);
                const barEl = document.getElementById(progressId);
                
                if (!txtEl || !barEl) {{
                    setTimeout(initTimer, 100);
                    return;
                }}

                function updateCounter() {{
                    const currentTxt = document.getElementById(targetId);
                    const currentBar = document.getElementById(progressId);

                    if (!currentTxt) return; 

                    const now = new Date().getTime();
                    const diff = expireTime - now;

                    if (diff <= 0) {{
                        currentTxt.innerHTML = "⏳ 終了しました";
                        if (currentBar) {{
                            currentBar.style.width = "0%";
                            currentBar.className = "h-full bg-red-500 dark:bg-red-600";
                        }}
                        return;
                    }}

                    const hours = String(Math.floor(diff / (1000 * 60 * 60))).padStart(2, '0');
                    const minutes = String(Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))).padStart(2, '0');
                    const seconds = String(Math.floor((diff % (1000 * 60)) / 1000)).padStart(2, '0');
                    currentTxt.innerHTML = `⏳ 消滅まであと ${{hours}}:${{minutes}}:${{seconds}}`;

                    if (currentBar) {{
                        const pct = Math.min(100, Math.max(0, (diff / maxDuration) * 100));
                        currentBar.style.width = pct + "%";
                        
                        if (diff > 2 * 60 * 60 * 1000) {{
                            currentBar.className = "h-full bg-cyan-400 shadow-[0_0_8px_#06b6d4]";
                        }} else if (diff > 1 * 60 * 60 * 1000) {{
                            currentBar.className = "h-full bg-amber-400 shadow-[0_0_8px_#fbbf24]";
                        }} else {{
                            currentBar.className = "h-full bg-red-500 shadow-[0_0_8px_#ef4444] animate-pulse";
                        }}
                    }}

                    setTimeout(updateCounter, 1000);
                }}
                
                updateCounter();
            }}
            
            initTimer();
        }})();
        """)


def confirm_and_open_flat_dialog(current_user_id, is_su, refresh_cb, enter_chat_cb):
    """募集ボタン押下時のルール確認ワンクッションダイアログ"""
    with ui.dialog() as confirm_dialog, ui.card().classes('w-full max-w-sm bg-white/95 dark:bg-slate-900/90 border border-cyan-400/60 dark:border-cyan-500/40 text-slate-800 dark:text-white flex flex-col gap-4 backdrop-blur-md rounded-2xl p-6 shadow-2xl'):
        with ui.row().classes('w-full items-center gap-2 border-b border-cyan-500/20 pb-3'):
            ui.icon('info', size='sm', color='cyan-500')
            ui.label('「ふらっと」募集の確認').classes('text-lg font-bold text-cyan-700 dark:text-cyan-400')
        
        with ui.column().classes('gap-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed'):
            ui.label('通常の公式イベントとは異なり、以下の特殊なルールで開始されます。')
            
            with ui.row().classes('items-start gap-2 no-wrap bg-slate-100 dark:bg-white/5 p-3 rounded-xl border border-slate-200 dark:border-white/5'):
                ui.icon('timer', size='sm').classes('text-cyan-600 dark:text-cyan-400 mt-0.5')
                with ui.column().classes('gap-0 flex-grow'):
                    ui.label('3時間で自動消滅').classes('font-bold text-cyan-700 dark:text-cyan-300')
                    ui.label('募集開始から募集人数に達しないまま3時間経つと、自動的に画面から消え去ります。募集人数に達した時点で会議室が作成され、入室できるようになります。その場合は参加者以外には「満員」と表示され参加はできません。').classes('text-xs')
                    
            with ui.row().classes('items-start gap-2 no-wrap bg-slate-100 dark:bg-white/5 p-3 rounded-xl border border-slate-200 dark:border-white/5'):
                ui.icon('masks', size='sm').classes('text-cyan-600 dark:text-cyan-400 mt-0.5')
                with ui.column().classes('gap-0 flex-grow'):
                    ui.label('匿名（通り名）での作戦会議').classes('font-bold text-cyan-700 dark:text-cyan-300')
                    ui.label('作戦会議中、全員が合意して公式化するまでは、お互い誰か分からない状態で相談します。合意に至らず抜けたとしても誰が抜けたかわからないようになっており、その場合は作戦会議が中断され、募集状態に戻ります。').classes('text-xs')
                    
            with ui.row().classes('items-start gap-2 no-wrap bg-slate-100 dark:bg-white/5 p-3 rounded-xl border border-slate-200 dark:border-white/5'):
                ui.icon('celebration', size='sm').classes('text-cyan-600 dark:text-cyan-400 mt-0.5')
                with ui.column().classes('gap-0 flex-grow'):
                    ui.label('合意で公式イベントへ昇格').classes('font-bold text-cyan-700 dark:text-cyan-300')
                    ui.label('人数が揃って全員が合意すると、公式イベントに昇格し実名チャットに切り替わります。ここからはイベント一覧とチャット一覧に表示され、どなたでも参加できるようになります。この時点で場所や時間など詳細をお決めください。').classes('text-xs')

        with ui.row().classes('w-full justify-end mt-2 gap-3'):
            ui.button('やめる', on_click=confirm_dialog.close).props('flat color=grey').classes('font-bold')
            def proceed():
                confirm_dialog.close()
                open_create_flat_dialog(current_user_id, is_su, refresh_cb, enter_chat_cb)
            ui.button('了承して作成', on_click=proceed).props('outline color=primary').classes('font-bold shadow-sm')
            
    confirm_dialog.open()


def open_create_flat_dialog(current_user_id, is_su, refresh_cb, enter_chat_cb):
    """新しく突発ふらっと募集を作成するダイアログ本体"""
    from database.profile_db import get_safe_profile
    from components.comp_profile import show_profile_dialog
    profile = get_safe_profile(current_user_id)

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-slate-200 dark:border-white/10 text-slate-800 dark:text-white'):
        ui.label('🍻 新しくふらっと募集する').classes('text-lg font-bold text-slate-800 dark:text-white mb-4')
        
        genre = ui.select(
            ['🍺 ガッツリ飲み', '☕️ お茶・カフェ', '🍚 サク飯', '👩 女子会', '🏍️ 趣味トーク'], 
            label='ジャンル', 
            value='🍺 ガッツリ飲み'
        ).classes('w-full mb-2').props('color="primary" outlined')
        
        timing = ui.select(
            ['[即]今すぐ', '[1H]1時間後', '[夜]夜から'], 
            label='開始目安', 
            value='[即]今すぐ'
        ).classes('w-full mb-2').props('color="primary" outlined')
        
        capacity = ui.select(
            [3, 4, 5, 6, 7, 8], 
            label='最小催行人数', 
            value=3
        ).classes('w-full mb-2').props('color="primary" outlined')
        
        location = ui.input(
            label='場所 (例: 中野駅北口)'
        ).classes('w-full mb-2').props('color="primary" outlined')
        
        description = ui.input(
            label='ひとこと (例: サクッと1杯だけ！)'
        ).classes('w-full mb-4').props('color="primary" outlined')
        
        def submit():
            if not location.value or not description.value:
                ui.notify('場所とひとことは入力必須です', type='warning', position='top')
                return
            
            if genre.value == '👩 女子会':
                user_gender = profile.get('gender', 0)
                if user_gender == 0:
                    ui.notify('「女子会」を募集するには、プロフィールで性別を設定してください！', type='warning', position='top', timeout=5000)
                    dialog.close()
                    show_profile_dialog(current_user_id, current_user_id)
                    return
                elif user_gender != 2:
                    ui.notify('「女子会」の募集は女性ユーザーのみ作成可能です。', type='negative', position='top')
                    return

            try:
                create_flat_recruitment(current_user_id, capacity.value, genre.value, location.value, description.value, timing.value)
                ui.notify('突発募集を開始しました！', type='positive', position='top')
                dialog.close()
                refresh_all_cb=refresh_cb
                refresh_all_cb()
            except Exception as e:
                ui.notify(f'募集に失敗しました: {e}', type='negative', position='top')
        
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('キャンセル', on_click=dialog.close).props('flat color=grey').classes('font-bold')
            ui.button('募集する', on_click=submit).props('outline color=primary').classes('font-bold shadow-sm')
            
    dialog.open()