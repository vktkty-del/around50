# themes.py
# 各テーマのカラーパレット定義（ダーク6種・ライト6種の計12種類に厳選整理）

THEMES = {
    # ==========================================
    # 🌙 ダークテーマ（6種類）
    # ==========================================
    'Moonlight': {
        'bg': 'bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-800',
        'accent': 'text-sky-300',
        'border': 'border-white/10',
        'primary': '#06b6d4'  # ★ 澄んだシアン（水色）
    },
    'Yozakura': {
        'bg': 'bg-gradient-to-br from-[#1a1a2e] via-[#2d1b36] to-[#4a1c32]',
        'accent': 'text-pink-300',
        'border': 'border-pink-500/20',
        'primary': '#ec4899'  # ★ 鮮やかな夜桜ピンク
    },
    'Sunset': {
        'bg': 'bg-gradient-to-br from-slate-900 via-purple-900 to-amber-900',
        'accent': 'text-amber-300',
        'border': 'border-amber-500/20',
        'primary': '#f59e0b'  # ★ 温かみのあるアンバーイエロー
    },
    'OceanBlue': {
        'bg': 'bg-gradient-to-br from-blue-900 via-blue-800 to-cyan-700',
        'accent': 'text-cyan-300',
        'border': 'border-white/20',
        'primary': '#0ea5e9'  # ★ 鮮やかなライトブルー
    },
    'EmeraldForest': {
        'bg': 'bg-gradient-to-br from-emerald-950 via-emerald-800 to-green-700',
        'accent': 'text-emerald-300',
        'border': 'border-emerald-500/30',
        'primary': '#10b981'  # ★ 深緑に映えるエメラルドグリーン
    },
    'Monochrome': {
        'bg': 'bg-gradient-to-br from-slate-950 via-slate-800 to-slate-900',
        'accent': 'text-slate-300',
        'border': 'border-white/10',
        'primary': '#94a3b8'  # ★ シックなスレートグレー
    },

    # ==========================================
    # ☀️ ライトテーマ（7種類：is_light=True）
    # ==========================================
    'PureCrystal': {
        'bg': 'bg-gradient-to-br from-slate-50 via-gray-100 to-indigo-50',
        'accent': 'text-indigo-600',
        'border': 'border-slate-900/10',
        'is_light': True,
        'primary': '#4f46e5'  # ★ 白背景に映える上品なインディゴブルー
    },
    'PeachCream': {
        'bg': 'bg-gradient-to-br from-orange-50 via-rose-50 to-amber-50',
        'accent': 'text-rose-500',
        'border': 'border-rose-900/10',
        'is_light': True,
        'primary': '#f43f5e'  # ★ 可愛らしいローズピンク
    },
    'MintMist': {
        'bg': 'bg-gradient-to-br from-teal-50 via-emerald-50 to-slate-100',
        'accent': 'text-teal-600',
        'border': 'border-teal-900/10',
        'is_light': True,
        'primary': '#0d9488'  # ★ 爽快感のあるミントティール
    },
    'SakuraPetal': {
        'bg': 'bg-gradient-to-br from-rose-50 via-pink-100 to-slate-50',
        'accent': 'text-pink-500',
        'border': 'border-pink-900/10',
        'is_light': True,
        'primary': '#db2777'  # ★ 視認性の高い華やかなさくらピンク
    },
    'CitronSorbet': {
        'bg': 'bg-gradient-to-br from-amber-50 via-yellow-100 to-zinc-100',
        'accent': 'text-amber-600',
        'border': 'border-amber-900/10',
        'is_light': True,
        'primary': '#d97706'  # ★ 深みのあるゴールドアンバー
    },
    'MonochromeLight': {
        'bg': 'bg-gradient-to-br from-slate-100 via-slate-50 to-zinc-100',
        'accent': 'text-slate-700',
        'border': 'border-slate-900/10',
        'is_light': True,
        'primary': '#334155'  # ★ 知的なダークスレートグレー
    },
    'LavenderFog': {
        'bg': 'bg-gradient-to-br from-purple-50 via-indigo-100 to-slate-50',
        'accent': 'text-indigo-500',
        'border': 'border-indigo-900/10',
        'is_light': True,
        'primary': '#6366f1'  # ★ 気品のあるラベンダーパープル
    }
}

