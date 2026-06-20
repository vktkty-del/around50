# database/scoring_db.py
from config.supabase_config import get_supabase
from datetime import datetime, timezone, timedelta

# スコアの重み付け定義
SCORE_CONFIG = {
    'event': 20,     # イベント【出席】
    'comment': 5,    
    'like': 2,       
    'login': 1,      # ログインボーナス
    'auto_recovery': 0.98, # サイレント自動回復
    'penalty_ng': -10,     # NG否認時のペナルティ
    'penalty_cancel': -20,  # ドタキャン時のペナルティ
    'review': 10
}

def calculate_user_level(total_score: float) -> str:
    """トータルスコアから表示用のレベル文字列（LV.0〜MAX）を計算する共通関数"""
    if total_score is None:
        total_score = 0.0
    
    lv = int(float(total_score) // 20) + 1
    
    if lv <= 0:
        return "LV.0"
    elif lv >= 100:
        return "MAX"
    else:
        return f"LV.{lv}"

def get_user_level_raw(total_score: float) -> int:
    """計算用の生のレベル数値を返す（上限なし、下限0）"""
    if total_score is None:
        total_score = 0.0
    lv = int(float(total_score) // 20) + 1
    return max(0, lv)

def check_and_award_login_bonus(user_id: str):
    """1日1回のログインボーナスと自動回復を付与する関所"""
    sb = get_supabase()
    jst = timezone(timedelta(hours=9))
    today_str = datetime.now(jst).date().isoformat()
    
    try:
        res = sb.table("profiles").select("is_tester, last_login_date").eq("id", user_id).single().execute()
        if not res.data:
            return
            
        # 開発者フラグが立っている場合はスコア暴走を防ぐため完全スルー
        if res.data.get('is_tester'):
            return 
            
        last_login = res.data.get('last_login_date')
        if last_login == today_str:
            return # 今日の分はすでに受け取り済み
            
        # ログインボーナス (+1.0pt) を interactions に記録
        sb.table("interactions").insert({
            "user_id": user_id,
            "interaction_type": "login",
            "points": SCORE_CONFIG['login']
        }).execute()
        
        # 初回登録じゃなければ、裏で自動回復 (+0.98pt) も付与
        if last_login:
            sb.table("interactions").insert({
                "user_id": user_id,
                "interaction_type": "auto_recovery",
                "points": SCORE_CONFIG['auto_recovery']
            }).execute()
            
        # 最終ログイン日を今日に更新して、スコアを再計算
        sb.table("profiles").update({"last_login_date": today_str}).eq("id", user_id).execute()
        update_user_total_score(user_id)
        
    except Exception as e:
        print(f"❌ [ログインボーナス付与エラー]: {e}")

def log_interaction(user_id: str, interaction_type: str, source_id: str = None) -> bool:
    sb = get_supabase()
    points = SCORE_CONFIG.get(interaction_type, 0)
    
    if points == 0:
        return False
        
    try:
        sb.table("interactions").insert({
            "user_id": user_id,
            "interaction_type": interaction_type,
            "source_id": source_id,
            "points": points
        }).execute()
        
        update_user_total_score(user_id)
        return True
    except Exception as e:
        print(f"❌ [log_interaction エラー]: {e}")
        return False

def record_event_attendance(user_id: str, event_id: str) -> bool:
    sb = get_supabase()
    try:
        existing = sb.table("event_attendance").select("id").eq("user_id", user_id).eq("event_id", event_id).execute()
        if not existing.data:
            sb.table("event_attendance").insert({"user_id": user_id, "event_id": event_id}).execute()
            update_user_total_score(user_id)
            return True
        return False
    except Exception as e:
        print(f"❌ [record_event_attendance エラー]: {e}")
        return False

def remove_event_attendance(user_id: str, event_id: str) -> bool:
    sb = get_supabase()
    try:
        sb.table("event_attendance").delete().eq("user_id", user_id).eq("event_id", event_id).execute()
        update_user_total_score(user_id)
        return True
    except Exception as e:
        print(f"❌ [remove_event_attendance エラー]: {e}")
        return False

def update_user_total_score(user_id: str) -> float:
    """イベント出席と日常アクションを合算して numeric 型の total_score を更新"""
    sb = get_supabase()
    try:
        events_check = sb.table("event_attendance").select("id", count="exact").eq("user_id", user_id).execute()
        event_count = events_check.count if events_check.count is not None else len(events_check.data)
        event_points = float(event_count * SCORE_CONFIG['event'])
        
        interaction_check = sb.table("interactions").select("points").eq("user_id", user_id).execute()
        interaction_points = sum(float(item.get('points', 0)) for item in interaction_check.data)
        
        new_total = event_points + interaction_points
        
        sb.table("profiles").update({"total_score": new_total, "last_active_at": "now()"}).eq("id", user_id).execute()
        return new_total
    except Exception as e:
        print(f"❌ [update_user_total_score エラー]: {e}")
        return 0.0

def get_frequent_companions(user_id: str, limit: int = 3) -> list:
    sb = get_supabase()
    try:
        my_events_res = sb.table("event_attendance").select("event_id").eq("user_id", user_id).execute()
        my_event_ids = [item['event_id'] for item in my_events_res.data if 'event_id' in item]
        if not my_event_ids: return []
            
        companions_res = sb.table("event_attendance").select("user_id").in_("event_id", my_event_ids).neq("user_id", user_id).execute()
        if not companions_res.data: return []
            
        counts = {}
        for item in companions_res.data:
            c_id = item['user_id']
            counts[c_id] = counts.get(c_id, 0) + 1
            
        sorted_companions = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        result_list = []
        for c_id, count in sorted_companions:
            profile_res = sb.table("profiles").select("name, avatar_url").eq("id", c_id).single().execute()
            if profile_res.data:
                result_list.append({
                    "user_id": c_id,
                    "name": profile_res.data.get("name", "名無し"),
                    "avatar_url": profile_res.data.get("avatar_url", ""),
                    "common_count": count
                })
        return result_list
    except Exception as e:
        print(f"❌ [get_frequent_companions エラー]: {e}")
        return []