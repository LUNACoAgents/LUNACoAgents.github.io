#!/usr/bin/env python3
"""マーケット指標ボードのデータ（market-data.js）に1日分の値を入れるための道具。

集めてきた「生の値」だけを渡せば、前日比・騰落率・移動平均乖離率はこの道具が計算する。
おかしな値（前日から大きく離れすぎ、数字でない等）は書き込まずにエラーで止まる。

使い方:
  python3 scripts/update_board.py jp     '{"date":"2026-11-13","nk":60819.36,"tp":3937.33,"gr":729.65,"adr25":98.76,...}'
  python3 scripts/update_board.py us     '{"date":"2026-11-12","spx":7619.38,"ixic":25466.19,...}'
  python3 scripts/update_board.py margin '{"week":"2026-11-06","buy":58809,"sell":6134,"pl":-21.08}'
  python3 scripts/update_board.py matsui '{"date":"2026-11-12","buy_pl":-14.328,"sell_pl":-16.859}'
  python3 scripts/update_board.py check   # 最新行のまとめを表示するだけ（書き込まない）

値に null を渡すと、その項目は消える（取れなかった・休場で値がない場合）。
"""
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'market-data.js'
PAGE = ROOT / 'market.html'

# 生の値として受け付ける項目
JP_RAW = {'nk', 'tp', 'gr', 'adr25', 'short', 'nvi', 'nk_per_f', 'nk_per_t', 'nk_pbr', 'nk_eps', 'nk_bps', 'nk_dy',
          'arb_buy', 'pr_per_t', 'pr_per_f', 'pr_pbr', 'gm_per_t', 'gm_per_f', 'gm_pbr', 'val_est', 'val_off'}
US_RAW = {'spx', 'ixic', 'ndx', 'dji', 'vix', 'fg', 'tnx', 'usdjpy', 'spx_per_t', 'spx_per_f', 'ndx_per_t', 'ndx_per_f'}
JP_IDX, JP_MA = ['nk', 'tp', 'gr'], [25, 75, 200]
US_IDX, US_MA = ['spx', 'ixic', 'ndx', 'dji'], [50, 200]

# 前日からこれ以上離れていたら書き込まない（取り違え防止）
MAX_JUMP = {'nk': 12, 'tp': 12, 'gr': 15, 'spx': 10, 'ixic': 12, 'ndx': 12, 'dji': 10, 'usdjpy': 6, 'tnx': 15}
RANGE = {'adr25': (30, 200), 'short': (20, 70), 'nvi': (5, 120), 'vix': (5, 100), 'fg': (0, 100), 'tnx': (0, 15),
         'usdjpy': (80, 250), 'nk_per_f': (5, 40), 'nk_pbr': (0.5, 5), 'spx_per_f': (8, 40), 'ndx_per_f': (8, 50)}


def load():
    s = DATA.read_text(encoding='utf-8')
    return json.loads(s[s.index('{'):s.rindex('}') + 1])


def save(d):
    out = ['window.MB_DATA = {']
    keys = list(d)
    for i, k in enumerate(keys):
        out.append(f'  {json.dumps(k)}: [')
        rows = d[k]
        for j, r in enumerate(rows):
            out.append('    ' + json.dumps(r, ensure_ascii=False) + (',' if j < len(rows) - 1 else ''))
        out.append('  ]' + (',' if i < len(keys) - 1 else ''))
    out.append('};')
    DATA.write_text('\n'.join(out) + '\n', encoding='utf-8')


def history():
    h = PAGE.read_text(encoding='utf-8')
    m = re.search(r'<script type="application/json" id="mb-chart-history">(.*?)</script>', h, re.S)
    return json.loads(m.group(1)) if m else {}


def closes(field, rows, hist):
    pts = dict(hist.get(field, {}).get('points', []))
    for r in rows:
        if r.get(field) is not None:
            pts[r['date']] = r[field]
    return sorted(pts.items())


