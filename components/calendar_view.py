# components/calendar_view.py
import calendar
from datetime import datetime, date
from dateutil import parser as date_parser
from nicegui import app, ui, context

# DB関連のインポート
from database.event_db import fetch_active_events
from database.flat_db import get_active_flats

# 既存のダイアログ関連コンポーネント
from components.event_dialogs import (
    open_create_event_dialog, open_event_detail_dialog,
    is_event_past, open_edit_event_dialog
)
from themes import THEMES

# 今回新しく分割したモジュールのインポート
from utils.calendar_utils import get_user_calendar_state, get_japanese_holidays
from components.flat_dialogs import draw_flat_special_card, confirm_and_open_flat_dialog
from components.event_card import draw_event_card
from components.review_ui import draw_inline_review_page


def render_events(current_user_id: str, is_su: bool, enter_chat_cb):
    """イベントカレンダー画面全体の描画と状態管理を行うメイン関数"""
    ui.add_head_html('''
    <style>
    div:has(> .events-responsive-grid),
    div:has(> * > .events-responsive-grid),
    div:has(> * > * > .events-responsive-grid) {
        max-width: none !important; 
    }
    @keyframes avatar-appear {
        0% {
            opacity: 0;
            filter: blur(3px);          
            transform: scale(0.9) translateY(4px); 
        }
        100% {
            opacity: 1;
            filter: blur(0);
            transform: scale(1) translateY(0);
        }
    }
    .animate-avatar {
        animation: avatar-appear 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    .events-responsive-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 16px;
        width: 100% !important;
        align-items: start;
    }
    .events-pc-only {
        display: none !important;
    }
    .events-mobile-only {
        display: flex !important;
    }
    
    .calendar-day-weekday {
        color: #f8fafc !important; 
    }
    .theme-light .calendar-day-weekday,
    body.theme-light .calendar-day-weekday {
        color: #1e293b !important; 
    }
    
    .calendar-header-weekday {
        color: rgba(255, 255, 255, 0.6) !important; 
    }
    .theme-light .calendar-header-weekday,
    body.theme-light .calendar-header-weekday {
        color: #475569 !important; 
    }
    
    .calendar-day-sat {
        color: #3b82f6 !important; 
    }
    .calendar-day-sun-holiday {
        color: #ef4444 !important; 
    }

    @media (min-width: 768px) {
        .events-responsive-grid {
            grid-template-columns: repeat(12, minmax(0, 1fr)) !important;
        }
        .events-pc-col-5 {
            grid-column: span 5 / span 5 !important;
        }
        .events-pc-col-7 {
            grid-column: span 7 / span 7 !important;
        }
        .events-pc-only {
            display: flex !important;
        }
        .events-mobile-only {
            display: none !important;
        }
    }
    
    body.theme-light .q-field__native,
    body.theme-light .q-field__input,
    body.theme-light .q-field__label,
    body.theme-light .q-select__focus-value,
    body.theme-light .q-item__label,
    body.theme-light .q-field__prefix,
    body.theme-light .q-field__suffix,
    body.theme-light textarea {
        color: #1e293b !important; 
    }
    
    body.theme-light .q-field__control {
        background-color: rgba(0, 0, 0, 0.03) !important;
    }
    
    body.theme-light .q-menu,
    body.theme-light .q-menu .q-item,
    body.theme-light .q-menu .q-item__label,
    body.theme-light .q-menu .q-item__section {
        background-color: #ffffff !important;
        color: #1e293b !important;
    }
    
    body.theme-light .q-menu .q-item--active,
    body.theme-light .q-menu .q-item:hover {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
    }
    </style>
    ''')

    target_year = app.storage.user.pop('target_calendar_year', None)
    target_month = app.storage.user.pop('target_calendar_month', None)

    client_st = get_user_calendar_state()
    if target_year:
        client_st.calendar_year = target_year
    if target_month:
        client_st.calendar_month = target_month
        
    client_st.cached_events = fetch_active_events()  

    theme_name = app.storage.user.get('theme_name', 'Moonlight')
    theme_data = THEMES.get(theme_name, THEMES.get('Moonlight', {}))
    is_light = theme_data.get('is_light', False)

    dialog_container = ui.element('div').style('display: none;')

    def open_detail_safely(target_ev):
        with dialog_container:
            open_event_detail_dialog(target_ev, current_user_id, refresh_all)

    def open_create_safely():
        with dialog_container:
            open_create_event_dialog(current_user_id, refresh_all)

    def open_edit_safely(target_ev):
        with dialog_container:
            open_edit_event_dialog(target_ev, current_user_id, refresh_all)

    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    select_options = {}
    for i in range(-12, 13):
        m = current_month + i
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
            
        has_event_on_month = False
        for ev in client_st.cached_events:
            d_str = ev.get('event_date')
            if d_str:
                try:
                    ev_dt = date_parser.parse(d_str)
                    if ev_dt.year == y and ev_dt.month == m:
                        has_event_on_month = True
                        break
                except Exception:
                    pass
                    
        label = f"{y}年 {m}月"
        if has_event_on_month:
            label += " 🍷"  
            
        select_options[f"{y}-{m}"] = label

    curr_key = f"{client_st.calendar_year}-{client_st.calendar_month}"
    if curr_key not in select_options:
        select_options[curr_key] = f"{client_st.calendar_year}年 {client_st.calendar_month}月"

    def get_genre_badge_colors(genre: str, is_past: bool, is_deleted: bool):
        if is_past or is_deleted:
            return 'bg-slate-800/40 text-slate-400 border border-slate-700/30 line-through'
        colors = {
            '飲み会': 'bg-pink-500/15 text-pink-300 border border-pink-500/20',
            'サク飯': 'bg-amber-500/15 text-amber-300 border border-amber-500/20',
            'お茶・カフェ': 'bg-teal-500/15 text-teal-300 border border-teal-500/20',
            '女子会': 'bg-rose-500/15 text-rose-300 border border-rose-500/20',
            '趣味トーク': 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20'
        }
        return colors.get(genre, 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20')

    @ui.refreshable
    def draw_calendar_grid():
        year = client_st.calendar_year
        month = client_st.calendar_month
        events = client_st.cached_events
        japan_holidays = get_japanese_holidays(year)
        
        def prev_month():
            if client_st.calendar_month == 1:
                client_st.calendar_month = 12
                client_st.calendar_year -= 1
            else:
                client_st.calendar_month -= 1
            refresh_all()
            
        def next_month():
            if client_st.calendar_month == 12:
                client_st.calendar_month = 1
                client_st.calendar_year += 1
            else:
                client_st.calendar_month += 1
            refresh_all()

        with ui.column().classes('w-full gap-0'):
            with ui.row().classes('w-full items-center justify-between bg-white/5 p-3 rounded-t-xl border-t border-x border-white/10 no-wrap'):
                ui.button(icon='chevron_left', on_click=prev_month).props('flat text-color=white size=sm').classes('bg-white/5 hover:bg-white/10 rounded-lg')
                
                with ui.row().classes('items-center cursor-pointer hover:text-indigo-400 transition-colors select-none') as p_header_month:
                    ui.label(f"{year}年 {month}月 ▾").classes('text-sm sm:text-base font-extrabold text-indigo-300')
                    
                    with ui.menu().classes('bg-slate-900 border border-white/10 text-white rounded-xl p-2 w-48') as p_month_menu:
                        for opt_val, opt_label in select_options.items():
                            def make_menu_handler(val_str=opt_val):
                                def handle():
                                    y_str, m_str = val_str.split('-')
                                    client_st.calendar_year = int(y_str)
                                    client_st.calendar_month = int(m_str)
                                    p_month_menu.close()
                                    refresh_all()
                                return handle
                            ui.menu_item(opt_label, on_click=make_menu_handler()).classes('text-xs hover:bg-indigo-600/30 rounded-lg')

                with ui.row().classes('items-center gap-1.5 shrink-0'):
                    ui.button(icon='chevron_right', on_click=next_month).props('flat text-color=white size=sm').classes('bg-white/5 hover:bg-white/10 rounded-lg')

            days_jp = ['日', '月', '火', '水', '木', '金', '土']
            with ui.grid(columns=7).classes('w-full gap-1 p-2 bg-white/5 border-x border-b border-white/10'):
                for idx, day in enumerate(days_jp):
                    lbl = ui.label(day).classes('text-center text-[11px] font-bold py-1')
                    if idx == 0:  
                        lbl.style('color: #ef4444 !important;')
                    elif idx == 6:  
                        lbl.style('color: #3b82f6 !important;')
                    else:
                        lbl.classes('calendar-header-weekday')
            
            events_by_day = {}
            for ev in events:
                date_str = ev.get('event_date')
                if date_str:
                    try:
                        ev_dt = date_parser.parse(date_str)
                        if ev_dt.year == year and ev_dt.month == month:
                            d_num = ev_dt.day
                            if d_num not in events_by_day:
                                events_by_day[d_num] = []
                            events_by_day[d_num].append(ev)
                    except Exception:
                        pass
            
            month_weeks = calendar.monthcalendar(year, month)
            today = datetime.now()
            
            with ui.grid(columns=7).classes('w-full gap-1.5 p-2 bg-slate-950/40 rounded-b-xl border-x border-b border-white/10 hibi-glass'):
                for week in month_weeks:
                    for day_idx, day in enumerate(week):
                        if day == 0:
                            ui.card().classes('bg-white/[0.01] border border-dashed border-white/5 min-h-[110px] p-1 shadow-none rounded-lg')
                        else:
                            is_today = (today.year == year and today.month == month and today.day == day)
                            is_holiday_day = date(year, month, day) in japan_holidays
                            
                            if day_idx == 0 or is_holiday_day:  
                                day_style = 'color: #ef4444 !important; font-weight: bold;'
                                day_class = ''
                            elif day_idx == 6:  
                                day_style = 'color: #3b82f6 !important; font-weight: bold;'
                                day_class = ''
                            else:  
                                day_style = ''
                                day_class = 'calendar-day-weekday'
                                
                            if is_today:
                                day_class += ' text-indigo-300 font-extrabold'
                            
                            primary_color = theme_data.get('primary', '#6366f1')
                            if is_today:
                                bg_val = 'rgba(15, 23, 42, 0.05)' if is_light else 'rgba(255, 255, 255, 0.12)'
                                cell_style = f'background-color: {bg_val} !important; border: 2px solid {primary_color} !important; box-shadow: 0 0 12px {primary_color}60 !important;'
                                cell_classes = 'p-1.5 min-h-[110px] flex flex-col justify-between transition-all duration-200 rounded-lg shrink-0'
                            else:
                                cell_style = ''
                                cell_classes = 'p-1.5 min-h-[110px] flex flex-col justify-between border transition-all duration-200 rounded-lg shrink-0 bg-white/[0.03] border-white/10 hover:border-white/25 hover:bg-white/[0.07]'
                        
                            with ui.card().classes(cell_classes).style(cell_style):
                                with ui.row().classes('w-full items-center justify-between no-wrap px-0.5'):
                                    ui.label(str(day)).classes(f'text-xs select-none {day_class}').style(day_style)
                                    if is_today:
                                        ui.badge('今日', color='indigo-600').classes('text-[8px] px-1 py-0 scale-75')
                                        
                                day_events = events_by_day.get(day, [])
                                if day_events:
                                    with ui.column().classes('w-full gap-1 mt-1'):
                                        for ev in day_events[:3]:
                                            title = ev.get('title', 'イベント')
                                            is_past = is_event_past(ev.get('event_date'))
                                            is_deleted = ev.get('deleted_at') is not None
                                            
                                            btn_color = 'bg-slate-700/60 hover:bg-slate-600/60' if (is_deleted or is_past) else 'bg-indigo-600/40 hover:bg-indigo-500/80 border border-indigo-500/20'
                                            title_class = 'text-[9px] text-white truncate text-left block w-full leading-tight font-medium'
                                            if is_past or is_deleted:
                                                title_class += ' opacity-50 line-through'
                                                
                                            with ui.row().classes(f'w-full cursor-pointer rounded px-1.5 py-0.5 {btn_color} no-wrap items-center overflow-hidden transition-all hover:scale-[1.02]') as ev_row:
                                                def make_calendar_click(target_ev=ev):
                                                    return lambda: open_detail_safely(target_ev)
                                                ev_row.on('click', make_calendar_click())
                                                ui.label(title).classes(title_class)
                                                
                                        if len(day_events) > 3:
                                            ui.label(f"+他 {len(day_events)-3}件").classes('text-[8px] text-white/40 text-center block w-full')
                                else:
                                    ui.label('').classes('flex-grow')

    @ui.refreshable
    def draw_mobile_calendar_grid():
        year = client_st.calendar_year
        month = client_st.calendar_month
        events = client_st.cached_events
        japan_holidays = get_japanese_holidays(year)
        selected_day = getattr(client_st, 'selected_day', datetime.now().day)
        
        days_jp = ['日', '月', '火', '水', '木', '金', '土']
        
        events_by_day = {}
        for ev in events:
            date_str = ev.get('event_date')
            if date_str:
                try:
                    ev_dt = date_parser.parse(date_str)
                    if ev_dt.year == year and ev_dt.month == month:
                        d_num = ev_dt.day
                        events_by_day.setdefault(d_num, []).append(ev)
                except Exception:
                    pass
                    
        month_weeks = calendar.monthcalendar(year, month)
        today = datetime.now()
        
        _, max_days = calendar.monthrange(year, month)
        if selected_day > max_days:
            selected_day = 1
            client_st.selected_day = 1
        
        with ui.column().classes('w-full gap-1 p-2 hibi-glass rounded-3xl border border-white/10 shadow-xl bg-slate-950/20'):
            with ui.grid(columns=7).classes('w-full gap-1 text-center'):
                for idx, day_name in enumerate(days_jp):
                    lbl = ui.label(day_name).classes('text-[10px] font-bold py-1')
                    if idx == 0:  
                        lbl.style('color: #ef4444 !important;')
                    elif idx == 6:  
                        lbl.style('color: #3b82f6 !important;')
                    else:
                        lbl.classes('calendar-header-weekday')
            
            with ui.grid(columns=7).classes('w-full gap-1'):
                for week in month_weeks:
                    for day_idx, day in enumerate(week):
                        if day == 0:
                            ui.element('div').classes('w-full h-16') 
                        else:
                            is_today = (today.year == year and today.month == month and today.day == day)
                            is_selected = (
                                getattr(client_st, 'selected_year', today.year) == year and
                                getattr(client_st, 'selected_month', today.month) == month and
                                selected_day == day
                            )
                            is_holiday_day = date(year, month, day) in japan_holidays
                            
                            if day_idx == 0 or is_holiday_day:  
                                day_style = 'color: #ef4444 !important; font-weight: bold;'
                                day_class = ''
                            elif day_idx == 6:  
                                day_style = 'color: #3b82f6 !important; font-weight: bold;'
                                day_class = ''
                            else:  
                                day_class = 'calendar-day-weekday font-bold'
                                day_style = ''
                                
                            primary_color = theme_data.get('primary', '#6366f1')
                            
                            if is_selected:
                                bg_val = 'rgba(99, 102, 241, 0.2)' if is_light else 'rgba(255, 255, 255, 0.22)'
                                cell_bg = ''
                                cell_style = f'background-color: {bg_val} !important; border: 2px solid {primary_color} !important; box-shadow: 0 0 10px {primary_color}80 !important;'
                            elif is_today:
                                bg_val = 'rgba(15, 23, 42, 0.03)' if is_light else 'rgba(255, 255, 255, 0.08)'
                                cell_bg = ''
                                cell_style = f'background-color: {bg_val} !important; border: 1.5px dashed {primary_color} !important;'
                            else:
                                cell_bg = 'bg-white/5 hover:bg-white/10'
                                cell_style = ''
                            
                            day_events = events_by_day.get(day, [])
                            
                            def select_day_handler(d=day):
                                client_st.selected_year = year
                                client_st.selected_month = month
                                client_st.selected_day = d
                                draw_mobile_calendar_grid.refresh()
                                draw_mobile_selected_day_events.refresh()
                            
                            with ui.column().classes(f'w-full h-16 flex flex-col items-stretch justify-start rounded-lg cursor-pointer transition-all p-1 gap-1 {cell_bg}').style(cell_style).on('click', lambda e, d=day: select_day_handler(d)):
                                with ui.row().classes('w-full items-center justify-between no-wrap px-0.5'):
                                    ui.label(str(day)).classes(f'text-[10px] font-bold leading-none {day_class}').style(day_style)
                                
                                if day_events:
                                    with ui.column().classes('w-full gap-0.5 overflow-hidden flex-grow justify-start'):
                                        if len(day_events) <= 2:
                                            for ev in day_events:
                                                title = ev.get('title', 'イベント')
                                                genre = ev.get('genre', '飲み会')
                                                is_past_ev = is_event_past(ev.get('event_date'))
                                                is_del_ev = ev.get('deleted_at') is not None
                                                bg_color_cls = get_genre_badge_colors(genre, is_past_ev, is_del_ev)
                                                ui.label(title).classes(f'text-[8px] leading-tight px-1 py-0.5 rounded text-center truncate block w-full font-bold {bg_color_cls}')
                                        else:
                                            ev1 = day_events[0]
                                            title1 = ev1.get('title', 'イベント')
                                            genre1 = ev1.get('genre', '飲み会')
                                            bg_color_cls1 = get_genre_badge_colors(genre1, is_event_past(ev1.get('event_date')), ev1.get('deleted_at') is not None)
                                            ui.label(title1).classes(f'text-[8px] leading-tight px-1 py-0.5 rounded text-center truncate block w-full font-bold {bg_color_cls1}')
                                            ui.label('>>').classes('text-[8px] text-indigo-400 dark:text-indigo-300 font-extrabold text-center block w-full leading-none mt-1 animate-pulse').tooltip('他複数のイベントがあります')

    @ui.refreshable
    def draw_mobile_selected_day_events():
        year = client_st.calendar_year
        month = client_st.calendar_month
        events = client_st.cached_events
        selected_day = getattr(client_st, 'selected_day', datetime.now().day)
        
        day_events = []
        for ev in events:
            date_str = ev.get('event_date')
            if date_str:
                try:
                    ev_dt = date_parser.parse(date_str)
                    if ev_dt.year == year and ev_dt.month == month and ev_dt.day == selected_day:
                        day_events.append(ev)
                except Exception:
                    pass
                    
        with ui.column().classes('w-full gap-3 px-1 mt-1'):
            ui.label(f"📅 {month}月{selected_day}日の公式イベント ({len(day_events)}件)").classes('text-xs font-extrabold text-indigo-300 pl-1')
            
            if not day_events:
                with ui.column().classes('w-full items-center justify-center p-6 hibi-glass rounded-2xl border border-white/5'):
                    ui.icon('event_note', size='2rem', color='white').classes('opacity-20')
                    ui.label('この日の公式イベントはありません。').classes('text-slate-500 dark:text-white/40 text-[11px] mt-1')
            else:
                for ev in day_events:
                    draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)

    @ui.refreshable
    def draw_mobile_status_bar():
        year = client_st.calendar_year
        month = client_st.calendar_month
        events = client_st.cached_events
        
        upcoming_count = 0  
        past_count = 0      
        for ev in events:
            date_str = ev.get('event_date')
            if date_str:
                try:
                    ev_dt = date_parser.parse(date_str)
                    if ev_dt.year == year and ev_dt.month == month:
                        if is_event_past(date_str):
                            past_count += 1
                        else:
                            upcoming_count += 1
                except Exception:
                    pass
                    
        total_events_count = upcoming_count + past_count
        if total_events_count > 0:
            with ui.row().classes('w-full items-center justify-between p-3 bg-indigo-500/10 dark:bg-indigo-500/15 border border-indigo-500/20 rounded-2xl no-wrap shadow-sm mb-1'):
                with ui.row().classes('items-center gap-1.5 truncate flex-grow'):
                    ui.icon('campaign', color='indigo-400', size='22px').classes('shrink-0')
                    ui.label(f"{month}月のイベント状況：").classes('text-xs font-bold text-slate-800 dark:text-indigo-200 shrink-0')
                with ui.row().classes('items-center gap-1 shrink-0 no-wrap'):
                    ui.badge(f"予定 {upcoming_count}", color='indigo-600').classes('text-[9px] px-1.5 py-0.5')
                    ui.badge(f"終了 {past_count}", color='slate-600').classes('text-[9px] px-1.5 py-0.5')

    @ui.refreshable
    def draw_mobile_flats_list():
        active_flats = get_active_flats()
        if active_flats:
            with ui.column().classes('w-full gap-2 px-1 mb-2'):
                ui.label('🍻 本日限定の突発ふらっと').classes('text-xs font-extrabold text-cyan-600 dark:text-cyan-400 pl-1 animate-pulse')
                draw_flat_special_card(active_flats[0], current_user_id, is_su, refresh_all, enter_chat_cb)
                if len(active_flats) > 1:
                    with ui.expansion(f'他のふらっとを見る ({len(active_flats)-1}件)', icon='expand_more').classes('w-full border border-cyan-500/20 rounded-xl overflow-hidden').props('header-class="text-cyan-600 dark:text-cyan-400 text-xs font-bold bg-cyan-100 dark:bg-cyan-950/20"'):
                        with ui.column().classes('w-full gap-3 p-2 bg-slate-100 dark:bg-black/10'):
                            for room in active_flats[1:]:
                                draw_flat_special_card(room, current_user_id, is_su, refresh_all, enter_chat_cb)

    def draw_mobile_calendar_container():
        def handle_select_change(val_str: str):
            if getattr(client_st, 'ignore_select_change', False): return
            if not val_str: return
            try:
                y_str, m_str = val_str.split('-')
                client_st.calendar_year = int(y_str)
                client_st.calendar_month = int(m_str)
                refresh_all()
            except Exception: pass
                
        def prev_month():
            if client_st.calendar_month == 1:
                client_st.calendar_month = 12
                client_st.calendar_year -= 1
            else:
                client_st.calendar_month -= 1
            refresh_all()
            
        def next_month():
            if client_st.calendar_month == 12:
                client_st.calendar_month = 1
                client_st.calendar_year += 1
            else:
                client_st.calendar_month += 1
            refresh_all()
            
        with ui.column().classes('w-full gap-3'):
            with ui.column().classes('w-full gap-1 px-1'):
                with ui.row().classes('w-full items-center justify-between no-wrap'):
                    current_val = f"{client_st.calendar_year}-{client_st.calendar_month}"
                    with ui.row().classes('items-center gap-1.5 flex-grow overflow-hidden'):
                        ui.icon('event', size='sm', color='indigo-400').classes('shrink-0')
                        
                        curr_key = f"{client_st.calendar_year}-{client_st.calendar_month}"
                        if curr_key not in select_options:
                            select_options[curr_key] = f"{client_st.calendar_year}年 {client_st.calendar_month}月"
                            
                        m_select = ui.select(
                            options=select_options, 
                            value=current_val,
                            on_change=lambda e: handle_select_change(e.value)
                        ).classes('w-44 text-sm font-bold').props('outlined dense options-dense color="indigo"').style('background-color: rgba(255,255,255,0.03);')
                        client_st.mobile_month_select = m_select
                    
                    with ui.row().classes('gap-1 items-center shrink-0'):
                        ui.button(icon='chevron_left', on_click=prev_month).props('flat text-color=white size=xs').classes('w-8 h-8 flex items-center justify-center bg-white/10 hover:bg-white/20 border border-white/5 rounded')
                        ui.button(icon='chevron_right', on_click=next_month).props('flat text-color=white size=xs').classes('w-8 h-8 flex items-center justify-center bg-white/10 hover:bg-white/20 border border-white/5 rounded')
            
            draw_mobile_status_bar()
            draw_mobile_calendar_grid()
            draw_mobile_flats_list()
            draw_mobile_selected_day_events()


    @ui.refreshable
    def draw_upcoming_list():
        year = client_st.calendar_year
        month = client_st.calendar_month
        events = client_st.cached_events

        active_flats = get_active_flats()
        if active_flats:
            with ui.column().classes('w-full gap-3 p-0 m-0 mb-2'):
                ui.label('🍻 本日限定の即飲み急募！').classes('text-xs font-extrabold text-cyan-600 dark:text-cyan-400 pl-1 animate-pulse')
                draw_flat_special_card(active_flats[0], current_user_id, is_su, refresh_all, enter_chat_cb)
                
                if len(active_flats) > 1:
                    with ui.expansion(f'他のふらっと募集を展開 ({len(active_flats)-1}件)', icon='expand_more').classes('w-full border border-cyan-500/20 rounded-xl overflow-hidden').props('header-class="text-cyan-600 dark:text-cyan-400 text-xs font-bold bg-cyan-100 dark:bg-cyan-950/10"'):
                        with ui.column().classes('w-full gap-4 p-3 bg-slate-100 dark:bg-black/10'):
                            for room in active_flats[1:]:
                                draw_flat_special_card(room, current_user_id, is_su, refresh_all, enter_chat_cb)
            
            ui.element('q-separator').props('dark font-bold').classes('my-2 bg-slate-300 dark:bg-white/5')

        monthly_upcoming = []
        for ev in events:
            if not is_event_past(ev.get('event_date', '')):
                try:
                    ev_dt = date_parser.parse(ev.get('event_date'))
                    if ev_dt.year == year and ev_dt.month == month:
                        monthly_upcoming.append(ev)
                except Exception:
                    pass
                    
        def get_dt(item):
            try: return date_parser.parse(item.get('event_date', ''))
            except Exception: return datetime.max
        monthly_upcoming = sorted(monthly_upcoming, key=get_dt)
        
        with ui.column().classes('w-full gap-4 p-0 m-0'):
            if not monthly_upcoming:
                with ui.column().classes('w-full items-center justify-center p-8 hibi-glass rounded-xl'):
                    ui.icon('event', size='3rem', color='white').classes('opacity-30')
                    ui.label(f'{month}月の予定はありません。').classes('text-slate-500 dark:text-white/50 text-xs mt-2 text-center')
            else:
                if len(monthly_upcoming) <= 2:
                    for ev in monthly_upcoming:
                        draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)
                else:
                    for ev in monthly_upcoming[:2]:
                        draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)
                    
                    with ui.expansion('もっと見る', icon='expand_more').classes('w-full border border-slate-300 dark:border-white/5 rounded-xl overflow-hidden').props('header-class="text-indigo-500 dark:text-indigo-300 font-bold bg-slate-100 dark:bg-white/5"'):
                        with ui.column().classes('w-full gap-4 p-3 bg-slate-50 dark:bg-black/15'):
                            for ev in monthly_upcoming[2:]:
                                draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)

    @ui.refreshable
    def draw_past_list():
        year = client_st.calendar_year
        month = client_st.calendar_month
        events = client_st.cached_events

        monthly_past = []
        for ev in events:
            if is_event_past(ev.get('event_date', '')):
                try:
                    ev_dt = date_parser.parse(ev.get('event_date'))
                    if ev_dt.year == year and ev_dt.month == month:
                        monthly_past.append(ev)
                except Exception:
                    pass
                    
        def get_dt(item):
            try: return date_parser.parse(item.get('event_date', ''))
            except Exception: return datetime.min
        monthly_past = sorted(monthly_past, key=get_dt, reverse=True)
        
        with ui.column().classes('w-full gap-4 p-0 m-0'):
            if not monthly_past:
                with ui.column().classes('w-full items-center justify-center p-8 hibi-glass rounded-xl'):
                    ui.icon('history', size='3rem', color='white').classes('opacity-30')
                    ui.label(f'{month}月に終了したイベントはありません。').classes('text-slate-500 dark:text-white/50 text-xs mt-2 text-center')
            else:
                if len(monthly_past) <= 2:
                    for ev in monthly_past:
                        draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)
                else:
                    for ev in monthly_past[:2]:
                        draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)
                    
                    with ui.expansion('もっと見る', icon='expand_more').classes('w-full border border-slate-300 dark:border-white/5 rounded-xl overflow-hidden').props('header-class="text-indigo-500 dark:text-indigo-300 font-bold bg-slate-100 dark:bg-white/5"'):
                        with ui.column().classes('w-full gap-4 p-3 bg-slate-50 dark:bg-black/15'):
                            for ev in monthly_past[2:]:
                                draw_event_card(ev, current_user_id, is_su, enter_chat_cb, refresh_all, open_detail_safely, open_edit_safely)

    # ★ 評価画面も含め、カレンダー親レイアウト全体の切り替え制御を確実にするリフレッシュ
    @ui.refreshable
    def draw_all_ui():
        # ★ 評価ページ切り替え中なら、抽出した review_ui を呼び出して全画面描画する
        if getattr(client_st, 'review_event', None):
            draw_inline_review_page(client_st, current_user_id, refresh_all)
            return

        with ui.element('div').classes('events-pc-only w-full items-center justify-between mb-6 no-wrap gap-4'):
            with ui.column().classes('gap-1'):
                ui.label('イベントカレンダー').classes('text-2xl font-extrabold tracking-wider text-slate-800 dark:text-white')
                #ui.label('公式イベントの確認と、今すぐ飲める突発募集ができます').classes('text-xs text-slate-500 dark:text-white/50')
            
            with ui.row().classes('gap-2 shrink-0 items-center no-wrap'):
                ui.button('🍻 ふらっと即飲みを募集', icon='local_bar', on_click=lambda: confirm_and_open_flat_dialog(current_user_id, is_su, refresh_all, enter_chat_cb)).props('outline color=primary').classes('font-bold rounded-xl px-4 py-2.5 shadow-sm text-sm')
                if is_su:
                    ui.button('📅 公式イベントを告知', icon='add', on_click=open_create_safely).props('outline color=secondary').classes('font-bold rounded-xl px-4 py-2.5 shadow-sm text-sm')

        with ui.element('div').classes('events-mobile-only w-full flex-col gap-3 mb-4'):
            with ui.column().classes('gap-1'):
                ui.label('イベントカレンダー').classes('text-2xl font-extrabold tracking-wider text-slate-800 dark:text-white')
                ui.label('みんなが参加できるイベント一覧です').classes('text-xs text-slate-500 dark:text-white/50')
            
            with ui.column().classes('w-full gap-2 mt-1'):
                ui.button('🍻 今すぐ飲める人をふらっと募集', icon='local_bar', on_click=lambda: confirm_and_open_flat_dialog(current_user_id, is_su, refresh_all, enter_chat_cb)).props('outline color=primary').classes('w-full font-bold rounded-xl py-2.5 shadow-sm text-sm')
                if is_su:
                    ui.button('📅 新規公式イベントを告知する', icon='add', on_click=open_create_safely).props('outline color=secondary').classes('w-full font-bold rounded-xl py-2.5 shadow-sm text-sm')

        with ui.element('div').classes('events-responsive-grid'):
            with ui.element('div').classes('events-pc-only events-pc-col-5 w-full flex-col gap-4'):
                draw_calendar_grid()
                
            with ui.element('div').classes('events-pc-only events-pc-col-7 w-full grid grid-cols-2 gap-6'):
                with ui.element('div').classes('col-span-1 w-full flex flex-col gap-3'):
                    ui.label('📋 開催予定イベント').classes('text-lg font-bold text-indigo-500 dark:text-indigo-300 whitespace-nowrap')
                    draw_upcoming_list()
                    
                with ui.element('div').classes('col-span-1 w-full flex flex-col gap-3'):
                    ui.label('📁 終了したイベント').classes('text-lg font-bold text-slate-500 dark:text-white/50 whitespace-nowrap')
                    draw_past_list()

            with ui.element('div').classes('events-mobile-only w-full flex-col gap-4'):
                draw_mobile_calendar_container()

    def refresh_all(jump_year: int = None, jump_month: int = None):
        client_st.cached_events = fetch_active_events()
        
        if jump_year is not None and jump_month is not None:
            client_st.calendar_year = jump_year
            client_st.calendar_month = jump_month
            client_st.selected_year = jump_year
            client_st.selected_month = jump_month
        
        curr_key = f"{client_st.calendar_year}-{client_st.calendar_month}"
        if curr_key not in select_options:
            select_options[curr_key] = f"{client_st.calendar_year}年 {client_st.calendar_month}月"
        
        if hasattr(client_st, 'mobile_month_select'):
            try:
                client_st.mobile_month_select.options = select_options
                client_st.mobile_month_select.update()
                target_val = f"{client_st.calendar_year}-{client_st.calendar_month}"
                if client_st.mobile_month_select.value != target_val:
                    client_st.ignore_select_change = True  
                    client_st.mobile_month_select.set_value(target_val)
                    client_st.ignore_select_change = False
            except Exception:
                client_st.ignore_select_change = False
        
        # 親ビューを丸ごと再描画して、分岐判定による表示・非表示の変更を適用
        draw_all_ui.refresh()

        if getattr(client_st, 'active_detail_event_id', None) and getattr(client_st, 'detail_dialog_refresh_cb', None):
            try: client_st.detail_dialog_refresh_cb()
            except Exception: pass

    # 初期描画を実行
    draw_all_ui()

    last_state_hash = None
    current_client = context.client
    
    def check_updates():
        if current_client and not current_client.has_socket_connection: return
        nonlocal last_state_hash
        try:
            events_data = fetch_active_events()
            flats_data = get_active_flats()
            
            current_state = [f"{ev.get('id')}_{len(ev.get('participant_ids', []))}_{ev.get('deleted_at')}" for ev in events_data]
            current_state += [f"flat_{f.get('id')}_{len(f.get('participant_ids', []))}_{f.get('status')}" for f in flats_data]
            
            if last_state_hash is None:
                last_state_hash = str(current_state)
                return
                
            if str(current_state) != last_state_hash:
                last_state_hash = str(current_state)
                refresh_all()
        except Exception: pass
            
    ui.timer(3.0, check_updates)