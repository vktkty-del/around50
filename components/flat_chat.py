import os
import re
import inspect
import base64
from datetime import datetime, timezone
import time
from nicegui import app, ui  
from dateutil import parser as date_parser

from database.chat_db import (
    fetch_messages, send_message, mark_as_read, create_chat_room,
    save_chat_image_local, delete_message, update_chat_message
)
from database.flat_db import get_flat_by_id, silent_leave_flat, approve_flat_recruitment, supabase
from utils.validator import check_ng_words
from components.lightbox import lightbox_image
from themes import THEMES

def get_anonymous_avatar(pseudo_name: str) -> str:
    safe_seed = base64.urlsafe_b64encode(pseudo_name.encode()).decode()[:15]
    return f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}"

def render_flat_chat(current_user_id: str, flat_id: str, exit_cb, enter_real_chat_cb):
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)
    dark_val = 'false' if is_light else 'true'
    btn_color = 'slate-800' if is_light else 'white'

    state = {
        'flat_data': None,
        'chat_room_id': None,
        'rendered_msg_ids': set(),
        'read_count_labels': {},
        'pending_image': None,  
        'reply_target': None    
    }
    
    flat_data = get_flat_by_id(flat_id)
    if not flat_data:
        ui.notify("募集が見つかりません（消滅した可能性があります）", type="negative", position='top')
        exit_cb()
        return
        
    state['flat_data'] = flat_data
    assigned_names = flat_data.get('assigned_names', {})
    state['chat_room_id'] = assigned_names.get('_chat_room_id')
    
    if not state['chat_room_id']:
        try:
            room_title = f"[FLAT砂場] {flat_data.get('genre', 'ふらっと募集')}"
            new_room = create_chat_room(title=room_title)
            if new_room:
                state['chat_room_id'] = new_room['id']
                assigned_names["_chat_room_id"] = new_room['id']
                supabase.table("flats").update({"assigned_names": assigned_names}).eq("id", flat_id).execute()
            else:
                ui.notify("チャットルームの準備に失敗しました", type="warning", position='top')
                exit_cb()
                return
        except Exception as e:
            print(f"チャットルーム自動修復エラー: {e}")
            ui.notify("チャットルームの準備でエラーが発生しました", type="warning", position='top')
            exit_cb()
            return

    msg_to_delete = {'id': None}
    with ui.dialog() as confirm_msg_delete_dialog, ui.card().classes('bg-white dark:bg-slate-900 border border-slate-200 dark:border-white/20 text-slate-800 dark:text-white w-80 p-6'):
        ui.label('この匿名メッセージを削除します。よろしいですか？').classes('text-base font-bold text-red-500 dark:text-red-400')
        with ui.row().classes('w-full justify-end mt-6 gap-3'):
            ui.button('キャンセル', on_click=confirm_msg_delete_dialog.close).props(f'flat color={btn_color}')
            def execute_msg_delete():
                if not msg_to_delete['id']: return
                try:
                    delete_message(msg_to_delete['id'])
                    ui.notify('メッセージを削除しました', color='positive')
                    confirm_msg_delete_dialog.close()
                    chat_scroll_container.clear()
                    state['rendered_msg_ids'].clear()
                    state['read_count_labels'].clear()
                    sync_flat_chat()
                except Exception as ex:
                    ui.notify(f'削除エラー: {ex}', color='negative')
            ui.button('削除する', on_click=execute_msg_delete).classes('bg-red-600 hover:bg-red-500 font-bold text-white')

    def open_edit_chat_dialog(m_id, current_text):
        match = re.match(r"<<<REPLY:(.*?):(.*?)(?:>>>\n)(.*)", current_text, re.DOTALL)
        prefix = ""
        if match:
            rep_name, rep_content, actual_text = match.groups()
            prefix = f"<<<REPLY:{rep_name}:{rep_content}>>>\n"
            editable_text = actual_text
        else:
            editable_text = current_text

        with ui.dialog() as edit_dialog, ui.card().classes('bg-white dark:bg-slate-900 border border-slate-200 dark:border-white/20 text-slate-800 dark:text-white w-[350px] p-5 shadow-2xl'):
            ui.label('匿名メッセージを編集').classes('text-base font-bold text-slate-800 dark:text-white mb-2')
            
            # ★ 修正ポイント1：編集フォームも明示的に色を出し分ける
            edit_bg = 'bg-slate-100' if is_light else 'bg-slate-800'
            edit_bd = 'border-slate-300' if is_light else 'border-slate-600'
            edit_tc = 'text-slate-800' if is_light else 'text-white'
            
            edit_input = ui.textarea(value=editable_text).classes(
                f'w-full {edit_bg} border {edit_bd} rounded-lg p-2'
            ).props(
                f'borderless :dark="{dark_val}" input-class="{edit_tc} text-sm" autogrow rows="3"'
            )
            
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
                ui.notify('編集しました', color='positive', position='top')
                edit_dialog.close()
                chat_scroll_container.clear()
                state['rendered_msg_ids'].clear()
                state['read_count_labels'].clear()
                sync_flat_chat()
                
            with ui.row().classes('w-full justify-end mt-4 gap-2'):
                ui.button('キャンセル', on_click=edit_dialog.close).props(f'flat color={btn_color}')
                ui.button('保存', on_click=handle_save).classes('bg-cyan-600 hover:bg-cyan-500 font-bold text-white')
        edit_dialog.open()

    def set_reply_target(name, text):
        match = re.match(r"<<<REPLY:.*?:.*?(?:>>>\n)(.*)", text, re.DOTALL)
        clean_text = match.group(1) if match else text
        
        state['reply_target'] = {'name': name, 'text': clean_text}
        reply_target_label.set_text(f"{name} さんの発言に返信: {clean_text[:20]}...")
        reply_preview_container.classes(remove='hidden')
        msg_input.run_method('focus')

    def parse_and_render_text(text, is_me):
        match = re.match(r"<<<REPLY:(.*?):(.*?)(?:>>>\n)(.*)", text, re.DOTALL)
        if match:
            rep_name, rep_content, actual_text = match.groups()
            reply_bg = 'bg-white/30 border-cyan-300' if is_light else 'bg-black/20 border-cyan-500'
            reply_text = 'text-white' if is_me else ('text-slate-600' if is_light else 'text-white/60')
            
            with ui.column().classes('w-full gap-1'):
                with ui.card().classes(f'w-full {reply_bg} p-2 shadow-none border-l-2 rounded-sm mb-1 gap-0'):
                    ui.label(f"@{rep_name}").classes('text-cyan-200 dark:text-cyan-400 font-bold text-[10px]' if is_me else 'text-cyan-700 dark:text-cyan-400 font-bold text-[10px]')
                    ui.label(rep_content).classes(f'{reply_text} text-[10px] line-clamp-1')
                ui.label(actual_text).classes('whitespace-pre-wrap break-words text-sm')
        else:
            ui.label(text).classes('whitespace-pre-wrap break-words text-sm')

    @ui.refreshable
    def chat_header():
        current_flat = get_flat_by_id(flat_id) or state['flat_data']
        participants = current_flat.get('participant_ids', [])
        current_assigned_names = current_flat.get('assigned_names', {})
        approved_users = current_assigned_names.get('approved_user_ids', [])
        
        is_approved = current_user_id in approved_users
        total_p = len(participants)
        app_count = len(approved_users)

        with ui.row().classes('w-full p-3 border-b border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-slate-900 items-center justify-between shrink-0 shadow-lg z-10'):
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='arrow_back_ios_new', on_click=exit_cb).props(f'flat round color={btn_color} size=sm')
                with ui.column().classes('gap-0'):
                    ui.label('作戦会議室（匿名砂場）').classes('font-bold text-cyan-600 dark:text-cyan-400 text-sm')
                    ui.label('本名や実アイコンは隠されています').classes('text-[10px] text-slate-500 dark:text-white/50')
            
            with ui.row().classes('items-center gap-2'):
                def handle_approve():
                    res = approve_flat_recruitment(flat_id, current_user_id)
                    if res.get('status') == 'success':
                        chat_header.refresh()
                        if not res.get('is_fully_approved'):
                            ui.notify('開催に合意しました！他のメンバーの決断を待機中...', type='info', position='top')
                            
                if is_approved:
                    ui.button(f'合意済 ({app_count}/{total_p})', icon='check_circle').props('disable').classes('bg-slate-200 dark:bg-slate-700 text-cyan-600 dark:text-cyan-400 text-xs font-bold rounded-full px-4 py-1 min-h-0')
                else:
                    ui.button(f'🍻開催する ({app_count}/{total_p})', on_click=handle_approve).classes('bg-amber-500 dark:bg-amber-600 hover:bg-amber-400 text-white text-xs font-bold rounded-full px-3 py-1 min-h-0 shadow-lg animate-pulse')

                def handle_leave():
                    silent_leave_flat(flat_id, current_user_id)
                    ui.notify('作戦会議からそっと抜けました。', type='info', position='top')
                    exit_cb()
                    
                ui.button('抜ける', icon='directions_run', on_click=handle_leave).classes('bg-red-100 dark:bg-red-900/50 hover:bg-red-200 dark:hover:bg-red-800 text-red-600 dark:text-red-200 text-xs font-bold rounded-full px-3 py-1 min-h-0 border border-red-300 dark:border-red-500/30')

    with ui.column().classes('absolute inset-0 no-wrap gap-0 bg-transparent'):
        chat_header() 

        chat_scroll_container = ui.column().props('id="flat-chat-scroll"').classes('w-full flex-grow p-4 gap-4 overflow-y-auto hide-scrollbar bg-slate-100/50 dark:bg-slate-950/50')

        outer_bg = 'bg-white border-slate-200' if is_light else 'bg-slate-900 border-white/10'
        with ui.column().classes(f'w-full {outer_bg} border-t shrink-0 z-20 gap-0 p-0 m-0'):
            
            reply_bg = 'bg-slate-100 border-slate-200' if is_light else 'bg-slate-800 border-white/5'
            reply_preview_container = ui.row().classes(f'w-full hidden {reply_bg} px-4 py-2 border-b items-center justify-between')
            with reply_preview_container:
                with ui.row().classes('items-center gap-2 overflow-hidden flex-grow'):
                    ui.icon('reply', color='cyan-400', size='sm')
                    reply_target_label = ui.label('').classes('text-xs text-slate-600 dark:text-white/70 truncate')
                def clear_reply():
                    state['reply_target'] = None
                    reply_preview_container.classes(add='hidden')
                ui.button(icon='close', on_click=clear_reply).props(f'flat round color={btn_color} size=xs')

            img_prev_bg = 'bg-slate-200 border-slate-300' if is_light else 'bg-black/40 border-white/5'
            image_preview_container = ui.row().classes(f'w-full hidden {img_prev_bg} px-4 py-2 border-b items-center justify-between')
            with image_preview_container:
                with ui.row().classes('items-center gap-2'):
                    ui.icon('image', color='cyan-400')
                    preview_label = ui.label('画像添付中...').classes('text-xs text-slate-600 dark:text-white/70')
                def clear_image():
                    state['pending_image'] = None
                    image_preview_container.classes(add='hidden')
                ui.button(icon='close', on_click=clear_image).props(f'flat round color={btn_color} size=xs')

            with ui.row().classes('w-full p-3 items-center gap-2 no-wrap'):
                
                async def handle_select_image(e):
                    try:
                        file_bytes = None
                        read_result = None
                        if hasattr(e, 'content') and e.content: read_result = e.content.read()
                        elif hasattr(e, 'file') and getattr(e, 'file', None): read_result = e.file.read()
                        elif hasattr(e, 'read') and callable(e.read): read_result = e.read()
                        elif hasattr(e, 'data') and getattr(e, 'data', None): read_result = e.data if isinstance(e.data, bytes) else e.data.read()
                        
                        if inspect.isawaitable(read_result): file_bytes = await read_result
                        else: file_bytes = read_result
                        
                        filename = getattr(e, 'name', 'uploaded_image.jpg')
                        state['pending_image'] = {'bytes': file_bytes, 'name': filename}
                        preview_label.set_text(filename)
                        image_preview_container.classes(remove='hidden')
                    except Exception as ex:
                        ui.notify('画像の読み込みに失敗しました', color='negative')

                img_uploader = ui.upload(on_upload=handle_select_image, auto_upload=True, max_files=1).props('accept="image/*"').style('display: none;')
                ui.button(icon='image', on_click=lambda: img_uploader.run_method('pickFiles')).props(f'flat round color={btn_color} size=sm').tooltip('画像を送る')
                
                # ★ 修正箇所：入力フォーム自体も明示的に切り替え、白飛びを完全防止
                input_bg = 'bg-slate-100 border-slate-200' if is_light else 'bg-white/5 border-white/10'
                input_tc = 'text-slate-800' if is_light else 'text-white'
                
                msg_input = ui.input(placeholder='匿名でメッセージを入力...').classes(
                    f'flex-grow {input_bg} border rounded-full px-4 w-0 min-w-0'
                ).props(f'borderless :dark="{dark_val}" input-class="{input_tc} text-sm"').on('keydown.enter', lambda e: handle_send())
                
                ui.button(icon='send', on_click=lambda e: handle_send()).props('flat round color=cyan-400')

    def handle_send():
        val = msg_input.value or ""
        img_data = state['pending_image']
        
        if not val.strip() and not img_data: return
        
        if check_ng_words(val)['is_ng']:
            ui.notify('不適切な表現が含まれているため送信できません。', color='negative', position='top')
            return
        
        if state['reply_target'] and val:
            r_name = state['reply_target']['name'].replace(':', '：').replace('>', '＞')
            r_text = state['reply_target']['text'].replace(':', '：').replace('\n', ' ').replace('>', '＞')[:30]
            val = f"<<<REPLY:{r_name}:{r_text}>>>\n{val}"
        
        try:
            image_url = None
            if img_data:
                image_url = save_chat_image_local(img_data['bytes'], img_data['name'])
                
            send_message(state['chat_room_id'], current_user_id, val, image_url=image_url)
            
            msg_input.set_value('')
            clear_image()
            clear_reply()
            sync_flat_chat()
        except Exception as e:
            ui.notify(f"送信に失敗しました: {e}", color='negative')

    def sync_flat_chat():
        try:
            current_flat = get_flat_by_id(flat_id)
            if not current_flat:
                ui.notify('この募集は消滅しました', type='warning', position='top')
                exit_cb()
                return
                
            participants = current_flat.get('participant_ids', [])
            status = current_flat.get('status')
            
            if status == "開催確定":
                ui.notify('🎉 全員の合意がとれました！公式イベントに昇格し、実名チャットへ移行します！', type='positive', position='center', duration=5)
                ui.timer(2.0, lambda: enter_real_chat_cb(state['chat_room_id']), once=True)
                return
            
            if current_user_id not in participants or status != "作戦会議中":
                ui.notify('参加人数が下回ったため、作戦会議は中断されました。', type='warning', position='top')
                exit_cb()
                return

            current_assigned_names = current_flat.get('assigned_names', {})
            new_approved = current_assigned_names.get('approved_user_ids', [])
            old_approved = state['flat_data'].get('assigned_names', {}).get('approved_user_ids', [])
            if len(new_approved) != len(old_approved):
                state['flat_data'] = current_flat
                chat_header.refresh() 

            messages = fetch_messages(state['chat_room_id'])
            has_new = False
            
            for msg in messages:
                msg_id = msg['id']
                read_count = max(0, len(msg.get('read_user_ids', [])) - 1)
                
                if msg_id in state['rendered_msg_ids']:
                    if msg_id in state['read_count_labels']:
                        label = state['read_count_labels'][msg_id]
                        if read_count > 0 and label:
                            label.set_text(f'既読 {read_count}')
                            label.set_visibility(True)
                else:
                    has_new = True
                    state['rendered_msg_ids'].add(msg_id)
                    
                    is_me = (msg.get('user_id') == current_user_id)
                    
                    pseudo_name = current_assigned_names.get(msg.get('user_id'), '名無しのゲスト')
                    avatar = get_anonymous_avatar(pseudo_name)
                    text = msg.get('message', '')
                    image_url = msg.get('image_url')
                    
                    raw_time = msg.get('created_at', '')
                    time_str = ''
                    if raw_time:
                        try:
                            raw_time = raw_time.replace('Z', '+00:00')
                            dt = date_parser.isoparse(raw_time)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            diff = now - dt
                            if diff.total_seconds() < 0:
                                time_str = "たった今"
                            else:
                                if diff.days > 0:
                                    time_str = f"{diff.days}日前"
                                elif diff.seconds >= 3600:
                                    time_str = f"{diff.seconds // 3600}時間前"
                                elif diff.seconds >= 60:
                                    time_str = f"{diff.seconds // 60}分前"
                                else:
                                    time_str = "たった今"
                        except Exception as e:
                            print(f"日付計算エラー: {e}")
                    
                    with chat_scroll_container:
                        read_label = None
                        
                        def trigger_msg_delete(m_id):
                            msg_to_delete['id'] = m_id
                            confirm_msg_delete_dialog.open()

                        if is_me:
                            with ui.row().classes('w-full items-start justify-end gap-2 mt-2'):
                                with ui.column().classes('gap-0.5 items-end flex-grow'):
                                    with ui.row().classes('gap-3 items-center opacity-60 hover:opacity-100 transition mb-0.5 mr-1'):
                                        ui.button(icon='edit', on_click=lambda e, m=msg_id, t=text: open_edit_chat_dialog(m, t)).props(f'flat round size=xs color=cyan-500 dark:color=cyan-400').classes('p-0 min-h-0 min-w-0').tooltip('編集')
                                        ui.button(icon='delete', on_click=lambda e, m=msg_id: trigger_msg_delete(m)).props('flat round size=xs color=red-500 dark:color=red-400').classes('p-0 min-h-0 min-w-0').tooltip('削除')
                                    
                                    with ui.row().classes('items-end gap-1.5'):
                                        with ui.column().classes('items-end gap-0 mb-1'):
                                            read_label = ui.label(f'既読 {read_count}').classes('text-[9px] text-cyan-600 dark:text-cyan-400 font-bold leading-none mb-0.5')
                                            read_label.set_visibility(read_count > 0)
                                            if time_str: ui.label(time_str).classes('text-[9px] text-slate-400 dark:text-white/40 leading-none')
                                        
                                        card_bg = 'bg-cyan-500 text-white' if is_light else 'bg-cyan-700/80 text-white'
                                        with ui.card().classes(f'p-3 {card_bg} backdrop-blur rounded-l-xl rounded-br-xl text-sm max-w-xs shadow-sm flex flex-col gap-2'):
                                            if image_url: lightbox_image(image_url, thumbnail_classes='w-48 rounded-lg cursor-pointer hover:opacity-80 transition-opacity')
                                            if text: parse_and_render_text(text, is_me=True)
                        else:
                            with ui.row().classes('w-full items-start gap-2 mt-2'):
                                ui.image(avatar).classes('w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-800 shrink-0 mt-3 border border-cyan-400/50 dark:border-cyan-500/30')
                                
                                with ui.column().classes('gap-0.5 flex-grow'):
                                    with ui.row().classes('w-full items-center justify-start gap-3'):
                                        ui.label(pseudo_name).classes('text-[10px] text-cyan-700 dark:text-cyan-300 font-bold')
                                        with ui.row().classes('gap-3 items-center opacity-60 hover:opacity-100 transition'):
                                            ui.button(icon='reply', on_click=lambda e, n=pseudo_name, t=text: set_reply_target(n, t)).props(f'flat round size=xs color={btn_color}').classes('p-0 min-h-0 min-w-0').tooltip('返信')
                                                
                                    with ui.row().classes('items-end gap-1.5'):
                                        card_bg = 'bg-white text-slate-800 border border-slate-200' if is_light else 'bg-slate-800/80 text-white border border-white/5'
                                        with ui.card().classes(f'p-3 {card_bg} backdrop-blur rounded-r-xl rounded-bl-xl text-sm max-w-xs shadow-sm flex flex-col gap-2'):
                                            if image_url: lightbox_image(image_url, thumbnail_classes='w-48 rounded-lg cursor-pointer hover:opacity-80 transition-opacity')
                                            if text: parse_and_render_text(text, is_me=False)
                                        
                                        with ui.column().classes('items-start gap-0 mb-1'):
                                            read_label = ui.label(f'既読 {read_count}').classes('text-[9px] text-cyan-600 dark:text-cyan-400 font-bold leading-none mb-0.5')
                                            read_label.set_visibility(read_count > 0)
                                            if time_str: ui.label(time_str).classes('text-[9px] text-slate-400 dark:text-white/40 leading-none')
                        
                        state['read_count_labels'][msg_id] = read_label
                        
            if has_new:
                ui.run_javascript('setTimeout(() => { var el = document.getElementById("flat-chat-scroll"); if(el) el.scrollTop = el.scrollHeight; }, 100);')
                mark_as_read(state['chat_room_id'], current_user_id)

        except Exception as e:
            print(f"砂場チャット同期エラー: {e}")

    sync_flat_chat()
    ui.timer(3.0, sync_flat_chat)