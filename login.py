# login.py
import asyncio
import os
import uuid
import hashlib  # 暗号化（ハッシュ化）用
import httpx  # ★ LINE API通信用
import urllib.parse  # ★ URLエンコード用
from nicegui import ui, app
from dotenv import load_dotenv  # 環境変数ロード用
from components.splash import show_splash_screen
from fastapi import Request
from database.profile_db import validate_invite_code # ★招待コード検証用

# =============================================================
# ★ 安全設計：最初に .env をロードし、その後に Supabase を初期化
# =============================================================
# 1. find_dotenv もインポートし、自動的に親ディレクトリを遡って .env ファイルを見つけてロード
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

# 2. ロードが終わった状態で Supabase を初期化
from config.supabase_config import get_supabase
supabase = get_supabase()

# 3. .env から合言葉（招待コード）を取得
# （※後方互換性・初期設定用マスターコードとして維持）
SHARED_INVITATION_CODE = os.getenv("INVITATION_CODE", "hibi1234")


def hash_password(password: str) -> str:
    """
    パスワードをSHA-256技術を使って安全にハッシュ化する。
    DBを覗かれても元のパスワードが絶対に解読できないセキュリティ技術です。
    """
    return hashlib.sha256(password.encode()).hexdigest()


# ==========================================
# 🔑 新規登録（サインアップ）の処理
# ==========================================
def handle_passcode_signup(nickname: str, invite_code: str, personal_pw: str):
    nickname_stripped = nickname.strip()
    invite_stripped = invite_code.strip()
    pw_stripped = personal_pw.strip()

    # ★ 追加：名前が空の場合は弾く
    if not nickname_stripped:
        ui.notify('ユーザ名を入力してください', color='warning', position='top')
        return

    if not invite_stripped or not pw_stripped:
        ui.notify('すべての項目を入力してください', color='warning', position='top')
        return

    # ★ 改善：DBによる動的招待コード照合 ＆ マスターコードのフォールバック
    inviter_id = validate_invite_code(invite_stripped)
    if not inviter_id and invite_stripped != SHARED_INVITATION_CODE:
        ui.notify('無効な招待コードです', color='negative', position='top')
        return

    try:
        # 重複チェック：すでに同じニックネームのユーザーがいるか
        check = supabase.table("profiles").select("id").eq("name", nickname_stripped).execute()
        if check.data:
            ui.notify('その名前はすでに使用されています。別の名前にしてください。', color='warning', position='top')
            return

        # パスワードを暗号（ハッシュ）化
        hashed = hash_password(pw_stripped)
        user_id = str(uuid.uuid4())

        # データベースに新規登録（承認待ち status="pending"）
        insert_data = {
            "id": user_id,
            "name": nickname_stripped,
            "password_hash": hashed,
            "avatar_url": f"https://api.dicebear.com/7.x/bottts/svg?seed={nickname_stripped}",
            "status": "pending",
            "role": "member"
        }
        
        # ★ 招待者のIDがあれば記録
        if inviter_id:
            insert_data["invited_by"] = inviter_id

        supabase.table("profiles").insert(insert_data).execute()

        # 自動ログイン処理
        app.storage.user['is_authenticated'] = True
        app.storage.user['user_id'] = user_id
        app.storage.user['user_metadata'] = {"name": nickname_stripped}
        
        ui.notify('メンバー新規登録（承認待ち）が完了しました！', color='positive', position='top')
        ui.navigate.to('/')

    except Exception as e:
        ui.notify(f'登録エラー: {e}', color='red-500', position='top')


# ==========================================
# 🔑 通常ログインの処理（パスワード認証）
# ==========================================
def handle_passcode_login(nickname: str, personal_pw: str):
    nickname_stripped = nickname.strip()
    pw_stripped = personal_pw.strip()

    if not nickname_stripped or not pw_stripped:
        ui.notify('ニックネームとパスワードを入力してください', color='warning', position='top')
        return

    try:
        # ユーザーをDBから検索
        res = supabase.table("profiles").select("id, password_hash, status").eq("name", nickname_stripped).execute()
        
        if not res.data:
            ui.notify('ニックネームまたはパスワードが正しくありません', color='negative', position='top')
            return
            
        db_user = res.data[0]
        db_hash = db_user.get('password_hash')
        
        # セキュリティ：初期メンバーなどでパスワードハッシュが未登録の場合のケア
        if not db_hash:
            ui.notify('このアカウントはパスワード未登録です。新規登録から再設定してください。', color='warning', position='top')
            return

        # パスワードハッシュの比較
        if hash_password(pw_stripped) != db_hash:
            ui.notify('ニックネームまたはパスワードが正しくありません', color='negative', position='top')
            return

        # 一致すればログイン成功！
        app.storage.user['is_authenticated'] = True
        app.storage.user['user_id'] = db_user['id']
        app.storage.user['user_metadata'] = {"name": nickname_stripped}
        
        ui.notify(f'{nickname_stripped} としてログインしました！', color='positive', position='top')
        ui.navigate.to('/')

    except Exception as e:
        ui.notify(f'ログインエラー: {e}', color='red-500', position='top')


