#!/usr/bin/env python3
"""data/products.json の形式チェック。CI と手元の両方で使う。"""
import json
import re
import sys

# スキンケア: TONER/EMULSION/GEL/CREAM、ベース（下地）: BASE/BB_CC/TONE_UP
CATEGORIES = {"TONER", "EMULSION", "GEL", "CREAM", "BASE", "BB_CC", "TONE_UP"}
REQUIRED = {"id", "maker", "brand", "name", "category", "quasiDrug", "ingredients", "sourceUrl", "verifiedAt"}


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
    errors = []
    if catalog.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    # アフィリエイトの ID（未設定は null）。Amazon は日本のトラッキングID（末尾 -22）、楽天はアフィリエイトID（16進4組）
    aff = catalog.get("affiliate") or {}
    if not isinstance(aff, dict):
        errors.append("affiliate must be an object")
        aff = {}
    tag = aff.get("amazonTag")
    if tag is not None and not re.fullmatch(r"[A-Za-z0-9_-]+-22", tag):
        errors.append("affiliate.amazonTag must look like xxxx-22")
    rid = aff.get("rakutenAffiliateId")
    if rid is not None and not re.fullmatch(r"[0-9a-f]{8}\.[0-9a-f]{8}\.[0-9a-f]{8}\.[0-9a-f]{8}", rid):
        errors.append("affiliate.rakutenAffiliateId must look like 1a2b3c4d.5e6f7a8b.9c0d1e2f.3a4b5c6d")
    # 未収録製品のリクエスト先（Google フォームの事前入力。未設定は null）。fields は brand/name/note → entry.xxx
    form = catalog.get("requestForm")
    if form is not None:
        if not isinstance(form, dict) or not str(form.get("url", "")).startswith("https://docs.google.com/forms/"):
            errors.append("requestForm.url must be a Google Forms URL (https://docs.google.com/forms/...)")
        fields = (form or {}).get("fields") or {}
        if not fields.get("name") or any(not re.fullmatch(r"entry\.\d+", v) for v in fields.values()):
            errors.append("requestForm.fields must map brand/name/note to entry.<number> (name is required)")
    seen = set()
    jans = set()
    for i, p in enumerate(catalog.get("products", [])):
        where = f"products[{i}] ({p.get('id', '?')})"
        missing = REQUIRED - p.keys()
        if missing:
            errors.append(f"{where}: missing {sorted(missing)}")
            continue
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", p["id"]):
            errors.append(f"{where}: id must be kebab-case ascii")
        if p["id"] in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(p["id"])
        if p["category"] not in CATEGORIES:
            errors.append(f"{where}: unknown category {p['category']}")
        if not isinstance(p["quasiDrug"], bool):
            errors.append(f"{where}: quasiDrug must be boolean")
        # 区切りは「、」「,」「，」「・」（コーセー）「､」（セザンヌ）のいずれか。アベンヌ ウオーター（温泉水、窒素）のように短い全成分もある
        if len(p["ingredients"]) < 5 or not any(sep in p["ingredients"] for sep in ("、", ",", "，", "・", "､")):
            errors.append(f"{where}: ingredients look incomplete")
        if not p["sourceUrl"].startswith("https://"):
            errors.append(f"{where}: sourceUrl must be https")
        if p.get("jan") is not None:
            if not re.fullmatch(r"\d{13}", p["jan"]):
                errors.append(f"{where}: jan must be 13 digits")
            elif p["jan"] in jans:
                errors.append(f"{where}: duplicate jan {p['jan']}")
            jans.add(p["jan"])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["verifiedAt"]):
            errors.append(f"{where}: verifiedAt must be YYYY-MM-DD")
        spf = p.get("spf")
        if spf is not None and (not isinstance(spf, (int, float)) or not 0 < spf <= 50):
            errors.append(f"{where}: spf must be a number in (0, 50] or null")
        pa = p.get("pa")
        if pa is not None and not re.fullmatch(r"\+{1,4}", pa):
            errors.append(f"{where}: pa must be + .. ++++ or null")
        shades = p.get("shades", [])
        if not isinstance(shades, list) or not all(isinstance(x, str) and x for x in shades):
            errors.append(f"{where}: shades must be a list of non-empty strings")
        price = p.get("price")
        if price is not None:
            if price.get("kind") not in ("SRP", "STORE", "OPEN"):
                errors.append(f"{where}: price.kind must be SRP, STORE or OPEN")
            elif price["kind"] != "OPEN" and not (isinstance(price.get("amount"), int) and price["amount"] > 0):
                errors.append(f"{where}: price.amount must be a positive integer (yen)")
            if not str(price.get("sourceUrl", "")).startswith("https://"):
                errors.append(f"{where}: price.sourceUrl must be https")
        asin = p.get("amazonAsin")
        if asin is not None and not re.fullmatch(r"[A-Z0-9]{10}", asin):
            errors.append(f"{where}: amazonAsin must be 10 chars")
    for e in errors:
        print("ERROR:", e)
    print(f"{len(seen)} products checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/products.json"))