# ==========================================
# 🎨 グローバルCSS / HTML定義
# ==========================================

LIGHT_THEME_CSS = r'''
@layer utilities {
    /* 1. タイトル等の白い drop-shadow 光彩効果を強制リセット */
    html body.theme-light [class*="drop-shadow-"],
    html body.theme-light [class*="shadow-"] { filter: none !important; text-shadow: none !important; }

    /* 2. 【最重要】text-white を持つすべての文字を一括でダークグレーに強制反転 */
    html body.theme-light .text-white, body.theme-light .text-white,
    html body.theme-light [class*='text-white'], body.theme-light [class*='text-white'] { color: #1e293b !important; }

    /* 3. 親要素（グラスパネル等）の内側にある白文字をピンポイント強制上書き */
    html body.theme-light .hibi-glass .text-white, html body.theme-light .hibi-panel-glass .text-white,
    body.theme-light .hibi-glass .text-white, body.theme-light .hibi-panel-glass .text-white { color: #1e293b !important; }

    /* 4. 薄グレー文字を一斉にダークグレー化 */
    html body.theme-light [class*='text-slate-'], html body.theme-light [class*='text-gray-'],
    html body.theme-light [class*='text-zinc-'], html body.theme-light [class*='text-neutral-'],
    html body.theme-light [class*='text-indigo-'], html body.theme-light [class*='text-blue-'],
    body.theme-light [class*='text-slate-'], body.theme-light [class*='text-gray-'],
    body.theme-light [class*='text-zinc-'], body.theme-light [class*='text-neutral-'],
    body.theme-light [class*='text-indigo-'], body.theme-light [class*='text-blue-'] { color: #1e293b !important; }

    /* 5. ロゴとサブタイトルの調整 */
    html body.theme-light [class*='tracking-'], body.theme-light [class*='tracking-'] { color: #0f172a !important; font-weight: 500 !important; }
    html body.theme-light [class*='text-white/30'], html body.theme-light [class*='text-white/40'],
    body.theme-light [class*='text-white/30'], body.theme-light [class*='text-white/40'] { color: rgba(15, 23, 42, 0.6) !important; }

    /* 6. 小さな注記や日付など */
    html body.theme-light .text-xs, html body.theme-light .text-sm,
    body.theme-light .text-xs, body.theme-light .text-sm { color: #475569 !important; }
    html body.theme-light [class*='text-white/60'], html body.theme-light [class*='text-white/70'],
    body.theme-light [class*='text-white/60'], body.theme-light [class*='text-white/70'] { color: #475569 !important; }

    /* 7. 暗いダイアログ背景などを反転 */
    html body.theme-light .bg-slate-950, html body.theme-light .bg-slate-900, html body.theme-light .bg-slate-800,
    html body.theme-light .bg-slate-700, html body.theme-light .bg-gray-800, html body.theme-light .bg-gray-700,
    body.theme-light .bg-slate-950, body.theme-light .bg-slate-900, body.theme-light .bg-slate-800,
    body.theme-light .bg-slate-700, body.theme-light .bg-gray-800, body.theme-light .bg-gray-700 { background-color: #e2e8f0 !important; color: #0f172a !important; }
    html body.theme-light [class*='bg-white/5'], html body.theme-light [class*='bg-white/10'],
    body.theme-light [class*='bg-white/5'], body.theme-light [class*='bg-white/10'] { background-color: #e2e8f0 !important; color: #0f172a !important; }

    /* 8. プレースホルダー */
    html body.theme-light ::placeholder, html body.theme-light .q-placeholder,
    body.theme-light ::placeholder, body.theme-light .q-placeholder { color: #94a3b8 !important; opacity: 1 !important; }

    /* 9. アイコン類の色 */
    html body.theme-light .q-icon, html body.theme-light .material-icons,
    body.theme-light .q-icon, body.theme-light .material-icons { color: #334155 !important; }

    /* 10. カードを薄いグレーの半透明ガラスに変更 */
    html body.theme-light .hibi-glass, body.theme-light .hibi-glass { background: rgba(241, 245, 249, 0.85) !important; border: 1px solid rgba(15, 23, 42, 0.1) !important; box-shadow: 0 10px 30px 0 rgba(15, 23, 42, 0.05) !important; }
    html body.theme-light .hibi-panel-glass, body.theme-light .hibi-panel-glass { background: rgba(241, 245, 249, 0.7) !important; border-color: rgba(15, 23, 42, 0.1) !important; }
    html body.theme-light .hibi-input, body.theme-light .hibi-input { background: rgba(255, 255, 255, 0.9) !important; border: 1px solid rgba(15, 23, 42, 0.12) !important; color: #0f172a !important; }

    /* 11. 区切り線 */
    html body.theme-light [class*='border-white/10'], body.theme-light [class*='border-white/10'] { border-color: rgba(15, 23, 42, 0.08) !important; }
    html body.theme-light [class*='border-white/20'], body.theme-light [class*='border-white/20'] { border-color: rgba(15, 23, 42, 0.12) !important; }

    /* 12. ポップアップメニュー */
    html body.theme-light .q-menu, body.theme-light .q-menu { background: rgba(255, 255, 255, 0.95) !important; border: 1px solid rgba(15, 23, 42, 0.1)  !important; }
    html body.theme-light .q-item:hover, body.theme-light .q-item:hover { background: rgba(15, 23, 42, 0.05) !important; }
    html body.theme-light .sp-menu, body.theme-light .sp-menu { border-top: 1px solid rgba(15, 23, 42, 0.08) !important; }
    /* === 【修正：ここを追記します】 === */
    /* 基本スタイルにある「color: white !important;」を、ライトモード時のみ暗いグレー(#1e293b)に強制上書きします */
    html body.theme-light .q-item, html body.theme-light .q-item *,
    body.theme-light .q-item, body.theme-light .q-item * { color: #1e293b !important; }

    /* 13. Quasarの通知トーストの文字色を白で保護 */
    html body.theme-light .q-notification, html body.theme-light .q-notification * { color: #ffffff !important; }

    /* 14. 半透明背景（bg-black/）をライトグレーに反転 */
    html body.theme-light [class*='bg-black/'], body.theme-light [class*='bg-black/'] { background-color: rgba(255, 255, 255, 0.6) !important; border: 1px solid rgba(15, 23, 42, 0.08) !important; }

    /* 15. Tailwindのplaceholder修飾子 */
    html body.theme-light [class*='placeholder-']::placeholder, body.theme-light [class*='placeholder-']::placeholder { color: #94a3b8 !important; }

    /* 16. 入力フォームのラベル等 */
    html body.theme-light .q-field__label, html body.theme-light .q-field__messages, html body.theme-light .q-field__bottom,
    body.theme-light .q-field__label, body.theme-light .q-field__messages, body.theme-light .q-field__bottom { color: #475569 !important; }

    /* === 【17. プルダウンの選択中テキスト：ここを上書きします】 === */
    /* セレクトボックスのコンテナ(.q-field__control)とその中にあるすべての子要素(*)に対して、
       ライトモード時に強制的に文字色を暗いグレーに上書きします */
    html body.theme-light .q-field__control,
    html body.theme-light .q-field__control *,
    body.theme-light .q-field__control,
    body.theme-light .q-field__control * {
        color: #1e293b !important;
    }
    /* ========================================================= */

    /* 18. ダイアログの白飛び対策 */
    html body.theme-light .q-dialog .q-card, body.theme-light .q-dialog .q-card { background-color: #ffffff !important; color: #1e293b !important; }

    /* 19. ライトテーマ時のタブ切り替えボタン背景 */
    html body.theme-light .hibi-tab-row, body.theme-light .hibi-tab-row { background-color: #f1f5f9 !important; border: 1px solid rgba(15, 23, 42, 0.08) !important; }
    
    /* 20. ライトテーマ時の非アクティブタブボタン文字色 */
    html body.theme-light .hibi-tab-btn-inactive, body.theme-light .hibi-tab-btn-inactive { color: #64748b !important; opacity: 1 !important; }

    /* 21. 【最重要】ライトモード時に潰れがちだったインディゴやシアンのアクセントカラーを、クッキリ鮮やかな色へ自動調整 */
    html body.theme-light .text-indigo-300, html body.theme-light .text-indigo-400,
    body.theme-light .text-indigo-300, body.theme-light .text-indigo-400 {
        color: #4f46e5 !important; /* 濃い鮮やかなインディゴブルー */
    }
    html body.theme-light .text-cyan-300, html body.theme-light .text-cyan-400,
    body.theme-light .text-cyan-300, body.theme-light .text-cyan-400 {
        color: #0369a1 !important; /* 濃い鮮やかなシアン（スカイブルー） */
    }
    /* 22. 【追加】バッジやボタンの内側の文字を白に固定 */
    html body.theme-light .q-badge,
    html body.theme-light .q-badge *,
    html body.theme-light .q-btn:not(.q-btn--flat):not(.q-btn--outline),
    html body.theme-light .q-btn:not(.q-btn--flat):not(.q-btn--outline) *,
    body.theme-light .q-badge,
    body.theme-light .q-badge *,
    body.theme-light .q-btn:not(.q-btn--flat):not(.q-btn--outline),
    body.theme-light .q-btn:not(.q-btn--flat):not(.q-btn--outline) * {
        color: #ffffff !important;
    }
}
'''

