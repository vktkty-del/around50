from nicegui import ui

def create_header():
    with ui.row().classes('w-full items-center justify-between pb-4 border-b border-gray-200 shrink-0'):
        ui.label('Gemini AI Chat').classes('text-2xl font-bold text-gray-800')
        ui.badge('3.5-flash', color='primary')

def styled_chat_message(text: str, is_user: bool):
    # 3カラム化を物理的に阻止する最強のレイアウト：w-full固定
    with ui.row().classes('w-full ' + ('justify-end' if is_user else 'justify-start')):
        with ui.column().classes('max-w-[80%] p-3 rounded-2xl ' + ('bg-teal-500 text-white' if is_user else 'bg-gray-200 text-gray-800')):
            ui.label(text).classes('whitespace-pre-wrap')