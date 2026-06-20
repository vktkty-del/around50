# components/su_dashboard_users.py
from nicegui import ui
from config.supabase_config import get_supabase
from components.su_dashboard_logic import (
    get_avatar_url, format_datetime_string, update_user_status,
    update_user_role, fetch_all_users_for_admin
)
# ★ 招待コードを取得するための関数をインポート
from database.profile_db import get_or_create_invite_code

# ==========================================
# 1. ユーザー管理 詳細・操作ダイアログ
# ==========================================
def open_user_detail_dialog(u: dict, current_user_id: str, refresh_users_cb, refresh_kpi_cb, user_dict: dict):
    u_id = u['id']
    u_name = u.get('name') or "名無し"
    u_status = u.get('status', "pending")
    u_role = u.get('role', "member")
    u_invited_by = u.get('invited_by')
    inviter_name = user_dict.get(u_invited_by, "なし") if u_invited_by else "なし"
    created_at = format_datetime_string(u.get('created_at', ''), include_seconds=False)
    comment = u.get('comment') or "自己紹介・コメントは設定されていません。"
    avatar_url = get_avatar_url(u.get('avatar_url'), u_name)

    # ★ 対象ユーザーが所有している招待コードを取得
    try:
        raw_invite_code = get_or_create_invite_code(u_id)
        invite_code = "取得失敗" if str(raw_invite_code).startswith("ERR:") else raw_invite_code
    except Exception:
        invite_code = "なし / 取得エラー"

    status_labels = {
        "approved": "✅ 承認済み (APPROVED)",
        "pending": "⏳ 承認待ち (PENDING)",
        "banned": "🚫 BAN (BANNED)"
    }
    
    status_classes = {
        "approved": "text-green-400 font-bold",
        "pending": "text-amber-400 font-bold animate-pulse",
        "banned": "text-red-400 font-bold"
    }

    role_options = {
        'member': '一般メンバー (member)',
        'superuser': '管理者 (superuser)'
    }

    with ui.dialog() as dialog, ui.card().classes('bg-slate-900 border border-cyan-500/30 text-white w-90 max-w-full p-5 shadow-2xl rounded-2xl gap-4'):
        # ヘッダー
        with ui.row().classes('w-full justify-between items-center border-b border-white/10 pb-2'):
            with ui.row().classes('items-center gap-1.5'):
                ui.icon('manage_accounts', size='sm', color='cyan-400')
                ui.label('ユーザー詳細管理').classes('text-sm font-bold text-white')
            ui.button(icon='close', on_click=dialog.close).props('flat round size=sm color=white')

        # プロフィールカード（基本）
        with ui.row().classes('w-full items-center gap-3 bg-white/5 p-3 rounded-xl border border-white/5 m-0'):
            ui.image(avatar_url).classes('w-12 h-12 rounded-full border border-white/20 shrink-0')
            with ui.column().classes('gap-0.5 flex-grow overflow-hidden'):
                ui.label(u_name).classes('font-bold text-base text-white truncate w-full')
                ui.label(f"ID: {u_id}").classes('text-[9px] text-white/30 font-mono break-all w-full')

        # 詳細パラメータ
        with ui.column().classes('w-full gap-3 text-xs text-slate-300'):
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('🚦 登録ステータス').classes('text-[10px] text-white/40 font-bold')
                ui.label(status_labels.get(u_status, u_status)).classes(f'pl-1 {status_classes.get(u_status, "text-white")}')
            
            with ui.column().classes('gap-1 w-full'):
                ui.label('👥 アカウント権限 (ロール変更)').classes('text-[10px] text-white/40 font-bold')
                def handle_role_change(e):
                    new_val = e.value
                    try:
                        update_user_role(u_id, new_val)
                        refresh_users_cb()
                        ui.notify(f'{u_name} さんの権限を「{role_options[new_val]}」に変更しました。', type='positive', position='top')
                    except Exception as err:
                        ui.notify(f'権限の更新に失敗しました: {err}', type='negative', position='top')

                ui.select(options=role_options, value=u_role, on_change=handle_role_change)\
                    .classes('w-full bg-slate-950 border border-white/10 rounded-lg text-white px-2 py-1 text-xs').props('borderless dark dense')
            
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('🤝 紹介（招待）ユーザー').classes('text-[10px] text-white/40 font-bold')
                ui.label(inviter_name).classes('pl-1 text-cyan-300 font-bold')

            # ★ 新規追加: ユーザーが所有している招待コード（コピーボタン付き）
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('✉️ 所有する招待コード').classes('text-[10px] text-white/40 font-bold')
                with ui.row().classes('w-full items-center justify-between bg-black/20 p-2 rounded-lg border border-white/5 mt-0.5 no-wrap'):
                    ui.label(invite_code).classes('text-xs font-mono text-cyan-300 font-bold pl-1')
                    ui.button('コピー', on_click=lambda e, code=invite_code: (
                        ui.run_javascript(f'navigator.clipboard.writeText("{code}")'),
                        ui.notify('招待コードをコピーしました！', color='positive', position='top')
                    )).props('flat dense size=xs color=cyan-400').classes('text-[10px] font-bold')

            with ui.column().classes('gap-0.5 w-full'):
                ui.label('📅 登録申請日時').classes('text-[10px] text-white/40 font-bold')
                ui.label(created_at).classes('pl-1 text-white font-mono')
                
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('💬 自己紹介・メッセージ').classes('text-[10px] text-white/40 font-bold')
                ui.label(comment).classes('pl-1 text-white leading-relaxed bg-black/20 p-2 rounded-lg border border-white/5 max-h-24 overflow-y-auto clean-scroll')

        # アクションエリア
        ui.separator().classes('bg-white/10 my-1')
        ui.label('⚙️ 管理操作を実行').classes('text-[10px] text-white/40 font-bold -mb-1')
        
        with ui.row().classes('w-full gap-2 justify-stretch m-0'):
            if u_status == "pending":
                def handle_approve():
                    update_user_status(u_id, "approved")
                    refresh_users_cb()
                    refresh_kpi_cb()
                    dialog.close()
                    ui.notify(f'{u_name} さんを承認しました。', type='positive', position='top')
                ui.button('承認する', icon='done', on_click=handle_approve).classes('flex-grow bg-green-600 hover:bg-green-500 text-white font-bold text-xs py-2 rounded-xl')
            
            if u_status == "banned":
                def handle_unban():
                    update_user_status(u_id, "approved")
                    refresh_users_cb()
                    refresh_kpi_cb()
                    dialog.close()
                    ui.notify(f'{u_name} さんのBANを解除しました。', type='info', position='top')
                ui.button('BAN解除 (承認)', icon='settings_backup_restore', on_click=handle_unban).classes('flex-grow bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs py-2 rounded-xl')
            else:
                def handle_ban():
                    update_user_status(u_id, "banned")
                    refresh_users_cb()
                    refresh_kpi_cb()
                    dialog.close()
                    ui.notify(f'{u_name} さんをBANしました。', type='warning', position='top')
                ui.button('BAN (利用停止)', icon='gavel', on_click=handle_ban).classes('flex-grow bg-red-700 hover:bg-red-600 text-white font-bold text-xs py-2 rounded-xl')
                
        ui.button('閉じる', on_click=dialog.close).classes('w-full bg-slate-800 hover:bg-slate-700 text-white py-1.5 rounded-xl text-xs font-bold')
    dialog.open()


