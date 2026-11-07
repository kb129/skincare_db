#!/usr/bin/env python3
"""data/products.json から GitHub Pages 用の静的 API（_site/）を生成する。

  /v1/index.json             目次（件数・更新日・各ファイルのハッシュ）。アプリはまずここを見る
  /v1/products.json          全商品（アプリが端末に保存する本体）
  /v1/products/{id}.json     商品1件（共有リンク・Web 用）
  /v1/jan/{jan}.json         JAN コードから商品1件（バーコード読み取り用）
  /                          ブラウザで見られる一覧ページ
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

API_VERSION = "v1"


def dump(path: Path, obj) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    path.write_bytes(data)
    return data


def main(src: str = "data/products.json", out: str = "_site") -> int:
    catalog = json.loads(Path(src).read_text(encoding="utf-8"))
    site = Path(out)
    if site.exists():
        shutil.rmtree(site)
    api = site / API_VERSION
    products = catalog["products"]

    body = dump(api / "products.json", catalog)
    for p in products:
        dump(api / "products" / f"{p['id']}.json", p)
        if p.get("jan"):
            dump(api / "jan" / f"{p['jan']}.json", p)

    index = {
        "schemaVersion": catalog["schemaVersion"],
        "apiVersion": API_VERSION,
        "updatedAt": catalog["updatedAt"],
        "count": len(products),
        "brands": sorted({p["brand"] for p in products}),
        "files": {
            "products": {
                "path": "products.json",
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
            },
        },
        "endpoints": {
            "product": "products/{id}.json",
            "jan": "jan/{jan}.json",
        },
    }
    dump(api / "index.json", index)

    shutil.copy("site/index.html", site / "index.html")
    (site / ".nojekyll").write_text("")
    print(f"built {len(products)} products into {site}/{API_VERSION} (products.json {len(body)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
