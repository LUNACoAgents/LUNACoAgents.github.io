#!/usr/bin/env python3
"""投資の森（nikkei225jp.com）の日次データから、日本の指標を取り出す。

https://nikkei225jp.com/data/per.php が読み込んでいるデータファイル（daily2.json）を直接読む。
WebFetch の要約を通さないので、数字の写しまちがいが起きない。

使い方:
  python3 scripts/fetch_nikkei225jp.py              # 最新の日
  python3 scripts/fetch_nikkei225jp.py 2026-11-12   # 日付を指定
出力（そのまま update_board.py jp に渡せる）:
  {"date": "2026-11-12", "nk": 60819.36, "adr25": 98.76, "nvi": 36.08, "nk_per_f": 15.35, "nk_pbr": 1.79,
   "nk_dy": 1.94, "nk_eps": 3962.17, "nk_bps": 33977.30}
"""
import datetime as dt
import json
import re
import sys
import subprocess

PAGE = 'https://nikkei225jp.com/data/per.php'
# 列の位置（2026-06〜11の既存データと突き合わせて確認ずみ）
COL = {'nk': 1, 'adr25': 7, 'nvi': 11, 'nk_per_f': 12, 'nk_pbr': 13, 'nk_dy': 14}


def load():
    # ページが読み込んでいるデータファイルの場所（版番号つき）をページから取り、curl で取る
    # （Python 標準の取得はこのサイトに断られるため curl を使う）
    get = lambda u: subprocess.run(['curl', '-sfL', '-m', '30', u], capture_output=True, check=True).stdout.decode('utf-8')
    m = re.search(r'src="(/_data/_nfsDATA/data_DAY/daily2\.json\?[0-9]+)"', get(PAGE))
    if not m:
        sys.exit('エラー: ページの中にデータファイルの場所が見つかりません（サイトの作りが変わったかも）')
    s = get('https://nikkei225jp.com' + m.group(1))
    body = s[s.index('['):s.rindex(']') + 1]
    body = re.sub(r',(?=\s*[,\]])', ',null', body)  # 空の欄を null に
    rows = {}
    for r in json.loads(body):
        day = dt.datetime.fromtimestamp(r[0] / 1000, dt.timezone(dt.timedelta(hours=9))).date().isoformat()
        rows[day] = r
    return rows


def pick(r):
    out = {}
    for k, c in COL.items():
        v = r[c] if c < len(r) else None
        if v not in (None, ''):
            out[k] = float(v)
    if out.get('nk') and out.get('nk_per_f'):
        out['nk_eps'] = round(out['nk'] / out['nk_per_f'], 2)
    if out.get('nk') and out.get('nk_pbr'):
        out['nk_bps'] = round(out['nk'] / out['nk_pbr'], 2)
    return out


def main():
    rows = load()
    day = sys.argv[1] if len(sys.argv) > 1 else max(rows)
    if day not in rows:
        sys.exit(f'エラー: {day} の行がありません（最新は {max(rows)}）')
    print(json.dumps({'date': day, **pick(rows[day])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
