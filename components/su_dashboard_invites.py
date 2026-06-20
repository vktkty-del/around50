# components/su_dashboard_invites.py
from nicegui import ui
from config.supabase_config import get_supabase
from components.su_dashboard_logic import format_datetime_string

def build_invites_ui():
    """
    招待履歴のカードUIを生成する外部コンポーネント
    """
    with ui.card().classes('w-full h-[450px] hibi-glass rounded-xl p-4 shadow-xl border-t-2 border-fuchsia-500 flex flex-col overflow-hidden'):
        ui.label('🤝 招待履歴').classes('font-bold text-fuchsia-400 mb-2 shrink-0')
        
        try:
            sb = get_supabase()
            all_profiles = sb.table("profiles").select("id, name, created_at, invited_by").order("created_at", desc=True).execute().data or []
            user_dict = {p['id']: p['name'] for p in all_profiles}
            
            table_rows = []
            for p in all_profiles:
                if p.get('invited_by'):
                    joined_date = format_datetime_string(p.get('created_at'), False)
                    new_user_name = p.get('name', '名無し')
                    inviter_name = user_dict.get(p['invited_by'], '不明')
                    
                    table_rows.append({
                        'joined_at': joined_date,
                        'new_user': new_user_name,
                        'inviter': inviter_name
                    })
            
            # スクロールエリア（高さを固定し、絶対に崩れないように保護します）
            with ui.column().classes('w-full h-[350px] overflow-y-auto clean-scroll shrink-0'):
                if table_rows:
                    cols = [
                        {'name': 'joined_at', 'label': '登録日', 'field': 'joined_at', 'align': 'left'},
                        {'name': 'new_user', 'label': '新規', 'field': 'new_user', 'align': 'left'},
                        {'name': 'inviter', 'label': '紹介者', 'field': 'inviter', 'align': 'left'}
                    ]
                    ui.table(columns=cols, rows=table_rows, row_key='new_user')\
                        .classes('w-full bg-transparent text-white border border-white/10 rounded-lg')\
                        .props('dark flat hide-pagination dense')
                else:
                    ui.label('招待経由での登録はまだありません。').classes('text-xs text-white/50 bg-black/20 p-3 rounded-lg text-center w-full')
                    
        except Exception as e:
            print(f"💡 招待履歴取得エラー: {e}")
            ui.label('通信が混み合っています...').classes('text-white/50 text-xs p-2')