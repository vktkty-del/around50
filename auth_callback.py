from config.supabase_config import get_supabase
supabase = get_supabase()
from nicegui import ui, app

from starlette.responses import RedirectResponse
import asyncio

async def handle_callback(code: str = None):
    try:
        if code:
            
            # セッション交換
            exchange_res = supabase.auth.exchange_code_for_session({"auth_code": code})
            
            if exchange_res and getattr(exchange_res, 'session', None):
                session = exchange_res.session
                user = session.user
                
                # Appストレージへの同期
                app.storage.user['user_id'] = str(user.id)
                app.storage.user['is_authenticated'] = True
                app.storage.user['access_token'] = session.access_token
                
                await asyncio.sleep(0.2)
                return RedirectResponse('/')
        return RedirectResponse('/login')
    except Exception as e:
        print(f"🚨 Auth Callback Error: {e}")
        return RedirectResponse('/login')