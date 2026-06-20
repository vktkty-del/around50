# components/su_dashboard.py
from nicegui import ui, app
from datetime import datetime, timezone, timedelta
from config.supabase_config import get_supabase
from database.profile_db import is_user_online
from database.su_db import (
    fetch_pending_posts, approve_post, fetch_support_tickets, 
    update_ticket_status, fetch_admin_memos, create_admin_memo, delete_ticket
)
from database.timeline_db import delete_post

# 共通アバターコンポーネントのインポート
from components.avatar import draw_user_avatar

# ★ 新規追加：長大な運営ガイドダイアログは別ファイルからインポート
from components.su_dashboard_help import open_su_help_dialog

# メンテナンス性向上のため、ロジック・ユーティリティ関数は別ファイルから取得
from components.su_dashboard_logic import (
    get_avatar_url, format_datetime_string, format_time, parse_user_agent,
    insert_access_log, fetch_all_users_for_admin, update_user_status,
    update_user_role, fetch_access_logs, fetch_page_pv_data
)
from components.su_dashboard_memos import build_memos_ui
from components.su_dashboard_invites import build_invites_ui
from components.su_dashboard_logs import build_logs_ui
from components.su_dashboard_ng import build_ng_ui
from components.su_dashboard_tickets import build_tickets_ui
from components.su_dashboard_users import build_users_ui
from components.su_dashboard_kpi import build_kpi_ui
from components.su_dashboard_presence import build_presence_ui
from components.su_dashboard_events import build_events_ui
from components.su_dashboard_ranking import build_ranking_ui
# ★ 新規追加: リクエスト管理コンポーネント
from components.su_dashboard_requests import build_requests_ui

# ==========================================
# グローバルダイアログ (最外周定義)
# ==========================================

# 1. ユーザー管理 詳細・操作ダイアログ (アカウント権限設定プルダウン付き)
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

    # ロールの表示名定義
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


# 2. 防犯アクセスログ詳細ダイアログ
def open_log_detail_dialog(log: dict):
    full_date_jst = format_datetime_string(log.get('created_at', ''), include_seconds=True)
    friendly_ua = parse_user_agent(log.get('user_agent') or '')

    with ui.dialog() as dialog, ui.card().classes('bg-slate-900 border border-cyan-500/30 text-white w-85 max-w-full p-5 shadow-2xl rounded-2xl gap-3'):
        with ui.row().classes('w-full justify-between items-center border-b border-white/10 pb-2 mb-1'):
            with ui.row().classes('items-center gap-1.5'):
                ui.icon('security', size='sm', color='cyan-400')
                ui.label('防犯アクセスログ詳細').classes('text-sm font-bold text-white')
            ui.button(icon='close', on_click=dialog.close).props('flat round size=sm color=white')
            
        with ui.column().classes('w-full gap-3 text-xs text-slate-300'):
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('🕒 操作日時').classes('text-[10px] text-white/40 font-bold')
                ui.label(full_date_jst).classes('pl-1 text-white font-mono')
            
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('👤 操作ユーザー').classes('text-[10px] text-white/40 font-bold')
                ui.label(log.get('user_name', 'ゲスト')).classes('pl-1 text-cyan-300 font-bold')
            
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('⚙️ 操作内容').classes('text-[10px] text-white/40 font-bold')
                ui.label(log.get('action', '操作')).classes('pl-1 text-white leading-relaxed whitespace-pre-line')
            
            with ui.column().classes('🌐 IPアドレス').classes('gap-0.5 w-full'):
                ui.label('🌐 IPアドレス').classes('text-[10px] text-white/40 font-bold')
                ui.label(log.get('ip_address', '0.0.0.0')).classes('pl-1 text-amber-400 font-mono')
            
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('📍 接続元地域').classes('text-[10px] text-white/40 font-bold')
                ui.label(log.get('location') or 'ローカル / 不明').classes('pl-1 text-green-300 font-bold')
                    
            with ui.column().classes('gap-0.5 w-full'):
                ui.label('💻 デバイス情報').classes('text-[10px] text-white/40 font-bold')
                ui.label(friendly_ua).classes('text-white font-bold pl-1 mb-1')
                ui.label(log.get('user_agent') or '不明').classes('text-white/40 pl-1 text-[9px] leading-tight break-all bg-black/20 p-2 rounded-lg border border-white/5')
                
        ui.button('閉じる', on_click=dialog.close).classes('w-full mt-2 bg-slate-800 hover:bg-slate-700 text-white py-2 rounded-xl text-xs font-bold')
    dialog.open()


