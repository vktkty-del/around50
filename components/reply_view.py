# components/reply_view.py
from nicegui import ui
import uuid
import re
import html
from datetime import datetime, timezone, timedelta
from config.supabase_config import get_supabase
from database.timeline_db import add_reply_and_return as create_reply, delete_post, update_post_content, get_user_like_status, toggle_like
from utils.validator import check_ng_words
from components.avatar import draw_user_avatar
from components.comp_profile import show_profile_dialog

def get_time_str(raw_time):
    """時間表示を absolute (YYYY/MM/DD HH:MM) に変換するヘルパー"""
    time_str = ""
    if raw_time:
        try:
            dt = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
            jst_dt = dt.astimezone(timezone(timedelta(hours=9)))
            time_str = jst_dt.strftime('%Y/%m/%d %H:%M')
        except: pass
    return time_str

def fetch_replies_for_post(post_id: str):
    """特定の投稿に対するコメント（返信）を、削除済み・審査中を除外してDBから直接再取得する"""
    sb = get_supabase()
    res = sb.table("timeline_posts") \
        .select("*, profiles(name, avatar_url, role)") \
        .eq("parent_id", post_id) \
        .is_("deleted_at", "null") \
        .or_("status.eq.approved,status.is.null") \
        .order("created_at", desc=False) \
        .execute()
    
    replies = []
    if res.data:
        for row in res.data:
            profile = row.get("profiles") or {}
            replies.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "content": row["content"],
                "time_str": get_time_str(row.get("created_at")),
                "likes_count": row.get("likes_count") or 0, # 🌟 これを追加
                "user_name": profile.get("name", "名無し"),
                "avatar_url": profile.get("avatar_url"),
                "role": profile.get("role")
            })
    return replies

def open_edit_reply_dialog(reply: dict, post: dict, comments_container_ref, dialog_container):
    """コメントを編集するための専用ダイアログを開く"""
    with dialog_container:
        with ui.dialog() as edit_reply_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-[350px] max-w-full p-5 shadow-2xl'):
            with ui.row().classes('w-full justify-between items-center mb-2'):
                ui.label('コメントを編集').classes('text-base font-bold text-white')
                ui.button(icon='close', on_click=edit_reply_dialog.close).props('flat round size=sm color=white')
            
            edit_input = ui.textarea(value=reply['content']).classes('w-full bg-black/30 border border-white/10 rounded-lg p-2').props('borderless input-class="text-white text-sm" autogrow rows="3"')
            
            def handle_save_reply():
                new_text = edit_input.value or ""
                if not new_text.strip():
                    ui.notify('本文を入力してください', color='warning', position='top')
                    return
                if new_text == reply['content']:
                    edit_reply_dialog.close()
                    return
                
                ng_result = check_ng_words(new_text)
                if ng_result['is_ng']:
                    ui.notify('不適切な表現が含まれています', color='negative', position='top')
                    return
                
                update_post_content(reply['id'], new_text, status='approved')
                reply['content'] = new_text
                ui.notify('コメントを編集しました', color='positive', position='top')
                edit_reply_dialog.close()
                comments_container_ref.refresh()
                
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('保存する', on_click=handle_save_reply).classes('bg-cyan-600 hover:bg-cyan-500 text-white font-bold px-6 rounded-full')
    edit_reply_dialog.open()


