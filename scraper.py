"""
J-REIT 取得物件データ 自動更新スクリプト（本格版）
====================================================

【重要な注意】
このスクリプトは、2026年7月にClaudeが各REIT公式サイトを手動で確認しながら
書いたものです。Claudeの実行環境にはインターネット接続がないため、
このコード自体を実際に動かして動作確認することができていません。
GitHub Actions上で初めて実行され、そこで初めて成功/失敗が分かります。

失敗した場合は、Actionsのログ（どのサイトで何のエラーが出たか）を
Claudeに共有してもらえれば、該当箇所を修正します。

対応REIT（17銘柄、HTML構造が比較的シンプルで自動化を試みたもの）:
  物流: GLP, 日本プロロジスリート, 日本ロジスティクスファンド, MFLP,
        三菱地所物流リート, CREロジスティクスファンド, ラサールロジポート, SOSiLA
  ホテル: ジャパン・ホテル・リート, 日本ホテル&レジデンシャル
  ヘルスケア: ヘルスケア&メディカル
  商業施設: 三井不動産商業ファンド
  住宅: コンフォリア・レジデンシャル, 三井不動産アコモデーションファンド
  オフィス: 日本ビルファンド, ジャパンリアルエステイト, 大和証券オフィス

【自動化を見送った銘柄】(このスクリプトでは触らない。CSV内の該当行はそのまま保持)
  - 星野リゾート・リート: 所在地が「地域」区分のみで住所がなく、
    物件名から個別に地図検索して座標を特定したため自動化不可
  - 大和証券リビング: 同上、地域区分のみ
  - アドバンス・レジデンス: 公式ページがJS動的読み込みで全287件のうち
    118件しか静的取得できなかった
  - いちごホテルリート/いちごオフィスリート/イオンリート/日本都市ファンド:
    JS動的読み込み、またはCSVがShift-JISで文字化けし取得不可
"""

import csv
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "properties.csv")
FIELDNAMES = ["REIT名", "証券コード", "物件名", "所在地", "用途", "取得予定日",
              "取得価格_億円", "緯度", "経度", "出典", "属性"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JREITMapBot/1.0)"}
TIMEOUT = 30

