# database/event_db.py

from config.supabase_config import get_supabase
supabase = get_supabase()
from datetime import datetime, timedelta

def fetch_active_events():
    now = datetime.now()
    limit_time = now - timedelta(hours=12)
    
    try:
        response = supabase.table("events").select("*, profiles(name, avatar_url)").or_(
            f"deleted_at.is.null,deleted_at.gt.{limit_time.isoformat()}"
        ).order("created_at", desc=False).execute()
        
        supabase.table("events").delete().lt("deleted_at", limit_time.isoformat()).execute()
        
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []

def create_event(user_id: str, data: dict):
    data["created_by"] = user_id
    response = supabase.table("events").insert(data).execute()
    return response.data[0] if response.data else None

def soft_delete_event(event_id: str):
    now = datetime.now().isoformat()
    supabase.table("events").update({"deleted_at": now}).eq("id", event_id).execute()

def restore_event(event_id: str):
    supabase.table("events").update({"deleted_at": None}).eq("id", event_id).execute()
    
def get_active_events():
    response = supabase.table("events").select("*, profiles(name, avatar_url)").is_("deleted_at", "null").order("created_at", desc=False).execute()
    return response.data if response.data else []

def join_event(event_id: str, user_id: str):
    try:
        res = supabase.table("events").select("participant_ids").eq("id", event_id).execute()
        if not res.data: return False
        
        participants = res.data[0].get("participant_ids") or []
        if user_id not in participants:
            participants.append(user_id)
            
        update_data = {
            "participant_ids": participants,
            "participants_count": len(participants)
        }
        supabase.table("events").update(update_data).eq("id", event_id).execute()
        return True
    except Exception as e:
        print(f"Join event error: {e}")
        return False

def leave_event(event_id: str, user_id: str):
    try:
        res = supabase.table("events").select("participant_ids").eq("id", event_id).execute()
        if not res.data: return False
        
        participants = res.data[0].get("participant_ids") or []
        if user_id in participants:
            participants.remove(user_id)
            
        update_data = {
            "participant_ids": participants,
            "participants_count": len(participants)
        }
        supabase.table("events").update(update_data).eq("id", event_id).execute()
        return True
    except Exception as e:
        print(f"Leave event error: {e}")
        return False

def fetch_participant_profiles(participant_ids: list):
    if not participant_ids: return []
    try:
        res = supabase.table("profiles").select("id, name, avatar_url").in_("id", participant_ids).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Fetch participant profiles error: {e}")
        return []

def fetch_event_reviews(event_id: str):
    try:
        response = supabase.table("event_reviews").select("*, profiles(name, avatar_url, role)").eq("event_id", event_id).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Fetch event reviews error: {e}")
        return []

def submit_event_review(event_id: str, user_id: str, rating: int, tags: list, comment: str, is_anonymous: bool):
    try:
        prof_res = supabase.table("profiles").select("is_tester").eq("id", user_id).single().execute()
        is_tester = prof_res.data.get("is_tester", False) if prof_res.data else False

        data = {
            "event_id": event_id,
            "user_id": user_id,
            "rating": rating,
            "tags": tags,
            "comment": comment,
            "is_anonymous": is_anonymous
        }
        response = supabase.table("event_reviews").insert(data).execute()
        
        if response.data:
            if not is_tester:
                from database.scoring_db import log_interaction
                log_interaction(user_id, 'review', source_id=event_id)
                
            return response.data[0]
            
        return None
    except Exception as e:
        print(f"Submit event review error: {e}")
        return None

# ==========================================
# ★ 新機能：お店(shops)・リクエスト機能用の関数
# ==========================================

def get_or_create_shop(name: str, url: str = None, image_url: str = None):
    """
    URLがあればURLで、なければ店名で検索。なければ新規登録する。
    （URLがないマイナー店舗でも平等に登録・ランキング対象にするための修正）
    """
    if not name or not name.strip():
        return None
        
    try:
        # 1. URLがある場合はURLで完全一致検索
        if url and url.strip():
            res = supabase.table("shops").select("*").eq("url", url.strip()).execute()
            if res.data:
                return res.data[0]
        else:
            # 2. URLがない場合は、店名で検索（重複登録を防ぐ）
            res = supabase.table("shops").select("*").eq("name", name.strip()).execute()
            if res.data:
                return res.data[0]
        
        # 3. どちらでも見つからなければ新規作成
        data = {
            "name": name.strip(), 
            "url": url.strip() if url and url.strip() else None, 
            "image_url": image_url
        }
        ins_res = supabase.table("shops").insert(data).execute()
        return ins_res.data[0] if ins_res.data else None
    except Exception as e:
        print(f"Get or create shop error: {e}")
        return None

def submit_event_request(shop_id: str, user_id: str, comment: str):
    try:
        data = {
            "shop_id": shop_id,
            "requested_by": user_id,
            "comment": comment,
            "status": "pending"
        }
        res = supabase.table("event_requests").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Submit event request error: {e}")
        return None

def fetch_pending_requests_for_su():
    try:
        res = supabase.table("event_requests").select(
            "*, shops(*), profiles(name, avatar_url)"
        ).eq("status", "pending").order("created_at", desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Fetch pending requests error: {e}")
        return []

def update_request_status(request_id: str, status: str):
    try:
        res = supabase.table("event_requests").update({"status": status}).eq("id", request_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Update request status error: {e}")
        return None

def fetch_shop_portal_data():
    try:
        shops_res = supabase.table("shops").select("*").order("created_at", desc=True).execute()
        shops = shops_res.data if shops_res.data else []
        
        events_res = supabase.table("events").select("id, shop_id, event_date, title").not_.is_("shop_id", "null").execute()
        events = events_res.data if events_res.data else []
        
        reviews_res = supabase.table("event_reviews").select("event_id, rating, comment, is_anonymous, user_id, profiles(name, avatar_url)").execute()
        reviews = reviews_res.data if reviews_res.data else []
        
        reqs_res = supabase.table("event_requests").select("shop_id").eq("status", "pending").execute()
        requests = reqs_res.data if reqs_res.data else []

        return {
            "shops": shops,
            "events": events,
            "reviews": reviews,
            "requests": requests
        }
    except Exception as e:
        print(f"Fetch shop portal data error: {e}")
        return {"shops": [], "events": [], "reviews": [], "requests": []}