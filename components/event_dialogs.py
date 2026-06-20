# components/event_dialogs.py
from nicegui import ui
import datetime
import re
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser

from database.event_db import (
    create_event, soft_delete_event, restore_event,
    join_event, leave_event, fetch_participant_profiles, supabase,
    get_or_create_shop # ★ 追加
)
from components.avatar import draw_user_avatar
from database.scoring_db import get_user_level_raw

def is_event_past(event_date_str: str) -> bool:
    if not event_date_str:
        return False
    try:
        ev_dt = date_parser.parse(event_date_str)
        if ev_dt.tzinfo is not None:
            now_utc = datetime.now(timezone.utc)
            return ev_dt < now_utc
        else:
            now = datetime.now()
            return ev_dt < now
    except Exception as e:
        print(f"Error parsing event_date: {e}")
        return False

def fetch_shop_info_from_url(url: str) -> dict:
    result = {'image_url': None, 'shop_name': None}
    if not url or not url.strip():
        return result
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=4)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                result['image_url'] = og_img.get('content')
            else:
                tw_img = soup.find('meta', name='twitter:image')
                if tw_img and tw_img.get('content'):
                    result['image_url'] = tw_img.get('content')
            
            title_text = ""
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title_text = og_title.get('content')
            elif soup.title and soup.title.string:
                title_text = soup.title.string
                
            if title_text:
                for separator in [' - ', ' | ', ' [', '｜', ' ： ']:
                    if separator in title_text:
                        title_text = title_text.split(separator)[0]
                result['shop_name'] = title_text.strip()
                
    except Exception as e:
        print(f"ショップ自動取得エラー: {e}")
    return result

