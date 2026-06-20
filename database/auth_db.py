from config.supabase_config import get_supabase

def get_profile_status(user_id: str) -> dict:
    supabase = get_supabase()
    """ユーザーの現在の承認状態（status）と役職（role）をDBから取得する。"""
    
    
    try:
        response = supabase.table("profiles").select("status, role, name").eq("id", user_id).execute()
        if response.data:
            return response.data[0]
        else:
            return {"status": "pending", "role": "member", "name": "新規ユーザー"}
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return {"status": "pending", "role": "member", "name": "エラー"}

def check_user_approval(user_id: str) -> bool:
    """承認済み（approved）か、またはsuperuserなら許可する"""
    status_data = get_profile_status(user_id)
    
    # 1. 承認済みかチェック
    is_approved = status_data.get("status") == "approved"
    
    # 2. スーパーユーザーかチェック
    is_superuser = status_data.get("role") == "superuser"
    
    # どちらか一方でTrueなら許可
    return is_approved or is_superuser

def upsert_profile(user_id: str, data: dict):
    supabase = get_supabase()
    """プロフィールの更新・新規登録"""
    
    data["id"] = user_id
    supabase.table("profiles").upsert(data).execute()