# components/members_view.py
import inspect
import uuid
import os
import asyncio
from nicegui import ui, app, context
from components.comp_profile import show_profile_dialog, get_parent_categories, LIQUOR_CATEGORIES, GENDER_MASTER, ALL_LIQUORS
from database.profile_db import get_all_profiles, get_safe_profile, is_user_online, supabase, fetch_ogp_data
from components.avatar import draw_user_avatar
from themes import THEMES
from database.scoring_db import get_frequent_companions, calculate_user_level
from components.members_logic import is_mobile_client, parse_liquor_type, MembersPresenter, ADMIN_ROLES, DRINKING_STYLES

def render_section_title(title):
    with ui.row().classes('items-center gap-2 mt-4 mb-2 px-1 w-full'):
        ui.element('div').classes('w-1 h-4 bg-cyan-400 rounded-full shadow-[0_0_8px_#22d3ee]')
        ui.label(title).classes('text-sm font-black text-cyan-400 tracking-widest')

def inject_custom_css():
    ui.add_css('''
        /* 白飛び対策 */
        .theme-light .q-menu, .theme-light .q-dialog .q-card {
            background-color: #ffffff !important;
            color: #1e293b !important;
        }
        .theme-light .q-menu .q-item, .theme-light .q-dialog .q-item {
            color: #1e293b !important;
        }
        .theme-light .q-menu .q-item__label, .theme-light .q-dialog .q-item__label {
            color: #1e293b !important;
        }

        /* PC画面での一瞬真ん中に寄るワープ現象の完全防止 */
        main:has(.members-view-container), 
        .q-page:has(.members-view-container),
        div:has(> .members-view-container) {
            max-width: none !important;
            width: 100% !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
        }

        /* スマホ・PCのレスポンシブ表示制御用 */
        @media (max-width: 767px) {
            .mobile-hidden {
                display: none !important;
            }
        }
        @media (min-width: 768px) {
            .pc-hidden {
                display: none !important;
            }
        }

        /* ライトテーマ時の白飛び大対策 */
        .theme-light .q-expansion-item,
        .theme-light .q-expansion-item .q-item__label,
        .theme-light .q-expansion-item .q-focus-helper,
        .theme-light .q-expansion-item .q-item,
        .theme-light .q-expansion-item .q-item__label * {
            color: #1e293b !important;
        }

        /* スクロールバーのカスタマイズ */
        .hide-scrollbar::-webkit-scrollbar {
            width: 4px;
        }
        .hide-scrollbar::-webkit-scrollbar-track {
            background: transparent;
        }
        .hide-scrollbar::-webkit-scrollbar-thumb {
            background-color: rgba(156, 163, 175, 0.4);
            border-radius: 4px;
        }
        .theme-light .hide-scrollbar::-webkit-scrollbar-thumb {
            background-color: rgba(148, 163, 184, 0.4);
        }
    ''')