# =====================================================================
# 🛠️ 3. メイン画面描画コンポーネント (render_su_dashboard)
# =====================================================================
if 'ng_history' not in globals():
    ng_history = []

def render_su_dashboard(current_user_id: str):
    # テーマパレットの取得とライトテーマ確認
    from themes import THEMES
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)

    with ui.row().classes('w-full items-center justify-between mb-4 no-wrap gap-4'):
        with ui.column().classes('gap-1 flex-grow min-w-0'):
            ui.label('管理者モード').classes('text-2xl font-extrabold tracking-wider text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.3)] leading-none')
            ui.label('コミュニティの治安維持と運用情報の俯瞰監視パネル').classes('text-xs text-white/50 leading-none mt-1.5')
        
        if is_light:
            ui.button('❓ 運営ガイド', on_click=lambda: open_su_help_dialog(is_light))\
              .props('unelevated color="primary" size=sm')\
              .classes('font-bold rounded-lg px-3 py-1.5 text-xs shrink-0')\
              .style('color: #ffffff !important;')
        else:
            ui.button('❓ 運営ガイド', on_click=lambda: open_su_help_dialog(is_light))\
              .props('flat text-color=white size=sm')\
              .classes('bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold rounded-lg px-3 py-1.5 text-xs shrink-0')

    log_state = {'limit': 15}

    def refresh_kpi():
        comp_kpi_sp.refresh()
        comp_kpi_pc.refresh()
        
    def refresh_users():
        comp_users_sp.refresh()
        comp_users_pc.refresh()
        refresh_presence()
        
    def refresh_logs():
        comp_logs_sp.refresh()
        comp_logs_pc.refresh()
        
    def refresh_ng():
        comp_ng_sp.refresh()
        comp_ng_pc.refresh()
        
    def refresh_tickets():
        comp_tickets_sp.refresh()
        comp_tickets_pc.refresh()
        
    def refresh_memos():
        comp_memos_sp.refresh()
        comp_memos_pc.refresh()
        
    def refresh_invites():
        comp_invites_sp.refresh()
        comp_invites_pc.refresh()

    def refresh_presence():
        comp_presence_sp.refresh()
        comp_presence_pc.refresh()

    def refresh_events():
        comp_events_sp.refresh()
        comp_events_pc.refresh()

    def refresh_ranking():
        comp_ranking_sp.refresh()
        comp_ranking_pc.refresh()

    # ★ 追加: リクエスト用リフレッシュ
    def refresh_requests():
        comp_requests_sp.refresh()
        comp_requests_pc.refresh()
    
    dashboard_theme_state = {'active_theme': app.storage.user.get('theme_name', 'Moonlight')}

    def check_theme_changed_realtime():
        current_theme = app.storage.user.get('theme_name', 'Moonlight')
        if current_theme != dashboard_theme_state['active_theme']:
            dashboard_theme_state['active_theme'] = current_theme
            
            theme_data = THEMES.get(current_theme, THEMES.get('Moonlight', {}))
            is_light_theme = theme_data.get('is_light', False)
            if is_light_theme:
                ui.run_javascript('document.body.classList.add("theme-light")')
            else:
                ui.run_javascript('document.body.classList.remove("theme-light")')

            refresh_kpi()
            refresh_memos()
            refresh_users()
            refresh_logs()
            refresh_ng()
            refresh_tickets()
            refresh_invites()
            refresh_presence()
            refresh_events()
            refresh_ranking()
            refresh_requests() # 追加

    ui.timer(0.1, check_theme_changed_realtime)

    # ==========================================
    # ★ 内部ネストUI定義
    # ==========================================

    @ui.refreshable
    def comp_kpi_sp(): build_kpi_ui(is_pc_mode=False)
    @ui.refreshable
    def comp_kpi_pc(): build_kpi_ui(is_pc_mode=True)

    def build_ng():
        build_ng_ui(ng_history, refresh_ng, refresh_kpi)

    @ui.refreshable
    def comp_ng_sp(): build_ng()
    @ui.refreshable
    def comp_ng_pc(): build_ng()

    @ui.refreshable
    def comp_tickets_sp(): build_tickets_ui(refresh_tickets, refresh_kpi)
    @ui.refreshable
    def comp_tickets_pc(): build_tickets_ui(refresh_tickets, refresh_kpi)

    @ui.refreshable
    def comp_users_sp(): build_users_ui(current_user_id, refresh_users, refresh_kpi)
    @ui.refreshable
    def comp_users_pc(): build_users_ui(current_user_id, refresh_users, refresh_kpi)

    @ui.refreshable
    def comp_presence_sp(): build_presence_ui(refresh_presence)
    @ui.refreshable
    def comp_presence_pc(): build_presence_ui(refresh_presence)

    @ui.refreshable
    def comp_events_sp(): build_events_ui(refresh_users, refresh_kpi)
    @ui.refreshable
    def comp_events_pc(): build_events_ui(refresh_users, refresh_kpi)

    @ui.refreshable
    def comp_ranking_sp(): build_ranking_ui()
    @ui.refreshable
    def comp_ranking_pc(): build_ranking_ui()

    # ★ 追加: リクエストパネル
    @ui.refreshable
    def comp_requests_sp(): build_requests_ui(current_user_id, refresh_requests)
    @ui.refreshable
    def comp_requests_pc(): build_requests_ui(current_user_id, refresh_requests)

    def build_invites():
        build_invites_ui()

    @ui.refreshable
    def comp_invites_sp(): build_invites()
    @ui.refreshable
    def comp_invites_pc(): build_invites()

    def build_logs():
        build_logs_ui(log_state, refresh_logs, open_log_detail_dialog)

    @ui.refreshable
    def comp_logs_sp(): build_logs()
    @ui.refreshable
    def comp_logs_pc(): build_logs()

    @ui.refreshable
    def comp_memos_sp(): build_memos_ui(current_user_id)
    @ui.refreshable
    def comp_memos_pc(): build_memos_ui(current_user_id)

    # ==========================================
    # ★ スマホ用レイアウト (md:hidden) : タブ方式
    # ==========================================
    with ui.column().classes('w-full md:hidden p-0 m-0 gap-0'):
        with ui.tabs().classes('w-full bg-slate-900/40 rounded-xl p-1 mb-4 border border-white/5 overflow-x-auto no-wrap') as admin_tabs:
            dash_tab = ui.tab('📊 概要').classes('text-white text-xs shrink-0')
            event_tab = ui.tab('📅 イベント').classes('text-white text-xs shrink-0')
            req_tab = ui.tab('💌 リク').classes('text-white text-xs shrink-0') # ★ 追加
            ranking_tab = ui.tab('🏆 貢献').classes('text-white text-xs shrink-0')
            users_tab = ui.tab('👥 ユーザー').classes('text-white text-xs shrink-0')
            presence_tab = ui.tab('🟢 稼働').classes('text-white text-xs shrink-0')
            logs_tab = ui.tab('📋 ログ').classes('text-white text-xs shrink-0')
            invites_tab = ui.tab('🤝 招待').classes('text-white text-xs shrink-0')
            tab_ng = ui.tab('🚨 NG').classes('text-white text-xs shrink-0')
            tab_ticket = ui.tab('📩 チケ').classes('text-white text-xs shrink-0')
            tab_memo = ui.tab('📝 メモ').classes('text-white text-xs shrink-0')

        with ui.tab_panels(admin_tabs, value=dash_tab).classes('w-full bg-transparent p-0 m-0'):
            with ui.tab_panel(dash_tab).classes('p-0 m-0'):
                comp_kpi_sp()
            with ui.tab_panel(event_tab).classes('p-0 m-0'):
                comp_events_sp()
            with ui.tab_panel(req_tab).classes('p-0 m-0'): # ★ 追加
                comp_requests_sp()
            with ui.tab_panel(ranking_tab).classes('p-0 m-0'):
                comp_ranking_sp()
            with ui.tab_panel(users_tab).classes('p-0 m-0'):
                comp_users_sp()
            with ui.tab_panel(presence_tab).classes('p-0 m-0'):
                comp_presence_sp()
            with ui.tab_panel(logs_tab).classes('p-0 m-0'):
                comp_logs_sp()
            with ui.tab_panel(invites_tab).classes('p-0 m-0'):
                comp_invites_sp()
            with ui.tab_panel(tab_ng).classes('p-0 m-0'):
                comp_ng_sp()
            with ui.tab_panel(tab_ticket).classes('p-0 m-0'):
                comp_tickets_sp()
            with ui.tab_panel(tab_memo).classes('p-0 m-0'):
                comp_memos_sp()

    # ==========================================
    # ★ PC用レイアウト (max-md:hidden) : 完璧な左右同期ダッシュボード
    # ==========================================
    with ui.column().classes('w-full max-md:hidden p-0 m-0 gap-6'):
        
        # 1. アナリティクス・KPIエリア
        comp_kpi_pc()
        
        # イベント管理パネルとランキングパネルを横並びで配置
        with ui.row().classes('w-full gap-4 no-wrap items-stretch'):
            with ui.column().classes('w-[calc(65%-0.5rem)] gap-4'):
                comp_events_pc()
                comp_requests_pc() # ★ 追加: イベントの下にリクエストを配置
            with ui.column().classes('w-[calc(35%-0.5rem)]'):
                comp_ranking_pc()
        
        # 2. 治安維持・緊急対応セクション
        with ui.column().classes('w-full gap-2'):
            ui.label('🛡️ 治安維持・緊急対応').classes('text-[10px] font-extrabold text-white/40 tracking-widest uppercase pl-1')
            with ui.row().classes('w-full gap-4 no-wrap items-stretch'):
                with ui.column().classes('w-[calc(50%-0.5rem)]'):
                    comp_ng_pc()
                with ui.column().classes('w-[calc(50%-0.5rem)]'):
                    comp_tickets_pc()
                    
        # 3. コミュニティユーザー管理セクション
        with ui.column().classes('w-full gap-2'):
            ui.label('👥 コミュニティ管理').classes('text-[10px] font-extrabold text-white/40 tracking-widest uppercase pl-1')
            with ui.row().classes('w-full gap-4 no-wrap items-start'):
                with ui.column().classes('w-[38%]'):
                    comp_users_pc()
                with ui.column().classes('w-[24%]'):
                    comp_presence_pc()
                with ui.column().classes('w-[38%]'):
                    comp_invites_pc()

        # 4. システム運用記録セクション
        with ui.column().classes('w-full gap-2'):
            ui.label('⚙️ システム運用補助 & ログ記録').classes('text-[10px] font-extrabold text-white/40 tracking-widest uppercase pl-1')
            with ui.row().classes('w-full gap-4 no-wrap items-start'):
                with ui.column().classes('w-2/3'):
                    comp_logs_pc()
                with ui.column().classes('w-1/3'):
                    comp_memos_pc()