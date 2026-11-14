#!/usr/bin/env python3
"""dumps/dhc/pages.jsonl（tools/fetch_missing.py dhc で取得）から、DHC の製品を data/products.json に取り込む。

  python3 tools/import_dhc.py            # 取り込む
  python3 tools/import_dhc.py --dry-run  # 一覧だけ

取り込むのは、商品ページに全成分がそのまま載っている化粧品だけ。
医薬部外品（薬用〜）は商品ページに全成分がない（指定成分だけ）ので、取り込まない。
種類は DHC のカテゴリと製品名から決める。迷うもの（ミスト・美容液・ボディ用・マッサージ用・セット・旧製品）は入れない。
"""
import argparse
import json
import re
import sys
import unicodedata

DUMP = "dumps/dhc/pages.jsonl"
CATALOG = "data/products.json"
SKIP_NAME = re.compile(r"^【|ミスト|マッサージ|バーム|セラム|エッセンス|ボディ|ハンド|ネック|アイ|リップ|セット|オイル$|モイスチュアライザー")


def category(dhc_cat: str, name: str) -> str | None:
    if SKIP_NAME.search(name):
        return None
    if dhc_cat == "化粧水・ミスト":
        return "GEL" if "ジェル" in name else "TONER"
    if dhc_cat == "ミルク・ジェル":
        return "GEL" if "ジェル" in name else "EMULSION" if "ミルク" in name else None
    if dhc_cat == "クリーム・オイル":
        return "CREAM" if "クリーム" in name else None
    if dhc_cat == "化粧下地":
        return "BB_CC" if re.search(r"CC|BB", name) else "BASE"
    return None


def ingredients(lines: list[str]) -> str | None:
    for x in lines:
        if x.count("、") >= 8 and not x.endswith("。") and re.match(r"^(全色共通[:：])?\s*[^、。]{1,30}、", x):
            return re.sub(r"^全色共通[:：]\s*", "", x).strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified-at", default="2026-11-14")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    made, seen = [], set()
    with open(DUMP, encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            m = re.match(r"(.+?) \| (.+?)通販のDHC", page["title"])
            g = re.search(r"/goods/(\d+)\.html", page["url"])
            if not m or not g:
                continue
            full_name, dhc_cat = m.groups()
            name = re.sub(r"^DHC\s*", "", unicodedata.normalize("NFKC", full_name)).strip()
            # 名前の後ろの補足（<顔・体用 美容液>、【DHC for MEN ハイライフ】、(化粧下地)）は外す
            name = re.sub(r"\s*(<[^>]*>|【[^】]*】|\(化粧下地\))\s*$", "", name).strip()
            cat = category(dhc_cat, name)
            lines = page["lines"]
            ing = ingredients(lines)
            if not cat or not ing or name in seen:
                continue
            if any("医薬部外品" in l for l in lines if len(l) < 40):
                continue
            seen.add(name)
            text = " ".join(lines)
            p = {
                "id": f"dhc-{g.group(1)}",
                "maker": "DHC",
                "brand": "DHC",
                "name": name,
                "category": cat,
                "quasiDrug": False,
                "jan": None,
                "ingredients": ing,
                "sourceUrl": page["url"],
                "verifiedAt": a.verified_at,
                "amazonAsin": None,
            }
            jan = re.search(r"JANコード[:：]\s*(\d{13})", text)
            if jan:
                p["jan"] = jan.group(1)
            # 「（商品番号：12345）」の次の行が通常価格（税込）。その次はキャンペーン価格なので使わない
            for i, l in enumerate(lines):
                if l == f"（商品番号：{g.group(1)}）" and i + 1 < len(lines):
                    pm = re.fullmatch(r"([\d,]+)円(（税込）)?", lines[i + 1])
                    if pm:
                        p["price"] = {"kind": "STORE", "amount": int(pm.group(1).replace(",", "")), "taxIncluded": True, "sourceUrl": page["url"]}
                        vol = next((x for x in lines[max(0, i - 12):i] if re.fullmatch(r"[\d.]+\s?(mL|ｍL|ml|g|ｇ)", x)), None)
                        if vol:
                            p["price"]["volume"] = unicodedata.normalize("NFKC", vol)
                    break
            if cat in ("BASE", "BB_CC"):
                s = re.search(r"SPF\s?(\d+)\+?\s?[・/／ 　]*\s?PA\s?(\++)", unicodedata.normalize("NFKC", text))
                if s:
                    p["spf"], p["pa"] = int(s.group(1)), s.group(2)
            made.append(p)
    made.sort(key=lambda p: (["TONER", "EMULSION", "GEL", "CREAM", "BASE", "BB_CC"].index(p["category"]), p["name"]))
    for p in made:
        print(f"{p['category']:8} {p['name']}  {p.get('price', {}).get('amount', '-')}円 {p.get('price', {}).get('volume', '')} JAN={p['jan']} {('SPF%s PA%s' % (p['spf'], p['pa'])) if 'spf' in p else ''}")
    print(f"DHC: {len(made)} products")
    if a.dry_run:
        return 0
    with open(CATALOG, encoding="utf-8") as f:
        catalog = json.load(f)
    catalog["products"] = [p for p in catalog["products"] if p.get("maker") != "DHC"] + made
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
