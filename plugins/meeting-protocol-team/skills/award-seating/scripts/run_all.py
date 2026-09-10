#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键流程：议程 docx + 表彰明细 docx -> 主表工作簿（5 个工作表，含桌牌打印单）

  python run_all.py --agenda 议程.docx --detail 明细.docx --outdir 输出目录

流程：
  1) parse_inputs.py  解析出 data.json（草稿）
  2) 停顿，等人工核对 data.json（加 --auto 可跳过停顿直接生成）
  3) build_tables.py  生成《…颁奖领导排位及领奖顺序.xlsx》：
     座位排布表 / 领导排位图(发放顺序) / 领奖顺序图 / 桌牌打印单 / 桌牌打印单(领导)
     后四表全部公式引用座位排布表，改座位表即全表联动。
  4) build_print.py   仅在加 --with-print 时另出独立打印单文件（一般不需要）

常用可选参数：
  --first-seat-row 4   礼堂前几排留空（默认第4排起排领奖人）
  --seats-per-row 6    每排座位数
  --leader-rule school_first|doc   主席台座次规则
  --duty-style compact|full        职务显示
  --template <xlsx>    独立打印单模板（默认 assets/打印单模板.xlsx）
  --force              覆盖已存在的 data.json
  --auto               不等待人工核对，直接出表
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(args):
    print('\n$ ' + ' '.join(f'"{x}"' if ' ' in x else x for x in args))
    r = subprocess.run([PY] + args)
    if r.returncode != 0:
        raise SystemExit(f'步骤失败：{args[-1]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agenda', required=True)
    ap.add_argument('--detail', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--template', default=os.path.join(HERE, '..', 'assets',
                                                       '打印单模板.xlsx'))
    ap.add_argument('--first-seat-row', type=int, default=4)
    ap.add_argument('--seats-per-row', type=int, default=6)
    ap.add_argument('--leader-rule', default='school_first',
                    choices=['school_first', 'doc'])
    ap.add_argument('--duty-style', default='compact', choices=['compact', 'full'])
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--auto', action='store_true')
    ap.add_argument('--with-print', action='store_true',
                    help='额外生成独立桌牌打印单文件（主表已内置「桌牌打印单」工作表，一般不需要）')
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    data = os.path.join(a.outdir, 'data.json')

    # 1 解析
    cmd = [os.path.join(HERE, 'parse_inputs.py'), '--agenda', a.agenda,
           '--detail', a.detail, '--out', data,
           '--first-seat-row', str(a.first_seat_row),
           '--seats-per-row', str(a.seats_per_row),
           '--leader-rule', a.leader_rule]
    if a.force:
        cmd.append('--force')
    run(cmd)

    D = json.load(open(data, encoding='utf-8'))
    todo = [it['unit'] for x in D['awards'] for it in x['items']
            if it['name'] == '待定']
    print('\n==== 需人工核对 ====')
    print('1) data.json 中 leaders 的座次顺序（1号居中、奇数在左偶数在右）')
    print('2) awards 是否只含本部门负责发放的奖项')
    if todo:
        print(f'3) 待定领奖代表 {len(todo)} 个：{"、".join(todo)}')
    print('4) meta：标题 / 时间 / 地点 / 主持人 / scope / extra_notes')
    if not a.auto:
        try:
            input('\n核对完 data.json 后按回车继续生成表格（Ctrl+C 可中止）...')
        except EOFError:
            print('（非交互环境，自动继续）')

    # 2 三表
    m = re.search(r'(\d{4})', D['meta'].get('date', ''))
    year = m.group(1) if m else 'output'
    xlsx = os.path.join(a.outdir, f'{year}年科教工作大会颁奖领导排位及领奖顺序.xlsx')
    run([os.path.join(HERE, 'build_tables.py'), '--data', data,
         '--out', xlsx, '--duty-style', a.duty_style])

    # 3 独立打印单（可选；主表已内置公式联动的「桌牌打印单」工作表）
    if a.with_print:
        out_p = os.path.join(a.outdir, f'打印单_{year}科教大会桌牌.xlsx')
        run([os.path.join(HERE, 'build_print.py'), '--src', xlsx,
             '--template', a.template, '--out', out_p,
             '--first-seat-row', str(a.first_seat_row)])

    print('\n==== 完成 ====')
    print('主表（含桌牌打印单工作表）：', xlsx)
    if a.with_print:
        print('独立打印单：', os.path.join(a.outdir, f'打印单_{year}科教大会桌牌.xlsx'))
    print('Word 模版：', os.path.join(HERE, '..', 'assets', '打印模版.docx'),
          '（MERGEFIELD "姓名"，数据源选主表「桌牌打印单」A:C /「桌牌打印单(领导)」）')


if __name__ == '__main__':
    main()
