#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
入参解析：议程 docx + 表彰明细 docx -> data.json（草稿，需人工核对）

用法：
  python parse_inputs.py --agenda 议程.docx --detail 明细.docx --out data.json
可选：
  --first-seat-row 4     领奖人起始排（礼堂前几排留空）
  --seats-per-row 6      每排座位数
  --leader-rule school_first|doc   主席台座次排序规则（默认校院交替）
  --force                覆盖已存在的 data.json
"""
import argparse
import json
import os
import re

import docx

# 议程环节名尾部需剥离的赘语（长后缀优先，避免误伤“先进科技团队”本身）
STRIP_TAIL = ['获奖科室', '获奖人员', '获奖代表', '获奖团队', '获奖人', '获奖',
              '代表', '科室', '人员', '教师', '人']
# 明细奖项标题前缀（用于生成无括号名单的“科室/团队”列）
UNIT_PREFIX = r'^(优秀|最佳|先进)'


def paras(path):
    d = docx.Document(path)
    return [p.text.strip() for p in d.paragraphs if p.text.strip()]


def parse_meta(ps):
    meta = {}
    for t in ps:
        for key, field in [('会议时间', 'date'), ('会议地点', 'venue'),
                           ('会议主持', 'host')]:
            if t.startswith(key):
                meta[field] = t.split('：', 1)[-1].strip()
        if '宣读科技表彰决定' in t or '宣读表彰决定' in t:
            meta['announcer'] = t
    if ps:
        meta['title'] = re.sub(r'议程$', '', ps[0]).strip()
    return meta


def parse_leaders(ps):
    """从“与会领导”段解析姓名+职务+单位，返回文档原始顺序"""
    out, org, started = [], '', False
    for t in ps:
        if t.startswith('与会领导'):
            started = True
            continue
        if not started:
            continue
        if re.match(r'^(参会人员|会议主持|会议总时长|主持人宣布|会议议程)', t):
            break
        if t.endswith('：') and '（' not in t:
            org = t[:-1]
            continue
        for m in re.finditer(r'([^\s，,、；;]+?)（([^）]+)）', t):
            nm = m.group(1).strip()
            if not nm or nm in ('等',):
                continue
            out.append({'name': nm, 'duty': m.group(2).strip(), 'org': org})
    return out


def order_leaders(leaders, rule='school_first'):
    """
    编排主席台座次号（1号居中）。
    school_first（默认，院内惯例）：
        1号=上级单位首位（如校领导），2号=本院党委/行政主要负责人，
        3号=上级单位第2位，其余按文档顺序顺延（本院在前、上级单位在后）。
    doc：完全按文档出现顺序编号。
    """
    if rule == 'doc' or not leaders:
        for i, x in enumerate(leaders):
            x['no'] = i + 1
        return leaders
    groups, order = {}, []
    for x in leaders:
        k = x.get('org', '') or '—'
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(x)
    g0 = groups[order[0]]                       # 上级/外单位
    g1 = groups[order[1]] if len(order) > 1 else []
    seq = []
    if g0:
        seq.append(g0[0])
    if g1:
        seq.append(g1[0])
    if len(g0) > 1:
        seq.append(g0[1])
    rest = g1[1:] + g0[2:]
    for k in order[2:]:
        rest += groups[k]
    seq += rest
    for i, x in enumerate(seq):
        x['no'] = i + 1
    return seq


def parse_agenda_items(ps):
    """抽取颁奖环节（保留议程全局序号）"""
    items, started, idx = [], False, 0
    for t in ps:
        if t.startswith('颁奖仪式'):
            started = True
            continue
        if not started:
            continue
        if '上台领奖' in t:
            idx += 1
            name = re.sub(r'上台领奖.*$', '', t)
            while True:
                for suf in STRIP_TAIL:
                    if name.endswith(suf) and len(name) > len(suf):
                        name = name[:-len(suf)]
                        break
                else:
                    break
            items.append({'seq': idx, 'name': name.strip('“”" ')})
        elif idx:
            break
    return items


def is_heading(t):
    """明细中的奖项标题：形如“1、最佳质量奖”，或无编号的独立短标题。
    必须短且不含分隔符，避免把“2、江西省科学技术进步奖二等奖-周为民团队-题目”误判为标题。"""
    core = re.sub(r'^\d{1,2}、\s*', '', t).strip()
    if len(core) > 20:
        return False
    if '：' in core or '万元' in core or '（' in core or '、' in core:
        return False
    if core.endswith('。'):
        return False
    return re.search(r'(奖|团队|博士后)$', core) is not None


def shorten_level(s):
    s = s.replace('江西省', '省').replace('科学技术进步', '科技进步')
    return s.strip()


def parse_detail(ps):
    """表彰明细：奖项 + 获奖名单 + 奖励标准"""
    awards, cur = [], None
    for t in ps:
        t2 = re.sub(r'^\d{1,2}、', '', t).strip()
        if is_heading(t) and not re.match(r'^\d{4}年度', t):
            cur = {'name': t2, 'items': [], 'reward': ''}
            awards.append(cur)
            continue
        # 获奖科室：超声科（章春泉）、内分泌代谢科；
        # 行内等次自动识别（两种写法）：
        #   分组式：“一等奖：心内科（张三）、呼吸科（李四）；二等奖：骨科（王五）”
        #   标注式：“心内科（张三，一等奖）”
        if re.match(r'^(获奖科室|奖励人员|获奖人员|获奖人)', t):
            body = re.split(r'：|:', t, maxsplit=1)[-1]
            if cur is None:
                cur = {'name': '未命名奖项', 'items': [], 'reward': ''}
                awards.append(cur)
            default_unit = re.sub(UNIT_PREFIX, '', cur['name']) or cur['name']
            grade = None
            for chunk in re.split(r'[；;]', body):
                mg = re.match(r'^\s*((?:特等|一等|二等|三等)奖|优秀奖)\s*[：:]\s*(.*)$', chunk)
                if mg:
                    grade, seg_body = mg.group(1), mg.group(2)
                else:
                    seg_body = chunk
                for seg in re.split('、', seg_body):
                    seg = seg.strip('。； ')
                    if not seg:
                        continue
                    mm = re.match(r'^(.+?)（(.+?)）$', seg)
                    if mm:
                        nm, g2 = mm.group(2).strip(), None
                        m3 = re.match(r'^(.+?)[，,]\s*((?:特等|一等|二等|三等)奖|优秀奖)$', nm)
                        if m3:
                            nm, g2 = m3.group(1).strip(), m3.group(2)
                        item = {'unit': mm.group(1).strip(), 'name': nm}
                        item['grade'] = g2 or grade
                        cur['items'].append(item)
                    elif t.startswith('获奖科室'):
                        cur['items'].append({'unit': seg, 'name': '待定',
                                             'grade': grade})
                    else:
                        cur['items'].append({'unit': default_unit, 'name': seg,
                                             'grade': grade})
            continue
        if cur is not None and '万元' in t and '奖励' in t:
            mm = re.search(r'奖励([\d.]+万元[^，。；]*)', t)
            if mm and not cur['reward']:
                cur['reward'] = mm.group(1) + ('/项' if '科室' in t else '/人')
            continue
        # 省科技奖团队：等级-团队-题目；（领奖人）
        if '团队' in t and re.search(r'[一二三]等奖', t):
            if cur is None or '科技奖' not in cur.get('name', ''):
                cur = {'name': '江西省科技奖先进科技团队', 'items': [],
                       'reward': '按表彰决定'}
                awards.append(cur)
            body = re.sub(r'^\d{1,2}、', '', t).strip()
            parts = [x for x in re.split(r'[-—]', body) if x.strip()]
            level = shorten_level(parts[0].strip()) if parts else ''
            team = parts[1].strip() if len(parts) > 1 else ''
            mm = re.search(r'；（(.+?)）', t) or re.search(r'\((.+?)\)', t)
            who = mm.group(1).strip() if mm else re.sub(r'团队$', '', team)
            unit = level + ('／' + team if team and not team.startswith(who) else '')
            item = {'unit': unit or team, 'name': who}
            # 省科技奖行首的“X等奖”即奖级，直接作为等次（用于奖级对位）
            gm = re.search(r'((?:特等|一等|二等|三等)奖|优秀奖)', level)
            if gm:
                item['grade'] = gm.group(1)
            cur['items'].append(item)
            continue
    for a in awards:
        for it in a['items']:
            if not it.get('grade'):
                it.pop('grade', None)
    return [a for a in awards if a['items']]


def norm(s):
    """归一化奖项名用于匹配：去掉申报口径与赘语"""
    return re.sub(r'(国基金申报|国家自然科学基金|获奖|代表|人员|科室|团队|工作)', '', s or '')


def match(agenda_items, detail_awards):
    """议程环节 × 明细奖项：归一化后互为子串即纳入（未匹配的多为教学类，排除）"""
    picked, excluded, used = [], [], set()
    for it in agenda_items:
        an = norm(it['name'])
        hit = None
        for k, aw in enumerate(detail_awards):
            if k in used:
                continue
            dn = norm(aw['name'])
            if dn and an and (dn == an or (len(dn) >= 3 and dn in an)
                              or (len(an) >= 3 and an in dn)):
                hit = k
                break
        if hit is None:
            excluded.append(it)
        else:
            used.add(hit)
            picked.append((it, detail_awards[hit]))
    return picked, excluded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agenda', required=True)
    ap.add_argument('--detail', required=True)
    ap.add_argument('--out', required=True, help='输出 data.json')
    ap.add_argument('--first-seat-row', type=int, default=4)
    ap.add_argument('--seats-per-row', type=int, default=6)
    ap.add_argument('--ushers', type=int, default=0,
                    help='礼仪人数；0=按“每2位领导配1名”自动取')
    ap.add_argument('--leader-rule', default='school_first',
                    choices=['school_first', 'doc'])
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    if os.path.exists(a.out) and not a.force:
        print('已存在', a.out, '（加 --force 覆盖）')
        return

    aps, dps = paras(a.agenda), paras(a.detail)
    meta = parse_meta(aps)
    leaders = order_leaders(parse_leaders(aps), a.leader_rule)
    agenda_items = parse_agenda_items(aps)
    detail_awards = parse_detail(dps)
    picked, excluded = match(agenda_items, detail_awards)

    awards = []
    for i, (it, aw) in enumerate(picked):
        awards.append({'no': i + 1, 'agenda': it['seq'], 'name': it['name'],
                       'reward': aw.get('reward') or '按表彰决定',
                       'items': aw['items']})

    data = {
        'meta': meta,
        'leaders': leaders,
        'awards': awards,
        'layout': {'first_seat_row': a.first_seat_row,
                   'seats_per_row': a.seats_per_row, 'ushers': a.ushers},
        # 未纳入的颁奖环节（多为教学类），用于在座位表说明中提示另行安排区域
        'excluded_agenda': [{'seq': x['seq'], 'name': x['name']} for x in excluded],
        # 需补充的会务说明，逐条追加到座位表末尾（如“某领导本人上台领奖”等特例）
        'extra_notes': [],
        '_review': {
            'leader_rule': a.leader_rule,
            'excluded_agenda_items': [x['name'] for x in excluded],
            'todo': ['核对 leaders 座次顺序（1号居中，奇数在左、偶数在右）',
                     '核对 awards 是否只含本部门负责发放的奖项',
                     '补齐 items 中 name=待定 的领奖代表',
                     '核对 meta 标题/时间/地点/主持人'],
        },
    }
    if any(it.get('grade') for x in awards for it in x['items']):
        data['_review']['todo'].insert(0, '核对带等次奖项的对位（一等奖→1号、二等奖→2/3号……同级按明细顺序）')
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

    total = sum(len(x['items']) for x in awards)
    todo = [f'{it["unit"]}' for x in awards for it in x['items']
            if it['name'] == '待定']
    print('== 解析结果 ==')
    print(f'会议：{meta.get("title", "?")}｜{meta.get("date", "?")}')
    if leaders:
        print(f'领导 {len(leaders)} 位：1号 {leaders[0]["name"]} 居中，'
              f'2号 {leaders[1]["name"] if len(leaders) > 1 else "—"}')
    print(f'颁奖环节 {len(agenda_items)} 个 → 纳入 {len(awards)} 个，排除 {len(excluded)} 个')
    print(f'领奖单元 {total} 个，其中待定 {len(todo)} 个：{"、".join(todo) or "无"}')
    for aw in awards:
        cnt = {}
        for it in aw['items']:
            if it.get('grade'):
                cnt[it['grade']] = cnt.get(it['grade'], 0) + 1
        gs = '，'.join(f'{g}{c}' for g, c in cnt.items())
        print(f'   {aw["no"]}. {aw["name"]}（{len(aw["items"])}位，'
              f'议程第{aw["agenda"]}项，{aw["reward"]}'
              + (f'；等次：{gs}' if gs else '') + '）')
    print('已写入', a.out, '——请核对后运行 build_tables.py')


if __name__ == '__main__':
    main()
