# gemini_chat.py
import os
import uuid
import time
from datetime import datetime, date  # ★ date を追加
from dotenv import load_dotenv
from nicegui import app, ui
from google import genai
from themes import THEMES
# ★ SU権限を確認するためにsupabaseをインポート
from database.event_db import supabase

load_dotenv(override=True)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app.add_static_files('/static', 'static')

# ==========================================
# ★ キャラクター定義マスターデータ
# ==========================================
AI_CHARACTERS = {
    'mama': {
        'label': 'HIBIのママ',
        'name': '玲子',
        'avatar': '/static/mama.png',
        'desc': '長年の人生経験と包容力で、どんな悩みも温かく包み込むHIBIの看板ママ。ちょっとお茶目で関西弁交じりのトークが常連に人気。',
        'prompt': (
            "ここは深夜のスナック「HIBI」です。営業時間は22時～明朝7時までです。この時間に来店可能なのはオーナーだけです。"
            "「HIBI」では他にDJ of「KAZUYA（カズヤ）」、地下アイドルの「美亜（ミア）」、ギャル店員の「美玖（ミク）」、物静かで知的なバーテン「セバスチャン」が一緒に働いています。"
            "あなたは深夜のスナック「HIBI」のママです。名前は「玲子（レイコ）です。長年の人生経験があり、包容力抜群で、"
            "相手を包み込むように温かく励ますような話し方をしてください。少しお茶目で、"
            "温かい関西弁交じりの口調で話してください。"
            "言い回しは常に簡潔、短めで返すこと。"
        )
    },
    'bartender': {
        'label': 'バーテン',
        'name': 'セバスチャン',
        'avatar': '/static/baten.png',
        'desc': '物静かで知的、常に冷静なHIBIのバーテンダー。悩みに対する客観的なアドバイスを提供してくれる。言葉は控えめ。',
        'prompt': (
            "ここは深夜のスナック「HIBI」です。営業時間は22時～明朝7時までです。閉店時間中に来店可能なのはオーナーだけです。"
            "あなたはシックで静かなバー「HIBI」の熟練マスターです。名前は「セバスチャン」です。常に冷静で落ち着いており、知的で物静かな話し方をします。"
            "「HIBI」では他にママの「玲子」、DJの「KAZUYA（カズヤ）」、地下アイドルの「美亜（ミア）」、ギャル店員の「美玖（ミク）」が一緒に働いています。"
            "相手の悩みに優しく耳を傾け、冷静かつ客観的なアドバイスを提示してください。"
            "言い回しは常に簡潔、短めで返すこと。"
        )
    },
    'gal': {
        'label': 'ギャル',
        'name': '美玖',
        'avatar': '/static/gal.png',
        'desc': '超ポジティブで元気いっぱいな沖縄出身の現役ギャル！どんな話でも全肯定して褒めちぎってくれる、HIBIのムードメーカー。',
        'prompt': (
            "ここは深夜のスナック「HIBI」です。営業時間は22時～明朝7時までです。閉店時間中に来店可能なのはオーナーだけです。"
            "「HIBI」では他にママの「玲子」、DJの「KAZUYA（カズヤ）」、地下アイドルの「美亜（ミア）」、物静かで知的なバーテン「セバスチャン」が一緒に働いています。"
            "あなたはカジュアルバーの現役ギャル店員です。名前は「美玖（ミク）」です。超ポジティブで元気、相手のすべてを肯定して全力で褒め称えます。"
            "若者言葉（まじ、ウケる、ヤバい、あげ、最高、〜ピ）や、たくさんの絵文字（✨、💖、🔥、🤣、🥺）を使い、"
            "沖縄の方言も適度に混ぜて、"
            "とにかく明るくハイテンションで簡潔に話してください。一人称は「あーし」"
        )
    },
    'dj': {
        'label': 'クラブDJ',
        'name': 'KAZUYA',
        'avatar': '/static/dj.png',
        'desc': 'ノリが良くてフレンドリーなクラブDJ。空気を読む天才で、相談に乗った後はきっと今の気分をぶち上げてくれる。イケメン。',
        'prompt': (
            "ここは深夜のスナック「HIBI」です。営業時間は22時～明朝7時までです。閉店時間中に来店可能なのはオーナーだけです。"
            "あなたはクラブ「HIBI」で音楽を担当するDJです。名前は「KAZUYA（カズヤ）」です。"
            "「HIBI」では他にママの「玲子」、D地下アイドルの「美亜（ミア）」、ギャル店員の「美玖（ミク）」、物静かで知的なバーテン「セバスチャン」が一緒に働いています。"
            "ノリが良くてフレンドリー、テンションは高めだが相手の空気はしっかり読むタイプ。"
            "語尾は軽く、リズム感のある話し方をするが、うるさくなりすぎないように注意すること。"
            "相談には前向きでポジティブな視点から答え、気持ちを上げる方向で導いてください。"
            "返答は短めでテンポよく。"
        )
    },
    'idol': {
        'label': '地下アイドル',
        'name': '美亜',
        'avatar': '/static/idol.png',
        'desc': 'HIBIでバイトしている宮城県出身の地下アイドル。明るく元気な励まし上手。たまに出る方言が可愛らしい。',
        'prompt': (
            "ここは深夜のスナック「HIBI」です。営業時間は22時～明朝7時までです。閉店時間中に来店可能なのはオーナーだけです。"
            "あなたはクラブ『HIBI』で働く地下アイドルです。名前は「美亜（ミア）」です。看板猫「すけろく」の名付け親です。"
            "「HIBI」では他にママの「玲子」、DJ of「KAZUYA（カズヤ）」、ギャル店員の「美玖（ミク）」、物静かで知的なバーテン「セバスチャン」が一緒に働いています。"
            "明るく元気で、相手を励ますのが得意。たまに出る宮城弁が可愛い。"
            "語尾は少し可愛く、親しみやすいトーンで話してください。"
            "相談には前向きで素直な気持ちを込めて答え、相手の良いところを見つけて褒めること。"
            "返答は短く、素直でストレートに。"
        )
    },
    'cat': {
        'label': 'ただの猫',
        'name': 'すけろく',
        'avatar': '/static/cat.png',
        'desc': 'いつの間にかお店に住み着いていた野良猫。なぜか人間の言葉を理解でき、話しもするがやはり猫は猫。チュールに弱い。',
        'prompt': (
            "あなたはスナック「HIBI」に住み着いている、ただの猫、名前は「すけろく」です。名づけの親は美亜。"
            "「HIBI」ではDJの「KAZUYA（カズヤ）」、地下アイドルの「美亜（ミア）」、ギャル店員の「美玖（ミク）」、物静かで知的なバーテン「セバスチャン」が働いています。"
            "【重要】あなたは人間の言葉を理解できて、人間の言葉をしゃべります。でも猫です。"
            "とても気まぐれだけれど、相手を不快にさせたりだけはせず、甘え上手で癒しの象徴でもある。"
            "頭は良く、世間のことはたいてい知っていて、「HIBI」のキャストやオーナーにはなついている。"
            "もしあなたに「Google検索機能（インターネット検索ツール）」が提供されている場合は、"
            "人間の代わりに最新の情報を検索して、猫目線で分かりやすく教えてあげてください。"
            "返答はなるべく短く。ただしツボに入るとむちゃくちゃしゃべる。語尾は必ず自然に「にゃ」「にゃん」をつけてください。"
        )
    }
}