# ==========================================
# 2. ユーザー管理リスト コンポーネント
# ==========================================
def build_users_ui(current_user_id: str, refresh_users_cb, refresh_kpi_cb):
    try:
        users = fetch_all_users_for_admin(current_user_id)
        sb = get_supabase()
        count_res = sb.table("profiles").select("id", count="exact").execute()
        total_u_count = count_res.count if count_res.count is not None else (len(users) + 1)
    except Exception as e:
        print(f"ユーザー管理取得エラー: {e}")
        with ui.card().classes('w-full h-[450px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-cyan-500 flex flex-col overflow-hidden'):
            ui.label('👥 ユーザー管理').classes('font-bold text-cyan-400 mb-2 shrink-0')
            ui.label('通信が混み合っています。再読み込みをお待ちください...').classes('text-white/50 text-xs p-2')
        return

    with ui.card().classes('w-full h-[450px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-cyan-500 flex flex-col overflow-hidden'):
        with ui.row().classes('w-full items-center gap-2 mb-2 shrink-0'):
            ui.label('👥 ユーザー管理').classes('font-bold text-cyan-400')
            ui.badge(f"総登録: {total_u_count} 名", color='cyan-950').classes('text-[10px] text-cyan-300 px-2 py-0.5 border border-cyan-500/30 rounded-full font-bold')
        
        if not users:
            ui.label('あなた以外の登録ユーザーが見つかりません。').classes('text-white/50 text-xs p-2')
            return

        try:
            all_profiles = sb.table("profiles").select("id, name").execute()
            user_dict = {p['id']: p['name'] for p in all_profiles.data or []}
        except Exception:
            user_dict = {}

        # ui.scroll_area と flex-grow を使って高さの潰れを防止
        with ui.scroll_area().classes('w-full flex-grow border border-white/5 rounded-lg'):
            with ui.column().classes('w-full gap-2 pb-4'):
                for u in users:
                    u_id = u['id']
                    u_name = u.get('name') or "名無し"
                    u_status = u.get('status', "pending")
                    u_invited_by = u.get('invited_by')
                    
                    status_colors = {
                        "approved": "bg-green-500/10 border-green-500/40 text-green-300", 
                        "pending": "bg-amber-500/10 border-amber-500/40 text-amber-300 animate-pulse", 
                        "banned": "bg-red-500/10 border-red-500/40 text-red-300 opacity-60"
                    }
                    badge_color = status_colors.get(u_status, "border-white/10")
                    
                    # リストアイテム (shrink-0 で潰れを防止)
                    with ui.row().classes('w-full items-center justify-between p-2.5 bg-black/30 hover:bg-white/10 cursor-pointer rounded-lg border border-white/5 text-xs no-wrap gap-2 shrink-0').on('click', lambda _, usr=u: open_user_detail_dialog(usr, current_user_id, refresh_users_cb, refresh_kpi_cb, user_dict)):
                        with ui.row().classes('items-center gap-2.5 no-wrap overflow-hidden'):
                            avatar_url = get_avatar_url(u.get('avatar_url'), u_name)
                            ui.image(avatar_url).classes('w-6 h-6 rounded-full border border-white/20 shrink-0')
                            with ui.column().classes('gap-0 overflow-hidden'):
                                ui.label(u_name).classes('font-bold text-white truncate w-28')
                                if u_invited_by:
                                    inviter_name = user_dict.get(u_invited_by, "不明")
                                    ui.label(f'紹介: {inviter_name}').classes('text-[9px] text-cyan-300 truncate w-24')
                        
                        ui.badge(u_status.upper(), color='slate-800').classes(f'text-[9px] px-1.5 py-0.5 border {badge_color} shrink-0')