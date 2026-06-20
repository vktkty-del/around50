from nicegui import ui
import base64
from database.flat_db import (
    get_active_flats, create_flat_recruitment, join_flat_recruitment, 
    silent_leave_flat, delete_flat_recruitment
)
from database.profile_db import get_safe_profile
from components.comp_profile import show_profile_dialog

def get_anonymous_avatar(pseudo_name: str) -> str:
    """通り名をシード値にして固有の仮面アイコン（ボット）を生成"""
    safe_seed = base64.urlsafe_b64encode(pseudo_name.encode()).decode()[:15]
    return f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}"

# ★即飲み(FLAT)詳細 ＆ 参加/サイレント離脱/募集削除ダイアログ
def open_flat_detail_dialog(room, current_user_id, is_su, refresh_cb, enter_chat_cb):
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

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-cyan-500/30 text-white flex flex-col gap-4'):
        # ヘッダー
        with ui.row().classes('w-full items-center justify-between no-wrap'):
            ui.label('ふらっと 詳細').classes('text-base sm:text-lg font-bold text-white truncate')
            ui.badge(room.get('genre', 'ジャンル未定'), color='cyan-600').classes('text-[10px] px-2 py-0.5 shrink-0')

        # 基本情報
        with ui.column().classes('w-full gap-1.5'):
            with ui.row().classes('items-center gap-2'):
                ui.image(avatar_url).classes('w-6 h-6 rounded-full bg-slate-800 border border-cyan-500/50')
                ui.label(f"主催者: {host_pseudo_name}").classes('text-xs text-white/70')
            
            with ui.row().classes('items-center gap-2 text-xs text-white/90'):
                ui.icon('access_time', size='14px', color='cyan-300')
                ui.label(f"開始目安: {room.get('timing', '時間未定')}")
                
            if room.get('location'):
                with ui.row().classes('items-center gap-2 text-xs text-white/90'):
                    ui.icon('place', size='14px', color='cyan-300')
                    ui.label(f"場所: {room.get('location')}")

        # ひとこと説明
        if room.get('description'):
            ui.label(room.get('description')).classes('text-sm text-slate-200 bg-black/30 p-3.5 rounded-lg w-full whitespace-pre-wrap')

        # 参加者のアバター重ね表示
        if participants:
            with ui.column().classes('w-full gap-1 mt-1'):
                ui.label('現在のメンバー:').classes('text-[10px] text-white/50')
                with ui.row().classes('items-center gap-0'):
                    for idx, pid in enumerate(participants):
                        p_name = assigned_names.get(pid, 'ゲスト')
                        av_url = get_anonymous_avatar(p_name)
                        z_index = 100 - idx
                        ml_style = 'margin-left: -14px;' if idx > 0 else 'margin-left: 0px;'
                        ui.image(av_url).style(f'position: relative; z-index: {z_index}; {ml_style}').classes('w-8 h-8 rounded-full bg-slate-800 border-2 border-cyan-500/30 shadow-md').tooltip(p_name)

        # アクションボタン
        with ui.row().classes('w-full justify-end gap-2 mt-2 items-center no-wrap'):
            ui.button('閉じる', on_click=dialog.close).classes('bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')

            # ★ 修正: asyncを外し、通常の同期関数（def）に変更してクリック時のコルーチン死滅バグを完全に解消
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

                # こちらはダイアログ内でroom_idが一意のため、単純に呼び出すだけで100%安全に動作します
                ui.button('募集を削除', icon='delete', on_click=handle_delete).classes('bg-red-800 hover:bg-red-700 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')

            if is_joined:
                if is_host:
                    ui.badge('👑 主催者', color='cyan-600').classes('text-xs px-3 py-2 h-10 flex items-center rounded-lg shrink-0 font-bold')
                else:
                    if remaining > 0:
                        # ★ 修正: こちらも同様に async を外した通常の同期関数へ修正
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
                        # 性別チェック＆強制プロフィール設定誘導
                        profile = get_safe_profile(current_user_id)
                        gender = profile.get('gender', 0)
                        
                        if gender == 0:
                            ui.notify('参加前にプロフィールで「性別」を設定してください！', type='warning', position='top', timeout=5000)
                            dialog.close()
                            show_profile_dialog(current_user_id, current_user_id)
                            return
                        
                        if current_room.get('genre') == '👩 女子会' and gender != 2:
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


