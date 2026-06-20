import re

# ==========================================
# NGワードリスト（初期ダミー）
# ※実運用時はDBの別テーブル（ng_words等）で管理し、SUが追加・削除できるように拡張すると便利です
# ==========================================
NG_WORDS = [
    "死ね", "殺す", "アホ", "バカ", "出会い系", "パパ活", "クソ"
]

def check_ng_words(text: str) -> dict:
    """
    テキスト内のNGワードを検知し、判定結果とハイライト済みテキストを返す
    
    Returns:
        dict: {
            "is_ng": bool,           # NGワードが含まれているか
            "matched_words": list,   # 検知されたNGワードのリスト
            "highlighted_text": str  # SUダッシュボード表示用（赤字ハイライト付き）
        }
    """
    if not text:
        return {"is_ng": False, "matched_words": [], "highlighted_text": ""}

    matched = []
    highlighted = text

    for word in NG_WORDS:
        if word in text:
            if word not in matched:
                matched.append(word)
            # 該当箇所をHTMLのspanタグで囲み、Tailwindの赤文字クラスを付与（SU画面での描画用）
            highlighted = re.sub(f"({re.escape(word)})", r'<span class="text-red-500 font-extrabold bg-red-500/20 px-1 rounded">\1</span>', highlighted)

    return {
        "is_ng": len(matched) > 0,
        "matched_words": matched,
        "highlighted_text": highlighted
    }