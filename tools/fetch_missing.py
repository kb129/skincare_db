#!/usr/bin/env python3
"""未収録ブランドの公式サイトから、全成分が載っている商品ページをまとめて取る（日本国内の PC で実行する）。

  python3 tools/fetch_missing.py              # tools/missing_targets.json の全部
  python3 tools/fetch_missing.py dhc muji     # 指定したものだけ
  python3 tools/fetch_missing.py --list       # 一覧

取得先ごとに dumps/<key>/pages.jsonl（全成分を含むページ）と visited.txt（巡回の記録）を作る。
終わったら dumps/ を push すれば、取り込み（全成分の転記）はこちらで行う。

約束ごと（tools/fetch_site_pages.py が守る）
- robots.txt で禁止されたページは取らない。Crawl-delay の指定があればそれ以上あける（既定 1.5 秒に1ページ）。
- 403 / 429 / 503 が続いたらそのサイトはやめる。自動アクセスを拒否しているサイトを、回避して取ることはしない。
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*", help="取得先の key（空なら全部）")
    ap.add_argument("--targets", default=str(HERE / "missing_targets.json"))
    ap.add_argument("--out", default="dumps")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    targets = json.loads(Path(a.targets).read_text(encoding="utf-8"))["targets"]
    if a.list:
        for t in targets:
            print(f"{t['key']:15} {t['brand']:12} {t['start']}")
        return 0
    chosen = [t for t in targets if not a.keys or t["key"] in a.keys]
    unknown = set(a.keys) - {t["key"] for t in targets}
    if unknown:
        print(f"不明な key: {', '.join(sorted(unknown))}（--list で一覧）", file=sys.stderr)
        return 2
    summary = []
    for t in chosen:
        out = Path(a.out) / t["key"]
        print(f"\n=== {t['brand']}（{t['start']}）", file=sys.stderr)
        cmd = [sys.executable, str(HERE / "fetch_site_pages.py"), t["start"], str(out), "--max-pages", str(t.get("maxPages", 600))]
        if t.get("sitemap"):
            cmd += ["--sitemap", t["sitemap"]]
        if t.get("match"):
            cmd += ["--match", t["match"]]
        if t.get("skip"):
            cmd += ["--skip", t["skip"]]
        started = time.time()
        rc = subprocess.call(cmd)
        pages = out / "pages.jsonl"
        saved = sum(1 for _ in pages.open(encoding="utf-8")) if pages.exists() else 0
        summary.append((t["brand"], saved, rc, int(time.time() - started)))
    print("\n結果", file=sys.stderr)
    for brand, saved, rc, sec in summary:
        print(f"  {brand:12} 全成分ありのページ {saved:4} 件  {sec // 60}分{'' if rc == 0 else '（途中で終了）'}", file=sys.stderr)
    print(f"\n{a.out}/ を git add して push してください。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
