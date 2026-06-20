# components/su_dashboard_presence.py
from nicegui import ui
from database.profile_db import get_all_profiles, is_user_online
from components.avatar import draw_user_avatar

# ★統一規格：モジュールレベルで状態を保持
presence_state = {'active': 'online'}

def build_presence_ui(refresh_presence_cb):
    """
    稼働状態（オンライン/オフライン）のUIを生成する外部コンポーネント (ボタン切り替え統一版)
    """
    with ui.card().classes('w-full h-[450px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-green-500 flex flex-col gap-2 overflow-hidden'):
        with ui.row().classes('w-full justify-between items-center m-0 shrink-0'):
            ui.label('🟢 稼働状態').classes('font-bold text-green-400')
            ui.button(icon='refresh', on_click=refresh_presence_cb).props('flat round dense color=green-400 size=sm').tooltip('最新に更新')
        
        try:
            all_users = get_all_profiles()  # 承認待ちを除く全プロフィール
        except Exception as e:
            print(f"稼働状態一覧取得エラー: {e}")
            ui.label('通信が混み合っています...').classes('text-white/50 text-xs p-2')
            return

        online_list = []
        offline_list = []

        for u in all_users:
            u_id = str(u.get('id', ''))
            if is_user_online(u_id):
                online_list.append(u)
            else:
                offline_list.append(u)

        # --- ★統一規格：シンプルなボタンによる切り替えUI ---
        # ★ 変更: bg-slate-900/30 border border-white/5 をカスタムクラス「hibi-tab-row」に差し替え
        with ui.row().classes('w-full hibi-tab-row rounded-lg p-1 mb-1 border shrink-0 gap-2 justify-stretch'):
            is_online = (presence_state['active'] == 'online')
            
            # ★ 変更: 非アクティブ時のカラープロパティを "white" にし、クラスに 「hibi-tab-btn-inactive」を付与します
            on_color = 'primary' if is_online else 'white'
            ui.button(f'🟢 オンライン ({len(online_list)})', on_click=lambda: (presence_state.update(active='online'), refresh_presence_cb())) \
                .props(f'flat color={on_color} size=sm')\
                .classes('flex-grow font-bold text-[10px]' + ('' if is_online else ' hibi-tab-btn-inactive'))
                
            off_color = 'white' if is_online else 'primary'
            ui.button(f'⚪ オフライン ({len(offline_list)})', on_click=lambda: (presence_state.update(active='offline'), refresh_presence_cb())) \
                .props(f'flat color={off_color} size=sm')\
                .classes('flex-grow font-bold text-[10px]' + ('' if not is_online else ' hibi-tab-btn-inactive'))


        # --- 【オンライン 領域】 ---
        if presence_state['active'] == 'online':
            if not online_list:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('オンラインのユーザーはいません').classes('text-[10px] text-white/30 italic text-center w-full block')
            else:
                with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg mt-1'):
                    with ui.column().classes('w-full gap-2 pb-4'):
                        for u in online_list:
                            u_name = u.get('name') or "名無し"
                            with ui.row().classes('items-center gap-2 px-2.5 py-1.5 bg-black/35 rounded-lg border border-green-500/10 no-wrap w-full shrink-0'):
                                draw_user_avatar(
                                    avatar_url=u.get('avatar_url'),
                                    name=u_name,
                                    user_id=u.get('id'),
                                    role=u.get('role'),
                                    size_class='w-6 h-6',
                                    show_online_badge=True,
                                    border_class='border-green-500/30'
                                )
                                ui.label(u_name).classes('text-xs font-bold text-white truncate flex-grow')

        # --- 【オフライン 領域】 ---
        else:
            if not offline_list:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('オフラインのユーザーはいません').classes('text-[10px] text-white/30 italic text-center w-full block')
            else:
                with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg mt-1'):
                    with ui.column().classes('w-full gap-2 pb-4'):
                        for u in offline_list:
                            u_name = u.get('name') or "名無し"
                            with ui.row().classes('items-center gap-2 px-2.5 py-1.5 bg-black/15 rounded-lg border border-white/5 no-wrap w-full opacity-70 shrink-0'):
                                draw_user_avatar(
                                    avatar_url=u.get('avatar_url'),
                                    name=u_name,
                                    user_id=u.get('id'),
                                    role=u.get('role'),
                                    size_class='w-6 h-6',
                                    show_online_badge=True,
                                    border_class='border-white/10'
                                )
                                ui.label(u_name).classes('text-xs text-white/70 truncate flex-grow')