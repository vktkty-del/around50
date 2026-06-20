# components/avatar.py
import base64
import sys
import asyncio
import re
from nicegui import app, ui, background_tasks, context, Client  # ★ Client をインポート

# =====================================================================
# ★ 超堅牢化：Pythonのモジュール重複ロード対策
# =====================================================================
# メモリの実体はすべて database/profile_db.py の中で sys._active_users_presence にバインドされています。
from database.profile_db import get_safe_profile, is_user_online

# =====================================================================
# ★ リアルタイム・バッジ監視エンジン (NiceGUI専用設計)
# =====================================================================
if not hasattr(sys, '_live_avatar_badges'):
    sys._live_avatar_badges = {}  # {element_id: (user_id, refresh_func, last_known_state, client_id)}

def update_all_avatar_badges():
    """
    稼働中のすべてのバッジのオンライン状態をチェックします。
    ★再接続バグ修正：
    Clientオブジェクトは再接続時に新しく作り直されるため、client_idから常に「現在のアクティブな最新接続インスタンス」
    を nicegui.Client.instances から引き直すことで、古い接続情報に囚われて監視が永久にフリーズする不具合を完全に解消します。
    """
    dead_ids = []
    # 登録された client_id を展開して安全に処理
    for elem_id, (u_id, ref_fn, last_known_state, client_id) in list(sys._live_avatar_badges.items()):
        try:
            # 1. 現在サーバー上に存在するすべての稼働中接続（Client.instances）から、最新のClientを安全に引き出す
            client = Client.instances.get(client_id)
            
            # クライアントがすでにサーバー上に存在しない（ブラウザを完全に閉じた・破棄された）場合
            if not client:
                dead_ids.append(elem_id)
                continue
                
            # 2. スマホがスリープや別画面にいて、一時的にWebSocketが切断されている場合
            # 再接続時の不整合（画面全体が真っ白になる強制ハードリロード）を完全に防ぐため、
            # 切断中であるクライアントへの UI refresh 配信を安全にスキップ（一時保留）します
            if not client.has_socket_connection:
                continue

            current_state = is_user_online(u_id)
            if current_state != last_known_state:
                sys._live_avatar_badges[elem_id] = (u_id, ref_fn, current_state, client_id)
                ref_fn.refresh()
        except Exception as e:
            print(f"Error updating badge: {e}")
            dead_ids.append(elem_id)
            
    for d_id in dead_ids:
        sys._live_avatar_badges.pop(d_id, None)

async def live_badge_polling_loop():
    while True:
        try:
            await asyncio.sleep(3.0)
            update_all_avatar_badges()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in live_badge_polling_loop: {e}")

if not hasattr(sys, '_live_avatar_timer_started'):
    app.on_startup(lambda: background_tasks.create(live_badge_polling_loop()))
    sys._live_avatar_timer_started = True


def get_avatar_url(url, name):
    if url and str(url).strip() and str(url).strip().lower() not in ["none", "null", ""]:
        return url
    safe_seed = base64.urlsafe_b64encode(str(name or "名無し").encode()).decode()[:15]
    return f"https://api.dicebear.com/7.x/bottts/svg?seed={safe_seed}"

