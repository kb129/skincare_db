# skincare_db

Android アプリ「肌ログ最適化」が使う商品カタログ（化粧水・乳液・ジェル・クリーム）。GitHub Pages で配信します。

- 元データ: `data/products.json`（編集するのはこのファイルだけ）
- `main` にマージすると、検証 → 静的 API の生成（`scripts/build_api.py`）→ GitHub Pages へ公開、が自動で行われます
- 一覧ページ: <https://kb129.github.io/skincare_db/>

## API（静的ファイル）
ベース URL: `https://kb129.github.io/skincare_db/v1/`

| パス | 内容 | 用途 |
|---|---|---|
| `index.json` | 件数・更新日・ブランド一覧・`products.json` の SHA-256 とサイズ | アプリが起動時に最初に取得（数百バイト）。ハッシュが変わったときだけ本体を取りに行く |
| `products.json` | 全商品（`schemaVersion`, `updatedAt`, `products[]`） | アプリが端末に保存する本体。取得後に `index.json` のハッシュで検証 |
| `products/{id}.json` | 商品1件 | 共有リンク・Web 表示 |
| `jan/{jan}.json` | JAN コードから商品1件（JAN がある商品のみ） | バーコード読み取り（存在しなければ 404） |

設計の方針
- **パスでバージョン管理**：互換性のない変更は `/v2/` を追加し、`/v1/` は古いアプリのために残す。`v1` の中での変更は「任意項目の追加」だけにする
- **目次 → 本体の2段階**：GitHub Pages は約10分キャッシュされ、細かい制御ができないため、小さな目次のハッシュで更新を判定する
- **全件1ファイル**：数百件までは1ファイル（1件あたり約1.4KB、gzip でさらに小さい）が最速。数千件を超えたら `index.json` の `files` にカテゴリ別などの分割ファイルを追加する
- CORS は GitHub Pages が `Access-Control-Allow-Origin: *` を返すため、Web からも利用できる

## データのルール
- **全成分はメーカー公式サイトの掲載内容をそのまま転記する。** 記憶や口コミサイト・通販サイトからの転記はしない
- `sourceUrl` に公式ページ、`verifiedAt` に確認日を入れる
- 成分が別ページにある場合は `ingredientsSourceUrl` も入れる
- 医薬部外品は `quasiDrug: true`。「有効成分：」「その他の成分：」の区分は改行で残す
- 分量が公開されている場合（ちふれ等）は `ingredientAmounts` に残す
- `amazonAsin` は将来のアフィリエイト用。確認できたものだけ入れる

## 項目

| 項目 | 必須 | 内容 |
|---|---|---|
| `id` | ✓ | 英小文字とハイフン。変更しない（アプリが登録済みの判定に使う） |
| `maker` | ✓ | 製造販売元の会社名（例：花王）。アプリでメーカー別に分けて表示する |
| `brand`, `name` | ✓ | ブランド名・商品名 |
| `category` | ✓ | `TONER`（化粧水）/ `EMULSION`（乳液）/ `GEL` / `CREAM` |
| `quasiDrug` | ✓ | 医薬部外品か |
| `jan` | | JAN コード（13桁）。将来のバーコード読み取り用 |
| `ingredients` | ✓ | 全成分（公式表記のまま） |
| `sourceUrl`, `verifiedAt` | ✓ | 出典と確認日 |
| `ingredientsSourceUrl`, `ingredientAmounts`, `amazonAsin` | | 任意 |

`schemaVersion` を上げるとアプリの古い版は読み込まなくなるので、項目の追加は任意項目で行います。

## 検証
```bash
python3 scripts/validate_catalog.py data/products.json
python3 scripts/build_api.py data/products.json _site   # 生成物の確認
```

## 収録状況（2026-11-07）
収録: キュレル、ソフィーナ、アルブラン（花王）／肌ラボ、メラノCC（ロート）／エリクシール、dプログラム、イハダ、アクアレーベル（資生堂）／ミノン／ちふれ／ナチュリエ／ファンケル／アクセーヌ／アベンヌ／セタフィル

未収録（公式サイトから取得できなかったもの）

| ブランド | 理由 |
|---|---|
| 無印良品 | 公式サイトがメンテナンス中 |
| オルビス、DHC、ラロッシュポゼ | 自動アクセスを拒否（HTTP 503 / 403） |
| 雪肌精・コーセー各ブランド、なめらか本舗 | 公式サイトが別ドメイン（maison.kose.co.jp など）に移っており未対応 |
| アクアレーベルの化粧水・乳液、スペシャルジェルクリーム EX の一部 | 商品ページが見つからない、または別サイトへ転送される |
