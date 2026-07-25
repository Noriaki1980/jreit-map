"""
J-REIT 取得物件データ 定期更新スクリプト（ひな形）
=================================================

現状できること:
  - JAPAN-REIT.COM が Yahoo!ファイナンスに配信するニュース一覧
    (https://finance.yahoo.co.jp/news/media/japanreit) から
    「〜を取得」を含む見出しを拾い、REIT名・物件名（見出しベース）を抽出
  - data/properties.csv に既存データと重複しない行だけ追記

現状できないこと（要拡張）:
  - 正式な取得価格・詳細所在地は見出しだけでは分からないため、
    本文ページ（各ニュース詳細）を個別に読みに行って抽出する処理が必要
    （本スクリプトでは detail 取得の骨組みだけ用意）
  - 緯度・経度の自動付与（ジオコーディング）
    → Google Geocoding API 等の有料APIキーが必要。
      GitHub Actions の Secrets に GOOGLE_MAPS_API_KEY を登録し、
      geocode() 内の TODO を実装してください。
  - japan-reit.com 本家の月次一覧ページ (report/shutoku/) は
    JavaScriptで描画されるため、requests + BeautifulSoup では
    最新月のデータを直接取得できません（確認済み）。
    Selenium/Playwright 等のヘッドレスブラウザ導入が必要です。

運用イメージ:
  GitHub Actions が週次でこのスクリプトを実行 → 新規行があれば
  data/properties.csv を更新 → 変更があれば自動コミット
  → GitHub Pages 上の index.html が最新CSVを表示
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone, timedelta
import urllib.request

NEWS_LIST_URL = "https://finance.yahoo.co.jp/news/media/japanreit"
CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "properties.csv")
HEADERS = ["REIT名", "証券コード", "物件名", "所在地", "用途", "取得予定日",
           "取得価格_億円", "緯度", "経度", "出典"]

# 主要エリアの概算座標（拡充してください。無ければ緯度・経度は空欄のまま出力）
AREA_COORDS = {
    "東京都千代田区": (35.6938, 139.7530),
    "東京都中央区": (35.6706, 139.7720),
    "東京都港区": (35.6581, 139.7514),
    "東京都渋谷区": (35.6640, 139.6982),
    "東京都新宿区": (35.6938, 139.7034),
    "大阪府大阪市": (34.6937, 135.5023),
    "福岡市": (33.5904, 130.4017),
    "名古屋市": (35.1815, 136.9066),
    "横浜市": (35.4437, 139.6380),
    "札幌市": (43.0618, 141.3545),
    "仙台市": (38.2682, 140.8694),
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read().decode("utf-8", errors="ignore")


def geocode(area: str):
    """
    TODO: Google Geocoding API などに差し替え可能。
    現状は AREA_COORDS の部分一致で概算座標を返す簡易版。
    """
    for key, coord in AREA_COORDS.items():
        if key in area:
            return coord
    return (None, None)


def parse_acquisition_headlines(html: str):
    """
    ニュース一覧HTMLから「〜が〜を取得」系の見出しを抽出する簡易パーサ。
    本番運用では BeautifulSoup 等でDOM構造から正確に抜き出すことを推奨。
    """
    pattern = re.compile(r"([^\s]{2,20}投資法人)が(.{2,40}?)を取得")
    results = []
    for m in pattern.finditer(html):
        reit, property_name = m.group(1), m.group(2)
        results.append({"REIT名": reit, "物件名": property_name})
    return results


def load_existing_keys(path):
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            keys.add((row.get("REIT名", ""), row.get("物件名", "")))
    return keys


def append_rows(path, new_rows):
    file_exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if not file_exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)


def main():
    html = fetch(NEWS_LIST_URL)
    candidates = parse_acquisition_headlines(html)
    existing = load_existing_keys(CSV_PATH)

    new_rows = []
    for c in candidates:
        key = (c["REIT名"], c["物件名"])
        if key in existing:
            continue
        lat, lng = geocode(c["物件名"])
        new_rows.append({
            "REIT名": c["REIT名"],
            "証券コード": "",
            "物件名": c["物件名"],
            "所在地": "",  # 詳細ページ取得実装後に埋める
            "用途": "",
            "取得予定日": "",
            "取得価格_億円": "",
            "緯度": lat if lat else "",
            "経度": lng if lng else "",
            "出典": NEWS_LIST_URL,
        })
        existing.add(key)

    if new_rows:
        append_rows(CSV_PATH, new_rows)
        print(f"{len(new_rows)}件の新規候補を追記しました（所在地・価格は要手動確認）")
    else:
        print("新規候補なし")

    # index.html の最終更新表示用タイムスタンプを更新
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).strftime("%Y-%m-%d")
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            r'window\.__LAST_UPDATED__ = "[^"]*"',
            f'window.__LAST_UPDATED__ = "{today}"',
            content,
        )
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)


if __name__ == "__main__":
    sys.exit(main())
