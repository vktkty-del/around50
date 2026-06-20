# components/splash.py
import uuid
from nicegui import ui

def show_splash_screen():
    """
    文字の美しさと『彩り』を表現する光の揺らぎだけで構築された、
    和モダン・テキストスプラッシュ画面。
    """
    # 1. アニメーションを定義するCSSをヘッドに注入
    ui.add_head_html('''
        <style>
            /* 1-1. 文字や線のフェードイン */
            @keyframes hibiFadeIn {
                0% { opacity: 0; transform: translateY(12px); filter: blur(5px); }
                100% { opacity: 1; transform: translateY(0); filter: blur(0); }
            }
            /* 1-2. 背景の光がゆっくり呼吸するアニメーション */
            @keyframes hibiBreathe {
                0% { transform: scale(1); opacity: 0.25; }
                50% { transform: scale(1.15); opacity: 0.45; }
                100% { transform: scale(1); opacity: 0.25; }
            }
            .animate-hibi-fade {
                animation: hibiFadeIn 1.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            }
            .animate-hibi-fade-slow {
                animation: hibiFadeIn 2.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                animation-delay: 0.6s;
                opacity: 0; /* ディレイ中の初期非表示 */
            }
            .animate-breathe-cyan {
                animation: hibiBreathe 10s ease-in-out infinite;
            }
            .animate-breathe-indigo {
                animation: hibiBreathe 14s ease-in-out infinite;
                animation-delay: -3s;
            }
        </style>
    ''', shared=True)

    # 2. スプラッシュの一意のIDを生成
    splash_id = f"splash_{uuid.uuid4().hex[:8]}"

    # 3. 画面全体を覆う黒いガラス風のコンテナ
    # transition-opacity をかけておくことで、JSでのフェードアウトが滑らかになります
    with ui.element('div').classes('fixed inset-0 bg-slate-950 z-[9999] flex flex-col items-center justify-center transition-opacity duration-1000 overflow-hidden').props(f'id="{splash_id}"'):
        
        # 背景の「彩り」の光（シアンとインディゴのグラデーション光）
        ui.element('div').classes('absolute bg-cyan-500/10 blur-[130px] w-96 h-96 rounded-full -top-20 -left-20 animate-breathe-cyan')
        ui.element('div').classes('absolute bg-indigo-500/10 blur-[130px] w-96 h-96 rounded-full -bottom-20 -right-20 animate-breathe-indigo')
        
        # 中央のテキストコンテンツ
        with ui.column().classes('items-center justify-center gap-1'):
            # メインタイトル（余白を贅沢に広く取り、完璧なセンタリングのために左パディングで相殺）
            ui.label('日々、彩り。').classes('text-3xl sm:text-4xl font-extralight text-white tracking-[0.5em] pl-[0.5em] drop-shadow-[0_0_20px_rgba(255,255,255,0.25)] animate-hibi-fade')
            
            # 繊細な細い仕切り線
            ui.element('div').classes('w-16 h-[1px] bg-white/20 my-4 animate-hibi-fade-slow')
            
            # タグライン（静かで優しい言葉づかい）
            ui.label('何気ない日常に、大切な仲間と、小さな彩りを。')\
                .classes('text-[10px] sm:text-xs text-white/40 tracking-[0.25em] pl-[0.25em] text-center leading-relaxed animate-hibi-fade-slow')

    # 4. 2秒間表示し、1秒かけてフェードアウトした後にDOMから完全に消去するスマートJS
    js_destruct = f"""
    setTimeout(() => {{
        const el = document.getElementById('{splash_id}');
        if (el) {{
            el.style.opacity = '0'; // フェードアウト発火
            setTimeout(() => {{
                el.remove(); // DOMから完全消去してメモリを解放
            }}, 1000);
        }}
    }}, 2000);
    """
    ui.run_javascript(js_destruct)