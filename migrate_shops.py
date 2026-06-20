# migrate_shops.py
import os
import re
from dotenv import load_dotenv
from config.supabase_config import get_supabase

# 環境変数の読み込みとSupabaseクライアントの初期化
load_dotenv(override=True)
supabase = get_supabase()

def get_or_create_shop(name: str, url: str, image_url: str):
    """URLをキーにしてお店を検索し、なければ新規作成する"""
    try:
        if url and url.strip():
            res = supabase.table("shops").select("*").eq("url", url).execute()
            if res.data:
                return res.data[0]
        
        # ない場合は新規作成
        data = {
            "name": name if name else "不明な店舗", 
            "url": url if url else None, 
            "image_url": image_url
        }
        ins_res = supabase.table("shops").insert(data).execute()
        return ins_res.data[0] if ins_res.data else None
    except Exception as e:
        print(f"Shop creation error: {e}")
        return None

def run_migration():
    print("🚀 過去のイベントの「お店データ」自動紐付けを開始します...")
    
    try:
        # 1. すべてのイベントを取得
        events_res = supabase.table("events").select("*").execute()
        events = events_res.data or []
        
        success_count = 0
        skip_count = 0
        
        for ev in events:
            # 既に shop_id が入っている場合はスキップ
            if ev.get("shop_id"):
                skip_count += 1
                continue
                
            ev_id = ev["id"]
            url = ev.get("url") or ""
            image_url = ev.get("image_url")
            desc = ev.get("description") or ""
            
            # 2. 過去の description の中から 【店名】〇〇 を救出する
            shop_name = ""
            shop_match = re.search(r'【店名】([^\n]+)', desc)
            if shop_match:
                shop_name = shop_match.group(1).strip()
            elif ev.get("location"):
                # 店名がない場合は、場所（location）を仮の店名とする
                shop_name = ev.get("location")
            else:
                shop_name = ev.get("title", "不明なイベント会場")

            # 3. shopsテーブルにお店を登録（または取得）
            shop = get_or_create_shop(shop_name, url, image_url)
            
            if shop and shop.get("id"):
                # 4. 過去のイベントに新しい shop_id を書き込む！
                supabase.table("events").update({"shop_id": shop["id"]}).eq("id", ev_id).execute()
                print(f"✅ イベント「{ev.get('title')}」を お店「{shop_name}」に紐付けました！")
                success_count += 1
            else:
                print(f"⚠️ イベント「{ev.get('title')}」の紐付けに失敗しました。")
                
        print("-" * 40)
        print(f"🎉 マイグレーション完了！")
        print(f"更新成功: {success_count}件")
        print(f"スキップ (紐付け済): {skip_count}件")
        
    except Exception as e:
        print(f"🚨 エラーが発生しました: {e}")

if __name__ == "__main__":
    run_migration()