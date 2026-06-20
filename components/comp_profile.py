# components/comp_profile.py
from nicegui import ui, app
import inspect
import uuid
import os
import base64
from database.profile_db import (
    get_safe_profile, update_profile, fetch_ogp_data, 
    is_user_online, get_or_create_invite_code, regenerate_invite_code
)
from components.avatar import draw_user_avatar, get_avatar_url

# ★ 新規追加：イベント側で作ったお店マスター登録関数をインポート
from database.event_db import get_or_create_shop 

LIQUOR_CATEGORIES = {
    '🍺 ビール系': ['ピルスナー', 'クラフトビール全般', 'IPA', 'ペールエール', 'スタウト・黒ビール', 'ヴァイツェン', 'フルーツビール', '発泡酒・第3のビール'],
    '🍶 和酒系': ['日本酒（純米系）', '日本酒（吟醸系）', '日本酒（本醸造系）', '芋焼酎', '麦焼酎', '米焼酎', '黒糖焼酎', '泡盛', 'マッコリ'],
    '🍷 ワイン・果実酒系': ['赤ワイン', '白ワイン', 'スパークリング・シャンパン', 'ロゼ', 'オレンジ・自然派ワイン', '梅酒', 'ゆず酒・その他果実酒'],
    '🥃 ウイスキー・スピリッツ系': ['スコッチウイスキー', 'バーボン', 'ジャパニーズウイスキー', 'シングルモルト', 'ブランデー・コニャック', 'ジン・クラフトジン', 'ウォッカ', 'ラム', 'テキーラ'],
    '🍹 サワー・カクテル系': ['レモンサワー', 'お茶割り・チューハイ', 'ハイボール', 'カクテル全般', '甘いリキュール系', 'ホッピー', 'ノンアルコール・モクテル']
}

ALL_LIQUORS = [item for sublist in LIQUOR_CATEGORIES.values() for item in sublist]

def get_parent_categories(selected_liquors):
    parents = set()
    for liquor in selected_liquors:
        for parent, children in LIQUOR_CATEGORIES.items():
            if liquor in children:
                parents.add(parent)
                break
    return list(parents)

DRINKING_STYLES = [
    'みんなでワイワイ', '少人数でじっくり', '一人でしっぽり', 'とりあえず飲む！'
]

GENDER_MASTER = {
    0: '回答しない',
    1: '男性',
    2: '女性',
    3: 'その他'
}

def render_section_title(title):
    with ui.row().classes('items-center gap-2 mt-6 mb-2 px-1 w-full'):
        ui.element('div').classes('w-1 h-4 bg-cyan-400 rounded-full shadow-[0_0_8px_#22d3ee]')
        ui.label(title).classes('text-sm font-black text-cyan-400 tracking-widest')

