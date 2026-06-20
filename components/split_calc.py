# components/split_calc.py
from nicegui import ui
import math

def calculate_dutch_treat(total_bill: int, std_count: int, heavy_count: int, heavy_extra: int, light_count: int, light_discount: int, round_unit: int):
    """
    傾斜割り勘の計算ロジック。
    """
    total_people = std_count + heavy_count + light_count
    if total_people == 0:
        return None

    # 普通の人の基準額 X を逆算する方程式
    numerator = total_bill - (heavy_count * heavy_extra) + (light_count * light_discount)
    raw_base = numerator / total_people
    
    # 端数処理（丸め）
    if round_unit > 1:
        std_payment = math.ceil(raw_base / round_unit) * round_unit
    else:
        std_payment = int(raw_base)

    # 各グループの支払額を算出
    heavy_payment = std_payment + heavy_extra
    light_payment = std_payment - light_discount

    # 実際に回収できる合計金額
    collected_total = (std_count * std_payment) + (heavy_count * heavy_payment) + (light_count * light_payment)
    
    # 差額（お釣り、または不足額）
    diff = collected_total - total_bill

    return {
        "std_pay": max(0, std_payment),
        "heavy_pay": max(0, heavy_payment),
        "light_pay": max(0, light_payment),
        "collected_total": collected_total,
        "diff": diff,
    }


