#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
科教大会颁奖排表生成器：data.json -> 三表工作簿
  1 座位排布表（唯一数据源：主席台席位 + 领奖人座位）
  2 领导排位图(发放顺序)
  3 领奖顺序图
后两表的领导姓名/职务/座次号、领奖人姓名/科室全部以公式引用座位排布表，
改座位表即自动同步（"待定"标红用条件格式，改掉后自动恢复黑字）。
用法：python build_tables.py --data data.json --out 输出.xlsx
"""
import argparse
import json
import math
import os
import re
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.formatting.rule import CellIsRule, FormulaRule

PALETTE = [('FBE5E5', 'C0504D'), ('DCE6F1', '376092'), ('E2EFDA', '4F7942'),
           ('FFF2CC', 'BF8F00'), ('E4E0EC', '60497A'), ('FCE4D6', 'C55A11')]
CN = '①②③④⑤⑥⑦⑧⑨⑩'
GOLD, GOLD_TXT = 'FFD966', '7F6000'
LEAD_BG, LEAD_BD = 'D9E2F3', '2F5597'
GREY_BG, GREY_BD, GREY_TX = 'F2F2F2', 'BFBFBF', '808080'
HDR_BG, HDR_TX = '2F5597', 'FFFFFF'

CEN = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT = Alignment(horizontal='left', vertical='center', wrap_text=True)
FILL_HDR = PatternFill('solid', fgColor=HDR_BG)
FILL_GREY = PatternFill('solid', fgColor=GREY_BG)
FILL_LEAD = PatternFill('solid', fgColor=LEAD_BG)


def seat_order(n, mode='odd_left'):
    """n位领奖人 -> 颁奖领导座次号，自左至右
    odd_left（默认）：左奇降序 + 右偶升序，即 [13,11,...,3,1,2,4,...]
    even_left：左偶降序 + 右奇升序，即 [12,10,...,2,1,3,5,...]
    （1号均居中；2号在左=even_left，2号在右=odd_left）"""
    odds = list(range(1, n + 1, 2))
    evens = list(range(2, n + 1, 2))
    if mode == 'even_left':
        return evens[::-1] + odds
    return odds[::-1] + evens


def lr_label(n, mode='odd_left'):
    seq = seat_order(n, mode)
    return seq[0], seq[-1]


def grade_rank(g):
    """奖级 -> 排序权值：一等奖=1、二等奖=2……数字或中文等次均可；无等次=99"""
    if g in (None, '', 0, False):
        return 99
    if isinstance(g, int):
        return g
    m = re.search(r'[一二三四五六七八九十]', str(g))
    return '一二三四五六七八九十'.index(m.group(0)) + 1 if m else 99


def afill(i):
    return PatternFill('solid', fgColor=PALETTE[i % len(PALETTE)][0])


def abox(i, style='thin'):
    c = PALETTE[i % len(PALETTE)][1]
    s = Side(style=style, color=c)
    return Border(left=s, right=s, top=s, bottom=s)


def greybox():
    s = Side(style='dotted', color=GREY_BD)
    return Border(left=s, right=s, top=s, bottom=s)


def cellbox(color):
    s = Side(style='thin', color=color)
    return Border(left=s, right=s, top=s, bottom=s)


def f(size=11, bold=False, color='000000'):
    return Font(name='宋体', size=size, bold=bold, color=color)


def put(ws, r, c, v, font=None, align=CEN, fill=None, border=None):
    x = ws.cell(r, c, v)
    if font:
        x.font = font
    x.alignment = align
    if fill:
        x.fill = fill
    if border:
        x.border = border
    return x


def paint(ws, r1, c1, r2, c2, fill=None, border=None):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            if fill:
                ws.cell(r, c).fill = fill
            if border:
                ws.cell(r, c).border = border


def fit_h(txt, per):
    """按每行可容纳字数估算行高，避免长文本被截断"""
    return max(20, math.ceil(len(str(txt)) / per) * 14 + 8)


def setup_page(ws, paper=9, fit_w=1, fit_h=0):
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = paper
    ws.page_setup.scale = None  # 固定缩放与 fitToPage 冲突，会导致打印两侧大空白
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = fit_w
    ws.page_setup.fitToHeight = fit_h
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5


def cn_no(i):
    return CN[i] if i < len(CN) else f'({i + 1})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='data.json 路径')
    ap.add_argument('--out', required=True, help='输出 xlsx 路径')
    ap.add_argument('--duty-style', default='compact', choices=['compact', 'full'],
                    help='compact=精简职务（去单位前缀与共有首段），full=原始职务')
    a = ap.parse_args()

    D = json.load(open(a.data, encoding='utf-8'))
    meta = D['meta']
    LEADERS = {int(x['no']): (x['name'], x.get('duty', ''), x.get('org', ''))
               for x in D['leaders']}
    N = len(LEADERS)
    AWARDS = D['awards']
    # 本单位 = 人数最多的单位（其职务不加单位前缀；外单位/上级单位才加，避免歧义）
    _cnt = {}
    for x in D['leaders']:
        _cnt[x.get('org', '') or '—'] = _cnt.get(x.get('org', '') or '—', 0) + 1
    MAIN_ORG = max(_cnt, key=_cnt.get) if _cnt else ''

    def short(s):
        return re.sub(r'（.*?）', '', s or '').strip()

    # 表彰类别/发放部门：从“宣读科技表彰决定”自动推导，也可在 meta.scope/dept 中直接指定
    _ann = meta.get('announcer', '')
    _sm = re.search(r'宣读(.+?)表彰决定', _ann)
    CAT = _sm.group(1) if _sm else ''
    SCOPE = meta.get('scope') or (f'{CAT}处发放部分' if CAT else '')
    DEPT = (meta.get('scope') or '').replace('发放部分', '') or (CAT + '处' if CAT else '')
    HOST = short(meta.get('host', ''))
    AG_MIN = min(int(x.get('agenda', 0)) for x in AWARDS) if AWARDS else 0
    AG_MAX = max(int(x.get('agenda', 0)) for x in AWARDS) if AWARDS else 0

    # 职务显示：去掉单位前缀（单位已在“台上单位”行标注）；compact 模式下
    # 再去掉多数人共有的首段（如“院党委委员、”），避免每格重复、撑爆列宽
    _raw = {}
    for _no, (_nm, _d, _o) in LEADERS.items():
        _s = (_d or '').strip()
        if _o and _s.startswith(_o):
            _s = _s[len(_o):].strip()
        _raw[_no] = _s
    _first = {}
    for _s in _raw.values():
        _f = re.split(r'[、,，]', _s)[0].strip()
        _first[_f] = _first.get(_f, 0) + 1
    _common = max(_first, key=_first.get) if _first else ''
    DUTY = {}
    for _no, _s in _raw.items():
        if a.duty_style == 'compact' and _first.get(_common, 0) > 1:
            _parts = re.split(r'[、,，]', _s)
            if len(_parts) > 1 and _parts[0].strip() == _common:
                _s = '、'.join(_parts[1:]).strip()
        if HOST and LEADERS[_no][0] == HOST:
            _s += '（大会主持）'
        DUTY[_no] = _s

    EXCL = D.get('excluded_agenda', []) or []
    EXCL_SEQ = [int(x['seq']) if isinstance(x, dict) else int(x) for x in EXCL]
    lay = D.get('layout', {})
    FIRST_SEAT_ROW = int(lay.get('first_seat_row', 4))
    SEATS_PER_ROW = int(lay.get('seats_per_row', 6))
    TOTAL = sum(len(x['items']) for x in AWARDS)
    LAST_ROW = FIRST_SEAT_ROW - 1 + math.ceil(TOTAL / SEATS_PER_ROW)
    SEAT_MODE = lay.get('seat_mode', 'odd_left')
    _odd_left = SEAT_MODE != 'even_left'
    _sides = '奇数号在左、偶数号在右' if _odd_left else '偶数号在左、奇数号在右'
    _ends = ('左端为最大奇数号、右端为最大偶数号' if _odd_left
             else '左端为最大偶数号、右端为最大奇数号')
    LEFT_TO_RIGHT = seat_order(N, SEAT_MODE)
    # 礼仪分配：
    #   A) layout.usher_groups 指定自定义分组（按台上左→右的座次号列表，如
    #      [[12,10],[8,6],[4,2],[1],[3,5],[7,9],[11,13]]，可配 layout.usher_note 补充说明）；
    #   B) 未指定时按 layout.ushers 人数自动分配：前 PAIRS 名各带2位领导，其余各带1位
    GROUPS = lay.get('usher_groups') or None
    if GROUPS:
        GROUPS = [[int(s) for s in g] for g in GROUPS]
        _seq = [s for g in GROUPS for s in g]
        if sorted(_seq) != sorted(LEFT_TO_RIGHT):
            raise SystemExit(f'usher_groups 座次号与主席台不符：{sorted(_seq)} '
                             f'vs {sorted(LEFT_TO_RIGHT)}')
        _pos = {s: i for i, s in enumerate(LEFT_TO_RIGHT)}
        if any(_pos[x] >= _pos[y] for x, y in zip(_seq, _seq[1:])):
            raise SystemExit('usher_groups 需按台上自左至右顺序列出各组座次号')
        USHER = {}
        for k, g in enumerate(GROUPS):
            for s in g:
                USHER[s] = f'礼仪{k + 1}'
        U = len(GROUPS)
        PAIRS = sum(1 for g in GROUPS if len(g) == 2)
    else:
        U = int(lay.get('ushers', 0) or 0) or math.ceil(N / 2)
        if not math.ceil(N / 2) <= U <= N:
            raise SystemExit(f'礼仪人数 {U} 不合法：需在 {math.ceil(N / 2)}（每人带2位）'
                             f'到 {N}（每人带1位）之间')
        PAIRS = N - U
        USHER = {}
        for i, s in enumerate(LEFT_TO_RIGHT):
            USHER[s] = (f'礼仪{i // 2 + 1}' if i < 2 * PAIRS
                        else f'礼仪{i - PAIRS + 1}')
    _n2 = sum(1 for g in (GROUPS or []) if len(g) == 2)
    if GROUPS and _n2 == U:
        USHER_DESC = f'共{U}名，每名各对应2位领导'
    elif GROUPS and _n2 == 0:
        USHER_DESC = f'共{U}名，每名各对应1位领导'
    elif GROUPS:
        USHER_DESC = f'共{U}名，{_n2}名各对应2位领导、{U - _n2}名各对应1位领导'
    else:
        USHER_DESC = f'共{U}名，前{PAIRS}名各对应2位领导、后{U - PAIRS}名各对应1位领导'
    if lay.get('usher_note'):
        USHER_DESC += '；' + lay['usher_note']

    # 领奖对位规则：
    #   默认（无等次）：领奖人按明细顺序自左至右列队，依次对位台上同位置的领导；
    #   有等次（如一/二/三等奖）：改为“奖级高者对位领导职务高者”——
    #   一等奖→1号、二等奖→2、3号、三等奖→4、5、6号……同级按明细顺序，
    #   领导排位不动，领奖人上台后各立于所对位领导面前。
    ORDER, LEADER_OF, ITEM_OF_LEADER, GRADE_SUM, MANUAL = [], [], [], [], []
    for aw in AWARDS:
        items = aw['items']
        n = len(items)
        seq = seat_order(n, SEAT_MODE)
        manual = [it.get('leader_no') for it in items]
        if any(m is not None for m in manual):
            # 显式指定对位（items 带 leader_no）：行序=名单顺序，行 k 的领奖人对位
            # manual[k] 号领导；颁奖领导序列（如 3,1,2）与其他批次 zig-zag 模式一致，
            # 领导席位不动。leader_no 须为 1..n 的完整排列。
            assert sorted(int(m) for m in manual) == list(range(1, n + 1)), \
                f'{aw["name"]}: leader_no 须为 1..{n} 的完整排列（当前 {manual}）'
            leader_of = {k: int(m) for k, m in enumerate(manual)}
            order = list(range(n))
            cnt = {}
            for it in items:
                g = it.get('grade')
                if g:
                    cnt[g] = cnt.get(g, 0) + 1
            grade_sum = '、'.join(f'{g}{c}项' for g, c in sorted(cnt.items(), key=lambda x: grade_rank(x[0])))
            MANUAL.append(True)
        elif any(it.get('grade') for it in items):
            order = sorted(range(n), key=lambda k: (grade_rank(items[k].get('grade')), k))
            leader_of = {k: r + 1 for r, k in enumerate(order)}
            cnt = {}
            for it in items:
                g = it.get('grade')
                if g:
                    cnt[g] = cnt.get(g, 0) + 1
            grade_sum = '、'.join(f'{g}{c}项' for g, c in sorted(cnt.items(), key=lambda x: grade_rank(x[0])))
            MANUAL.append(False)
        else:
            # 默认对位（zig-zag，与台上位置一致）：行 i 的领奖人 → seq[i] 号领导
            order = list(range(n))
            leader_of = {k: seq[k] for k in range(n)}
            grade_sum = ''
            MANUAL.append(False)
        ORDER.append(order)
        LEADER_OF.append(leader_of)
        ITEM_OF_LEADER.append({v: k for k, v in leader_of.items()})
        GRADE_SUM.append(grade_sum)
    HAS_GRADE = any(GRADE_SUM)
    HAS_MANUAL = any(MANUAL)
    # 块标题用的“颁奖领导区间”文字：有等次的奖项按奖级对位后的领导号序列显示（1→n 号），
    # 块标题用的“颁奖领导区间”文字：按行序（上台顺序）的领导号首尾 + 两端领导姓名，
    # 与批次内领导序列模式保持一致（zig-zag 批次如 3-2 号，指定对位批次如 3-2 号）
    LEADER_SPAN = []
    for i, aw in enumerate(AWARDS):
        n = len(aw['items'])
        walk = [LEADER_OF[i][k] for k in ORDER[i]]
        LEADER_SPAN.append(f'{walk[0]}-{walk[-1]} 号（{LEADERS[walk[0]][0]} → {LEADERS[walk[-1]][0]}）')

    def legend(ws, r, c1, c2, per=34):
        put(ws, r, c1, '批次图例', f(11, True), LEFT)
        ws.row_dimensions[r].height = 20
        r += 1
        for i, aw in enumerate(AWARDS):
            n = len(aw['items'])
            lft, rgt = lr_label(n, SEAT_MODE)
            put(ws, r, c1, cn_no(i), f(11, True, PALETTE[i % 6][1]), CEN, afill(i), abox(i))
            txt = (f'{cn_no(i)} {aw["name"]}（{n}位）｜颁奖领导 {LEADER_SPAN[i]}'
                   f'｜议程第 {aw.get("agenda", "—")} 项')
            put(ws, r, c1 + 1, txt, f(10), LEFT)
            ws.merge_cells(start_row=r, start_column=c1 + 1, end_row=r, end_column=c2)
            ws.row_dimensions[r].height = fit_h(txt, per)
            r += 1
        return r

    wb = Workbook()

    # ================= Sheet1 座位排布表 =================
    ws = wb.create_sheet('座位排布表', 0)
    MAIN1, MAIN2 = 6, 11
    ZONE = [(2, 4, '教务 / 会务区'), (MAIN1, MAIN2, '领奖人员区'), (13, 15, '其他参会人员区')]
    AISLE = [5, 12]
    LF, LL = 3, 15
    TX1, TX2 = 17, 21
    GAP = 16
    MAXC = TX2
    ROW0 = 11
    N_ROWS = (FIRST_SEAT_ROW - 1) + (TOTAL + SEATS_PER_ROW - 1) // SEATS_PER_ROW

    put(ws, 1, 1, '← 西', f(11, True), CEN, FILL_HDR, cellbox(HDR_BG))
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
    put(ws, 1, LF, '主 席 台（LED显示屏）', f(14, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    ws.merge_cells(start_row=1, start_column=LF, end_row=1, end_column=LL)
    put(ws, 1, TX1, '东 →', f(11, True), CEN, FILL_HDR, cellbox(HDR_BG))
    ws.merge_cells(start_row=1, start_column=TX1, end_row=1, end_column=TX2)
    ws.row_dimensions[1].height = 24

    put(ws, 2, LF, f'{meta.get("title", "")}  座 位 排 布 表', f(18, True))
    ws.merge_cells(start_row=2, start_column=LF, end_row=2, end_column=LL)
    ws.row_dimensions[2].height = 32
    sub = f'会议时间：{meta.get("date", "")}　　地点：{meta.get("venue", "")}'
    if meta.get('host'):
        sub += f'　　主持人：{meta.get("host")}'
    put(ws, 3, LF, sub, f(10, '595959'))
    ws.merge_cells(start_row=3, start_column=LF, end_row=3, end_column=LL)
    ws.row_dimensions[3].height = 20

    # 台上单位：按连续相同 org 自动分段
    LEAD_NO_ROW, LEAD_NAME_ROW, LEAD_DUTY_ROW = 5, 6, 7
    LEAD_COL = {s: LF + i for i, s in enumerate(LEFT_TO_RIGHT)}
    GOLD_CF = PatternFill(start_color='FFFFD966', end_color='FFFFD966', fill_type='solid')
    segs, cur = [], None
    for s in LEFT_TO_RIGHT:
        org = LEADERS[s][2] or ''
        if cur and cur[2] == org:
            cur[1] = LEAD_COL[s]
        else:
            cur = [LEAD_COL[s], LEAD_COL[s], org]
            segs.append(cur)
    for c1, c2, org in segs:
        put(ws, 4, c1, org or '—', f(10, '595959'), CEN, FILL_GREY, cellbox(GREY_BD))
        ws.merge_cells(start_row=4, start_column=c1, end_row=4, end_column=c2)
    ws.row_dimensions[4].height = 18

    for i, s in enumerate(LEFT_TO_RIGHT):
        col = LF + i
        put(ws, LEAD_NO_ROW, col, s, f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
        put(ws, LEAD_NAME_ROW, col, LEADERS[s][0], f(15, True), CEN, FILL_LEAD, cellbox(LEAD_BD))
        put(ws, LEAD_DUTY_ROW, col, DUTY[s], f(10, '404040'), CEN, FILL_LEAD, cellbox(LEAD_BD))
    ws.row_dimensions[5].height = 20
    ws.row_dimensions[6].height = 30
    ws.row_dimensions[7].height = 42
    ws.conditional_formatting.add(
        f"{get_column_letter(LF)}{LEAD_NO_ROW}:{get_column_letter(LL)}{LEAD_NO_ROW}",
        CellIsRule(operator='equal', formula=['1'], fill=GOLD_CF, font=Font(color=GOLD_TXT, bold=True)))
    ws.conditional_formatting.add(
        f"{get_column_letter(LF)}{LEAD_NAME_ROW}:{get_column_letter(LL)}{LEAD_DUTY_ROW}",
        FormulaRule(formula=[f'{get_column_letter(LF)}${LEAD_NO_ROW}=1'], fill=GOLD_CF))

    for c1, c2, label in ZONE:
        put(ws, 8, c1, label, f(12, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
        ws.merge_cells(start_row=8, start_column=c1, end_row=8, end_column=c2)
    for x in AISLE:
        put(ws, 8, x, '走\n廊', f(10, GREY_TX), CEN, FILL_GREY, cellbox(GREY_BD))
        ws.merge_cells(start_row=8, start_column=x, end_row=ROW0 + N_ROWS * 2, end_column=x)
    ws.row_dimensions[8].height = 22

    num = 1
    for c1, c2, _ in ZONE:
        for col in range(c1, c2 + 1):
            put(ws, 9, col, num, f(9, GREY_TX), CEN,
                PatternFill('solid', fgColor='FAFAFA'), greybox())
            num += 1
    ws.row_dimensions[9].height = 16

    put(ws, 10, MAIN1, '↑ 领奖人按批次由左至右起身上台，上台动线沿左侧通道', f(11, 'C00000'), CEN)
    ws.merge_cells(start_row=10, start_column=MAIN1, end_row=10, end_column=MAIN2)
    put(ws, 10, TX1, '领 奖 批 次 与 上 台 顺 序', f(12, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    ws.merge_cells(start_row=10, start_column=TX1, end_row=10, end_column=TX2)
    ws.row_dimensions[10].height = 22

    flat, SEAT_ADDR = [], {}
    for i, aw in enumerate(AWARDS):
        for it in aw['items']:
            flat.append((i, it.get('unit', ''), it.get('name', '待定')))
    seat_map, rn, sn = [], FIRST_SEAT_ROW, 1
    _skip = set(lay.get('skip_seats', []) or [])
    for _ in flat:
        while f'第{rn}排{sn}号' in _skip:
            sn, rn = (1, rn + 1) if sn >= SEATS_PER_ROW else (sn + 1, rn)
        seat_map.append(f'第{rn}排{sn}号')
        sn, rn = (1, rn + 1) if sn >= SEATS_PER_ROW else (sn + 1, rn)
    _seat2flat = {s: i for i, s in enumerate(seat_map)}

    for k in range(N_ROWS):
        r = ROW0 + k * 2
        row_no = k + 1
        put(ws, r, 1, f'第{row_no}排', f(12, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
        ws.merge_cells(start_row=r, start_column=1, end_row=r + 1, end_column=1)
        paint(ws, r + 1, 1, r + 1, 1, border=cellbox(HDR_BG))
        if row_no < FIRST_SEAT_ROW:
            put(ws, r, MAIN1, f'留 空（礼堂惯例：第1—{FIRST_SEAT_ROW - 1}排不排座）',
                f(12, True, GREY_TX), CEN, FILL_GREY, greybox())
            ws.merge_cells(start_row=r, start_column=MAIN1, end_row=r + 1, end_column=MAIN2)
            paint(ws, r, MAIN1, r + 1, MAIN2, border=greybox())
        else:
            for j in range(SEATS_PER_ROW):
                seat_no = f'第{row_no}排{j + 1}号'
                col = MAIN1 + j
                if seat_no in _skip or seat_no not in _seat2flat:
                    paint(ws, r, col, r + 1, col, fill=FILL_GREY, border=greybox())
                    continue
                ci, unit, person = flat[_seat2flat[seat_no]]
                put(ws, r, col, person, f(15, True), CEN, afill(ci), abox(ci))
                put(ws, r + 1, col, unit, f(10, PALETTE[ci % 6][1]), CEN, afill(ci), abox(ci))
                SEAT_ADDR[_seat2flat[seat_no]] = {'name': f"{get_column_letter(col)}{r}",
                                                  'unit': f"{get_column_letter(col)}{r + 1}"}
        for c1, c2, _ in ZONE:
            if c1 == MAIN1:
                continue
            for col in range(c1, c2 + 1):
                paint(ws, r, col, r + 1, col, fill=FILL_GREY, border=greybox())
        ws.row_dimensions[r].height = 30
        ws.row_dimensions[r + 1].height = 34

    for i, aw in enumerate(AWARDS):
        n = len(aw['items'])
        lft, rgt = lr_label(n, SEAT_MODE)
        r = ROW0 + (FIRST_SEAT_ROW - 1) * 2 + i * 2
        start_idx = sum(len(x['items']) for x in AWARDS[:i])
        seats = seat_map[start_idx:start_idx + n]
        head = (f'{cn_no(i)} {aw["name"]}（{n}位）｜对应 {LEADER_SPAN[i]}'
                + (f'｜{GRADE_SUM[i]}' if GRADE_SUM[i] else ''))
        body = ('上台顺序：' + ' → '.join(
            f'{aw["items"][k].get("unit","")}{aw["items"][k].get("name","")}'
            + (f'（{aw["items"][k]["grade"]}）' if aw["items"][k].get('grade') else '')
            for k in ORDER[i]))
        tail = (f'座位：{seats[0]} — {seats[-1]}（{len(seats)}座）｜奖励：{aw.get("reward","—")}｜奖品形式待定')
        body_f = ('="上台顺序："&'
                  + '&" → "&'.join(f"{SEAT_ADDR[start_idx + k]['name']}&{SEAT_ADDR[start_idx + k]['unit']}"
                                   for k in ORDER[i])
                  + f'&CHAR(10)&"{tail}"')
        put(ws, r, TX1, head, f(12, True, PALETTE[i % 6][1]), LEFT, afill(i), abox(i))
        ws.merge_cells(start_row=r, start_column=TX1, end_row=r, end_column=TX2)
        put(ws, r + 1, TX1, body_f, f(10, '404040'), LEFT, afill(i), abox(i))
        ws.merge_cells(start_row=r + 1, start_column=TX1, end_row=r + 1, end_column=TX2)
        ws.row_dimensions[r].height = 24
        ws.row_dimensions[r + 1].height = max(44, fit_h(body + tail, 36))

    ws.conditional_formatting.add(
        f"{get_column_letter(MAIN1)}{ROW0 + (FIRST_SEAT_ROW - 1) * 2}:"
        f"{get_column_letter(MAIN2)}{ROW0 + N_ROWS * 2 - 1}",
        CellIsRule(operator='equal', formula=['"待定"'], font=Font(color='C00000', bold=True)))

    rb = ROW0 + N_ROWS * 2 + 1
    rb = legend(ws, rb, 1, 15, per=72)
    body = [
        f'主席台1号位居中，{_sides}；n位领奖人由1至n号领导颁奖，'
        '领奖人自左至右与领导座次对位。',
        f'按礼堂惯例第1—{FIRST_SEAT_ROW - 1}排留空；{CAT + "类" if CAT else ""}共{TOTAL}个领奖单元'
        f'自第{FIRST_SEAT_ROW}排起每排{SEATS_PER_ROW}座依次排布，'
        f'共占{math.ceil(TOTAL / SEATS_PER_ROW)}排（第{FIRST_SEAT_ROW}—{LAST_ROW}排）。',
    ]
    if EXCL_SEQ:
        ss = sorted(EXCL_SEQ)
        rng = (f'第{ss[0]}—{ss[-1]}项' if ss[-1] - ss[0] == len(ss) - 1
               else '、'.join(f'第{x}项' for x in ss))
        body.append(f'教学类{len(ss)}个颁奖环节（议程{rng}）未纳入本表，如需同场就座建议'
                    f'安排在第{LAST_ROW + 1}排及以后，或由教务另行指定区域。')
    body.append('标红“待定”为表彰明细未列明领奖代表的科室，'
                '请相关科室于会前补报（改掉“待定”后自动恢复黑字）。')
    if HAS_GRADE:
        body.append('有等次的奖项按“奖级高者对位领导职务高者”对位：一等奖→1号、二等奖→2、3号、'
                    '三等奖→4、5、6号……同级按明细顺序；领导排位不变，领奖人上台后各立于所对位领导面前。')
    if HAS_MANUAL:
        body.append('领导指定顺序的批次（如江西省科技奖）按其名单顺序直接对位 1、2、3 号领导，'
                    '座位区首位对应 1 号领导，领导排位不变。')
    body.append('本表为唯一数据源：修改领奖人姓名/科室，或调整主席台座次号、领导姓名、职务后，'
                '「领导排位图(发放顺序)」「领奖顺序图」「桌牌打印单」及右侧批次说明全部自动同步；'
                '请勿在领奖区或主席台插入/删除行、列，直接替换单元格内容即可。')
    body += [re.sub(r'^\d+[.、]\s*', '', str(x)) for x in D.get('extra_notes', [])]
    notes = ['说明：1. ' + body[0]] + [f'{i}. {t}' for i, t in enumerate(body[1:], start=2)]
    for t in notes:
        put(ws, rb, 1, t, f(10, '595959'), LEFT)
        ws.merge_cells(start_row=rb, start_column=1, end_row=rb, end_column=TX2)
        ws.row_dimensions[rb].height = fit_h(t, 110)
        rb += 1

    ws.column_dimensions['A'].width = 6.5
    for col in range(2, 16):
        ws.column_dimensions[get_column_letter(col)].width = 10 if col in AISLE else 11
    ws.column_dimensions[get_column_letter(GAP)].width = 2
    for col in range(TX1, TX2 + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14
    setup_page(ws, paper=9, fit_w=1, fit_h=0)
    ws.print_area = f'A1:{get_column_letter(MAXC)}{rb - 1}'

    # ================= Sheet2 领导排位图 =================
    w2 = wb.create_sheet('领导排位图(发放顺序)', 1)
    FC = 6
    LC = FC + N - 1
    COL_OF = {s: FC + i for i, s in enumerate(LEFT_TO_RIGHT)}
    put(w2, 1, 1, f'{meta.get("title", "")}  颁 奖 领 导 排 位 图', f(18, True))
    w2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=LC)
    w2.row_dimensions[1].height = 34
    _ann = meta.get('announcer', '')
    _m = re.match(r'^(.+?)（', _ann)
    _sm = re.search(r'宣读(.+?)表彰决定', _ann)
    _ann_txt = (f'｜宣读{_sm.group(1)}表彰决定：{_m.group(1).strip()}'
                if (_m and _sm) else '')
    sub2 = f'会议时间：{meta.get("date", "")}｜{meta.get("venue", "")}'
    if meta.get('host'):
        sub2 += f'｜主持人：{short(meta.get("host"))}'
    sub2 += _ann_txt
    sub2 += f'｜发放顺序：按议程第{AG_MIN}—{AG_MAX}项'
    put(w2, 2, 1, sub2, f(10, '595959'))
    w2.merge_cells(start_row=2, start_column=1, end_row=2, end_column=LC)
    w2.row_dimensions[2].height = 20
    put(w2, 4, 1, '台上方位', f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    w2.row_dimensions[4].height = 20
    put(w2, 4, 3, '← 西', f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    put(w2, 4, LC + 1, '东 →', f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))

    for label, ri, src_row, fnt in [('座次序号', 5, LEAD_NO_ROW, lambda: f(12, True, 'C00000')),
                                    ('颁奖领导', 6, LEAD_NAME_ROW, lambda: f(14, True)),
                                    ('职务', 7, LEAD_DUTY_ROW, lambda: f(10, '404040'))]:
        put(w2, ri, 3, label, f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
        for s in LEFT_TO_RIGHT:
            put(w2, ri, COL_OF[s], f"='座位排布表'!{get_column_letter(LEAD_COL[s])}{src_row}",
                fnt(), CEN, FILL_LEAD, cellbox(LEAD_BD))
        w2.row_dimensions[ri].height = 20 if ri == 5 else (30 if ri == 6 else 44)
    w2.conditional_formatting.add(f"{get_column_letter(FC)}5:{get_column_letter(LC)}5",
        CellIsRule(operator='equal', formula=['1'], fill=GOLD_CF, font=Font(color=GOLD_TXT, bold=True)))
    w2.conditional_formatting.add(f"{get_column_letter(FC)}6:{get_column_letter(LC)}7",
        FormulaRule(formula=[f'{get_column_letter(FC)}$5=1'], fill=GOLD_CF))

    r = 8
    put(w2, r, 3, '礼仪', f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    i = 0
    while i < len(LEFT_TO_RIGHT):
        s = LEFT_TO_RIGHT[i]
        j = i
        while j + 1 < len(LEFT_TO_RIGHT) and USHER[LEFT_TO_RIGHT[j + 1]] == USHER[s]:
            j += 1
        c1, c2 = COL_OF[s], COL_OF[LEFT_TO_RIGHT[j]]
        put(w2, r, c1, USHER[s], f(11), CEN, FILL_GREY, cellbox(GREY_BD))
        if c2 > c1:
            w2.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
        paint(w2, r, c1, r, c2, border=cellbox(GREY_BD))
        i = j + 1
    w2.row_dimensions[r].height = 22

    r += 2
    for i, aw in enumerate(AWARDS):
        n = len(aw['items'])
        seq = seat_order(n, SEAT_MODE)
        lft, rgt = lr_label(n, SEAT_MODE)
        start_idx = sum(len(x['items']) for x in AWARDS[:i])
        item_of_leader = ITEM_OF_LEADER[i]
        top = r
        put(w2, r, 1, f'{cn_no(i)}\n{aw["name"]}\n（{n}位）\n对应 {LEADER_SPAN[i]}\n'
                      f'议程第 {aw.get("agenda", "—")} 项\n{aw.get("reward", "")}'
                      + (f'\n等次：{GRADE_SUM[i]}' if GRADE_SUM[i] else ''),
            f(12, True, PALETTE[i % 6][1]), CEN, afill(i), abox(i, 'medium'))
        w2.merge_cells(start_row=r, start_column=1, end_row=r + 4, end_column=2)
        paint(w2, r, 1, r + 4, 2, border=abox(i, 'medium'))
        rows = [
            ('座次号', lambda k: f"='座位排布表'!{get_column_letter(LEAD_COL[seq[k]])}{LEAD_NO_ROW}",
             lambda: f(12, True, PALETTE[i % 6][1])),
            ('颁奖领导', lambda k: f"='座位排布表'!{get_column_letter(LEAD_COL[seq[k]])}{LEAD_NAME_ROW}",
             lambda: f(13, True)),
            ('领奖代表', lambda k: f"='座位排布表'!{SEAT_ADDR[start_idx + item_of_leader[seq[k]]]['name']}",
             lambda: f(12, True)),
            ('领奖科室 / 团队', lambda k: f"='座位排布表'!{SEAT_ADDR[start_idx + item_of_leader[seq[k]]]['unit']}",
             lambda: f(10, '404040')),
            ('礼仪', lambda k: USHER[seq[k]], lambda: f(10, '595959')),
        ]
        for j, (label, fn, fnt) in enumerate(rows):
            rr = r + j
            put(w2, rr, 3, label, f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
            for k in range(n):
                put(w2, rr, COL_OF[seq[k]], fn(k), fnt(), CEN, afill(i), abox(i))
            w2.row_dimensions[rr].height = 26 if j != 3 else 36
        w2.conditional_formatting.add(
            f"{get_column_letter(COL_OF[seq[0]])}{r + 2}:{get_column_letter(COL_OF[seq[-1]])}{r + 3}",
            CellIsRule(operator='equal', formula=['"待定"'], font=Font(color='C00000', bold=True)))
        r = top + 6

    rb = r + 1
    rb = legend(w2, rb, 1, 5, per=26)
    if HAS_GRADE:
        _pair_txt = ('有等次的奖项按“奖级高者对位领导职务高者”（一等奖→1号，同级按明细顺序），'
                     '无等次的按台上位置依次对位')
    else:
        _pair_txt = '领奖人自左至右依次对位'
    if HAS_MANUAL:
        _pair_txt += '（领导指定顺序的批次按其名单顺序直接对位）'
    rule = (f'规则：n位领奖人由1至n号领导颁奖，{_pair_txt}，{_ends}；'
            f'礼仪{USHER_DESC}（详见「礼仪分工表」）。'
            '主席台座次号、领导姓名、职务及块内颁奖领导均引自「座位排布表」，席位调整后本表自动更新。')
    put(w2, rb, 1, rule, f(10, '595959'), LEFT)
    w2.merge_cells(start_row=rb, start_column=1, end_row=rb, end_column=LC)
    w2.row_dimensions[rb].height = fit_h(rule, 105)

    w2.column_dimensions['A'].width = 12
    w2.column_dimensions['B'].width = 13
    w2.column_dimensions['C'].width = 14
    for col in range(FC, LC + 2):
        w2.column_dimensions[get_column_letter(col)].width = 13
    setup_page(w2, paper=9, fit_w=1, fit_h=0)
    w2.freeze_panes = 'D5'

    # ================= Sheet3 领奖顺序图 =================
    w3 = wb.create_sheet('领奖顺序图', 2)
    HEAD = ['批次', '上台\n顺序', '奖项名称', '领奖科室 / 团队', '领奖代表',
            '颁奖领导\n(座次号)', '颁奖领导', '礼仪', '奖励标准', '台下座位', '议程']
    WIDTH = [6, 7, 26, 19, 11, 11, 11, 8, 13, 12, 7]
    _scope = f'（{meta["scope"]}）' if meta.get('scope') else ''
    put(w3, 1, 1, f'{meta.get("title", "")}  领 奖 顺 序 图{_scope}', f(18, True))
    w3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(HEAD))
    w3.row_dimensions[1].height = 34
    s3 = f'会议时间：{meta.get("date", "")}｜{meta.get("venue", "")}｜上台顺序自左至右与颁奖领导座次一一对应'
    s3 += f'｜礼堂第1—{FIRST_SEAT_ROW - 1}排留空，领奖人自第{FIRST_SEAT_ROW}排起每排{SEATS_PER_ROW}座依次排布'
    put(w3, 2, 1, s3, f(10, '595959'))
    w3.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(HEAD))
    w3.row_dimensions[2].height = 20
    for j, h in enumerate(HEAD, start=1):
        put(w3, 3, j, h, f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    w3.row_dimensions[3].height = 32

    r = 4
    for i, aw in enumerate(AWARDS):
        n = len(aw['items'])
        start_idx = sum(len(x['items']) for x in AWARDS[:i])
        seq = seat_order(n, SEAT_MODE)
        lft, rgt = lr_label(n, SEAT_MODE)
        top = r
        for r_i, k in enumerate(ORDER[i]):
            it = aw['items'][k]
            s = LEADER_OF[i][k]
            g = it.get('grade')
            vals = [cn_no(i), (f'{r_i + 1}\n{g}' if g else r_i + 1), None,
                    f"='座位排布表'!{SEAT_ADDR[start_idx + k]['unit']}",
                    f"='座位排布表'!{SEAT_ADDR[start_idx + k]['name']}",
                    f"='座位排布表'!{get_column_letter(LEAD_COL[s])}{LEAD_NO_ROW}&\" 号\"",
                    f"='座位排布表'!{get_column_letter(LEAD_COL[s])}{LEAD_NAME_ROW}",
                    USHER[s], aw.get('reward', '—'), seat_map[start_idx + k], f'第{aw.get("agenda", "—")}项']
            for j, v in enumerate(vals, start=1):
                if v is None:
                    continue
                put(w3, r, j, v, f(12, True) if j == 2 else f(11),
                    LEFT if j in (3, 4) else CEN, afill(i), abox(i))
            w3.row_dimensions[r].height = 36 if g else 26
            r += 1
        put(w3, top, 1, cn_no(i), f(14, True, PALETTE[i % 6][1]), CEN, afill(i), abox(i, 'medium'))
        w3.merge_cells(start_row=top, start_column=1, end_row=r - 1, end_column=1)
        put(w3, top, 3, f'{cn_no(i)} {aw["name"]}（{n}位）｜对应 {LEADER_SPAN[i]}',
            f(12, True, PALETTE[i % 6][1]), CEN, afill(i), abox(i, 'medium'))
        w3.merge_cells(start_row=top, start_column=3, end_row=r - 1, end_column=3)
        put(w3, top, 9, aw.get('reward', '—'), f(11, True, PALETTE[i % 6][1]), CEN, afill(i), abox(i))
        w3.merge_cells(start_row=top, start_column=9, end_row=r - 1, end_column=9)
        paint(w3, top, 1, r - 1, 1, border=abox(i, 'medium'))
        paint(w3, top, 3, r - 1, 3, border=abox(i, 'medium'))

    w3.conditional_formatting.add(f'D4:E{r - 1}',
        CellIsRule(operator='equal', formula=['"待定"'], font=Font(color='C00000', bold=True)))
    rb = r + 1
    rb = legend(w3, rb, 1, 4, per=26)
    _no_amt = [x['name'] for x in AWARDS if x.get('reward') in (None, '', '按表彰决定')]
    _b3 = [
        f'本表含{DEPT}负责发放的{len(AWARDS)}个奖项（议程第{AG_MIN}—{AG_MAX}项），'
        f'共{TOTAL}个领奖单元；'
        + (f'教学类{len(EXCL_SEQ)}个颁奖环节未纳入。' if EXCL_SEQ else '')
        + f'礼堂第1—{FIRST_SEAT_ROW - 1}排按惯例留空，'
          f'领奖人自第{FIRST_SEAT_ROW}排起排座。',
        '本表 D、E 两列（领奖科室/团队、领奖代表）为公式，引用「座位排布表」对应座位；'
        '修改座位表中的人名或科室，本表与「领导排位图(发放顺序)」自动同步。',
        ('、'.join(_no_amt) + '的奖励标准在明细中未列明金额，按表彰决定执行。')
        if _no_amt else '奖励标准以表彰明细为准；明细未列明金额的按表彰决定执行。',
        '座次号、颁奖领导均引自「座位排布表」主席台（行5座次号、行6姓名），席位调整后本表自动更新；'
        f'礼仪{USHER_DESC}（详见「礼仪分工表」），'
        '领导或礼仪人数变化时需重跑生成脚本。',
    ]
    if HAS_GRADE:
        _b3.append('有等次的奖项已按“奖级高者对位领导职务高者”排定领奖顺序'
                   '（一等奖→1号领导、二等奖→2、3号……同级按明细顺序），领导排位不变；'
                   '“上台顺序”栏同步标注奖级。')
    if HAS_MANUAL:
        for _i, _aw in enumerate(AWARDS):
            if MANUAL[_i]:
                _pairs = '、'.join(f'{_aw["items"][k].get("name", "")}→{LEADER_OF[_i][k]}号'
                                   for k in ORDER[_i])
                _b3.append(f'{_aw["name"]}批次按领导指定顺序上台（{_pairs}），'
                           '领导排位不变，领奖人上台后各立于所对位领导面前。')
    for i, t in enumerate(_b3):
        put(w3, rb, 1, f'说明：{i + 1}. {t}' if i == 0 else f'{i + 1}. {t}',
            f(10, '595959'), LEFT)
        w3.merge_cells(start_row=rb, start_column=1, end_row=rb, end_column=len(HEAD))
        w3.row_dimensions[rb].height = fit_h(t, 62)
        rb += 1
    for j, w in enumerate(WIDTH, start=1):
        w3.column_dimensions[get_column_letter(j)].width = w
    setup_page(w3, paper=9, fit_w=1, fit_h=0)
    w3.freeze_panes = 'A4'
    w3.auto_filter.ref = f'A3:{get_column_letter(len(HEAD))}{r - 1}'

    # ========= Sheet4 桌牌打印单 / Sheet5 桌牌打印单(领导)：并入主表，公式联动 =========
    def pad_f(ref):
        """两字名中间补两个半角空格的公式（与独立打印单一致）"""
        return (f'IF({ref}="待定",{ref},'
                f'IF(LEN({ref})=2,LEFT({ref},1)&"  "&RIGHT({ref},1),{ref}))')

    w4 = wb.create_sheet('桌牌打印单', 3)
    for j, h in enumerate(['名单（科室）', '姓名', '座位', '领导（主席台）'], start=1):
        put(w4, 1, j, h, f(12, True), CEN, FILL_HDR, cellbox(HDR_BG))
    w4.row_dimensions[1].height = 22
    for idx in range(TOTAL):
        r = 2 + idx
        na, un = SEAT_ADDR[idx]['name'], SEAT_ADDR[idx]['unit']
        put(w4, r, 1, f"='座位排布表'!{un}", f(12), LEFT, border=cellbox(GREY_BD))
        put(w4, r, 2, '=' + pad_f(f"'座位排布表'!{na}"), f(12), CEN, border=cellbox(GREY_BD))
        put(w4, r, 3, seat_map[idx], f(12), CEN, border=cellbox(GREY_BD))
        w4.row_dimensions[r].height = 20
    for i, s in enumerate(LEFT_TO_RIGHT):
        lc = get_column_letter(LEAD_COL[s])
        put(w4, 2 + i, 4, f"='座位排布表'!{lc}{LEAD_NO_ROW}&\". \"&"
                          + pad_f(f"'座位排布表'!{lc}{LEAD_NAME_ROW}"),
            f(12), LEFT, border=cellbox(GREY_BD))
    w4.conditional_formatting.add(
        f'B2:B{TOTAL + 1}',
        CellIsRule(operator='equal', formula=['"待定"'], font=Font(color='C00000', bold=True)))
    rn = TOTAL + 3
    tip = ('说明：本表全部为公式，引用「座位排布表」（领奖区 + 主席台），改座位表即自动同步，无需另行维护。'
           '打印桌牌：Word 打开打印模版 → 邮件合并，领奖人数据源选本表 A:C 列，'
           '领导桌牌数据源选「桌牌打印单(领导)」工作表。')
    put(w4, rn, 1, tip, f(10, '595959'), LEFT)
    w4.merge_cells(start_row=rn, start_column=1, end_row=rn, end_column=4)
    w4.row_dimensions[rn].height = fit_h(tip, 42)
    for c, wd in zip('ABCD', (20.75, 13, 12, 15)):
        w4.column_dimensions[c].width = wd
    w4.freeze_panes = 'A2'
    w4.sheet_view.showGridLines = False

    w5 = wb.create_sheet('桌牌打印单(领导)', 4)
    put(w5, 1, 1, '姓名', f(12, True), CEN, FILL_HDR, cellbox(HDR_BG))
    w5.row_dimensions[1].height = 22
    for i, s in enumerate(LEFT_TO_RIGHT):
        lc = get_column_letter(LEAD_COL[s])
        put(w5, 2 + i, 1, '=' + pad_f(f"'座位排布表'!{lc}{LEAD_NAME_ROW}"),
            f(12), CEN, border=cellbox(GREY_BD))
        w5.row_dimensions[2 + i].height = 20
    w5.column_dimensions['A'].width = 15
    w5.sheet_view.showGridLines = False

    # ========= Sheet6 礼仪分工表 =========
    w6 = wb.create_sheet('礼仪分工表', 5)
    put(w6, 1, 1, f'{meta.get("title", "")}  礼 仪 分 工 表', f(16, True))
    w6.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)
    w6.row_dimensions[1].height = 30
    sub6 = (f'会议时间：{meta.get("date", "")}｜{meta.get("venue", "")}｜'
            f'礼仪{USHER_DESC}')
    put(w6, 2, 1, sub6, f(10, '595959'), LEFT)
    w6.merge_cells(start_row=2, start_column=1, end_row=2, end_column=4)
    w6.row_dimensions[2].height = 20
    for j, h in enumerate(['礼仪', '对应领导（座次号，自左至右）', '人数', '负责颁奖批次'], start=1):
        put(w6, 3, j, h, f(11, True, HDR_TX), CEN, FILL_HDR, cellbox(HDR_BG))
    w6.row_dimensions[3].height = 24

    usher_leaders = {}
    for s in LEFT_TO_RIGHT:
        usher_leaders.setdefault(USHER[s], []).append(s)
    for k in range(1, U + 1):
        r = 3 + k
        ls = usher_leaders.get(f'礼仪{k}', [])
        ref = '&"、"&'.join(
            f"'座位排布表'!{get_column_letter(LEAD_COL[s])}{LEAD_NAME_ROW}"
            f"&\"（\"&'座位排布表'!{get_column_letter(LEAD_COL[s])}{LEAD_NO_ROW}&\"号）\""
            for s in ls)
        batches = []
        for bi, aw in enumerate(AWARDS):
            n = len(aw['items'])
            if any(s <= n for s in ls):
                batches.append(f'{cn_no(bi)}{aw["name"]}（议程第{aw.get("agenda", "—")}项）')
        btxt = '、'.join(batches) or '—'
        put(w6, r, 1, f'礼仪{k}', f(12, True), CEN, FILL_LEAD, cellbox(LEAD_BD))
        put(w6, r, 2, '=' + ref if ref else '—', f(12), LEFT, border=cellbox(GREY_BD))
        put(w6, r, 3, len(ls), f(12), CEN, border=cellbox(GREY_BD))
        put(w6, r, 4, btxt, f(10, '404040'), LEFT, border=cellbox(GREY_BD))
        w6.row_dimensions[r].height = max(26, fit_h(btxt, 32))
    rn6 = 3 + U + 2
    for t in [
        f'说明：1. 礼仪按台上自左至右顺序编号，{USHER_DESC}'
        '（分组可在 data.json layout.usher_groups 中指定，或用 layout.ushers 人数自动分配，改后重跑）。',
        '2. 「对应领导」为公式，引用「座位排布表」主席台（行5座次号、行6姓名），'
        '主席台席位调整后本表自动同步。',
        '3. 「负责颁奖批次」按“座次号≤该批次领奖人数的领导参与该批次颁奖”统计；'
        '礼仪在对应批次负责引导其对应领导上台颁奖及奖品交接。',
    ]:
        put(w6, rn6, 1, t, f(10, '595959'), LEFT)
        w6.merge_cells(start_row=rn6, start_column=1, end_row=rn6, end_column=4)
        w6.row_dimensions[rn6].height = fit_h(t, 60)
        rn6 += 1
    for c, wd in zip('ABCD', (10, 36, 8, 48)):
        w6.column_dimensions[c].width = wd
    setup_page(w6, paper=9, fit_w=1, fit_h=0)

    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])
    out = a.out
    tmp = out.replace('.xlsx', '.tmp.xlsx')
    wb.save(tmp)
    try:
        os.replace(tmp, out)
    except PermissionError:
        alt = out.replace('.xlsx', '_新.xlsx')
        os.replace(tmp, alt)
        out = alt
        print('[提示] 原文件被占用，已另存为', alt)
    print('saved:', out)
    print('sheets:', wb.sheetnames)


if __name__ == '__main__':
    main()
