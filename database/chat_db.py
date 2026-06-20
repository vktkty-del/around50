# database/chat_db.py
from config.supabase_config import get_supabase
supabase = get_supabase()
import os
import time
import urllib.parse
import urllib.request

# ==========================================
# ★ サーバー共通：リアルタイム同期用のインメモリキャッシュ
# ==========================================
# 1. 閲覧中ユーザーの管理
# 構造: { room_id_str: { user_id_str: { 'avatar_url': url, 'expire': timestamp } } }
GLOBAL_CHAT_VIEWERS = {}

# 2. 【ノック機能】SUの入室リクエスト管理
# 構造: { room_id_str: { su_user_id_str: { 'name': str, 'expire': timestamp, 'approved': bool } } }
GLOBAL_KNOCK_REQUESTS = {}

# 3. ★ 新規追記: タイピング中ユーザーの管理（インポートエラー対策）
# 構造: { room_id_str: { user_id_str: { 'expire': timestamp, 'name': str } } }
GLOBAL_TYPING_STATE = {}


def fetch_chat_rooms():
    try:
        response = supabase.table("chat_rooms").select("*").order("created_at", desc=False).execute()
        rooms = response.data if response.data else []
        
        # ★ 修正: 公式昇格前（タイトルが [FLAT砂場] で始まるもの）は、
        # チャット一覧に一切表示させない（シークレット化する）
        return [r for r in rooms if not r.get('title', '').startswith('[FLAT砂場]')]
        
    except Exception as e:
        print(f"Error fetching chat rooms: {e}")
        return []

def fetch_messages(room_id: str):
    """特定の部屋のメッセージを取得"""
    response = supabase.table("chat_messages").select("*, profiles(name, avatar_url)").eq("room_id", room_id).order("created_at", desc=False).execute()
    return response.data if response.data else []

def create_chat_room(title: str, created_by: str = None, genre: str = "daily", description: str = None, password: str = None):
    """新しいチャットルームを作成する（ジャンル・説明・合言葉対応）"""
    data = {
        "title": title,
        "genre": genre or "daily"
    }
    if created_by:
        data["created_by"] = created_by
    if description:
        data["description"] = description.strip()
    if password and password.strip():
        data["password"] = password.strip()
        
    response = supabase.table("chat_rooms").insert(data).execute()
    return response.data[0] if response.data else None

def send_message(room_id: str, user_id: str, message: str, image_url: str = None):
    """メッセージを送信"""
    data = {
        "room_id": room_id,
        "user_id": user_id,
        "message": message,
        "image_url": image_url,
        "read_user_ids": [user_id]
    }
    supabase.table("chat_messages").insert(data).execute()

def save_chat_image_local(file_bytes: bytes, filename: str) -> str:
    """画像をローカルに保存して公開URLパスを返す"""
    save_dir = "static/chat"
    os.makedirs(save_dir, exist_ok=True)
    
    safe_filename = urllib.parse.quote(filename)
    unique_filename = f"{int(time.time())}_{safe_filename}"
    filepath = os.path.join(save_dir, unique_filename)
    
    with open(filepath, 'wb') as f:
        f.write(file_bytes)
    return f"/static/chat/{unique_filename}"

def mark_as_read(room_id: str, user_id: str):
    """部屋を開いた時、未読のメッセージに自分のIDを追加する"""
    response = supabase.table("chat_messages") \
        .select("id, read_user_ids") \
        .eq("room_id", room_id) \
        .execute()
        
    messages = response.data if response.data else []
    for msg in messages:
        current_readers = msg.get("read_user_ids", [])
        if current_readers is None:
            current_readers = []
        if user_id not in current_readers:
            current_readers.append(user_id)
            supabase.table("chat_messages") \
                .update({"read_user_ids": current_readers}) \
                .eq("id", msg["id"]) \
                .execute()

def delete_chat_room(room_id: str):
    """チャットルームを削除する"""
    supabase.table("timeline_posts").update({"chat_room_id": None}).eq("chat_room_id", room_id).execute()
    supabase.table("chat_messages").delete().eq("room_id", room_id).execute()
    supabase.table("chat_rooms").delete().eq("id", room_id).execute()

def delete_message(message_id: str):
    """個別のメッセージを削除する"""
    supabase.table("chat_messages").delete().eq("id", message_id).execute()

def update_chat_message(message_id: str, new_message: str):
    """個別のメッセージ内容を更新する"""
    supabase.table("chat_messages").update({"message": new_message}).eq("id", message_id).execute()

