# components/event_card.py
from nicegui import ui

from components.avatar import draw_user_avatar
from components.event_dialogs import handle_soft_delete_with_cb, is_event_past
from database.event_db import restore_event, fetch_event_reviews
from utils.calendar_utils import get_user_calendar_state

def draw_event_card(ev, current_user_id: str, is_su: bool, enter_chat_cb, refresh_all_cb, open_detail_cb, open_edit_cb):
    """
    公式イベントのカード型UIを1件分描画するコンポーネント
    """
    host = ev.get('profiles') or {}
    host_name = host.get('name', '名無し')
    is_deleted = ev.get('deleted_at') is not None
    is_past = is_event_past(ev.get('event_date'))
    is_host = str(ev.get('created_by')) == str(current_user_id)
    
    # ★ 改善: カード全体への opacity-50 をやめてボタンの視認性を確保
    card_classes = 'w-full hibi-glass rounded-xl shadow-2xl overflow-hidden border-t-4 border-indigo-500 flex flex-col'
    if is_deleted or is_past:
        card_classes += ' bg-slate-950/20'

    client_st = get_user_calendar_state()

    # ★ 追加: レビューを事前に1回だけ取得し、評価平均と投稿済みフラグを判定
    reviews = fetch_event_reviews(ev['id'])
    has_posted = any(str(r.get('user_id')) == str(current_user_id) for r in reviews)

    with ui.card().classes(card_classes).style('padding: 0px !important; gap: 0px !important;'):
        default_no_image = 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=500&auto=format&fit=crop&q=60'
        img_src = ev.get('image_url') or default_no_image
        
        # ★ 改善: 終了イベントの画像部分のみ不透明度を下げて「終了感」を演出
        img_classes = 'w-full h-32 object-cover shrink-0'
        if is_deleted or is_past:
            img_classes += ' opacity-40'
        ui.image(img_src).classes(img_classes).props('no-transition no-spinner')
        
        # ★ 改善: 終了イベントの情報エリアのみ不透明度を適用 (ボタンのある下部エリアは鮮明なまま)
        info_opacity = 'opacity-60' if (is_deleted or is_past) else 'opacity-100'
        
        with ui.column().classes('w-full p-3 gap-2 flex-grow justify-between'):
            # ヘッダーエリア
            with ui.row().classes('w-full justify-between items-center no-wrap gap-2'):
                with ui.row().classes(f'items-center gap-1.5 overflow-hidden flex-grow {info_opacity}'):
                    ui.label(ev.get('title', 'イベント')).classes('text-sm font-bold text-slate-800 dark:text-white truncate')
                
                with ui.row().classes('items-center gap-1 shrink-0 no-wrap'):
                    # ★ 改善: 終了したイベントに獲得した星の平均を表示
                    if reviews:
                        avg_rating = sum(r.get('rating', 0) for r in reviews) / len(reviews)
                        with ui.row().classes('items-center gap-0.5 shrink-0 bg-amber-500/10 border border-amber-500/25 px-1.5 py-0.5 rounded'):
                            ui.icon('star', size='11px', color='amber')
                            ui.label(f"{avg_rating:.1f}").classes('text-[9px] font-black text-amber-500')
                            ui.label(f"({len(reviews)})").classes('text-[8px] text-slate-400 dark:text-white/40 font-medium')

                    if is_deleted:
                        ui.badge('削除猶予中', color='red-600').classes('text-[8px] px-1 py-0.5 shrink-0')
                    elif is_past:
                        ui.badge('終了', color='slate-600').classes('text-[8px] px-1 py-0.5 shrink-0')
                    
                    ui.badge(ev.get('genre', '飲み会'), color='indigo-500').classes('text-[8px] px-1.5 py-0.5 shrink-0')

            # 主催者情報
            with ui.row().classes(f'items-center gap-1.5 {info_opacity}'):
                draw_user_avatar(
                    avatar_url=host.get('avatar_url'),
                    name=host_name,
                    user_id=host.get('id') or ev.get('created_by'),
                    role=host.get('role'),
                    size_class='w-4 h-4',
                    show_online_badge=True,
                    border_class='border-slate-800'
                )
                ui.label(f"主催: {host_name}").classes('text-[10px] text-slate-600 dark:text-white/60 truncate')

            # 日時・場所
            with ui.column().classes(f'w-full gap-1 text-[11px] text-slate-700 dark:text-white/80 {info_opacity}'):
                with ui.row().classes('items-center gap-1 no-wrap'):
                    ui.icon('calendar_today', size='12px', color='indigo-300')
                    ui.label(ev.get('event_date', '日時未定')).classes('truncate')
                with ui.row().classes('items-center gap-1 no-wrap'):
                    ui.icon('place', size='12px', color='indigo-300')
                    ui.label(ev.get('location', '場所未定')).classes('truncate')

            # 詳細・紹介
            if ev.get('description'):
                ui.label(ev.get('description')).classes(f'text-[10px] text-slate-500 dark:text-slate-400 bg-black/5 dark:bg-black/10 p-2 rounded-lg w-full whitespace-pre-wrap break-words line-clamp-3 {info_opacity}')

            # 下部ボタンアクション領域 (不透明度100%を維持して評価や詳細ボタンを非常に目立たせる)
            with ui.row().classes('w-full justify-between items-center mt-1 pt-1 border-t border-white/5 gap-1 opacity-100'):
                p_count = ev.get('participants_count', 1)
                ui.label(f"参加: {p_count}人").classes('text-[10px] text-indigo-500 dark:text-indigo-300 font-bold')
                
                with ui.row().classes('gap-1 shrink-0'):
                    if (is_su or is_host) and not is_past:
                        if is_deleted:
                            ui.button(icon='restore', on_click=lambda: (restore_event(ev['id']), ui.notify('イベントを復活させました！', color='positive', position='top'), refresh_all_cb())).props('flat size=xs color=green').classes('px-1 min-h-0').tooltip('復活')
                        else:
                            ui.button(icon='edit', on_click=lambda r=ev: open_edit_cb(r)).props('flat size=xs color=cyan').classes('px-1 min-h-0').tooltip('編集')
                            ui.button(icon='delete', on_click=lambda: handle_soft_delete_with_cb(ev['id'], refresh_all_cb)).props('flat size=xs color=red').classes('px-1 min-h-0').tooltip('削除')
                    
                    chat_room_id = ev.get('details')
                    if chat_room_id and enter_chat_cb and not is_deleted and not is_past:
                        ui.button(icon='forum', on_click=lambda r=chat_room_id: enter_chat_cb(r)).props('flat size=xs color=amber').classes('px-1 min-h-0 animate-pulse').tooltip('会議室')
                    
                    # ★ 改善: 未評価ならTeal塗りつぶし、評価済みならグレーのアウトライン+チェックマーク
                    if not is_deleted and is_past:
                        if not has_posted:
                            ui.button('評価', on_click=lambda: (setattr(client_st, 'review_event', ev), refresh_all_cb())).classes('bg-teal-600 hover:bg-teal-500 text-white text-[10px] px-2.5 py-1 rounded font-bold shadow-md')
                        else:
                            ui.button('評価済み', icon='check', on_click=lambda: (setattr(client_st, 'review_event', ev), refresh_all_cb())).props('outline color=grey').classes('text-[10px] px-2 py-1 rounded font-bold')

                    if not is_deleted:
                        ui.button('詳細', on_click=lambda r=ev: open_detail_cb(r)).classes('bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] px-2.5 py-1 rounded font-bold')