# ==========================================
# 外部ログイン（Google / X / LINE）
# ==========================================
def login_with_google():
    try:
        redirect_to = "https://around50cl.win/auth/callback"
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirect_to": redirect_to}
        })
        
        storage = getattr(supabase.auth, '_storage', getattr(supabase.auth, 'storage', None))
        if storage:
            verifier = storage.get_item("supabase.auth.token-code-verifier")
            if verifier:
                app.storage.user['pkce_verifier'] = verifier
                print(f"DEBUG: [ログイン開始] Verifierを退避 -> {verifier}")
            
        if res.url:
            print(f"DEBUG: [リダイレクト] Googleへ飛びます -> {res.url[:50]}...")
            ui.run_javascript(f'window.location.href = "{res.url}";')
            
    except Exception as e:
        print(f"🚨 ログイン開始エラー: {str(e)}")
        ui.notify(f'エラー: {e}', color='red-500')

def login_with_x():
    try:
        redirect_to = "https://around50cl.win/auth/callback"
        res = supabase.auth.sign_in_with_oauth({
            "provider": "x",
            "options": {"redirect_to": redirect_to}
        })
        try:
            storage = getattr(supabase.auth, '_storage', getattr(supabase.auth, 'storage', None))
            if storage:
                verifier = storage.get_item("supabase.auth.token-code-verifier")
                if verifier:
                    app.storage.user['pkce_verifier'] = verifier
        except Exception as e:
            pass
        if res.url:
            ui.navigate.to(res.url)
    except Exception as e:
        ui.notify(f'エラー: {e}', color='red-500')


def login_with_line():
    """
    LINE Developersで作成したLINEログインの認可画面へリダイレクトします。
    """
    try:
        channel_id = os.getenv("LINE_CHANNEL_ID")
        redirect_uri = os.getenv("LINE_REDIRECT_URI", "https://around50cl.win/auth/line-callback")
        
        # 🛡️ 安全弁（ガード）：環境変数が読めていない場合は、即時中断して通知を出す
        if not channel_id or str(channel_id).strip() == "" or channel_id == "None":
            print("🚨 [警告] LINE_CHANNEL_ID が環境変数から取得できません。.env ファイルの設定を確認してください。")
            ui.notify(
                'LINEのチャネル設定が読み込めませんでした。.envファイルを確認してください。', 
                color='negative', 
                position='top'
            )
            return
            
        state = str(uuid.uuid4())
        app.storage.user['line_oauth_state'] = state
        
        # 400エラーを防ぐため、権限が必要な "%20email" を scope から安全に除外
        line_auth_url = (
            f"https://access.line.me/oauth2/v2.1/authorize"
            f"?response_type=code"
            f"&client_id={channel_id}"
            f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
            f"&state={state}"
            f"&scope=profile%20openid"
        )
        
        print(f"DEBUG: [LINEリダイレクト] -> {line_auth_url[:60]}...")
        ui.run_javascript(f'window.location.href = "{line_auth_url}";')
        
    except Exception as e:
        print(f"🚨 LINEログイン開始エラー: {str(e)}")
        ui.notify(f'エラー: {e}', color='red-500')


