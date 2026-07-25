# J-REIT 取得物件マップ

REIT別に色分けした、J-REIT各社の取得（予定）物件を表示するLeaflet地図です。
GitHub Pagesで公開し、GitHub Actionsで定期的にデータを更新する構成になっています。

## 構成

```
reit-map/
├── .github/workflows/update.yml   # 毎週月曜9:00(JST)に自動実行
├── scraper.py                      # データ取得スクリプト（要拡張、下記「制約」参照）
├── data/properties.csv             # 地図が読み込むデータ本体
├── index.html                      # Leaflet地図（GitHub Pagesで公開されるページ）
└── README.md
```

## 公開手順（最初の1回だけ）

1. このフォルダの中身をGitHubリポジトリにpush
2. リポジトリの **Settings → Pages** を開く
3. Source を「Deploy from a branch」、Branch を `main` / `/(root)` に設定 → Save
4. 数分後、`https://<ユーザー名>.github.io/<リポジトリ名>/` で地図が公開されます

## データ更新の仕組み

- `update.yml` が毎週月曜9:00(JST)に `scraper.py` を自動実行
- 新しい取得物件情報があれば `data/properties.csv` に追記してコミット・push
- 手動で今すぐ更新したい場合は、GitHubのActionsタブから
  `Update J-REIT property data` → `Run workflow` で即時実行可能

## 現状の制約（重要）

`scraper.py` は最小構成のひな形です。実運用前に以下の対応を推奨します。

| 課題 | 対応案 |
|---|---|
| 物件別の正確な取得価格・詳細所在地が見出しだけでは分からない | 各ニュース詳細ページ／適時開示PDFを個別に読みに行くパーサーを追加 |
| 緯度・経度が自動で入らない（エリア名からの概算のみ） | Google Geocoding API等のキーをGitHub Secretsに登録し `geocode()` を実装 |
| japan-reit.com本家の月次一覧ページはJavaScript描画のため直接スクレイピング不可 | Playwright/Selenium等ヘッドレスブラウザの導入、またはARES「J-REIT Databook」等の静的データソースへの切替を検討 |
| 会員限定の詳細データにはアクセスできない | 有料会員登録 + ログイン処理の実装（利用規約要確認） |

## data/properties.csv の列

| 列名 | 内容 |
|---|---|
| REIT名 | 投資法人名 |
| 証券コード | 証券コード |
| 物件名 | 物件名 |
| 所在地 | 市区町村レベルの所在地 |
| 用途 | オフィス／住宅／物流施設等 |
| 取得予定日 | 取得日または取得予定日 |
| 取得価格_億円 | 取得価格（億円）。不明な場合は空欄 |
| 緯度・経度 | 地図表示用の座標 |
| 出典 | 情報の出典URL・備考 |

このCSVを直接編集してpushするだけでも地図は更新されます（自動化を待たずに手動更新も可能）。

