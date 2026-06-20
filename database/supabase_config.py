# config/supabase_config.py
from supabase import create_client
import os
from dotenv import load_dotenv

class LazySupabase:
    def __init__(self):
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            load_dotenv() # 使う瞬間にだけ読み込む
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if not url: raise ValueError("環境変数が読み込めません")
            self._client = create_client(url, key)
        return self._client

    # どんなメソッドを呼ばれても、_client に転送する
    def __getattr__(self, name):
        return getattr(self._ensure_client(), name)

# これをインスタンス化する（起動時には接続しない）
supabase_instance = LazySupabase()

# 互換性のため
def get_supabase():
    return supabase_instance