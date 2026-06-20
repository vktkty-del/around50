# database/profile_db.py
import sys
from config.supabase_config import get_supabase
supabase = get_supabase()
import requests
from bs4 import BeautifulSoup
import time  # 時間計測用にインポート
import string
import secrets

# =====================================================================
# ★ メモリ型リアルタイムプレゼンス機能 (メモリ空間の物理的一元化)
# =====================================================================
# ポインタ貼り替えを廃止し、プロセス内で唯一の sys._active_users_presence を直接参照します。
if not hasattr(sys, '_active_users_presence'):
    sys._active_users_presence = {}

def mark_user_active(user_id: str):
    """ユーザーのアクティブ時刻を更新する"""
    sys._active_users_presence[str(user_id)] = time.time()

def is_user_online(user_id: str, timeout: int = 45) -> bool:
    """指定ユーザーが現在オンライン（アクティブ）か判定する"""
    last_active = sys._active_users_presence.get(str(user_id), 0)
    return (time.time() - last_active) < timeout

def remove_user_active(user_id: str):
    """ユーザーのアクティブ状態を即座に破棄する（ログアウト高速反映用）"""
    if hasattr(sys, '_active_users_presence'):
        sys._active_users_presence.pop(str(user_id), None)


# ==========================================
# プロフィール操作関連
# ==========================================
def get_safe_profile(user_id: str):
    """ユーザーのプロフィールを取得し、存在しない場合はデフォルト値を返す"""
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if not response.data:
            return {"name": "名無し"}
            
        db_data = response.data[0]
        
        # カオスな文字列からゴミ記号を完全に排除してリスト化する
        raw_liquor = db_data.get("liquor_type")
        if raw_liquor:
            cleaned_str = str(raw_liquor).replace('[', '').replace(']', '').replace('"', '').replace("'", '')
            liquor_list = [x.strip() for x in cleaned_str.split(',') if x.strip()]
        else:
            liquor_list = []

        return {
            "name": db_data.get("name") or "",
            "avatar_url": db_data.get("avatar_url") or "",
            "header_image_url": db_data.get("header_image_url") or "",  # ★追加
            "birthday": db_data.get("birthday") or "",
            "location": db_data.get("location") or "",
            "occupation": db_data.get("occupation") or "",
            "hobbies": db_data.get("hobbies") or "",
            "comment": db_data.get("comment") or "",
            "bio": db_data.get("bio") or "",
            "liquor_type": liquor_list,
            "favorite_brand": db_data.get("favorite_brand") or "",
            "drinking_style": db_data.get("drinking_style") or "",
            "drinking_area": db_data.get("drinking_area") or "",
            "recommended_bar": db_data.get("recommended_bar") or "",
            "bar_url": db_data.get("bar_url") or "",
            "bar_image_url": db_data.get("bar_image_url") or "",
            "role": db_data.get("role") or "member",
            "status": db_data.get("status") or "pending",
            "gender": db_data.get("gender") or 0,
            "agreed_tos": db_data.get("agreed_tos", False)
        }
    except Exception as e:
        print(f"Profile fetch error: {e}")
        return {"name": "エラー"}

def update_profile(user_id: str, profile_data: dict):
    """プロフィールを更新する（安全なupsert）"""
    
    profile_data["id"] = user_id
    
    if "liquor_type" in profile_data and isinstance(profile_data["liquor_type"], list):
        profile_data["liquor_type"] = ",".join(profile_data["liquor_type"])
        
    try:
        supabase.table("profiles").upsert(profile_data).execute()
        return True
    except Exception as e:
        print(f"Profile update error: {e}")
        raise e

def fetch_ogp_data(url: str):
    """指定されたURLからOGP（タイトルと画像）を取得する"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.find('meta', property='og:title')
        image = soup.find('meta', property='og:image')

        return {
            "title": title['content'] if title else "店舗情報",
            "image": image['content'] if image else ""
        }
    except Exception:
        return {"title": "店舗情報（取得失敗）", "image": ""}

# database/profile_db.py の該当する関数をこれに上書きします
def get_all_profiles():
    """全メンバーのリストを取得する（承認待ちユーザーは除外、お酒情報や登録日なども取得）"""
    try:
        # ★ header_image_url を追加
        response = supabase.table("profiles").select(
            "id, name, avatar_url, header_image_url, comment, role, status, liquor_type, drinking_style, drinking_area, created_at"
        ).neq("status", "pending").execute()
        return response.data or []
    except Exception as e:
        print(f"Fetch all profiles error: {e}")
        return []

# ==========================================
# ★ 招待コード操作関連
# ==========================================
def generate_random_code(length: int = 8) -> str:
    """セキュリティ的に安全なランダム8桁の英数字を生成"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_or_create_invite_code(user_id: str) -> str:
    """ユーザー固有の招待コードを取得、なければ新規生成する"""
    try:
        response = supabase.table("invitation_codes").select("code").eq("owner_id", user_id).execute()
        if response.data:
            return response.data[0]["code"]
            
        new_code = generate_random_code()
        supabase.table("invitation_codes").insert({
            "code": new_code,
            "owner_id": user_id
        }).execute()
        return new_code
    except Exception as e:
        err_msg = str(e)
        print(f"Invite code fetch error: {err_msg}")
        return f"ERR:{err_msg}"

def validate_invite_code(code: str) -> str:
    """入力された招待コードを検証し、有効なら招待者のIDを返す"""
    try:
        response = supabase.table("invitation_codes").select("owner_id").eq("code", code).execute()
        if response.data:
            return response.data[0]["owner_id"]
        return None
    except Exception as e:
        print(f"Validate code error: {e}")
        return None

def regenerate_invite_code(user_id: str) -> str:
    """★ 新設：既存の招待コードを無効化し、新しいコードを再発行する"""
    try:
        new_code = generate_random_code()
        # 既存のレコードを新しいコードで上書き更新（UPDATE）
        res = supabase.table("invitation_codes").update({
            "code": new_code
        }).eq("owner_id", user_id).execute()
        
        # もし万が一レコードが無かった場合は新規作成にフォールバック
        if not res.data:
            supabase.table("invitation_codes").insert({
                "code": new_code,
                "owner_id": user_id
            }).execute()
            
        return new_code
    except Exception as e:
        err_msg = str(e)
        print(f"Invite code regenerate error: {err_msg}")
        return f"ERR:{err_msg}"