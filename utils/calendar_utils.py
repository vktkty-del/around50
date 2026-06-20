# utils/calendar_utils.py
import calendar
import datetime
from nicegui import context

# カレンダーの週の始まりを日曜日に設定
calendar.setfirstweekday(calendar.SUNDAY)

MONTH_NAMES_EN = [
    "", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
]

def get_user_calendar_state():
    """
    ユーザーごとのカレンダー状態（年、月、選択日、フィルタ状態など）を
    NiceGUIのclientオブジェクトに保持・初期化する
    """
    client_obj = context.client
    
    if not hasattr(client_obj, 'calendar_year'):
        client_obj.calendar_year = datetime.datetime.now().year
    if not hasattr(client_obj, 'calendar_month'):
        client_obj.calendar_month = datetime.datetime.now().month
    if not hasattr(client_obj, 'filter_events_only'):
        client_obj.filter_events_only = False
    if not hasattr(client_obj, 'ignore_select_change'):
        client_obj.ignore_select_change = False
    
    if not hasattr(client_obj, 'selected_year'):
        client_obj.selected_year = datetime.datetime.now().year
    if not hasattr(client_obj, 'selected_month'):
        client_obj.selected_month = datetime.datetime.now().month
    if not hasattr(client_obj, 'selected_day'):
        client_obj.selected_day = datetime.datetime.now().day  
        
    # 評価ページ切り替え用の状態を追加
    if not hasattr(client_obj, 'review_event'):
        client_obj.review_event = None

    return client_obj


def get_japanese_holidays(year: int) -> set:
    """
    指定された年の日本の祝日（振替休日、国民の休日を含む）を計算してsetで返す
    """
    holidays = set()
    
    # 春分の日・秋分の日の簡易計算式 (1980年〜2099年に対応)
    if 1980 <= year <= 2099:
        vernal_day = int(20.8431 + 0.242194 * (year - 1980)) - int((year - 1980) / 4)
        autumnal_day = int(23.2488 + 0.242194 * (year - 1980)) - int((year - 1980) / 4)
    else:
        vernal_day, autumnal_day = 20, 23
        
    def happy_monday(month: int, nth: int) -> int:
        first_day = datetime.date(year, month, 1)
        first_monday_offset = (0 - first_day.weekday()) % 7
        return 1 + first_monday_offset + (nth - 1) * 7

    # 固定の祝日
    fixed_holidays = [
        (1, 1), (2, 11), (2, 23), (4, 29), (5, 3), (5, 4), (5, 5), (8, 11), (11, 3), (11, 23)
    ]
    for m, d in fixed_holidays:
        holidays.add(datetime.date(year, m, d))
        
    # 変動する祝日を追加
    holidays.add(datetime.date(year, 3, vernal_day))
    holidays.add(datetime.date(year, 9, autumnal_day))
    holidays.add(datetime.date(year, 1, happy_monday(1, 2)))   # 成人の日
    holidays.add(datetime.date(year, 7, happy_monday(7, 3)))   # 海の日
    holidays.add(datetime.date(year, 9, happy_monday(9, 3)))   # 敬老の日
    holidays.add(datetime.date(year, 10, happy_monday(10, 2))) # スポーツの日
    
    # 振替休日の計算（祝日が日曜日の場合、翌日以降の平日を休みにする）
    substitute_holidays = set()
    for h_date in sorted(holidays):
        if h_date.weekday() == 6: # 6 = 日曜日
            sub_date = h_date + datetime.timedelta(days=1)
            while sub_date in holidays or sub_date in substitute_holidays:
                sub_date += datetime.timedelta(days=1)
            substitute_holidays.add(sub_date)
    holidays.update(substitute_holidays)
    
    # 国民の休日の計算（祝日と祝日に挟まれた平日を休みにする）
    citizens_holidays = set()
    sorted_holidays = sorted(holidays)
    for i in range(len(sorted_holidays) - 1):
        d1 = sorted_holidays[i]
        d2 = sorted_holidays[i+1]
        if (d2 - d1).days == 2:
            sandwich_day = d1 + datetime.timedelta(days=1)
            if sandwich_day.weekday() != 6: # 日曜でなければ追加
                citizens_holidays.add(sandwich_day)
    holidays.update(citizens_holidays)
    
    return holidays