def open_create_event_dialog(current_user_id: str, refresh_cb, prefill_data: dict = None):
    initial_img_url = prefill_data.get('image_url') if prefill_data else None
    dialog_state = {'scraped_image_url': initial_img_url}
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-indigo-500/30 text-slate-800 dark:text-white'):
        ui.label('📅 新規公式イベントを告知').classes('text-lg font-bold text-slate-800 dark:text-white mb-4')
        
        title = ui.input(label='イベント名').classes('w-full mb-2').props('color="indigo" outlined')
        
        level_options = {1: '誰でも参加可能 (LV.1〜)', 2: '少し慣れた方 (LV.2〜)', 3: '常連さん限定 (LV.3〜)', 5: '超常連限定 (LV.5〜)', 10: 'VIP限定 (LV.10〜)'}
        with ui.row().classes('w-full gap-2 mb-2 no-wrap'):
            genre = ui.select(['飲み会', 'サク飯', 'お茶・カフェ', '女子会', '趣味トーク'], label='ジャンル', value='飲み会').classes('w-28').props('color="indigo" outlined')
            min_level = ui.select(options=level_options, value=1, label='参加条件 (LV制限)').classes('flex-grow').props('color="indigo" outlined')

        with ui.row().classes('w-full gap-2 mb-2 no-wrap'):
            date_input = ui.input(label='開催日').classes('flex-grow').props('type="date" color="indigo" outlined stack-label')
            time_input = ui.input(label='開始時間').classes('w-28').props('type="time" color="indigo" outlined stack-label')
        
        location = ui.input(label='場所 (例: 新宿駅東口)').classes('w-full mb-2').props('color="indigo" outlined')
        
        with ui.row().classes('w-full items-end gap-2 no-wrap mb-2'):
            initial_url = prefill_data.get('url') if prefill_data else ''
            shop_url = ui.input(label='店舗紹介URL (食べログなど)', value=initial_url).classes('flex-grow').props('color="indigo" outlined')
            
            async def handle_fetch_info():
                url_val = shop_url.value or ""
                if not url_val.strip():
                    ui.notify('先に店舗紹介URLを入力してください。', type='warning', position='top')
                    return
                
                loading = ui.notification('店名と店舗写真を自動取得中...', type='ongoing', position='top', timeout=None)
                try:
                    from nicegui import run
                    info = await run.io_bound(fetch_shop_info_from_url, url_val)
                    loading.dismiss()
                    
                    if info['shop_name']:
                        shop_name.set_value(info['shop_name'])
                        ui.notify('店名を取得・セットしました！', type='positive', position='top')
                    else:
                        ui.notify('店名の自動抽出ができませんでした', type='warning', position='top')
                        
                    if info['image_url']:
                        dialog_state['scraped_image_url'] = info['image_url']
                        preview_img.set_source(info['image_url'])
                        preview_container.classes(remove='hidden')
                        ui.notify('店舗写真を取得しました！', type='positive', position='top')
                    else:
                        dialog_state['scraped_image_url'] = None
                        preview_container.classes(add='hidden')
                        ui.notify('店舗写真が見つかりませんでした。', type='warning', position='top')
                        
                except Exception as ex:
                    loading.dismiss()
                    ui.notify(f'自動取得エラー: {ex}', type='negative', position='top')

            ui.button(icon='bolt', on_click=handle_fetch_info).classes('bg-indigo-600 hover:bg-indigo-500 text-white h-[56px] px-4 rounded-lg').tooltip('URLから店名と写真を自動取得')
        
        fee = ui.input(label='会費 (例: 4000円 / 割り勘など)').classes('w-full mb-2').props('color="indigo" outlined')
        
        initial_shop_name = prefill_data.get('shop_name') if prefill_data else ''
        shop_name = ui.input(label='店名 (例: 〇〇バル 新宿店)', value=initial_shop_name).classes('w-full mb-2').props('color="indigo" outlined')
        
        preview_hidden = 'hidden' if not dialog_state['scraped_image_url'] else ''
        with ui.row().classes(f'w-full {preview_hidden} bg-black/5 dark:bg-black/30 p-2 rounded-lg border border-indigo-500/20 items-center justify-between no-wrap mb-2') as preview_container:
            with ui.row().classes('items-center gap-2.5 overflow-hidden flex-grow'):
                preview_img = ui.image(dialog_state['scraped_image_url'] or '').classes('w-10 h-10 rounded object-cover border border-white/10 shrink-0')
                ui.label('取得した写真をセットしました').classes('text-[10px] text-slate-500 dark:text-white/50 truncate')
            def reset_preview():
                dialog_state['scraped_image_url'] = None
                preview_container.classes(add='hidden')
            ui.button(icon='close', on_click=reset_preview).props('flat round color=grey size=xs')

        description = ui.textarea(label='イベント詳細').classes('w-full mb-4').props('color="indigo" autogrow rows=3 outlined')
        
        async def submit():
            if not title.value or not date_input.value or not time_input.value or not location.value:
                ui.notify('イベント名、開催日、開始時間、場所は必須です', type='warning', position='top')
                return
            try:
                # ★ 変更：description には純粋に会費と詳細だけを入れ、店名は結合しない
                formatted_desc = ""
                if fee.value:
                    formatted_desc += f"【会費】{fee.value}\n"
                formatted_desc += f"\n{description.value or ''}"
                
                # ★ 新規：URLの有無に関わらず、店名が入力されていればshopsマスターでIDを取得/発行する
                shop_id_to_save = None
                if shop_name.value:
                    shop_data = get_or_create_shop(shop_name.value, shop_url.value, dialog_state['scraped_image_url'])
                    if shop_data:
                        shop_id_to_save = shop_data.get('id')
                
                event_date_str = f"{date_input.value} {time_input.value}"
                event_data = {
                    "title": title.value,
                    "genre": genre.value,
                    "event_date": event_date_str,
                    "location": location.value,
                    "url": shop_url.value,
                    "description": formatted_desc.strip(),
                    "image_url": dialog_state['scraped_image_url'],
                    "color_class": "bg-indigo-600",
                    "participant_ids": [current_user_id],
                    "participants_count": 1,
                    "min_level": min_level.value,
                    "shop_name": shop_name.value, # ★ 新設したカラムに直接保存
                    "shop_id": shop_id_to_save    # ★ URLがなくてもランキングに乗るよう紐付け
                }
                
                res = create_event(current_user_id, event_data)
                if res:
                    if prefill_data and prefill_data.get('request_id'):
                        try:
                            supabase.table("event_requests").update({"status": "approved"}).eq("id", prefill_data['request_id']).execute()
                            notif_msg = f"🎉 あなたのリクエストが叶いました！『{title.value}』が企画されました。カレンダーから詳細を確認してエントリーしてね！"
                            supabase.table("notifications").insert({
                                "user_id": prefill_data['requested_by'],
                                "content": notif_msg,
                                "type": "system",
                                "is_read": False
                            }).execute()
                        except Exception as req_err:
                            print(f"⚠️ [リクエスト承認連携エラー] {req_err}")

                    try:
                        formatted_content = f"📅 開催日時: {event_date_str}\n📍 場所: {location.value}\n\n新しいイベントが登録されました！ご都合が合えばぜひご参加ください！"
                        timeline_data = {
                            "user_id": current_user_id,
                            "title": f"【新規イベント】{title.value.strip()}",
                            "content": formatted_content,
                            "status": "approved",
                            "is_pinned": True,
                            "allow_chat": True
                        }
                        supabase.table("timeline_posts").insert(timeline_data).execute()
                    except Exception as tl_err:
                        print(f"⚠️ [自動告知連携エラー] {tl_err}")
                        
                    ui.notify('イベントを告知しました！', type='positive', position='top')
                    dialog.close()
                    
                    try:
                        parts = date_input.value.split('-')
                        refresh_cb(int(parts[0]), int(parts[1]))
                    except Exception:
                        refresh_cb()
                else:
                    ui.notify('イベント登録に失敗しました。', type='negative', position='top')
            except Exception as e:
                ui.notify(f'告知エラー: {e}', type='negative', position='top')
                
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('キャンセル', on_click=dialog.close).classes('bg-slate-700 text-white')
            ui.button('告知する', on_click=submit).classes('bg-indigo-600 font-bold text-white')
    dialog.open()


