# components/su_dashboard_memos.py
from nicegui import ui
from database.su_db import fetch_admin_memos, create_admin_memo
from components.su_dashboard_logic import get_avatar_url

def build_memos_ui(current_user_id: str):
    """
    運営メモのカードUIを生成し、ちらつきのないリアルタイム差分同期を行うコンポーネント（ライト・ダーク対応 [完全ラグ0版]）
    """
    rendered_memo_ids = set()
    rendered_elements = {}

    with ui.card().classes('w-full h-[440px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-indigo-500 flex flex-col overflow-hidden'):
        ui.label('📝 運営メモ').classes('font-bold text-indigo-500 dark:text-indigo-400 mb-2 shrink-0')
        
        # ★ bg-black/30 は themes.py の LIGHT_THEME_CSS でライト時に自動で薄グレーに反転されるため、固定クラスでOKになりました
        with ui.column().classes('w-full h-[280px] overflow-y-auto bg-black/30 rounded-lg p-3 gap-2 border border-white/5 hide-scrollbar shrink-0') as memo_scroll:
            empty_label = ui.label('メモはまだありません。').classes('text-white/30 text-[10px] text-center w-full py-14 shrink-0')
            empty_label.set_visibility(True)

        # ----------------------------------------------------
        # メモの入力と送信
        # ----------------------------------------------------
        with ui.row().classes('w-full gap-2 items-center no-wrap m-0 mt-auto shrink-0'):
            
            # ★ 変更: インラインスタイルでの色指定を廃止し、themes.pyに元々ある『hibi-input』クラスを指定するだけにしました
            memo_input = ui.input(placeholder='メモを追加...')\
                .classes('flex-grow text-xs hibi-input')\
                .props('borderless dense')\
                .style('border-radius: 12px; padding: 0 12px; height: 36px;')
            
            def handle_send_memo():
                val = memo_input.value
                if not val or not val.strip(): return
                create_admin_memo(current_user_id, val)
                memo_input.set_value('')
                sync_memos_diff()
                
            memo_input.on('keydown.enter', handle_send_memo)
            ui.button(icon='send', on_click=handle_send_memo).props('flat round color=indigo-400 size=sm').classes('shrink-0')

        # 差分同期処理
        def sync_memos_diff():
            try:
                memos = fetch_admin_memos()
            except Exception as e:
                print(f"💡 メモ同期エラー: {e}")
                return

            current_db_ids = {m['id'] for m in memos}

            # 1. 削除
            for m_id in list(rendered_memo_ids):
                if m_id not in current_db_ids:
                    el = rendered_elements.get(m_id)
                    if el:
                        memo_scroll.remove(el)
                        del rendered_elements[m_id]
                    rendered_memo_ids.remove(m_id)

            # 2. 追加
            has_new = False
            for m in memos:
                m_id = m['id']
                if m_id not in rendered_memo_ids:
                    profile = m.get('profiles') or {}
                    avatar_url = get_avatar_url(profile.get('avatar_url'), profile.get('name'))
                    
                    # ★ 変更: bg-slate-800、text-slate-200 も LIGHT_THEME_CSS がライト時に自動でライトグレーとダークグレーに反転してくれるため、固定クラスでOKになりました
                    with memo_scroll:
                        with ui.row().classes('w-full gap-2 items-start') as new_row:
                            ui.image(avatar_url).classes('w-5 h-5 rounded-full shrink-0 mt-0.5')
                            with ui.column().classes('gap-0 flex-grow bg-slate-800 p-2 rounded-lg rounded-tl-none'):
                                ui.label(profile.get('name', '名無し')).classes('text-[9px] font-bold text-cyan-400')
                                ui.label(m.get('content', '')).classes('text-[11px] text-slate-200 whitespace-pre-wrap leading-tight')
                        
                        rendered_elements[m_id] = new_row
                        rendered_memo_ids.add(m_id)
                        has_new = True

            empty_label.set_visibility(len(rendered_memo_ids) == 0)

            if has_new:
                ui.run_javascript('setTimeout(() => { var el = document.querySelector(".hide-scrollbar"); if(el) el.scrollTop = el.scrollHeight; }, 50);')

        sync_memos_diff()

        ui.timer(5.0, sync_memos_diff)