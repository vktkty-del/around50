# components/review_ui.py
from nicegui import ui
from database.event_db import fetch_event_reviews, submit_event_review, supabase
from components.flat_dialogs import get_anonymous_avatar

@ui.refreshable
def draw_inline_review_page(client_st, current_user_id: str, refresh_all_cb):
    """
    イベントの評価（振り返り）をインラインで表示・投稿するUIコンポーネント
    """
    review_ev = getattr(client_st, 'review_event', None)
    if not review_ev:
        return
        
    event_id = review_ev.get('id')
    event_title = review_ev.get('title', 'イベント')
    participant_ids = review_ev.get('participant_ids') or []
    
    # ユーザー情報の取得（投稿権限・SU権限の確認）
    try:
        res_prof = supabase.table("profiles").select("role").eq("id", current_user_id).single().execute()
        my_role = res_prof.data.get('role', 'member') if res_prof.data else 'member'
    except Exception:
        my_role = 'member'
        
    is_su_user = str(my_role).lower() in ['superuser', 'admin', 'owner', 'master', 'submaster']
    is_p_user = current_user_id in participant_ids
    can_post = is_p_user or is_su_user
    
    with ui.column().classes('w-full max-w-2xl mx-auto p-4 gap-4 text-slate-800 dark:text-white'):
        # ヘッダー領域
        with ui.row().classes('w-full items-center justify-between no-wrap border-b border-white/10 pb-3'):
            with ui.row().classes('items-center gap-2 cursor-pointer text-slate-500 dark:text-white/60 hover:text-indigo-400') as back_btn:
                back_btn.on('click', lambda: (setattr(client_st, 'review_event', None), refresh_all_cb()))
                ui.icon('arrow_back', size='sm')
                ui.label('カレンダーに戻る').classes('text-xs font-bold')
            ui.badge(review_ev.get('genre', '飲み会'), color='indigo-500').classes('text-[10px] px-2 py-0.5 shrink-0')
            
        ui.label(f"みんなの評価: {event_title}").classes('text-xl font-black text-slate-800 dark:text-white mt-1')
        
        reviews = fetch_event_reviews(event_id)
        has_already_posted = any(str(r.get('user_id')) == str(current_user_id) for r in reviews)
        
        # 投稿フォーム（未投稿かつ参加資格ありの場合に表示）
        if can_post and not has_already_posted:
            with ui.column().classes('w-full bg-slate-100/90 dark:bg-white/5 p-5 rounded-2xl border border-teal-500/20 gap-4 shadow-lg'):
                ui.label('✨ このイベントを振り返る').classes('text-xs font-bold text-teal-600 dark:text-teal-400')
                
                # 解決アプローチ: 干渉を受けるui.iconを排除し、ui.labelの★/☆で構築
                state = {'rating': 5}
                star_icons = []
                
                def handle_star_click(clicked_val):
                    state['rating'] = clicked_val
                    for i, label in enumerate(star_icons, 1):
                        if i <= clicked_val:
                            # 選択された星以下は「★」を黄色で表示
                            label.text = '★'
                            label.style('color: #fbbf24')
                        else:
                            # 選択より上の星は「☆」をグレーで表示
                            label.text = '☆'
                            label.style('color: #cbd5e1')
                        label.update()

                with ui.row().classes('items-center gap-1'):
                    ui.label('満足度:').classes('text-xs text-slate-600 dark:text-white/80 font-bold mr-1')
                    for i in range(1, 6):
                        # ui.iconの代わりにui.labelを配置。初期状態は5つすべて黄色の「★」
                        label = ui.label('★').classes('cursor-pointer hover:scale-110 transition-all').style('font-size: 28px; color: #fbbf24; line-height: 1; font-family: sans-serif;')
                        label.on('click', lambda e, i=i: handle_star_click(i))
                        star_icons.append(label)
                
                # 理由タグ
                ui.label('当てはまる理由を選択してください（複数選択可）:').classes('text-xs font-bold text-slate-500 dark:text-white/50')
                
                ui.label('👍 良かったこと').classes('text-[11px] font-bold text-teal-600 dark:text-teal-400 mt-1')
                pos_tags = ['会話が盛り上がった', '食べ物飲み物が充実してた', 'お店の雰囲気が良かった']
                pos_checkboxes = {}
                with ui.row().classes('gap-2 flex-wrap'):
                    for t in pos_tags:
                        pos_checkboxes[t] = ui.checkbox(t).classes('text-xs')

                ui.label('🤔 悪かったこと・反省点').classes('text-[11px] font-bold text-rose-500 mt-1')
                neg_tags = ['落ち着けなかった', '飲み物食べ物がイマイチ', '会話に入れなかった']
                neg_checkboxes = {}
                with ui.row().classes('gap-2 flex-wrap'):
                    for t in neg_tags:
                        neg_checkboxes[t] = ui.checkbox(t).classes('text-xs')
                
                # 自由記入欄の表示トグル
                other_chk = ui.checkbox('その他 (自由記入を開く)').classes('text-xs text-slate-500 dark:text-white/60 mt-1')
                
                comment_area = ui.textarea(label='コメント・感想').classes('w-full text-xs').props('color="teal" outlined rows=3 autogrow')
                comment_area.bind_visibility_from(other_chk, 'value')
                
                # 匿名設定 & 送信ボタン
                with ui.row().classes('w-full justify-between items-center mt-2 no-wrap gap-2'):
                    anon_chk = ui.checkbox('匿名で投稿').classes('text-xs')
                    
                    async def handle_submit():
                        selected_tags = []
                        for t, chk in pos_checkboxes.items():
                            if chk.value: selected_tags.append(t)
                        for t, chk in neg_checkboxes.items():
                            if chk.value: selected_tags.append(t)
                                
                        comment_text = comment_area.value if other_chk.value else ""
                        rating_val = state['rating']
                        
                        res = submit_event_review(
                            event_id=event_id,
                            user_id=current_user_id,
                            rating=rating_val,
                            tags=selected_tags,
                            comment=comment_text,
                            is_anonymous=anon_chk.value
                        )
                        if res:
                            ui.notify('評価を投稿しました！スコア10ptを獲得しました。', type='positive', position='top')
                            refresh_all_cb()
                        else:
                            ui.notify('投稿に失敗しました。', type='negative', position='top')
                            
                    ui.button('送信', on_click=handle_submit).classes('bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl shadow-md')

        # --- 評価リストの一覧表示 ---
        ui.label(f"評価一覧 ({len(reviews)}件)").classes('text-sm font-bold text-slate-500 dark:text-white/60 mt-2')
        
        if not reviews:
            with ui.column().classes('w-full items-center justify-center p-8 bg-slate-100 dark:bg-white/5 rounded-2xl border border-dashed border-slate-300 dark:border-white/5'):
                ui.icon('rate_review', size='32px').classes('opacity-30')
                ui.label('まだ評価はありません。').classes('text-xs text-slate-400 dark:text-white/30 mt-1')
        else:
            with ui.column().classes('w-full gap-3.5'):
                for rev in reviews:
                    is_anon = rev.get('is_anonymous', False)
                    prof = rev.get('profiles') or {}
                    
                    if is_anon:
                        display_name = "参加者さん"
                        avatar_src = get_anonymous_avatar("anonymous-participant")
                    else:
                        display_name = prof.get('name', '名無し')
                        avatar_src = prof.get('avatar_url') or ""
                    
                    with ui.column().classes('w-full bg-slate-100/60 dark:bg-white/5 p-4 rounded-xl border border-slate-200 dark:border-white/5 gap-2 shadow-sm'):
                        with ui.row().classes('w-full justify-between items-center no-wrap'):
                            with ui.row().classes('items-center gap-2 overflow-hidden'):
                                if avatar_src:
                                    ui.image(avatar_src).classes('w-5 h-5 rounded-full bg-slate-800 shrink-0 border border-white/10')
                                else:
                                    ui.icon('person', size='20px').classes('text-slate-400')
                                ui.label(display_name).classes('text-xs font-bold text-slate-600 dark:text-white/80 truncate')
                            
                            # リスト側の読み取り専用星（こちらもui.labelを使用して外部CSSの干渉を防ぎます）
                            rev_stars = rev.get('rating', 5)
                            with ui.row().classes('gap-0.5 items-center shrink-0'):
                                for i in range(1, 6):
                                    char = '★' if i <= rev_stars else '☆'
                                    color = '#fbbf24' if i <= rev_stars else '#cbd5e1'
                                    ui.label(char).style(f'color: {color}; font-size: 16px; font-family: sans-serif;')
                        
                        tags_list = rev.get('tags') or []
                        if tags_list:
                            with ui.row().classes('gap-1 flex-wrap'):
                                for t in tags_list:
                                    is_neg = t in ['落ち着けなかった', '飲み物食べ物がイマイチ', '会話に入れなかった']
                                    badge_color = 'rose-500/10 text-rose-400 border border-rose-500/20' if is_neg else 'teal-500/10 text-teal-400 border border-teal-500/20'
                                    ui.label(t).classes(f'text-[9px] px-1.5 py-0.5 rounded {badge_color}')
                                    
                        comment_val = rev.get('comment')
                        if comment_val and comment_val.strip():
                            ui.label(comment_val).classes('text-xs text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-normal mt-1')

                        # ★ 運営からの返信表示（編集・削除機能つき） ＆ 新規投稿フォーム
                        reply_text = rev.get('reply')
                        
                        # ★ 不具合修正: "null" や "None" などの無効な文字列を徹底的にガード
                        if reply_text and str(reply_text).strip().lower() not in ['null', 'none', '']:
                            with ui.row().classes('w-full bg-indigo-500/10 border border-indigo-500/20 p-3 rounded-xl mt-2 gap-2 items-start no-wrap'):
                                ui.icon('reply', size='16px').classes('text-indigo-400 mt-0.5 shrink-0')
                                
                                # 通常の表示モード
                                with ui.column().classes('gap-1 flex-grow') as display_col:
                                    with ui.row().classes('w-full justify-between items-start no-wrap'):
                                        ui.label('運営からの返信').classes('text-[10px] font-bold text-indigo-400')
                                        if is_su_user:
                                            with ui.row().classes('gap-1 shrink-0'):
                                                edit_btn = ui.button(icon='edit').props('flat round size=xs color="indigo"').classes('p-1 min-h-0').tooltip('返信を編集')
                                                delete_btn = ui.button(icon='delete').props('flat round size=xs color="red"').classes('p-1 min-h-0').tooltip('返信を削除')
                                                
                                    ui.label(reply_text).classes('text-xs text-slate-700 dark:text-indigo-100 whitespace-pre-wrap leading-normal')
                                
                                # 編集モード (初期は隠す)
                                if is_su_user:
                                    with ui.column().classes('w-full gap-2') as edit_col:
                                        edit_col.set_visibility(False)
                                        ui.label('運営からの返信を編集').classes('text-[10px] font-bold text-indigo-400')
                                        edit_input = ui.textarea(value=reply_text).classes('w-full text-xs').props('outlined color="indigo" rows=2 autogrow')
                                        
                                        with ui.row().classes('w-full justify-end gap-2 mt-1'):
                                            cancel_edit_btn = ui.button('キャンセル').props('flat size=sm color="grey"').classes('px-2 py-0.5')
                                            
                                            async def do_update_reply(r_id=rev['id'], inp=edit_input):
                                                val = inp.value
                                                if not val:
                                                    ui.notify('返信を入力するか、削除ボタンを使用してください', type='warning', position='top')
                                                    return
                                                res = supabase.table("event_reviews").update({"reply": val}).eq("id", r_id).execute()
                                                if res.data:
                                                    ui.notify('返信を更新しました！', type='positive', position='top')
                                                    refresh_all_cb()
                                                else:
                                                    ui.notify('更新に失敗しました。', type='negative', position='top')

                                            save_edit_btn = ui.button('保存', on_click=do_update_reply).classes('bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-4 py-1 rounded shadow-md')

                                        def toggle_edit_mode(e, d_col=display_col, e_col=edit_col):
                                            d_col.set_visibility(False)
                                            e_col.set_visibility(True)
                                        
                                        def cancel_edit_mode(e, d_col=display_col, e_col=edit_col, inp=edit_input, orig_val=reply_text):
                                            inp.value = orig_val
                                            e_col.set_visibility(False)
                                            d_col.set_visibility(True)

                                        edit_btn.on('click', toggle_edit_mode)
                                        cancel_edit_btn.on('click', cancel_edit_mode)
                                        
                                        # 削除処理（ワンクッションの確認ダイアログ付き）
                                        async def do_delete_reply(r_id=rev['id']):
                                            with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white p-6 w-80'):
                                                ui.label('この返信を削除しますか？').classes('text-base font-bold text-red-400')
                                                with ui.row().classes('w-full justify-end mt-6 gap-3'):
                                                    ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                                                    def execute_delete():
                                                        # 返信カラムを空にすることで、再び「未返信」状態に戻す
                                                        res = supabase.table("event_reviews").update({"reply": None}).eq("id", r_id).execute()
                                                        if res.data:
                                                            ui.notify('返信を削除しました', type='info', position='top')
                                                            confirm_dialog.close()
                                                            refresh_all_cb()
                                                        else:
                                                            ui.notify('削除に失敗しました', type='negative', position='top')
                                                    ui.button('削除する', on_click=execute_delete).classes('bg-red-600 hover:bg-red-500 font-bold')
                                            confirm_dialog.open()
                                            
                                        delete_btn.on('click', lambda e, r=rev['id']: do_delete_reply(r))

                        elif is_su_user:
                            # まだ返信していない場合の新規投稿フォーム
                            with ui.column().classes('w-full mt-2 gap-2'):
                                reply_input = ui.textarea('運営としての返信を入力...').classes('w-full text-xs').props('outlined color="indigo" rows=2 autogrow')
                                reply_input.set_visibility(False)
                                
                                with ui.row().classes('w-full justify-end gap-2 mt-1'):
                                    reply_btn = ui.button('返信する', icon='reply').props('flat size=sm color="indigo"').classes('px-2 py-0.5')
                                    
                                    cancel_btn = ui.button('キャンセル').props('flat size=sm color="grey"').classes('px-2 py-0.5')
                                    cancel_btn.set_visibility(False)
                                    
                                    async def do_submit(r_id=rev['id'], inp=reply_input):
                                        val = inp.value
                                        if not val:
                                            ui.notify('返信を入力してください', type='warning', position='top')
                                            return
                                        res = supabase.table("event_reviews").update({"reply": val}).eq("id", r_id).execute()
                                        if res.data:
                                            ui.notify('返信を投稿しました！', type='positive', position='top')
                                            refresh_all_cb()
                                        else:
                                            ui.notify('返信の保存に失敗しました。', type='negative', position='top')

                                    submit_reply_btn = ui.button('送信', on_click=do_submit).classes('bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-4 py-1 rounded shadow-md')
                                    submit_reply_btn.set_visibility(False)
                                    
                                    def toggle_reply(e, rb=reply_btn, sb=submit_reply_btn, cb=cancel_btn, ri=reply_input):
                                        rb.set_visibility(False)
                                        sb.set_visibility(True)
                                        cb.set_visibility(True)
                                        ri.set_visibility(True)
                                    
                                    def cancel_reply(e, rb=reply_btn, sb=submit_reply_btn, cb=cancel_btn, ri=reply_input):
                                        rb.set_visibility(True)
                                        sb.set_visibility(False)
                                        cb.set_visibility(False)
                                        ri.set_visibility(False)
                                        ri.value = ""

                                    reply_btn.on('click', toggle_reply)
                                    cancel_btn.on('click', cancel_reply)