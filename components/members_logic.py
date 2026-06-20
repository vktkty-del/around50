# components/members_logic.py
import inspect
import uuid
import os
import asyncio
from nicegui import ui, app, context
from components.comp_profile import get_parent_categories, LIQUOR_CATEGORIES
from database.profile_db import get_all_profiles, get_safe_profile, is_user_online, update_profile, supabase

# 管理者と判定するロールの定義
ADMIN_ROLES = {'superuser', 'admin', 'owner', 'master', 'submaster'}

DRINKING_STYLES = [
    'みんなでワイワイ', '少人数でじっくり', '一人でしっぽり', 'とりあえず飲む！'
]

# ------------------------------------------------------------------
# サーバーサイド・モバイルデバイス判定
# ------------------------------------------------------------------
def is_mobile_client() -> bool:
    try:
        user_agent = context.get_client().request.headers.get('user-agent', '').lower()
        mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'phone']
        return any(k in user_agent for k in mobile_keywords)
    except Exception:
        return False

# ------------------------------------------------------------------
# どんなカオスな形式のliquor_typeでも100%カンマ分割して平坦なリストにするパースヘルパー
# ------------------------------------------------------------------
def parse_liquor_type(raw_val) -> list:
    if not raw_val:
        return []
    
    # リスト、セット、タプルなどであれば、一度すべての要素をカンマで結合してフラットにする
    if isinstance(raw_val, (list, set, tuple)):
        s = ",".join(str(x) for x in raw_val)
    else:
        s = str(raw_val)
        
    # PostgreSQL配列括弧やJSONブラケットなどのゴミ記号を徹底排除
    for char in ['{', '}', '[', ']', '"', "'"]:
        s = s.replace(char, '')
        
    # 分割して、個々の余計なスペースを取り除いてリストにする
    return [x.strip() for x in s.split(',') if x.strip()]

