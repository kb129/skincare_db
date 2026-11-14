#!/usr/bin/env python3
"""公式サイトの商品ページ（全成分が載っているページ）を、ページの文字だけで保存する。

海外IPからアクセスできないサイト（例: ORBIS）を、日本国内の自分の PC から取得するためのツール。
標準ライブラリだけで動く（Python 3.8+）。1.5秒に1ページのゆっくりした速度で巡回する。

使い方:
  # おすすめ: サイトマップから商品ページだけを取る（記事ページを巡回しない）
  python3 fetch_site_pages.py https://www.orbis.co.jp/ orbis_dump --sitemap auto --match '/small/[0-9]+/'
  # サイトマップがないとき: リンクをたどる（記事ページなどは --skip で飛ばす）
  python3 fetch_site_pages.py https://www.orbis.co.jp/ orbis_dump --skip '/archives/' --max-pages 1500
出力:
  orbis_dump/pages.jsonl   全成分を含むページ1件=1行（url, title, lines=ページの文字を行ごとに）
  orbis_dump/visited.txt   巡回したURLとステータス（確認用）
"""
import argparse, gzip, json, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from collections import deque
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|webp|svg|css|js|pdf|zip|mp4|ico|woff2?)(\?|$)", re.I)
# 商品・カテゴリっぽいURLを先に巡回する（見つかりやすくするため）
PRIORITY = re.compile(r"(product|item|goods|detail|skincare|base|make|lotion|milk|category|lineup)", re.I)
# 買い物かご・ログイン・検索結果の大量ページなどは巡回しない
AVOID = re.compile(r"(cart|login|logout|mypage|member|order|favorite|review|search\?|sort=|page=\d{2,}|javascript:|mailto:|tel:)", re.I)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.lines, self.title, self._buf, self._skip, self._in_title = [], [], "", [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in ("br", "p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "dt", "dd", "section", "table"):
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in ("p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "dt", "dd", "section", "table"):
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        self._buf.append(data)

    def _flush(self):
        s = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if s:
            self.lines.append(s)
        self._buf = []


def safe_url(url):
    """日本語などを含むURLを、送れる形（%エンコード）にする。"""
    p = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(p.query, safe="=&%/:+,;-._~")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, query, ""))


def fetch(url):
    req = urllib.request.Request(safe_url(url), headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.5"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        charset = r.headers.get_content_charset() or "utf-8"
        return r.status, r.geturl(), raw.decode(charset, errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start_url")
    ap.add_argument("out_dir")
    ap.add_argument("--max-pages", type=int, default=600)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--sitemap", help="サイトマップのURL。auto なら robots.txt と /sitemap.xml から探す")
    ap.add_argument("--match", help="サイトマップのうち、このパターン（正規表現）に合うURLだけ取る。巡回では優先して回る")
    ap.add_argument("--skip", help="巡回しないURLのパターン（正規表現）。例: '/archives/'")
    ap.add_argument("--stop-after-blocks", type=int, default=5, help="403/429/503 がこの回数続いたら、そのサイトはやめる（自動アクセスの拒否を回避しない）")
    a = ap.parse_args()
    # robots.txt を守る（巡回してよいページか、待ち時間の指定があるか）
    root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(a.start_url))
    robots = urllib.robotparser.RobotFileParser()
    try:
        _, _, txt = fetch(root + "/robots.txt")
        robots.parse(txt.splitlines())
    except Exception:
        robots.parse([])  # robots.txt がなければ制限なし
    if robots.crawl_delay("*"):
        a.delay = max(a.delay, float(robots.crawl_delay("*")))
        print(f"robots.txt: {a.delay}秒に1ページ", file=sys.stderr)
    match = re.compile(a.match) if a.match else None
    skip = re.compile(a.skip) if a.skip else None
    host = urllib.parse.urlparse(a.start_url).netloc
    import os
    os.makedirs(a.out_dir, exist_ok=True)
    out = open(os.path.join(a.out_dir, "pages.jsonl"), "w", encoding="utf-8")
    log = open(os.path.join(a.out_dir, "visited.txt"), "w", encoding="utf-8")
    seen, hi, lo, saved, n = {a.start_url}, deque([a.start_url]), deque(), 0, 0
    crawl = True
    if a.sitemap:
        urls = sitemap_urls(a.start_url, a.sitemap, a.delay, log)
        picked = [u for u in urls if not match or match.search(u)]
        print(f"sitemap: {len(urls)} URLs, {len(picked)} match", file=sys.stderr)
        if picked:
            hi, seen, crawl = deque(picked), set(picked), False  # 商品ページだけ取る（リンクはたどらない）
    blocked = 0
    while (hi or lo) and n < a.max_pages:
        url = hi.popleft() if hi else lo.popleft()
        if not robots.can_fetch("*", safe_url(url)):
            log.write(f"ROBOTS\t{url}\n"); continue
        n += 1
        try:
            status, final, html = fetch(url)
            blocked = 0
        except urllib.error.HTTPError as e:
            log.write(f"ERR\t{url}\t{e}\n"); log.flush()
            if e.code in (403, 429, 503):
                blocked += 1
                if blocked >= a.stop_after_blocks:
                    print(f"\n{e.code} が{blocked}回続いたので中止します（このサイトは自動アクセスを受け付けていません）", file=sys.stderr)
                    break
            time.sleep(a.delay); continue
        except Exception as e:  # 失敗しても続ける
            log.write(f"ERR\t{url}\t{e}\n"); log.flush(); time.sleep(a.delay); continue
        log.write(f"{status}\t{url}\n"); log.flush()
        p = Page(); p.feed(html); p._flush()
        if any("成分" in l for l in p.lines):
            out.write(json.dumps({"url": final, "title": p.title.strip(), "lines": p.lines}, ensure_ascii=False) + "\n")
            out.flush(); saved += 1
        for href in (p.links if crawl else []):
            if "{" in href:  # テンプレートの書きかけ（{{...}}）は飛ばす
                continue
            u = urllib.parse.urljoin(final, href).split("#")[0]
            pu = urllib.parse.urlparse(u)
            if pu.scheme not in ("http", "https") or pu.netloc != host or u in seen or SKIP_EXT.search(u) or AVOID.search(u):
                continue
            if skip and skip.search(u):
                continue
            seen.add(u)
            (hi if (match.search(u) if match else PRIORITY.search(pu.path)) else lo).append(u)
        print(f"\r{n} pages visited, {saved} with ingredients", end="", file=sys.stderr)
        time.sleep(a.delay)
    print(f"\ndone: {n} visited, {saved} saved -> {a.out_dir}/pages.jsonl", file=sys.stderr)


def sitemap_urls(start_url, sitemap, delay, log):
    """サイトマップ（入れ子のサイトマップも）から、ページのURLを集める。"""
    root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(start_url))
    todo = []
    if sitemap == "auto":
        try:
            _, _, robots = fetch(root + "/robots.txt")
            todo = [l.split(":", 1)[1].strip() for l in robots.splitlines() if l.lower().startswith("sitemap:")]
        except Exception as e:
            log.write(f"ERR\t{root}/robots.txt\t{e}\n")
        if not todo:
            todo = [root + "/sitemap.xml"]
    else:
        todo = [sitemap]
    pages, done = [], set()
    while todo:
        sm = todo.pop(0)
        if sm in done:
            continue
        done.add(sm)
        try:
            _, _, xml = fetch(sm)
        except Exception as e:
            log.write(f"ERR\t{sm}\t{e}\n"); continue
        log.write(f"SITEMAP\t{sm}\n")
        locs = [x.strip() for x in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)]
        if "<sitemapindex" in xml:
            todo += locs
        else:
            pages += locs
        time.sleep(delay)
    return list(dict.fromkeys(p.replace("&amp;", "&") for p in pages))


if __name__ == "__main__":
    main()
