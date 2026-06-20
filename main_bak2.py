import os
from nicegui import ui

@ui.page('/', title='メンテ', dark=True)
def maintenance_page():
    # ページ全体のパディングを削除し、フルスクリーンで配置
    # CSSで「スクロール禁止」と「オーバースクロール無効」を設定
    ui.add_head_html('''
        <style>
            html, body {
                margin: 0;
                padding: 0;
                width: 100vw;
                height: 100svh;
                overflow: hidden;
                overscroll-behavior: none;
            }
            .center-container {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
                width: 100%;
            }
        </style>
    ''')
    
    # 独自のクラス 'center-container' を適用
    with ui.column().classes('center-container'):
        
        ui.icon('engineering', size='64px').classes('text-blue-500 mb-8')
        
        ui.label('メンテナンス中').classes('text-2xl font-light tracking-widest')
        ui.label('現在、システムをメンテナンス中です。').classes('text-gray-500 mt-4')
        
        ui.label('再開まで今しばらくお待ちください').classes('text-sm text-gray-700 mt-12')
        

        
        # フッター連絡先
        ui.label('お問い合わせ: LINE某所でよっしーまで').classes('text-xs text-gray-600 mt-12')



# サーバー起動
ui.run(
    host='127.0.0.1', 
    port=8000, 
    title='日々、彩り。', 
    favicon='static/favicon/favicon_rev3.png', 
    reconnect_timeout=30.0
)