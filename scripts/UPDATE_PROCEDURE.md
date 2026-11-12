# マーケット指標ボードの毎日の更新手順

毎日18:40（日本時間、平日）にレイが実行する。データは `market-data.js`、書き込みは必ず `scripts/update_board.py` を使う（前日比・騰落率・移動平均乖離率は道具が計算するので、生の値だけ渡す）。

## 1. 取る日を決める

- **日本**：今日（日本時間）が東証の営業日なら今日の分。休場日（土日・祝日・年末年始）は日本はやらない
- **米国**：日本時間の今朝6時ごろに確定した、直近の米国の取引日（現地日付）の分。米国が休場の日は入れない
- **前回の抜け**：`python3 scripts/update_board.py check` で最新行を見て、前の営業日に空の項目があれば、今回取れたら埋める

## 2. 値を集める（WebFetch で読む。数字はページの表記どおり、日付が合っているか必ず確かめる）

### 日本（`jp`）

**まず道具で取る（いちばん確か）**：`python3 scripts/fetch_nikkei225jp.py`（日付指定もできる）。投資の森のデータファイルを直接読んで、日経平均終値・騰落レシオ・日経VI・予想PER・PBR・配当利回り・EPS・BPS を出す。出力の日付が今日になっていれば、その JSON をそのまま `update_board.py jp` に渡す。今日の行がまだなければ、残りを下の表のページから取る。

| 項目 | キー | 出どころ | 単位・注意 |
|---|---|---|---|
| 日経平均・TOPIX・グロース250 終値 | `nk` `tp` `gr` | https://finance.matsui.co.jp/stock/index | 更新日時が今日の15:30（終値）になっていること。場中の値は使わない（`nk` は上の道具でも取れる） |
| 騰落レシオ（25日・プライム） | `adr25` | 上の道具。だめなら https://stock-marketdata.com/advance-decline-tse-prime-market | |
| 空売り比率（東証全体） | `short` | https://stock-marketdata.com/karauri.html | % |
| 日経VI | `nvi` | 上の道具。だめなら https://stock-marketdata.com/vi.html | |
| 日経平均 予想PER・EPS・PBR・配当利回り | `nk_per_f` `nk_eps` `nk_pbr` `nk_dy` | 上の道具。だめなら https://stock-marketdata.com/kabukashihyo.html | ページの場合は「加重平均」の列を使う（「指数」の列ではない）。`nk_bps` は `nk ÷ nk_pbr` を小数2桁で |
| 裁定買い残（株数） | `arb_buy` | https://stock-marketdata.com/saiteitorihiki.html | **万株**（8億1,863万株 → 81863）。数日遅れで出るので、出ている最新日の行に入れる |
| プライム・グロース全銘柄のPER・PBR | `pr_*` `gm_*` | まだ取れる場所がない | 入れない |

- 今日のPERがまだ出ていないとき：`nk_per_f = nk ÷ 前日のnk_eps`、`nk_pbr = nk ÷ 前日のnk_bps` で推計し、`val_est: 1` を付ける。翌日以降に正式値が出たら正式値に入れ替えて `val_est: 0`
- 騰落レシオ・空売り比率・日経VIが18:40にまだ出ていなければ、その項目は渡さない（次回に埋める）

### 米国（`us`、日付は現地の取引日）

| 項目 | キー | 出どころ |
|---|---|---|
| NYダウ・S&P500・NASDAQ総合 | `dji` `spx` `ixic` | https://finance.matsui.co.jp/stock-overseas/index |
| NASDAQ100・VIX | `ndx` `vix` | Yahoo Finance（^NDX・^VIX）など。WebSearch で当日の終値を確認 |
| 米10年債利回り | `tnx` | https://finance.matsui.co.jp/bonds/index（または Yahoo の ^TNX）。% |
| ドル円 | `usdjpy` | https://finance.matsui.co.jp/fx/index（米国の取引日の終値に近い値） |
| Fear & Greed | `fg` | https://stock-marketdata.com/cnn-fear-and-greed-index | 
| S&P500・NASDAQ100 の実績/予想PER（週1回） | `spx_per_t` `spx_per_f` `ndx_per_t` `ndx_per_f` | https://stock-marketdata.com/per-nasdaq.html（ページの日付の行に入れる。毎日は入れない） |

- **債券市場だけ休みの日**（SIFMAの休場日。コロンブスデー・ベテランズデーなど）は `tnx` を入れない。ページがこの日を自動で「休場」と表示する。新しい年の休場日は `market.html` の `BOND_HOLIDAYS` に足す

### 信用残（週1回・`margin`）

- https://stock-marketdata.com/shinyozandaka.html の最新の申込日の行。まだ入っていない週だけ入れる
- `buy` `sell` は**億円**（5兆8,809億円 → 58809）、`pl` は買い方の信用評価損益率（%）。信用倍率は道具が計算する

### 松井証券のお客さんの信用評価損益率（毎日・`matsui`）

- https://www.matsui.co.jp/market/ の「信用残速報（松井証券内）」。ログインはいらない
- ページに書いてある日付で入れる（`buy_pl` 買い方、`sell_pl` 売り方、%）。年が書いていないので今年として扱う

## 3. 書き込む

```
python3 scripts/update_board.py jp     '{"date":"YYYY-MM-DD","nk":...,"tp":...,"gr":...,"adr25":...}'
python3 scripts/update_board.py us     '{"date":"YYYY-MM-DD","spx":...,"tnx":...}'
python3 scripts/update_board.py margin '{"week":"YYYY-MM-DD","buy":...,"sell":...,"pl":...}'
python3 scripts/update_board.py matsui '{"date":"YYYY-MM-DD","buy_pl":...,"sell_pl":...}'
```

- 道具がエラーで止まったら、その値をもう一度出どころで確かめる。確かめても合わないときは、その項目は入れずに報告する
- 確信が持てない値は入れない（空欄のほうが、まちがった値よりいい）

## 4. 確認して公開する

1. `python3 scripts/update_board.py check` で最新行を見直す
2. `git diff --stat` で `market-data.js`（と必要なら `market.html`）だけが変わっていることを確かめる
3. コミットメッセージ：`マーケット指標を更新（日本M/D・米国M/D）`。main に push する
4. 1〜2分後に https://lunacoagents.github.io/market-data.js に今日の日付が出ていることを確かめる

## 5. 報告

ゆうやに短く伝える：入れた日付、主な値（日経平均・騰落レシオ・VIX・10年債）、取れなかった項目とその理由。
