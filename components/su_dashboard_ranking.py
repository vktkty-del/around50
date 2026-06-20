# components/su_dashboard_ranking.py
from nicegui import ui, app
from config.supabase_config import get_supabase
# ★ calculate_user_level をインポートに追加
from database.scoring_db import get_frequent_companions, calculate_user_level

def build_ranking_ui():
    from themes import THEMES
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)
    sb = get_supabase()

    # テーマ別のカラー設定
    card_bg = 'bg-white border-amber-300 shadow-sm' if is_light else 'bg-slate-900/40 border-amber-500/30'
    text_color = 'text-slate-800' if is_light else 'text-white'
    rank_text = 'text-amber-600' if is_light else 'text-amber-400'
    border_color = 'border-slate-200' if is_light else 'border-white/10'
    comp_text = 'text-slate-500' if is_light else 'text-white/40'
    
    with ui.card().classes(f'w-full h-[430px] p-4 {card_bg} shadow-xl rounded-xl border-t-2 flex flex-col overflow-hidden'):
        ui.label('🏆 貢献度トップランキング').classes(f'text-sm font-bold {rank_text} mb-2 shrink-0')
        
        try:
            res = sb.table("profiles").select("id, name, total_score, role").order("total_score", desc=True).limit(10).execute()
            top_users = res.data or []
            
            if not top_users:
                with ui.column().classes('w-full flex-grow justify-center items-center'):
                    ui.label('まだデータがありません').classes('text-xs text-slate-500')
            else:
                with ui.scroll_area().classes('w-full flex-grow pr-2'):
                    for i, user in enumerate(top_users, 1):
                        user_id = user.get('id')
                        score = user.get('total_score') or 0
                        role = user.get('role', 'member')
                        is_su = str(role).lower() in ['superuser', 'admin', 'owner']
                        
                        # ★ 直書きの計算式をやめて、共通関数を呼び出す（これで整数化＆MAX判定が効きます）
                        lv_str = calculate_user_level(score)
                        
                        with ui.column().classes(f'w-full py-1.5 border-b {border_color} last:border-0 gap-0.5'):
                            # --- 上段：ランキングと基本情報 ---
                            with ui.row().classes('w-full justify-between items-center no-wrap'):
                                with ui.row().classes('items-center gap-1.5'):
                                    ui.label(f"{i}位").classes(f'text-[10px] font-bold bg-amber-500/20 {rank_text} px-2 py-0.5 rounded-full')
                                    # ★ LVバッジに文字列をそのまま適用
                                    ui.label(lv_str).classes('text-[9px] font-bold bg-orange-500/10 text-orange-500 border border-orange-500/20 px-1 rounded')
                                    ui.label(user.get('name', '名無し')).classes(f'text-xs font-bold {text_color} truncate max-w-[100px]')
                                    if is_su:
                                        ui.label('運営').classes('text-[8px] bg-cyan-500/20 text-cyan-500 px-1 rounded')
                                
                                ui.label(f"{score} pt").classes(f'text-xs font-mono font-bold {rank_text}')
                            
                            # --- 下段：よく一緒に飲む人（トップ3まで） ---
                            companions = get_frequent_companions(user_id, limit=3)
                            if companions:
                                with ui.row().classes('w-full items-center gap-1 pl-8 mt-0.5'):
                                    ui.icon('handshake', size='10px', color='grey-5' if is_light else 'grey-6')
                                    ui.label('よく飲む:').classes(f'text-[9px] {comp_text}')
                                    with ui.row().classes('gap-1'):
                                        for comp in companions:
                                            # アバターにマウスホバーで「名前（〇回）」を表示
                                            ui.image(comp['avatar_url']).classes(f'w-4 h-4 rounded-full border {"border-slate-300" if is_light else "border-white/20"}').tooltip(f"{comp['name']} ({comp['common_count']}回)")

        except Exception as e:
            print(f"ランキング取得エラー: {e}")
            ui.label('データの取得に失敗しました').classes('text-xs text-red-500')