# ----------------------------------------------------------------------
# 市区町村 → 概算座標（このプロジェクトを通じて集めたものを集約）
# 完全一致ではなく部分一致(in演算子)でマッチさせる
# ----------------------------------------------------------------------
CITY_COORDS = {
    "北海道札幌市": (43.0618, 141.3545), "北海道旭川市": (43.7706, 142.3650),
    "宮城県仙台市": (38.2682, 140.8694), "宮城県富谷市": (38.3489, 140.8850),
    "茨城県常総市": (36.0241, 139.9943), "茨城県つくば市": (36.0839, 140.0761),
    "茨城県つくばみらい市": (35.9506, 139.9958), "茨城県土浦市": (36.0781, 140.1969),
    "茨城県古河市": (36.1786, 139.7522), "茨城県水戸市": (36.3658, 140.4711),
    "栃木県日光市": (36.7211, 139.6983), "群馬県渋川市": (36.4886, 139.0022),
    "群馬県高崎市": (36.3228, 139.0031), "群馬県太田市": (36.2914, 139.3756),
    "埼玉県さいたま市": (35.8617, 139.6455), "埼玉県川口市": (35.8078, 139.7242),
    "埼玉県川越市": (35.9251, 139.4858), "埼玉県草加市": (35.8256, 139.8047),
    "埼玉県越谷市": (35.8917, 139.7903), "埼玉県三郷市": (35.8322, 139.8747),
    "埼玉県春日部市": (35.9758, 139.7522), "埼玉県加須市": (36.1276, 139.6013),
    "埼玉県北本市": (36.0069, 139.5286), "埼玉県久喜市": (36.0642, 139.6667),
    "埼玉県上尾市": (35.9758, 139.5906), "埼玉県所沢市": (35.7994, 139.4694),
    "埼玉県新座市": (35.7847, 139.5658), "埼玉県八潮市": (35.8175, 139.8300),
    "埼玉県戸田市": (35.8172, 139.6789), "埼玉県羽生市": (36.1783, 139.5486),
    "埼玉県吉川市": (35.8908, 139.8542), "千葉県千葉市": (35.6073, 140.1063),
    "千葉県船橋市": (35.6947, 139.9825), "千葉県習志野市": (35.6673, 140.0129),
    "千葉県柏市": (35.8676, 139.9709), "千葉県松戸市": (35.7877, 139.9033),
    "千葉県市川市": (35.7219, 139.9306), "千葉県浦安市": (35.6534, 139.9016),
    "千葉県野田市": (35.9486, 139.8753), "千葉県印西市": (35.8244, 140.1467),
    "千葉県八千代市": (35.7186, 140.1006), "千葉県成田市": (35.7767, 140.3183),
    "千葉県富里市": (35.7373, 140.3444), "千葉県白井市": (35.7817, 140.0669),
    "東京都千代田区": (35.6938, 139.7530), "東京都中央区": (35.6706, 139.7720),
    "東京都港区": (35.6581, 139.7514), "東京都新宿区": (35.6938, 139.7034),
    "東京都文京区": (35.7075, 139.7519), "東京都台東区": (35.7128, 139.7800),
    "東京都墨田区": (35.7106, 139.8014), "東京都江東区": (35.6729, 139.8172),
    "東京都品川区": (35.6092, 139.7300), "東京都目黒区": (35.6414, 139.6983),
    "東京都大田区": (35.5613, 139.7161), "東京都世田谷区": (35.6467, 139.6533),
    "東京都渋谷区": (35.6640, 139.6982), "東京都中野区": (35.7073, 139.6637),
    "東京都杉並区": (35.6994, 139.6364), "東京都豊島区": (35.7261, 139.7164),
    "東京都北区": (35.7526, 139.7336), "東京都荒川区": (35.7364, 139.7833),
    "東京都板橋区": (35.7514, 139.7092), "東京都練馬区": (35.7357, 139.6517),
    "東京都足立区": (35.7750, 139.8044), "東京都葛飾区": (35.7436, 139.8469),
    "東京都江戸川区": (35.7066, 139.8686), "東京都八王子市": (35.6551, 139.3392),
    "東京都立川市": (35.6938, 139.4136), "東京都昭島市": (35.7053, 139.3546),
    "東京都羽村市": (35.7756, 139.3122), "東京都調布市": (35.6513, 139.5417),
    "東京都町田市": (35.5464, 139.4467), "東京都武蔵村山市": (35.7519, 139.3908),
    "東京都日野市": (35.6714, 139.3947), "東京都西東京市": (35.7256, 139.5378),
    "東京都狛江市": (35.6367, 139.5772), "東京都小金井市": (35.6997, 139.5147),
    "神奈川県横浜市": (35.4437, 139.6380), "神奈川県川崎市": (35.5308, 139.7029),
    "神奈川県相模原市": (35.5714, 139.3739), "神奈川県藤沢市": (35.3389, 139.4867),
    "神奈川県厚木市": (35.4419, 139.3639), "神奈川県座間市": (35.4886, 139.4056),
    "神奈川県海老名市": (35.4483, 139.3892), "神奈川県平塚市": (35.3267, 139.3411),
    "神奈川県伊勢原市": (35.4033, 139.3139), "神奈川県横須賀市": (35.2811, 139.6722),
    "神奈川県三浦市": (35.1439, 139.6167), "神奈川県小田原市": (35.2547, 139.1522),
    "神奈川県南足柄市": (35.3308, 139.1006), "神奈川県綾瀬市": (35.4358, 139.4319),
    "神奈川県鎌倉市": (35.3192, 139.5467), "神奈川県愛甲郡": (35.5167, 139.3167),
    "新潟県新潟市": (37.9161, 139.0364), "石川県金沢市": (36.5613, 136.6562),
    "福井県あわら市": (36.2233, 136.2306), "山梨県": (35.6739, 138.5683),
    "長野県": (36.2048, 138.2529), "岐阜県羽島市": (35.3081, 136.7000),
    "静岡県磐田市": (34.7167, 137.8500), "静岡県富士市": (35.1611, 138.6764),
    "愛知県名古屋市": (35.1815, 136.9066), "愛知県小牧市": (35.2989, 136.9128),
    "愛知県春日井市": (35.2477, 136.9725), "愛知県東海市": (35.0353, 136.9014),
    "愛知県愛西市": (35.1381, 136.7947), "愛知県稲沢市": (35.2506, 136.7861),
    "愛知県北名古屋市": (35.2506, 136.8617), "愛知県一宮市": (35.3042, 136.8033),
    "愛知県犬山市": (35.3317, 136.9370), "三重県桑名市": (35.0667, 136.6944),
    "三重県鈴鹿市": (34.8781, 136.5844), "京都府京都市": (35.0116, 135.7681),
    "京都府京田辺市": (34.8144, 135.7514), "京都府八幡市": (34.8955, 135.7044),
    "大阪府大阪市": (34.6937, 135.5023), "大阪府堺市": (34.5733, 135.4831),
    "大阪府枚方市": (34.8153, 135.6497), "大阪府茨木市": (34.8158, 135.5686),
    "大阪府高槻市": (34.8467, 135.6178), "大阪府門真市": (34.7381, 135.5714),
    "大阪府寝屋川市": (34.7644, 135.6283), "大阪府摂津市": (34.7583, 135.5619),
    "大阪府交野市": (34.7583, 135.6772), "大阪府東大阪市": (34.6783, 135.6006),
    "大阪府豊中市": (34.7815, 135.4694), "大阪府吹田市": (34.7617, 135.5158),
    "大阪府大東市": (34.7167, 135.6222), "兵庫県神戸市": (34.6901, 135.1955),
    "兵庫県尼崎市": (34.7331, 135.4053), "兵庫県西宮市": (34.7381, 135.3419),
    "兵庫県川西市": (34.8331, 135.4167), "兵庫県加古川市": (34.7575, 134.8408),
    "兵庫県明石市": (34.6486, 134.9975), "兵庫県川辺郡": (34.8836, 135.3572),
    "滋賀県草津市": (35.0128, 135.9600), "滋賀県野洲市": (35.0553, 136.0269),
    "滋賀県湖南市": (34.9989, 136.0067), "奈良県奈良市": (34.6851, 135.8048),
    "岡山県総社市": (34.6667, 133.7500), "岡山県都窪郡": (34.6081, 133.8317),
    "岡山県岡山市": (34.6551, 133.9195), "広島県広島市": (34.3853, 132.4553),
    "香川県丸亀市": (34.2894, 133.7981), "香川県高松市": (34.3401, 134.0434),
    "愛媛県松山市": (33.8392, 132.7657), "福岡県福岡市": (33.5904, 130.4017),
    "福岡県糟屋郡": (33.6167, 130.4667), "福岡県小郡市": (33.4306, 130.5533),
    "佐賀県鳥栖市": (33.3778, 130.5069), "佐賀県三養基郡": (33.4908, 130.5153),
    "熊本県熊本市": (32.8032, 130.7079), "福島県会津若松市": (37.4956, 139.9294),
    "福島県郡山市": (37.4003, 140.3592), "沖縄県那覇市": (26.2124, 127.6809),
    "沖縄県浦添市": (26.2517, 127.7217), "沖縄県中頭郡": (26.3958, 127.7614),
    "沖縄県名護市": (26.5917, 127.9772), "沖縄県糸満市": (26.1247, 127.6689),
}


