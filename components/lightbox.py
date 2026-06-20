from nicegui import ui

def lightbox_image(source: str, thumbnail_classes: str = 'w-full h-48 object-cover rounded-lg cursor-pointer hover:opacity-80 transition-opacity'):
    """
    クリックすると全画面表示（ライトボックス）になる画像コンポーネント。
    
    :param source: 画像のURLまたはローカルパス
    :param thumbnail_classes: 通常時（サムネイル）の画像に適用するTailwind CSSクラス
    :return: ui.image オブジェクト
    """
    
    # --- ライトボックス（全画面ダイアログ）の定義 ---
    with ui.dialog().props('maximized transition-show="fade" transition-hide="fade"') as dialog:
        # ui.card()からdiv(ui.element('div'))に変更し、w-screen/h-screenで画面サイズに固定
        with ui.element('div').classes('w-screen h-screen bg-black/95 flex flex-col items-center justify-center relative'):
            
            # 閉じるボタン（どんな画像でも見やすいように少し半透明の黒背景を追加）
            ui.button(icon='close', on_click=dialog.close).props('flat round text-white size=lg').classes('absolute top-4 right-4 z-50 bg-black/50')
            
            # ★修正箇所: w-full h-full で画面いっぱいに広げつつ、props('fit="contain"') でアスペクト比を維持して収める
            ui.image(source).props('fit="contain"').classes('w-full h-full cursor-pointer').on('click', dialog.close)

    # --- サムネイル（通常画面に表示されるもの）の定義 ---
    thumbnail = ui.image(source).classes(thumbnail_classes).on('click', dialog.open)
    
    return thumbnail