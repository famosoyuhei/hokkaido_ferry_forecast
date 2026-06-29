# Hokkaido Ferry Forecast - Agent Guide

北海道フェリー運航予報システム（稚内⇔利尻島・礼文島）。
本番URL: https://web-production-a628.up.railway.app/

## Context Loading Policy

このルートファイルは、全作業で常時読む最小ルールだけを置く。
詳細は該当ディレクトリの `AGENTS.md` または専門ドキュメントを読む。

- AI社員・自動化仕様: `docs/ai_employees/AGENTS.md`
- 欠航リサーチ・時刻表JSON: `skills/ferry-cancellation-research/AGENTS.md`
- GitHub Actions: `.github/AGENTS.md`
- Flask画面・PWA: `templates/AGENTS.md` と `static/AGENTS.md`

## Always Hard Rules

1. `.db` ファイル、APIキー、シークレットをコミットしない。DBは本番では Railway Volume 管理。
2. JSTを必ず明示する。Railwayの `datetime.now()` はUTCなので、必要時は `Asia/Tokyo` を使う。
3. 欠損した風速・波高・視程を `0` で埋めない。NULLとして保存し、精度計算から除外する。
4. 気象欠航以外（整備運休・季節運休・ダイヤ切り替え）は精度評価に混ぜない。`is_likely_maintenance` で除外する。
5. 便別運航記録は `ferry_status_enhanced` を使う。旧 `ferry_status` を新規実装で使わない。
6. 2026-04-05以前のデータは精度計算に使わない。スクレイパーバグで全便欠航として誤記録されている。
7. モデル閾値はデータ確認後にだけ調整する。誤データでチューニングしない。

## Timetable And Routes

- 航路リストは `jst_utils.get_active_routes_on(date_str)` で取得する。ハードコード禁止。
- 便別時刻は `jst_utils.get_timetable_sailings(route, date_str)` を使う。
- 時刻表JSONは年ハードコード禁止。`heartland_{year}_timetable.json` + 最新年globフォールバックを使う。
- 時刻表にない便を欠航・運航どちらとしても記録しない。
- 2026年の切り替え日をまたぐ処理では必ず当日ダイヤをJSONで確認する。
  - 2026-04-28: 稚内-鴛泊、稚内-香深が2便から3便へ
  - 2026-06-01: 夏ダイヤ開始、沓形-香深便が新設
  - 2026-10-01: 沓形-香深便終了、稚内-香深に鴛泊経由便復活
  - 2026-11-01: 冬ダイヤ、全航路2便へ

### Valid Ferry Keys

港キー: `wakkanai`, `oshidomari`, `kutsugata`, `kafuka`

有効な航路キー:
- `wakkanai_oshidomari` / `oshidomari_wakkanai`
- `wakkanai_kafuka` / `kafuka_wakkanai`
- `oshidomari_kafuka` / `kafuka_oshidomari`
- `kutsugata_kafuka` / `kafuka_kutsugata`（2026-06-01〜2026-09-30のみ）

禁止キー（コード・コメント・テストデータにも書かない）:
- `wakkanai_kutsugata`
- `kutsugata_wakkanai`

## Ferry Risk Logic

`weather_forecast_collector.py` の `calculate_cancellation_risk()` と
`unified_accuracy_tracker.py` の `_calc_risk()` は常に同期する。

```python
if wind >= 35:   score += 70
elif wind >= 30: score += 60
elif wind >= 25: score += 50
elif wind >= 20: score += 35
elif wind >= 15: score += 20
elif wind >= 10: score += 10

if wave >= 4.0:   score += 40
elif wave >= 3.0: score += 30
elif wave >= 2.0: score += 15

if vis < 1.0:   score += 20
elif vis < 3.0: score += 10
```

判定: `score >= 70` HIGH, `>= 40` MEDIUM, `>= 20` LOW, otherwise MINIMAL.

## Flight Forecast Rules

- 利尻空港（RIS/RJER）の滑走路は 07/25。横風計算は必ず `RUNWAY_HEADING_DEG = 70` を使う。
- 01/19、RWY01、RWY19 と混同しない。
- HACは通年の丘珠(OKD)便、ANAは6/1〜9/30のみの新千歳(CTS)便。日付から動的に就航便を取得する。
- 飛行機リスクは風速だけでなく横風成分と視程で判定する。
- 精度検証前に飛行機リスク閾値を変更しない。最低30日分の実運航データ蓄積後に検討する。
- 気象データは鴛泊 `actual_weather` / `weather_forecast` を流用する。

初期リスク閾値:
- `crosswind >= 10.0`: HIGH
- `crosswind >= 7.0`: MEDIUM
- `crosswind >= 4.0`: LOW
- otherwise MINIMAL
- `visibility < 1.6 km`: HIGH
- `visibility < 3.0 km`: MEDIUM

## Accuracy And Sheets Rules

- `predicted_wind` / `predicted_wave` / `predicted_visibility` は予報時点の値だけを保存する。
- `actual_wind` / `actual_wave` / `actual_visibility` は `actual_weather` 由来にする。
- 実測気象から後知恵で再計算したリスクを `predicted_*` に保存しない。
- 予報値と実測値が多数完全一致する場合は `forecast_actual_leakage` としてデータ異常扱い。
- Sheets出力前に明細行から日次指標を再計算し、保存済み集計と照合する。
- `accuracy_fill_auditor.py` は精度監査・Sheets同期後に実行し、永久保存DBとGoogle Sheetsの両方を確認する。
- Sheets確認用の `GOOGLE_SHEETS_API_KEY` または `GOOGLE_SHEETS_BEARER_TOKEN` が未設定なら重大異常として扱う。

## Flask And Railway Rules

- Flask内から同一サーバーのHTTPエンドポイントを呼ばない。内部チェックはSQLiteを直接クエリする。
- `subprocess` でスクリプトを起動する時は `sys.executable` と絶対パスを使う。
- push後にRailwayを確認する場合は最低5分待ち、先に `/api/stats` などで応答確認する。
- `forecast_dashboard.py` 変更時は `/api/stats` エンドポイントの動作を確認する。

## Commit Checks

Pythonを編集したら:

```bash
python -m py_compile <edited_file>.py
```

コミット前の禁止パターン確認:

```bash
grep -rn "wakkanai_kutsugata\|kutsugata_wakkanai" *.py
grep -rn "heartland_20[0-9][0-9]_timetable" *.py
grep -rn "_load_2026_timetable\|_TIMETABLE_2026" *.py
grep -rn "ferry_routes\s*=\s*\[" *.py
grep -rn "runway.*01\|runway.*19\|RWY01\|RWY19" *.py
grep -rn "flight_routes\s*=\s*\[" *.py
grep -rn "rishiri_flight_20[0-9][0-9]_timetable" *.py
```

## Database Paths

本番:
- `/data/ferry_weather_forecast.db`
- `/data/heartland_ferry_real_data.db`

ローカル:
- カレントディレクトリ
- `os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')` で切り替える。

## Main Scripts

- `weather_forecast_collector.py`: 海上気象予報取得
- `actual_weather_collector.py`: 海上気象実測取得
- `improved_ferry_collector.py`: フェリー運航記録取得
- `unified_accuracy_tracker.py`: 予報精度監査
- `accuracy_sheet_exporter.py`: Sheets全面監査用データ出力
- `accuracy_fill_auditor.py`: 永久保存DB・Sheets充填監査
- `issue_prompt_composer.py`: 問題点整理・修正依頼生成
