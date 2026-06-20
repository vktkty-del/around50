# database/flat_db.py
from config.supabase_config import get_supabase
from datetime import datetime, timedelta, timezone
import random
import base64
from database.chat_db import create_chat_room
from database.profile_db import get_safe_profile

supabase = get_supabase()

# ==========================================
# 匿名ガード用 辞書データ（100x100）
# ==========================================
ADJECTIVES = [
    "腹ペコな", "喉カラカラな", "糖分を欲する", "カフェイン依存の", "飲み足りない", "胃袋無限大の", "スパイスを求める", "炭水化物大好き", "塩分控えめな", "辛党の",
    "甘党の", "限界突破した", "食べ盛りの", "ほろ酔いの", "泥酔一歩手前の", "締めのラーメンを狙う", "おつまみ探しの", "焼肉気分の", "お冷待ちの", "アルコール消毒済みの",
    "定時退社した", "残業明けの", "現実逃避中の", "連休が待ち遠しい", "休日出勤した", "有休消化中の", "納期前の", "満員電車を耐え抜いた", "リモートワーク疲れの", "ノー残業デーの",
    "華金の", "給料日前の", "ボーナス直後の", "現実逃避の", "脳みそ溶けかけの", "燃え尽きた", "覚醒した", "迷走中の", "修羅場を抜けた", "悟りを開いた",
    "低速走行中の", "アイドリング中の", "バッテリー残量1%の", "通信制限の", "フリーズした", "迷子の", "挙動不審な", "テンション高めの", "癒やしを求める", "黄昏時の",
    "夜行性の", "太陽が眩しい", "筋肉痛の", "サウナ上がりの", "ととのった", "湯冷めした", "睡眠不足の", "快眠した", "絶好調な", "完全に理解した",
    "終電を逃した", "改札前をウロウロする", "道に迷った", "待ち合わせ中の", "暇を持て余した", "散歩中の", "走り出した", "立ち止まった", "深呼吸する", "背伸びした",
    "寄り道したい", "帰宅拒否症の", "冒険に出る", "財布を忘れた", "傘がない", "探し物をする", "記憶をなくした", "爆笑する", "ニヤニヤする", "ぼーっとする",
    "謎の自信に満ちた", "存在感が薄い", "オーラを放つ", "伝説の", "幻の", "野生の", "突然変異の", "宇宙と交信する", "前世が猫の", "重力に逆らう",
    "時空を歪める", "未来から来た", "過去を振り返らない", "影が薄い", "光の速さの", "規格外の", "匿名希望の", "正体不明の", "噂の", "奇跡の"
]

NOUNS = [
    "ピスタチオ", "味玉", "お通し", "枝豆の皮", "ジョッキ", "提灯", "赤ちょうちん", "焼き鳥の串", "ホッピー", "レモンサワー",
    "餃子の羽根", "チャーシュー", "メンマ", "おしぼり", "割り箸", "小皿", "メニュー表", "呼び出しボタン", "伝票", "レシート",
    "ガード下", "信号待ち", "改札口", "券売機", "終電", "始発", "終点", "ホームのベンチ", "コインロッカー", "ネオンサイン",
    "路地裏", "踏切", "電柱", "マンホール", "終電案内", "つり革", "網棚", "エスカレーター", "自動ドア", "ショーウィンドウ",
    "腹ペコダヌキ", "迷い猫", "忠犬", "ハト", "カラス", "フクロウ", "ツバメ", "ナマケモノ", "ハリネズミ", "カピバラ",
    "アザラシ", "ペンギン", "クマムシ", "恐竜", "ツチノコ", "河童", "天狗", "妖精", "モンスター", "スライム",
    "ヘルメット", "スマホ", "モバイルバッテリー", "イヤホン", "充電ケーブル", "マウス", "キーボード", "Wi-Fiルーター", "リモコン", "電卓",
    "ガチャガチャ", "クレーンゲーム", "スロットのメダル", "ICカード", "定期券", "折りたたみ傘", "エコバッグ", "マグカップ", "タンブラー", "ダンボール",
    "ピクセル", "バグ", "エラーコード", "パスワード", "ログファイル", "スキーマ", "キャッシュ", "アルゴリズム", "伏線", "オチ",
    "奇跡", "伝説", "幻影", "蜃気楼", "流れ星", "ブラックホール", "超新星", "隕石", "オーラ", "概念"
]

def generate_pseudo_name():
    return f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}"

def get_active_flats():
    # タイムゾーンを明示的にUTCにして現在時刻を取得
    now_iso = datetime.now(timezone.utc).isoformat()
    response = supabase.table("flats").select("*").gte("expires_at", now_iso).neq("status", "開催確定").is_("deleted_at", "null").execute()
    return response.data if response.data else []

def get_flat_by_id(flat_id: str):
    response = supabase.table("flats").select("*").eq("id", flat_id).execute()
    return response.data[0] if response.data else None

def create_flat_recruitment(user_id: str, capacity: int, genre: str, location: str, description: str, timing: str):
    profile = get_safe_profile(user_id)
    if genre == '👩 女子会' and profile.get('gender') != 2:
        raise ValueError("女子会の募集は女性のみ可能です。")

    # タイムゾーンを明示的にUTCにして3時間後の期限を算出
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=3)
    pseudo_name = generate_pseudo_name()
    assigned_names = {user_id: pseudo_name}
    
    flat_data = {
        "created_by": user_id,
        "pseudo_name": pseudo_name,
        "genre": genre,
        "location": location,
        "description": description,
        "timing": timing,
        "target_count": capacity,
        "participant_ids": [user_id],
        "status": "募集中",
        "expires_at": expires_at.isoformat(),
        "assigned_names": assigned_names
    }
    response = supabase.table("flats").insert(flat_data).execute()
    return response.data[0] if response.data else None


