#!/usr/bin/env python3
"""ORBIS の商品ページ（orbis_dump/pages.jsonl、fetch_site_pages.py で国内から取得）から全成分を読み取り、
data/products.json の ORBIS の製品を作り直す。

  python3 tools/import_orbis.py [--verified-at YYYY-MM-DD]

取り込むのは、アプリの分類（化粧水・乳液・ジェル・クリーム・下地・BB）に当たるものだけ。
洗顔・クレンジング・美容液・ファンデーション・パウダーは対象外（ほかのメーカーと同じ）。
価格は公式サイトで表示のときに読み込まれ、取得したページの文字に含まれないので入れない。
"""
import argparse
import json
import re
import sys

DUMP = "orbis_dump/pages.jsonl"
CATALOG = "data/products.json"
BASE_URL = "https://www.orbis.co.jp/small/{}/"

# (ページ番号, id, ブランド, 商品名, 分類, タイプ（品番の行に含まれる文字。複数タイプで成分が違うとき）, SPF, PA, 色)
ITEMS = [
    ("11010382", "orbis-u-essence-lotion", "オルビスユー", "エッセンスローション", "TONER", None, None, None, []),
    ("11010383", "orbis-u-gel-moisturizer", "オルビスユー", "ジェルモイスチャライザー", "GEL", None, None, None, []),
    ("11010502", "orbis-u-encore-lotion", "オルビスユー アンコール", "ローション", "TONER", None, None, None, []),
    ("11010503", "orbis-u-encore-day-milk", "オルビスユー アンコール", "デイミルク", "EMULSION", None, 20, "+++", []),
    ("11010504", "orbis-u-encore-night-creamy-gel", "オルビスユー アンコール", "ナイトクリーミージェル", "GEL", None, None, None, []),
    ("11010702", "orbis-u-white-lotion", "オルビスユー ホワイト", "ローション", "TONER", None, None, None, []),
    ("11010703", "orbis-u-white-day-moisture", "オルビスユー ホワイト", "デイモイスチャー", "EMULSION", None, 30, "+++", []),
    ("11010704", "orbis-u-white-night-moisture", "オルビスユー ホワイト", "ナイトモイスチャー", "EMULSION", None, None, None, []),
    ("11010705", "orbis-u-white-extra-creamy-moisture", "オルビスユー ホワイト", "エキストラ クリーミーモイスチャー", "CREAM", None, None, None, []),
    ("11010453", "orbis-amber-vital-treatment-cream", "オルビスアンバー", "ヴァイタルトリートメントクリーム", "CREAM", None, None, None, []),
    ("11010662", "orbis-bright-lotion-l", "オルビス ブライト", "ローション L（さっぱりタイプ）", "TONER", "L（さっぱりタイプ）", None, None, []),
    ("11010662", "orbis-bright-lotion-m", "オルビス ブライト", "ローション M（しっとりタイプ）", "TONER", "M（しっとりタイプ）", None, None, []),
    ("11010663", "orbis-bright-moisture-l", "オルビス ブライト", "モイスチャー L（さっぱりタイプ）", "EMULSION", "L（さっぱりタイプ）", None, None, []),
    ("11010663", "orbis-bright-moisture-m", "オルビス ブライト", "モイスチャー M（しっとりタイプ）", "EMULSION", "M（しっとりタイプ）", None, None, []),
    ("11011102", "orbis-clearful-lotion-l", "クリアフル", "ローション L（さっぱりタイプ）", "TONER", "L（さっぱりタイプ）", None, None, []),
    ("11011102", "orbis-clearful-lotion-m", "クリアフル", "ローション M（しっとりタイプ）", "TONER", "M（しっとりタイプ）", None, None, []),
    ("11011103", "orbis-clearful-moisture-l", "クリアフル", "モイスチャー L（さっぱりタイプ）", "EMULSION", "L（さっぱりタイプ）", None, None, []),
    ("11011103", "orbis-clearful-moisture-m", "クリアフル", "モイスチャー M（しっとりタイプ）", "EMULSION", "M（しっとりタイプ）", None, None, []),
    ("1156010", "orbis-enrich-cream", "オルビス", "エンリッチ クリーム", "CREAM", None, None, None, []),
    # ベース（下地）
    ("1152040", "orbis-clearful-day-care-base", "クリアフル", "デイケアベース", "BASE", None, 28, "+++", []),
    ("1253050", "orbis-skin-moisture-base", "オルビス", "スキンモイスチャーベース", "BASE", None, 28, "+++", []),
    ("1253030", "orbis-smooth-matte-base", "オルビス", "スムースマットベース", "BASE", None, None, None, []),
    ("1251201", "orbis-u-treatment-primer", "オルビスユー", "トリートメントプライマー", "BASE", None, 50, "+++", []),
    ("1301010", "orbis-sunscreen-on-face-moist", "オルビス", "サンスクリーン(R) オンフェイス モイスト", "BASE", "モイスト", 34, "+++", []),
    ("1301010", "orbis-sunscreen-on-face-light", "オルビス", "サンスクリーン(R) オンフェイス ライト", "BASE", "ライト", 34, "+++", []),
    ("1201100", "orbis-melty-moist-bb", "オルビス", "メルティーモイストBB", "BB_CC", None, 30, "+++", ["ライト", "ナチュラル"]),
    # 色で色材（酸化鉄）が違うので色ごとに分ける
    ("1201110", "orbis-whitening-bb-light", "オルビス", "ホワイトニングBB ライト", "BB_CC", "ライト", 40, "+++", []),
    ("1201110", "orbis-whitening-bb-natural", "オルビス", "ホワイトニングBB ナチュラル", "BB_CC", "ナチュラル", 40, "+++", []),
]


