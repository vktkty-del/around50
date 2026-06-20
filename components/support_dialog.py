from nicegui import ui
from database.su_db import create_support_ticket

def open_support_ticket_dialog(current_user_id: str):
    """ユーザーが運営にチケット（要望・通報）を送るためのダイアログ"""
    
    with ui.dialog() as dialog, ui.card().classes('bg-slate-900 border border-white/20 text-white w-[400px] max-w-full p-6 shadow-2xl'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('support_agent', size='sm', color='cyan-400')
                ui.label('運営へのお問い合わせ').classes('text-lg font-bold text-white')
            ui.button(icon='close', on_click=dialog.close).props('flat round size=sm color=white')
            
        ui.label('荒らしの報告、機能の要望、不具合の報告などはこちらから送信してください。').classes('text-xs text-white/60 mb-4')
        
        # 入力フォーム群
        ticket_title = ui.input(placeholder='件名').classes('w-full bg-black/30 border border-white/10 rounded-lg mb-3 px-2').props('borderless input-class="text-white text-sm"')
        
        ticket_content = ui.textarea(placeholder='お問い合わせ内容').classes('w-full bg-black/30 border border-white/10 rounded-lg mb-3 px-2').props('borderless input-class="text-white text-sm" autogrow rows="4"')
        
        # 優先度の選択（SUダッシュボードで赤いハイライトになるかどうかを分ける）
        priority_select = ui.select(
            options={'normal': '通常 (要望・質問など)', 'high': '緊急 (荒らし報告・深刻な不具合)'},
            value='normal',
            label='優先度'
        ).classes('w-full mb-4').props('dark filled')

        def handle_submit():
            title = ticket_title.value or ""
            content = ticket_content.value or ""
            priority = priority_select.value
            
            if not title.strip() or not content.strip():
                ui.notify('件名と内容を入力してください。', color='warning', position='top')
                return
                
            try:
                # su_db.py の関数を呼び出す
                create_support_ticket(current_user_id, title.strip(), content.strip(), priority)
                ui.notify('運営に送信しました。ご報告ありがとうございます。', color='positive', position='top')
                dialog.close()
            except Exception as e:
                ui.notify(f'送信エラー: {e}', color='negative', position='top')

        # ボタンエリア
        with ui.row().classes('w-full justify-end mt-2 gap-2'):
            ui.button('キャンセル', on_click=dialog.close).props('flat color=white')
            ui.button('送信する', on_click=handle_submit).classes('bg-cyan-600 hover:bg-cyan-500 text-white font-bold px-6 rounded-full')
            
    dialog.open()