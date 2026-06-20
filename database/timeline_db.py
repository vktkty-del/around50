# database/timeline_db.py
from config.supabase_config import get_supabase
supabase = get_supabase()

from datetime import datetime, timezone, timedelta

def add_like(post_id: str):
    """いいね数を+1する"""
    supabase.rpc('increment_likes', {'row_id': post_id}).execute()

def create_post(user_id: str, content: str, image_url: str = None, allow_chat: bool = False, title: str = None, status: str = 'approved', highlighted_content: str = None):
    """タイムラインに新規投稿を作成する（NGワードによるステータス管理対応）"""
    data = {
        "user_id": user_id,
        "content": content,
        "image_url": image_url,
        "allow_chat": allow_chat,
        "status": status
    }
    
    # タイトルが入力されていれば保存データに追加
    if title:
        data["title"] = title
    
    # SUが確認するためのハイライトテキスト
    if highlighted_content:
        data["highlighted_content"] = highlighted_content
        
    response = supabase.table("timeline_posts").insert(data).execute()
    return response.data

def delete_post(post_id: str):
    """投稿または返信を論理削除する"""
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("timeline_posts").update({"deleted_at": now_iso}).eq("id", post_id).execute()

def update_post_content(post_id: str, new_content: str, status: str = 'approved', highlighted_content: str = None):
    """投稿や返信の内容を更新（編集）する"""
    data = {"content": new_content, "status": status}
    if highlighted_content is not None:
        data["highlighted_content"] = highlighted_content
    supabase.table("timeline_posts").update(data).eq("id", post_id).execute()