def open_post_detail_dialog(post: dict, current_user_id: str, current_user_name: str, avatar_url: str, is_su: bool, dialog_container):
    """
    タイムライン投稿の詳細（オリジナル投稿 ＋ コメント一覧 ＋ インラインコメント入力）ダイアログを開く
    """
    from components.feed_item import render_image_grid_ui

    try:
        post['replies'] = fetch_replies_for_post(post['id'])
    except Exception as e:
        print(f"💡 [詳細リロード] 返信の取得に失敗しました: {e}")

    with dialog_container:
        card_classes = (
            'w-full max-w-xl max-h-[80vh] '
            'hibi-panel-glass rounded-t-3xl md:rounded-3xl p-0 shadow-2xl '
            'flex flex-col flex-nowrap border border-white/10 overflow-hidden'
        )
        with ui.dialog() as detail_dialog, ui.card().classes(card_classes):
            
            # --- ヘッダー ---
            with ui.row().classes('w-full justify-between items-center px-5 py-3 border-b border-white/10 shrink-0 bg-white/5'):
                ui.label(f"{post.get('user_name')} さんの投稿").classes('text-sm font-bold text-white')
                ui.button(icon='close', on_click=detail_dialog.close).props('flat round size=sm color=white')

            # --- スクロール領域（投稿本文 ＋ コメント一覧） ---
            with ui.column().classes('w-full flex-grow min-h-0 overflow-y-auto clean-scroll p-0 m-0 gap-0').props('id="detail_scroll_area"'):
                
                # オリジナル投稿部分
                with ui.column().classes('w-full p-5 gap-3 shrink-0'):
                    with ui.row().classes('items-center gap-3 cursor-pointer').on('click', lambda *args, uid=post['user_id']: show_profile_dialog(uid, current_user_id)):
                        draw_user_avatar(
                            avatar_url=post.get('avatar_url'),
                            name=post.get('user_name'),
                            user_id=post.get('user_id'),
                            role=post.get('role'),
                            size_class='w-11 h-11',
                            show_online_badge=True,
                            border_class='border-white/20'
                        )
                        with ui.column().classes('gap-0'):
                            ui.label(post.get('user_name')).classes('font-bold text-white text-sm')
                            ui.label(post.get('time_str')).classes('text-[11px] text-white/40')

                    if post.get('title'):
                        ui.label(post['title']).classes('font-bold text-white text-[15px] mt-2')
                    if post.get('content'):
                        ui.label(post['content']).classes('text-slate-200 text-[14px] whitespace-pre-wrap break-words mt-1')

                    if post.get('image_url'):
                        serialized_images_str = post['image_url']
                        post_images_list = [u.strip() for u in serialized_images_str.split(',') if u.strip()]
                        if post_images_list:
                            with ui.row().classes('w-full justify-center mt-3 bg-black/20 rounded-lg p-2 border border-white/10'):
                                render_image_grid_ui(post_images_list, is_preview=False)

                # コメント一覧部分
                @ui.refreshable
                def comments_container():
                    has_replies = bool(post.get('replies'))
                    
                    if has_replies:
                        ui.separator().classes('w-full bg-white/10 shrink-0')
                        with ui.column().classes('w-full bg-black/20 flex-grow p-5 gap-5'):
                            for reply in post['replies']:
                                with ui.row().classes('w-full gap-3 items-start no-wrap'):
                                    draw_user_avatar(
                                        avatar_url=reply.get('avatar_url'),
                                        name=reply.get('user_name'),
                                        user_id=reply.get('user_id'),
                                        role=reply.get('role'),
                                        size_class='w-8 h-8 mt-1 cursor-pointer',
                                        show_online_badge=True,
                                        border_class='border-white/20'
                                    ).on('click', lambda *args, uid=reply['user_id']: show_profile_dialog(uid, current_user_id))
                                    
                                    with ui.column().classes('gap-0 flex-grow'):
                                        with ui.row().classes('items-center gap-2 w-full'):
                                            ui.label(reply.get('user_name')).classes('font-bold text-white text-[12px]')
                                            ui.label(reply.get('time_str')).classes('text-[10px] text-white/40')
                                            
                                            is_rep_own = reply['user_id'] == current_user_id
                                            with ui.row().classes('ml-auto gap-0 items-center'):
                                                # ====== 🌟 ここから【いいねボタン】追加 ======
                                                rep_is_liked = get_user_like_status(reply['id'], current_user_id)
                                                rep_likes_count = reply.get('likes_count', 0)
                                                
                                                with ui.row().classes('items-center gap-0 mr-3'):
                                                    btn_rep_like = ui.button(icon='favorite' if rep_is_liked else 'favorite_border') \
                                                        .props(f'flat round size=xs color={"pink-400" if rep_is_liked else "white/60"}') \
                                                        .classes('p-1 min-h-0 min-w-0 transition-transform hover:scale-110')
                                                    
                                                    lbl_rep_like = ui.label(str(rep_likes_count) if rep_likes_count > 0 else "") \
                                                        .classes(f'text-[10px] font-bold {"text-pink-400" if rep_is_liked else "text-white/60"}')
                                                    
                                                    if is_rep_own:
                                                        btn_rep_like.disable() # 自分のコメントにはいいね不可
                                                    else:
                                                        def handle_rep_toggle(e, r=reply, btn=btn_rep_like, lbl=lbl_rep_like):
                                                            new_state = toggle_like(r['id'], current_user_id)
                                                            r['likes_count'] = (r.get('likes_count', 0) + 1) if new_state else max(0, r.get('likes_count', 0) - 1)
                                                            btn.set_icon('favorite' if new_state else 'favorite_border')
                                                            btn.props(f'flat round size=xs color={"pink-400" if new_state else "white/60"}')
                                                            lbl.set_text(str(r['likes_count']) if r['likes_count'] > 0 else "")
                                                            lbl.classes(replace=f'text-[10px] font-bold {"text-pink-400" if new_state else "text-white/60"}')
                                                            
                                                            # ====== 🌟 ここから【コメントいいね通知】追加 ======
                                                            if new_state and r['user_id'] != current_user_id:
                                                                try:
                                                                    from config.supabase_config import get_supabase
                                                                    sb = get_supabase()
                                                                    snippet = r.get('content', '')[:20] + '...' if len(r.get('content', '')) > 20 else r.get('content', '')
                                                                    
                                                                    sb.table("notifications").insert({
                                                                        "user_id": r['user_id'],
                                                                        "content": f"{current_user_name} さんがあなたのコメントにいいねしました: 「{snippet}」|[post_id:{post['id']}]",
                                                                        "is_read": False,
                                                                        "type": "like"
                                                                    }).execute()
                                                                except Exception as e:
                                                                    print(f"💡 [コメントいいね通知エラー] {e}")
                                                            # ====== 🌟 ここまで ======
                                                            
                                                        btn_rep_like.on('click', handle_rep_toggle)
                                                ui.button(icon='reply', on_click=lambda e, r=reply: reply_input.set_value(f"@{r.get('user_name')} ")) \
                                                    .props('flat round size=xs color=white/60').classes('p-1 min-h-0 min-w-0 mr-1').tooltip('この人に返信')
                                                
                                                if is_rep_own or is_su:
                                                    ui.button(icon='edit', on_click=lambda e, r=reply: open_edit_reply_dialog(r, post, comments_container, dialog_container)) \
                                                        .props('flat round size=xs color=cyan-400').classes('p-1 min-h-0 min-w-0 mr-1').tooltip('編集')
                                                    
                                                    def confirm_delete_reply(r_id=reply['id']):
                                                        with dialog_container:
                                                            with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-[280px] p-5 shadow-2xl'):
                                                                ui.label('コメントの削除').classes('text-base font-bold text-white mb-1')
                                                                ui.label('このコメントを削除しますか？').classes('text-xs text-white/70 mb-4')
                                                                
                                                                with ui.row().classes('w-full justify-end gap-2'):
                                                                    ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                                                                    
                                                                    def proceed_delete():
                                                                        if not str(r_id).startswith('temp_'):
                                                                            delete_post(r_id)
                                                                        if 'replies' in post and post['replies']:
                                                                            post['replies'] = [rep for rep in post['replies'] if rep['id'] != r_id]
                                                                        comments_container.refresh()
                                                                        ui.notify('コメントを削除しました', color='negative', position='top')
                                                                        confirm_dialog.close()
                                                                        
                                                                    ui.button('削除', on_click=proceed_delete).classes('bg-red-600 hover:bg-red-500 text-white font-bold rounded-full px-4')
                                                        confirm_dialog.open()
                                                        
                                                    ui.button(icon='delete', on_click=lambda e, r_id=reply['id']: confirm_delete_reply(r_id)) \
                                                        .props('flat round size=xs color=red-400').classes('p-1 min-h-0 min-w-0').tooltip('削除')
                                        # ====== 🌟 ここから【メンションのシアン色化】変更 ======
                                        # 元の ui.label(reply['content']) を消して、以下に差し替え
                                        escaped_text = html.escape(reply.get('content', ''))
                                        formatted_html = re.sub(
                                            r'(@[a-zA-Z0-9_\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+)', 
                                            r'<span class="text-cyan-400 font-bold">\1</span>', 
                                            escaped_text
                                        )
                                        ui.html(formatted_html).classes('text-slate-300 text-[13px] leading-relaxed mt-1 whitespace-pre-wrap break-words')
                
                comments_container()

            # --- 使いやすいフッター入力欄（インライン） ---
            def submit_reply():
                text = reply_input.value or ""
                if not text.strip():
                    return
                
                ng_result = check_ng_words(text)
                if ng_result['is_ng']:
                    ui.notify('不適切な表現が含まれています', color='negative', position='top')
                    return
                    
                try:
                    new_reply_record = create_reply(post['id'], current_user_id, text)
                    new_id = new_reply_record.get('id') if new_reply_record else f"temp_{uuid.uuid4()}"
                    
                    mentions = re.findall(r'@([a-zA-Z0-9_\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+)', text)
                    sb = get_supabase() 
                    notified_uids = set()
                    if mentions:
                        sb = get_supabase()
                        for username in set(mentions):
                            prof_res = sb.table("profiles").select("id").eq("name", username).execute()
                            if prof_res.data:
                                target_uid = prof_res.data[0]['id']
                                if target_uid != current_user_id:
                                    snippet = text.replace(f"@{username}", "").strip()
                                    snippet_truncated = snippet[:30] + '...' if len(snippet) > 30 else snippet
                                    
                                    sb.table("notifications").insert({
                                        "user_id": target_uid,
                                        "content": f"{current_user_name} さんがあなた宛てにコメントしました: 「{snippet_truncated}」|[post_id:{post['id']}]|[reply_id:{new_id}]",
                                        "is_read": False,
                                        "type": "comment"
                                    }).execute()
                                    notified_uids.add(target_uid)

                    # ====== 🌟 ここから追加 🌟 ======
                    # 投稿のオーナー（投稿者）への通知処理
                    post_owner_id = post.get('user_id')
                    
                    # 条件: 投稿者が存在し、自分自身への返信ではなく、かつメンションで既に通知されていない場合
                    if post_owner_id and (post_owner_id != current_user_id) and (post_owner_id not in notified_uids):
                        snippet_truncated = text[:30] + '...' if len(text) > 30 else text
                        
                        sb.table("notifications").insert({
                            "user_id": post_owner_id,
                            "content": f"{current_user_name} さんがあなたの投稿にコメントしました: 「{snippet_truncated}」|[post_id:{post['id']}]|[reply_id:{new_id}]",
                            "is_read": False,
                            "type": "comment"
                        }).execute()
                    # ====== 🌟 ここまで追加 🌟 ======
                    if 'replies' not in post or post['replies'] is None:
                        post['replies'] = []
                        
                    post['replies'].append({
                        'id': new_id,
                        'user_id': current_user_id,
                        'user_name': current_user_name,
                        'avatar_url': avatar_url,
                        'role': 'superuser' if is_su else 'member',
                        'content': text,
                        'time_str': 'たった今',
                        'likes_count': 0 # 🌟 これを追加
                    })
                    
                    reply_input.set_value('')
                    comments_container.refresh()
                    
                    ui.notify('コメントを送信しました！', color='positive', position='top')
                    ui.run_javascript("setTimeout(() => { const el = document.getElementById('detail_scroll_area'); if(el) el.scrollTop = el.scrollHeight; }, 100);")
                except Exception as e:
                    ui.notify(f'エラーが発生しました: {e}', color='negative', position='top')

            # ★ 修正箇所: 全体の上下パディングを py-2 に統一して高さを圧縮
            with ui.row().classes('w-full px-3 py-2 border-t border-white/10 shrink-0 bg-slate-950 items-end gap-2 no-wrap relative z-10'):
                draw_user_avatar(
                    avatar_url=avatar_url,
                    name=current_user_name,
                    user_id=current_user_id,
                    role='superuser' if is_su else 'member',
                    size_class='w-8 h-8 shrink-0 mb-0.5',
                    show_online_badge=False,
                    border_class='border-white/20'
                )
                
                # ★ 最重要修正箇所: props に `dense` を追加し、真の1行高さを実現
                reply_input = ui.textarea(placeholder=f"{post.get('user_name')} さんにコメント...")\
                    .classes('flex-grow bg-white/10 border border-white/10 rounded-2xl px-3 w-0 min-w-0 transition-all focus-within:border-cyan-500/50 focus-within:bg-white/20')\
                    .props('borderless dark dense input-class="text-white text-[14px] py-1" autogrow rows="1" max-rows="5"')
                
                ui.button(icon='send', on_click=submit_reply)\
                    .props('flat round size=sm color=cyan-400')\
                    .classes('shrink-0 mb-0 hover:bg-cyan-500/20 transition-all')\
                    .tooltip('送信')

        detail_dialog.open()
        
        if post.get('replies'):
            ui.run_javascript("setTimeout(() => { const el = document.getElementById('detail_scroll_area'); if(el) el.scrollTop = el.scrollHeight; }, 300);")