# ==========================================
# UI表示画面
# ==========================================
@ui.page('/login')
def login_ui():
    app.storage.user['initialized'] = True
    ui.dark_mode().enable()
    show_splash_screen()

    ui.add_head_html('''
    <style>
        body {
            background: #090d16;
            color: #fff;
            font-family: 'Segoe UI', -apple-system, sans-serif;
            overflow: hidden;
            position: relative;
            min-height: 100vh;
        }
        .bg-blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(100px);
            opacity: 0.55;
            z-index: -1;
            pointer-events: none;
            animation: float_blobs 20s infinite alternate ease-in-out;
        }
        .blob-1 { width: 350px; height: 350px; background: radial-gradient(circle, #0d9488 0%, transparent 70%); top: -50px; left: -50px; }
        .blob-2 { width: 400px; height: 400px; background: radial-gradient(circle, #db2777 0%, transparent 70%); bottom: -100px; right: -50px; animation-delay: -10s; }
        .blob-3 { width: 300px; height: 300px; background: radial-gradient(circle, #4f46e5 0%, transparent 70%); top: 40%; left: 30%; animation-delay: -5s; }
        @keyframes float_blobs {
            0% { transform: translate(0px, 0px) scale(1); }
            50% { transform: translate(40px, -60px) scale(1.15); }
            100% { transform: translate(-20px, 20px) scale(0.95); }
        }
        .login-box {
            width: 90%;
            max-width: 380px;
            padding: 20px 25px;
            background: rgba(255, 255, 255, 0.04);
            border-radius: 20px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 15px 45px rgba(0, 0, 0, 0.35);
        }
        .divider {
            text-align: center;
            margin: 15px 0;
            color: rgba(255, 255, 255, 0.3);
            display: flex;
            align-items: center;
            font-size: 0.75rem;
        }
        .divider:before, .divider:after {
            content: "";
            flex: 1;
            height: 1px;
            background: rgba(255, 255, 255, 0.08);
            margin: 0 10px;
        }
    </style>
    ''')

    ui.add_body_html('''
    <div class="bg-blob blob-1"></div>
    <div class="bg-blob blob-2"></div>
    <div class="bg-blob blob-3"></div>
    ''')

    # 【1つの画面中央寄せ親コンテナ】にロゴもログインボックスもすべて中に格納
    with ui.column().classes('w-full min-h-screen items-center justify-center p-4 relative z-10 gap-0'):
        
        # 子要素1：メインロゴ
        with ui.column().classes('items-center justify-center gap-0 mb-6 w-full'):
            ui.label('日々、彩り。').classes('text-3xl sm:text-4xl font-extralight text-white tracking-[0.5em] pl-[0.5em] drop-shadow-[0_0_15px_rgba(255,255,255,0.2)] text-center')
            ui.label('何気ない日常に、大切な仲間と、小さな彩りを。').classes('text-[10px] text-white/45 tracking-[0.2em] pl-[0.2em] mt-3 text-center')

        # 子要素2：ログインボックス
        with ui.element('div').classes('login-box'):
            
            # ログイン ＆ 新規登録 を美しく切り替えるタブ
            with ui.tabs().classes('w-full bg-slate-900/40 rounded-xl p-1 mb-3 border border-white/5') as login_tabs:
                login_tab = ui.tab('🔑 ログイン').classes('text-[11px] text-white')
                signup_tab = ui.tab('📝 新規登録').classes('text-[11px] text-white')

            with ui.tab_panels(login_tabs, value=login_tab).classes('w-full bg-transparent p-0 m-0'):
                
                # --- 【A】ログインタブの入力フォーム ---
                with ui.tab_panel(login_tab).classes('w-full p-0 m-0 gap-2.5 flex flex-col items-stretch'):
                    login_name = ui.input(placeholder='ユーザ名')\
                        .classes('w-full').props('dark filled color=cyan dense')
                        
                    login_pw = ui.input(placeholder='パスワード', password=True)\
                        .classes('w-full').props('dark filled color=cyan dense')
                    
                    ui.button('ログインする', on_click=lambda: handle_passcode_login(login_name.value or "", login_pw.value or ""))\
                        .classes('w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold py-2 rounded-lg text-xs shadow-lg shadow-cyan-500/10 mt-1')

                # --- 【B】新規登録（サインアップ）タブの入力フォーム ---
                with ui.tab_panel(signup_tab).classes('w-full p-0 m-0 gap-2.5 flex flex-col items-stretch'):
                    ui.label('招待コードが必要です。予めご準備ください。').classes('text-[10px] text-white/45 tracking-[0.2em] pl-[0.2em] mt-3 text-center')
                    signup_name = ui.input(placeholder='ユーザ名')\
                        .classes('w-full').props('dark filled color=cyan dense')
                                            
                    signup_pw = ui.input(placeholder='パスワード (次回から使用)', password=True)\
                        .classes('w-full').props('dark filled color=cyan dense')                    
                        
                    signup_code = ui.input(placeholder='招待コード', password=True)\
                        .classes('w-full').props('dark filled color=cyan dense')
                    
                    ui.button('メンバー新規登録する', on_click=lambda: handle_passcode_signup(signup_name.value or "", signup_code.value or "", signup_pw.value or ""))\
                        .classes('w-full bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 text-white font-bold py-2 rounded-lg text-xs shadow-lg shadow-emerald-500/10 mt-1')
            
            # 外部アカウント連携（仕切り線）
            ui.html('<div class="divider">または外部アカウントでログイン</div>')

            # Googleログイン
            ui.button('Googleでログイン', on_click=login_with_google) \
                .props('icon="img:https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg" flat') \
                .classes('w-full rounded-lg font-bold text-black bg-white border border-slate-300 text-xs py-2.5 lowercase=false')
            
            # Xログイン
            ui.button('Xでログイン', on_click=login_with_x) \
                .props('icon="img:data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' fill=\'white\'><path d=\'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z\'/></svg>" flat') \
                .classes('w-full rounded-lg font-bold text-white bg-black text-xs py-2.5 lowercase=false mt-2 border border-white/10')

            # LINEログイン（Xボタンのすぐ下に配置）
            ui.button('LINEでログイン', on_click=login_with_line) \
                .props('icon="img:https://upload.wikimedia.org/wikipedia/commons/4/41/LINE_logo.svg" flat') \
                .classes('w-full rounded-lg font-bold text-white bg-[#06C755] text-xs py-2.5 lowercase=false mt-2')