def geocode(addr: str):
    if not addr:
        return (None, None)
    for key, coord in CITY_COORDS.items():
        if key in addr:
            return coord
    pref_match = re.match(r"(..??[都道府県])", addr)
    if pref_match:
        pref = pref_match.group(1)
        for key, coord in CITY_COORDS.items():
            if key.startswith(pref):
                return coord
    return (None, None)


def fetch_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "html.parser")


LEADING_NUMBER_RE = re.compile(r"^[\d,]+(?:\.\d+)?")


def parse_price_to_oku(text: str, unit: str = "百万円"):
    """
    価格セルのテキストから数値を取り出して億円に変換する。

    一部サイト（例: 日本ロジスティクスファンド）は、PC表示用とスマホ表示用の
    要素が同じセル内に両方存在し、get_text()で両方の値が区切りなく連結されて
    しまうことがある。例: "1,4661,466.0"（"1,466" と "1,466.0" が連結）。

    対策として、セル先頭の連続した数字(カンマ・小数点含む)を1つの塊として取り出し、
    整数部分の桁を半分に割って前半＝後半かどうかを確認する。一致すれば重複と判断し
    片方だけを使う。一致しなければ（桁数が奇数、または前半≠後半なら）通常の数値として
    そのまま扱う。単純な正規表現の重複マッチよりも誤判定が起きにくい。
    """
    if not text:
        return None

    text = text.strip()
    m = LEADING_NUMBER_RE.match(text)
    if not m:
        return None
    raw = m.group(0)

    if "." in raw:
        int_part, dec_part = raw.split(".", 1)
    else:
        int_part, dec_part = raw, None

    int_digits = int_part.replace(",", "")
    if not int_digits:
        return None

    n = len(int_digits)
    if n % 2 == 0 and n >= 4:
        half = n // 2
        first, second = int_digits[:half], int_digits[half:]
        if first == second:
            int_digits = first  # 重複と判定 → 片方だけ使う

    cleaned = int_digits + (f".{dec_part}" if dec_part else "")
    try:
        value = float(cleaned)
    except ValueError:
        return None

    if unit == "百万円":
        result = round(value / 100, 2)
    elif unit == "千円":
        result = round(value / 100000, 2)
    elif unit == "円":
        result = round(value / 100000000, 2)
    else:
        result = round(value, 2)

    # 単一物件の取得価格として現実的にありえない大きさなら、
    # 集計行やパース失敗の混入とみなして捨てる（安全装置）
    if result is not None and result > 5000:
        return None
    return result


