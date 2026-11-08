#!/usr/bin/env python3
"""data/products.json の形式チェック。CI と手元の両方で使う。"""
import json
import re
import sys

CATEGORIES = {"TONER", "EMULSION", "GEL", "CREAM"}
REQUIRED = {"id", "brand", "name", "category", "quasiDrug", "ingredients", "sourceUrl", "verifiedAt"}


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
    errors = []
    if catalog.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
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
        # 区切りは「、」「,」「，」のいずれか。アベンヌ ウオーター（温泉水、窒素）のように短い全成分もある
        if len(p["ingredients"]) < 5 or not any(sep in p["ingredients"] for sep in ("、", ",", "，")):
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
        asin = p.get("amazonAsin")
        if asin is not None and not re.fullmatch(r"[A-Z0-9]{10}", asin):
            errors.append(f"{where}: amazonAsin must be 10 chars")
    for e in errors:
        print("ERROR:", e)
    print(f"{len(seen)} products checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/products.json"))
