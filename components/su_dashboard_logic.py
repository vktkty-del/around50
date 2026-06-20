# components/su_dashboard_logic.py
import base64
import threading
import requests
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from dateutil import tz
from config.supabase_config import get_supabase

# ==========================================
# ユーティリティ・フォーマッター
# ==========================================
def get_avatar_url(url, name):
    if url and str(url).strip() and str(url).strip().lower() not in ["none", "null", ""]:
        return url
    safe_seed = base64.urlsafe_b64encode(str(name or "名無し").encode()).decode()[:15]
    return f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}"

def format_datetime_string(raw_date_str: str, include_seconds: bool = True) -> str:
    """世界標準時 (UTC) を日本時間 (JST / Asia/Tokyo) に変換する"""
    if not raw_date_str:
        return "不明"
    try:
        dt = date_parser.isoparse(raw_date_str)
        jst_tz = tz.gettz('Asia/Tokyo')
        dt_jst = dt.astimezone(jst_tz)
        if include_seconds:
            return dt_jst.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return dt_jst.strftime("%Y-%m-%d %H:%M")
    except Exception:
        try:
            dt = date_parser.parse(raw_date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.tzutc())
            jst_tz = tz.gettz('Asia/Tokyo')
            dt_jst = dt.astimezone(jst_tz)
            if include_seconds:
                return dt_jst.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return dt_jst.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw_date_str

def format_time(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.astimezone(timezone(timedelta(hours=9))).strftime('%m/%d %H:%M')
    except:
        return ""

def parse_user_agent(ua_string: str) -> str:
    if not ua_string or str(ua_string).strip() == "":
        return "不明なデバイス"
    
    ua = ua_string.lower()
    
    if "googlebot" in ua: return "🤖 Google Bot"
    if "bingbot" in ua: return "🤖 Bing Bot"
    if "spider" in ua or "bot" in ua or "crawl" in ua: return "🤖 クローラーBot"
    
    os_name = "不明"
    if "iphone" in ua: os_name = "iPhone"
    elif "ipad" in ua: os_name = "iPad"
    elif "android" in ua: os_name = "Android"
    elif "windows" in ua: os_name = "Windows"
    elif "macintosh" in ua: os_name = "Mac"
    
    browser_name = "ブラウザ"
    if "line/" in ua: browser_name = "LINE"
    elif "instagram" in ua: browser_name = "Insta"
    elif "twitter" in ua or "t.co/" in ua: browser_name = "Xアプリ"
    elif "chrome" in ua: browser_name = "Chrome"
    elif "safari" in ua: browser_name = "Safari"
    
    device_icon = "📱" if os_name in ["iPhone", "iPad", "Android"] else "💻"
    return f"{device_icon} {os_name} ({browser_name})"

# ==========================================
# データベース操作関数
# ==========================================
def insert_access_log(user_name: str, action: str, ip_address: str, user_agent_raw: str = None):
    try:
        sb = get_supabase()
        res = sb.table("access_logs").select("user_name, action, created_at").order("created_at", desc=True).limit(1).execute()
        if res.data:
            last_log = res.data[0]
            if last_log.get('user_name') == user_name and last_log.get('action') == action:
                try:
                    last_time = date_parser.isoparse(last_log.get('created_at'))
                    if (datetime.now(timezone.utc) - last_time).total_seconds() < 5:
                        return True
                except Exception:
                    pass
        
        def worker():
            location = "ローカル / 不明"
            if ip_address and ip_address not in ["127.0.0.1", "0.0.0.0"] and not ip_address.startswith("192.168."):
                try:
                    response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=1.0)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            country_code = data.get('countryCode', '')
                            flag = "🇯🇵 " if country_code == "JP" else f"🏳️‍🌈 ({country_code}) "
                            location = f"{flag}{data.get('country', '')} ({data.get('regionName', '')})"
                except Exception:
                    pass
            try:
                sb.table("access_logs").insert({
                    "user_name": user_name, 
                    "action": action, 
                    "ip_address": ip_address, 
                    "user_agent": user_agent_raw, 
                    "location": location
                }).execute()
                
                try:
                    rotation_check = sb.table("access_logs").select("created_at").order("created_at", desc=True).offset(500).limit(1).execute()
                    if rotation_check.data:
                        sb.table("access_logs").delete().lte("created_at", rotation_check.data[0]['created_at']).execute()
                except Exception:
                    pass
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        return True
    except Exception:
        return False

def fetch_all_users_for_admin(current_user_id: str):
    try:
        res = get_supabase().table("profiles").select("id, name, avatar_url, role, status, comment, created_at, invited_by").neq("id", current_user_id).order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"fetch_all_users_for_admin error: {e}")
        return []

def update_user_status(user_id: str, new_status: str):
    try:
        return get_supabase().table("profiles").update({"status": new_status}).eq("id", user_id).execute()
    except Exception as e:
        raise e

def update_user_role(user_id: str, new_role: str):
    try:
        return get_supabase().table("profiles").update({"role": new_role}).eq("id", user_id).execute()
    except Exception as e:
        raise e

def fetch_access_logs(limit: int = 15):
    try:
        res = get_supabase().table("access_logs").select("*").order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        print(f"fetch_access_logs error: {e}")
        return []

# ==========================================
# アナリティクスデータ集計
# ==========================================
def fetch_page_pv_data():
    """
    各ページのアクセス数（PV）の最新内訳データを取得する。
    (現在はダミーデータですが、将来的にSQL集計やテーブル取得に差し替え可能な構造にしています)
    """
    return {
        'labels': ['AI Chat', '割り勘', 'FLAT', 'イベント', 'メンバー', 'タイムライン'],
        'values': [24, 35, 48, 52, 60, 110]
    }