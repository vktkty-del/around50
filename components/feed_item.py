# components/feed_item.py
from nicegui import app, ui, context
import inspect
import uuid
import os
import io
import re
import themes
from PIL import Image, ImageOps

from components.comp_profile import show_profile_dialog 
from components.reply_view import open_post_detail_dialog
from database.timeline_db import (
    fetch_timeline_posts, 
    create_post, 
    toggle_like, 
    delete_post, 
    get_user_like_status, 
    link_chat_room_to_post, 
    update_post_content, 
    update_full_post, 
    toggle_pin_status
)
from database.chat_db import create_chat_room
from database.su_db import create_support_ticket
from utils.validator import check_ng_words
from components.lightbox import lightbox_image
from components.avatar import draw_user_avatar

def extract_file_data(e):
    name = "uploaded_image.jpg"
    data = None
    try:
        if hasattr(e, 'name'): name = e.name
        content_obj = getattr(e, 'content', getattr(e, 'file', getattr(e, 'data', None)))
        if content_obj:
            data = content_obj.read() if hasattr(content_obj, 'read') else content_obj
    except Exception:
        pass
    return name, data

def compress_and_save_image(file_bytes: bytes, filepath: str) -> bool:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)
        
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
            
        max_size = 1600
        width, height = img.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.ANTIALIAS
            img = img.resize((new_width, new_height), resample_filter)
            
        img.save(filepath, 'WEBP', quality=85, method=4)
        return True
    except Exception as ex:
        print(f"💡 [画像処理システム] 圧縮変換中にエラーが発生しました: {ex}")
        return False

def render_image_grid_ui(urls: list, is_preview: bool = False, on_remove_cb = None):
    count = len(urls)
    if count == 0:
        return

    grid_classes = "grid w-full relative gap-1.5 rounded-xl overflow-hidden"
    if count == 1: grid_classes += " grid-cols-1"
    elif count == 2: grid_classes += " grid-cols-2"
    elif count >= 3: grid_classes += " grid-cols-2 grid-rows-2"

    with ui.element('div').classes(grid_classes).style('aspect-ratio: 16/9; max-height: 500px;'):
        for idx, url in enumerate(urls):
            cell_classes = "relative w-full h-full overflow-hidden bg-black/50"
            if count == 3 and idx == 0: cell_classes += " row-span-2 h-full"
            else: cell_classes += " h-full"
            
            with ui.element('div').classes(cell_classes):
                if is_preview:
                    ui.image(url).classes('w-full h-full object-cover')
                    if on_remove_cb:
                        ui.button(icon='close', on_click=lambda _, u=url: on_remove_cb(u))\
                            .props('flat round size=xs color=white')\
                            .classes('absolute top-1 right-1 bg-black/60 rounded-full z-20')
                else:
                    lightbox_image(url, thumbnail_classes='w-full h-full object-cover cursor-pointer hover:opacity-90 transition')