def add_reply_and_return(post_id: str, user_id: str, content: str, status: str = 'approved', highlighted_content: str = None):
    """返信をDBに保存し、登録された新しいレコードを確実に返す"""
    data = {
        "user_id": user_id,
        "content": content,
        "parent_id": post_id,
        "status": status
    }
    if highlighted_content:
        data["highlighted_content"] = highlighted_content
        
    response = supabase.table("timeline_posts").insert(data).execute()
    
    # 1. 通常通り、インサート結果からデータが戻ってきた場合はそれを返す
    if response.data:
        return response.data[0]
        
    # ★ 修正: SDKのバージョン違い等でインサートデータが空で戻ってきた場合、
    # 今登録したばかりのコメントをデータベースから100%確実に再取得して返します
    try:
        fallback_res = supabase.table("timeline_posts")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("parent_id", post_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if fallback_res.data:
            return fallback_res.data[0]
    except Exception as e:
        print(f"💡 [返信リトライ取得失敗] {e}")
        
    return None

# 追加: ピン留め状態を切り替える関数
def toggle_pin_status(post_id: str, current_status: bool):
    """SUが投稿をピン留め/解除する"""
    new_status = not current_status
    supabase.table("timeline_posts").update({"is_pinned": new_status}).eq("id", post_id).execute()
    return new_status

def fetch_timeline_posts():
    """タイムラインの投稿を取得（削除済を除外、pendingを除外、返信は親に紐付ける）"""
    response = supabase.table("timeline_posts") \
        .select("*, profiles(name, avatar_url, role)") \
        .is_("deleted_at", "null") \
        .or_("status.eq.approved,status.is.null") \
        .order("is_pinned", desc=True) \
        .order("created_at", desc=True) \
        .limit(200) \
        .execute()
    
    main_posts = []
    replies_dict = {}

    # 有効なチャットルームIDの一覧
    active_room_ids = set()
    if response.data:
        room_ids = [row["chat_room_id"] for row in response.data if row.get("chat_room_id")]
        if room_ids:
            try:
                rooms_res = supabase.table("chat_rooms").select("id").in_("id", room_ids).execute()
                if rooms_res.data:
                    active_room_ids = {str(r["id"]) for r in rooms_res.data}
            except Exception as e:
                print(f"💡 [timeline_db] チャットルーム実在確認に失敗: {e}")
                active_room_ids = {str(rid) for rid in room_ids}

    # ★ 追加：共有メモリ(GLOBAL_CHAT_VIEWERS)から、現在閲覧中のメンバーを取得
    from database.chat_db import GLOBAL_CHAT_VIEWERS
    import time
    now = time.time()

    def get_time_str(raw_time):
        time_str = ""
        if raw_time:
            try:
                dt = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
                jst_dt = dt.astimezone(timezone(timedelta(hours=9)))
                time_str = jst_dt.strftime('%Y/%m/%d %H:%M')
            except: pass
        return time_str

    if response.data:
        for row in response.data:
            profile = row.get("profiles") or {}
            
            chat_room_id = row.get("chat_room_id")
            if chat_room_id:
                if str(chat_room_id) not in active_room_ids:
                    chat_room_id = None
                    try:
                        supabase.table("timeline_posts").update({"chat_room_id": None}).eq("id", row["id"]).execute()
                    except: pass

            # ★ 変更：現在その部屋をリアルタイムに開いているユーザーのアバターをメモリから抽出
            participants = []
            if chat_room_id:
                room_id_str = str(chat_room_id)
                viewers = GLOBAL_CHAT_VIEWERS.get(room_id_str, {})
                for uid, info in list(viewers.items()):
                    # 有効期限内のユーザーのアバターを追加
                    if info.get('expire', 0) > now:
                        avatar_url = info.get('avatar_url')
                        if avatar_url and avatar_url not in participants:
                            participants.append(avatar_url)

            post_data = {
                "id": row["id"],
                "user_id": row["user_id"],
                "content": row["content"],
                "title": row.get("title"),
                "image_url": row.get("image_url"),
                "allow_chat": row.get("allow_chat", False),
                "chat_room_id": chat_room_id,
                "participants": participants, # リアルタイム参加者アバター
                "likes_count": row.get("likes_count") or 0,
                "parent_id": row.get("parent_id"),
                "status": row.get("status", "approved"),
                "is_pinned": row.get("is_pinned", False),
                "user_name": profile.get("name", "名無し"),
                "avatar_url": profile.get("avatar_url"),
                "role": profile.get("role"),
                "time_str": get_time_str(row.get("created_at"))
            }
            
            if row.get("parent_id"):
                pid = row["parent_id"]
                if pid not in replies_dict:
                    replies_dict[pid] = []
                replies_dict[pid].append(post_data)
            else:
                post_data["replies"] = []
                main_posts.append(post_data)
        
        for post in main_posts:
            if post["id"] in replies_dict:
                post["replies"] = replies_dict[post["id"]][::-1]

    return main_posts

def subscribe_to_timeline(callback):
    return supabase.table("timeline_posts").on("UPDATE", callback).subscribe()

def get_user_like_status(post_id, user_id):
    res = supabase.table("likes").select("id").eq("post_id", post_id).eq("user_id", user_id).execute()
    return len(res.data) > 0

def toggle_like(post_id, user_id):
    res = supabase.table("likes").select("id").eq("post_id", post_id).eq("user_id", user_id).execute()
    if res.data:
        supabase.table("likes").delete().eq("id", res.data[0]['id']).execute()
        supabase.table("timeline_posts").update({"likes_count": supabase.table("timeline_posts").select("likes_count").eq("id", post_id).single().execute().data['likes_count'] - 1}).eq("id", post_id).execute()
        return False
    else:
        supabase.table("likes").insert({"post_id": post_id, "user_id": user_id}).execute()
        supabase.table("timeline_posts").update({"likes_count": supabase.table("timeline_posts").select("likes_count").eq("id", post_id).single().execute().data['likes_count'] + 1}).eq("id", post_id).execute()
        return True

def get_user_role(user_id: str) -> str:
    res = supabase.table("profiles").select("role").eq("id", user_id).execute()
    if res.data:
        return res.data[0].get("role", "User")
    return "User"

def link_chat_room_to_post(post_id: str, room_id: str):
    """タイムラインの投稿に作成したチャットルームのIDを紐付ける"""
    supabase.table("timeline_posts").update({"chat_room_id": room_id}).eq("id", post_id).execute()

def update_full_post(post_id: str, new_title: str, new_content: str, image_url: str = None, status: str = 'approved', highlighted_content: str = None):
    """投稿のタイトル、本文、画像をフルアップデート（編集）する"""
    data = {
        "title": new_title,
        "content": new_content,
        "image_url": image_url,
        "status": status
    }
    if highlighted_content is not None:
        data["highlighted_content"] = highlighted_content
    supabase.table("timeline_posts").update(data).eq("id", post_id).execute()