def load_pages():
    pages = {}
    with open(DUMP, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = re.search(r"/small/(\d+)/", r["url"])
            if m and "/review/" not in r["url"] and any("全成分" in l for l in r["lines"]):
                pages.setdefault(m.group(1), r["lines"])
    return pages


def entries(lines):
    """「［品番］商品名 容量」の行と、その次の行（全成分）の組。"""
    start = next(i for i, l in enumerate(lines) if "全成分" in l)
    out = []
    for i in range(start, len(lines) - 1):
        if lines[i] in ("ツイート", "商品選択"):
            break
        if lines[i].startswith("［"):
            out.append((lines[i], lines[i + 1]))
    return out


def clean(ing):
    ing = ing.replace("【全成分表示】", "").strip()
    # 医薬部外品はほかのメーカーと同じ「有効成分：…\nその他の成分：…」の形にそろえる
    m = re.fullmatch(r"【有効成分】\s*(.+?)\s*【その他の成分】\s*(.+)", ing)
    if m:
        ing = f"有効成分：{m.group(1)}\nその他の成分：{m.group(2)}"
    return ing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified-at", default="2026-11-14")
    a = ap.parse_args()
    pages = load_pages()
    made = []
    for sid, pid, brand, name, cat, variant, spf, pa, shades in ITEMS:
        if sid not in pages:
            sys.exit(f"page {sid} not in dump")
        es = [(h, i) for h, i in entries(pages[sid]) if variant is None or variant in h]
        ings = {clean(i) for _, i in es}
        if len(ings) != 1:
            sys.exit(f"{pid}: ingredients differ between entries ({len(ings)})")
        head = es[0][0]
        p = {
            "id": pid,
            "maker": "オルビス",
            "brand": brand,
            "name": name,
            "category": cat,
            "quasiDrug": "医薬部外品" in head,
            "jan": None,
            "ingredients": ings.pop(),
            "sourceUrl": BASE_URL.format(sid),
            "verifiedAt": a.verified_at,
            "amazonAsin": None,
        }
        if spf is not None:
            p["spf"], p["pa"] = spf, pa
        if shades:
            p["shades"] = shades
        made.append(p)
    with open(CATALOG, encoding="utf-8") as f:
        catalog = json.load(f)
    kept = [p for p in catalog["products"] if p.get("maker") != "オルビス"]
    catalog["products"] = kept + made
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"ORBIS: {len(made)} products")


if __name__ == "__main__":
    main()
