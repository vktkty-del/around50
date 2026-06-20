# auth_utils.py
from config.supabase_config import get_supabase
supabase = get_supabase()
from nicegui import app


def get_auth_supabase():
    """
    セッション情報を持つSupabaseクライアントを返す共通メソッド
    """
    
    
    # app.storage.userからセッション情報を取得してセット
    session = app.storage.user.get("session")
    if session:
        supabase.auth.set_session(
            access_token=session.get("access_token"),
            refresh_token=session.get("refresh_token")
        )
    return supabase