# ==========================================
# 最終完成版：サーバーに優しく、確実に遷移するコールバック（Google / X 用）
# ==========================================
@ui.page('/auth/callback')
def auth_callback(code: str = None):
    ui.dark_mode().enable()
    print(f"DEBUG: [コールバック到達] 受信コード -> {code}")
    
    if not code:
        print("DEBUG: 認証コードがありませんでした")
        ui.notify('認証コードがありません', color='negative')
        ui.timer(1.5, lambda: ui.navigate.to('/login'), once=True)
        return

    try:
        # 個人セッションから合言葉を取り出す
        verifier = app.storage.user.get('pkce_verifier')
        print(f"DEBUG: [コールバック処理] 個人セッションから復元したVerifier -> {verifier}")
        
        storage = getattr(supabase.auth, '_storage', getattr(supabase.auth, 'storage', None))
        if storage and verifier:
            storage.set_item("supabase.auth.token-code-verifier", verifier)

        # 認証コードの交換
        res = supabase.auth.exchange_code_for_session({"auth_code": code})
        print("DEBUG: [成功] セッションの交換に成功しました！")
        
        # ログイン状態の保存
        app.storage.user['is_authenticated'] = True
        app.storage.user['user_id'] = res.user.id
        app.storage.user['user_metadata'] = res.user.user_metadata
        
        # profilesへの自動インサート
        try:
            user_id = res.user.id
            user_meta = res.user.user_metadata or {}
            
            # ★ 修正：様々なキーから名前を探し、見つからなければ空文字にする
            raw_name = (
                user_meta.get('name') or 
                user_meta.get('full_name') or 
                user_meta.get('nickname') or 
                user_meta.get('preferred_username') or 
                ''
            )
            user_name = str(raw_name).strip()
            
            # ★ 追加：名前が取得できなかった場合は登録を拒否して中断
            if not user_name:
                print("🚨 警告: SNSから名前が取得できませんでした")
                supabase.auth.sign_out() # 念のため認証セッションを破棄
                # エラー詳細と解決策を明記（timeoutを長めに設定）
                error_msg = (
                    '【登録エラー】SNSからお名前が取得できませんでした。\n'
                    '連携時の「プロフィール情報の提供」のチェックが外れているか、'
                    'お名前に特殊な記号が含まれている可能性があります。\n'
                    '権限を許可したうえでもう一度連携をやり直していただくか、'
                    '「📝 新規登録」タブから紹介コードを使用して手動でアカウントを作成してください。'
                )
                ui.notify(error_msg, color='negative', position='top', multi_line=True, timeout=8000)
                
                ui.run_javascript('setTimeout(() => { window.location.href = "/login"; }, 2000);')
                return

            avatar_url = user_meta.get('avatar_url') or ''
            
            profile_check = supabase.table("profiles").select("id").eq("id", user_id).execute()
            if not profile_check.data:
                supabase.table("profiles").insert({
                    "id": user_id,
                    "name": user_name,  # 確実に取得できた名前が入る
                    "avatar_url": avatar_url,
                    "status": "pending",
                    "role": "member"
                }).execute()
            avatar_url = user_meta.get('avatar_url') or ''
            
            profile_check = supabase.table("profiles").select("id").eq("id", user_id).execute()
            if not profile_check.data:
                supabase.table("profiles").insert({
                    "id": user_id,
                    "name": user_name,
                    "avatar_url": avatar_url,
                    "status": "pending",
                    "role": "member"
                }).execute()
        except Exception as db_err:
            print(f"⚠️ プロフィール自動生成エラー: {db_err}")

        with ui.column().classes('w-full h-screen items-center justify-center bg-[#090d16] text-white gap-4'):
            ui.spinner('dots', size='lg', color='cyan-500')
            ui.label('認証に成功しました！').classes('text-xl font-bold tracking-widest')
            ui.label('画面を準備しています...').classes('text-sm text-white/50')
            
            ui.run_javascript('setTimeout(() => { window.location.href = "/"; }, 1500);')
            print("DEBUG: [完了] 1.5秒後にトップページへ遷移します")
        
    except Exception as e:
        print(f"🚨 コールバックエラー: {str(e)}")
        ui.notify('ログイン処理中にエラーが発生しました', color='negative')
        ui.run_javascript('setTimeout(() => { window.location.href = "/"; }, 1500);')