def join_flat_recruitment(flat_id: str, user_id: str) -> dict:
    response = supabase.table("flats").select("*").eq("id", flat_id).execute()
    if not response.data:
        return {"status": "error", "message": "募集が見つかりません。"}
        
    flat = response.data[0]
    participants = flat.get('participant_ids', [])
    assigned_names = flat.get('assigned_names', {})
    target_count = flat.get('target_count', 3)
    
    if user_id in participants:
        return {"status": "warning", "message": "すでにこの作戦会議に参加しています。"}
    if len(participants) >= target_count:
        return {"status": "error", "message": "申し訳ありません、たった今満員になりました！"}

    profile = get_safe_profile(user_id)
    gender = profile.get('gender', 0)
    
    # ★ 修正: 女子会の時だけ厳密に性別をチェックするように緩和
    if flat.get('genre') == '👩 女子会':
        if gender == 0:
             return {"status": "error", "message": "女子会に参加するため、プロフィールで性別を設定してください。"}
        elif gender != 2:
             return {"status": "error", "message": "この募集は女性限定です。"}
        
    new_pseudo_name = generate_pseudo_name()
    while new_pseudo_name in assigned_names.values():
        new_pseudo_name = generate_pseudo_name()
        
    participants.append(user_id)
    assigned_names[user_id] = new_pseudo_name
    
    update_data = {
        "participant_ids": participants,
        "assigned_names": assigned_names
    }
    
    if len(participants) == target_count:
        update_data["status"] = "作戦会議中"
        try:
            room_title = f"[FLAT砂場] {flat.get('genre', 'ふらっと募集')}"
            new_room = create_chat_room(title=room_title)
            if new_room:
                assigned_names["_chat_room_id"] = new_room['id']
                update_data["assigned_names"] = assigned_names
        except Exception as e:
            print(f"砂場作成エラー: {e}")
                
    supabase.table("flats").update(update_data).eq("id", flat_id).execute()
    return {"status": "success", "message": f"「{new_pseudo_name}」として混ざりました！"}


def silent_leave_flat(flat_id: str, user_id: str):
    response = supabase.table("flats").select("*").eq("id", flat_id).execute()
    if not response.data: return
    
    flat = response.data[0]
    participants = flat.get('participant_ids', [])
    assigned_names = flat.get('assigned_names', {}) or {}
    
    if user_id in participants:
        participants.remove(user_id)
        
    if "_chat_room_id" in assigned_names:
        del assigned_names["_chat_room_id"]
        
    if user_id in assigned_names:
        del assigned_names[user_id]
        
    approved_users = assigned_names.get('approved_user_ids', [])
    if user_id in approved_users:
        approved_users.remove(user_id)
        assigned_names['approved_user_ids'] = approved_users
        
    update_data = {
        "participant_ids": participants,
        "assigned_names": assigned_names,
        "status": "募集中" 
    }
    supabase.table("flats").update(update_data).eq("id", flat_id).execute()


def approve_flat_recruitment(flat_id: str, user_id: str):
    response = supabase.table("flats").select("*").eq("id", flat_id).execute()
    if not response.data: return {"status": "error"}
    
    flat = response.data[0]
    assigned_names = flat.get('assigned_names', {})
    approved_users = assigned_names.get('approved_user_ids', [])
    participants = flat.get('participant_ids', [])
    
    if user_id not in approved_users:
        approved_users.append(user_id)
        assigned_names['approved_user_ids'] = approved_users
        
    is_fully_approved = len(approved_users) >= len(participants) and len(participants) > 0
    
    update_data = {"assigned_names": assigned_names}
    if is_fully_approved:
        update_data["status"] = "開催確定"
        
    supabase.table("flats").update(update_data).eq("id", flat_id).execute()
    
    if is_fully_approved:
        str_participant_ids = [str(pid) for pid in participants]
        genre = flat.get('genre', 'ふらっと')
        chat_room_id = assigned_names.get('_chat_room_id') 
        
        if chat_room_id:
            try:
                new_title = f"【🎉開催確定🍻】{genre}"
                supabase.table("chat_rooms").update({"title": new_title}).eq("id", chat_room_id).execute()
            except Exception as e:
                print(f"チャットルーム名更新エラー: {e}")

        timing = flat.get('timing', '[即]今すぐ')
        now = datetime.now(timezone.utc)
        event_datetime = now
        
        if "[1H]" in timing or "1時間後" in timing:
            event_datetime = now + timedelta(hours=1)
        elif "[夜]" in timing or "夜から" in timing:
            night_time = now.replace(hour=19, minute=0, second=0, microsecond=0)
            if now >= night_time:
                night_time += timedelta(days=1)
            event_datetime = night_time
            
        event_date_str = event_datetime.strftime("%Y-%m-%d %H:%M")

        event_data = {
            "title": f"【即飲み成立🍻】{genre}",
            "event_date": event_date_str,  
            "location": flat.get('location', '場所未定'),
            "description": flat.get('description', '') + "\n\n※このイベントは「ふらっと(即飲み)」の作戦会議から成立・昇格しました！",
            "created_by": flat.get('created_by'),
            "genre": genre,
            "participants_count": len(participants),
            "participant_ids": str_participant_ids,
            "color_class": "bg-amber-600",
            "details": chat_room_id 
        }
        try:
            supabase.table("events").insert(event_data).execute()
        except Exception as e:
            print(f"イベント昇格エラー: {e}")
            
    return {"status": "success", "is_fully_approved": is_fully_approved}

def delete_flat_recruitment(flat_id: str):
    try:
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("flats").update({"deleted_at": now}).eq("id", flat_id).execute()
        return True
    except Exception as e:
        print(f"Delete flat error: {e}")
        return False