def fetch_active_chat_rooms():
    """過去イベントのチャットルームを除外した、有効なチャットルーム一覧を取得"""
    rooms = fetch_chat_rooms()
    try:
        from config.supabase_config import get_supabase
        from dateutil import parser as date_parser
        from datetime import datetime, timezone
        sb = get_supabase()
        
        events_res = sb.table("events").select("details, event_date").not_.is_("details", "null").execute()
        past_room_ids = []
        
        if events_res.data:
            now_time = datetime.now()
            for ev in events_res.data:
                ev_date_str = ev.get('event_date')
                room_id = ev.get('details')
                if ev_date_str and room_id:
                    try:
                        ev_dt = date_parser.parse(ev_date_str)
                        is_past = False
                        if ev_dt.tzinfo is not None:
                            now_utc = datetime.now(timezone.utc)
                            is_past = ev_dt < now_utc
                        else:
                            is_past = ev_dt < now_time
                            
                        if is_past:
                            past_room_ids.append(str(room_id))
                    except Exception:
                        pass
        
        rooms = [r for r in rooms if str(r['id']) not in past_room_ids]
    except Exception as e:
        print(f"Error filtering active rooms: {e}")
    return rooms

def get_room_last_message_time(room_id: str):
    """最新メッセージの送信時刻を取得"""
    try:
        response = supabase.table("chat_messages") \
            .select("created_at") \
            .eq("room_id", room_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        if response.data:
            return response.data[0].get('created_at')
    except Exception as e:
        print(f"Error getting last message time: {e}")
    return None

def add_reaction(message_id: str, user_id: str, emoji: str):
    """メッセージにリアクションを追加/削除"""
    try:
        res = supabase.table("chat_messages").select("reactions").eq("id", message_id).execute()
        if not res.data:
            return
        
        reactions = res.data[0].get("reactions") or {}
        if not isinstance(reactions, dict):
            reactions = {}
            
        if emoji not in reactions:
            reactions[emoji] = []
            
        if user_id in reactions[emoji]:
            reactions[emoji].remove(user_id)
            if not reactions[emoji]:
                del reactions[emoji]
        else:
            reactions[emoji].append(user_id)
            
        supabase.table("chat_messages").update({"reactions": reactions}).eq("id", message_id).execute()
    except Exception as e:
        print(f"Error handling reaction: {e}")
        raise Exception("リアクション処理に失敗しました。")

def save_stamp_locally(stamp_url: str) -> str:
    """外部のスタンプ画像をローカルに保存して公開パスを返す"""
    save_dir = "static/stamps"
    os.makedirs(save_dir, exist_ok=True)
    
    parsed_url = urllib.parse.urlparse(stamp_url)
    filename = os.path.basename(parsed_url.path)
    if not filename:
        filename = f"stamp_{int(time.time())}.svg"
        
    filepath = os.path.join(save_dir, filename)
    if os.path.exists(filepath):
        return f"/static/stamps/{filename}"
        
    try:
        req = urllib.request.Request(stamp_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        return f"/static/stamps/{filename}"
    except Exception as e:
        print(f"Error downloading stamp: {e}")
    return stamp_url


# ==========================================
# ★ 追加：【ノック機能】リアルタイム処理関数群
# ==========================================
def send_knock_request(room_id: str, su_id: str, su_name: str):
    """【ノック機能】SUが鍵部屋に対して入室要請を送信する（インメモリ）"""
    room_id = str(room_id)
    su_id = str(su_id)
    if room_id not in GLOBAL_KNOCK_REQUESTS:
        GLOBAL_KNOCK_REQUESTS[room_id] = {}
        
    GLOBAL_KNOCK_REQUESTS[room_id][su_id] = {
        'name': su_name,
        'expire': time.time() + 30,  # 30秒間有効
        'approved': False
    }

def check_knock_status(room_id: str, su_id: str) -> bool:
    """【ノック機能】SU側が入室許可（承認）が下りたかをポーリング監視する"""
    room_id = str(room_id)
    su_id = str(su_id)
    if room_id in GLOBAL_KNOCK_REQUESTS and su_id in GLOBAL_KNOCK_REQUESTS[room_id]:
        req = GLOBAL_KNOCK_REQUESTS[room_id][su_id]
        if req['expire'] > time.time():
            return req['approved']
    return False

def approve_knock_request(room_id: str, su_id: str):
    """【ノック機能】一般メンバーが、SUから届いた入室要請を「許可」する"""
    room_id = str(room_id)
    su_id = str(su_id)
    if room_id in GLOBAL_KNOCK_REQUESTS and su_id in GLOBAL_KNOCK_REQUESTS[room_id]:
        GLOBAL_KNOCK_REQUESTS[room_id][su_id]['approved'] = True

def fetch_pending_knocks(room_id: str):
    """【ノック機能】一般メンバーが、現在自分のいる部屋に届いているノック一覧を取得する"""
    room_id = str(room_id)
    now = time.time()
    pending = []
    
    if room_id in GLOBAL_KNOCK_REQUESTS:
        for su_id, info in list(GLOBAL_KNOCK_REQUESTS[room_id].items()):
            if info['expire'] > now and not info['approved']:
                pending.append({
                    'su_id': su_id,
                    'name': info['name']
                })
    return pending