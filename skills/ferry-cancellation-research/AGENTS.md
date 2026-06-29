# Ferry Cancellation Research Skill Guide

欠航リサーチ、時刻表JSON、航路・便別データを扱う時だけ読む。

## Source Of Truth

- 2026年フェリー時刻表の機械処理正ソース:
  `references/heartland_2026_timetable.json`
- 飛行機時刻表:
  `references/rishiri_flight_{year}_timetable.json`
- 人間向け資料よりJSONを優先する。

## Ferry Timetable Rules

- `schedules` を `start_date <= target_date <= end_date` で検索して当日ダイヤを決定する。
- 時刻表に存在しない便を欠航・運航どちらとしても記録しない。
- 沓形-香深便は 2026-06-01〜2026-09-30 以外には存在しない。
- 切り替え当日は新ダイヤで扱う。
- 便数が変わる日の取得件数差は正常であり、即 `parser_error` にしない。

## 2026 Change Dates

| 日付 | 変化内容 |
|---|---|
| 2026-04-28 | 稚内-鴛泊・稚内-香深が1日2便から3便へ |
| 2026-06-01 | 夏ダイヤ開始、沓形-香深便が新設 |
| 2026-10-01 | 沓形-香深便終了、稚内-香深に鴛泊経由便が復活 |
| 2026-11-01 | 冬ダイヤ、全航路1日2便へ |

## Valid Ferry Keys

- `wakkanai_oshidomari` / `oshidomari_wakkanai`
- `wakkanai_kafuka` / `kafuka_wakkanai`
- `oshidomari_kafuka` / `kafuka_oshidomari`
- `kutsugata_kafuka` / `kafuka_kutsugata`

禁止キー:
- `wakkanai_kutsugata`
- `kutsugata_wakkanai`

## Flight Rules

- RIS/RJERの滑走路は07/25。横風計算は `RUNWAY_HEADING_DEG = 70`。
- HACは通年の丘珠便、ANAは6/1〜9/30のみの新千歳便。
- 飛行機リスクは横風成分と視程を使う。風速のみで判定しない。