# =============================================================
# ★ 新機能：LINEログイン専用コールバック
# =============================================================
@ui.page('/auth/line-callback')
async def line_callback(code: str = None, state: str = None):
    ui.dark_mode().enable()
    print(f"DEBUG: [LINEコールバック到達] code={code}, state={state}")
    
    if not code:
        ui.notify('認証コードがありませんでした', color='negative')
        ui.timer(1.5, lambda: ui.navigate.to('/login'), once=True)
        return

    # CSRFの軽度なチェック
    saved_state = app.storage.user.get('line_oauth_state')
    if saved_state and saved_state != state:
        print("DEBUG: [警告] LINE OAuthのStateが一致しません。")

    try:
        channel_id = os.getenv("LINE_CHANNEL_ID")
        channel_secret = os.getenv("LINE_CHANNEL_SECRET")
        redirect_uri = os.getenv("LINE_REDIRECT_URI", "https://around50cl.win/auth/line-callback")

        # 1. 認可コードをアクセストークン・IDトークンに交換する
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://api.line.me/oauth2/v2.1/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": channel_id,
                    "client_secret": channel_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_data = token_res.json()

        if "error" in token_data:
            print(f"🚨 LINEトークン取得エラー: {token_data}")
            ui.notify(f"LINE認証エラー: {token_data.get('error_description')}", color='negative')
            ui.timer(1.5, lambda: ui.navigate.to('/login'), once=True)
            return

        access_token = token_data.get("access_token")
        id_token = token_data.get("id_token")

        # 2. LINE検証エンドポイント経由でトークンを安全にデコード＆検証
        async with httpx.AsyncClient() as client:
            verify_res = await client.post(
                "https://api.line.me/oauth2/v2.1/verify",
                data={
                    "id_token": id_token,
                    "client_id": channel_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            user_info = verify_res.json()

        if "error" in user_info:
            print(f"🚨 LINEトークン検証エラー: {user_info}")
            ui.notify("ユーザー情報の取得に失敗しました", color='negative')
            ui.timer(1.5, lambda: ui.navigate.to('/login'), once=True)
            return

        line_user_id = user_info.get("sub")
        
        # ★ 修正：「LINEユーザー」というデフォルト値をやめ、空文字を取得
        raw_name = user_info.get("name", "")
        line_name = str(raw_name).strip()
        
        # ★ 追加：名前が取得できなかった場合は登録を拒否して中断
        if not line_name:
            print("🚨 警告: LINEから名前が取得できませんでした")
            error_msg = (
                '【登録エラー】LINEからお名前が取得できませんでした。\n'
                '権限の許可が外れているか、特殊な文字が使われている可能性があります。\n'
                'お手数ですが、権限を許可したうえでもう一度LINEログインをやり直すか、'
                '「📝 新規登録」タブから招待コードを使用して手動で登録を行ってください。'
            )
            ui.notify(error_msg, color='negative', position='top', multi_line=True, timeout=8000)
            
            ui.timer(2.0, lambda: ui.navigate.to('/login'), once=True)
            return
        line_avatar = user_info.get("picture") or f"https://api.dicebear.com/7.x/bottts/svg?seed={line_user_id}"

        # ★ 新機能：アクセストークンを使って「LINEの一言（ステータスメッセージ）」を取得する
        line_comment = ""
        try:
            async with httpx.AsyncClient() as client:
                profile_res = await client.get(
                    "https://api.line.me/v2/profile",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                profile_data = profile_res.json()
                line_comment = profile_data.get("statusMessage", "")  # 一言を取得
                print(f"DEBUG: LINEから取得した一言（statusMessage）-> {line_comment}")
        except Exception as e:
            print(f"⚠️ LINE一言の取得に失敗しました（処理は継続します）: {e}")

        # LINE IDから決定論的なUUID(UUIDv5)を生成し、PostgreSQLのUUID型に完全適合させます
        LINE_NAMESPACE = uuid.UUID('e2a4073e-3f6c-48dc-8b65-e9dfcb8ef991')
        mapped_user_id = str(uuid.uuid5(LINE_NAMESPACE, line_user_id))

        print(f"DEBUG: LINEユーザーID={line_user_id} -> 変換後UUID={mapped_user_id}")

        # 3. 既存の `profiles` テーブルを照合
        profile_check = supabase.table("profiles").select("id, status").eq("id", mapped_user_id).execute()

        # A. 既存ユーザーの場合
        if profile_check.data:
            # 既存のGoogle/Xと同様、ステータス制限をコールバック内では行わず、そのままセッションを確立してトップへ流します
            # （これにより、approved の人は即時ログイン、pending の人は自動で /pending へ美しく遷移します）
            app.storage.user['is_authenticated'] = True
            app.storage.user['user_id'] = mapped_user_id
            app.storage.user['user_metadata'] = {"name": line_name, "avatar_url": line_avatar}
            
            with ui.column().classes('w-full h-screen items-center justify-center bg-[#090d16] text-white gap-4'):
                ui.spinner('dots', size='lg', color='cyan-500')
                ui.label('LINEでログインしました！').classes('text-xl font-bold tracking-widest')
                ui.run_javascript('setTimeout(() => { window.location.href = "/"; }, 1500);')
            return

        # B. 新規ユーザーの場合
        try:
            # profilesに新規登録（statusは pending、roleは member）
            # ★ ここで「LINEの一言（line_comment）」を profiles.comment に新規登録時の一回限り流し込みます
            supabase.table("profiles").insert({
                "id": mapped_user_id,
                "name": line_name,
                "avatar_url": line_avatar,
                "comment": line_comment,  # 一言を自己紹介にマッピング
                "status": "pending",
                "role": "member"
            }).execute()
            
            # セッションを確立
            app.storage.user['is_authenticated'] = True
            app.storage.user['user_id'] = mapped_user_id
            app.storage.user['user_metadata'] = {"name": line_name, "avatar_url": line_avatar}

            with ui.column().classes('w-full h-screen items-center justify-center bg-[#090d16] text-white gap-4'):
                ui.spinner('dots', size='lg', color='cyan-500')
                ui.label('LINEでの連携登録が完了しました！').classes('text-xl font-bold tracking-widest')
                ui.label('画面を準備しています...').classes('text-sm text-white/50')
                ui.run_javascript('setTimeout(() => { window.location.href = "/"; }, 1500);')
                
        except Exception as db_err:
            print(f"⚠️ LINEプロフィール自動生成エラー: {db_err}")
            ui.notify('プロフィールの自動作成に失敗しました', color='negative')
            ui.timer(2.0, lambda: ui.navigate.to('/login'), once=True)

    except Exception as e:
        print(f"🚨 LINEコールバックエラー: {str(e)}")
        ui.notify('ログイン処理中にエラーが発生しました', color='negative')
        ui.timer(1.5, lambda: ui.navigate.to('/login'), once=True)