def render_split_calc():
    ui.label('割り勘傾斜計算機').classes('text-2xl font-extrabold tracking-wider text-white')
    ui.label('先輩の上乗せ、ノンアルの割引、端数の計算も一瞬で解決します').classes('text-xs text-white/50 -mt-4 mb-2')

    # 初期表示＆リセット用の値（すべて0スタート）
    INITIAL_STATE = {
        'total_bill': 0,
        'std_count': 0,
        'heavy_count': 0,
        'heavy_extra': 0,
        'light_count': 0,
        'light_discount': 0,
        'round_unit': 100  # これを0にするとゼロ除算エラーになるため100を維持
    }

    # リアクティブな入力状態
    state = INITIAL_STATE.copy()
    
    # UIコンポーネントの参照を保持する辞書
    refs = {}

    @ui.refreshable
    def draw_results():
        """計算結果を描画するエリア"""
        res = calculate_dutch_treat(
            total_bill=state['total_bill'],
            std_count=state['std_count'],
            heavy_count=state['heavy_count'],
            heavy_extra=state['heavy_extra'],
            light_count=state['light_count'],
            light_discount=state['light_discount'],
            round_unit=state['round_unit']
        )
        
        if not res:
            with ui.card().classes('w-full bg-red-950/20 border border-red-500/30 p-4 text-center text-red-300 text-xs rounded-xl'):
                ui.label('合計人数が0人です。人数を入力してください。')
            return

        with ui.column().classes('w-full gap-3 mt-2'):
            # 結果表示カード
            with ui.card().classes('w-full bg-cyan-950/20 border border-cyan-500/30 p-5 rounded-2xl shadow-xl'):
                ui.label('💸 一人あたりの支払額').classes('text-xs font-bold text-cyan-400 border-b border-cyan-500/10 pb-1.5 w-full')
                
                # 多めグループ
                if state['heavy_count'] > 0:
                    with ui.row().classes('w-full justify-between items-center text-xs mt-2'):
                        ui.label(f'👑 多めの人 (先輩・主役など) × {state["heavy_count"]}人').classes('text-white font-bold')
                        with ui.row().classes('items-baseline gap-1'):
                            ui.label(f'{res["heavy_pay"]:,}').classes('text-lg font-black text-amber-400 font-mono')
                            ui.label('円').classes('text-[10px] text-white/50')
                
                # 普通グループ
                if state['std_count'] > 0:
                    with ui.row().classes('w-full justify-between items-center text-xs mt-2'):
                        ui.label(f'🍺 普通の人 × {state["std_count"]}人').classes('text-white')
                        with ui.row().classes('items-baseline gap-1'):
                            ui.label(f'{res["std_pay"]:,}').classes('text-base font-bold text-white font-mono')
                            ui.label('円').classes('text-[10px] text-white/50')
                            
                # 少なめグループ
                if state['light_count'] > 0:
                    with ui.row().classes('w-full justify-between items-center text-xs mt-2'):
                        ui.label(f'☕ 少なめの人 (ノンアル・遅刻など) × {state["light_count"]}人').classes('text-white/70')
                        with ui.row().classes('items-baseline gap-1'):
                            ui.label(f'{res["light_pay"]:,}').classes('text-sm font-bold text-slate-300 font-mono')
                            ui.label('円').classes('text-[10px] text-white/50')

            # 集計詳細カード
            with ui.row().classes('w-full justify-between gap-3 text-xs'):
                # 集金合計
                with ui.card().classes('flex-grow bg-slate-900/60 border border-white/5 p-3 rounded-xl gap-0.5'):
                    ui.label('集金合計').classes('text-[9px] text-white/40 font-bold')
                    ui.label(f'{res["collected_total"]:,} 円').classes('text-sm font-bold text-white font-mono')
                
                # 端数（お釣り、または不足）
                diff_val = res['diff']
                diff_color = 'text-green-400' if diff_val >= 0 else 'text-red-400'
                diff_label = '幹事の財布に余る額（お釣り）' if diff_val >= 0 else '不足している額'
                
                with ui.card().classes('flex-grow bg-slate-900/60 border border-white/5 p-3 rounded-xl gap-0.5'):
                    ui.label(diff_label).classes('text-[9px] text-white/40 font-bold')
                    ui.label(f'{abs(diff_val):,} 円').classes(f'text-sm font-bold {diff_color} font-mono')


    def reset_form():
        """入力値をすべて0クリアする"""
        state.update(INITIAL_STATE.copy())
        
        # 辞書に格納した参照を使ってUIの数値を確実に0にリセット
        refs['total_bill'].value = state['total_bill']
        refs['std_count'].value = state['std_count']
        refs['heavy_count'].value = state['heavy_count']
        refs['heavy_extra'].value = state['heavy_extra']
        refs['light_count'].value = state['light_count']
        refs['light_discount'].value = state['light_discount']
        refs['round_unit'].value = state['round_unit']
        
        # 画面を再描画して通知を出す
        draw_results.refresh()
        ui.notify('すべて0にクリアしました！', type='positive', position='top')


    # --- 入力インターフェース部分 ---
    with ui.card().classes('w-full hibi-glass rounded-xl p-5 gap-4 shadow-xl text-white'):
        # タイトルとリセットボタン
        with ui.row().classes('w-full justify-between items-center border-b border-white/10 pb-1.5'):
            ui.label('💵 お会計データ入力').classes('text-xs font-bold text-cyan-400')
            ui.button('クリア', on_click=reset_form).props('outline color=white size=sm dense').classes('px-3 py-1 text-[10px]')
        
        # 合計金額
        refs['total_bill'] = ui.number(
            'お店の合計お会計 (円)', 
            value=state['total_bill'], 
            format='%.0f',
            on_change=lambda e: (state.update({'total_bill': int(e.value or 0)}), draw_results.refresh())
        ).classes('w-full').props('dark filled color=cyan')

        # 3つのグループの人数・差額設定
        with ui.row().classes('w-full gap-3 no-wrap'):
            # 普通の人
            with ui.card().classes('w-1/3 bg-black/20 border border-white/5 p-3 rounded-xl gap-1'):
                ui.label('🍺 普通の人').classes('text-[10px] text-cyan-400 font-bold')
                refs['std_count'] = ui.number(
                    '人数', 
                    value=state['std_count'], 
                    format='%.0f',
                    on_change=lambda e: (state.update({'std_count': int(e.value or 0)}), draw_results.refresh())
                ).classes('w-full').props('dark dense borderless')
            
            # 多めの人
            with ui.card().classes('w-1/3 bg-black/20 border border-white/5 p-3 rounded-xl gap-1'):
                ui.label('👑 多めの人').classes('text-[10px] text-amber-400 font-bold')
                refs['heavy_count'] = ui.number(
                    '人数', 
                    value=state['heavy_count'], 
                    format='%.0f',
                    on_change=lambda e: (state.update({'heavy_count': int(e.value or 0)}), draw_results.refresh())
                ).classes('w-full').props('dark dense borderless')
                refs['heavy_extra'] = ui.number(
                    '上乗せ (+円)', 
                    value=state['heavy_extra'], 
                    format='%.0f',
                    on_change=lambda e: (state.update({'heavy_extra': int(e.value or 0)}), draw_results.refresh())
                ).classes('w-full text-xs').props('dark dense borderless')
                    
            # 少なめの人
            with ui.card().classes('w-1/3 bg-black/20 border border-white/5 p-3 rounded-xl gap-1'):
                ui.label('☕ 少なめの人').classes('text-[10px] text-slate-400 font-bold')
                refs['light_count'] = ui.number(
                    '人数', 
                    value=state['light_count'], 
                    format='%.0f',
                    on_change=lambda e: (state.update({'light_count': int(e.value or 0)}), draw_results.refresh())
                ).classes('w-full').props('dark dense borderless')
                refs['light_discount'] = ui.number(
                    '割引 (-円)', 
                    value=state['light_discount'], 
                    format='%.0f',
                    on_change=lambda e: (state.update({'light_discount': int(e.value or 0)}), draw_results.refresh())
                ).classes('w-full text-xs').props('dark dense borderless')

        # 丸め単位の選択
        round_options = {1: "1円単位（端数なし）", 10: "10円単位に切り上げ", 100: "100円単位に切り上げ", 500: "500円単位に切り上げ", 1000: "1000円単位に切り上げ"}
        refs['round_unit'] = ui.select(
            options=round_options, 
            label='小銭の丸め単位', 
            value=state['round_unit'],
            on_change=lambda e: (state.update({'round_unit': int(e.value or 100)}), draw_results.refresh())
        ).classes('w-full').props('dark filled color=cyan')

    # 結果を最初から下に描画
    draw_results()