#!/usr/bin/env python3
"""Yahoo!ショッピング 商品検索API（v3）で、カタログの各製品の商品画像を探して data/images.json に保存する。

  YAHOO_APP_ID=... python3 tools/fetch_yahoo_images.py            # 全件
  YAHOO_APP_ID=... python3 tools/fetch_yahoo_images.py --dry-run  # 保存せず、一致の結果だけ表示

探し方
  1. JAN コードがある製品は jan_code で検索し、JAN が同じ商品だけを使う。
  2. ない製品は「ブランド 名前」で検索し、名前の語がすべて含まれる商品だけを使う。
     I / II / III や 01 / 02 のような英数字は単語として一致させる（「化粧水 I」が「化粧水 II」に一致しないように）。
     セット・まとめ買い・お試し・詰め替え（製品名にないとき）などは除外する。
見つからなければ画像なしのまま（アプリはイラストを出す）。間違った写真を出すよりよい。

利用条件: 1秒に1回まで。表示するところには「Webサービス by Yahoo! JAPAN」のクレジットが必要。
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
CREDIT = "Webサービス by Yahoo! JAPAN"
CREDIT_URL = "https://developer.yahoo.co.jp/sitemap/"
# 一致しても使わない商品（中身が違う・数が違う）
EXCLUDE = ["セット", "まとめ買い", "まとめ売り", "お試し", "トライアル", "サンプル", "ミニサイズ", "福袋", "訳あり", "中古",
           "2個", "3個", "4個", "5個", "6個", "2本", "3本", "4本", "5本", "6本", "×2", "x2", "×3", "x3", "ケース販売"]
REFILL = ["詰め替え", "詰替", "つめかえ", "付け替え", "付替", "つけかえ", "取替", "レフィル", "リフィル", "替え"]
# 同じ製品の種類違い（しっとり／とてもしっとり など）。出品名にあって製品名にない語があれば別の種類
VARIANTS = ["とても", "もっと", "やや", "さっぱり", "しっとり", "さらっと", "ライト", "リッチ"]
# 一致の判定で無視する語（どの商品名にも付く飾り）
STOP = {"の", "用", "公式", "送料無料", "国内正規品"}
RETRY_WAITS = [10, 30, 60, 120]
INTERVAL = 1.5  # リクエストの間隔（秒）。上限は1秒に1回だが、余裕を持たせる
KEEP_DAYS = 120  # 見つからなくなった画像を残す日数（出品が一時的に消えることがある）


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return s.replace("・", " ").replace("　", " ")


def tokens(name: str) -> list[str]:
    parts = re.split(r"[\s/()（）\[\]【】「」『』,、。:：+＋]+", norm(name))
    return [p for p in parts if p and p not in STOP]


def has_token(text: str, tok: str) -> bool:
    if re.fullmatch(r"[a-z0-9.+\-]+", tok):
        return re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", text) is not None
    return tok in text


def excluded(hit_name: str, product_name: str) -> bool:
    t = norm(hit_name)
    if any(norm(w) in t for w in EXCLUDE):
        return True
    p = norm(product_name)
    return any(norm(w) in t and norm(w) not in p for w in REFILL)


def name_match(product: dict, hit: dict) -> bool:
    text = norm(hit.get("name", "")) + " " + norm((hit.get("brand") or {}).get("name", ""))
    brand = norm(product["brand"]).replace(" ", "")
    if brand not in text.replace(" ", ""):
        return False
    compact = text.replace(" ", "")
    pname = norm(product["name"]).replace(" ", "")
    if any(v in compact and v not in pname for v in VARIANTS):
        return False
    for tok in tokens(product["name"]):
        if re.fullmatch(r"[a-z0-9.+\-]+", tok):
            if not has_token(text, tok):
                return False
        elif tok not in compact:
            return False
    return True


def search(app_id: str, **params) -> list[dict]:
    q = {"appid": app_id, "results": 30, "image_size": 600}
    q.update(params)
    url = ENDPOINT + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "skincare-catalog/1.0"})
    # 429（短時間にリクエストが多すぎる）は、待ってからやり直す（10・30・60・120秒）。それでもだめなら諦める
    for wait in RETRY_WAITS + [None]:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("hits", [])
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or wait is None:
                raise
            print(f"  … HTTP {e.code}、{wait}秒待ってやり直します", file=sys.stderr)
            time.sleep(wait)
    return []


def pick(product: dict, hits: list[dict]) -> tuple[dict | None, str]:
    jan = product.get("jan")
    ok = [h for h in hits if not excluded(h.get("name", ""), product["name"]) and (h.get("exImage") or {}).get("url")]
    if jan:
        same = [h for h in ok if h.get("janCode") == jan]
        if same:
            return best(same), "jan"
    named = [h for h in ok if name_match(product, h)]
    # JAN が分かっている製品で、名前は合うが JAN が違う商品は使わない（色・容量違いの可能性）
    if jan:
        named = [h for h in named if not h.get("janCode") or h.get("janCode") == jan]
    return (best(named), "name") if named else (None, "")


def best(hits: list[dict]) -> dict:
    # 在庫あり → レビューが多い順（よく売れている＝商品写真がきちんとしていることが多い）
    return sorted(hits, key=lambda h: (not h.get("inStock"), -((h.get("review") or {}).get("count") or 0)))[0]


def entry(hit: dict, how: str, today: str) -> dict:
    return {
        "url": hit["exImage"]["url"],
        "thumbUrl": (hit.get("image") or {}).get("medium"),
        "itemUrl": hit.get("url"),
        "match": how,
        "hitName": hit.get("name"),
        "hitJan": hit.get("janCode") or None,
        "fetchedAt": today,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="data/products.json")
    ap.add_argument("--out", default="data/images.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="先頭から N 件だけ（試し用）")
    ap.add_argument("--only", help="この ID を含む製品だけ（正規表現）")
    ap.add_argument("--missing", action="store_true", help="画像がまだない製品だけ（前回取りこぼした分の取り直し）")
    args = ap.parse_args()
    app_id = (os.environ.get("YAHOO_APP_ID") or "").strip()  # 貼り付けたときの改行・空白を除く
    if not app_id:
        print("YAHOO_APP_ID が未設定です", file=sys.stderr)
        return 2
    # 値は出さず、形だけ確かめる（Client ID はふつう dj00 で始まる。シークレットと取り違えやすい）
    print(f"YAHOO_APP_ID: {len(app_id)}文字・dj0 で{'始まる' if app_id.startswith('dj0') else '始まらない'}")
    try:
        search(app_id, query="化粧水", results=1)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"API の確認に失敗: HTTP {e.code} {body}", file=sys.stderr)
        print("Client ID（アプリケーションID）が正しいか、Secrets の値を確かめてください。", file=sys.stderr)
        return 1
    time.sleep(INTERVAL)

    products = json.loads(Path(args.catalog).read_text(encoding="utf-8"))["products"]
    if args.only:
        products = [p for p in products if re.search(args.only, p["id"])]
    if args.limit:
        products = products[: args.limit]
    out = Path(args.out)
    old = json.loads(out.read_text(encoding="utf-8")).get("images", {}) if out.exists() else {}
    if args.missing:
        products = [p for p in products if p["id"] not in old]
    today = dt.date.today().isoformat()
    images: dict[str, dict] = {}
    found = {"jan": 0, "name": 0}
    for i, p in enumerate(products):
        hits: list[dict] = []
        try:
            if p.get("jan"):
                hits = search(app_id, jan_code=p["jan"])
                time.sleep(INTERVAL)
            if not any(h.get("janCode") == p.get("jan") for h in hits):
                hits += search(app_id, query=f"{p['brand']} {p['name']}")
                time.sleep(INTERVAL)
        except Exception as e:  # 通信の失敗は前回の結果を残す
            print(f"  ! {p['id']}: {e}", file=sys.stderr)
            if p["id"] in old:
                images[p["id"]] = old[p["id"]]
            time.sleep(2)
            continue
        hit, how = pick(p, hits)
        if hit:
            found[how] += 1
            images[p["id"]] = entry(hit, how, today)
            print(f"[{i + 1}/{len(products)}] {how:4} {p['brand']} {p['name']}  ←  {hit.get('name', '')[:70]}")
        else:
            prev = old.get(p["id"])
            if prev and (dt.date.fromisoformat(today) - dt.date.fromisoformat(prev["fetchedAt"])).days <= KEEP_DAYS:
                images[p["id"]] = prev
            print(f"[{i + 1}/{len(products)}] --   {p['brand']} {p['name']}  （{len(hits)}件中 一致なし）")

    print(f"\n一致 {found['jan'] + found['name']}/{len(products)}（JAN {found['jan']}・名前 {found['name']}）")
    if args.dry_run:
        return 0
    if args.only or args.limit or args.missing:  # 一部だけ取ったときは、残りの前回の結果を消さない
        images = {**old, **images}
    doc = {
        "source": "Yahoo!ショッピング 商品検索API（v3）",
        "credit": CREDIT,
        "creditUrl": CREDIT_URL,
        "updatedAt": today,
        "images": dict(sorted(images.items())),
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {len(images)} images to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