# =========================================================================
# タイムライン描画コンポーネント (引数は元の形式に100%完全復元します)
# =========================================================================
def render_timeline(current_user_id: str, current_user_name: str, avatar_url: str, is_su: bool, refresh_cb, change_menu_cb):
    ui_elements = {'likes': {}, 'replies': {}}
    dialog_container = ui.element('div').classes('hidden')
    
    # ── [★重要変更] app.storageへの直接アクセスを安全な try-except で100%クラッシュガード ──
    try:
        muted_users = app.storage.user.get('muted_users', [])
    except Exception:
        muted_users = []

    try:
        auto_open_pid = app.storage.user.get('auto_open_post_id')
        if auto_open_pid:
            app.storage.user['auto_open_post_id'] = None
    except Exception:
        auto_open_pid = None

    post_state = {
        'edit_post_id': None,
        'title': '',
        'content': '',
        'image_urls': [],
        'allow_chat': False
    }

    def handle_delete(pid):
        delete_post(pid)
        ui.notify('削除しました', color='negative', position='top')
        posts_list.refresh()

    def confirm_delete(pid):
        dialog_container.clear()
        with dialog_container:
            with ui.dialog() as confirm_dialog, ui.card().classes('bg-white dark:bg-slate-900 border border-gray-200 dark:border-white/20 p-6 shadow-2xl rounded-xl w-[320px]'):
                ui.icon('delete_outline', size='3xl', color='red-500').classes('w-full flex justify-center mb-2')
                ui.label('本当に削除しますか？').classes('text-base font-bold text-slate-800 dark:text-white text-center w-full mb-1')
                ui.label('この操作は取り消すことができません。').classes('text-xs text-slate-500 dark:text-white/60 text-center w-full mb-6')
                
                with ui.row().classes('w-full gap-3 justify-between no-wrap'):
                    ui.button('キャンセル', on_click=confirm_dialog.close).props('flat').classes('text-slate-600 dark:text-white flex-grow font-bold')
                    def do_delete():
                        handle_delete(pid)
                        confirm_dialog.close()
                    ui.button('削除する', on_click=do_delete).classes('bg-red-500 hover:bg-red-600 text-white font-bold flex-grow rounded-lg shadow-md')
        confirm_dialog.open()

    def confirm_create_chat(post):
        post_id = post['id']
        raw_title = post.get('title') or ""
        
        if raw_title.startswith('【新規イベント】') or raw_title.startswith('【イベント】'):
            genre = 'event'
            room_title = raw_title.replace('【新規イベント】', '').replace('【イベント】', '').strip() or "イベントチャット"
            description = f"イベント「{room_title}」の公式連携チャットです。みんなで盛り上がりましょう！"
        else:
            genre = 'daily'
            room_title = raw_title or f"{post.get('user_name', 'メンバー')} さんの話題"
            description = "タイムラインの投稿から自動作成された連携ルームです。気軽に語り合いましょう！"

        dialog_container.clear()
        with dialog_container:
            with ui.dialog() as confirm_chat_dialog, ui.card().classes('bg-white dark:bg-slate-900 border border-gray-200 dark:border-white/20 p-6 shadow-2xl rounded-xl w-[320px]'):
                ui.icon('add_comment', size='3xl', color='amber-500').classes('w-full flex justify-center mb-2')
                ui.label('チャットルームを作成しますか？').classes('text-base font-bold text-slate-800 dark:text-white text-center w-full mb-1')
                ui.label(f'ジャンル：{ "📅 イベント" if genre == "event" else "💬 日常" } として専用ルームを作成します。').classes('text-xs text-slate-500 dark:text-white/60 text-center w-full mb-6')
                
                with ui.row().classes('w-full gap-3 justify-between no-wrap'):
                    ui.button('キャンセル', on_click=confirm_chat_dialog.close).props('flat').classes('text-slate-600 dark:text-white flex-grow font-bold')
                    def do_create():
                        new_room = create_chat_room(room_title, created_by=current_user_id, genre=genre, description=description)
                        if new_room:
                            link_chat_room_to_post(post_id, new_room['id'])
                            ui.notify('専用チャットルームを生成しました！', color='positive', position='top')
                            posts_list.refresh()
                        confirm_chat_dialog.close()
                    ui.button('作成する', on_click=do_create).classes('bg-amber-500 hover:bg-amber-600 text-white font-bold flex-grow rounded-lg shadow-md')
        confirm_chat_dialog.open()

    def handle_mute_user(target_user_id, target_user_name):
        nonlocal muted_users
        try:
            muted_list = app.storage.user.get('muted_users', [])
            if target_user_id not in muted_list:
                muted_list.append(target_user_id)
                app.storage.user['muted_users'] = muted_list
                muted_users = muted_list
                ui.notify(f'{target_user_name} さんをミュートしました。', color='warning', position='top')
                posts_list.refresh()
        except Exception:
            pass

    def open_report_dialog(post_data):
        dialog_container.clear()
        with dialog_container:
            with ui.dialog() as report_dialog, ui.card().classes('bg-white dark:bg-slate-900 border border-gray-200 dark:border-white/20 p-6 shadow-2xl rounded-xl w-[320px]'):
                ui.icon('report_problem', size='3xl', color='red-500').classes('w-full flex justify-center mb-2')
                ui.label('この投稿を通報する').classes('text-base font-bold text-slate-800 dark:text-white text-center w-full mb-2')
                
                reason_input = ui.textarea(placeholder='通報の理由（スパム、不適切など）を入力してください...')\
                    .classes('w-full bg-slate-100 dark:bg-black/30 border border-slate-300 dark:border-white/10 rounded-lg p-2 mb-4')\
                    .props('borderless input-class="text-slate-800 dark:text-white text-sm" autogrow')

                with ui.row().classes('w-full gap-3 justify-between no-wrap'):
                    ui.button('キャンセル', on_click=report_dialog.close).props('flat').classes('text-slate-600 dark:text-white flex-grow font-bold')
                    
                    def submit_report():
                        reason_text = reason_input.value or ""
                        if not reason_text.strip():
                            ui.notify('通報理由を入力してください', color='warning', position='top')
                            return
                        
                        try:
                            report_title = f"【通報】不適切な投稿の報告"
                            report_content = (
                                f"対象ユーザー: {post_data.get('user_name')} (ID: {post_data['user_id']})\n"
                                f"投稿ID: {post_data['id']}\n\n"
                                f"【通報理由】\n{reason_text}\n\n"
                                f"【対象の投稿内容】\n{post_data.get('content', '')}"
                            )
                            create_support_ticket(current_user_id, report_title, report_content, priority='high')
                            
                            ui.notify('運営に通報を送信しました。ご協力ありがとうございます。', color='positive', position='top')
                            report_dialog.close()
                        except Exception as e:
                            ui.notify(f"通報エラー: {e}", color='negative', position='top')
                        
                    ui.button('送信する', on_click=submit_report).classes('bg-red-500 hover:bg-red-600 text-white font-bold flex-grow rounded-lg shadow-md')
        report_dialog.open()


    # =========================================================================
    # ⚙️ 新規投稿/編集 共通ダイアログ（静的定義）
    # =========================================================================
    with ui.dialog() as post_dialog, ui.card().classes('post-wizard-card bg-slate-900 border border-white/20 text-white w-[500px] max-w-full p-0 overflow-y-auto clean-scroll max-h-[95vh] shadow-2xl'):
        
        with ui.row().classes('post-wizard-header w-full px-5 py-4 justify-between items-center bg-black/40 border-b border-white/10 sticky top-0 z-50 backdrop-blur-md'):
            wizard_title_label = ui.label('新規投稿').classes('text-lg font-bold tracking-wide text-white')
            ui.button(icon='close', on_click=lambda: (post_dialog.close(), img_uploader.run_method('reset')) if 'img_uploader' in locals() else post_dialog.close())\
                .props('flat round size=sm color=white')

        with ui.stepper().props('vertical flat').classes('w-full bg-transparent text-white') as stepper:
            with ui.step('画像を選択').classes('w-full p-2'):
                
                cropper_container = ui.element('div').classes('w-full hidden')
                with cropper_container:
                    with ui.row().classes('w-full justify-between items-center mb-2'):
                        ui.label('画像の表示範囲を調整').classes('text-white font-bold text-sm')
                        crop_progress_label = ui.label('').classes('text-xs font-bold text-cyan-400 bg-cyan-400/10 px-2 py-1 rounded-full hidden')

                    crop_img_html = ui.html('').classes('w-full bg-black/50 rounded-xl overflow-hidden').style('height: 50vh; max-height: 400px; min-height: 200px;')
                    
                    with ui.row().classes('w-full justify-start items-center gap-2 mt-4 flex-wrap'):
                        ui.button('破棄', on_click=lambda: cancel_crop()).props('outline').classes('post-wizard-btn-dismiss text-xs text-white border-white/50 hover:bg-white/10')
                        ui.button('そのまま', on_click=lambda: skip_crop()).props('outline color=primary').classes('text-xs')
                        ui.button('1:1', on_click=lambda: ui.run_javascript('window.cropper.setAspectRatio(1)')).props('outline color=primary').classes('text-xs')
                        ui.button('4:3', on_click=lambda: ui.run_javascript('window.cropper.setAspectRatio(4/3)')).props('outline color=primary').classes('text-xs')
                        ui.button('16:9', on_click=lambda: ui.run_javascript('window.cropper.setAspectRatio(16/9)')).props('outline color=primary').classes('text-xs')
                        ui.button('フリー', on_click=lambda: ui.run_javascript('window.cropper.setAspectRatio(NaN)')).props('outline color=primary').classes('text-xs')
                        ui.button('切り抜いて決定', on_click=lambda: trigger_crop()).props('outline="false"').classes('bg-primary text-white font-bold px-4 rounded-full text-xs ml-auto shadow-md hover:scale-105 transition-transform border-0')

                upload_btn_area = ui.element('div').classes('w-full')
                with upload_btn_area:
                    def remove_preview_image(url_to_remove):
                        post_state['image_urls'] = [u for u in post_state['image_urls'] if u != url_to_remove]
                        draw_upload_previews.refresh()
                    def clear_all_images():
                        post_state['image_urls'] = []
                        img_uploader.run_method('reset')
                        draw_upload_previews.refresh()

                    img_uploader = ui.upload(auto_upload=True, on_upload=lambda e: handle_upload(e), max_files=4, multiple=True)\
                        .props('accept=".jpg,.jpeg,.png,.webp,.gif,image/*"').style('display: none;')

                    with ui.card().classes('post-wizard-upload-card w-full border-2 border-dashed border-white/30 bg-black/20 hover:bg-black/40 cursor-pointer items-center justify-center p-8 shadow-none mb-4 transition-colors')\
                        .on('click', lambda: img_uploader.run_method('pickFiles')):
                        ui.icon('add_photo_alternate', size='4xl', color='cyan-400').classes('opacity-80')
                        ui.label('クリックして画像を選択').classes('text-white mt-2 font-bold tracking-wide')
                        ui.label('最大4枚 (複数選択可能)').classes('text-white/40 text-[11px] mt-1')

                draw_upload_previews_area = ui.element('div').classes('w-full')
                with draw_upload_previews_area:
                    @ui.refreshable
                    def draw_upload_previews():
                        urls = post_state['image_urls']
                        if not urls: return
                        with ui.column().classes('post-wizard-preview-area w-full bg-black/20 p-3 rounded-xl border border-white/10'):
                            render_image_grid_ui(urls, is_preview=True, on_remove_cb=remove_preview_image)
                            with ui.row().classes('w-full justify-between items-center mt-2 pt-2 border-t border-white/5'):
                                ui.label(f'選択済み: {len(urls)} / 4枚').classes('text-xs text-white/60')
                                ui.button('すべてクリア', on_click=clear_all_images).props('flat dense size=sm color=red-400')

                temp_crop_state = {
                    'filepath': None, 
                    'queue': [], 
                    'is_cropping': False, 
                    'current_index': 0
                }
                
                def update_crop_progress():
                    total_in_batch = temp_crop_state['current_index'] + len(temp_crop_state['queue'])
                    if total_in_batch > 1:
                        crop_progress_label.set_text(f"{temp_crop_state['current_index']} / {total_in_batch} 枚目を調整中")
                        crop_progress_label.classes(remove='hidden')
                    else:
                        crop_progress_label.classes(add='hidden')
                
                def process_next_in_queue():
                    if temp_crop_state['is_cropping']:
                        return 
                        
                    if not temp_crop_state['queue']:
                        cropper_container.classes(add='hidden')
                        upload_btn_area.classes(remove='hidden')
                        draw_upload_previews_area.classes(remove='hidden')
                        img_uploader.run_method('reset')
                        temp_crop_state['current_index'] = 0
                        return
                        
                    temp_crop_state['is_cropping'] = True
                    temp_crop_state['current_index'] += 1
                    next_filepath = temp_crop_state['queue'].pop(0)
                    temp_crop_state['filepath'] = next_filepath
                    
                    update_crop_progress()
                    
                    upload_btn_area.classes(add='hidden')
                    draw_upload_previews_area.classes(add='hidden')
                    cropper_container.classes(remove='hidden')
                    
                    img_url = f"/{next_filepath}?t={uuid.uuid4().hex}" 
                    crop_img_html.content = f'<img id="image_to_crop" src="{img_url}" style="max-width: 100%; display: block; margin: 0 auto;">'
                    
                    ui.run_javascript('''
                        setTimeout(() => {
                            const image = document.getElementById('image_to_crop');
                            if(window.cropper) { window.cropper.destroy(); }
                            window.cropper = new Cropper(image, {
                                viewMode: 1, 
                                dragMode: 'move', 
                                autoCropArea: 0.9,
                                restore: false,
                                guides: true,
                                center: true,
                                highlight: false,
                                cropBoxMovable: true,
                                cropBoxResizable: true,
                                toggleDragModeOnDblclick: false,
                            });
                        }, 100);
                    ''')
                
                async def handle_upload(e):
                    name, data = extract_file_data(e)
                    if inspect.isawaitable(data): data = await data
                    if not data: return
                    
                    total_future_images = len(post_state['image_urls']) + len(temp_crop_state['queue']) + (1 if temp_crop_state['is_cropping'] else 0)
                    if total_future_images >= 4:
                        ui.notify('添付できる画像は最大4枚までです！', type='warning', position='top')
                        return
                    
                    temp_filename = f"temp_crop_{uuid.uuid4()}.webp"
                    temp_filepath = f"static/posts/{temp_filename}"
                    os.makedirs('static/posts', exist_ok=True)
                    
                    success = compress_and_save_image(data, temp_filepath)
                    if not success:
                        with open(temp_filepath, 'wb') as f: f.write(data)
                        
                    temp_crop_state['queue'].append(temp_filepath)
                    process_next_in_queue()

                # ★ 改善：ui.on イベント登録を完全撤去。
                # JSの実行完了（Cropper座標データ）を直接Python側で async/await 同期キャッチして
                # ページの切り替え時（動的リビルド時）にNiceGUIがDOM初期化暴走（テーマ崩れ）するバグを根本解決。
                async def trigger_crop():
                    crop_data = await ui.run_javascript('''
                        if (window.cropper) {
                            const data = window.cropper.getData(true);
                            window.cropper.destroy();
                            window.cropper = null;
                            return data;
                        }
                        return null;
                    ''')
                    
                    if not crop_data:
                        finish_crop_step(add_to_list=False)
                        return
                        
                    filepath = temp_crop_state['filepath']
                    if not filepath or not os.path.exists(filepath):
                        finish_crop_step(add_to_list=False)
                        return
                        
                    try:
                        img = Image.open(filepath)
                        x = int(crop_data['x'])
                        y = int(crop_data['y'])
                        w = int(crop_data['width'])
                        h = int(crop_data['height'])
                        r = int(crop_data.get('rotate', 0))
                        
                        if r != 0:
                            img = img.rotate(-r, expand=True)
                            
                        img = img.crop((x, y, x + w, y + h))
                        
                        final_filename = f"post_{uuid.uuid4()}.webp"
                        final_filepath = f"static/posts/{final_filename}"
                        img.save(final_filepath, 'WEBP', quality=85)
                        
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            
                        temp_crop_state['filepath'] = final_filepath
                        finish_crop_step(add_to_list=True)
                        
                    except Exception as ex:
                        print(f"💡 [画像切り抜き] エラー: {ex}")
                        finish_crop_step(add_to_list=False)
                    
                def cancel_crop():
                    ui.run_javascript('if(window.cropper){ window.cropper.destroy(); window.cropper=null; }')
                    filepath = temp_crop_state['filepath']
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                    finish_crop_step(add_to_list=False)

                def skip_crop():
                    ui.run_javascript('if(window.cropper){ window.cropper.destroy(); window.cropper=null; }')
                    filepath = temp_crop_state['filepath']
                    if filepath and os.path.exists(filepath):
                        final_filename = f"post_{uuid.uuid4()}.webp"
                        final_filepath = f"static/posts/{final_filename}"
                        os.rename(filepath, final_filepath)
                        
                        temp_crop_state['filepath'] = final_filepath
                        finish_crop_step(add_to_list=True)
                    else:
                        finish_crop_step(add_to_list=False)

                def finish_crop_step(add_to_list=True):
                    if add_to_list and temp_crop_state['filepath']:
                        post_state['image_urls'].append(f"/{temp_crop_state['filepath']}")
                        draw_upload_previews.refresh()
                        
                    temp_crop_state['filepath'] = None
                    temp_crop_state['is_cropping'] = False
                    
                    process_next_in_queue()

                with ui.stepper_navigation().classes('w-full mt-4'):
                    ui.button('次へ', on_click=stepper.next).props('outline="false"').classes('bg-primary text-white font-bold px-6 py-2 rounded-full border-0')

            with ui.step('詳細を入力').classes('w-full'):
                post_title_input = ui.input(placeholder='タイトル (省略可)').classes('post-wizard-input w-full mb-3')\
                    .props('borderless input-class="text-white font-bold bg-white/5 rounded-lg px-3 py-2 border border-white/10"')
                post_content_input = ui.textarea(placeholder='キャプションを入力...').classes('post-wizard-input w-full mb-3')\
                    .props('borderless input-class="text-white bg-white/5 rounded-lg px-3 py-2 border border-white/10 min-h-[100px]" autogrow')
                
                chk_chat = ui.checkbox('チャット許可（専用ルーム作成）').classes('post-wizard-chk text-sm text-white/70 mb-4')

                def execute_db_action(status='approved', highlighted_content=None):
                    try:
                        serialized_images = ",".join(post_state['image_urls']) if post_state['image_urls'] else None
                        is_edit = post_state['edit_post_id'] is not None
                        if is_edit:
                            update_full_post(post_state['edit_post_id'], post_title_input.value.strip(), post_content_input.value.strip(), serialized_images, status=status, highlighted_content=highlighted_content)
                            ui.notify('編集を保存しました！', color='positive', position='top')
                        else:
                            create_post(current_user_id, post_content_input.value.strip(), serialized_images, chk_chat.value, title=post_title_input.value.strip(), status=status, highlighted_content=highlighted_content)
                            ui.notify('投稿しました！', color='positive', position='top')
                    except Exception as e:
                        ui.notify('エラーが発生しました', color='negative', position='top')
                        return
                    post_dialog.close()
                    posts_list.refresh()

                def handle_post_submit():
                    content_val = post_content_input.value or ""
                    title_val = post_title_input.value or ""
                    if not content_val.strip() and not post_state['image_urls']:
                        ui.notify('画像またはテキストを入力してください', color='warning', position='top')
                        return
                    check_text = f"{title_val}\n{content_val}"
                    ng_result = check_ng_words(check_text)
                    if ng_result['is_ng']:
                        with ui.dialog() as ng_dialog, ui.card().classes('post-wizard-card bg-slate-900 border border-red-500/50 text-white w-[320px] p-6 shadow-2xl'):
                            ui.icon('warning', color='red-500', size='3xl').classes('w-full flex justify-center mb-2')
                            ui.label('不適切な表現が含まれている可能性があります').classes('text-base font-bold text-red-400 text-center w-full leading-tight mb-2')
                            with ui.row().classes('w-full justify-between gap-2 mt-4'):
                                ui.button('書き直す', on_click=ng_dialog.close).props('flat color=white').classes('flex-grow')
                                def submit_pending():
                                    execute_db_action(status='pending', highlighted_content=ng_result['highlighted_text'])
                                    ng_dialog.close()
                                ui.button('審議に出す', on_click=submit_pending).props('outline="false"').classes('bg-red-600 hover:bg-red-500 text-white font-bold flex-grow border-0')
                        ng_dialog.open()
                    else: execute_db_action(status='approved')

                with ui.stepper_navigation().classes('w-full flex gap-3 mt-2'):
                    ui.button('戻る', on_click=stepper.previous).props('flat color=white').classes('px-4 py-2')
                    btn_submit = ui.button('シェアする', on_click=handle_post_submit).props('outline="false"').classes('bg-primary text-white font-bold px-8 py-2 rounded-full shadow-lg ml-auto border-0')


    def open_post_wizard(edit_post=None):
        stepper.set_value('画像を選択')
        
        if edit_post:
            post_state['edit_post_id'] = edit_post['id']
            post_state['title'] = edit_post.get('title') or ''
            post_state['content'] = edit_post.get('content') or ''
            post_state['allow_chat'] = edit_post.get('allow_chat', False)
            if edit_post.get('image_url'):
                post_state['image_urls'] = [u.strip() for u in edit_post['image_url'].split(',') if u.strip()]
            else:
                post_state['image_urls'] = []
                
            wizard_title_label.set_text('投稿を編集')
            btn_submit.set_text('更新する')
        else:
            post_state['edit_post_id'] = None
            post_state['title'] = ''
            post_state['content'] = ''
            post_state['allow_chat'] = False
            post_state['image_urls'] = []
            
            wizard_title_label.set_text('新規投稿')
            btn_submit.set_text('シェアする')

        post_title_input.set_value(post_state['title'])
        post_content_input.set_value(post_state['content'])
        chk_chat.set_value(post_state['allow_chat'])
        
        draw_upload_previews.refresh()
        post_dialog.open()

        ui.run_javascript('''
            setTimeout(() => {
                const isLight = document.body.classList.contains('theme-light') || document.body.className.includes('theme-light') || document.querySelector('.theme-light');
                const card = document.querySelector('.post-wizard-card');
                if (card) {
                    if (isLight) {
                        card.style.setProperty('background-color', '#ffffff', 'important');
                        card.style.setProperty('color', '#1e293b', 'important');
                        card.style.setProperty('border-color', '#e2e8f0', 'important');
                        
                        const header = card.querySelector('.post-wizard-header');
                        if (header) {
                            header.style.setProperty('background-color', '#f1f5f9', 'important');
                            header.style.setProperty('border-color', '#cbd5e1', 'important');
                        }
                        
                        card.querySelectorAll('.text-white').forEach(el => {
                            el.style.setProperty('color', '#1e293b', 'important');
                        });
                        
                        card.querySelectorAll('.post-wizard-btn-dismiss').forEach(el => {
                            el.style.setProperty('color', '#475569', 'important');
                            el.style.setProperty('border-color', '#cbd5e1', 'important');
                        });
                        
                        const uploadCard = card.querySelector('.post-wizard-upload-card');
                        if (uploadCard) {
                            uploadCard.style.setProperty('background-color', '#f8fafc', 'important');
                            uploadCard.style.setProperty('border-color', '#cbd5e1', 'important');
                        }

                        const previewArea = card.querySelector('.post-wizard-preview-area');
                        if (previewArea) {
                            previewArea.style.setProperty('background-color', '#f8fafc', 'important');
                            previewArea.style.setProperty('border-color', '#e2e8f0', 'important');
                        }
                        
                        card.querySelectorAll('.post-wizard-input input, .post-wizard-input textarea').forEach(el => {
                            el.style.setProperty('color', '#1e293b', 'important');
                            el.style.setProperty('background-color', '#f1f5f9', 'important');
                            el.style.setProperty('border-color', '#cbd5e1', 'important');
                        });

                        const chkLabel = card.querySelector('.post-wizard-chk span');
                        if (chkLabel) {
                            chkLabel.style.setProperty('color', '#475569', 'important');
                        }
                    } else {
                        card.style.removeProperty('background-color');
                        card.style.removeProperty('color');
                        card.style.removeProperty('border-color');
                        
                        const header = card.querySelector('.post-wizard-header');
                        if (header) {
                            header.style.removeProperty('background-color');
                            header.style.removeProperty('border-color');
                        }
                        
                        card.querySelectorAll('.text-white').forEach(el => {
                            el.style.removeProperty('color');
                        });
                        
                        card.querySelectorAll('.post-wizard-btn-dismiss').forEach(el => {
                            el.style.removeProperty('color');
                            el.style.removeProperty('border-color');
                        });
                        
                        const uploadCard = card.querySelector('.post-wizard-upload-card');
                        if (uploadCard) {
                            uploadCard.style.removeProperty('background-color');
                            uploadCard.style.removeProperty('border-color');
                        }

                        const previewArea = card.querySelector('.post-wizard-preview-area');
                        if (previewArea) {
                            previewArea.style.removeProperty('background-color');
                            previewArea.style.removeProperty('border-color');
                        }
                        
                        card.querySelectorAll('.post-wizard-input input, .post-wizard-input textarea').forEach(el => {
                            el.style.removeProperty('color');
                            el.style.removeProperty('background-color');
                            el.style.removeProperty('border-color');
                        });

                        const chkLabel = card.querySelector('.post-wizard-chk span');
                        if (chkLabel) {
                            chkLabel.style.removeProperty('color');
                        }
                    }
                }
            }, 50);
        ''')


    # ==========================================
    # タイムライン 画面表示領域
    # ==========================================
    with ui.column().classes('w-full m-0 p-0 gap-4') as main_container:
        with ui.row().classes('w-full justify-between items-center mb-2 mt-2'):
            ui.label('タイムライン').classes('text-2xl font-extrabold tracking-wider text-white')
            ui.button('＋ 新規投稿', on_click=lambda: open_post_wizard())\
                .props('outline color=primary')\
                .classes('font-bold text-white rounded-full px-5 py-1.5 shadow-xl transition-transform hover:scale-105')

        @ui.refreshable
        def posts_list():
            nonlocal auto_open_pid, muted_users
            ui_elements['likes'].clear()
            ui_elements['replies'].clear()
            db_posts = fetch_timeline_posts()
            
            if auto_open_pid:
                matched_post = next((p for p in db_posts if str(p['id']) == str(auto_open_pid)), None)
                if matched_post and matched_post['user_id'] not in muted_users:
                    ui.timer(0.2, lambda: open_post_detail_dialog(matched_post, current_user_id, current_user_name, avatar_url, is_su, dialog_container), once=True)
                auto_open_pid = None

            for post in db_posts:
                if post['user_id'] in muted_users:
                    def handle_unmute(uid=post['user_id'], uname=post.get('user_name', 'ユーザー')):
                        nonlocal muted_users
                        try:
                            if context.client and context.client.has_socket_connection:
                                m_list = app.storage.user.get('muted_users', [])
                                if uid in m_list:
                                    m_list.remove(uid)
                                    app.storage.user['muted_users'] = m_list
                                    muted_users = m_list 
                                    ui.notify(f'{uname} さんのミュートを解除しました', color='positive', position='top')
                                    posts_list.refresh()
                        except Exception:
                            pass
                            
                    with ui.card().classes('w-full bg-slate-100/50 dark:bg-black/20 border border-slate-200 dark:border-white/5 py-2 px-3 mb-5 rounded-xl shadow-none flex-row items-center gap-2 cursor-pointer hover:bg-slate-200/50 dark:hover:bg-white/5 transition-colors').on('click', lambda e, uid=post['user_id'], uname=post.get('user_name', 'ユーザー'): handle_unmute(uid, uname)):
                        ui.icon('visibility_off', size='sm').classes('text-slate-400 dark:text-white/40 pointer-events-none')
                        ui.label(f"{post.get('user_name', 'ユーザー')} さんの投稿をミュート解除").classes('text-xs text-slate-500 dark:text-white/50 font-bold pointer-events-none')
                    continue

                is_pinned = post.get('is_pinned', False)
                card_cls = 'w-full hibi-glass p-0 shadow-2xl overflow-hidden mb-5 transition-all rounded-none sm:rounded-xl border-y sm:border border-white/10'
                if is_pinned: card_cls += ' border-[2px] border-amber-500/40 bg-amber-900/10'
                
                with ui.card().classes(card_cls):
                    
                    # ① ヘッダー
                    with ui.row().classes('w-full px-4 py-3 items-center border-b border-white/5'):
                        with ui.row().classes('items-center gap-3 cursor-pointer hover:opacity-80 transition flex-grow').on('click', lambda *args, uid=post['user_id']: show_profile_dialog(uid, current_user_id)):
                            draw_user_avatar(avatar_url=post.get('avatar_url'), name=post.get('user_name'), user_id=post.get('user_id'), role=post.get('role'), size_class='w-9 h-9', show_online_badge=True, border_class='border-white/20')
                            ui.label(post.get('user_name')).classes('font-bold text-white text-sm tracking-wide')
                            
                        if is_pinned: ui.badge('📌 運営からのお知らせ', color='amber-600').classes('text-[10px] font-bold px-2 py-0.5 shadow-md mr-2')
                            
                        is_own_post = post['user_id'] == current_user_id
                        with ui.button(icon='more_horiz').props('flat round color=white size=sm').classes('opacity-60 hover:opacity-100 ml-auto'):
                            with ui.menu().classes('bg-white rounded-xl overflow-hidden').style('background-color: white !important;'):
                                if is_su: 
                                    ui.menu_item('ピン留め切替', on_click=lambda e, p=post: (toggle_pin_status(p['id'], p.get('is_pinned', False)), ui.notify('ピン留め状態を変更しました', position='top'), posts_list.refresh())).style('color: #1e293b !important; font-weight: bold;')
                                if is_own_post or is_su:
                                    ui.menu_item('編集する', on_click=lambda e, p=post: open_post_wizard(p)).style('color: #1e293b !important; font-weight: bold;')
                                    ui.menu_item('削除する', on_click=lambda e, p=post: confirm_delete(p['id'])).style('color: #ef4444 !important; font-weight: bold;')
                                if not is_own_post:
                                    ui.menu_item('非表示にする', on_click=lambda e, p=post: handle_mute_user(p['user_id'], p.get('user_name'))).style('color: #1e293b !important; font-weight: bold;')
                                    if not is_su: 
                                        ui.menu_item('通報する', on_click=lambda e, p=post: open_report_dialog(p)).style('color: #1e293b !important; font-weight: bold;')

                    # ② メインビジュアル
                    if post.get('image_url'):
                        serialized_images_str = post['image_url']
                        post_images_list = [u.strip() for u in serialized_images_str.split(',') if u.strip()]
                        if post_images_list:
                            with ui.column().classes('w-full gap-0 border-b border-white/5'):
                                carousel = ui.carousel(value='0', animated=True, arrows=True, navigation=False).classes('w-full bg-black').props('swipeable control-color="white" transition-prev="slide-right" transition-next="slide-left"').style('height: 500px;')
                                with carousel:
                                    for i, url in enumerate(post_images_list):
                                        with ui.carousel_slide(name=str(i)).classes('p-0 m-0 flex justify-center items-center bg-black'):
                                            lightbox_image(url, thumbnail_classes='w-full h-full object-contain')
                                dots = []
                                with ui.row().classes('w-full justify-center items-center pt-3 pb-1 gap-2 bg-transparent'):
                                    for i in range(len(post_images_list)):
                                        def create_dot(idx, target_carousel=carousel):
                                            d = ui.element('div').classes('rounded-full cursor-pointer transition-all shadow-sm')
                                            d.on('click', lambda _, c=target_carousel, i=idx: c.set_value(str(i)))
                                            return d
                                        dots.append(create_dot(i))
                                def sync_dots(e=None, target_carousel=carousel, target_dots=dots):
                                    val = target_carousel.value
                                    for j, d in enumerate(target_dots):
                                        if str(j) == val: d.classes(replace='rounded-full cursor-pointer transition-all bg-cyan-500').style(replace='width: 8px; height: 8px;')
                                        else: d.classes(replace='rounded-full cursor-pointer transition-all bg-gray-400 dark:bg-white/30 hover:bg-gray-500').style(replace='width: 6px; height: 6px;')
                                carousel.on_value_change(sync_dots)
                                sync_dots() 

                    # 🌟 アクションバーより先に「キャプション（本文）」を表示
                    replies_count = len(post.get('replies', []))
                    
                    with ui.column().classes('w-full px-4 pt-3 pb-1 gap-1'):
                        if post.get('title'): ui.label(post['title']).classes('font-bold text-white text-[14px]')
                        if post.get('content'):
                            with ui.element('div').classes('text-[14px] leading-relaxed break-words whitespace-pre-wrap'):
                                ui.label(post['content']).classes('text-slate-200 inline')
                        if replies_count > 0: ui.label(f'>>コメントをすべて見る').classes('text-cyan-400 text-[13px] mt-1 cursor-pointer hover:text-cyan-300 transition').on('click', lambda e, p=post: open_post_detail_dialog(p, current_user_id, current_user_name, avatar_url, is_su, dialog_container))

                    # 🌟 そのあとに「アクションバー（いいね・コメントなど）」を表示
                    with ui.row().classes('w-full px-4 pt-2 pb-3 items-center gap-5'):
                        is_own = post['user_id'] == current_user_id
                        is_liked = get_user_like_status(post['id'], current_user_id)
                        likes_count = post.get('likes_count', 0)
                        
                        with ui.row().classes('items-center gap-1'):
                            btn_like = ui.button('❤️' if is_liked else '🤍').props('flat round').classes('text-xl p-1 min-h-0 min-w-0 transition-transform hover:scale-110')
                            if is_own: btn_like.disable()
                            
                            lbl_like = ui.label(str(likes_count)).classes(f'text-sm font-bold {"text-pink-400" if is_liked else "text-white"}')
                            ui_elements['likes'][str(post['id'])] = lbl_like 
                            
                            def handle_toggle(p_data, btn_ref, lbl_ref):
                                pid = p_data['id']
                                new_state = toggle_like(pid, current_user_id)
                                p_data['likes_count'] = (p_data.get('likes_count', 0) + 1) if new_state else max(0, p_data.get('likes_count', 0) - 1)
                                
                                btn_ref.text = '❤️' if new_state else '🤍'
                                btn_ref.update()
                                
                                lbl_ref.set_text(str(p_data['likes_count']))
                                lbl_ref.classes(replace=f'text-sm font-bold {"text-pink-400" if new_state else "text-white"}')
                                
                                if new_state:
                                    ui.run_javascript(f'''
                                        const btn = document.getElementById("c{btn_ref.id}");
                                        if (btn) {{
                                            const rect = btn.getBoundingClientRect();
                                            const heart = document.createElement('div');
                                            heart.innerHTML = '❤️';
                                            heart.style.position = 'fixed';
                                            heart.style.left = (rect.left + rect.width / 2 - 12) + 'px';
                                            heart.style.top = (rect.top + rect.height / 2 - 12) + 'px';
                                            heart.style.fontSize = '24px';
                                            heart.style.pointerEvents = 'none';
                                            heart.style.zIndex = '9999';
                                            heart.style.transition = 'all 0.8s ease-out';
                                            document.body.appendChild(heart);
                                            setTimeout(() => {{
                                                heart.style.transform = 'translateY(-60px) scale(1.5) rotate(15deg)';
                                                heart.style.opacity = '0';
                                            }}, 10);
                                            setTimeout(() => heart.remove(), 800);
                                        }}
                                    ''')
                                
                                if new_state and p_data['user_id'] != current_user_id:
                                    try:
                                        from config.supabase_config import get_supabase
                                        sb = get_supabase()
                                        content_text = p_data.get('content') or p_data.get('title') or "画像"
                                        snippet = content_text[:20] + '...' if len(content_text) > 20 else content_text
                                        sb.table("notifications").insert({
                                            "user_id": p_data['user_id'],
                                            "content": f"{current_user_name} さんがあなたの投稿にいいねしました: 「{snippet}」|[post_id:{pid}]",
                                            "is_read": False,
                                            "type": "like"
                                        }).execute()
                                    except Exception as e:
                                        pass
                                        
                            if not is_own: 
                                btn_like.on('click', lambda e, p=post, b=btn_like, l=lbl_like: handle_toggle(p, b, l))

                        with ui.row().classes('items-center gap-1 cursor-pointer group').on('click', lambda e, p=post: open_post_detail_dialog(p, current_user_id, current_user_name, avatar_url, is_su, dialog_container)):
                            ui.button('💬').props('flat round').classes('text-xl p-1 min-h-0 min-w-0 transition-transform group-hover:scale-110 pointer-events-none')
                            
                            lbl_reply = ui.label(str(replies_count)).classes('text-white text-sm font-bold pointer-events-none')
                            ui_elements['replies'][str(post['id'])] = lbl_reply 
                        
                        with ui.row().classes('ml-auto items-center gap-2'):
                            if post.get('allow_chat'):
                                if post.get('chat_room_id'): 
                                    participants = post.get('participants', [])
                                    if participants:
                                        display_avatars = participants[:10]
                                        has_more = len(participants) > 10
                                        
                                        with ui.row().classes('flex overflow-hidden items-center mr-1')\
                                                .style('gap: 0;')\
                                                .props(f'id="participants-container-{post["id"]}"'):
                                            
                                            for idx, avatar in enumerate(display_avatars):
                                                margin_class = '' if idx == 0 else '-ml-3.5'
                                                ui.element('img').props(f'src="{avatar}"')\
                                                    .classes(f'inline-block h-6 w-6 rounded-full border-2 border-white/20 dark:border-white/10 object-cover {margin_class}')\
                                                    .style(f'z-index: {20 - idx};')
                                                    
                                            if has_more:
                                                with ui.element('div').classes('flex items-center justify-center h-6 w-6 rounded-full border-2 border-white/20 dark:border-white/10 bg-slate-800 text-xs text-white/50 font-bold shrink-0 -ml-3.5')\
                                                        .style(f'z-index: {20 - len(display_avatars)};'):
                                                    ui.label('⋯').classes('leading-none mt-[-2px]')
                                    
                                    ui.button('🚪', on_click=lambda e, p=post: change_menu_cb('chat', p['chat_room_id'])).props('flat round').classes('text-xl p-1 min-h-0 min-w-0').tooltip('連携チャットへ')
                                else: 
                                    ui.button(icon='img:/static/edited-image.png', on_click=lambda e, p=post: confirm_create_chat(p)).props('flat round').classes('w-6 h-6 p-1 min-h-0 min-w-0 transition-transform hover:scale-110').tooltip('チャットルーム作成')
                            
                            elif (post.get('title') or '').startswith('【新規イベント】'): 
                                def jump_to_event(content_text):
                                    if content_text:
                                        m = re.search(r'(20\d{2})\s*[/年-]\s*([0-1]?\d)', content_text)
                                        if m:
                                            try:
                                                if ui.context.client and ui.context.client.has_socket_connection:
                                                    app.storage.user['target_calendar_year'] = int(m.group(1))
                                                    app.storage.user['target_calendar_month'] = int(m.group(2))
                                            except Exception:
                                                pass
                                    change_menu_cb('event')
                                ui.button('📅', on_click=lambda e, c=post.get('content'): jump_to_event(c)).props('flat round').classes('text-xl p-1 min-h-0 min-w-0 animate-pulse').tooltip('イベントへ')

                    ui.label(post.get('time_str')).classes('px-4 pb-4 text-[10px] text-white/40 uppercase tracking-widest')
        posts_list()


        # ==========================================
        # 🔄 リアルタイム更新＆ちらつき防止差分検知 (100%安全ガード版)
        # ==========================================
        timeline_state = {'last_sig_db': None, 'last_sig_avatars': {}}
        
        def check_updates():
            try:
                client = ui.context.client
                if not client or not client.has_socket_connection: return
            except Exception: return

            try:
                current_posts = fetch_timeline_posts()
                
                sig_db = "".join([f"{p['id']}_{p.get('is_pinned',False)}" for p in current_posts])
                
                for p in current_posts:
                    p_id = str(p['id'])
                    
                    avatars = p.get('participants', [])
                    avatars_sig = "-".join(avatars)
                    if p_id in timeline_state['last_sig_avatars']:
                        if timeline_state['last_sig_avatars'][p_id] != avatars_sig:
                            timeline_state['last_sig_avatars'][p_id] = avatars_sig
                            display_avatars = avatars[:10]
                            has_more = len(avatars) > 10
                            
                            html_list = []
                            for idx, av in enumerate(display_avatars):
                                margin_class = "" if idx == 0 else "-ml-3.5"
                                html_list.append(f'<img src="{av}" class="inline-block h-6 w-6 rounded-full border-2 border-white/20 dark:border-white/10 object-cover {margin_class}" style="z-index: {20 - idx};" />')
                                
                            if has_more:
                                idx_more = len(display_avatars)
                                html_list.append(f'<div class="flex items-center justify-center h-6 w-6 rounded-full border-2 border-white/20 dark:border-white/10 bg-slate-800 text-xs text-white/50 font-bold shrink-0 -ml-3.5" style="z-index: {20 - idx_more};"><span class="leading-none mt-[-2px]">⋯</span></div>')
                                
                            html_content = "".join(html_list)
                            ui.run_javascript(f'var el = document.getElementById("participants-container-{p_id}"); if (el) el.innerHTML = `{html_content}`;')
                    else:
                        timeline_state['last_sig_avatars'][p_id] = avatars_sig

                    if p_id in ui_elements['likes']:
                        new_likes = str(p.get('likes_count', 0))
                        if ui_elements['likes'][p_id].text != new_likes:
                            ui_elements['likes'][p_id].set_text(new_likes)
                            
                    if p_id in ui_elements['replies']:
                        new_replies = str(len(p.get('replies', [])))
                        if ui_elements['replies'][p_id].text != new_replies:
                            ui_elements['replies'][p_id].set_text(new_replies)

                if timeline_state['last_sig_db'] is not None and timeline_state['last_sig_db'] != sig_db:
                    posts_list.refresh()
                    
                timeline_state['last_sig_db'] = sig_db
                
            except Exception as e:
                pass
                
        update_timer = ui.timer(3.0, check_updates)
        original_delete = main_container.delete
        def safe_delete():
            update_timer.deactivate()
            original_delete()
        main_container.delete = safe_delete