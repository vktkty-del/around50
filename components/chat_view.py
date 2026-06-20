# components/chat_view.py
from nicegui import app, ui
from datetime import datetime, timedelta, timezone
import inspect
import time
import re

from database.chat_db import (
    fetch_chat_rooms, fetch_messages, send_message, mark_as_read, 
    create_chat_room, save_chat_image_local, delete_chat_room, 
    delete_message, update_chat_message, add_reaction, save_stamp_locally,
    GLOBAL_CHAT_VIEWERS, GLOBAL_KNOCK_REQUESTS, send_knock_request,
    check_knock_status, approve_knock_request, fetch_pending_knocks
)
from utils.validator import check_ng_words
from components.lightbox import lightbox_image
from themes import THEMES

try:
    from .stamps import STAMP_LIST
except ImportError:
    from stamps import STAMP_LIST

from dateutil import parser as date_parser
from config.supabase_config import get_supabase
supabase = get_supabase()

# ==========================================
# ★ ジャンル定義マスターデータ
# ==========================================
GENRES = {
    'all': {
        'label': 'すべて', 
        'icon': 'apps', 
        'color': 'slate-400', 
        'bg_css': 'bg-slate-500/10 border-slate-500/20 text-slate-400'
    },
    'daily': {
        'label': '日常', 
        'icon': 'wb_sunny', 
        'color': 'amber-400', 
        'bg_css': 'bg-amber-500/10 border-amber-500/30 text-amber-400'
    },
    'alcohol': {
        'label': 'お酒', 
        'icon': 'local_bar', 
        'color': 'pink-400', 
        'bg_css': 'bg-pink-500/10 border-pink-500/30 text-pink-400'
    },
    'hobby': {
        'label': '音楽', 
        'icon': 'music_note', 
        'color': 'violet-400', 
        'bg_css': 'bg-violet-500/10 border-violet-500/30 text-violet-400'
    },
    'event': {
        'label': 'イベント', 
        'icon': 'flag', 
        'color': 'indigo-400', 
        'bg_css': 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'
    },
    'locked': {
        'label': '鍵付き', 
        'icon': 'lock', 
        'color': 'rose-400', 
        'bg_css': 'bg-rose-500/10 border-rose-500/30 text-rose-400'
    }
}


