from nicegui import ui
ui.label('トンネルは正常に開通しています！').classes('text-3xl font-bold m-10')
ui.run(host='127.0.0.1', port=8000, show=False)