def open_edit_event_dialog(ev, current_user_id: str, refresh_cb):
    dialog_state = {'scraped_image_url': ev.get('image_url')}
    
    ev_date_str = ev.get('event_date') or ""
    date_val = ""
    time_val = ""
    if ev_date_str:
        try:
            parts = ev_date_str.strip().split(' ')
            if len(parts) >= 2:
                date_val = parts[0]
                time_val = parts[1][:5]
            else:
                date_val = ev_date_str
        except Exception:
            pass

    desc_raw = ev.get('description') or ""
    # ★ 新カラムから取得。もし空なら、旧データ互換のために description から救出する
    shop_name_val = ev.get('shop_name') or ""
    fee_val = ""
    clean_desc = desc_raw
    
    try:
        # 旧データ互換用：【店名】が残っていれば吸い出して消す
        if not shop_name_val:
            shop_match = re.search(r'【店名】([^\n]+)', desc_raw)
            if shop_match:
                shop_name_val = shop_match.group(1).strip()
                clean_desc = clean_desc.replace(shop_match.group(0), "")
            
        fee_match = re.search(r'【会費】([^\n]+)', desc_raw)
        if fee_match:
            fee_val = fee_match.group(1).strip()
            clean_desc = clean_desc.replace(fee_match.group(0), "")
            
        clean_desc = clean_desc.strip()
    except Exception:
        clean_desc = desc_raw

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-indigo-500/30 text-slate-800 dark:text-white'):
        ui.label('📝 イベント内容を編集').classes('text-lg font-bold text-slate-800 dark:text-white mb-4')
        
        title = ui.input(label='イベント名', value=ev.get('title')).classes('w-full mb-2').props('color="indigo" outlined')
        
        level_options = {1: '誰でも参加可能 (LV.1〜)', 2: '少し慣れた方 (LV.2〜)', 3: '常連さん限定 (LV.3〜)', 5: '超常連限定 (LV.5〜)', 10: 'VIP限定 (LV.10〜)'}
        with ui.row().classes('w-full gap-2 mb-2 no-wrap'):
            genre = ui.select(['飲み会', 'サク飯', 'お茶・カフェ', '女子会', '趣味トーク'], label='ジャンル', value=ev.get('genre', '飲み会')).classes('w-28').props('color="indigo" outlined')
            min_level = ui.select(options=level_options, value=ev.get('min_level', 1), label='参加条件 (LV制限)').classes('flex-grow').props('color="indigo" outlined')

        with ui.row().classes('w-full gap-2 mb-2 no-wrap'):
            date_input = ui.input(label='開催日', value=date_val, on_change=lambda e: None).classes('flex-grow').props('type="date" color="indigo" outlined stack-label')
            time_input = ui.input(label='開始時間', value=time_val, on_change=lambda e: None).classes('w-28').props('type="time" color="indigo" outlined stack-label')
        
        location = ui.input(label='場所 (例: 新宿駅東口)', value=ev.get('location')).classes('w-full mb-2').props('color="indigo" outlined')
        
        with ui.row().classes('w-full items-end gap-2 no-wrap mb-2'):
            shop_url = ui.input(label='店舗紹介URL (食べログなど)', value=ev.get('url')).classes('flex-grow').props('color="indigo" outlined')
            
            async def handle_fetch_info():
                url_val = shop_url.value or ""
                if not url_val.strip():
                    ui.notify('先に店舗紹介URLを入力してください。', type='warning', position='top')
                    return
                
                loading = ui.notification('店名と店舗写真を自動取得中...', type='ongoing', position='top', timeout=None)
                try:
                    from nicegui import run
                    info = await run.io_bound(fetch_shop_info_from_url, url_val)
                    loading.dismiss()
                    
                    if info['shop_name']:
                        shop_name.set_value(info['shop_name'])
                        ui.notify('店名を取得・セットしました！', type='positive', position='top')
                    else:
                        ui.notify('店名の自動抽出ができませんでした', type='warning', position='top')
                        
                    if info['image_url']:
                        dialog_state['scraped_image_url'] = info['image_url']
                        preview_img.set_source(info['image_url'])
                        preview_container.classes(remove='hidden')
                        ui.notify('店舗写真を取得しました！', type='positive', position='top')
                    else:
                        dialog_state['scraped_image_url'] = None
                        preview_container.classes(add='hidden')
                        ui.notify('店舗写真が見つかりませんでした。', type='warning', position='top')
                        
                except Exception as ex:
                    loading.dismiss()
                    ui.notify(f'自動取得エラー: {ex}', type='negative', position='top')

            ui.button(icon='bolt', on_click=handle_fetch_info).classes('bg-indigo-600 hover:bg-indigo-50 text-white h-[56px] px-4 rounded-lg').tooltip('URLから店名と写真を自動取得')
        
        fee = ui.input(label='会費 (例: 4000円 / 割り勘など)', value=fee_val).classes('w-full mb-2').props('color="indigo" outlined')
        shop_name = ui.input(label='店名 (例: 〇〇バル 新宿店)', value=shop_name_val).classes('w-full mb-2').props('color="indigo" outlined')
        
        preview_hidden = 'hidden' if not ev.get('image_url') else ''
        with ui.row().classes(f'w-full bg-black/5 dark:bg-black/30 p-2 rounded-lg border border-indigo-500/20 items-center justify-between no-wrap mb-2 {preview_hidden}') as preview_container:
            with ui.row().classes('items-center gap-2.5 overflow-hidden flex-grow'):
                preview_img = ui.image(ev.get('image_url') or '').classes('w-10 h-10 rounded object-cover border border-white/10 shrink-0')
                ui.label('店舗写真をセットしています').classes('text-[10px] text-slate-500 dark:text-white/50 truncate')
            def reset_preview():
                dialog_state['scraped_image_url'] = None
                preview_container.classes(add='hidden')
            ui.button(icon='close', on_click=reset_preview).props('flat round color=grey size=xs')

        description = ui.textarea(label='イベント詳細', value=clean_desc).classes('w-full mb-4').props('color="indigo" autogrow rows=3 outlined')
        
        async def submit_edit():
            if not title.value or not date_input.value or not time_input.value or not location.value:
                ui.notify('イベント名、開催日、開始時間、場所は必須です', type='warning', position='top')
                return
            try:
                formatted_desc = ""
                if fee.value:
                    formatted_desc += f"【会費】{fee.value}\n"
                formatted_desc += f"\n{description.value or ''}"
                
                # ★ 新規：編集時も同様に、最新の店名・URLでマスターを更新/取得して紐付ける
                shop_id_to_save = None
                if shop_name.value:
                    shop_data = get_or_create_shop(shop_name.value, shop_url.value, dialog_state['scraped_image_url'])
                    if shop_data:
                        shop_id_to_save = shop_data.get('id')
                
                event_date_str = f"{date_input.value} {time_input.value}"
                
                event_data = {
                    "title": title.value,
                    "genre": genre.value,
                    "event_date": event_date_str,
                    "location": location.value,
                    "url": shop_url.value,
                    "description": formatted_desc.strip(),
                    "image_url": dialog_state['scraped_image_url'],
                    "min_level": min_level.value,
                    "shop_name": shop_name.value, # ★ 旧イベントを編集した場合も、ここに綺麗なデータが入る
                    "shop_id": shop_id_to_save
                }
                
                res = supabase.table("events").update(event_data).eq("id", ev['id']).execute()
                if res.data:
                    ui.notify('イベント内容を保存しました！', type='positive', position='top')
                    dialog.close()
                    try:
                        parts = date_input.value.split('-')
                        refresh_cb(int(parts[0]), int(parts[1]))
                    except Exception:
                        refresh_cb()
                else:
                    ui.notify('イベントの更新に失敗しました。', type='negative', position='top')
            except Exception as e:
                ui.notify(f'更新エラー: {e}', type='negative', position='top')
                
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('キャンセル', on_click=dialog.close).classes('bg-slate-700 text-white')
            ui.button('変更を保存', on_click=submit_edit).classes('bg-indigo-600 font-bold text-white')
    dialog.open()