def num(k, v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.replace(',', '').replace('%', '').replace('倍', '').strip()
    try:
        v = float(v)
    except ValueError:
        sys.exit(f'エラー: {k} の値「{v}」が数字ではありません')
    return int(v) if k in ('val_est', 'val_off', 'arb_buy', 'fg') else v


def check_date(s):
    try:
        day = dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        sys.exit(f'エラー: 日付「{s}」は YYYY-MM-DD で書いてください')
    if day.weekday() >= 5:
        sys.exit(f'エラー: {s} は土日です')
    if day > dt.date.today() + dt.timedelta(days=1):
        sys.exit(f'エラー: {s} は未来の日付です')
    return s


def add_daily(d, key, raw_keys, idx, mas, vals):
    date = check_date(vals.pop('date', None))
    unknown = set(vals) - raw_keys
    if unknown:
        sys.exit('エラー: 知らない項目があります: ' + ', '.join(sorted(unknown)))
    rows = d[key]
    row = next((r for r in rows if r['date'] == date), None)
    if row is None:
        row = {'date': date}
        rows.append(row)
        rows.sort(key=lambda r: r['date'])
    prev = [r for r in rows if r['date'] < date]
    for k, v in vals.items():
        v = num(k, v)
        if v is None:
            row.pop(k, None)
            continue
        if k in RANGE and not RANGE[k][0] <= v <= RANGE[k][1]:
            sys.exit(f'エラー: {k}={v} はありえない範囲です（{RANGE[k]}）')
        last = next((r[k] for r in reversed(prev) if r.get(k) is not None), None)
        if k in MAX_JUMP and last and abs(v / last - 1) * 100 > MAX_JUMP[k]:
            sys.exit(f'エラー: {k}={v} が前回 {last} から {abs(v / last - 1) * 100:.1f}% 離れています。値を確かめてください')
        row[k] = v
    hist = history()
    for f in idx:
        c = row.get(f)
        if c is None:
            continue
        series = [p for p in closes(f, rows, hist) if p[0] <= date]
        if len(series) >= 2:
            p = series[-2][1]
            row[f + '_chg'] = round(c - p, 2)
            row[f + '_pct'] = round((c / p - 1) * 100, 2)
        for n in mas:
            if len(series) >= n:
                sma = sum(v for _, v in series[-n:]) / n
                row[f'{f}_d{n}'] = round((c / sma - 1) * 100, 2)
    # 項目の並びをそろえる（生の値 → 計算した値）
    order = ['date'] + [k for k in row if k != 'date' and not re.search(r'_(chg|pct|d\d+)$', k)]
    order += [k for k in row if re.search(r'_(chg|pct|d\d+)$', k)]
    rows[rows.index(row)] = {k: row[k] for k in order}
    return rows[[r['date'] for r in rows].index(date)]


def add_margin(d, vals):
    week = check_date(vals.get('week'))
    buy, sell, pl = num('buy', vals.get('buy')), num('sell', vals.get('sell')), num('pl', vals.get('pl'))
    if not (buy and sell) or pl is None or not -60 < pl < 20:
        sys.exit('エラー: buy・sell（億円）と pl（%）をそろえてください')
    rows = d['jp_margin']
    row = {'week': week, 'buy': int(buy), 'sell': int(sell), 'pl': pl, 'ratio': round(buy / sell, 2)}
    rows[:] = [r for r in rows if r['week'] != week] + [row]
    rows.sort(key=lambda r: r['week'])
    return row


def add_matsui(d, vals):
    date = check_date(vals.get('date'))
    buy, sell = num('buy_pl', vals.get('buy_pl')), num('sell_pl', vals.get('sell_pl'))
    if buy is None or not -60 < buy < 30:
        sys.exit('エラー: buy_pl（買い方の評価損益率%）を確かめてください')
    rows = d.setdefault('jp_matsui', [])
    row = {'date': date, 'buy_pl': buy}
    if sell is not None:
        row['sell_pl'] = sell
    rows[:] = [r for r in rows if r['date'] != date] + [row]
    rows.sort(key=lambda r: r['date'])
    return row


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    d = load()
    if cmd == 'check':
        for k, rows in d.items():
            if rows:
                print(k, len(rows), json.dumps(rows[-1], ensure_ascii=False))
        return
    vals = json.loads(sys.argv[2])
    if cmd == 'jp':
        row = add_daily(d, 'jp_daily', JP_RAW, JP_IDX, JP_MA, vals)
    elif cmd == 'us':
        row = add_daily(d, 'us_daily', US_RAW, US_IDX, US_MA, vals)
    elif cmd == 'margin':
        row = add_margin(d, vals)
    elif cmd == 'matsui':
        row = add_matsui(d, vals)
    else:
        sys.exit(f'エラー: 「{cmd}」は使えません（jp / us / margin / matsui / check）')
    save(d)
    print('書き込みました:', json.dumps(row, ensure_ascii=False))


if __name__ == '__main__':
    main()