def is_valid_url_or_path(string: str) -> bool:
    if not string:
        return False
    s = str(string).strip().lower()
    return (
        s.startswith('http://') or 
        s.startswith('https://') or 
        s.startswith('/static') or 
        s.startswith('data:image') or 
        any(s.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp'])
    )

def draw_user_avatar(
    avatar_url: str, 
    name: str = None, 
    user_id: str = None, 
    role: str = None, 
    size_class: str = 'w-12 h-12', 
    show_online_badge: bool = False, 
    border_class: str = 'border-slate-600',
    style: str = '',
    size: str = None,
    **kwargs
):

    if size:
        size_aliases = {
            'xs': 'w-6 h-6',
            'sm': 'w-8 h-8',
            'md': 'w-10 h-10',
            'lg': 'w-14 h-14',
            'xl': 'w-28 h-28',  # プロフィール編集用の黄金サイズ
        }
        size_class = size_aliases.get(size.lower(), size)

    if (user_id and not role) or (avatar_url and not is_valid_url_or_path(avatar_url)):
        extracted_user_id = user_id if (user_id and not role) else avatar_url
        try:
            profile = get_safe_profile(extracted_user_id)
            if profile:
                # 確実に本物のプロフィールURLで強制上書きします
                avatar_url = profile.get('avatar_url')
                name = name or profile.get('name')
                user_id = extracted_user_id
                role = role or profile.get('role')
        except Exception as e:
            print(f"Failed to auto-resolve profile in draw_user_avatar: {e}")

    # 役割（SU）判定ロジック
    target_role_lower = str(role or '').lower()
    target_is_su = target_role_lower in ['superuser', 'admin', 'owner', 'master', 'submaster']
    
    try:
        viewer_role = app.storage.user.get('role', 'member')
        viewer_is_su = str(viewer_role).lower() in ['superuser', 'admin', 'owner', 'master', 'submaster']
    except Exception:
        viewer_is_su = False

    display_badge_allowed = viewer_is_su or target_is_su

    av_src = get_avatar_url(avatar_url, name)
    
    with ui.element('div').classes(f'relative shrink-0 {size_class}').style(style) as container:
        ui.image(av_src).classes(f'w-full h-full rounded-full object-cover border-2 {border_class}')
        
        # ★ 徹底改修：管理者(SU)への王冠👑表示
        # アバターサイズ(px)に100%比例した、美しく完璧なサイズと配置を自動計算して表示します。
        # if target_is_su:
        #     match_crown = re.search(r'w-([0-9.]+)', size_class)
        #     crown_size = 'text-xs'
        #     top_offset = '-top-1.5'
        #     left_offset = '-left-1.5'
            
        #     if match_crown:
        #         val = float(match_crown.group(1))
        #         avatar_px = val * 4  # w-28 の場合は 112px
                
        #         if avatar_px >= 112:     # w-28 などの特大アバター
        #             crown_size = 'text-[28px]'
        #             top_offset = '-top-4.5'
        #             left_offset = '-left-3.5'
        #         elif avatar_px >= 56:    # w-14
        #             crown_size = 'text-xl'
        #             top_offset = '-top-3'
        #             left_offset = '-left-2.5'
        #         elif avatar_px >= 48:    # w-12
        #             crown_size = 'text-lg'
        #             top_offset = '-top-2.5'
        #             left_offset = '-left-2'
        #         elif avatar_px >= 44:    # w-11
        #             crown_size = 'text-base'
        #             top_offset = '-top-2'
        #             left_offset = '-left-1.5'
        #         elif avatar_px >= 32:    # w-8, w-9
        #             crown_size = 'text-xs'
        #             top_offset = '-top-1.5'
        #             left_offset = '-left-1.5'
        #         elif avatar_px >= 24:    # w-6, w-7
        #             crown_size = 'text-[9px]'
        #             top_offset = '-top-1.5'
        #             left_offset = '-left-1'
        #         else:                    # w-5以下の極小アバター
        #             crown_size = 'text-[7px]'
        #             top_offset = '-top-1'
        #             left_offset = '-left-0.5'
        #     elif 'xl' in size_class:
        #         crown_size = 'text-[28px]'
        #         top_offset = '-top-4.5'
        #         left_offset = '-left-3.5'
        #     elif 'lg' in size_class:
        #         crown_size = 'text-xl'
        #         top_offset = '-top-3'
        #         left_offset = '-left-2.5'

        #     ui.label('👑').classes(f'absolute {top_offset} {left_offset} {crown_size} drop-shadow-lg z-10')
            
        # オンラインバッジ判定
        if show_online_badge and user_id and display_badge_allowed:
            match = re.search(r'w-([0-9.]+)', size_class)
            
            badge_style = "width: 13px; height: 13px;"
            icon_size = "8px"
            
            if match:
                val = float(match.group(1))
                avatar_px = val * 4
                badge_px = max(5.0, min(16.0, avatar_px * 0.28))
                badge_style = f"width: {badge_px:.1f}px; height: {badge_px:.1f}px;"
                icon_px = max(3.5, badge_px * 0.6)
                icon_size = f"{icon_px:.1f}px"
            elif 'xl' in size_class:
                badge_style = "width: 18px; height: 18px;"
                icon_size = "10px"
            elif 'lg' in size_class:
                badge_style = "width: 14px; height: 14px;"
                icon_size = "8px"

            # バッジの描画部分
            @ui.refreshable
            def render_live_badge():
                try:
                    is_online = is_user_online(str(user_id))
                except Exception:
                    is_online = False

                if is_online:
                    ui.element('div').classes('absolute bottom-0 right-0 bg-green-500 border border-slate-950 rounded-full z-10')\
                        .style(badge_style).tooltip('オンライン')
                else:
                    with ui.element('div').classes('absolute bottom-0 right-0 bg-slate-600 border border-slate-950 rounded-full z-10 flex items-center justify-center')\
                            .style(badge_style) as badge:
                        ui.icon('close', size=icon_size, color='white/70')
                        badge.tooltip('オフライン')

            # 初回バッジ描画を実行
            render_live_badge()
            
            # グローバル監視システムにこのバッジの再描画参照を登録
            element_id = id(container)
            try:
                is_online_initial = is_user_online(str(user_id))
            except Exception:
                is_online_initial = False
            
            current_client_id = context.client.id
            sys._live_avatar_badges[element_id] = (str(user_id), render_live_badge, is_online_initial, current_client_id)
                    
    return container