def open_event_detail_dialog(ev, current_user_id, refresh_cb):
    from nicegui import context
    client_st = context.client
    client_st.active_detail_event_id = ev['id']
    
    is_past_init = is_event_past(ev.get('event_date'))
    host_init = ev.get('profiles') or {}
    host_name_init = host_init.get('name', '名無し')
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md hibi-glass p-6 border border-indigo-500/30 text-slate-800 dark:text-white flex flex-col gap-4'):
        
        dialog.on('close', lambda: (
            setattr(client_st, 'active_detail_event_id', None),
            setattr(client_st, 'detail_dialog_refresh_cb', None)
        ))
        
        with ui.row().classes('w-full items-center justify-between no-wrap'):
            ui.label(ev.get('title', 'イベント詳細')).classes('text-base sm:text-lg font-bold text-slate-800 dark:text-white truncate')
            if is_past_init:
                ui.badge('イベント終了', color='slate-600').classes('text-[10px] px-2 py-0.5 shrink-0')
            else:
                ui.badge(ev.get('genre', '飲み会'), color='indigo-500').classes('text-[10px] px-2 py-0.5 shrink-0')
            
        with ui.column().classes('w-full gap-1.5'):
            with ui.row().classes('items-center gap-2'):
                draw_user_avatar(
                    avatar_url=host_init.get('avatar_url'),
                    name=host_name_init,
                    user_id=host_init.get('id') or ev.get('created_by'),
                    role=host_init.get('role'),
                    size_class='w-6 h-6',
                    show_online_badge=True,
                    border_class='border-slate-800'
                )
                ui.label(f"主催: {host_name_init}").classes('text-xs text-slate-600 dark:text-white/70')
            
            with ui.row().classes('items-center gap-2 text-xs text-slate-700 dark:text-white/90'):
                ui.icon('calendar_today', size='14px', color='indigo-300')
                ui.label(f"日時: {ev.get('event_date', '未定')}")
                
            with ui.row().classes('items-center gap-2 text-xs text-slate-700 dark:text-white/90'):
                ui.icon('place', size='14px', color='indigo-300')
                ui.label(f"場所: {ev.get('location', '未定')}")

            # ★ 新設した shop_name を表示（古いデータの場合は fallback）
            display_shop_name = ev.get('shop_name')
            if display_shop_name:
                with ui.row().classes('items-center gap-2 text-xs text-slate-700 dark:text-white/90'):
                    ui.icon('storefront', size='14px', color='teal-400')
                    ui.label(f"店名: {display_shop_name}").classes('font-bold text-teal-600 dark:text-teal-300')

        if ev.get('description'):
            ui.label(ev.get('description')).classes('text-sm text-slate-700 dark:text-slate-200 bg-black/5 dark:bg-black/30 p-3.5 rounded-lg w-full whitespace-pre-wrap')

        if ev.get('url'):
            with ui.row().classes('w-full justify-start'):
                ui.button('🍕 お店の紹介ページを開く (外部サイト)', icon='launch', on_click=lambda: ui.navigate.to(ev['url'], new_tab=True)).classes('bg-indigo-900/50 hover:bg-indigo-800 text-indigo-200 text-xs w-full py-2 rounded-lg border border-indigo-500/20')

        @ui.refreshable
        def draw_participation_section():
            current_ev = None
            try:
                res = supabase.table("events").select("*, profiles(name, avatar_url)").eq("id", ev['id']).execute()
                if res.data:
                    current_ev = res.data[0]
            except Exception as ex:
                print(f"Error fetching latest event for dialog: {ex}")
            
            if not current_ev:
                current_ev = ev
                
            try:
                res_prof = supabase.table("profiles").select("total_score, role").eq("id", current_user_id).single().execute()
                my_profile = res_prof.data or {}
                my_role = my_profile.get('role', 'member')
                my_score = float(my_profile.get('total_score') or 0.0)
            except Exception:
                my_role = 'member'
                my_score = 0.0
                
            my_lv = get_user_level_raw(my_score)
            is_su = str(my_role).lower() in ['superuser', 'admin', 'owner', 'master', 'submaster']
            is_host = str(current_ev.get('created_by')) == str(current_user_id)
            
            min_level = current_ev.get('min_level') or 1
            is_restricted = not is_su and not is_host and (my_lv < min_level)
            
            if is_restricted:
                with ui.column().classes('w-full items-center justify-center gap-3 mt-4 mb-2'):
                    ui.label('※ このイベントは、参加条件を満たしていません').classes('text-xs font-bold text-slate-500 dark:text-white/60 bg-black/10 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10 w-full text-center')
                    ui.button('閉じる', on_click=dialog.close).classes('bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold h-10 px-8 rounded-lg mt-2')
                return 
                
            participant_ids = current_ev.get('participant_ids') or []
            is_joined = current_user_id in participant_ids
            is_past = is_event_past(current_ev.get('event_date'))
            
            p_profiles = fetch_participant_profiles(participant_ids)
            
            existing_profile_ids = {p.get('id') for p in p_profiles if p.get('id')}
            for p_id in participant_ids:
                if p_id not in existing_profile_ids:
                    p_profiles.append({
                        'id': p_id,
                        'name': '名無し (テスト)',
                        'avatar_url': None,
                        'role': 'user'
                    })

            with ui.column().classes('w-full gap-4'):
                if p_profiles:
                    with ui.column().classes('w-full gap-1 mt-1'):
                        ui.label('現在の参加者:').classes('text-[10px] text-slate-500 dark:text-white/50')
                        with ui.row().classes('items-center -space-x-2'):
                            for idx, profile in enumerate(p_profiles):
                                p_name = profile.get('name', '名無し')
                                z_index = 100 - idx
                                ml_style = 'margin-left: -20px;' if idx > 0 else 'margin-left: 0px;'
                                style_str = f'position: relative; z-index: {z_index}; {ml_style}'
                                
                                with ui.element('div').classes('animate-avatar').style(style_str) as avatar_wrapper:
                                    draw_user_avatar(
                                        avatar_url=profile.get('avatar_url'),
                                        name=p_name,
                                        user_id=profile.get('id'),
                                        role=profile.get('role'),
                                        size_class='w-8 h-8',
                                        show_online_badge=True,
                                        border_class='border-slate-900 shadow-md',
                                    ).tooltip(p_name)

                with ui.row().classes('w-full justify-end gap-2 mt-2 items-center no-wrap'):
                    if (is_su or is_host) and not is_past:
                        def trigger_edit():
                            dialog.close()
                            open_edit_event_dialog(current_ev, current_user_id, refresh_cb)
                        ui.button(icon='edit', on_click=trigger_edit).props('flat round color=cyan size=sm').classes('shrink-0').tooltip('編集')
                        
                        def trigger_delete():
                            dialog.close()
                            handle_soft_delete_with_cb(current_ev['id'], refresh_cb)
                        ui.button(icon='delete', on_click=trigger_delete).props('flat round color=red size=sm').classes('shrink-0').tooltip('削除')

                    ui.button('閉じる', on_click=dialog.close).classes('bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')
                    
                    if is_host:
                        ui.badge('👑 主催イベント', color='indigo-500').classes('text-xs px-3 py-2 h-10 flex items-center rounded-lg shrink-0 font-bold')
                    elif is_past:
                        ui.button('イベントは終了しました', icon='lock').props('disable').classes('bg-slate-800 text-white/40 text-xs font-bold h-10 px-4 rounded-lg shrink-0 border border-white/5')
                    else:
                        if is_joined:
                            async def handle_leave():
                                with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-80 p-6'):
                                    ui.label('イベントの参加を取り消しますか？').classes('text-base font-bold text-red-400')
                                    with ui.row().classes('w-full justify-end mt-6 gap-3'):
                                        ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
                                        def execute_leave():
                                            if leave_event(current_ev['id'], current_user_id):
                                                ui.notify('イベント参加をキャンセルしました。', type='warning', position='top')
                                                confirm_dialog.close()
                                                dialog.close()
                                                refresh_cb()
                                            else:
                                                ui.notify('キャンセルの処理でエラーが発生しました。', type='negative', position='top')
                                        ui.button('取り消す', on_click=execute_leave).classes('bg-red-600 hover:bg-red-500 font-bold')
                                confirm_dialog.open()
                            ui.button('参加済み (タップで辞める)', icon='check_circle', on_click=handle_leave).classes('bg-teal-600 hover:bg-red-700 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0 transition-all duration-200')
                        else:
                            async def handle_join():
                                if join_event(current_ev['id'], current_user_id):
                                    ui.notify('イベントに参加しました！よろしくね！', type='positive', position='top')
                                    refresh_cb()
                                else:
                                    ui.notify('参加登録の処理でエラーが発生しました。', type='negative', position='top')
                            ui.button('このイベントに参加する', icon='add_circle', on_click=handle_join).classes('bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold h-10 px-4 rounded-lg shrink-0')
        
        client_st.detail_dialog_refresh_cb = draw_participation_section.refresh
        draw_participation_section()
        
    dialog.open()

def handle_soft_delete_with_cb(ev_id: str, refresh_cb):
    with ui.dialog() as confirm_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-80 p-6'):
        ui.label('イベントを削除しますか？').classes('text-base font-bold text-red-400')
        ui.label('※仮削除状態になり、12時間以内であれば「復活」ボタンから復元可能です。').classes('text-xs text-white/60')
        with ui.row().classes('w-full justify-end mt-6 gap-3'):
            ui.button('キャンセル', on_click=confirm_dialog.close).props('flat color=white')
            def execute_delete():
                soft_delete_event(ev_id)
                ui.notify('イベントを仮削除しました（12時間以内なら復活可能）', color='warning', position='top')
                confirm_dialog.close()
                refresh_cb()
            ui.button('削除する', on_click=execute_delete).classes('bg-red-600 hover:bg-red-500 font-bold')
    confirm_dialog.open()