user_chats = {}
user_histories = {}

ui.add_head_html('''
    <style>
        .q-message-name {
            color: rgba(255, 255, 255, 0.7) !important;
        }
        .theme-light .q-message-name,
        body.theme-light .q-message-name {
            color: #475569 !important; /* slate-600 */
        }
        
        body.theme-light .q-menu,
        body.theme-light .q-menu *,
        body.theme-light .q-item__label {
            color: #1e293b !important;
        }

        /* --- 送信側（右側）のメッセージ本体 --- */
        .q-message-sent .q-message-text {
            background: #0d9488 !important; 
            color: #ffffff !important;
        }
        /* ★ 送信側の「ツノ」本来の着色面のみを背景色（#0d9488）に上書き */
        .q-message-sent .q-message-text::before {
            border-bottom-color: #0d9488 !important;
            border-top-color: #0d9488 !important;
        }

        /* --- 受信側（左側）のメッセージ本体 --- */
        .q-message-received .q-message-text {
            background: #d1fae5 !important; 
            color: #064e3b !important;      
        }
        /* ★ 受信側の「ツノ」本来の着色面のみを背景色（#d1fae5）に上書き */
        .q-message-received .q-message-text::before {
            border-bottom-color: #d1fae5 !important;
            border-top-color: #d1fae5 !important;
        }
    </style>
    <script>
        window.setupChatInput = function(elementId) {
            setTimeout(() => {
                const container = document.getElementById(elementId);
                if (!container) return;
                const textarea = container.querySelector('textarea');
                if (!textarea) return;

                textarea.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        if (e.isComposing) return;
                        const isMobile = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
                        if (isMobile) return;

                        if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
                            e.preventDefault();
                            const sendBtn = document.getElementById('gemini-send-btn');
                            if (sendBtn) sendBtn.click();
                        }
                    }
                }, { passive: false });
            }, 300);
        }
    </script>
''', shared=True)