def clean_address(addr: str) -> str:
    """
    所在地セル末尾に紛れ込む、地域区分ラベルなどの余分な1桁数字を取り除く。
    例: "神奈川県平塚市1" -> "神奈川県平塚市"
    住所自体が数字（丁目・番地）で終わる場合は誤って削らないよう、
    直前が日本語の住所語尾（市区町村郡都道府県）の場合のみ末尾の単独数字を削る。
    """
    if not addr:
        return addr
    return re.sub(r"(?<=[市区町村郡都道府県])\d$", "", addr.strip()).strip()


def generic_table_scrape(url, name_keys, addr_keys, price_keys, price_unit="百万円"):
    """
    <table> を総当たりし、ヘッダー行に name_keys/addr_keys/price_keys に
    部分一致する列があるテーブルをデータテーブルとみなして抽出する。
    """
    soup = fetch_soup(url)
    results = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        headers = [c.get_text(strip=True) for c in header_row.find_all(["th", "td"])]
        if not headers:
            continue

        def find_col(keys):
            for i, h in enumerate(headers):
                if any(k in h for k in keys):
                    return i
            return None

        idx_name = find_col(name_keys)
        idx_addr = find_col(addr_keys)
        idx_price = find_col(price_keys)
        if idx_name is None or idx_addr is None:
            continue

        rows = table.find_all("tr")[1:]
        for tr in rows:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(idx_name, idx_addr):
                continue
            name = cells[idx_name].get_text(strip=True)
            addr = clean_address(cells[idx_addr].get_text(strip=True))
            if not name or not addr:
                continue
            # 「合計」「小計」などの集計行は物件データではないため除外
            if name in ("合計", "小計", "計") or addr in ("合計", "小計", "計"):
                continue
            price_text = cells[idx_price].get_text(strip=True) if idx_price is not None and idx_price < len(cells) else ""
            results.append({
                "name": name, "addr": addr,
                "price_oku": parse_price_to_oku(price_text, price_unit),
            })
    return results