def render_members(current_user_id: str):
    is_mobile = is_mobile_client()
    inject_custom_css()

    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)
    dark_val = 'false' if is_light else 'true'

    current_user_profile = get_safe_profile(current_user_id)
    current_role = str(current_user_profile.get('role', 'member')).lower()
    is_current_admin = current_role in ADMIN_ROLES
    
    sort_options = {'new': '登録が新しい順', 'score': 'スコア順 (貢献度)', 'name': '名前（五十音）順'}
    if is_current_admin:
        sort_options = {'active': '最近アクティブ（管理者用）'} | sort_options

    p = MembersPresenter(current_user_id, is_mobile)

    def draw_detail(target_id, refresh_func, close_dialog=None):
        profile = get_safe_profile(target_id)
        db_liquor_types = parse_liquor_type(profile.get('liquor_type'))
        profile['liquor_type'] = db_liquor_types

        target_role = str(profile.get('role', 'member')).lower()
        is_target_admin = target_role in ADMIN_ROLES
        show_badge_permission = is_current_admin or is_target_admin

        with ui.column().classes('w-full flex-grow p-0 gap-6'):
            
            with ui.card().classes('w-full hibi-glass rounded-2xl overflow-hidden p-0 border border-slate-200 dark:border-white/5 shadow-xl bg-slate-50/50 dark:bg-slate-900/40 w-full'):
                
                header_img_container = ui.element('div').classes('w-full h-28 relative bg-gradient-to-r from-slate-900 via-indigo-950 to-amber-950/40 overflow-hidden')
                
                if p.is_editing and target_id == current_user_id:
                    e_state = p.edit_state
                    
                    async def handle_header_upload(e):
                        try:
                            content_obj = getattr(e, 'content', getattr(e, 'file', None))
                            if not content_obj: return
                            data = content_obj.read()
                            if inspect.isawaitable(data): data = await data
                            if not data: return
                            
                            filename = f"header_{uuid.uuid4()}.jpg"
                            filepath = f"static/profiles/{filename}"
                            os.makedirs('static/profiles', exist_ok=True)
                            with open(filepath, 'wb') as f:
                                f.write(data)
                            e_state['header_image_url'] = f"/{filepath}"
                            refresh_func()
                            ui.notify('ヘッダー画像を変更しました！', color='positive', position='top')
                        except Exception as ex:
                            ui.notify(f'画像の保存に失敗しました: {ex}', color='negative', position='top')

                    header_uploader = ui.upload(on_upload=handle_header_upload, auto_upload=True, max_files=1).props('accept="image/*"').style('display: none;')
                    def trigger_header_upload(): header_uploader.run_method('pickFiles')
                    
                    with header_img_container:
                        if e_state.get('header_image_url'):
                            ui.image(e_state['header_image_url']).classes('w-full h-full object-cover')
                        
                        click_layer = ui.element('div').classes('absolute inset-0 cursor-pointer bg-black/40 opacity-0 hover:opacity-100 flex flex-col items-center justify-center transition-opacity duration-200 z-10')
                        click_layer.on('click', trigger_header_upload)
                        with click_layer:
                            ui.icon('camera_alt', size='sm', color='white')
                            ui.label('ヘッダーを変更').classes('text-white text-[10px] mt-1 font-bold')
                else:
                    with header_img_container:
                        if profile.get('header_image_url'):
                            ui.image(profile.get('header_image_url')).classes('w-full h-full object-cover')
                
                with ui.row().classes('w-full px-4 md:px-6 pb-4 md:pb-6 items-start justify-between gap-3 md:gap-4 flex-wrap md:flex-nowrap'):
                    with ui.row().classes('items-start gap-3 md:gap-4 flex-grow min-w-0 no-wrap'):
                        
                        if p.is_editing and target_id == current_user_id:
                            e_state = p.edit_state
                            edit_avatar_container = ui.element('div').classes('relative inline-block w-24 h-24 -mt-12 shrink-0 z-10')
                            
                            async def handle_avatar_upload(e):
                                try:
                                    content_obj = getattr(e, 'content', getattr(e, 'file', None))
                                    if not content_obj: return
                                    data = content_obj.read()
                                    if inspect.isawaitable(data): data = await data
                                    if not data: return
                                    
                                    filename = f"avatar_{uuid.uuid4()}.jpg"
                                    filepath = f"static/profiles/{filename}"
                                    os.makedirs('static/profiles', exist_ok=True)
                                    with open(filepath, 'wb') as f:
                                        f.write(data)
                                    e_state['avatar_url'] = f"/{filepath}"
                                    refresh_func()
                                    ui.notify('アバター画像を変更しました！', color='positive', position='top')
                                except Exception as ex:
                                    ui.notify(f'画像の保存に失敗しました: {ex}', color='negative', position='top')

                            uploader = ui.upload(on_upload=handle_avatar_upload, auto_upload=True, max_files=1).props('accept="image/*"').style('display: none;')
                            def trigger_upload(): uploader.run_method('pickFiles')

                            with edit_avatar_container:
                                draw_user_avatar(
                                    avatar_url=e_state['avatar_url'], 
                                    name=e_state['name'], 
                                    user_id=target_id, 
                                    role=profile.get('role', ''), 
                                    size_class='w-full h-full', 
                                    border_class='border-4 border-white dark:border-slate-900 shadow-lg cursor-pointer hover:opacity-80 transition'
                                )
                                ui.element('div').classes('absolute inset-0 cursor-pointer rounded-full z-20').on('click', trigger_upload)
                                ui.icon('camera_alt', size='xs', color='white').classes('absolute -bottom-1 left-1/2 -translate-x-1/2 bg-cyan-600 rounded-full p-1.5 border-2 border-slate-900 cursor-pointer hover:bg-cyan-500 transition shadow-md z-30').on('click', trigger_upload)
                        else:
                            with ui.element('div').classes('w-24 h-24 -mt-12 shrink-0 z-10'):
                                draw_user_avatar(
                                    avatar_url=profile.get('avatar_url'), 
                                    name=profile.get('name'), 
                                    user_id=target_id, 
                                    role=profile.get('role'),
                                    size_class='w-full h-full', 
                                    show_online_badge=show_badge_permission, 
                                    border_class='border-4 border-white dark:border-slate-900 shadow-lg'
                                )

                        if p.is_editing and target_id == current_user_id:
                            e_state = p.edit_state
                            with ui.column().classes('gap-2 z-10 flex-grow min-w-0 w-full pt-2'):
                                ui.input(
                                    label='ニックネーム', 
                                    value=e_state['name'], 
                                    on_change=lambda e: e_state.update({'name': e.value})
                                ).props('dense filled').classes('text-sm font-bold w-full')
                                
                                ui.input(
                                    label='ひと言コメント', 
                                    value=e_state['comment'], 
                                    on_change=lambda e: e_state.update({'comment': e.value})
                                ).props('dense filled').classes('text-xs w-full')
                        else:
                            with ui.column().classes('gap-1 z-10 flex-grow min-w-0 justify-center pt-2'):
                                with ui.row().classes('items-center gap-2 max-w-full no-wrap'):
                                    ui.label(profile.get('name', '名無し')).classes('text-2xl font-black text-slate-800 dark:text-slate-100 tracking-wide truncate')
                                    if is_target_admin:
                                        ui.label('運営').classes('text-[10px] font-black bg-cyan-100 dark:bg-cyan-950/60 text-cyan-800 dark:text-cyan-400 px-2 py-0.5 rounded border border-cyan-300 dark:border-cyan-500/30 shrink-0')

                                if profile.get('comment'):
                                    ui.label(profile.get('comment')).classes('text-xs font-bold text-amber-700 dark:text-amber-400/90 bg-amber-50 dark:bg-amber-950/30 px-3 py-1.5 rounded-xl border border-amber-500/10 max-w-full break-words whitespace-normal')

                with ui.row().classes('w-full items-center gap-2 px-4 md:px-6 pb-4 shrink-0'):
                    if close_dialog:
                        ui.button('戻る', icon='arrow_back', on_click=close_dialog).props('flat dense color=cyan-500').classes('text-xs font-bold md:hidden')

                    ui.element('div').classes('flex-grow')

                    if target_id == current_user_id:
                        if not p.is_editing:
                            ui.button(
                                'プロフィールを編集', 
                                icon='edit', 
                                on_click=lambda: [p.start_editing(profile, db_liquor_types), refresh_func()]
                            ).props('outline color=amber-500').classes('text-[10px] md:text-xs font-bold rounded-full px-3 md:px-4')
                        else:
                            ui.button(
                                '保存する', 
                                icon='save', 
                                on_click=p.save_editing
                            ).props('filled color=cyan-600').classes('text-[10px] md:text-xs font-bold text-white rounded-full px-3 md:px-4')
                            
                            ui.button(
                                'キャンセル', 
                                on_click=lambda: [p.cancel_editing(), refresh_func()]
                            ).props('flat color=grey').classes('text-[10px] md:text-xs font-bold rounded-full')

            with ui.grid(columns=1).classes('w-full gap-6 mt-2 md:grid-cols-2'):
                
                with ui.column().classes('w-full gap-4'):
                    with ui.card().classes('w-full p-4 hibi-glass rounded-2xl border border-slate-200 dark:border-white/5'):
                        ui.label('◆ ゲスト基本情報').classes('text-xs font-bold text-slate-400 dark:text-white/30 tracking-widest mb-2')
                        
                        def render_field(icon, label, value_key, input_type='text'):
                            if not p.is_editing:
                                val = profile.get(value_key)
                                if value_key == 'gender': val = GENDER_MASTER.get(val, '未設定')
                                if val:
                                    with ui.row().classes('items-center gap-2.5 text-xs py-1.5 border-b border-slate-150 dark:border-white/5 w-full'):
                                        ui.icon(icon, size='xs').classes('text-slate-400 dark:text-white/40')
                                        ui.label(label).classes('text-slate-400 dark:text-white/30 w-12 shrink-0')
                                        ui.label(str(val)).classes('text-slate-800 dark:text-slate-100 font-medium')
                            else:
                                e_state = p.edit_state
                                with ui.column().classes('w-full gap-1 py-1 border-b border-slate-100 dark:border-white/5'):
                                    ui.label(label).classes('text-[10px] text-slate-400 dark:text-white/30 font-bold')
                                    with ui.row().classes('items-center gap-2 w-full'):
                                        ui.icon(icon, size='xs').classes('text-slate-400 dark:text-white/40')
                                        if value_key == 'gender':
                                            if e_state['gender'] == 0:
                                                ui.select(options=GENDER_MASTER, value=e_state['gender'], on_change=lambda e: e_state.update({'gender': e.value})).props('dense filled').classes('flex-grow text-xs')
                                            else:
                                                ui.select(options=GENDER_MASTER, value=e_state['gender']).props('dense filled disable').classes('flex-grow text-xs')
                                        elif input_type == 'date':
                                            ui.input(value=e_state[value_key], on_change=lambda e, k=value_key: e_state.update({k: e.value})).props('dense filled type=date').classes('flex-grow text-xs')
                                        else:
                                            ui.input(value=e_state[value_key], on_change=lambda e, k=value_key: e_state.update({k: e.value})).props('dense filled').classes('flex-grow text-xs')

                        render_field('wc', '性別', 'gender')
                        render_field('cake', '誕生日', 'birthday', 'date')
                        render_field('place', '居住地', 'location')
                        render_field('work', '職業', 'occupation')
                        render_field('favorite', '趣味', 'hobbies')

                    with ui.card().classes('w-full p-4 hibi-glass rounded-2xl border border-slate-200 dark:border-white/5'):
                        ui.label('◆ 自己紹介').classes('text-xs font-bold text-slate-400 dark:text-white/30 tracking-widest mb-2')
                        if not p.is_editing:
                            bio_text = profile.get('bio')
                            if bio_text:
                                ui.label(bio_text).classes('text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap leading-relaxed px-1')
                            else:
                                ui.label('まだ自己紹介がありません。').classes('text-xs text-slate-400 dark:text-white/30 italic px-1')
                        else:
                            e_state = p.edit_state
                            ui.textarea(
                                value=e_state['bio'], 
                                on_change=lambda e: e_state.update({'bio': e.value})
                            ).props('filled autogrow dense').classes('w-full text-xs')

                with ui.column().classes('w-full gap-4'):
                    with ui.card().classes('w-full p-4 hibi-glass rounded-2xl border border-slate-200 dark:border-white/5'):
                        ui.label('◆ お酒の嗜好').classes('text-xs font-bold text-slate-400 dark:text-white/30 tracking-widest mb-2')
                        
                        if not p.is_editing:
                            liquors = db_liquor_types
                            if liquors:
                                with ui.row().classes('gap-1 flex-wrap mb-2'):
                                    for l in liquors:
                                        ui.label(l).classes('text-[10px] font-bold bg-amber-50 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300 px-2.5 py-0.5 rounded-full border border-amber-500/10')
                            else:
                                ui.label('好きなお酒は未登録です。').classes('text-xs text-slate-400 dark:text-white/30 italic mb-2')
                        else:
                            ui.label('好きなお酒 (最大10個まで)').classes('text-[10px] text-slate-400 dark:text-white/30 font-bold mb-1')
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
                            dark_prop = 'dark' if not is_light else ''
                            with ui.column().classes('w-full gap-2 mb-2'):
                                for parent, children in LIQUOR_CATEGORIES.items():
                                    with ui.expansion(parent).classes('w-full bg-slate-100 dark:bg-black/10 rounded-lg border border-slate-200 dark:border-white/5').props(f'dense {dark_prop}'):
                                        with ui.row().classes('w-full gap-2 p-2'):
                                            for l_name in children:
                                                e_state = p.edit_state
                                                is_selected = l_name in e_state['liquor_type']
                                                
                                                btn_classes = 'px-2.5 py-1 text-[10px] liquor-btn '
                                                if is_selected:
                                                    btn_classes += 'selected'
                                                
                                                btn = ui.button(l_name).props('flat rounded size=sm').classes(btn_classes)
                                                
                                                def make_toggle_handler(button, name):
                                                    def handler():
                                                        if name in e_state['liquor_type']:
                                                            e_state['liquor_type'].remove(name)
                                                            button.classes(remove='selected')
                                                        else:
                                                            if len(e_state['liquor_type']) >= 10:
                                                                ui.notify('登録できるお酒は10個までです！', type='warning', position='top')
                                                                return
                                                            e_state['liquor_type'].add(name)
                                                            button.classes(add='selected')
                                                        button.update()
                                                    return handler
                                                    
                                                btn.on('click', make_toggle_handler(btn, l_name))

                    if not p.is_editing:
                        render_field('local_bar', 'スタイル', 'drinking_style')
                    else:
                        e_state = p.edit_state
                        with ui.column().classes('w-full gap-1 py-1 border-b border-slate-100 dark:border-white/5'):
                            ui.label('飲み方スタイル').classes('text-[10px] text-slate-400 dark:text-white/30 font-bold')
                            ui.radio(
                                DRINKING_STYLES, 
                                value=e_state['drinking_style'] if e_state['drinking_style'] in DRINKING_STYLES else None, 
                                on_change=lambda e: e_state.update({'drinking_style': e.value})
                            ).props('inline').classes('w-full text-xs')

                    render_field('place', '出没エリア', 'drinking_area')
                    render_field('favorite_border', '好きな銘柄', 'favorite_brand')

                    with ui.card().classes('w-full p-4 hibi-glass rounded-2xl border border-slate-200 dark:border-white/5'):
                        ui.label('◆ おすすめ・行きつけの店').classes('text-xs font-bold text-slate-400 dark:text-white/30 tracking-widest mb-2')
                        
                        if not p.is_editing:
                            rec_bar = profile.get('recommended_bar')
                            if rec_bar:
                                with ui.row().classes('w-full bg-white dark:bg-slate-900/80 p-3 rounded-xl border border-slate-200 dark:border-white/5 items-center justify-between mt-1'):
                                    with ui.row().classes('items-center gap-2.5 overflow-hidden flex-grow'):
                                        ui.icon('local_pizza', color='amber-500', size='sm').classes('opacity-80')
                                        with ui.column().classes('gap-0.5 overflow-hidden flex-grow'):
                                            ui.label(rec_bar).classes('text-xs font-bold text-slate-800 dark:text-slate-100 truncate w-full')
                                            if profile.get('bar_url'):
                                                ui.link('店舗情報を食べログ等で開く ↗', profile.get('bar_url'), new_tab=True).classes('text-[10px] text-blue-500 dark:text-blue-400 font-bold hover:underline')
                                    if profile.get('bar_image_url'):
                                        ui.image(source=profile.get('bar_image_url')).classes('w-14 h-14 object-cover rounded-xl border border-slate-200 dark:border-white/5')
                            else:
                                ui.label('おすすめの店は未設定です。').classes('text-xs text-slate-400 dark:text-white/30 italic px-1')
                        else:
                            e_state = p.edit_state
                            with ui.column().classes('w-full gap-2 mt-1'):
                                with ui.row().classes('w-full gap-2 items-center'):
                                    ui.input(
                                        placeholder='店舗URL (食べログ等)', 
                                        value=e_state['bar_url'], 
                                        on_change=lambda e: e_state.update({'bar_url': e.value})
                                    ).classes('flex-grow text-xs').props('filled dense')
                                    
                                    async def magic_fetch():
                                        if not e_state['bar_url']:
                                            ui.notify('URLを入力してください', color='negative', position='top')
                                            return
                                        try:
                                            data = fetch_ogp_data(e_state['bar_url'])
                                            e_state['recommended_bar'] = data['title']
                                            e_state['bar_image_url'] = data['image']
                                            refresh_func()
                                            ui.notify('店舗情報を自動取得しました！', color='positive', position='top')
                                        except Exception as ex:
                                            ui.notify(f'店舗情報の取得に失敗しました: {ex}', color='negative', position='top')
                                            
                                    ui.button(icon='auto_awesome', on_click=magic_fetch).props('flat round color=orange dense').tooltip('URLから自動取得')
                                
                                ui.input(
                                    label='店名', 
                                    value=e_state['recommended_bar'], 
                                    on_change=lambda e: e_state.update({'recommended_bar': e.value})
                                ).classes('w-full text-xs').props('filled dense')
                                
                                if e_state['bar_image_url']:
                                    ui.image(source=e_state['bar_image_url']).classes('w-full h-32 object-cover rounded-xl mt-2')

            with ui.card().classes('w-full p-4 hibi-glass rounded-2xl border border-slate-200 dark:border-white/5'):
                ui.label('◆ よく一緒に飲むメンバー').classes('text-xs font-bold text-slate-400 dark:text-white/30 tracking-widest mb-3')
                
                if p.is_editing:
                    ui.label('編集中は表示されません。').classes('text-xs text-slate-400 dark:text-white/30 italic px-1')
                else:
                    from database.scoring_db import get_frequent_companions
                    companions = get_frequent_companions(target_id)
                    
                    if not companions:
                        ui.label('まだ一緒に飲んだデータがありません。').classes('text-xs text-slate-400 dark:text-white/30 italic px-1')
                    else:
                        with ui.row().classes('gap-4 flex-wrap items-start'):
                            for comp in companions:
                                with ui.column().classes('items-center gap-1'):
                                    ui.image(comp['avatar_url']).classes('w-12 h-12 rounded-full border-2 border-slate-300 dark:border-slate-700 shadow-md')
                                    ui.label(comp['name']).classes('text-[10px] font-bold text-slate-800 dark:text-slate-200 truncate w-14 text-center')
                                    ui.label(f"{comp['common_count']}回").classes('text-[9px] text-amber-600 dark:text-amber-400')

    with ui.column().classes('w-full flex-col pc-hidden gap-4 pb-20 members-view-container'):
        
        @ui.refreshable
        def render_mobile_view():
            filter_label = 'フィルター絞り込み 🔍'
            if p.is_filter_active:
                filter_label += ' (適用中)'
                filter_header_classes = 'w-full bg-amber-50/80 dark:bg-amber-950/20 border border-amber-300 dark:border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 font-bold shrink-0'
            else:
                filter_header_classes = 'w-full bg-slate-100 dark:bg-slate-900/40 border border-slate-200 dark:border-white/5 rounded-xl shrink-0'

            dark_prop = 'dark' if not is_light else ''
            
            with ui.expansion(filter_label, icon='tune').classes(filter_header_classes).props(f'dense {dark_prop}').bind_value(p, 'filter_expanded'):
                with ui.column().classes('w-full p-3 gap-3.5'):
                    ui.input('キーワード（名前、自己紹介、職業など）', value=p.filter_query, on_change=lambda e: [p.__setattr__('filter_query', e.value), render_mobile_view.refresh()]).props('dense filled clearable debounce=500').classes('w-full text-xs')

                    liquor_options = {'すべて': 'すべてのお酒'}
                    for parent, children in LIQUOR_CATEGORIES.items():
                        liquor_options[parent] = f"【ジャンル】{parent}"
                        for child in children: liquor_options[child] = f"　├ {child}"

                    ui.select(options=liquor_options, label='好きなお酒', value=p.filter_liquor, on_change=lambda e: [p.__setattr__('filter_liquor', e.value), render_mobile_view.refresh()]).props(f':dark="{dark_val}" dense filled options-dense').classes('w-full text-xs')
                    
                    style_options = {'すべて': 'すべてのスタイル'} | {s: s for s in DRINKING_STYLES}
                    ui.select(options=style_options, label='飲み方スタイル', value=p.filter_drinking_style, on_change=lambda e: [p.__setattr__('filter_drinking_style', e.value), render_mobile_view.refresh()]).props(f':dark="{dark_val}" dense filled options-dense').classes('w-full text-xs')
                    ui.input('よく飲むエリア (部分一致)', value=p.filter_drinking_area, on_change=lambda e: [p.__setattr__('filter_drinking_area', e.value), render_mobile_view.refresh()]).props('dense filled clearable debounce=500').classes('w-full text-xs')

                    if p.is_filter_active:
                        ui.button('フィルターをクリア ↩', on_click=lambda: [p.reset_filters(), render_mobile_view.refresh()]).props('flat dense color=red size=sm').classes('w-full font-bold mt-1')

            with ui.row().classes('w-full justify-between items-center mb-2 px-1 border-b border-slate-200 dark:border-white/5 pb-2 shrink-0'):
                ui.label('メンバー一覧').classes('text-sm text-slate-800 dark:text-slate-100 font-bold')
                with ui.row().classes('items-center gap-1.5'):
                    ui.icon('sort', size='xs').classes('text-slate-500 dark:text-white/50')
                    sort_select = ui.select(options=sort_options, value=p.sort_by, on_change=lambda e: [p.__setattr__('sort_by', e.value), render_mobile_view.refresh()])
                    sort_select.props(f':dark="{dark_val}" dense options-dense borderless size=sm').classes('text-xs font-bold text-slate-800 dark:text-slate-100')

            parsed_members = p.get_sorted_members()
            if not parsed_members:
                with ui.column().classes('w-full items-center p-6 text-slate-400 dark:text-white/30 gap-2 border border-dashed border-slate-200 dark:border-white/5 rounded-xl'):
                    ui.icon('search_off', size='md').classes('opacity-50')
                    ui.label('条件に該当するゲストが見つかりません。').classes('text-xs')
            else:
                for mem, parents in parsed_members[:p.display_limit]:
                    target_id = mem.get('id')
                    target_role = str(mem.get('role', 'member')).lower()
                    show_badge_permission = is_current_admin or (target_role in ADMIN_ROLES)

                    with ui.card().classes('w-full hibi-glass rounded-xl p-3 border-slate-200 dark:border-white/5 bg-white/90 dark:bg-slate-900/60 flex-row items-center gap-3 shadow-lg'):
                        draw_user_avatar(
                            avatar_url=mem.get('avatar_url'), name=mem.get('name'), user_id=target_id, role=mem.get('role'),
                            size_class='w-14 h-14 shrink-0', show_online_badge=show_badge_permission, border_class='border-slate-300 dark:border-slate-800'
                        )
                        
                        with ui.column().classes('gap-1 flex-grow min-w-0 justify-center'):
                            with ui.row().classes('w-full items-center gap-1.5 no-wrap'):
                                ui.label(mem.get('name', '名無し')).classes('text-sm font-bold text-slate-800 dark:text-slate-100 truncate max-w-[120px]')
                                if mem.get('drinking_area'):
                                    ui.label(f"📍{mem.get('drinking_area')}").classes('text-[10px] text-slate-400 dark:text-white/50 truncate')
                                
                                is_target_admin = target_role in ADMIN_ROLES
                                if is_target_admin:
                                    ui.label('運営').classes('text-[9px] font-black bg-cyan-100 dark:bg-cyan-950/60 text-cyan-800 dark:text-cyan-400 px-1.5 py-0.5 rounded border border-cyan-300 dark:border-cyan-500/30 shrink-0')
                                
                                # ★ スコア(ポイント)表示を削除、LV表示のみに統一
                                score = mem.get('total_score') or 0
                                is_target_su = str(mem.get('role', 'member')).lower() in ADMIN_ROLES

                                if is_target_su:
                                    ui.label("✨ LV: ??").classes('text-[10px] font-bold text-purple-500 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/30 px-1.5 py-0.5 rounded border border-purple-200 dark:border-purple-500/30 shrink-0')
                                else:
                                    lv_str = calculate_user_level(score)
                                    ui.label(f"✨ {lv_str}").classes('text-[10px] font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-1.5 py-0.5 rounded border border-amber-200 dark:border-amber-500/30 shrink-0')
                            
                            if parents:
                                with ui.row().classes('gap-1.5 flex-wrap mt-0.5 items-center'):
                                    for p_name in parents:
                                        emoji = p_name[0] if p_name else ''
                                        if is_light:
                                            box_classes = 'relative p-2 bg-white border border-slate-200 shadow-xl rounded-xl z-50 whitespace-nowrap'
                                            arrow_bg = 'bg-white border-t border-l border-slate-200'
                                            label_style = 'color: #1e293b !important; font-size: 11px; font-weight: 800; line-height: 1;'
                                        else:
                                            box_classes = 'relative p-2 bg-slate-900 border border-white/10 shadow-xl rounded-xl z-50 whitespace-nowrap'
                                            arrow_bg = 'bg-slate-900 border-t border-l border-white/10'
                                            label_style = 'color: #22d3ee !important; font-size: 11px; font-weight: 900; letter-spacing: 0.05em; line-height: 1;'

                                        with ui.element('div').classes('relative inline-block cursor-pointer'):
                                            ui.label(emoji).classes('text-sm hover:scale-125 transition-transform duration-100 px-0.5')
                                            
                                            with ui.menu().props('anchor="bottom middle" self="top middle" :offset="[0, 4]"').classes('p-0 min-w-0 overflow-visible').style('background: transparent !important; box-shadow: none !important; border: none !important;'):
                                                with ui.element('div').classes('pt-1.5'):
                                                    with ui.element('div').classes(box_classes):
                                                        ui.element('div').classes(f'absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 rotate-45 {arrow_bg} z-40')
                                                        ui.label(p_name).style(label_style).classes('z-50 relative')

                        def make_mobile_click(m_id):
                            def click_handler():
                                p.selected_id = m_id
                                p.is_editing = False
                                with ui.dialog().classes('w-full h-full m-0 p-0').props('maximized transition-show="slide-left" transition-hide="slide-right"') as dialog:
                                    with ui.card().classes('w-full h-full m-0 p-0 bg-slate-100 dark:bg-[#0f172a] rounded-none overflow-hidden flex flex-col no-wrap'):
                                        @ui.refreshable
                                        def render_dialog_content():
                                            with ui.column().classes('w-full flex-grow overflow-y-auto hide-scrollbar p-2 sm:p-4 pb-20'):
                                                draw_detail(p.selected_id, refresh_func=render_dialog_content.refresh, close_dialog=dialog.close)
                                        render_dialog_content()
                                dialog.open()
                            return click_handler

                        ui.button(icon='chevron_right', on_click=make_mobile_click(target_id)).props('flat round color=grey-6 size=md').classes('shrink-0 ml-auto')

            if len(parsed_members) > p.display_limit:
                ui.button('もっとメンバーを見る ▽', on_click=lambda: [p.__setattr__('display_limit', p.display_limit + 30), render_mobile_view.refresh()]).props('flat color=grey size=sm').classes('w-full text-xs py-2 mt-2')

        render_mobile_view()


    with ui.row().classes('mobile-hidden w-full items-start no-wrap gap-6 members-view-container'):
        
        with ui.element('div').classes('w-[320px] lg:w-[360px] shrink-0 sticky top-4 z-20'):
            @ui.refreshable
            def render_pc_left_pane():
                with ui.column().classes('w-full flex-col gap-3 h-[calc(100vh-100px)]'):
                    
                    filter_label = 'フィルター絞り込み 🔍'
                    if p.is_filter_active:
                        filter_label += ' (適用中)'
                        filter_header_classes = 'w-full bg-amber-50/80 dark:bg-amber-950/20 border border-amber-300 dark:border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 font-bold shrink-0'
                    else:
                        filter_header_classes = 'w-full bg-slate-100 dark:bg-slate-900/40 border border-slate-200 dark:border-white/5 rounded-xl shrink-0'

                    dark_prop = 'dark' if not is_light else ''
                    
                    with ui.expansion(filter_label, icon='tune').classes(filter_header_classes).props(f'dense {dark_prop}').bind_value(p, 'filter_expanded'):
                        with ui.column().classes('w-full p-3 gap-3.5'):
                            ui.input('キーワード（名前、自己紹介、職業など）', value=p.filter_query, on_change=lambda e: [p.__setattr__('filter_query', e.value), render_pc_left_pane.refresh()]).props('dense filled clearable debounce=500').classes('w-full text-xs')

                            liquor_options = {'すべて': 'すべてのお酒'}
                            for parent, children in LIQUOR_CATEGORIES.items():
                                liquor_options[parent] = f"【ジャンル】{parent}"
                                for child in children: liquor_options[child] = f"　├ {child}"

                            ui.select(options=liquor_options, label='好きなお酒', value=p.filter_liquor, on_change=lambda e: [p.__setattr__('filter_liquor', e.value), render_pc_left_pane.refresh()]).props(f':dark="{dark_val}" dense filled options-dense').classes('w-full text-xs')
                            
                            style_options = {'すべて': 'すべてのスタイル'} | {s: s for s in DRINKING_STYLES}
                            ui.select(options=style_options, label='飲み方スタイル', value=p.filter_drinking_style, on_change=lambda e: [p.__setattr__('filter_drinking_style', e.value), render_pc_left_pane.refresh()]).props(f':dark="{dark_val}" dense filled options-dense').classes('w-full text-xs')
                            ui.input('よく飲むエリア (部分一致)', value=p.filter_drinking_area, on_change=lambda e: [p.__setattr__('filter_drinking_area', e.value), render_pc_left_pane.refresh()]).props('dense filled clearable debounce=500').classes('w-full text-xs')

                            if p.is_filter_active:
                                ui.button('フィルターをクリア ↩', on_click=lambda: [p.reset_filters(), render_pc_left_pane.refresh()]).props('flat dense color=red size=sm').classes('w-full font-bold mt-1')

                    with ui.row().classes('w-full justify-between items-center mb-2 px-1 border-b border-slate-200 dark:border-white/5 pb-2 shrink-0'):
                        ui.label('メンバー一覧').classes('text-sm text-slate-800 dark:text-slate-100 font-bold')
                        with ui.row().classes('items-center gap-1.5'):
                            ui.icon('sort', size='xs').classes('text-slate-500 dark:text-white/50')
                            sort_select = ui.select(options=sort_options, value=p.sort_by, on_change=lambda e: [p.__setattr__('sort_by', e.value), render_pc_left_pane.refresh()])
                            sort_select.props(f':dark="{dark_val}" dense options-dense borderless size=sm').classes('text-xs font-bold text-slate-800 dark:text-slate-100')

                    parsed_members = p.get_sorted_members()

                    user_cards = {}
                    active_card_classes = 'border-amber-500/40 dark:border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20 shadow-[0_0_15px_rgba(245,158,11,0.08)]'
                    inactive_card_classes = 'border-slate-200 dark:border-white/5 bg-white/90 dark:bg-slate-900/60'

                    with ui.column().classes('w-full gap-2 flex-grow min-h-0 overflow-y-auto hide-scrollbar pb-6 pr-1'):
                        if not parsed_members:
                            with ui.column().classes('w-full items-center p-6 text-slate-400 dark:text-white/30 gap-2 border border-dashed border-slate-200 dark:border-white/5 rounded-xl'):
                                ui.icon('search_off', size='md').classes('opacity-50')
                                ui.label('条件に該当するゲストが見つかりません。').classes('text-xs')
                        else:
                            for mem, parents in parsed_members[:p.display_limit]:
                                target_id = mem.get('id')
                                target_role = str(mem.get('role', 'member')).lower()
                                show_badge_permission = is_current_admin or (target_role in ADMIN_ROLES)

                                is_selected = (target_id == p.selected_id)
                                initial_classes = active_card_classes if is_selected else inactive_card_classes

                                with ui.card().classes(f'w-full hibi-glass rounded-xl p-3 hover:bg-slate-50 dark:hover:bg-white/5 transition flex-row items-center gap-3 shadow-lg {initial_classes}') as user_card:
                                    user_cards[target_id] = user_card
                                    
                                    draw_user_avatar(
                                        avatar_url=mem.get('avatar_url'), name=mem.get('name'), user_id=target_id, role=mem.get('role'),
                                        size_class='w-14 h-14 shrink-0', show_online_badge=show_badge_permission, border_class='border-slate-300 dark:border-slate-800'
                                    )
                                    
                                    with ui.column().classes('gap-1 flex-grow min-w-0 justify-center'):
                                        with ui.row().classes('w-full items-center gap-1.5 no-wrap'):
                                            ui.label(mem.get('name', '名無し')).classes('text-sm font-bold text-slate-800 dark:text-slate-100 truncate max-w-[120px]')
                                            if mem.get('drinking_area'):
                                                ui.label(f"📍{mem.get('drinking_area')}").classes('text-[10px] text-slate-400 dark:text-white/50 truncate')
                                            
                                            is_target_admin = target_role in ADMIN_ROLES
                                            if is_target_admin:
                                                ui.label('運営').classes('text-[9px] font-black bg-cyan-100 dark:bg-cyan-950/60 text-cyan-800 dark:text-cyan-400 px-1.5 py-0.5 rounded border border-cyan-300 dark:border-cyan-500/30 shrink-0')
                                            
                                            # ★ スコア(ポイント)表示を削除、LV表示のみに統一
                                            score = mem.get('total_score') or 0
                                            is_target_su = str(mem.get('role', 'member')).lower() in ADMIN_ROLES

                                            if is_target_su:
                                                ui.label("✨ LV: ??").classes('text-[10px] font-bold text-purple-500 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/30 px-1.5 py-0.5 rounded border border-purple-200 dark:border-purple-500/30 shrink-0')
                                            else:
                                                lv_str = calculate_user_level(score)
                                                ui.label(f"✨ {lv_str}").classes('text-[10px] font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-1.5 py-0.5 rounded border border-amber-200 dark:border-amber-500/30 shrink-0')
                                                
                                        if parents:
                                            with ui.row().classes('gap-1.5 flex-wrap mt-0.5 items-center'):
                                                for p_name in parents:
                                                    emoji = p_name[0] if p_name else ''
                                                    if is_light:
                                                        box_classes = 'relative p-2 bg-white border border-slate-200 shadow-xl rounded-xl z-50 whitespace-nowrap'
                                                        arrow_bg = 'bg-white border-t border-l border-slate-200'
                                                        label_style = 'color: #1e293b !important; font-size: 11px; font-weight: 800; line-height: 1;'
                                                    else:
                                                        box_classes = 'relative p-2 bg-slate-900 border border-white/10 shadow-xl rounded-xl z-50 whitespace-nowrap'
                                                        arrow_bg = 'bg-slate-900 border-t border-l border-white/10'
                                                        label_style = 'color: #22d3ee !important; font-size: 11px; font-weight: 900; letter-spacing: 0.05em; line-height: 1;'

                                                    with ui.element('div').classes('relative inline-block cursor-pointer'):
                                                        ui.label(emoji).classes('text-sm hover:scale-125 transition-transform duration-100 px-0.5')
                                                        
                                                        with ui.menu().props('anchor="bottom middle" self="top middle" :offset="[0, 4]"').classes('p-0 min-w-0 overflow-visible').style('background: transparent !important; box-shadow: none !important; border: none !important;'):
                                                            with ui.element('div').classes('pt-1.5'):
                                                                with ui.element('div').classes(box_classes):
                                                                    ui.element('div').classes(f'absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 rotate-45 {arrow_bg} z-40')
                                                                    ui.label(p_name).style(label_style).classes('z-50 relative')

                                    def make_pc_click(m_id):
                                        def click_handler():
                                            if p.selected_id in user_cards:
                                                user_cards[p.selected_id].classes(remove=active_card_classes, add=inactive_card_classes)
                                            if m_id in user_cards:
                                                user_cards[m_id].classes(remove=inactive_card_classes, add=active_card_classes)
                                            p.selected_id = m_id
                                            p.is_editing = False
                                            render_pc_right_pane.refresh()
                                        return click_handler

                                    ui.button(icon='chevron_right', on_click=make_pc_click(target_id)).props('flat round color=grey-6 size=md').classes('shrink-0 ml-auto').tooltip('詳細を見る')

                        if len(parsed_members) > p.display_limit:
                            ui.button('もっとメンバーを見る ▽', on_click=lambda: [p.__setattr__('display_limit', p.display_limit + 30), render_pc_left_pane.refresh()]).props('flat color=grey size=sm').classes('w-full text-xs py-2 mt-2')

            render_pc_left_pane()

        with ui.column().classes('flex-grow p-0 w-full min-w-0'):
            @ui.refreshable
            def render_pc_right_pane():
                target_id = p.selected_id or current_user_id
                draw_detail(target_id, refresh_func=render_pc_right_pane.refresh)
            
            render_pc_right_pane()