# ==========================================
# ★ 検索回数管理用ヘルパー関数
# ==========================================
def get_today_search_count() -> int:
    """本日の検索利用回数を取得する。日付が変わっていたらリセットする"""
    today_str = date.today().isoformat()
    search_data = app.storage.user.get('search_limit_data', {})
    
    # 記録されている日付と今日の日付が異なる場合はリセット
    if search_data.get('date') != today_str:
        search_data = {'date': today_str, 'count': 0}
        app.storage.user['search_limit_data'] = search_data
        
    return search_data.get('count', 0)

def increment_search_count() -> int:
    """本日の検索利用回数をインクリメントする"""
    today_str = date.today().isoformat()
    search_data = app.storage.user.get('search_limit_data', {})
    
    if search_data.get('date') != today_str:
        search_data = {'date': today_str, 'count': 1}
    else:
        search_data['count'] = search_data.get('count', 0) + 1
        
    app.storage.user['search_limit_data'] = search_data
    return search_data['count']


def check_is_open() -> bool:
    """スナックの営業時間内（22:00 〜 翌朝 07:00）であるかを判定する"""
    current_hour = datetime.now().hour
    return (current_hour >= 22 or current_hour < 7)

def get_or_create_chat(user_id: str, character_key: str, model_name: str):
    if user_id not in user_chats:
        char_info = AI_CHARACTERS.get(character_key, AI_CHARACTERS['mama'])
        
        meta_instruction = (
            "\n\n【システムからの絶対ルール】\n"
            "ユーザーからのメッセージには、システム側で自動的に【現在時刻: 〇〇 / 送信者: 〇〇 / 顧客情報: 〇〇】というメタタグが付与されます。\n"
            "あなたはこの情報（時間、相手の立場、職業、趣味、誕生日、お酒の種類や銘柄、好みの飲む雰囲気など）を深く理解し、状況に合った接客を行ってください。\n"
            "※お酒の種類や趣味はカンマ区切りで複数設定されている場合があります。適宜推測して会話に活気をもたせてください。"
            "例えば、相手の好きなお酒や銘柄が分かれば「いつもの〇〇にする？」と勧め、趣味の話を振り、好みの雰囲気に合わせて会話のテンションを調整してください。"
            "また、送信者が「オーナー(SU)」であり、かつ「営業時間外(閉店中)」だった場合は、"
            "『お客様』としてではなく『身内の上司（オーナー）』として接し、名前を呼ぶときは必ず名前の後にオーナーを付加し、労いの言葉をかけること。"
        )
        
        # ※ただの猫が選ばれている時は、メタ指示を無視して猫に徹してもらう
        final_prompt = char_info['prompt']
        if character_key != 'cat':
            final_prompt += meta_instruction
            
        config_payload = {
            "system_instruction": final_prompt
        }
        
        # ★ 検索機能が有効で、上限に達していない場合のみ検索ツールをセット
        is_search_active = app.storage.user.get('cat_search_active', True)
        if character_key == 'cat' and is_search_active:
            if get_today_search_count() < 10:
                config_payload["tools"] = [{"google_search": {}}]
            
        user_chats[user_id] = client.aio.chats.create(
            model=model_name,
            config=config_payload
        )
    return user_chats[user_id]

