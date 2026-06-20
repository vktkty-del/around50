# components/tos_dialog.py
import uuid
from nicegui import ui

def update_tos_agreement_db(user_id: str):
    """
    Supabaseのprofilesテーブルのagreed_tosカラムをTrueに更新するDB処理。
    """
    try:
        from config.supabase_config import get_supabase
        sb = get_supabase()
        sb.table('profiles').update({'agreed_tos': True}).eq('id', user_id).execute()
        return True
    except Exception as e:
        print(f"[TOS DB Update Error] {e}")
        raise e

def open_enforced_tos_dialog(current_user_id: str, success_cb):
    """
    規約に同意するまで閉じられない、強制利用規約同意ダイアログ。
    """
    # JSとPythonを紐付けるための一意のIDを生成
    scroll_box_id = f"tos_scroll_{uuid.uuid4().hex[:8]}"
    trigger_btn_id = f"tos_trigger_{uuid.uuid4().hex[:8]}"
    
    # ダイアログの外枠をクリックしても閉じないように「persistent=True」を設定
    with ui.dialog().props('persistent') as dialog, ui.card().classes('bg-slate-900 border border-cyan-500/30 text-white w-[460px] max-w-full p-6 shadow-2xl rounded-2xl'):
        
        # ヘッダー
        with ui.row().classes('items-center gap-2 mb-2 w-full'):
            ui.icon('assignment_turned_in', size='sm', color='cyan-400')
            ui.label('利用規約 ＆ プライバシーポリシー').classes('text-base font-bold text-white')
        
        ui.label('コミュニティの安全を守るため、以下の規約を最後までスクロールしてお読みいただき、同意をお願いいたします。').classes('text-[11px] text-white/60 mb-4 leading-tight')
        
        # 規約表示エリア（NiceGUIのScrollArea）
        with ui.scroll_area().props(f'id="{scroll_box_id}"').classes('h-72 w-full bg-black/40 border border-white/10 rounded-xl p-4 mb-4') as tos_scroll:
            
            # --- ここからMarkdownを使わず、Tailwindを駆使して読みやすくレイアウト ---
            with ui.column().classes('w-full gap-3 p-1'):
                
                # タイトル
                ui.label('Hibi ～IRODORI～ 利用規約').classes('text-xs font-black text-white w-full text-center border-b border-white/10 pb-2')
                
                # -------------------------------------------------------------
                # 1. 利用規約セクション
                # -------------------------------------------------------------
                ui.label('【 1. 利用規約 】').classes('text-xs font-black text-cyan-400 mt-2 mb-1 w-full')
                
                # 第1条
                ui.label('第1条（利用登録と承認）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    '① 本サービスは、完全招待制・事前承認制のクローズドなコミュニティです。\n'
                    '② ユーザーは、ログイン後に管理者（運営）による承認を経て、初めてすべての機能を利用することができます。\n'
                    '③ 運営は、コミュニティの秩序維持のために不適当と判断したアカウントの承認を拒絶、または取り消すことができるものとします。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/5')
                
                # 第2条
                ui.label('第2条（プロフィールの正確性と性別登録）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    '① ユーザーは、本サービスを利用するにあたり、真実かつ正確なプロフィール情報を登録するものとします。\n'
                    '② 本サービス内の安全および秩序（特に女性限定の募集機能等の適切運用）を確保するため、ユーザーは性別を偽って登録してはなりません。\n'
                    '③ 性別情報は一度登録するとユーザー自身で変更できません。誤登録があった場合は、速やかに運営へ申請するものとします。\n'
                    '④ 性別の虚偽申告が発覚した場合、運営は事前通告なしに対象ユーザーのアカウントを即時停止・削除できるものとします。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/5')
                
                # 第3条
                ui.label('第3条（禁止事項）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    'ユーザーは、本サービスの利用にあたり、以下の行為を行ってはなりません。\n\n'
                    '【1】情報の外部漏洩行為\n'
                    '・本サービス内の投稿内容、画像、イベント予定、メンバープロフィール、チャットの発言ログなどを、外部のSNSやウェブサイトへ転載・公開する行為。\n'
                    '・他のユーザーの本名や行動履歴などのプライバシーに関わる情報を、無断で外部に開示する行為。\n\n'
                    '【2】嫌がらせ・荒らし行為\n'
                    '・他のユーザーに対する誹謗中傷、脅迫、ハラスメント、ストーカー行為。\n'
                    '・システムが検知した「NGワード」の制限を意図的にすり抜けるような表現を用いる行為。\n\n'
                    '【3】無断勧誘・営業行為\n'
                    '・事前許可のない営利目的の宣伝、広告、勧誘（宗教・マルチ商法・他団体への引き抜き等）行為。\n\n'
                    '【4】コミュニティ運営を妨げる行為\n'
                    '・「ふらっと（即飲み募集）」における度重なる直前キャンセルや、連絡なしの不参加。\n'
                    '・過度の飲酒によるマナー違反や、他ユーザーに迷惑をかける実生活での行動。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/5')
                
                # 第4条
                ui.label('第4条（投稿の検閲と管理）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    '① システムがNGワードを検知した投稿、および運営が不適切と判断した投稿は、公開前に「審議（保留）状態」となります。\n'
                    '② 運営は、本規約に抵触する投稿について、ユーザーの同意なく削除または編集できる権利を有します。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/5')
                
                # 第5条
                ui.label('第5条（利用制限およびアカウントの削除）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    'ユーザーが本規約に違反した場合、または運営が不適当と判断した場合、運営は事前通知をすることなく、本サービスの一部または全部の利用制限、あるいはアカウントの即時停止・完全削除を行うことができるものとします。これに伴い生じた損害について、運営は一切の責任を負いません。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/10 my-2')
                
                # -------------------------------------------------------------
                # 2. プライバシーポリシーセクション
                # -------------------------------------------------------------
                ui.label('【 2. プライバシーポリシー 】').classes('text-xs font-black text-cyan-400 mt-2 mb-1 w-full')
                
                # ポリシー第1条
                ui.label('第1条（個人情報の収集方法）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    '本サービスでは、外部ログイン時の認証情報（ID、表示名、プロフィール画像）、プロフィール画面にて任意または必須で入力した情報、および投稿コンテンツ、チャットの発言ログ、アクセスログを適切に取得・保存します。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/5')
                
                # ポリシー第2条
                ui.label('第2条（個人情報の利用目的）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    '収集した個人情報は、本サービスの提供・利用承認（門番システム）のため、ユーザー同士の円滑なコミュニケーションのため、セキュリティ向上・NGワード検知のため、および運営からのお知らせ送信のためにのみ利用します。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')
                
                ui.separator().classes('bg-white/5')
                
                # ポリシー第3条
                ui.label('第3条（個人情報の管理）').classes('text-[11px] font-bold text-amber-300 mt-1')
                ui.label(
                    '本サービスは、セキュアなデータベース（Supabase等）を利用してデータを安全に管理し、不正アクセスや紛失、改ざん、漏洩の防止に努めます。また、ユーザーの同意を得ることなく第三者に個人情報を提供することはありません。'
                ).classes('text-[11px] text-white/70 pl-2 leading-relaxed whitespace-pre-line')

        # 同意フラグとチェックボックス
        scroll_finished = {'value': False} # 最下部到達でTrueになる内部フラグ
        
        agreement_checked = ui.checkbox('規約およびプライバシーポリシーに同意します')\
            .bind_value_from(scroll_finished, 'value')\
            .classes('text-xs text-white/60 mb-4')
        
        # 初期状態ではチェックボックスと送信ボタンを無効化（スクロールさせないと触れない）
        agreement_checked.disable() 
        submit_btn = ui.button('同意してSNSを始める')\
            .classes('w-full bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-3 rounded-xl shadow-lg shadow-cyan-500/20')
        submit_btn.disable()

        # 最下部到達時にPython側で呼び出される関数
        def on_scroll_completed():
            # すでに到達検知済みなら何もしない
            if scroll_finished['value']:
                return
                
            scroll_finished['value'] = True
            agreement_checked.enable()       # チェックボックスを選択可能に
            agreement_checked.set_value(True) # チェックを自動で入れる
            submit_btn.enable()              # 同意ボタンを押せるようにする
            ui.notify('規約の確認ありがとうございました。同意ボタンが有効化されました。', color='positive', position='top')

        # JSから叩くための「非表示ボタン」を設置
        trigger_btn = ui.button(on_click=on_scroll_completed).props(f'id="{trigger_btn_id}"').classes('hidden')

        # 送信ボタンクリック時の処理
        def handle_submit():
            try:
                update_tos_agreement_db(current_user_id)
                ui.notify('規約に同意しました。Hibi へようこそ！', color='positive', position='top')
                dialog.close()
                success_cb() # 成功コールバックを動かして画面を更新
            except Exception as e:
                ui.notify(f'データベースの更新に失敗しました。 (エラー: {e})', color='negative', position='top', timeout=6000)

        submit_btn.on('click', handle_submit)

    dialog.open()
    
    # -------------------------------------------------------------
    # JSによるスクロール監視のセットアップ
    # QuasarのScrollAreaの仕組み（内部にある .scroll コンテナ）に対応
    # -------------------------------------------------------------
    js_code = f"""
    setTimeout(() => {{
        const box = document.getElementById('{scroll_box_id}');
        const btn = document.getElementById('{trigger_btn_id}');
        if (box && btn) {{
            const scrollContainer = box.querySelector('.scroll');
            if (scrollContainer) {{
                scrollContainer.addEventListener('scroll', function() {{
                    const isAtBottom = scrollContainer.scrollHeight - scrollContainer.scrollTop <= scrollContainer.clientHeight + 10;
                    if (isAtBottom) {{
                        btn.click();
                    }}
                }});
            }} else {{
                box.addEventListener('scroll', function() {{
                    const isAtBottom = box.scrollHeight - box.scrollTop <= box.clientHeight + 10;
                    if (isAtBottom) {{
                        btn.click();
                    }}
                }});
            }}
        }}
    }}, 500);
    """
    ui.run_javascript(js_code)