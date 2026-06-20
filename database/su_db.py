# database/su_db.py
from config.supabase_config import get_supabase
supabase = get_supabase()

# ==========================================
# 1. NG審議（留保）フロー関連
# ==========================================
def fetch_pending_posts():
    """ステータスが 'pending'（審議待ち）の投稿を取得"""
    response = supabase.table("timeline_posts") \
        .select("*, profiles(name, avatar_url)") \
        .eq("status", "pending") \
        .is_("deleted_at", "null") \
        .order("created_at", desc=False) \
        .execute()
    return response.data if response.data else []

def approve_post(post_id: str):
    """留保された投稿を承認し、タイムラインに公開する"""
    supabase.table("timeline_posts").update({"status": "approved"}).eq("id", post_id).execute()

# ==========================================
# 2. 要望チケット管理関連
# ==========================================
def fetch_support_tickets():
    """チケット一覧を取得 (論理削除されたものは除外)"""
    response = supabase.table("support_tickets") \
        .select("*, profiles!support_tickets_created_by_fkey(name, avatar_url)") \
        .neq("status", "deleted") \
        .order("created_at", desc=True) \
        .execute()
    return response.data if response.data else []

def update_ticket_status(ticket_id: str, new_status: str):
    """チケットのステータスを更新し、ユーザーに通知を送る"""
    res = supabase.table("support_tickets").select("title, created_by").eq("id", ticket_id).execute()
    if res.data:
        ticket = res.data[0]
        title = ticket.get("title", "無題")
        user_id = ticket.get("created_by")

        supabase.table("support_tickets").update({"status": new_status}).eq("id", ticket_id).execute()

        if user_id:
            status_text = "【対応中】" if new_status == "in_progress" else "【解決済み】" if new_status == "resolved" else ""
            if status_text:
                content = f"お問い合わせ「{title[:10]}...」が{status_text}になりました。"
                create_notification(user_id, "ticket_update", content)

def delete_ticket(ticket_id: str):
    """チケットを論理削除し、ユーザーに通知を送る"""
    res = supabase.table("support_tickets").select("title, created_by").eq("id", ticket_id).execute()
    if res.data:
        ticket = res.data[0]
        title = ticket.get("title", "無題")
        user_id = ticket.get("created_by")

        supabase.table("support_tickets").update({"status": "deleted"}).eq("id", ticket_id).execute()

        if user_id:
            content = f"お問い合わせ「{title[:10]}...」が運営により削除(クローズ)されました。"
            create_notification(user_id, "ticket_delete", content)

def create_support_ticket(user_id: str, title: str, content: str, priority: str = 'normal'):
    """一般ユーザーからのサポートチケットを作成してDBに保存する"""
    data = {
        "title": title,
        "content": content,
        "priority": priority,
        "created_by": user_id
    }
    supabase.table("support_tickets").insert(data).execute()

def create_dummy_ticket(user_id: str):
    """UIテスト用のダミーチケットを生成（本番ではユーザー画面から実行）"""
    data = {
        "title": "荒らしユーザーの報告",
        "content": "Aさんがチャットルームで暴言を吐いています。対応をお願いします。",
        "priority": "high",
        "created_by": user_id
    }
    supabase.table("support_tickets").insert(data).execute()


# ==========================================
# ★ 通知(Notifications)関連
# ==========================================
def create_notification(user_id: str, notif_type: str, content: str):
    """汎用通知を作成する"""
    supabase.table("notifications").insert({
        "user_id": user_id,
        "type": notif_type,
        "content": content
    }).execute()

def fetch_unread_notifications(user_id: str):
    """未読の通知一覧を取得する"""
    response = supabase.table("notifications") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("is_read", False) \
        .order("created_at", desc=False) \
        .execute()
    return response.data if response.data else []

def mark_notifications_as_read(user_id: str):
    """対象ユーザーの未読通知をすべて既読にする"""
    supabase.table("notifications") \
        .update({"is_read": True}) \
        .eq("user_id", user_id) \
        .eq("is_read", False) \
        .execute()


# ==========================================
# 3. 運営メモボード関連
# ==========================================
def fetch_admin_memos():
    """運営メモを取得"""
    response = supabase.table("admin_memos") \
        .select("*, profiles!admin_memos_created_by_fkey(name, avatar_url)") \
        .order("created_at", desc=False) \
        .execute()
    return response.data if response.data else []

def create_admin_memo(user_id: str, content: str):
    """運営メモを作成"""
    supabase.table("admin_memos").insert({"created_by": user_id, "content": content}).execute()


# ==========================================
# ★ 4. 新規ユーザー承認(入国管理)関連
# ==========================================
def fetch_pending_users():
    """承認待ち(status='pending')のユーザーを取得"""
    response = supabase.table("profiles") \
        .select("id, name, avatar_url, created_at, comment") \
        .eq("status", "pending") \
        .order("created_at", desc=False) \
        .execute()
    return response.data if response.data else []

def approve_user(user_id: str):
    """ユーザーを承認する（status='approved', role='member'に変更）"""
    supabase.table("profiles").update({
        "status": "approved",
        "role": "member"
    }).eq("id", user_id).execute()

def reject_user(user_id: str):
    """ユーザーを拒否する（status='rejected'に変更）"""
    supabase.table("profiles").update({
        "status": "rejected"
    }).eq("id", user_id).execute()


# ==========================================
# ★ 5. 管理保留タスクの集計関数
# ==========================================
def get_su_pending_count() -> int:
    """管理者が処理すべき未対応件数（審議待ち投稿＋未対応チケット＋承認待ちユーザー）の合計を取得"""
    try:
        # 1. 審議待ち投稿の件数 (status = 'pending')
        pending_posts_count = len(fetch_pending_posts())

        # 2. 未対応チケットの件数 (status = 'unread')
        tickets = fetch_support_tickets()
        pending_tickets_count = len([t for t in tickets if t.get('status') == 'unread'])

        # 3. 承認待ちユーザーの件数 (status = 'pending')
        pending_users_count = len(fetch_pending_users())

        return pending_posts_count + pending_tickets_count + pending_users_count
    except Exception as e:
        print(f"💡 [管理タスクカウントエラー] {e}")
        return 0

# ==========================================
# ★ NG審議履歴（監査ログ）関連
# ==========================================
def fetch_ng_history_logs():
    """NG審議の履歴をデータベースから取得（最新20件）"""
    response = supabase.table("ng_history") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(20) \
        .execute()
    return response.data if response.data else []

def insert_ng_history_log(user_id: str, user_name: str, avatar_url: str, title: str, content: str, action: str):
    """NG審議の結果をデータベースに保存"""
    data = {
        "target_user_id": user_id,
        "user_name": user_name,
        "avatar_url": avatar_url,
        "title": title,
        "content": content,
        "action": action
    }
    supabase.table("ng_history").insert(data).execute()