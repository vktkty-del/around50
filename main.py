# main.py
from nicegui import app, ui
import os
from starlette.requests import ClientDisconnect
from fastapi.responses import PlainTextResponse
from fastapi import Request

# --- 認証・データベース・テーマ ---
from database.auth_db import check_user_approval
from database.timeline_db import get_user_role
import themes
import login
from components.tos_dialog import open_enforced_tos_dialog
from components.main_layout import draw_main_layout

# ★ 追加：ログインボーナス判定関数のインポート
from database.scoring_db import check_and_award_login_bonus

@app.exception_handler(ClientDisconnect)
async def client_disconnect_handler(request: Request, exc: Exception):
    print("💡 [アップロード監視] スマホ側の接続が一時的に切断されました（安全にスルーされました）")
    return PlainTextResponse("Client Disconnected Safely", status_code=499)

os.makedirs('static/posts', exist_ok=True)
os.makedirs('static/profiles', exist_ok=True)
os.makedirs('static/stamps', exist_ok=True)
app.add_static_files('/static', 'static')

def get_current_theme_data():
    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    return themes.THEMES.get(theme_name, themes.THEMES['Moonlight'])

def apply_theme():
    theme_data = get_current_theme_data()
    new_bg_class = theme_data['bg']
    is_light = theme_data.get('is_light', False)
    primary_color = theme_data.get('primary', '#06b6d4')
    
    ui.colors(primary=primary_color)
    
    bg_classes_js = str([t['bg'] for t in themes.THEMES.values()])
    is_light_js = 'true' if is_light else 'false'
    
    js_cmd = f"""
        const runThemeUpdate = () => {{
            if (!window.Quasar) {{
                setTimeout(runThemeUpdate, 50);
                return;
            }}
            
            const body = document.body;
            const bgClasses = {bg_classes_js};
            bgClasses.forEach(c => {{
                c.split(' ').forEach(cls => body.classList.remove(cls));
            }});
            '{new_bg_class}'.split(' ').forEach(cls => body.classList.add(cls));
            
            if ({is_light_js}) {{
                body.classList.add('theme-light');
                if (window.Quasar.Dark) Quasar.Dark.set(false);
            }} else {{
                body.classList.remove('theme-light');
                if (window.Quasar.Dark) Quasar.Dark.set(true);
            }}

            if (window.Quasar.utils && window.Quasar.utils.colors) {{
                window.Quasar.utils.colors.setBrand('primary', '{primary_color}');
            }} else {{
                document.body.style.setProperty('--q-primary', '{primary_color}');
            }}
        }};
        runThemeUpdate();
    """
    ui.run_javascript(js_cmd)

def enforce_auth(page_type="main"):
    is_auth = app.storage.user.get('is_authenticated')
    user_id = app.storage.user.get('user_id')
    
    if not is_auth or not user_id:
        ui.navigate.to('/login')
        return False
        
    try:
        from config.supabase_config import get_supabase
        sb = get_supabase()
        
        profile_check = sb.table("profiles").select("id").eq("id", user_id).execute()
        
        if not profile_check.data:
            user_metadata = app.storage.user.get('user_metadata', {})
            user_name = user_metadata.get('name') or user_metadata.get('full_name') or '名無しのゲスト'
            avatar_url = user_metadata.get('avatar_url') or ''
            
            sb.table("profiles").insert({
                "id": user_id,
                "name": user_name,
                "avatar_url": avatar_url,
                "status": "pending",
                "role": "member"
            }).execute()
            print(f"⚙️ [自己修復] profilesにレコードがなかったため自動生成しました: {user_name}")
    except Exception as e:
        print(f"⚙️ [自己修復エラー] {e}")

    if not check_user_approval(user_id):
        if page_type != "pending":
            ui.navigate.to('/pending')
            return False
            
    return True

@ui.page('/pending')
def pending_page():
    ui.dark_mode().enable()
    ui.query('body').style('background: #0f172a; color: white; margin: 0;')
    
    def handle_recheck():
        user_id = app.storage.user.get('user_id')
        if check_user_approval(user_id):
            status_timer.cancel()
            ui.navigate.to('/')
            
    status_timer = ui.timer(3.0, handle_recheck)

    with ui.column().classes('items-center justify-center h-screen w-full'):
        ui.icon('lock_clock', size='80px', color='amber-400').classes('animate-pulse')
        ui.label('承認待ちです').classes('text-2xl font-bold mt-4')
        ui.label('オーナーがアカウントを承認すると、自動的に画面が切り替わります。').classes('text-white/60 text-xs mt-1')
        ui.spinner(size='md', color='amber-400').classes('mt-4')
        ui.button('再読み込み', on_click=handle_recheck).classes('mt-6 bg-slate-800 text-white/70 text-xs')

@ui.page('/')
def main_page():
    if not enforce_auth(page_type="main"):
        return
        
    theme_data = get_current_theme_data()
    is_light = theme_data.get('is_light', False)
    
    body = ui.query('body')
    body.classes(add=theme_data.get('bg', ''))
    if is_light:
        body.classes(add='theme-light')

    if 'primary' in theme_data:
        ui.colors(primary=theme_data['primary'])

    js_cmd = f"if (window.Quasar && window.Quasar.Dark) {{ Quasar.Dark.set({str(not is_light).lower()}); }}"
    ui.run_javascript(js_cmd)

    ui.add_css(themes.LIGHT_THEME_CSS)
    ui.add_head_html(themes.GLOBAL_HTML, shared=True)

    current_user_id = app.storage.user.get('user_id', 'guest_user')
    try:
        from database.profile_db import mark_user_active
        mark_user_active(str(current_user_id))
        # ★ 追加：ログインボーナスと自動回復のトリガーをここで発動
        check_and_award_login_bonus(str(current_user_id))
    except Exception:
        pass

    apply_theme()

    from database.profile_db import get_safe_profile
    my_profile = get_safe_profile(current_user_id)

    agreed_tos = my_profile.get('agreed_tos', False)
    
    def on_tos_agreed_success():
        ui.navigate.reload()

    if not agreed_tos:
        ui.timer(0.5, lambda: open_enforced_tos_dialog(current_user_id, on_tos_agreed_success), once=True)

    user_metadata = app.storage.user.get('user_metadata', {})
    current_user_name = my_profile.get('name') or user_metadata.get('name', '名無し')
    avatar_url = my_profile.get('avatar_url') or user_metadata.get('avatar_url', '')
    
    if 'user_metadata' not in app.storage.user:
        app.storage.user['user_metadata'] = {}
    app.storage.user['user_metadata']['name'] = current_user_name
    app.storage.user['user_metadata']['avatar_url'] = avatar_url
    
    latest_role = get_user_role(current_user_id)
    app.storage.user['role'] = latest_role
    
    role_lower = str(latest_role).lower()
    is_su = role_lower in ['superuser', 'admin', 'owner', 'master', 'submaster']

    draw_main_layout(
        current_user_id=current_user_id,
        current_user_name=current_user_name,
        avatar_url=avatar_url,
        is_su=is_su
    )

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host='127.0.0.1', 
        port=8000, 
        title='日々、彩り。', 
        favicon='static/favicon/favicon_rev3.png', 
        storage_secret=os.getenv('STORAGE_SECRET', 'a-very-long-and-secure-random-string-1234567890'), 
        reload=True,
        show=False,
        reconnect_timeout=30.0
    )