SITE_CONFIGS = [
    dict(reit="ラサールロジポート投資法人", code="3466", attribute="物流施設",
         url="https://lasalle-logiport.com/ja/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="GLP投資法人", code="3281", attribute="物流施設",
         url="https://www.glpjreit.com/ja/portfolio/index.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="日本プロロジスリート投資法人", code="3283", attribute="物流施設",
         url="https://www.prologis-reit.co.jp/ja/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="日本ロジスティクスファンド投資法人", code="8967", attribute="物流施設",
         url="https://8967.jp/ja/portfolio/index.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="三井不動産ロジスティクスパーク投資法人", code="3471", attribute="物流施設",
         url="https://www.mflp-r.co.jp/ja/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="三菱地所物流リート投資法人", code="3481", attribute="物流施設",
         url="https://www.mel-reit.co.jp/ja/portfolio/index.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="CREロジスティクスファンド投資法人", code="3487", attribute="物流施設",
         url="https://cre-reit.co.jp/ja/portfolio/index.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="SOSiLA物流リート投資法人", code="2979", attribute="物流施設",
         url="https://sosila-reit.co.jp/ja/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="ジャパン・ホテル・リート投資法人", code="8985", attribute="ホテル",
         url="https://www.jhrth.co.jp/ja/portfolio/list.html",
         name_keys=["物件名", "名称", "ホテル名"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="日本ホテル&レジデンシャル投資法人", code="3472", attribute="ホテル",
         url="https://nhr-reit.com/ja/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="ヘルスケア&メディカル投資法人", code="3455", attribute="ヘルスケア",
         url="https://hcm3455.co.jp/ja/portfolio/list.html",
         name_keys=["物件名", "名称", "施設名"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="三井不動産商業ファンド投資法人", code="8964", attribute="商業施設",
         url="https://www.mrf-r.co.jp/ja/portfolio/index.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="コンフォリア・レジデンシャル投資法人", code="3282", attribute="住宅",
         url="https://www.comforia-reit.co.jp/ja/portfolio/index.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="三井不動産アコモデーションファンド投資法人", code="3226", attribute="住宅",
         url="https://www.naf-r.jp/portfolio/5-1.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="日本ビルファンド投資法人", code="8951", attribute="オフィス",
         url="https://www.nbf-m.com/nbf/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="ジャパンリアルエステイト投資法人", code="8952", attribute="オフィス",
         url="https://www.j-re.co.jp/ja_cms/portfolio/list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
    dict(reit="大和証券オフィス投資法人", code="8976", attribute="オフィス",
         url="https://www.daiwa-office.co.jp/ja/portfolio/port_list.html",
         name_keys=["物件名", "名称"], addr_keys=["所在地"], price_keys=["取得価格"]),
]

AUTOMATED_REIT_NAMES = {c["reit"] for c in SITE_CONFIGS}


def scrape_site(config):
    raw_rows = generic_table_scrape(
        config["url"], config["name_keys"], config["addr_keys"], config["price_keys"]
    )
    out = []
    for r in raw_rows:
        lat, lng = geocode(r["addr"])
        out.append({
            "REIT名": config["reit"],
            "証券コード": config["code"],
            "物件名": r["name"],
            "所在地": r["addr"],
            "用途": config["attribute"],
            "取得予定日": "既存保有",
            "取得価格_億円": r["price_oku"] if r["price_oku"] is not None else "",
            "緯度": lat if lat is not None else "",
            "経度": lng if lng is not None else "",
            "出典": f"{config['url']} (自動取得 {datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d')})",
            "属性": config["attribute"],
        })
    return out


def load_existing_rows():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save_rows(rows):
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDNAMES})


def main():
    existing = load_existing_rows()
    kept_rows = [r for r in existing if r.get("REIT名") not in AUTOMATED_REIT_NAMES]
    print(f"保持する既存行（自動化対象外）: {len(kept_rows)}件")

    new_rows = []
    failed = []
    for config in SITE_CONFIGS:
        try:
            rows = scrape_site(config)
            if not rows:
                raise ValueError("0件しか取得できませんでした（テーブル構造が変わった可能性）")
            new_rows.extend(rows)
            print(f"OK  {config['reit']}: {len(rows)}件")
        except Exception as e:
            failed.append((config["reit"], str(e)))
            print(f"NG  {config['reit']}: {e}")
        time.sleep(1)

    if not new_rows and failed:
        print("全サイトで取得に失敗したため、既存CSVは変更しません。")
        sys.exit(1)

    final_rows = kept_rows + new_rows
    save_rows(final_rows)
    print(f"\n合計 {len(final_rows)}件を保存しました（自動取得: {len(new_rows)}件）")

    if failed:
        print(f"\n以下 {len(failed)}件のREITで取得に失敗しました（該当REITの既存データは変更されていません）:")
        for reit, err in failed:
            print(f"  - {reit}: {err}")

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
