# skincare_db

Android アプリ「肌ログ最適化」が使う商品カタログ（化粧水・乳液・ジェル・クリーム）。GitHub Pages で配信します。

- データ: `public/products.json`
- 配信 URL: <https://kb129.github.io/skincare_db/products.json>（一覧ページ: <https://kb129.github.io/skincare_db/>）
- `main` に push すると検証のあと自動で公開されます（`.github/workflows/pages.yml`）

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
python3 scripts/validate_catalog.py public/products.json
```
