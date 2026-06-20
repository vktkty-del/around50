# components/shop_portal_ui.py

from nicegui import ui
from database.event_db import supabase, fetch_shop_portal_data, submit_event_request

def draw_shop_portal(current_user_id: str):
    """3カラム構成(スマホはテキスト切替)のお店ポータル画面を描画する"""
    
    # 1. DBからデータを一括取得
    data = fetch_shop_portal_data()
    all_shops = data.get("shops", [])
    events = data.get("events", [])
    reviews = data.get("reviews", [])
    requests = data.get("requests", [])
    
    # プロフィールから「おすすめバー」を登録しているメンバーを取得
    try:
        prof_res = supabase.table("profiles").select(
            "id, name, avatar_url, recommended_bar, bar_url, bar_image_url"
        ).not_.is_("recommended_bar", "null").execute()
        recommended_profiles = prof_res.data if prof_res.data else []
    except Exception as e:
        print(f"Fetch recommended profiles error: {e}")
        recommended_profiles = []

    # ==========================================
    # ★ 新規追加：「未定・不明」店舗の除外ロジック
    # ==========================================
    ng_shop_names = ['未定', '不明な店舗', '不明', 'テスト']
    shops = [s for s in all_shops if s.get('name') and s.get('name').strip() not in ng_shop_names]

    # 2. データの集計・結合処理（IDをすべて確実に文字列化）
    shop_dict = {str(s['id']): s for s in shops}
    event_shop_map = {str(e['id']): str(e['shop_id']) for e in events if e.get('shop_id')}
    
    # 各お店の集計用コンテナ（有効なお店のみ）
    shop_stats = {
        str(s['id']): {
            'shop': s, 
            'review_count': 0, 
            'rating_sum': 0.0, 
            'events_count': 0, 
            'pending_requests': 0, 
            'reviews': []
        } for s in shops
    }
    
    # リクエストのカウント
    for req in requests:
        sid = str(req.get('shop_id'))
        if sid in shop_stats:
            shop_stats[sid]['pending_requests'] += 1
            
    # イベント開催回数のカウント
    for ev in events:
        sid = str(ev.get('shop_id'))
        if sid in shop_stats:
            shop_stats[sid]['events_count'] += 1
            
    # レビューの集計と紐付け
    for rev in reviews:
        eid = str(rev.get('event_id'))
        sid = event_shop_map.get(eid)
        if sid and sid in shop_stats:
            shop_stats[sid]['review_count'] += 1
            shop_stats[sid]['rating_sum'] += float(rev.get('rating', 0))
            shop_stats[sid]['reviews'].append(rev)
            
    # 平均星の計算とランキング用リスト作成
    ranking_list = []
    for sid, stat in shop_stats.items():
        # レビューが1件以上あるお店だけをランキング候補に追加する！
        if stat['review_count'] > 0:
            stat['avg_rating'] = round(stat['rating_sum'] / stat['review_count'], 1)
            ranking_list.append(stat)
        
    # 星の平均が高い順、同点ならレビューが多い順
    ranking_list.sort(key=lambda x: (x['avg_rating'], x['review_count']), reverse=True)
    
    # 履歴用リスト（イベント開催実績がある店舗）
    history_list = [s for s in shop_stats.values() if s['events_count'] > 0]
    history_list.sort(key=lambda x: x['events_count'], reverse=True)


    # ==========================================
    # ★ 共通：お店詳細ダイアログ ＆ リクエスト機能
    # ==========================================
    shop_dialog = ui.dialog()

    def open_shop_dialog(stat_data):
        shop = stat_data['shop']
        avg = stat_data.get('avg_rating', '-')
        rcount = stat_data['review_count']
        revs = stat_data['reviews']
        
        shop_dialog.clear()
        # ダイアログ内部も基本ダーク設定(bg-slate-900)にしておけば、ライト時に themes.py で自動的に白反転されます
        with shop_dialog, ui.column().classes('w-full max-w-2xl hibi-glass p-6 gap-4 border border-indigo-500/30 text-white rounded-2xl shadow-2xl bg-slate-900'):
            with ui.row().classes('w-full justify-between items-start no-wrap'):
                with ui.column().classes('gap-1'):
                    ui.label(shop['name']).classes('text-xl sm:text-2xl font-bold text-indigo-400')
                    if shop.get('url'):
                        ui.link('🌐 お店の情報（外部サイト）', shop['url'], new_tab=True).classes('text-xs text-blue-400 hover:text-blue-300')
                ui.button(icon='close', on_click=shop_dialog.close).props('flat round dense').classes('shrink-0 text-white')
            
            with ui.row().classes('w-full gap-4 items-stretch'):
                # お店の画像
                img_url = shop.get('image_url') or '/static/default_shop.png'
                ui.image(img_url).classes('w-1/3 min-w-[100px] aspect-video rounded-xl object-cover border border-white/10 shrink-0')
                
                # 統計情報
                with ui.column().classes('flex-grow justify-center gap-2'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('star', size='sm', color='amber-400')
                        ui.label(f"{avg}").classes('text-xl font-bold')
                        ui.label(f"({rcount}件のレビュー)").classes('text-sm text-white/50')
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('history', size='sm', color='slate-400')
                        ui.label(f"過去の開催: {stat_data['events_count']}回").classes('text-sm text-white/70')
            
            ui.separator().classes('w-full opacity-20 my-2 bg-white')
            
            # リクエスト送信エリア
            with ui.column().classes('w-full bg-white/5 p-4 rounded-xl border border-white/10 gap-2'):
                ui.label('🙋‍♂️ ここでイベント開催をリクエスト！').classes('text-sm font-bold text-indigo-400')
                req_comment = ui.input(placeholder='例: このお店気になるので、イベントやりませんか').classes('w-full').props('outlined dense')
                
                def on_submit_request():
                    cmt = req_comment.value.strip()
                    res = submit_event_request(shop['id'], current_user_id, cmt)
                    if res:
                        ui.notify('オーナーにリクエストを送信しました！', type='positive')
                        shop_dialog.close()
                        ui.navigate.reload()
                    else:
                        ui.notify('エラーが発生しました', type='negative')
                        
                ui.button('リクエストを送信', on_click=on_submit_request, icon='send').classes('w-full mt-2 font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm')
            
            # 過去のレビュー一覧
            if revs:
                ui.label('みんなの口コミ').classes('text-sm font-bold mt-4')
                with ui.scroll_area().classes('w-full max-h-64'):
                    with ui.column().classes('w-full gap-2'):
                        for r in revs:
                            with ui.row().classes('w-full items-start gap-2 bg-black/20 p-3 rounded-lg border border-transparent'):
                                prof = r.get('profiles', {})
                                a_url = prof.get('avatar_url') or '/static/default_avatar.png'
                                name = "匿名さん" if r.get('is_anonymous') else prof.get('name', '名無し')
                                ui.image(a_url).classes('w-8 h-8 rounded-full object-cover shrink-0')
                                with ui.column().classes('gap-0 flex-grow'):
                                    with ui.row().classes('items-center justify-between w-full'):
                                        ui.label(name).classes('text-xs font-bold text-white/70')
                                        ui.label(f"★ {r.get('rating', 0)}").classes('text-xs text-amber-400 font-bold')
                                    ui.label(r.get('comment', '')).classes('text-sm mt-1 whitespace-pre-wrap')

        shop_dialog.open()


    # ==========================================
    # ★ UI描画の部品化（PC・スマホ両方で使い回すため）
    # ==========================================
    
    def render_history_panel(show_title=True):
        with ui.column().classes('w-full gap-3'):
            if show_title:
                ui.label('🕒 過去の開催店舗').classes('text-lg font-bold text-slate-300')
            if not history_list:
                ui.label('履歴はまだありません').classes('text-xs text-white/40')
            for stat in history_list:
                # ★ ui.cardを廃止し、ベースをダーク用の bg-slate-800 & border-white/10 に変更
                # これにより、ライトテーマ選択時は themes.py のルール7によって自動的に明るいグレーに反転されます
                with ui.column().classes('w-full bg-slate-800 border border-white/10 p-3 rounded-xl cursor-pointer hover:bg-slate-700 transition shadow-sm gap-1').on('click', lambda s=stat: open_shop_dialog(s)):
                    with ui.row().classes('w-full items-center justify-between no-wrap'):
                        ui.label(stat['shop']['name']).classes('text-sm font-bold text-white truncate flex-grow')
                        if stat['pending_requests'] > 0:
                            ui.badge(f"🔥 リクエスト {stat['pending_requests']}件", color='rose-500').classes('text-[10px] shrink-0')
                    with ui.row().classes('items-center gap-1 mt-1'):
                        ui.icon('history', size='xs', color='slate-400')
                        ui.label(f"開催 {stat['events_count']}回").classes('text-xs text-white/60')

    def render_ranking_panel(show_title=True):
        with ui.column().classes('w-full gap-4'):
            if show_title:
                ui.label('🏆 殿堂入りランキング').classes('text-xl font-bold text-amber-400')
            if not ranking_list:
                ui.label('評価データがありません').classes('text-xs text-white/40')
            for i, stat in enumerate(ranking_list):
                rank = i + 1
                shop = stat['shop']
                avg = stat['avg_rating']
                
                if rank <= 3:
                    # 1〜3位のカード背景も、ダーク用の bg-slate-800 をベースにします（ライト時はテーマ側CSSで美しく白反転します）
                    card_bg = 'bg-slate-800 border-white/10'
                    crown = ['👑 1位', '🥈 2位', '🥉 3位'][rank-1]
                    crown_color = ['text-amber-400', 'text-slate-300', 'text-amber-600'][rank-1]
                    
                    with ui.column().classes(f'w-full {card_bg} border p-0 rounded-xl overflow-hidden cursor-pointer hover:opacity-80 transition shadow-sm gap-0').on('click', lambda s=stat: open_shop_dialog(s)):
                        with ui.row().classes('w-full no-wrap'):
                            img_url = shop.get('image_url') or '/static/default_shop.png'
                            ui.image(img_url).classes('w-28 sm:w-32 h-24 object-cover shrink-0')
                            with ui.column().classes('p-3 justify-center gap-1 flex-grow overflow-hidden'):
                                ui.label(crown).classes(f'text-xs font-bold {crown_color}')
                                ui.label(shop['name']).classes('text-base sm:text-lg font-bold text-white truncate w-full')
                                with ui.row().classes('items-center gap-2'):
                                    ui.icon('star', size='sm', color='amber-400')
                                    ui.label(f"{avg}").classes('text-sm font-bold text-white')
                                    ui.label(f"({stat['review_count']}件)").classes('text-xs text-white/50')
                else:
                    # 4位以下も bg-slate-800 / border-white/10 をベースに変更
                    with ui.row().classes('w-full items-center justify-between bg-slate-800 border border-white/10 p-3 rounded-lg cursor-pointer hover:bg-slate-700 transition shadow-sm').on('click', lambda s=stat: open_shop_dialog(s)):
                        with ui.row().classes('items-center gap-3 flex-grow overflow-hidden'):
                            ui.label(f"{rank}位").classes('text-sm font-bold text-white/60 shrink-0')
                            ui.label(shop['name']).classes('text-sm font-bold text-white truncate')
                        with ui.row().classes('items-center gap-1 shrink-0'):
                            ui.icon('star', size='xs', color='amber-400')
                            ui.label(f"{avg}").classes('text-xs font-bold text-white')

    def render_recommended_panel(show_title=True):
        with ui.column().classes('w-full gap-3'):
            if show_title:
                ui.label('✨ メンバーのイチオシ').classes('text-lg font-bold text-indigo-400')
            if not recommended_profiles:
                ui.label('おすすめ情報はまだありません').classes('text-xs text-white/40')
            for prof in recommended_profiles:
                bar_name = prof.get('recommended_bar')
                bar_url = prof.get('bar_url')
                bar_img = prof.get('bar_image_url') or '/static/default_shop.png'
                
                # ★ ui.cardを廃止し、ベースを bg-slate-800 / border-white/10 に統一
                with ui.column().classes('w-full bg-slate-800 border border-white/10 p-3 rounded-xl shadow-sm gap-1'):
                    with ui.row().classes('items-center gap-2 mb-2 w-full no-wrap'):
                        a_url = prof.get('avatar_url') or '/static/default_avatar.png'
                        ui.image(a_url).classes('w-6 h-6 rounded-full object-cover shrink-0')
                        ui.label(f"{prof.get('name')} のおすすめ").classes('text-xs font-bold text-white/70 truncate flex-grow')
                    
                    ui.image(bar_img).classes('w-full h-24 rounded-lg object-cover mb-2 border border-white/10')
                    ui.label(bar_name).classes('text-sm font-bold text-white truncate w-full')
                    
                    if bar_url:
                        ui.link('🌐 お店を見る', bar_url, new_tab=True).classes('text-[10px] text-indigo-400 hover:text-indigo-300 mt-1 block')


    # ==========================================
    # ★ メインレイアウト構築
    # ==========================================
    with ui.column().classes('w-full max-w-7xl mx-auto p-4 md:p-6'):
        
        # ------------------------------------------
        # スマホ用レイアウト (md:hidden) - シンプルなテキスト切替UI
        # ------------------------------------------
        sp_state = {'active_view': 'ranking'}
        
        @ui.refreshable
        def render_sp_view():
            with ui.column().classes('md:hidden w-full gap-4'):
                # テキストナビゲーション部分
                with ui.row().classes('w-full justify-around items-center border-b border-white/10 pb-1 mb-2'):
                    def set_view(v):
                        sp_state['active_view'] = v
                        render_sp_view.refresh()

                    views = [
                        ('ranking', '🏆 ランキング'),
                        ('history', '🕒 履歴'),
                        ('recommended', '✨ イチオシ')
                    ]
                    
                    for v_id, v_name in views:
                        is_active = (sp_state['active_view'] == v_id)
                        
                        # アクティブな時は太字、そうでない時は薄い色
                        if is_active:
                            text_classes = 'text-xs font-extrabold text-indigo-400 border-b-2 border-indigo-400 pb-1'
                        else:
                            text_classes = 'text-xs font-bold text-white/40 pb-1'
                            
                        ui.label(v_name).classes(f'cursor-pointer transition-colors {text_classes}').on('click', lambda v=v_id: set_view(v))
                
                # 選択されたコンテンツのみを描画（タイトルはナビにあるので非表示に）
                if sp_state['active_view'] == 'ranking':
                    render_ranking_panel(show_title=False)
                elif sp_state['active_view'] == 'history':
                    render_history_panel(show_title=False)
                elif sp_state['active_view'] == 'recommended':
                    render_recommended_panel(show_title=False)

        # スマホ用の描画実行
        render_sp_view()

        # ------------------------------------------
        # PC用レイアウト (max-md:hidden) - 3カラムグリッド
        # ------------------------------------------
        with ui.element('div').classes('max-md:hidden w-full grid grid-cols-12 gap-6 items-start'):
            # 左カラム（25%幅）
            with ui.element('div').classes('col-span-3 w-full'):
                render_history_panel(show_title=True)
            
            # 中央カラム（50%幅）
            with ui.element('div').classes('col-span-6 w-full'):
                render_ranking_panel(show_title=True)
                
            # 右カラム（25%幅）
            with ui.element('div').classes('col-span-3 w-full'):
                render_recommended_panel(show_title=True)