# themes.py の GLOBAL_HTML 部分を以下に差し替え

GLOBAL_HTML = r'''
<style>
    html, .q-layout, .q-page-container, .q-page { background: transparent !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; }
    body { margin: 0 !important; padding: 0 !important; overflow: hidden !important; background-attachment: fixed !important; color: #f8fafc; }
    .hibi-glass { background: rgba(255, 255, 255, 0.06) !important; backdrop-filter: blur(20px) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important; }
    .hibi-panel-glass { background: rgba(15, 23, 42, 0.35) !important; backdrop-filter: blur(24px) !important; }
    .hibi-input { background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); }
    .clean-scroll { overflow-y: auto !important; scrollbar-width: none !important; }
    .clean-scroll::-webkit-scrollbar { display: none !important; }
    .q-menu { background: rgba(15, 23, 42, 0.95) !important; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1) !important; padding: 0 !important; }
    .q-item { color: white !important; }
    
    @keyframes swing {
        0% { transform: rotate(0deg); } 20% { transform: rotate(15deg); } 40% { transform: rotate(-10deg); }
        60% { transform: rotate(5deg); } 80% { transform: rotate(-5deg); } 100% { transform: rotate(0deg); }
    }
    .animate-swing { animation: swing 1s ease-in-out infinite; transform-origin: top center; }

    @media (max-width: 768px) { .pc-menu { display: none !important; } .sp-menu { display: flex !important; } .pc-chat { display: none !important; } }
    @media (min-width: 769px) { .sp-menu { display: none !important; } .pc-menu { display: flex !important; } }
    @media (max-width: 950px) { .pc-chat { display: none !important; } }
    @media (min-width: 951px) { .pc-chat { display: flex !important; } }
    .hibi-tab-row { background-color: rgba(15, 23, 42, 0.35) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; }

    @media (hover: hover) and (pointer: fine) {
        html body .q-btn:not(.q-btn--flat):not(.q-btn--round),
        html body.theme-light .q-btn:not(.q-btn--flat):not(.q-btn--round) {
            transition: transform 0.2s ease-out, background-color 0.2s ease, color 0.2s ease !important;
            will-change: transform;
        }
        html body .q-btn:not(.q-btn--flat):not(.q-btn--round):hover,
        html body.theme-light .q-btn:not(.q-btn--flat):not(.q-btn--round):hover {
            transform: scale(1.05) !important;
        }
    }
</style>
<link href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.css" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.js"></script>
<script>
    // ★ 暴走するボタン自動変換ロボット（enforceOutlineButtons）を完全撤去し、
    // 接続切断メッセージの非表示化に特化した安全かつ超軽量なDOMクリーンアップのみを実行します。
    var cleanConnectionLost = () => {
        const spans = document.querySelectorAll('span');
        spans.forEach(span => {
            if (span.textContent && span.textContent.includes('Connection lost.')) {
                const parentDiv = span.closest('div');
                if (parentDiv) {
                    parentDiv.style.setProperty('display', 'none', 'important');
                    parentDiv.style.setProperty('opacity', '0', 'important');
                    parentDiv.style.setProperty('visibility', 'hidden', 'important');
                    parentDiv.style.setProperty('pointer-events', 'none', 'important');
                }
            }
        });
    };

    const observer = new MutationObserver(cleanConnectionLost);
    document.addEventListener('DOMContentLoaded', () => {
        observer.observe(document.body, { childList: true, subtree: true });
        cleanConnectionLost();
    });
</script>
'''