# ------------------------------------------------------------------
# 状態管理 ＆ ビジネスロジック コントローラー (MembersPresenter)
# ------------------------------------------------------------------
class MembersPresenter:
    def __init__(self, current_user_id: str, is_mobile: bool):
        self.current_user_id = current_user_id
        self.is_mobile = is_mobile
        
        # 状態パラメータ
        self.selected_id = current_user_id
        self.sort_by = 'new'
        self.display_limit = 10  # ★ 初期表示を30から「10人」に変更
        self.view_mode = 'list'
        self.is_editing = False
        self.edit_state = None
        
        # フィルター状態
        self.filter_query = ''
        self.filter_liquor = 'すべて'
        self.filter_drinking_style = 'すべて'
        self.filter_drinking_area = ''
        self.filter_expanded = False  # アコーディオンの展開・折りたたみ状態
        
        # メンバー一覧のデータ
        self.all_members = []
        self.admin_online = False
        self.fetch_all_profiles_data()
        
    def fetch_all_profiles_data(self):
        try:
            # ★ total_score を取得対象に追加
            response = supabase.table("profiles").select(
                "id, name, avatar_url, header_image_url, comment, role, status, liquor_type, drinking_style, drinking_area, created_at, location, occupation, bio, total_score"
            ).neq("status", "pending").execute()
            self.all_members = response.data or []
        except Exception as e:
            print(f"Direct fetch profiles error: {e}")
            self.all_members = get_all_profiles()

        self.admin_online = False
        for mem in self.all_members:
            if str(mem.get('role', 'member')).lower() in ADMIN_ROLES:
                if is_user_online(mem['id']):
                    self.admin_online = True
                    break

    @property
    def is_filter_active(self) -> bool:
        return bool(
            self.filter_query or 
            (self.filter_liquor and self.filter_liquor != 'すべて') or 
            (self.filter_drinking_style and self.filter_drinking_style != 'すべて') or 
            self.filter_drinking_area
        )

    def reset_filters(self):
        self.filter_query = ''
        self.filter_liquor = 'すべて'
        self.filter_drinking_style = 'すべて'
        self.filter_drinking_area = ''

    def get_sorted_members(self) -> list:
        parsed_members = []
        for mem in self.all_members:
            raw_liquor = mem.get('liquor_type') or ''
            user_liquors = parse_liquor_type(raw_liquor)
            parents = get_parent_categories(user_liquors)

            # フィルター絞り込みロジックの適用
            if self.filter_query:
                q = self.filter_query.lower()
                name = (mem.get('name') or '').lower()
                comment = (mem.get('comment') or '').lower()
                bio = (mem.get('bio') or '').lower()
                location = (mem.get('location') or '').lower()
                occupation = (mem.get('occupation') or '').lower()
                
                if (q not in name and 
                    q not in comment and 
                    q not in bio and 
                    q not in location and 
                    q not in occupation):
                    continue

            if self.filter_liquor and self.filter_liquor != 'すべて':
                if self.filter_liquor in LIQUOR_CATEGORIES:
                    children = LIQUOR_CATEGORIES[self.filter_liquor]
                    if not any(child in user_liquors for child in children):
                        continue
                else:
                    if self.filter_liquor not in user_liquors:
                        continue

            if self.filter_drinking_style and self.filter_drinking_style != 'forget' and self.filter_drinking_style != 'すべて':
                if mem.get('drinking_style') != self.filter_drinking_style:
                    continue

            if self.filter_drinking_area:
                aq = self.filter_drinking_area.lower()
                area = (mem.get('drinking_area') or '').lower()
                if aq not in area:
                    continue

            parsed_members.append((mem, parents))

        # ソート処理（★ score を追加）
        if self.sort_by == 'active':
            parsed_members.sort(key=lambda x: (not is_user_online(x[0]['id']), x[0].get('name', '').lower()))
        elif self.sort_by == 'name':
            parsed_members.sort(key=lambda x: x[0].get('name', '').lower())
        elif self.sort_by == 'score':
            parsed_members.sort(key=lambda x: x[0].get('total_score') or 0, reverse=True)
        else:
            parsed_members.sort(key=lambda x: x[0].get('created_at') or '', reverse=True)
            
        return parsed_members

    def start_editing(self, profile, db_liquor_types):
        self.is_editing = True
        self.edit_state = {
            'name': profile.get('name', ''),
            'avatar_url': profile.get('avatar_url', ''),
            'header_image_url': profile.get('header_image_url', ''), 
            'gender': profile.get('gender', 0),
            'birthday': profile.get('birthday', ''),
            'location': profile.get('location', ''),
            'occupation': profile.get('occupation', ''),
            'comment': profile.get('comment', ''),
            'hobbies': profile.get('hobbies', ''),
            'bio': profile.get('bio', ''),
            'liquor_type': set(db_liquor_types),
            'favorite_brand': profile.get('favorite_brand', ''),
            'drinking_style': profile.get('drinking_style', ''),
            'drinking_area': profile.get('drinking_area', ''),
            'bar_url': profile.get('bar_url', ''),
            'recommended_bar': profile.get('recommended_bar', ''),
            'bar_image_url': profile.get('bar_image_url', ''),
        }

    def cancel_editing(self):
        self.is_editing = False
        self.edit_state = None

    def save_editing(self):
        e_state = self.edit_state
        new_data = {
            "name": e_state['name'],
            "avatar_url": e_state['avatar_url'],
            "header_image_url": e_state['header_image_url'], 
            "gender": e_state['gender'],
            "birthday": e_state['birthday'],
            "location": e_state['location'],
            "occupation": e_state['occupation'],
            "hobbies": e_state['hobbies'],
            "comment": e_state['comment'],
            "bio": e_state['bio'],
            "liquor_type": list(e_state['liquor_type']),
            "favorite_brand": e_state['favorite_brand'],
            "drinking_style": e_state['drinking_style'],
            "drinking_area": e_state['drinking_area'],
            "bar_url": e_state['bar_url'],
            "recommended_bar": e_state['recommended_bar'],
            "bar_image_url": e_state['bar_image_url']
        }
        try:
            update_profile(self.current_user_id, new_data)
            
            if 'user_metadata' not in app.storage.user:
                app.storage.user['user_metadata'] = {}
            app.storage.user['user_metadata']['avatar_url'] = e_state['avatar_url']
            app.storage.user['user_metadata']['name'] = e_state['name']
            
            ui.notify('プロフィールを保存しました！', color='positive', position='top')
            self.is_editing = False
            ui.run_javascript('window.location.reload()')
        except Exception as ex:
            ui.notify(f'プロフィールの更新に失敗しました: {ex}', color='negative', position='top')