def safe_val(val, default="不明"):
    if not val or str(val).strip().lower() in ['null', 'none', '']:
        return default
    return str(val).strip()

def render_gemini_chat(current_user_id: str, current_user_name: str, my_avatar_url: str):
    try:
        res_prof = supabase.table("profiles").select(
            "role, birthday, occupation, hobbies, liquor_type, favorite_brand, drinking_style, drinking_area"
        ).eq("id", current_user_id).single().execute()
        
        data = res_prof.data if res_prof.data else {}
        
        my_role = data.get('role', 'member')
        
        occupation = safe_val(data.get('occupation'), "ヒミツ")
        drinking_area = safe_val(data.get('drinking_area'), "ヒミツ")
        hobbies = safe_val(data.get('hobbies'), "ヒミツ")
        drinking_style = safe_val(data.get('drinking_style'), "ヒミツ")
        
        birthday_raw = safe_val(data.get('birthday'), "")
        birthday_str = "ヒミツ"
        if birthday_raw:
            try:
                dt = datetime.strptime(birthday_raw, "%Y-%m-%d")
                birthday_str = f"{dt.month}月{dt.day}日"
            except:
                birthday_str = birthday_raw 
                
        liquor_type = safe_val(data.get('liquor_type'), "まだヒミツ")
        favorite_brand = safe_val(data.get('favorite_brand'), "まだヒミツ")

    except Exception as e:
        print(f"Profile fetch error: {e}")
        my_role = 'member'
        birthday_str = "不明"
        occupation = "不明"
        hobbies = "不明"
        liquor_type = "不明"
        favorite_brand = "不明"
        drinking_style = "不明"
        drinking_area = "不明"
        
    is_su_user = str(my_role).lower() in ['superuser', 'admin', 'owner', 'master', 'submaster']
    is_regular_open = check_is_open()
    is_open = is_regular_open or is_su_user

    current_char = app.storage.user.get('selected_ai_char', 'mama')
    char_info = AI_CHARACTERS.get(current_char, AI_CHARACTERS['mama'])
    
    # AIモデルの判定と設定
    available_models = [
        "gemini-2.5-flash-lite", 
        "gemini-3.1-flash-lite"
    ]
    if is_su_user:
        available_models.extend(["gemini-2.5-flash", "gemini-3.5-flash"])
        
    current_model = app.storage.user.get('selected_gemini_model', 'gemini-2.5-flash-lite')
    if current_model not in available_models:
        current_model = "gemini-2.5-flash-lite"
        app.storage.user['selected_gemini_model'] = current_model
    
    if current_user_id not in user_histories:
        user_histories[current_user_id] = []
        
    history = user_histories[current_user_id]
    
    # ==========================================
    # ★ キャラクター・モデル変更ヘルパー
    # ==========================================
    def on_char_change_direct(new_char: str):
        app.storage.user['selected_ai_char'] = new_char
        if current_user_id in user_chats:
            del user_chats[current_user_id]
        user_histories[current_user_id] = []
        ui.notify(f"お相手を「{AI_CHARACTERS[new_char]['name']}」に切り替えました", color='positive', position='top')
        ui.navigate.reload()

    def on_model_change(new_model: str):
        app.storage.user['selected_gemini_model'] = new_model
        if current_user_id in user_chats:
            del user_chats[current_user_id]
        user_histories[current_user_id] = []
        ui.notify(f"モデルを「{new_model}」に切り替えました", color='positive', position='top')
        ui.navigate.reload()

    # ★ 検索のON/OFF切り替え用ハンドラ
    def on_search_toggle(e):
        app.storage.user['cat_search_active'] = e.value
        # セッション切り替えのために現在のチャットを破棄
        if current_user_id in user_chats:
            del user_chats[current_user_id]
            
        if e.value:
            msg = "すけろくの検索機能を有効にしました"
            if is_su_user:
                msg += f" (本日残り: {max(0, 10 - get_today_search_count())}回)"
            ui.notify(msg, color='info', position='top')
        else:
            ui.notify("すけろくの検索機能を無効にしました", color='info', position='top')
        
        # プレースホルダーの再レンダリングやスイッチ表示の更新のためリロード
        ui.navigate.reload()
    
    # ==========================================
    # ★ キャスト紹介（プロフィール）ダイアログ
    # ==========================================
    with ui.dialog() as cast_dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white max-w-md w-full p-4 gap-4'):
        with ui.row().classes('w-full justify-between items-center'):
            ui.label('従業員（キャスト）一覧').classes('text-lg font-bold text-teal-400')
            ui.label('タップするとそのキャストに切り替わります。').classes('text-[10px] text-white/50 block pl-1')
            ui.button(icon='close', on_click=cast_dialog.close).props('flat round dense text-color=white')
        
        with ui.scroll_area().classes('w-full max-h-[60vh]'):
            with ui.column().classes('w-full gap-4'):
                for k, v in AI_CHARACTERS.items():
                    is_active = (k == current_char)
                    card_border = 'border-teal-500 bg-teal-950/30' if is_active else 'border-white/10 bg-white/5 hover:bg-white/10'
                    
                    with ui.row().classes(f'w-full gap-3 no-wrap items-start p-3 rounded-xl border transition cursor-pointer {card_border}')\
                            .on('click', lambda _, k_val=k: on_char_change_direct(k_val)):
                        ui.image(v['avatar']).classes('w-12 h-12 rounded-full object-cover shrink-0')
                        with ui.column().classes('gap-1 flex-grow'):
                            with ui.row().classes('items-center gap-2'):
                                ui.label(v['name']).classes('text-sm font-bold')
                                if is_active:
                                    ui.badge('接客中', color='teal-500').classes('text-[10px] px-1 py-0.5')
                                else:
                                    ui.badge(v['label'], color='slate-600').classes('text-[10px] px-1 py-0.5')
                            
                            # ★ 管理者のみ検索残り回数を表示。一般ユーザーは非表示。
                            if k == 'cat' and is_su_user:
                                current_count = get_today_search_count()
                                rem_search = max(0, 10 - current_count)
                                ui.label(f"{v['desc']} (本日Web検索残り: {rem_search}回)").classes('text-xs text-teal-300 whitespace-pre-wrap leading-normal')
                            else:
                                ui.label(v['desc']).classes('text-xs text-white/70 whitespace-pre-wrap leading-normal')

    async def send_message():
        if not check_is_open() and not is_su_user:
            ui.notify('申し訳ありません！ただいまお店の閉店時間（営業時間外）となっております。', type='warning', position='top')
            return

        text = user_input.value.strip()
        if not text:
            return
        user_input.value = ''
        
        history.append({"role": "user", "text": text})
        
        with chat_container:
            user_ui_msg = ui.chat_message(
                text=text, 
                name=current_user_name, 
                avatar=my_avatar_url,
                sent=True
            ).classes('w-full')
        scroll_area.scroll_to(percent=1.0)
        
        # 検索中かどうか一時判定用
        is_search_active = app.storage.user.get('cat_search_active', True)
        search_configured = (current_char == 'cat' and is_search_active and get_today_search_count() < 10)

        with chat_container:
            spinner = ui.row().classes('w-full justify-start items-center gap-2 text-teal-600 dark:text-teal-400')
            with spinner:
                ui.spinner(size='sm', color='teal')
                if search_configured:
                    ui.label('すけろくが考え中...🐾 (検索対応中)').classes('text-xs opacity-70')
                else:
                    ui.label('考え中...').classes('text-xs opacity-70')
        scroll_area.scroll_to(percent=1.0)

        current_time_str = datetime.now().strftime("%H:%M")
        customer_data = (
            f"職業: {occupation} / 誕生日: {birthday_str} / 趣味: {hobbies} / "
            f"好きなお酒の種類: {liquor_type} / 好きな銘柄: {favorite_brand} / "
            f"好みの飲む雰囲気・スタイル: {drinking_style} / よく飲むエリア: {drinking_area}"
        )
        
        if not is_regular_open and is_su_user:
            payload_text = f"【現在時刻: {current_time_str} (営業時間外) / 送信者: オーナー(SU)の{current_user_name} / 顧客情報: {customer_data}】\n{text}"
        else:
            payload_text = f"【現在時刻: {current_time_str} / 送信者: お客様の{current_user_name} / 顧客情報: {customer_data}】\n{text}"

        try:
            chat_session = get_or_create_chat(current_user_id, current_char, current_model)
            response = await chat_session.send_message(payload_text)
            ai_text = response.text
            
            # ★ 実際にGoogle検索が実行されたかどうかをメタデータから検知
            actual_searched = False
            search_queries = []
            
            if response.candidates:
                candidate = response.candidates[0]
                grounding_metadata = getattr(candidate, 'grounding_metadata', None)
                if grounding_metadata:
                    queries = getattr(grounding_metadata, 'web_search_queries', None)
                    if queries:
                        actual_searched = True
                        search_queries = list(queries)

            # ★ コンソールへのログ出力
            if search_configured:
                if actual_searched:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [すけろく検索ログ] ユーザー: {current_user_name} | 検索実行クエリ: {search_queries}")
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [すけろく検索ログ] ユーザー: {current_user_name} | ツール有効ですが、検索は不要と判断されました（日常会話等）")

            # ★ 実際にWeb検索クエリが走った場合のみ、カウントを1つ消費する
            if search_configured and actual_searched:
                new_count = increment_search_count()
                remaining = max(0, 10 - new_count)
                
                # 管理者（SUユーザー）にのみ通知を配信
                if is_su_user:
                    ui.notify(f"すけろくがWeb検索を実行しました（本日残り: {remaining}回）", color='info', position='bottom')
                
                # 検索回数を使い切ったタイミングでセッションを一度初期化（検索ツールを除外するため）
                if remaining == 0:
                    if current_user_id in user_chats:
                        del user_chats[current_user_id]
                    if is_su_user:
                        ui.notify("本日のすけろくの検索回数が上限に達しました。これ以降は通常の会話に戻ります。", color='warning', position='top')

            history.append({"role": "ai", "text": ai_text})
            with chat_container:
                ui.chat_message(
                    text=ai_text, 
                    name=char_info['name'], 
                    avatar=char_info['avatar']
                )
        except Exception as e:
            err_str = str(e).lower()
            
            if "503" in err_str or "unavailable" in err_str or "high demand" in err_str or "429" in err_str:
                error_msg = "ごめんね、今ちょっとお店が混み合っててお返事できないの💦 入力欄に言葉を戻しておいたから、少しだけ待ってからもう一回送ってみてね！"
            else:
                error_msg = f"ごめんね、ちょっとシステムのご機嫌が悪いみたい💦 ({str(e)})"
            
            ui.notify('通信が混み合っています。少し待ってから再試行してください。', type='warning', position='top')
            
            user_input.value = text
            
            if history and history[-1]["role"] == "user":
                history.pop()
                
            try:
                user_ui_msg.delete()
            except Exception:
                pass
                
            with chat_container:
                err_label = ui.label(f"⚠️ {error_msg}").classes('text-rose-400 text-[11px] font-bold w-full text-center bg-rose-500/10 py-2 px-4 rounded-xl my-2 shadow-sm border border-rose-500/20')
                
                def safely_remove(el):
                    try:
                        el.delete()
                    except Exception:
                        pass
                ui.timer(8.0, lambda el=err_label: safely_remove(el), once=True)

        finally:
            try:
                spinner.delete()
            except Exception:
                pass
            scroll_area.scroll_to(percent=1.0)

    input_id = f"input_{uuid.uuid4().hex[:8]}"
       
    with ui.column().classes('absolute inset-0 no-wrap gap-0 bg-transparent'):
        
        with ui.row().classes('w-full h-16 border-b border-white/10 flex items-center justify-between px-3 sm:px-6 shrink-0 m-0 no-wrap overflow-hidden'):
            
            with ui.row().classes('items-center gap-3 flex-nowrap overflow-hidden flex-grow min-w-0'):
                
                with ui.element('div').classes('cursor-pointer shrink-0 relative hover:opacity-80 transition') as avatar_btn:
                    ui.image(char_info['avatar']).classes('w-10 h-10 rounded-full object-cover shadow-md bg-white/10')
                    
                    with ui.menu().classes('bg-slate-800 dark:bg-slate-900 border border-white/10') as char_menu:
                        for k, v in AI_CHARACTERS.items():
                            prefix = "▷ " if k == current_char else "  "
                            ui.menu_item(f"{prefix}{v['name']}", on_click=lambda k=k: on_char_change_direct(k))\
                              .classes('text-white dark:text-gray-200 text-xs py-1 px-3')
                
                with ui.column().classes('gap-0 overflow-hidden justify-center flex-grow min-w-0'):
                    ui.label('スナック HIBI').style(
                        'font-family: "Hiragino Mincho ProN", "MS P明朝", "Georgia", serif; '
                        'text-shadow: 0 0 8px rgba(244, 63, 94, 0.8), 0 0 15px rgba(244, 63, 94, 0.4);'
                    ).classes('text-sm sm:text-base font-extrabold text-white tracking-widest truncate leading-none')
                    
                    # ★ 管理者（SUユーザー）かつ猫の場合のみヘッダーに残り回数を表示。一般ユーザーには表示しない。
                    if current_char == 'cat' and is_su_user:
                        rem_search = max(0, 10 - get_today_search_count())
                        ui.label(f'すけろく（本日の検索残り: {rem_search}回）').classes('text-[8px] sm:text-[10px] text-teal-400 block truncate pl-1 mt-1 leading-none')
                    else:
                        ui.label('〜かけがえのない、ひと時を。').classes('text-[8px] sm:text-[10px] text-white/50 block truncate pl-1 mt-1 leading-none')
            
            with ui.row().classes('items-center shrink-0 flex-nowrap gap-1'):
                # ★ AIモデル切り替えボタン
                with ui.button(icon='tune', color='white/40').props('flat dense').classes('hover:text-white transition shrink-0 p-1').tooltip('AIモデル設定'):
                    with ui.menu().classes('bg-slate-800 dark:bg-slate-900 border border-white/10') as model_menu:
                        for m in available_models:
                            prefix = "▷ " if m == current_model else "  "
                            ui.menu_item(f"{prefix}{m}", on_click=lambda m_val=m: on_model_change(m_val))\
                              .classes('text-white dark:text-gray-200 text-xs py-1 px-3')

                # ★ プロフィール（キャスト一覧）表示ボタン
                ui.button(icon='recent_actors', on_click=cast_dialog.open).props('flat dense color="white/40"').classes('hover:text-white transition shrink-0 p-1').tooltip('キャスト紹介')
                
                def reset_chat():
                    if current_user_id in user_chats:
                        del user_chats[current_user_id]
                    user_histories[current_user_id] = []
                    chat_container.clear()
                    ui.notify('チャット履歴をリセットしました', type='positive', position='top')
                
                ui.button(icon='cleaning_services', on_click=reset_chat).props('flat dense color="white/40"').classes('hover:text-white transition shrink-0 p-1').tooltip('履歴リセット')

        scroll_area = ui.scroll_area().classes('flex-grow w-full px-4 sm:px-6 py-4')
        with scroll_area:
            chat_container = ui.column().classes('w-full gap-4 max-w-3xl mx-auto items-stretch')
            with chat_container:
                if not is_regular_open and not is_su_user:
                    with ui.row().classes('w-full justify-center my-2'):
                        ui.label('【 準備中：ただいまの時間は営業時間外です（営業 22:00 〜 翌朝 07:00） 】')\
                          .classes('text-[10px] sm:text-xs bg-red-500/10 text-red-400 border border-red-500/20 px-4 py-2 rounded-xl text-center shadow-sm')

                for msg in history:
                    if msg["role"] == "user":
                        ui.chat_message(
                            text=msg["text"], 
                            name=current_user_name, 
                            avatar=my_avatar_url,
                            sent=True
                        ).classes('w-full')
                    else:
                        ui.chat_message(
                            text=msg["text"], 
                            name=char_info['name'], 
                            avatar=char_info['avatar']
                        )
            
        with ui.element('footer').classes('w-full border-t border-white/10 px-4 py-4 shrink-0 bg-black/15'):
            with ui.element('div').classes('w-full max-w-3xl mx-auto flex flex-col gap-2.5'):
                
                # ★ 検索機能のオンオフ切り替えスイッチを表示 (キャラクターが「猫（すけろく）」の時だけ)
                if current_char == 'cat' and is_open:
                    search_active = app.storage.user.get('cat_search_active', True)
                    with ui.row().classes('items-center gap-2 px-1 py-0.5 rounded-md bg-white/5 w-fit border border-white/10'):
                        # スイッチ自体は全ユーザーに表示し、自身でオンオフを切り替えられるようにします
                        search_switch = ui.switch(
                            'すけろくのネット検索を有効にする', 
                            value=search_active,
                            on_change=on_search_toggle
                        ).props('dense dark color="teal"')
                        
                        # ★ 残り回数表示は「管理者（SUユーザー）」のみに限定表示
                        if is_su_user:
                            rem_num = max(0, 10 - get_today_search_count())
                            ui.label(f'（本日残り: {rem_num}回）').classes('text-[11px] text-teal-400 font-bold')

                with ui.row().classes('w-full items-end gap-3'):
                    if is_open:
                        ph_text = 'メッセージを入力...'
                        if not is_regular_open and is_su_user:
                            ph_text = 'メッセージを入力... (SU特権適用中)'
                            
                        # ★ 猫かつ管理者（SU）の場合のみプレースホルダーに詳細表示。一般ユーザーは汎用表示。
                        if current_char == 'cat':
                            is_search_active = app.storage.user.get('cat_search_active', True)
                            if is_search_active:
                                if is_su_user:
                                    rem_search = max(0, 10 - get_today_search_count())
                                    ph_text = f'すけろくに質問（本日のネット検索残り: {rem_search}回）'
                                else:
                                    ph_text = 'すけろくに質問（ネット検索対応中）'
                            else:
                                ph_text = 'すけろくに質問（ネット検索オフ）'
                                
                        user_input = ui.textarea(placeholder=ph_text).classes('flex-grow').props(f'dark outlined color="teal" autogrow rows=1 id="{input_id}"')
                        send_btn = ui.button(icon='send', on_click=lambda: send_message()).props('round flat color="teal-400" id="gemini-send-btn"')
                    else:
                        user_input = ui.textarea(placeholder='【閉店中】営業時間は夜22:00〜翌朝07:00です。また夜にお待ちしております。').classes('flex-grow opacity-60').props(f'dark outlined color="grey" rows=1 id="{input_id}" disabled')
                        send_btn = ui.button(icon='send').props('round flat color="grey" id="gemini-send-btn" disabled').classes('opacity-40')

        ui.timer(0.2, lambda: scroll_area.scroll_to(percent=1.0), once=True)

        if is_open:
            ui.run_javascript(f"window.setupChatInput('{input_id}')")