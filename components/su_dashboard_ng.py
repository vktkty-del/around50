# components/su_dashboard_ng.py
from nicegui import ui, app
from datetime import datetime, timezone, timedelta
from database.timeline_db import delete_post
from components.su_dashboard_logic import get_avatar_url

# ★修正: DB関数のインポートに履歴用の2つを追加
from database.su_db import fetch_pending_posts, approve_post, create_notification, fetch_ng_history_logs, insert_ng_history_log

ng_state = {'active': 'pending'}

def format_history_time(dt_str):
    """UTCのISO文字列をJSTの MM/DD HH:MM 形式に変換"""
    if not dt_str: return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        dt_jst = dt.astimezone(timezone(timedelta(hours=9)))
        return dt_jst.strftime('%m/%d %H:%M')
    except:
        return dt_str

def build_ng_ui(dummy_history, refresh_ng_cb, refresh_kpi_cb):

    # ★ 以下のテーマ取得とスタイル定義を追加します
    from themes import THEMES
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)

    tab_bg = 'bg-slate-150 border-slate-200' if is_light else 'bg-slate-900/30 border-white/5'
    inactive_color = 'grey-6' if is_light else 'white/50'
    """
    NG審議のカードUIを生成する外部コンポーネント (DB永続化・共有対応版)
    """
    try:
        # ★修正: 審議待ちリストと、履歴リストの両方を「データベースから」取得する
        posts = fetch_pending_posts()
        history_records = fetch_ng_history_logs()
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        with ui.card().classes('w-full h-[430px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-red-500/50 flex flex-col overflow-hidden'):
            ui.label('🚨 NG審議').classes('font-bold text-red-400 mb-2 shrink-0')
            ui.label('通信が混み合っています...').classes('text-white/50 text-xs p-2')
        return

    with ui.card().classes('w-full h-[430px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-red-500/50 flex flex-col overflow-hidden'):
        ui.label('🚨 NG審議').classes('font-bold text-red-400 mb-2 shrink-0')
        
        # ★ bg-slate-900/30 などのクラスを廃止し、カスタムクラス「hibi-tab-row」に差し替え
        with ui.row().classes('w-full hibi-tab-row rounded-lg p-1 mb-2.5 border shrink-0 gap-2 justify-stretch'):
            is_pending = (ng_state['active'] == 'pending')
            
            # ★ 非アクティブ時は、固定で "white" ＋ 「hibi-tab-btn-inactive」クラスを適用
            pending_color = 'primary' if is_pending else 'white'
            ui.button('審議待ち', on_click=lambda: (ng_state.update(active='pending'), refresh_ng_cb())) \
                .props(f'flat color={pending_color} size=sm')\
                .classes('flex-grow font-bold text-xs' + ('' if is_pending else ' hibi-tab-btn-inactive'))
                
            history_color = 'white' if is_pending else 'primary'
            ui.button('直近の履歴', on_click=lambda: (ng_state.update(active='history'), refresh_ng_cb())) \
                .props(f'flat color={history_color} size=sm')\
                .classes('flex-grow font-bold text-xs' + ('' if not is_pending else ' hibi-tab-btn-inactive'))
            
        # --- 【審議待ち 領域】 ---
        if ng_state['active'] == 'pending':
            if not posts:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('現在、審議待ちの投稿はありません。').classes('text-white/50 text-xs text-center w-full')
            else:
                with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg'):
                    with ui.column().classes('w-full gap-3 pb-4'):
                        for idx, post in enumerate(posts):
                            with ui.column().classes('w-full bg-slate-900/40 rounded-xl p-4 border border-white/5 shrink-0 min-h-[160px] gap-2'):
                                profile = post.get('profiles', {}) or {}
                                user_name = profile.get('name', '名無し')
                                post_title = post.get('title') or "無題の投稿"
                                avatar_url = get_avatar_url(profile.get('avatar_url'), user_name)
                                
                                with ui.row().classes('w-full items-center gap-2 m-0 pb-1 border-b border-white/5 no-wrap'):
                                    ui.image(avatar_url).classes('w-5 h-5 rounded-full border border-white/10 shrink-0')
                                    ui.label(user_name).classes('text-[11px] font-bold text-amber-300/80 truncate max-w-[180px]')
                                    ui.space()
                                    ui.label('審議中').classes('text-[9px] bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded border border-red-500/20 shrink-0')
                                
                                ui.label(post_title).classes('font-bold text-slate-100 text-sm truncate w-full mt-0.5 pl-0.5')
                                
                                full_content = post.get('content', '')
                                ng_word = post.get('highlighted_content', '')
                                
                                if ng_word and ng_word in full_content:
                                    highlight_tag = f'<span class="bg-red-500/25 text-red-300 px-1 py-0.5 rounded border border-red-500/30 font-bold mx-0.5">{ng_word}</span>'
                                    content_html = full_content.replace(ng_word, highlight_tag)
                                else:
                                    content_html = full_content if full_content else (ng_word if ng_word else "本文なし")
                                
                                ui.html(content_html).classes('text-xs text-slate-300 bg-black/15 p-3 rounded-xl w-full break-all border border-white/5 leading-relaxed')
                                
                                with ui.row().classes('w-full justify-end mt-1 m-0 gap-2'):
                                    
                                    # ★修正: リストの append をやめて、insert_ng_history_log で直接DBに書き込む
                                    def make_reject_cb(pid=post.get('id'), uid=post.get('user_id'), u_name=user_name, av_url=avatar_url, title=post_title, content=content_html):
                                        return lambda: (
                                            delete_post(pid),
                                            create_notification(uid, "system_alert", f"【投稿否認のお知らせ】\nあなたの投稿「{title}」は、コミュニティガイドラインに抵触する可能性があったため、運営により取り下げられました。") if uid else None,
                                            insert_ng_history_log(uid, u_name, av_url, title, content, '否認'),
                                            refresh_ng_cb(),
                                            refresh_kpi_cb(),
                                            ui.notify(f'{u_name} さんの投稿を否認し、通知を送りました', type='warning')
                                        )
                                    
                                    def make_approve_cb(pid=post.get('id'), uid=post.get('user_id'), u_name=user_name, av_url=avatar_url, title=post_title, content=content_html):
                                        return lambda: (
                                            approve_post(pid),
                                            insert_ng_history_log(uid, u_name, av_url, title, content, '承認'),
                                            refresh_ng_cb(),
                                            refresh_kpi_cb(),
                                            ui.notify(f'{u_name} さんの投稿を承認しました', type='positive')
                                        )
                                    
                                    ui.button('否認', on_click=make_reject_cb()).classes('bg-red-700/80 hover:bg-red-600 text-white font-bold py-1 px-3 text-[10px] rounded-lg shadow')
                                    ui.button('承認', on_click=make_approve_cb()).classes('bg-green-700/80 hover:bg-green-600 text-white font-bold py-1 px-3 text-[10px] rounded-lg shadow')

        # --- 【直近の履歴 領域】 ---
        else:
            if not history_records:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('最近の審議結果はありません。').classes('text-white/50 text-xs text-center w-full')
            else:
                with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg'):
                    with ui.column().classes('w-full gap-3 pb-4'):
                        # ★修正: DBから取得した最新の履歴(history_records)を展開
                        for h in history_records:
                            action_color = 'text-green-400/80' if h.get('action') == '承認' else 'text-red-400/80'
                            with ui.column().classes("w-full rounded-xl p-3 bg-slate-900/30 border border-white/5 shrink-0 min-h-[120px] gap-1.5"):
                                
                                with ui.row().classes('w-full items-center gap-2 m-0 pb-1 border-b border-white/5 no-wrap'):
                                    h_avatar = h.get('avatar_url') or get_avatar_url(None, h.get('user_name', '名無し'))
                                    ui.image(h_avatar).classes('w-5 h-5 rounded-full border border-white/10 shrink-0')
                                    ui.label(h.get('user_name', '名無し')).classes('text-[11px] text-slate-400 truncate max-w-[150px]')
                                    ui.space()
                                    
                                    # ★修正: UTCのタイムスタンプをJSTの分かりやすい時間に変換して表示
                                    time_str = format_history_time(h.get('created_at'))
                                    ui.label(f"{time_str} に {h.get('action', '処理')}済").classes(f'text-[9px] font-bold {action_color} shrink-0')
                                
                                ui.label(h.get('title') or '無題の投稿').classes('font-bold text-slate-300 text-xs truncate w-full pl-0.5 mt-0.5')
                                ui.html(h.get('content', '')).classes('text-xs text-slate-400 bg-black/10 p-2.5 rounded-xl w-full')