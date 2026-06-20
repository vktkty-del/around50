import google.generativeai as genai

# APIキーを設定
genai.configure(api_key="AIzaSyDRNSVThmXHQtnkCwEgbml-om8YYZXU9x4")

# モデル一覧を取得して表示
for m in genai.list_models():
    # generateContent（チャット機能）に対応しているモデルのみを表示する場合
    if 'generateContent' in m.supported_generation_methods:
        print(f"モデル名: {m.name}")
        print(f"説明: {m.description}")
        print("-" * 20)