def draw_chat_view(current_user_id: str, initial_room_id: str = None):
    """PC/スマホ最適化・ジャンルフィルター・合言葉・ノック承認対応型 2カラムチャットビュー"""
    
    role_lower = str(app.storage.user.get('role', '')).lower()
    is_su = role_lower in ['superuser', 'admin', 'owner', 'master', 'submaster']
    user_metadata = app.storage.user.get('user_metadata', {})
    current_user_name = user_metadata.get('name', '名無し')

    # テーマカラー適用
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)
    dark_val = 'false' if is_light else 'true'

    # スタイル変数
    c_bg = 'bg-white border-slate-200 text-slate-900 dark:bg-slate-900 dark:border-white/20 dark:text-white'
    c_btn_color = 'primary' if is_light else 'white'
    c_text = 'text-slate-800 dark:text-white' # 確実に白にします
    c_text_muted = 'text-slate-500 dark:text-white/60' # 読みやすい半透明白
    c_border = 'border-slate-200 dark:border-white/10'
    c_header_bg = 'bg-slate-100/80 border-b border-slate-200/60' if is_light else 'bg-slate-950/50 border-b border-white/10'
    c_input_container_bg = 'bg-slate-150 border-t border-slate-200' if is_light else 'bg-slate-900 border-t border-white/10'
    c_input_bg = 'bg-white border-slate-200 text-slate-800' if is_light else 'bg-white/5 border-white/10 text-white'
    c_msg_other_bg = 'bg-slate-200 text-slate-800' if is_light else 'bg-indigo-600/80 text-white'

    # パスワード解除セッションキャッシュ
    if 'unlocked_rooms' not in app.storage.user:
        app.storage.user['unlocked_rooms'] = []

    # 画面全体の初期状態設定
    initial_room = None
    if initial_room_id:
        rooms = fetch_chat_rooms()
        for r in rooms:
            if str(r['id']) == str(initial_room_id):
                # 解除済み、もしくは鍵なし、もしくはSUなら初期部屋に設定
                if not r.get('password') or str(r['id']) in app.storage.user['unlocked_rooms'] or is_su:
                    initial_room = r
                break

    state = {
        'active_room': initial_room,
        'selected_genre': 'all',  # フィルター用
        'rendered_msg_ids': set(),
        'read_count_labels': {},
        'reaction_containers': {},
        'message_elements': {},
        'typing_container': None,
        'typing_label': None,
        'pending_image': None,
        'reply_target': None,
        # ノック・認証状態
        'is_knocking': False,
        'knock_timer': None,
        'knock_expire_time': 0,
        # ★ 新規追加: 前回描画したヘッダー閲覧者アバターのハッシュ値記録用（点滅防止）
        'last_viewers_hash': "",
    }

    # ==========================================
    # リアクション
    # ==========================================
    def handle_reaction_click(msg_id, emoji_char, msg_owner_id, menu=None):
        if str(msg_owner_id) == str(current_user_id):
            ui.notify('自分の発言にはリアクションできません', color='warning', position='top')
            if menu: menu.close()
            return
        try:
            add_reaction(msg_id, current_user_id, emoji_char)
            sync_data()
            if menu: menu.close()
        except Exception as ex:
            ui.notify(str(ex), color='negative')
            if menu: menu.close()

    # ==========================================
    # 削除確認ダイアログ
    # ==========================================
    room_to_delete = {'id': None}
    with ui.dialog() as confirm_room_delete_dialog, ui.card().classes(f'{c_bg} w-80 p-6'):
        ui.label('発言もすべて削除されます、よろしいですか？').classes('text-base font-bold text-red-500')
        with ui.row().classes('w-full justify-end mt-6 gap-3'):
            ui.button('キャンセル', on_click=confirm_room_delete_dialog.close).props(f'flat color={c_btn_color}')
            def execute_room_delete():
                if not room_to_delete['id']: return
                try:
                    delete_chat_room(room_to_delete['id'])
                    ui.notify('ルームを完全に削除しました', color='negative')
                    if state['active_room'] and str(state['active_room']['id']) == str(room_to_delete['id']):
                        exit_active_room()
                    confirm_room_delete_dialog.close()
                    room_list_area.refresh()
                except Exception as ex:
                    ui.notify(f'削除エラー: {ex}', color='negative')
            ui.button('削除する', on_click=execute_room_delete).classes('bg-red-600 hover:bg-red-500 text-white font-bold')

    msg_to_delete = {'id': None}
    with ui.dialog() as confirm_msg_delete_dialog, ui.card().classes(f'{c_bg} w-80 p-6'):
        ui.label('このメッセージを削除します。よろしいですか？').classes('text-base font-bold text-red-500')
        with ui.row().classes('w-full justify-end mt-6 gap-3'):
            ui.button('キャンセル', on_click=confirm_msg_delete_dialog.close).props(f'flat color={c_btn_color}')
            def execute_msg_delete():
                if not msg_to_delete['id']: return
                try:
                    delete_message(msg_to_delete['id'])
                    ui.notify('メッセージを削除しました', color='positive')
                    confirm_msg_delete_dialog.close()
                    clear_chat_render_states()
                    sync_data()
                except Exception as ex:
                    ui.notify(f'削除エラー: {ex}', color='negative')
            ui.button('削除する', on_click=execute_msg_delete).classes('bg-red-600 hover:bg-red-500 text-white font-bold')

    # ==========================================
    # 【鍵付き】合言葉入力・ロック解除ダイアログ
    # ==========================================
    room_to_unlock = {'room_data': None}
    with ui.dialog() as password_dialog, ui.card().classes(f'{c_bg} w-80 p-6'):
        ui.label('🔓 鍵付きルーム').classes('text-lg font-bold text-rose-400')
        ui.label('このチャットルームに入るには「合言葉」が必要です。').classes(f'text-xs {c_text_muted} mb-2')
        input_pass = ui.input('合言葉を入力').classes('w-full').props(f':dark="{dark_val}" filled password autofocus').on('keydown.enter', lambda: execute_unlock())
        
        def execute_unlock():
            r = room_to_unlock['room_data']
            if not r: return
            pwd = input_pass.value or ""
            if pwd.strip() == r.get('password'):
                # アンロック成功、セッション保存
                unlocked = app.storage.user.get('unlocked_rooms', [])
                if str(r['id']) not in unlocked:
                    unlocked.append(str(r['id']))
                    app.storage.user['unlocked_rooms'] = unlocked
                
                ui.notify('ロックを解除しました！', color='positive')
                input_pass.set_value('')
                password_dialog.close()
                select_room_direct(r)
            else:
                ui.notify('合言葉が違います', color='negative')

        with ui.row().classes('w-full justify-end mt-4 gap-2'):
            ui.button('キャンセル', on_click=password_dialog.close).props(f'flat color={c_btn_color}')
            # SU限定：ノック送信ボタン
            if is_su:
                def trigger_su_knock():
                    r = room_to_unlock['room_data']
                    password_dialog.close()
                    start_knock_process(r)
                ui.button('ノックする', on_click=trigger_su_knock).classes('bg-amber-600 text-white font-bold').tooltip('合言葉がわからないのでメンバーにノックを要請します')
                
            ui.button('解除', on_click=execute_unlock).classes('bg-cyan-600 hover:bg-cyan-500 text-white font-bold')

    # ==========================================
    # 【ノック機能】SU用入室要請ポーリング・表示
    # ==========================================
    def start_knock_process(r):
        state['is_knocking'] = True
        state['active_room'] = r  # 選択中の仮の部屋をセットして画面を切り替える
        room_title_label.set_text(r['title'])
        
        # プレースホルダー、入力欄を一時退避して「ノック中」画面を起動
        update_responsive_visibility(entering_chat=True)
        clear_chat_render_states()
        
        # ノック開始をグローバルメモリに登録
        send_knock_request(r['id'], current_user_id, current_user_name)
        state['knock_expire_time'] = time.time() + 30
        
        # ノック画面描画
        with chat_scroll_container:
            with ui.column().classes('w-full h-full items-center justify-center py-20 gap-4') as knock_area:
                ui.spinner('audio', size='5rem', color='amber-500').classes('animate-pulse')
                ui.label('入室許可を求めて「ノック」しています...').classes(f'text-base font-bold text-amber-400')
                ui.label('現在この部屋にいるメンバーが「許可」ボタンを押すと自動的にチャットが開きます。').classes(f'text-xs {c_text_muted} text-center max-w-sm leading-relaxed')
                ui.button('ノックをキャンセルして戻る', on_click=exit_active_room).props('flat color=red-400')
        
        # 2秒おきに承認状況をポーリングチェック
        def poll_knock():
            if not state['is_knocking']:
                state['knock_timer'].cancel()
                return
            if time.time() > state['knock_expire_time']:
                ui.notify('応答がありませんでした（タイムアウト）', color='warning')
                exit_active_room()
                return
                
            if check_knock_status(r['id'], current_user_id):
                # 承認された！
                state['is_knocking'] = False
                state['knock_timer'].cancel()
                # アンロックリストに加える
                unlocked = app.storage.user.get('unlocked_rooms', [])
                if str(r['id']) not in unlocked:
                    unlocked.append(str(r['id']))
                    app.storage.user['unlocked_rooms'] = unlocked
                
                ui.notify('入室が許可されました！', color='positive')
                select_room_direct(r)

        state['knock_timer'] = ui.timer(2.0, poll_knock)

    # ==========================================
    # ルーム新規作成ダイアログ（シークレット動的トグル対応版）
    # ==========================================
    with ui.dialog() as new_room_dialog, ui.card().classes(f'{c_bg} w-[360px] p-6 shadow-2xl rounded-3xl'):
        ui.label('新しいルームを作成').classes('text-lg font-bold text-cyan-400 mb-2')
        new_title = ui.input('ルーム名（必須）').classes('w-full mb-3').props(f':dark="{dark_val}" filled autofocus')
        new_desc = ui.input('一言メッセージ（トピック）').classes('w-full mb-3').props(f':dark="{dark_val}" filled')
        
        # ★ 変更1：シークレット設定用チェックボックスを追加
        chk_secret = ui.checkbox('合言葉を設定する（シークレット）').classes('text-xs text-rose-400 font-bold mb-2')
        
        # ★ 変更2：合言葉入力欄を追加し、チェックが入っているときだけ表示(bind_visibility)させます
        new_pwd = ui.input('合言葉（シークレット用パスワード）').classes('w-full mb-4').props(f':dark="{dark_val}" filled password')
        new_pwd.bind_visibility_from(chk_secret, 'value')
        
        # ジャンル選択
        ui.label('ルームのジャンルを選択').classes(f'text-[10px] {c_text_muted} font-extrabold uppercase pl-1')
        selected_creation_genre = {'val': 'daily'}
        
        @ui.refreshable
        def draw_creation_genres():
            with ui.row().classes('w-full gap-2 mb-6 flex-wrap pl-1'):
                for key, g_info in GENRES.items():
                    if key == 'all' or key == 'locked': continue
                    is_sel = (selected_creation_genre['val'] == key)
                    bg = g_info['bg_css'] if is_sel else 'bg-white/5 border-white/5 text-white/40'
                    opacity = 'opacity-100 scale-105 border-[1.5px]' if is_sel else 'opacity-50 hover:opacity-85'
                    
                    ui.button(g_info['label'], icon=g_info['icon'], on_click=lambda k=key: (selected_creation_genre.update({'val': k}), draw_creation_genres.refresh()))\
                        .props('unelevated rounded size=sm')\
                        .classes(f'{bg} {opacity} font-bold transition-all px-3 py-1')

        draw_creation_genres()

        def handle_create():
            title = new_title.value
            if title and title.strip():
                try:
                    new_room = create_chat_room(
                        title=title.strip(),
                        created_by=current_user_id,
                        genre=selected_creation_genre['val'],
                        description=new_desc.value,
                        # ★ 変更3：チェックボックスにチェックが入っているときだけパスワードを適用します
                        password=new_pwd.value if chk_secret.value else None
                    )
                    # 初期化して閉じる
                    new_title.set_value('')
                    new_desc.set_value('')
                    new_pwd.set_value('')
                    chk_secret.set_value(False)  # チェックを外しておく
                    selected_creation_genre['val'] = 'daily'
                    new_room_dialog.close()
                    room_list_area.refresh()
                    
                    if new_room:
                        select_room_direct(new_room)
                    ui.notify('お洒落なルームを作成しました！', color='positive')
                except Exception as e:
                    ui.notify(f'作成エラー: {e}', color='negative')
            else:
                ui.notify('ルーム名を入力してください', color='warning')

        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('キャンセル', on_click=new_room_dialog.close).props(f'flat color={c_btn_color}')
            ui.button('作成する', on_click=handle_create).classes('bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-xl px-5')

    # ==========================================
    # 部屋一覧エリア
    # ==========================================
    @ui.refreshable
    def room_list_area():
        rooms = fetch_chat_rooms()
        
        # 過去イベント連携部屋の自動除外処理
        try:
            from config.supabase_config import get_supabase
            sb = get_supabase()
            events_res = sb.table("events").select("details, event_date").not_.is_("details", "null").execute()
            past_room_ids = []
            if events_res.data:
                now_time = datetime.now()
                for ev in events_res.data:
                    ev_date_str = ev.get('event_date')
                    room_id = ev.get('details')
                    if ev_date_str and room_id:
                        try:
                            ev_dt = date_parser.parse(ev_date_str)
                            is_past = ev_dt < (datetime.now(timezone.utc) if ev_dt.tzinfo else now_time)
                            if is_past: past_room_ids.append(str(room_id))
                        except Exception: pass
            rooms = [r for r in rooms if str(r['id']) not in past_room_ids]
        except Exception: pass

        # ジャンル・鍵によるフィルタリング
        filter_genre = state['selected_genre']
        if filter_genre != 'all':
            if filter_genre == 'locked':
                rooms = [r for r in rooms if r.get('password')]
            else:
                rooms = [r for r in rooms if r.get('genre') == filter_genre]

        if not rooms:
            with ui.column().classes('w-full items-center justify-center p-8 gap-2 text-center mt-6'):
                ui.icon('speaker_notes_off', size='3rem', color='primary' if is_light else 'white').classes('opacity-30')
                ui.label('該当するチャットルームがありません').classes(f'text-sm font-bold {c_text_muted}')
            return

        for room in rooms:
            row_border = 'border-slate-200' if is_light else 'border-white/5'
            row_hover = 'hover:bg-slate-100/50' if is_light else 'hover:bg-white/10'
            
            # ジャンルに応じたビジュアル・カラー決定
            g_key = room.get('genre', 'daily')
            g_info = GENRES.get(g_key, GENRES['daily'])
            
            is_locked = bool(room.get('password'))
            if is_locked:
                g_info = GENRES['locked']  # 鍵つき優先表示
                
            icon_name = g_info['icon']
            icon_color = g_info['color']
            badge_css = g_info['bg_css']

            is_active_select = state['active_room'] and str(state['active_room']['id']) == str(room['id'])
            card_active_border = 'border-cyan-500 bg-cyan-500/5 shadow-inner' if is_active_select else f'border-transparent bg-white/5'

            with ui.row().classes(f'w-full p-4 border-b {row_border} {row_hover} {card_active_border} transition-all items-center justify-between no-wrap'):
                with ui.row().classes('items-center gap-3 cursor-pointer flex-grow overflow-hidden').on('click', lambda e, r=room: handle_room_select_click(r)):
                    # 光るカラーバッジ化
                    ui.avatar(icon=icon_name, color=icon_color).classes('w-10 h-10 shrink-0 text-white shadow-md')
                    
                    with ui.column().classes('gap-0.5 overflow-hidden w-full'):
                        with ui.row().classes('w-full justify-between items-center gap-2 no-wrap'):
                            ui.label(room.get('title', '無題のルーム')).classes(f'text-sm font-bold {c_text} truncate flex-grow')
                            # タグ表示
                            ui.label(g_info['label']).classes(f'text-[8px] font-extrabold px-1.5 py-0.5 rounded border {badge_css} shrink-0')
                        
                        # 一言メッセージ(説明)の表示
                        desc_text = room.get('description') or 'タップして参加...'
                        ui.label(desc_text).classes(f'text-[11px] {c_text_muted} truncate w-full')
                
                room_creator = room.get('created_by')
                if "dummy" not in str(room['id']) and (is_su or room_creator == current_user_id):
                    def trigger_room_delete(r_id):
                        room_to_delete['id'] = r_id
                        confirm_room_delete_dialog.open()
                            
                    ui.button(icon='delete').props('flat round color=red-400 size=xs').classes('opacity-30 hover:opacity-100 transition shrink-0 ml-1').tooltip('このルームを削除').on('click.stop', lambda e, r_id=room['id']: trigger_room_delete(r_id))

    def handle_room_select_click(r):
        """部屋選択ボタンをタップした際のパスワード・SUノック判定"""
        is_locked = bool(r.get('password'))
        unlocked_list = app.storage.user.get('unlocked_rooms', [])
        
        # 鍵付きの場合
        if is_locked and str(r['id']) not in unlocked_list:
            if is_su:
                # SUはそのままパスワード解除ダイアログを開き、合言葉を入れるか、または直通で「ノック」を行うか選べます
                room_to_unlock['room_data'] = r
                password_dialog.open()
            else:
                # 一般ユーザーは合言葉入力のみ
                room_to_unlock['room_data'] = r
                password_dialog.open()
        else:
            # 鍵がない、またはアンロック済み
            select_room_direct(r)

    def select_room_direct(r):
        """ロックをクリアした安全な状態での、本質的な部屋選択処理"""
        state['active_room'] = r
        state['is_knocking'] = False
        if state['knock_timer']:
            state['knock_timer'].cancel()

        clear_chat_render_states()
        if state['pending_image']:
            state['pending_image'] = None
            image_preview_container.classes(add='hidden')
        if state['reply_target']:
            state['reply_target'] = None
            reply_preview_container.classes(add='hidden')
            
        room_title_label.set_text(r['title'])
        state['typing_container'].classes('hidden')
        
        # スマホ版・PC版でビューのアテンション(表示非表示)を切り替える
        update_responsive_visibility(entering_chat=True)
        
        room_list_area.refresh()
        update_lock_ui()
        state['last_viewers_hash'] = ""  # ★ 部屋切り替え時は強制的に再描画させるためハッシュをリセットします
        draw_header_viewers.refresh()  # ★ 部屋直通時にヘッダーの閲覧中アイコンを瞬時に構築
        sync_data()

    def exit_active_room():
        """チャット画面から退出して一覧に戻る処理"""
        state['active_room'] = None
        state['is_knocking'] = False
        if state['knock_timer']:
            state['knock_timer'].cancel()
            
        update_responsive_visibility(entering_chat=False)
        room_list_area.refresh()

    def clear_chat_render_states():
        """描画中のステート管理と実際のメッセージ表示コンテナの両方を一括でクリアする"""
        state['rendered_msg_ids'].clear()
        state['read_count_labels'].clear()
        state['reaction_containers'].clear()
        state['message_elements'].clear()
        # メッセージ表示用のDOMコンテナ自体を確実にクリア（二重描画を防ぐため）
        try:
            chat_scroll_container.clear()
        except (NameError, AttributeError):
            pass

    # ==========================================
    # ★ 確実なレスポンシブ ＆ 極上スライドトランジション用CSS（Pylance ＆ 表示バグ完治版）
    # ==========================================
    ui.add_head_html("""
    <style>
    /* 1. スマホ用の滑らかなページめくりアニメーション定義 */
    @keyframes slideInRight {
        from { transform: translateX(100%); }
        to { transform: translateX(0); }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); }
        to { transform: translateX(100%); }
    }
    .slide-in {
        animation: slideInRight 0.28s cubic-bezier(0.32, 0.94, 0.6, 1) forwards !important;
    }
    .slide-out {
        animation: slideOutRight 0.25s cubic-bezier(0.32, 0.94, 0.6, 1) forwards !important;
    }

    /* ★ チャット画面の右上アバターのフェードイン/出現用アニメーション */
    @keyframes avatar-appear {
        0% {
            opacity: 0;
            filter: blur(3px);
            transform: scale(0.9) translateY(4px);
        }
        100% {
            opacity: 1;
            filter: blur(0);
            transform: scale(1) translateY(0);
        }
    }
    .animate-avatar {
        animation: avatar-appear 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    /* 2. PC版（768px以上）：セパレーターをハッキリさせ、常に2カラムを維持 */
    @media (min-width: 768px) {
        .chat-left-list { display: flex !important; width: 320px !important; shrink: 0 !important; }
        .chat-right-col { display: flex !important; position: relative !important; flex-grow: 1 !important; transform: none !important; width: auto !important; }
        .chat-left-list.hide-sp { display: flex !important; }
        .chat-right-col.hide-sp { display: flex !important; }
        
        /* ★ 追加：PC版ではプレースホルダーを強制表示(Flex)します */
        .chat-placeholder { display: flex !important; }
    }
    /* 3. スマホ版（767px以下） */
    @media (max-width: 767px) {
        .chat-left-list { width: 100% !important; }
        .chat-right-col { position: absolute !important; inset: 0 !important; z-index: 30 !important; width: 100% !important; }
        .chat-left-list.hide-sp { display: none !important; }
        .chat-right-col.hide-sp { display: none !important; }
        
        /* ★ 追加：スマホ版ではプレースホルダーを絶対に非表示(display:none)にします */
        .chat-placeholder { display: none !important; }
    }
    </style>
    """)

    # ==========================================
    # レスポンシブ・スライド遷移の切り替え（プレースホルダー完全復旧版）
    # ==========================================
    def update_responsive_visibility(entering_chat=False):
        """スマホのスライドめくりと、PCの表示・非表示を安全に切り替えます"""
        if entering_chat:
            # ── 入室時 ──
            # PC版：プレースホルダーを隠し、チャットエリアを表示します
            view_placeholder.classes(add='hidden')  # ★ 追加
            chat_main_area.classes(remove='hidden')
            
            # スマホ版：リストを隠し、チャットを右からスライドイン
            left_list_col.classes(add='hide-sp')
            right_chat_col.classes(remove='hidden hide-sp')
            right_chat_col.classes(add='slide-in', remove='slide-out')
        else:
            # ── 退出時（プレースホルダーに戻る） ──
            # PC版：プレースホルダーを表示させ、チャットエリアを隠します
            view_placeholder.classes(remove='hidden') # ★ 追加
            chat_main_area.classes(add='hidden')
            
            # スマホ版：チャットを右へスライドアウト開始し、背景リストを即再表示
            right_chat_col.classes(add='slide-out', remove='slide-in')
            left_list_col.classes(remove='hide-sp')
            
            def complete_slide_out():
                right_chat_col.classes(add='hide-sp', remove='slide-out')
                
            ui.timer(0.25, complete_slide_out, once=True)

    # ==========================================
    # PC版・スマホ大改造用 2カラム分割大外レイアウト（初期状態の出し分け）
    # ==========================================
    # セパレーターをハッキリさせるために、border-r-2 と border-slate-300 / dark:border-white/10 を指定
    border_sep = 'border-r-2 border-slate-200 dark:border-white/10'

    if state['active_room'] or state['is_knocking']:
        # 選択中
        right_chat_classes = 'chat-right-col flex flex-col p-0 m-0 gap-0'
        left_list_classes = f'chat-left-list hide-sp {border_sep} flex flex-col gap-0 p-0 m-0'
    else:
        # 未選択
        right_chat_classes = 'chat-right-col hide-sp flex flex-col relative p-0 m-0 gap-0'
        left_list_classes = f'chat-left-list {border_sep} flex flex-col gap-0 p-0 m-0'

    # ----------------------------------------------------
    # ★ リアルタイム閲覧中ユーザーをヘッダー右に重ねて並べるUI (部分リフレッシュ)
    # ----------------------------------------------------
    @ui.refreshable
    def draw_header_viewers():
        room = state.get('active_room')
        if not room or "dummy" in str(room['id']):
            return
        
        room_id_str = str(room['id'])
        viewers = GLOBAL_CHAT_VIEWERS.get(room_id_str, {})
        participants = []
        now = time.time()
        
        for uid, info in list(viewers.items()):
            if info.get('expire', 0) > now:
                avatar_url = info.get('avatar_url')
                if avatar_url and avatar_url not in participants:
                    participants.append(avatar_url)
        
        if not participants:
            return
            
        display_avatars = participants[:3]
        has_more = len(participants) > 3
        
        # じわーっと登場するアニメーション付きでアバターをきれいに重ねて表示
        with ui.row().classes('items-center mr-3 select-none no-wrap').style('gap: 0;'):
            with ui.row().classes('flex items-center').style('gap: 0;'):
                for idx, avatar in enumerate(display_avatars):
                    margin_class = '' if idx == 0 else '-ml-2.5'
                    ui.element('img').props(f'src="{avatar}"')\
                        .classes(f'inline-block h-6 w-6 rounded-full border-2 border-slate-900 dark:border-white/20 object-cover {margin_class} animate-avatar')\
                        .style(f'z-index: {10 - idx};')
                
                if has_more:
                    with ui.element('div').classes('flex items-center justify-center h-6 w-6 rounded-full border-2 border-slate-900 dark:border-white/20 bg-slate-800 text-[10px] text-white/50 font-bold shrink-0 -ml-2.5')\
                            .style(f'z-index: {10 - len(display_avatars)};'):
                        ui.label('⋯').classes('leading-none mt-[-2px]')

    with ui.element('div').classes('absolute inset-0 flex flex-row no-wrap overflow-hidden p-0 m-0'):
        
        # ────────【左カラム：ルームリスト】────────
        with ui.column().classes(left_list_classes).style(f'border-color: {c_border};') as left_list_col:
            # === 【修正： 開く瞬間にすべての入力を完全に真っ新にリセットする処理を追加】 ===
            def open_create_room_wizard():
                new_title.set_value('')
                new_desc.set_value('')
                new_pwd.set_value('')
                chk_secret.set_value(False)
                selected_creation_genre['val'] = 'daily'
                draw_creation_genres.refresh()
                new_room_dialog.open()
            # === 【修正： ここまで】 ===

            with ui.row().classes(f'w-full h-14 p-0 px-4 items-center justify-between shrink-0 {c_header_bg}'):
                ui.label('チャットルーム').classes(f'text-sm font-extrabold {c_text}')
                # on_click を new_room_dialog.open から open_create_room_wizard に変更します
                ui.button(icon='add', on_click=open_create_room_wizard).props('flat round color=cyan-400 size=sm').tooltip('新規ルーム作成')

            # ジャンル切り替えフィルターチップス
            with ui.row().classes('w-full p-3 gap-1.5 justify-start overflow-x-auto hide-scrollbar shrink-0 border-b')\
                    .style(f'border-color: {c_border}; background-color: rgba(255,255,255,0.02);'):
                for key, g_info in GENRES.items():
                    def make_filter_cb(k=key):
                        def cb():
                            state['selected_genre'] = k
                            room_list_area.refresh()
                        return cb
                        
                    is_active = (state['selected_genre'] == key)
                    bg = g_info['bg_css'] if is_active else 'bg-white/5 border-transparent text-white/50'
                    border_cls = 'border-[1.5px]' if is_active else 'opacity-60'
                    
                    # ★ 修正： こちらも icon= 引数に変更して、アイコンタグの剥き出しを修正します
                    ui.button(g_info['label'], icon=g_info['icon'], on_click=make_filter_cb())\
                        .props('unelevated rounded size=xs')\
                        .classes(f'px-2.5 py-0.5 font-bold transition-all shrink-0 {bg} {border_cls}')

            # ルームカード一覧
            with ui.column().classes('w-full flex-grow overflow-y-auto hide-scrollbar p-0 m-0 gap-0'):
                room_list_area()

        # ────────【右カラム：チャット本体】────────
        with ui.column().classes(right_chat_classes).props('id="right-chat-col"') as right_chat_col:
            
            # === 【修正： Tailwindに依存しないカスタムクラス 'chat-placeholder' に変更】 ===
            with ui.element('div').classes('chat-placeholder w-full h-full flex flex-col items-center justify-center gap-4') as view_placeholder:
                if state['active_room'] or state['is_knocking']:
                    view_placeholder.classes('hidden')
                
                ui.icon('chat_bubble_outline', size='70px', color='primary' if is_light else 'white').classes('opacity-20 animate-pulse')
                ui.label('チャットを開いて、会話に参加しましょう！').classes(f'{c_text_muted} mt-2 text-sm font-bold')
                ui.label('左側の一覧からトピックをお選びください。鍵付きルームの入室には合言葉が必要です。').classes(f'{c_text_muted} text-[10px] text-center max-w-xs px-4 leading-relaxed')

            # === 【修正箇所③：チャット詳細を ui.element('div') に変更（PC入力欄の潰れバグ完治）】 ===
            with ui.element('div').classes('w-full h-full flex flex-col no-wrap p-0 m-0 gap-0') as chat_main_area:
                if not state['active_room'] or state['is_knocking']:
                    chat_main_area.classes('hidden')
            # === 【修正箇所③：ここまで】 ===
                
                # === 【修正： 左側と完全に揃えるため、 h-14 p-0 px-4 に統一します】 ===
                with ui.row().classes(f'w-full h-14 p-0 px-4 items-center justify-between shrink-0 {c_header_bg}'):
                    with ui.row().classes('items-center gap-3 no-wrap overflow-hidden'):
                        # スマホ用戻るボタン
                        ui.button(icon='arrow_back_ios_new', on_click=exit_active_room).props(f'flat round color={c_btn_color} size=sm').classes('bg-black/5 dark:bg-white/10')
                        
                        init_title = state['active_room']['title'] if state['active_room'] else 'ルーム名'
                        room_title_label = ui.label(init_title).classes(f'font-extrabold {c_text} text-md truncate')
                    
                    with ui.row().classes('items-center shrink-0'):
                        # ★ 新規追加: 現在の閲覧中メンバーのアイコンを重ね並べるコンポーネントをここに配置
                        draw_header_viewers()

                        if is_su:
                            def toggle_room_lock():
                                r = state.get('active_room')
                                if not r or "dummy" in str(r['id']): return
                                new_state = not r.get('is_locked', False)
                                try:
                                    supabase.table('chat_rooms').update({'is_locked': new_state}).eq('id', r['id']).execute()
                                    r['is_locked'] = new_state
                                    update_lock_ui()
                                    ui.notify('ルームをロックしました' if new_state else 'ルームのロックを解除しました', color='warning' if new_state else 'positive', position='top')
                                    room_list_area.refresh()
                                except Exception as e:
                                    ui.notify(f"DBエラー: {e}", type="negative", position='top')

                            lock_btn = ui.button(icon='lock_open', on_click=toggle_room_lock).props(f'flat round color={c_btn_color} size=sm')
                        else:
                            lock_btn = ui.icon('lock', color='red-400').classes('mr-2')
                            lock_btn.set_visibility(False)

                # ★ 改善：プレーンな div を使い、 flex-grow + h-0 + min-h-0 で縦幅を最大に引き伸ばします
                chat_scroll_container = ui.element('div').props('id="chat-scroll-container"')\
                    .classes('w-full flex-grow h-0 min-h-0 p-4 flex flex-col gap-4 overflow-y-auto hide-scrollbar')

                # タイピングインジケータ
                typing_bg = 'bg-slate-200/50' if is_light else 'bg-slate-900/30'
                state['typing_container'] = ui.row().classes(f'w-full px-6 py-1 items-center gap-2 {c_text_muted} text-[11px] shrink-0 {typing_bg} hidden')
                with state['typing_container']:
                    ui.spinner('dots', size='1.2em', color='primary' if is_light else 'white')
                    state['typing_label'] = ui.label("...")

                # 入力・送信コンテナ
                with ui.column().classes(f'w-full {c_input_container_bg} shrink-0 z-20 gap-0 p-0 m-0') as normal_input_container:
                    preview_bg = 'bg-slate-200 border-slate-300' if is_light else 'bg-slate-800 border-white/5'
                    preview_text = 'text-slate-700' if is_light else 'text-white/70'

                    # 返信先プレビュー
                    reply_preview_container = ui.row().classes(f'w-full hidden {preview_bg} px-4 py-2 border-b items-center justify-between')
                    with reply_preview_container:
                        with ui.row().classes('items-center gap-2 overflow-hidden flex-grow'):
                            ui.icon('reply', color='cyan-400', size='sm')
                            reply_target_label = ui.label('').classes(f'text-xs {preview_text} truncate')
                        ui.button(icon='close', on_click=lambda: clear_reply()).props(f'flat round color={c_btn_color} size=xs')

                    # 画像添付プレビュー
                    image_preview_container = ui.row().classes(f'w-full hidden {preview_bg} px-4 py-2 border-b items-center justify-between')
                    with image_preview_container:
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('image', color='cyan-400')
                            preview_label = ui.label('画像添付中...').classes(f'text-xs {preview_text}')
                        ui.button(icon='close', on_click=lambda: clear_image()).props(f'flat round color={c_btn_color} size=xs')

                    with ui.row().classes('w-full p-3 items-center gap-2 no-wrap'):
                        async def handle_select_image(e):
                            try:
                                file_bytes = None
                                read_result = e.content.read() if hasattr(e, 'content') else e.file.read()
                                if inspect.isawaitable(read_result): file_bytes = await read_result
                                else: file_bytes = read_result
                                
                                filename = getattr(e, 'name', 'uploaded_image.jpg')
                                state['pending_image'] = {'bytes': file_bytes, 'name': filename}
                                preview_label.set_text(filename)
                                image_preview_container.classes(remove='hidden')
                            except Exception:
                                ui.notify('画像の読み込みに失敗しました', color='negative')

                        img_uploader = ui.upload(on_upload=handle_select_image, auto_upload=True, max_files=1).props('accept="image/*"').style('display: none;')
                        ui.button(icon='image', on_click=lambda: img_uploader.run_method('pickFiles')).props(f'flat round color={c_btn_color} size=sm').tooltip('画像を送る')
                        
                        # スタンプ
                        with ui.button(icon='sentiment_satisfied').props(f'flat round color={c_btn_color} size=sm').tooltip('スタンプを送る') as stamp_btn:
                            stamp_menu_bg = 'bg-white border-slate-200' if is_light else 'bg-slate-900 border-white/10'
                            with ui.menu().props('anchor="top right" self="bottom right"').classes(f'{stamp_menu_bg} border p-2 rounded-xl') as stamp_menu:
                                def send_stamp(stamp_url: str):
                                    room = state.get('active_room')
                                    if not room or "dummy" in str(room['id']): return
                                    try:
                                        local_stamp_url = save_stamp_locally(stamp_url)
                                        send_message(room['id'], current_user_id, "[スタンプ]", image_url=local_stamp_url)
                                        clear_chat_render_states()
                                        sync_data()
                                        stamp_menu.close()
                                    except Exception: pass
                                        
                                with ui.grid(columns=3).classes('gap-2 p-1'):
                                    for stamp_url in STAMP_LIST:
                                        ui.image(stamp_url).classes('w-10 h-10 cursor-pointer hover:scale-110 transition-transform').on('click', lambda e, url=stamp_url: send_stamp(url))

                        msg_input = ui.input(placeholder='メッセージを入力...').classes(f'flex-grow {c_input_bg} rounded-full px-4 w-0 min-w-0').props(f'borderless :dark="{dark_val}" input-class="{c_text} text-sm"').on('keydown', lambda e: handle_typing()).on('keydown.enter', lambda e: handle_send())
                        ui.button(icon='send', on_click=lambda e: handle_send()).props('flat round color=cyan-400')

                # ロックアラート
                locked_alert_bg = 'bg-red-50 border-red-200 text-red-700' if is_light else 'bg-red-900/30 border-red-500/50 text-red-300'
                with ui.row().classes(f'w-full p-4 items-center justify-center {locked_alert_bg} gap-2 border-t') as locked_alert_container:
                    ui.icon('lock', color='red-500', size='sm')
                    ui.label('このルームは管理者により一時的にロックされています。').classes('text-sm font-bold')
                locked_alert_container.set_visibility(False)

    # ==========================================
    # ヘルパー関数群
    # ==========================================
    def clear_reply():
        state['reply_target'] = None
        reply_preview_container.classes(add='hidden')

    def clear_image():
        state['pending_image'] = None
        image_preview_container.classes(add='hidden')

    def handle_send():
        val = msg_input.value or ""
        img_data = state['pending_image']
        if not val.strip() and not img_data: return
        room = state['active_room']
        
        if check_ng_words(val)['is_ng']:
            ui.notify('不適切な表現が含まれているため送信できません。', color='negative', position='top')
            return
        
        if state['reply_target'] and val:
            r_name = state['reply_target']['name'].replace(':', '：').replace('>', '＞')
            r_text = state['reply_target']['text'].replace(':', '：').replace('\n', ' ').replace('>', '＞')[:30]
            val = f"<<<REPLY:{r_name}:{r_text}>>>\n{val}"
        
        if "dummy" not in str(room['id']):
            try:
                image_url = None
                if img_data:
                    image_url = save_chat_image_local(img_data['bytes'], img_data['name'])
                    
                send_message(room['id'], current_user_id, val, image_url=image_url)
                msg_input.set_value('')
                clear_image()
                clear_reply()
                sync_data()
            except Exception as e:
                ui.notify(f"送信エラー: {e}", color='negative')

    def handle_typing():
        room = state.get('active_room')
        if not room or "dummy" in str(room['id']): return
        room_id = str(room['id'])
        
        from database.chat_db import GLOBAL_TYPING_STATE
        if room_id not in GLOBAL_TYPING_STATE:
            GLOBAL_TYPING_STATE[room_id] = {}
        GLOBAL_TYPING_STATE[room_id][current_user_id] = {
            'expire': time.time() + 4,
            'name': current_user_name
        }

    def update_lock_ui():
        room = state.get('active_room')
        if not room: return
        is_locked = room.get('is_locked', False)
        if is_locked:
            if is_su:
                lock_btn.props(f'color=red-400 icon=lock')
            else:
                lock_btn.set_visibility(True)
                normal_input_container.set_visibility(False)
                locked_alert_container.set_visibility(True)
        else:
            if is_su:
                lock_btn.props(f'color={c_btn_color} icon=lock_open')
            else:
                lock_btn.set_visibility(False)
                normal_input_container.set_visibility(True)
                locked_alert_container.set_visibility(False)

    def set_reply_target(name, text):
        match = re.match(r"<<<REPLY:.*?:.*?(?:>>>\n)(.*)", text, re.DOTALL)
        clean_text = match.group(1) if match else text
        state['reply_target'] = {'name': name, 'text': clean_text}
        reply_target_label.set_text(f"{name} さんの発言に返信: {clean_text[:20]}...")
        reply_preview_container.classes(remove='hidden')
        msg_input.run_method('focus')

    def open_edit_chat_dialog(m_id, current_text):
        match = re.match(r"<<<REPLY:(.*?):(.*?)(?:>>>\n)(.*)", current_text, re.DOTALL)
        prefix = ""
        if match:
            rep_name, rep_content, actual_text = match.groups()
            prefix = f"<<<REPLY:{rep_name}:{rep_content}>>>\n"
            editable_text = actual_text
        else:
            editable_text = current_text

        with ui.dialog() as edit_dialog, ui.card().classes(f'{c_bg} w-[350px] p-5 shadow-2xl'):
            ui.label('メッセージを編集').classes(f'text-base font-bold {c_text} mb-2')
            edit_input_bg = 'bg-slate-100 border-slate-200' if is_light else 'bg-black/30 border-white/10'
            edit_input = ui.textarea(value=editable_text).classes(f'w-full {edit_input_bg} border rounded-lg p-2').props(f'borderless :dark="{dark_val}" input-class="{c_text} text-sm" autogrow rows="3"')
            
            def handle_save():
                new_text = edit_input.value or ""
                if not new_text.strip() or new_text == editable_text:
                    edit_dialog.close()
                    return
                if check_ng_words(new_text)['is_ng']:
                    ui.notify('不適切な表現が含まれています。', color='negative', position='top')
                    return
                final_text = prefix + new_text
                update_chat_message(m_id, final_text)
                edit_dialog.close()
                clear_chat_render_states()
                sync_data()
                
            with ui.row().classes('w-full justify-end mt-4 gap-2'):
                ui.button('キャンセル', on_click=edit_dialog.close).props(f'flat color={c_btn_color}')
                ui.button('保存', on_click=handle_save).classes('bg-cyan-600 hover:bg-cyan-500 text-white font-bold')
        edit_dialog.open()

    def parse_and_render_text(text):
        match = re.match(r"<<<REPLY:(.*?):(.*?)(?:>>>\n)(.*)", text, re.DOTALL)
        if match:
            rep_name, rep_content, actual_text = match.groups()
            reply_box_bg = 'bg-slate-200/50 border-slate-300' if is_light else 'bg-black/20 border-cyan-500'
            reply_box_text = 'text-slate-600' if is_light else 'text-white/60'
            
            with ui.column().classes('w-full gap-1'):
                with ui.card().classes(f'w-full {reply_box_bg} p-2 shadow-none border-l-2 rounded-sm mb-1 gap-0'):
                    ui.label(f"@{rep_name}").classes('text-cyan-600 dark:text-cyan-300 font-bold text-[10px]')
                    ui.label(rep_content).classes(f'{reply_box_text} text-[10px] line-clamp-1')
                ui.label(actual_text).classes('whitespace-pre-wrap break-words text-sm')
        else:
            ui.label(text).classes('whitespace-pre-wrap break-words text-sm')

    # ==========================================
    # データ同期 ＆ 描画
    # ==========================================
    def sync_data():
        room = state.get('active_room')
        
        # 1. 【ノック自動検出】自分がいる部屋にSUからのノックが届いていないかチェック (一般ユーザー時)
        if room and "dummy" not in str(room['id']):
            try:
                pending_knocks = fetch_pending_knocks(room['id'])
                for req in pending_knocks:
                    # リアルタイムノック許可確認ダイアログを開く
                    def create_approval_dialog(r_id=room['id'], su_id=req['su_id'], su_name=req['name']):
                        with ui.dialog() as approval_dialog, ui.card().classes(f'{c_bg} p-5 w-80'):
                            ui.label('🔑 入室リクエスト（ノック）').classes('text-base font-bold text-amber-500')
                            ui.label(f"管理者である「{su_name}」さんが、この鍵付きルームへの入室を求めてノックしています。入室を許可しますか？").classes('text-xs leading-relaxed mt-2')
                            with ui.row().classes('w-full justify-end mt-4 gap-2'):
                                ui.button('拒否', on_click=approval_dialog.close).props('flat color=red-400')
                                def do_approve():
                                    approve_knock_request(r_id, su_id)
                                    ui.notify(f'{su_name} さんの入室を許可しました', color='positive')
                                    approval_dialog.close()
                                ui.button('許可する', on_click=do_approve).classes('bg-cyan-600 text-white font-bold')
                        approval_dialog.open()
                    create_approval_dialog()
            except Exception as e:
                print(f"Error handling pending knocks: {e}")

        if not room or "dummy" in str(room['id']) or state['is_knocking']: return

        # 2. リアルタイム閲覧中メンバーとして共有メモリに登録 ＆ アバターリフレッシュ
        # (メッセージ描画部分の例外から隔離し、確実にアバターが追加・削除されるようにします)
        try:
            GLOBAL_CHAT_VIEWERS.setdefault(str(room['id']), {})
            my_avatar = app.storage.user.get('user_metadata', {}).get('avatar_url') or ""
            GLOBAL_CHAT_VIEWERS[str(room['id'])][current_user_id] = {
                'avatar_url': my_avatar,
                'expire': time.time() + 6
            }
            
            # ★ 改善: 閲覧メンバー一覧（数やURL）に変化があった時のみリフレッシュを呼び、2秒おきの定期チラつき・点滅を完全に防ぎます
            room_id_str = str(room['id'])
            viewers = GLOBAL_CHAT_VIEWERS.get(room_id_str, {})
            current_viewers = []
            now_time = time.time()
            for uid, info in list(viewers.items()):
                if info.get('expire', 0) > now_time:
                    avatar_url = info.get('avatar_url')
                    if avatar_url and avatar_url not in current_viewers:
                        current_viewers.append(avatar_url)
            
            current_viewers.sort() # 順序の不一致による不要な再描画を防ぐ
            current_viewers_hash = ",".join(current_viewers)
            
            # 閲覧メンバー（アバター配列）が変わったときだけリフレッシュ
            if current_viewers_hash != state['last_viewers_hash']:
                state['last_viewers_hash'] = current_viewers_hash
                draw_header_viewers.refresh()

        except Exception as e:
            print(f"Error updating GLOBAL_CHAT_VIEWERS: {e}")

        # 3. ロック状態同期
        try:
            rooms_update = fetch_chat_rooms()
            for r in rooms_update:
                if str(r['id']) == str(room['id']):
                    if room.get('is_locked', False) != r.get('is_locked', False):
                        room['is_locked'] = r.get('is_locked', False)
                        update_lock_ui()
                    break
        except Exception as e:
            print(f"Error syncing room lock: {e}")

        # 4. メッセージデータの取得
        try:
            view_placeholder.classes('hidden')
            chat_main_area.classes(remove='hidden')

            mark_as_read(room['id'], current_user_id)
            messages = fetch_messages(room['id'])
        except Exception as e:
            print(f"Error fetching/reading messages: {e}")
            return # メッセージ取得自体が失敗した場合はこれ以降を中断

        # 5. リアルタイム削除検知
        try:
            fetched_ids = {msg['id'] for msg in messages}
            deleted_ids = state['rendered_msg_ids'] - fetched_ids
            for d_id in list(deleted_ids):
                if d_id in state['message_elements']:
                    try: state['message_elements'][d_id].delete()
                    except: pass
                    del state['message_elements'][d_id]
                state['rendered_msg_ids'].discard(d_id)
                state['read_count_labels'].pop(d_id, None)
                state['reaction_containers'].pop(d_id, None)
        except Exception as e:
            print(f"Error processing deleted messages: {e}")

        # 6. メッセージ一覧のレンダリング
        has_new_messages = False
        for msg in messages:
            try:
                msg_id = msg['id']
                read_count = max(0, len(msg.get('read_user_ids', [])) - 1)
                reactions_data = msg.get('reactions') or {}
                if not isinstance(reactions_data, dict): reactions_data = {}

                read_label_color = 'text-indigo-600 font-black' if is_light else 'text-indigo-400 font-bold'
                time_label_color = 'text-slate-400' if is_light else 'text-white/40'

                if msg_id in state['rendered_msg_ids']:
                    if msg_id in state['read_count_labels']:
                        label = state['read_count_labels'][msg_id]
                        if label:
                            label.set_text(f'既読 {read_count}')
                            label.set_visibility(read_count > 0)
                            
                    # リアクション表示
                    if msg_id in state['reaction_containers']:
                        container, bubble_is_me, msg_owner_id = state['reaction_containers'][msg_id]
                        container.clear()
                        with container:
                            has_any_reaction = any(len(users) > 0 for users in reactions_data.values())
                            if has_any_reaction:
                                for emo, user_list in reactions_data.items():
                                    count = len(user_list)
                                    if count > 0:
                                        is_my_reaction = current_user_id in user_list
                                        bg_cls = ('bg-cyan-50 border-cyan-300' if is_light else 'bg-cyan-500/30 border-cyan-500/50') if is_my_reaction else ('bg-slate-100 border-slate-200' if is_light else 'bg-white/5 border-white/10')
                                        text_cls = 'text-cyan-700' if is_my_reaction else ('text-slate-600' if is_light else 'text-white/60')
                                        
                                        ui.button(f"{emo} {count}", on_click=lambda e, mi=msg_id, ec=emo, oi=msg_owner_id: handle_reaction_click(mi, ec, oi)) \
                                            .props('dense size=xs color=slate-800' if is_light else 'dense size=xs color=white flat') \
                                            .classes(f"px-1.5 py-0.5 rounded-full border text-[10px] transition-all {bg_cls} {text_cls}")
                else:
                    has_new_messages = True
                    state['rendered_msg_ids'].add(msg_id)
                    
                    is_me = (msg.get('user_id') == current_user_id)
                    profile = msg.get('profiles', {}) or {}
                    name = profile.get('name', '名無し')
                    avatar = profile.get('avatar_url', f"https://api.dicebear.com/7.x/bottts/svg?seed={name}")
                    text = msg.get('message', '')
                    image_url = msg.get('image_url')
                    
                    is_stamp = image_url and ("/static/stamps/" in image_url or "api.iconify.design" in image_url)
                    
                    raw_time = msg.get('created_at', '')
                    time_str = ''
                    if raw_time:
                        try:
                            dt = date_parser.isoparse(raw_time)
                            diff = datetime.now(timezone.utc) - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
                            if diff.total_seconds() < 0: time_str = "たった今"
                            elif diff.days > 0: time_str = f"{diff.days}日前"
                            elif diff.seconds >= 3600: time_str = f"{diff.seconds // 3600}時間前"
                            elif diff.seconds >= 60: time_str = f"{diff.seconds // 60}分前"
                            else: time_str = "たった今"
                        except: pass
                    
                    with chat_scroll_container:
                        read_label = None
                        
                        def trigger_msg_delete(m_id):
                            msg_to_delete['id'] = m_id
                            confirm_msg_delete_dialog.open()

                        if is_me:
                            with ui.row().classes('w-full items-start justify-end gap-2 mt-2') as msg_row_el:
                                with ui.column().classes('gap-0.5 items-end flex-grow'):
                                    with ui.row().classes('gap-3 items-center opacity-60 hover:opacity-100 transition mb-0.5 mr-1'):
                                        ui.button(icon='edit', on_click=lambda e, m=msg_id, t=text: open_edit_chat_dialog(m, t)).props('flat round size=xs color=cyan-400').classes('p-0 min-h-0 min-w-0')
                                        ui.button(icon='delete', on_click=lambda e, m=msg_id: trigger_msg_delete(m)).props('flat round size=xs color=red-400').classes('p-0 min-h-0 min-w-0')
                                    
                                    with ui.row().classes('items-end gap-1.5 relative'):
                                        with ui.column().classes('items-end gap-0 mb-1'):
                                            read_label = ui.label(f'既読 {read_count}').classes(f'text-[9px] {read_label_color} leading-none mb-0.5')
                                            read_label.set_visibility(read_count > 0)
                                            if time_str: ui.label(time_str).classes(f'text-[9px] {time_label_color} leading-none')
                                        
                                        card_bg = 'bg-transparent shadow-none border-none p-0' if is_stamp else 'p-3 bg-cyan-600/80 backdrop-blur text-white rounded-l-xl rounded-br-xl text-sm max-w-xs shadow-sm flex flex-col gap-2'
                                        with ui.card().classes(f'relative {card_bg}') as msg_card:
                                            if is_stamp:
                                                ui.image(image_url).classes('w-20 h-20 object-contain bg-transparent')
                                            else:
                                                if image_url: lightbox_image(image_url, thumbnail_classes='w-48 rounded-lg cursor-pointer hover:opacity-80 transition-opacity')
                                                if text: parse_and_render_text(text)
                                                
                                    reaction_container = ui.row().classes('items-center gap-1 mt-1 flex-wrap justify-end')
                                    state['reaction_containers'][msg_id] = (reaction_container, is_me, msg.get('user_id'))
                                    
                                    with reaction_container:
                                        has_any_reaction = any(len(users) > 0 for users in reactions_data.values())
                                        if has_any_reaction:
                                            for emo, user_list in reactions_data.items():
                                                count = len(user_list)
                                                if count > 0:
                                                    is_my_reaction = current_user_id in user_list
                                                    bg_cls = ('bg-cyan-50 border-cyan-300' if is_light else 'bg-cyan-500/30 border-cyan-500/50') if is_my_reaction else ('bg-slate-100 border-slate-200' if is_light else 'bg-white/5 border-white/10')
                                                    text_cls = 'text-cyan-700' if is_my_reaction else ('text-slate-600' if is_light else 'text-white/60')
                                                    ui.button(f"{emo} {count}", on_click=lambda e, mi=msg_id, ec=emo, oi=msg.get('user_id'): handle_reaction_click(mi, ec, oi)) \
                                                        .props('dense size=xs color=slate-800' if is_light else 'dense size=xs color=white flat') \
                                                        .classes(f"px-1.5 py-0.5 rounded-full border text-[10px] transition-all {bg_cls} {text_cls}")
                            
                            state['message_elements'][msg_id] = msg_row_el
                        else:
                            with ui.row().classes('w-full items-start gap-2 mt-2') as msg_row_el:
                                with ui.avatar().classes('w-8 h-8 bg-slate-200 shrink-0 mt-3'):
                                    ui.image(avatar).classes('w-full h-full object-cover')
                                    
                                with ui.column().classes('gap-0.5 flex-grow'):
                                    with ui.row().classes('w-full items-center justify-start gap-3'):
                                        ui.label(name).classes('text-[10px] text-slate-500 font-bold')
                                        with ui.row().classes('gap-3 items-center opacity-60 hover:opacity-100 transition'):
                                            ui.button(icon='reply', on_click=lambda e, n=name, t=text: set_reply_target(n, t)).props(f'flat round size=xs color={c_btn_color}').classes('p-0 min-h-0 min-w-0')
                                            if is_su:
                                                ui.button(icon='edit', on_click=lambda e, m=msg_id, t=text: open_edit_chat_dialog(m, t)).props('flat round size=xs color=cyan-400').classes('p-0 min-h-0 min-w-0')
                                                ui.button(icon='delete', on_click=lambda e, m=msg_id: trigger_msg_delete(m)).props('flat round size=xs color=red-400').classes('p-0 min-h-0 min-w-0')
                                                
                                    with ui.row().classes('items-end gap-1.5 relative'):
                                        card_bg = 'bg-transparent shadow-none border-none p-0' if is_stamp else f'p-3 {c_msg_other_bg} backdrop-blur rounded-r-xl rounded-bl-xl text-sm max-w-xs shadow-sm flex flex-col gap-2'
                                        with ui.card().classes(f'relative {card_bg}') as msg_card:
                                            ctx_menu_bg = 'bg-white border-slate-200' if is_light else 'bg-slate-900/95 border-white/15'
                                            ctx_menu_text = 'text-slate-500' if is_light else 'text-white/50'
                                            
                                            with ui.context_menu().classes(f'{ctx_menu_bg} border p-2 rounded-xl shadow-xl z-50') as ctx_menu:
                                                ui.label('リアクションを選択').classes(f'text-[10px] {ctx_menu_text} mb-1.5 px-1 font-bold')
                                                with ui.grid(columns=5).classes('gap-1.5 p-0.5'):
                                                    for emo in ['👍', '❤️', '😂', '😢', '🎉', '🔥', '✨', '🙏', '👏', '🥺']:
                                                        user_list = reactions_data.get(emo, [])
                                                        bg_btn = 'bg-cyan-100 rounded' if is_light and (current_user_id in user_list) else ('bg-cyan-500/20 rounded' if (current_user_id in user_list) else '')
                                                        ui.button(emo, on_click=lambda e, mi=msg_id, ec=emo, oi=msg.get('user_id'), menu_obj=ctx_menu: handle_reaction_click(mi, ec, oi, menu_obj)) \
                                                            .props('dense size=md flat') \
                                                            .classes(f"p-1.5 text-base hover:scale-115 transition-transform rounded {bg_btn}")

                                            if is_stamp:
                                                ui.image(image_url).classes('w-20 h-20 object-contain bg-transparent')
                                            else:
                                                if image_url: lightbox_image(image_url, thumbnail_classes='w-48 rounded-lg cursor-pointer hover:opacity-80 transition-opacity')
                                                if text: parse_and_render_text(text)
                                        
                                        with ui.column().classes('items-start gap-0 mb-1'):
                                            read_label = ui.label(f'既読 {read_count}').classes(f'text-[9px] {read_label_color} leading-none mb-0.5')
                                            read_label.set_visibility(read_count > 0)
                                            if time_str: ui.label(time_str).classes(f'text-[9px] {time_label_color} leading-none')

                                    reaction_container = ui.row().classes('items-center gap-1 mt-1 flex-wrap justify-start')
                                    state['reaction_containers'][msg_id] = (reaction_container, is_me, msg.get('user_id'))
                                    
                                    with reaction_container:
                                        has_any_reaction = any(len(users) > 0 for users in reactions_data.values())
                                        if has_any_reaction:
                                            for emo, user_list in reactions_data.items():
                                                count = len(user_list)
                                                if count > 0:
                                                    is_my_reaction = current_user_id in user_list
                                                    bg_cls = ('bg-cyan-50 border-cyan-300' if is_light else 'bg-cyan-500/30 border-cyan-500/50') if is_my_reaction else ('bg-slate-100 border-slate-200' if is_light else 'bg-white/5 border-white/10')
                                                    text_cls = 'text-cyan-700' if is_my_reaction else ('text-slate-600' if is_light else 'text-white/60')
                                                    ui.button(f"{emo} {count}", on_click=lambda e, mi=msg_id, ec=emo, oi=msg.get('user_id'): handle_reaction_click(mi, ec, oi)) \
                                                        .props('dense size=xs color=slate-800' if is_light else 'dense size=xs color=white flat') \
                                                        .classes(f"px-1.5 py-0.5 rounded-full border text-[10px] transition-all {bg_cls} {text_cls}")
                            
                            state['message_elements'][msg_id] = msg_row_el
                        
                        state['read_count_labels'][msg_id] = read_label
            except Exception as msg_err:
                print(f"Error rendering individual message: {msg_err}")

        # 7. スクロール、タイピング更新、タイマー
        try:
            if has_new_messages:
                ui.run_javascript('setTimeout(() => { var el = document.getElementById("chat-scroll-container"); if(el) el.scrollTop = el.scrollHeight; }, 100);')

            # タイピングインジケータ更新
            room_id_str = str(room['id'])
            from database.chat_db import GLOBAL_TYPING_STATE
            typing_users = GLOBAL_TYPING_STATE.get(room_id_str, {})
            now = time.time()
            active_typists = []
            for uid, data in list(typing_users.items()):
                if uid != current_user_id:
                    expire = data.get('expire', 0) if isinstance(data, dict) else data
                    name = data.get('name', '誰か') if isinstance(data, dict) else '誰か'
                    if expire > now: active_typists.append(name)
            
            if active_typists:
                state['typing_label'].set_text(f"{', '.join(active_typists)} が入力中...")
                state['typing_container'].classes(remove='hidden')
            else:
                state['typing_container'].classes('hidden')

        except Exception as e:
            print(f"Error in typing/scrolling updates: {e}")

    # 初期化：すでに部屋が選択されている場合のみスライド入室を実行し、未選択時は余計な処理を走らせないようにします
    if state['active_room']:
        ui.timer(0.1, lambda: update_responsive_visibility(entering_chat=True), once=True)

    # 2秒おきにリアルタイム同期
    ui.timer(2.0, sync_data)