def render_flats(current_user_id: str, is_su: bool, refresh_cb, enter_chat_cb):
    ui.label('ふらっと (即飲み募集)').classes('text-2xl font-extrabold tracking-wider text-white')
    ui.label('「今から飲める人」が集うリアルタイム空間（3時間自動消去）').classes('text-xs text-white/50 -mt-4')
    
    # ★ 改善: ループの肥大化を防ぎ、LateBindingバグを完璧に防止するため、カード側の削除ダイアログをここ（同期関数）に定義します
    def handle_card_delete(target_flat_id):
        with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-80 p-6'):
            ui.label('この募集を完全に削除しますか？').classes('text-base font-bold text-red-400')
            with ui.row().classes('w-full justify-end mt-6 gap-3'):
                ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                
                def execute_delete():
                    delete_flat_recruitment(target_flat_id)
                    ui.notify('募集を完全に消去しました。', type='negative', position='top')
                    confirm_dialog.close()
                    draw_cards.refresh()
                    
                ui.button('削除する', on_click=execute_delete).classes('bg-red-600 hover:bg-red-500 font-bold')
        confirm_dialog.open()

    def open_create_dialog():
        # 募集作成前の性別チェック
        profile = get_safe_profile(current_user_id)
        if profile.get('gender', 0) == 0:
            ui.notify('募集を作成する前に、プロフィールで「性別」を設定してください！', type='warning', position='top', timeout=5000)
            show_profile_dialog(current_user_id, current_user_id)
            return

        with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-cyan-500/30'):
            ui.label('🍻 新しくふらっと募集する').classes('text-lg font-bold text-white mb-4')
            
            genre = ui.select(
                ['🍺 ガッツリ飲み', '☕️ お茶・カフェ', '🍚 サク飯', '👩 女子会', '🏍️ 趣味トーク'], 
                label='ジャンル', 
                value='🍺 ガッツリ飲み'
            ).classes('w-full mb-2').props('dark color="cyan"')
            
            timing = ui.select(
                ['[即]今すぐ', '[1H]1時間後', '[夜]夜から'], 
                label='開始目安', 
                value='[即]今すぐ'
            ).classes('w-full mb-2').props('dark color="cyan"')
            
            capacity = ui.select(
                [3, 4, 5, 6, 7, 8], 
                label='最小催行人数（開催には設定した人数の参加が必要です）', 
                value=3
            ).classes('w-full mb-2').props('dark color="cyan"')
            
            location = ui.input(
                label='場所 (例: 中野駅北口)'
            ).classes('w-full mb-2').props('dark color="cyan"')
            
            description = ui.input(
                label='ひとこと (例: サクッと1杯だけ！)'
            ).classes('w-full mb-4').props('dark color="cyan"')
            
            def submit():
                if not location.value or not description.value:
                    ui.notify('場所とひとことは入力必須です', type='warning', position='top')
                    return
                    
                # 女子会募集のガード
                if genre.value == '👩 女子会' and profile.get('gender') != 2:
                    ui.notify('「女子会」の募集は女性ユーザーのみ作成可能です。', type='negative', position='top')
                    return
                    
                try:
                    create_flat_recruitment(current_user_id, capacity.value, genre.value, location.value, description.value, timing.value)
                    ui.notify('募集を開始しました！', type='positive', position='top')
                    dialog.close()
                    draw_cards.refresh()
                except Exception as e:
                    ui.notify(f'募集に失敗しました（DBエラー）: {e}', type='negative', position='top')
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('キャンセル', on_click=dialog.close).classes('bg-slate-700 text-white')
                ui.button('募集する', on_click=submit).classes('bg-cyan-600 font-bold text-white')
        dialog.open()

    ui.button('🍻 新しく即飲みを募集する', on_click=open_create_dialog).classes('w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl py-3 shadow-lg my-4')
    
    last_state_hash = None
    
    @ui.refreshable
    def draw_cards():
        nonlocal last_state_hash
        active_flats = get_active_flats()
        current_state = [f"{f.get('id')}_{len(f.get('participant_ids', []))}_{f.get('status')}" for f in active_flats]
        last_state_hash = str(current_state)
        
        if not active_flats:
            with ui.column().classes('w-full items-center justify-center p-8 hibi-glass rounded-xl mt-4'):
                ui.icon('nights_stay', size='3rem', color='white').classes('opacity-30')
                ui.label('現在、募集中のふらっとはありません。').classes('text-white/50 text-sm mt-2')
            return

        for room in active_flats:
            room_id = room.get('id')
            participants = room.get('participant_ids') or []
            assigned_names = room.get('assigned_names', {})
            current_members = len(participants)
            max_members = room.get('target_count') or 3
            remaining = max_members - current_members
            is_joined = current_user_id in participants
            host_pseudo_name = room.get('pseudo_name', '名無しのゲスト')
            avatar_url = get_anonymous_avatar(host_pseudo_name)
            
            is_host = str(room.get('created_by')) == str(current_user_id)

            with ui.card().classes('w-full hibi-glass rounded-xl p-5 shadow-2xl border-l-4 border-cyan-500 mb-4'):
                with ui.row().classes('w-full justify-between items-start'):
                    with ui.row().classes('items-center gap-3'):
                        ui.image(avatar_url).classes('w-10 h-10 rounded-full bg-slate-800 border border-cyan-500/50')
                        with ui.column().classes('gap-0'):
                            ui.label(host_pseudo_name).classes('font-bold text-white text-sm')
                            with ui.row().classes('gap-1'):
                                ui.badge(room.get('genre', 'ジャンル未定'), color='cyan-600').classes('text-[10px] px-1.5 py-0')
                                ui.badge(room.get('timing', '時間未定'), color='indigo-500').classes('text-[10px] px-1.5 py-0')
                    
                    status_color = 'cyan-500' if remaining > 0 else 'red-500'
                    status_text = '募集中' if remaining > 0 else '満員'
                    ui.badge(status_text, color=status_color).classes('text-xs px-2 py-0.5 shadow-md')
                
                with ui.column().classes('w-full my-3 bg-slate-950/40 p-3 rounded-lg border border-white/5'):
                    if room.get('location'):
                        with ui.row().classes('items-center gap-1 mb-1'):
                            ui.icon('place', size='14px', color='cyan-400')
                            ui.label(room.get('location')).classes('text-xs font-bold text-cyan-300')
                    ui.label(room.get('description', '')).classes('text-sm text-slate-200 line-clamp-2')
                
                with ui.row().classes('w-full justify-between items-end pt-2'):
                    with ui.column().classes('gap-1'):
                        if is_joined:
                            my_name = assigned_names.get(current_user_id, "あなた")
                            ui.label(f"あなたは「{my_name}」です").classes('text-[10px] text-cyan-400 font-bold')
                        else:
                            ui.label("現在の参加者").classes('text-[10px] text-white/50')
                            
                        with ui.row().classes('items-center gap-0'):
                            for idx, pid in enumerate(participants):
                                p_name = assigned_names.get(pid, 'ゲスト')
                                av_url = get_anonymous_avatar(p_name)
                                z_index = 100 - idx
                                ml_style = 'margin-left: -14px;' if idx > 0 else 'margin-left: 0px;'
                                ui.image(av_url).style(f'position: relative; z-index: {z_index}; {ml_style}').classes('w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-900 shadow-md')

                    def handle_join(target_room_id=room_id, current_room=room):
                        profile = get_safe_profile(current_user_id)
                        gender = profile.get('gender', 0)
                        
                        if gender == 0:
                            ui.notify('参加前にプロフィールで「性別」を設定してください！', type='warning', position='top', timeout=5000)
                            show_profile_dialog(current_user_id, current_user_id)
                            return
                        
                        if current_room.get('genre') == '👩 女子会' and gender != 2:
                            ui.notify('申し訳ありません、この募集は女性限定です。', type='negative', position='top')
                            return

                        res = join_flat_recruitment(target_room_id, current_user_id)
                        ui.notify(res['message'], type='positive' if res['status'] == 'success' else 'warning', position='top')
                        if res['status'] == 'success':
                            draw_cards.refresh()

                    with ui.column().classes('items-end gap-1'):
                        if is_joined:
                            if remaining > 0:
                                ui.label(f"あと {remaining} 人 待機中...").classes('text-sm text-cyan-300 font-bold animate-pulse mb-0.5')
                            else:
                                ui.label("作戦会議が始まりました！").classes('text-sm text-amber-400 font-bold mb-0.5')
                        else:
                            if remaining > 0:
                                ui.label(f"あと {remaining} 人 参加可能！").classes('text-sm text-cyan-300 font-bold animate-pulse mb-0.5')
                            else:
                                ui.label("作戦会議中（満員）").classes('text-sm text-red-400 font-bold mb-0.5')

                        with ui.row().classes('gap-1.5 items-center no-wrap'):
                            
                            # ★ 修正: ループ内遅延評価対策 ＆ lambda を「引数1つ受ける(自動eを捨てる)」形に再定義し、確実にUUIDを紐付け！
                            if is_host or is_su:
                                # ラムダのデフォルト引数「r_id=room_id」でUUIDを瞬時にバインドし、NiceGUIのClickEvent（第1引数 _）を確実に遮断します
                                ui.button(icon='delete', on_click=lambda _, r_id=room_id: handle_card_delete(r_id)).props('flat round color=red-400 size=xs').classes('opacity-30 hover:opacity-100 transition shrink-0 ml-1').tooltip('この募集を削除')

                            # ★ 修正: こちらも同様に、lambda で包んで正しく部屋IDを渡せるように同期
                            ui.button(
                                '詳細を見る', 
                                icon='info', 
                                on_click=lambda: open_flat_detail_dialog(room, current_user_id, is_su, draw_cards.refresh, enter_chat_cb)
                            ).classes('bg-cyan-700 hover:bg-cyan-600 text-white text-[10px] px-2 py-0.5 min-h-0 rounded-lg')
                            
                            if is_joined:
                                if remaining > 0:
                                    if is_host:
                                        ui.button('主催イベント', icon='star').props('disable flat').classes('text-cyan-400 text-xs font-bold px-1')
                                    else:
                                        ui.button('参加済み', icon='check_circle').props('disable flat').classes('text-cyan-400 text-xs font-bold px-1')
                                else:
                                    ui.button('会議室へ', icon='meeting_room', on_click=lambda r=room: enter_chat_cb(r['id'])).classes('bg-amber-600 hover:bg-amber-500 text-white text-[10px] px-2.5 py-0.5 min-h-0 rounded-lg animate-bounce')
                            else:
                                if remaining > 0:
                                    ui.button('混ざる', icon='login', on_click=lambda: handle_join()).classes('bg-cyan-600 hover:bg-cyan-500 text-white text-[10px] px-2.5 py-0.5 min-h-0 rounded-lg')
                                else:
                                    ui.button('満員御礼', icon='lock').props('disable').classes('bg-slate-700 text-white/50 text-[10px] px-2.5 py-0.5 min-h-0 rounded-lg')

    draw_cards()
    
    def check_updates():
        active_flats = get_active_flats()
        current_state = [f"{f.get('id')}_{len(f.get('participant_ids', []))}_{f.get('status')}" for f in active_flats]
        if str(current_state) != last_state_hash:
            draw_cards.refresh()
            
    ui.timer(3.0, check_updates)