def show_profile_dialog(target_user_id: str, current_user_id: str = None):
    is_me = (current_user_id is None) or (target_user_id == current_user_id)
    profile = get_safe_profile(target_user_id)
    
    with ui.dialog() as dialog, ui.card().classes('w-[450px] max-w-full max-h-[90vh] overflow-y-auto p-6 rounded-3xl bg-slate-900 border border-white/10 hide-scrollbar'):
        
        if is_me:
            role_str = app.storage.user.get('role', profile.get('role', ''))
        else:
            role_str = profile.get('role', '')
            
        role_lower = str(role_str).lower()
        is_su = role_lower in ['superuser', 'admin', 'owner', 'master', 'submaster']

        if is_me:
            with ui.row().classes('w-full items-center justify-between mb-4'):
                ui.label('プロフィール編集').classes('text-2xl font-bold text-white')
                ui.button(icon='close', on_click=dialog.close).props('flat round color=white size=sm')
                
            state = {}
            current_avatar_url = profile.get('avatar_url')
            
            with ui.column().classes('w-full gap-2'):
                with ui.row().classes('w-full justify-center mb-6'):
                    edit_avatar_container = ui.element('div').classes('relative inline-block w-28 h-28')
                    
                    async def handle_avatar_upload(e):
                        nonlocal current_avatar_url
                        try:
                            content_obj = getattr(e, 'content', getattr(e, 'file', None))
                            if not content_obj:
                                ui.notify('ファイルが読み込めませんでした', color='negative', position='top')
                                return
                                
                            data = content_obj.read()
                            if inspect.isawaitable(data):
                                data = await data
                                
                            if not data:
                                ui.notify('データが空です', color='negative', position='top')
                                return
                                
                            filename = f"avatar_{uuid.uuid4()}.jpg"
                            filepath = f"static/profiles/{filename}"
                            os.makedirs('static/profiles', exist_ok=True)
                            with open(filepath, 'wb') as f:
                                f.write(data)
                                
                            current_avatar_url = f"/{filepath}"
                            rebuild_edit_avatar()
                            ui.notify('アバター画像を変更しました！', color='positive', position='top')
                        except Exception as ex:
                            ui.notify(f'画像の保存に失敗しました: {ex}', color='negative', position='top')

                    uploader = ui.upload(on_upload=handle_avatar_upload, auto_upload=True, max_files=1).props('accept="image/*"').style('display: none;')
                    
                    def trigger_upload():
                        uploader.run_method('pickFiles')

                    def rebuild_edit_avatar():
                        edit_avatar_container.clear()
                        with edit_avatar_container:
                            draw_user_avatar(
                                avatar_url=current_avatar_url, 
                                name=profile.get('name'), 
                                user_id=target_user_id, 
                                role=role_str, 
                                size_class='w-28 h-28', 
                                border_class='border-4 border-slate-700 shadow-lg cursor-pointer hover:opacity-80 transition hover:border-cyan-500'
                            )
                            click_layer = ui.element('div').classes('absolute inset-0 cursor-pointer rounded-full z-20')
                            click_layer.on('click', trigger_upload)

                            camera_icon = ui.icon('camera_alt', size='xs', color='white').classes('absolute -bottom-2 left-1/2 -translate-x-1/2 bg-cyan-600 rounded-full p-1.5 border-2 border-slate-900 cursor-pointer hover:bg-cyan-500 transition shadow-md z-30')
                            camera_icon.on('click', trigger_upload)

                    rebuild_edit_avatar()

                render_section_title('基本情報')
                state['name'] = ui.input('ニックネーム', value=profile.get('name')).classes('w-full').props('dark filled')
                
                current_gender = profile.get('gender', 0)
                if current_gender == 0:
                    state['gender'] = ui.select(options=GENDER_MASTER, label='性別 (※登録後の変更不可)', value=current_gender).classes('w-full').props('dark filled')
                    ui.label('※クローズドコミュニティの安全のため、性別は一度登録すると後から変更できません。虚偽の申告が発覚した場合は、オーナーにより即時アカウント停止となります。')\
                        .classes('text-[10px] text-red-400 font-bold mb-2 leading-tight bg-red-900/20 p-2 rounded border border-red-500/50')
                else:
                    state['gender'] = ui.select(options=GENDER_MASTER, label='性別', value=current_gender).classes('w-full').props('dark filled disable')
                    ui.label('※性別の変更はできません。誤って登録した場合は運営へお問い合わせください。')\
                        .classes('text-[10px] text-white/50 mb-2')

                with ui.row().classes('w-full gap-2 no-wrap'):
                    state['birthday'] = ui.input('誕生日', value=profile.get('birthday')).props('type=date dark filled').classes('w-1/2')
                    state['location'] = ui.input('居住地', value=profile.get('location')).classes('w-1/2').props('dark filled')
                state['occupation'] = ui.input('職業', value=profile.get('occupation')).classes('w-full').props('dark filled')
                
                render_section_title('自己紹介')
                state['comment'] = ui.input('ひと言コメント', value=profile.get('comment')).classes('w-full').props('dark filled')
                state['hobbies'] = ui.input('趣味', value=profile.get('hobbies')).classes('w-full').props('dark filled')
                state['bio'] = ui.textarea('自己紹介文', value=profile.get('bio')).classes('w-full').props('dark filled autogrow')
                
                render_section_title('お酒のスタイル')
                ui.label('好きなお酒 (最大10個まで)').classes('text-xs text-white/70 mb-1')
                
                raw_val = profile.get('liquor_type')
                if isinstance(raw_val, list):
                    raw_liquors = [str(x).strip() for x in raw_val if x]
                elif isinstance(raw_val, str):
                    cleaned_str = raw_val.replace('[', '').replace(']', '').replace('"', '').replace("'", '')
                    raw_liquors = [x.strip() for x in cleaned_str.split(',') if x.strip()]
                else:
                    raw_liquors = []

                selected_liquors = set(raw_liquors)
                liquor_buttons = {}
                
                def toggle_liquor(l_name):
                    if l_name in selected_liquors:
                        selected_liquors.remove(l_name)
                        liquor_buttons[l_name].classes(remove='selected')
                    else:
                        if len(selected_liquors) >= 10:
                            ui.notify('登録できるお酒は10個までです！', type='warning', position='top')
                            return
                        selected_liquors.add(l_name)
                        liquor_buttons[l_name].classes(add='selected')
                    
                    liquor_buttons[l_name].update()
                    
                ui.add_head_html("""
                <style>
                .liquor-btn:not(.selected) {
                    border: 1.5px solid var(--q-primary) !important;
                    background-color: transparent !important;
                }
                .liquor-btn:not(.selected),
                .liquor-btn:not(.selected) * {
                    color: var(--q-primary) !important;
                }
                .liquor-btn.selected {
                    background-color: var(--q-primary) !important;
                    border: 1.5px solid var(--q-primary) !important;
                }
                .liquor-btn.selected,
                .liquor-btn.selected * {
                    color: #ffffff !important;
                }
                .liquor-btn {
                    transition: all 0.2s ease !important;
                }
                </style>
                """)
                with ui.column().classes('w-full gap-2 mb-2'):
                    for parent, children in LIQUOR_CATEGORIES.items():
                        with ui.expansion(parent, icon='local_bar').classes('w-full bg-black/30 rounded-lg border border-white/5').props('dense dark'):
                            with ui.row().classes('w-full gap-2 p-2'):
                                for l_name in children:
                                    is_selected = l_name in selected_liquors
                                    btn_classes = 'px-2.5 py-1 text-[10px] liquor-btn '
                                    if is_selected:
                                        btn_classes += 'selected'
                                    
                                    btn = ui.button(l_name, on_click=lambda e, n=l_name: toggle_liquor(n))\
                                        .props('flat rounded size=sm')\
                                        .classes(btn_classes)
                                        
                                    liquor_buttons[l_name] = btn

                state['favorite_brand'] = ui.input('好きな銘柄', value=profile.get('favorite_brand')).classes('w-full mt-2').props('dark filled')
                ui.label('飲み方スタイル').classes('text-xs text-white/70 mb-1 mt-2')
                current_style = profile.get('drinking_style')
                current_style = current_style if current_style in DRINKING_STYLES else None
                state['drinking_style'] = ui.radio(DRINKING_STYLES, value=current_style).props('dark inline').classes('w-full text-white text-sm')
                state['drinking_area'] = ui.input('よく飲むエリア', value=profile.get('drinking_area')).classes('w-full mt-2').props('dark filled')

                render_section_title('おすすめの店・行きつけ')
                with ui.row().classes('w-full gap-2 items-center'):
                    state['bar_url'] = ui.input(placeholder='店舗URL (食べログ等)', value=profile.get('bar_url')).classes('flex-grow').props('dark filled')
                    async def magic_fetch():
                        if not state['bar_url'].value: return
                        data = fetch_ogp_data(state['bar_url'].value)
                        state['recommended_bar'].set_value(data['title'])
                        state['bar_image_url'].set_source(data['image'])
                        ui.notify('店舗情報を取得しました！', color='positive', position='top')
                    ui.button(icon='auto_awesome', on_click=magic_fetch).props('flat round color=orange').tooltip('URLから自動取得')
                
                state['recommended_bar'] = ui.input('店名', value=profile.get('recommended_bar')).classes('w-full').props('dark filled')
                state['bar_image_url'] = ui.image(source=profile.get('bar_image_url')).classes('w-full h-32 object-cover rounded-xl mt-2')

            def save():
                raw_birthday = state['birthday'].value
                safe_birthday = raw_birthday.strip() if (raw_birthday and raw_birthday.strip()) else None

                # ★ 新規追加：おすすめのお店が入力されていれば、裏でshopsマスターにも登録・同期する！
                rec_bar = state['recommended_bar'].value
                if rec_bar and rec_bar.strip():
                    try:
                        get_or_create_shop(
                            name=rec_bar, 
                            url=state['bar_url'].value, 
                            image_url=state['bar_image_url'].source
                        )
                    except Exception as e:
                        print(f"Profile shop sync error: {e}")

                new_data = {
                    "name": state['name'].value,
                    "avatar_url": current_avatar_url,
                    "gender": state['gender'].value,
                    "birthday": safe_birthday,
                    "location": state['location'].value,
                    "occupation": state['occupation'].value,
                    "hobbies": state['hobbies'].value,
                    "comment": state['comment'].value,
                    "bio": state['bio'].value,
                    "liquor_type": list(selected_liquors),
                    "favorite_brand": state['favorite_brand'].value,
                    "drinking_style": state['drinking_style'].value,
                    "drinking_area": state['drinking_area'].value,
                    "bar_url": state['bar_url'].value,
                    "recommended_bar": state['recommended_bar'].value,
                    "bar_image_url": state['bar_image_url'].source
                }
                update_profile(target_user_id, new_data)
                
                if 'user_metadata' not in app.storage.user:
                    app.storage.user['user_metadata'] = {}
                app.storage.user['user_metadata']['avatar_url'] = current_avatar_url
                app.storage.user['user_metadata']['name'] = state['name'].value

                ui.notify('プロフィールを保存しました！', color='positive', position='top')
                dialog.close()
                ui.run_javascript('window.location.reload()')

            with ui.row().classes('w-full mt-8 gap-3'):
                ui.button('キャンセル', on_click=dialog.close).props('flat color=white').classes('flex-grow')
                ui.button('保存する', on_click=save).classes('flex-grow bg-cyan-600 hover:bg-cyan-500 font-bold text-lg')

        else:
            with ui.row().classes('w-full justify-between items-start mb-2'):
                ui.label(f"{profile.get('name', '名無し')}").classes('text-2xl font-extrabold text-white')
                ui.button(icon='close', on_click=dialog.close).props('flat round color=white size=sm')

            if profile.get('comment'):
                ui.label(profile.get('comment')).classes('text-sm text-cyan-300 font-bold mb-4 bg-cyan-900/30 px-3 py-1 rounded-lg inline-block')

            with ui.row().classes('w-full justify-center mb-4'):
                draw_user_avatar(
                    avatar_url=profile.get('avatar_url'), 
                    name=profile.get('name'), 
                    user_id=target_user_id, 
                    role=profile.get('role', ''), 
                    size_class='w-28 h-28', 
                    border_class='border-4 border-slate-800 shadow-[0_0_20px_rgba(34,211,238,0.2)]'
                )

            with ui.column().classes('w-full gap-1 text-white'):
                with ui.card().classes('w-full bg-white/5 border border-white/10 p-4 shadow-none gap-2 mt-2'):
                    def info_row(icon, label_text, val):
                        if val:
                            with ui.row().classes('items-center gap-2 w-full'):
                                ui.icon(icon, size='sm', color='white').classes('opacity-50')
                                ui.label(label_text).classes('text-xs text-white/50 w-16')
                                ui.label(val).classes('text-sm font-medium')
                    
                    gender_str = GENDER_MASTER.get(profile.get('gender', 0), '未設定')
                    info_row('wc', '性別', gender_str)
                    info_row('cake', '誕生日', profile.get('birthday'))
                    info_row('place', '居住地', profile.get('location'))
                    info_row('work', '職業', profile.get('occupation'))
                    info_row('favorite', '趣味', profile.get('hobbies'))

                render_section_title('自己紹介')
                bio_text = profile.get('bio')
                if bio_text:
                    ui.label(bio_text).classes('text-sm text-white/90 whitespace-pre-wrap px-2 leading-relaxed')
                else:
                    ui.label('まだ自己紹介がありません。').classes('text-xs text-white/40 italic px-2')
                
                render_section_title('お酒のスタイル')
                raw_liquors_view = profile.get('liquor_type') or []
                liquors = [x for x in raw_liquors_view if x in ALL_LIQUORS]
                    
                if liquors:
                    with ui.row().classes('gap-2 px-2 mb-2'):
                        for l in liquors:
                            ui.label(l).classes('text-[11px] font-bold bg-cyan-900/80 text-cyan-200 px-3 py-1 rounded-full border border-cyan-500/50')
                else:
                    ui.label('未設定').classes('text-xs text-white/40 italic px-2 mb-2')
                
                with ui.column().classes('px-2 gap-1 w-full'):
                    if profile.get('drinking_style'):
                        with ui.row().classes('items-center gap-2'):
                            ui.badge('スタイル', color='slate-700')
                            ui.label(profile.get('drinking_style')).classes('text-sm font-bold text-amber-400')
                    if profile.get('drinking_area'):
                        with ui.row().classes('items-center gap-2'):
                            ui.badge('出没エリア', color='slate-700')
                            ui.label(profile.get('drinking_area')).classes('text-sm')
                    if profile.get('favorite_brand'):
                        with ui.row().classes('items-center gap-2'):
                            ui.badge('好きな銘柄', color='slate-700')
                            ui.label(profile.get('favorite_brand')).classes('text-sm')

                render_section_title('おすすめの店')
                if profile.get('recommended_bar'):
                    with ui.card().classes('w-full bg-black/40 p-0 rounded-xl border border-white/5 overflow-hidden mt-2'):
                        if profile.get('bar_image_url'):
                            ui.element('img').props(f'src="{profile.get("bar_image_url")}"').style('width: 100%; height: 160px; object-fit: contain;')
                        with ui.column().classes('p-4 gap-1 w-full'):
                            ui.label(profile.get('recommended_bar')).classes('font-bold text-cyan-400 text-base')
                            if profile.get('bar_url'):
                                ui.link('店舗情報を見る', profile.get('bar_url'), new_tab=True).classes('text-sm text-blue-400 hover:text-blue-300 mt-1 block')
                else:
                    ui.label('未設定').classes('text-xs text-white/40 italic px-2')

            ui.button('閉じる', on_click=dialog.close).classes('w-full mt-8 bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-bold')

    dialog.open()