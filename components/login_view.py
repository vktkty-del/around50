from nicegui import ui, app
from config.supabase_config import IS_DEMO_MODE
from demo.demo_auth import login_as_demo_user

def login_page_ui(on_login_success):
    """ログイン画面 & 承認待ち画面のUI"""
    
    # 既にログインしていて、承認待ち状態のユーザー用の表示
    if app.storage.user.get("is_authenticated") and app.storage.user.get("status") == "pending":
        with ui.card().classes('w-96 mx-auto mt-20 p-8 text-center bg-white/30 backdrop-blur-md rounded-xl shadow-lg border border-white/20'):
            ui.label('Hibi ～IRODORI～').classes('text-2xl font-bold text-slate-800 mb-4')
            ui.icon('lock', size='lg').classes('text-amber-500 mb-4')
            ui.label('オーナーの承認待ちです').classes('text-lg font-bold text-slate-700')
            ui.label('現在、門番システムが稼働しています。関係者確認が取れるまでしばらくお待ちください。').classes('text-xs text-slate-500 mt-2')
        return

    # 通常のログイン選択画面
    with ui.card().classes('w-96 mx-auto mt-20 p-8 text-center bg-white/30 backdrop-blur-md rounded-xl shadow-lg border border-white/20'):
        ui.label('Hibi ～IRODORI～').classes('text-3xl font-extrabold text-slate-800 mb-2')
        ui.label('日々、彩り。').classes('text-xs text-slate-500 italic mb-6')
        
        # 本番用のSNSログインボタン（モック）
        ui.button('Googleでログイン', icon='login').classes('w-full bg-red-500 text-white font-bold mb-3')
        ui.button('X (旧Twitter)でログイン', icon='login').classes('w-full bg-black text-white font-bold mb-3')
        ui.button('Meta (Threads/Insta)でログイン', icon='login').classes('w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold mb-6')