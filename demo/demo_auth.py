import uuid
from nicegui import app
from config.supabase_config import IS_DEMO_MODE

# デモ用ユーザーの固定UUID（昨日流したSQLのprofilesテーブルに紐付けられます）
DEMO_MASTER_ID = "00000000-0000-0000-0000-000000000001"
DEMO_SUBMASTER_ID = "00000000-0000-0000-0000-000000000002"
DEMO_MEMBER_ID = "00000000-0000-0000-0000-000000000003"

def login_as_demo_user(role_type: str) -> bool:
    """
    デモ環境（APP_ENV=demo）の時だけ、指定した権限で仮ログイン状態を作る関数。
    本番環境では環境変数スイッチにより、この関数自体が強制的に動作を拒否します。
    """
    if not IS_DEMO_MODE:
        return False  # 本番環境なら何があっても拒否
        
    # 選択されたロールに応じて、アプリ内セッション（NiceGUIのapp.storage.user）に擬似データを注入
    if role_type == "Master":
        app.storage.user["user_id"] = DEMO_MASTER_ID
        app.storage.user["role"] = "Master"
        app.storage.user["status"] = "approved"
        app.storage.user["name"] = "オーナー (Master)"
    elif role_type == "SubMaster":
        app.storage.user["user_id"] = DEMO_SUBMASTER_ID
        app.storage.user["role"] = "SubMaster"
        app.storage.user["status"] = "approved"
        app.storage.user["name"] = "開発者 (SubMaster)"
    else:
        app.storage.user["user_id"] = DEMO_MEMBER_ID
        app.storage.user["role"] = "member"
        app.storage.user["status"] = "approved"
        app.storage.user["name"] = "一般メンバー"
        
    app.storage.user["is_authenticated"] = True
    return True